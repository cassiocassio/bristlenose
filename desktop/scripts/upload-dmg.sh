#!/usr/bin/env bash
# Publish a Developer-ID `.dmg`: verify it, upload it, swap it in atomically,
# and repoint the stable URL at it.
#
# Replaces a bare `scp Bristlenose-X.Y.Z.dmg host:.../Bristlenose.dmg`, which
# had two defects the 0.24.0 publish exposed:
#
#   1. It wrote DIRECTLY over the live file, so for the ~15 minutes the transfer
#      took, every visitor downloading got a truncated disk image. No error, no
#      way to know, and nobody watching at 2am.
#   2. Nothing verified what landed. A 644 MB transfer over a domestic uplink to
#      shared hosting is exactly where a truncated or corrupted upload happens,
#      and a broken .dmg fails silently — people just get an image that won't
#      mount and don't write in.
#
# So: stage under a temp name IN THE TARGET DIRECTORY, verify the bytes that
# actually arrived, then `mv`. The staging name must be in the same directory
# because `mv` is only atomic within a filesystem — staging in ~/tmp and moving
# across would degrade to copy+unlink and reopen the very window this closes.
#
# The stable URL is a REDIRECT to the versioned file, not a copy or a symlink.
# See docs/design-dmg-build.md § Publishing for why both URLs exist and why a
# symlink is the wrong tool (Apache follows it to read bytes, but the browser
# names the download from the request path, so the file in someone's Downloads
# folder would still be the anonymous `Bristlenose.dmg`).
#
# Usage:
#   desktop/scripts/upload-dmg.sh [--dry-run] [--keep N]
#
# Configuration — the remote is NOT hardcoded, deliberately. This is a public
# repo and the target is a shared host; committing `user@host:/home/user/...`
# would disclose the account and path permanently in git history, and neither
# the PreToolUse leak scan nor the commit-msg hook covers those patterns. Set:
#   BRISTLENOSE_DMG_REMOTE="host:/path/to/site/dmg"      (env), or
#   desktop/scripts/.ship-local.conf                      (gitignored)
#
# Exit codes:
#   0  Published (or a clean dry-run).
#   1  Failed — nothing was swapped; the live download is untouched.
#   2  Usage / not configured.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$ROOT/desktop/build"

# ---------------------------------------------------------------------------
# Pure decision helpers. Kept above the main body and free of I/O so
# test-upload-dmg.sh can source this file and exercise them without a network,
# a remote host, or a 644 MB artefact.
# ---------------------------------------------------------------------------

# swap_decision <local-sha> <remote-sha> -> "swap" | "abort: <reason>"
#
# The empty-vs-empty case is the one that matters and the reason this is a
# function rather than an inline `[ "$a" = "$b" ]`. `ssh host 'shasum …'` inside
# a command substitution DISCARDS ssh's exit status: if the remote lacks shasum
# (127), or the path is wrong, or a shared host prints a MOTD banner over
# stdout, the value comes back empty. If the local side also failed, `"" = ""`
# compares EQUAL and a bare test would cheerfully swap in an unverified file.
# Assert we measured something before believing the comparison.
swap_decision() {
    local local_sha="${1:-}" remote_sha="${2:-}"
    if [ "${#local_sha}" -ne 64 ]; then
        echo "abort: local hash is not a sha256 (got ${#local_sha} chars)"; return 0
    fi
    if [ "${#remote_sha}" -ne 64 ]; then
        echo "abort: remote hash is not a sha256 (got ${#remote_sha} chars) — ssh, path, or a login banner on stdout"; return 0
    fi
    if [ "$local_sha" != "$remote_sha" ]; then
        echo "abort: uploaded bytes differ from the local artefact"; return 0
    fi
    echo "swap"
}

# retention_plan <keep> <name>... -> names to delete, newest-version-first input
#
# `deploy.sh` carries `--filter='protect dmg/'`, so rsync never deletes anything
# from that directory — retention is this script's job or it is nobody's, and
# the directory grows by ~644 MB per cut against a shared-hosting quota.
retention_plan() {
    local keep="$1"; shift
    local n=0 name
    for name in "$@"; do
        n=$((n + 1))
        [ "$n" -gt "$keep" ] && echo "$name"
    done
    return 0
}

# Sourced by the test? Everything below is I/O; stop here.
[ "${UPLOAD_DMG_SOURCE_ONLY:-0}" = "1" ] && return 0

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DRY_RUN=0
KEEP=3
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --keep) KEEP="$2"; shift ;;
        *) echo "usage: $(basename "$0") [--dry-run] [--keep N]" >&2; exit 2 ;;
    esac
    shift
done

[ -f "$SCRIPT_DIR/.ship-local.conf" ] && . "$SCRIPT_DIR/.ship-local.conf"
REMOTE="${BRISTLENOSE_DMG_REMOTE:-}"
if [ -z "$REMOTE" ]; then
    echo "not configured: set BRISTLENOSE_DMG_REMOTE (host:/path/to/dmg) in the" >&2
    echo "environment or in desktop/scripts/.ship-local.conf (gitignored)." >&2
    exit 2
fi
REMOTE_HOST="${REMOTE%%:*}"
REMOTE_DIR="${REMOTE#*:}"

VERSION="$(sed -n 's/^__version__ *= *"\(.*\)"/\1/p' "$ROOT/bristlenose/__init__.py")"
# Validated, not merely read — everything below interpolates it into a command
# the REMOTE shell re-parses. A strict version shape makes that provably safe
# without quoting gymnastics. (Local paths are a different matter: this repo's
# worktrees are named `bristlenose_branch <name>/`, with a space.)
case "$VERSION" in
    [0-9]*.[0-9]*.[0-9]*) : ;;
    *) echo "refusing to publish: unexpected version shape '$VERSION'" >&2; exit 1 ;;
esac

DMG_NAME="Bristlenose-$VERSION.dmg"
DMG_PATH="$BUILD_DIR/$DMG_NAME"
STAGING=".upload-$DMG_NAME.part"   # dot-prefixed: not served while in flight
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=15 -o ServerAliveCountMax=4)

say() { printf '\n\033[1m==>\033[0m %s\n' "$1"; }
ok()  { printf '    \033[32m✓\033[0m %s\n' "$1"; }
die() { printf '    \033[31m✗\033[0m %s\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Resolve strictly by version, and gate on shippability
# ---------------------------------------------------------------------------
say "Publish $DMG_NAME"
[ -f "$DMG_PATH" ] || die "no such artefact: $DMG_PATH (cut one with build-dmg.sh)"

# A PRECONDITION, not a sibling step. Every check below this line verifies
# TRANSPORT — that the bytes arrived intact. None of them would notice that the
# artefact is unnotarised, which is exactly the 0.24.0 near-miss: a complete,
# correctly-sized, correctly-hashed image that every Mac would have refused.
"$SCRIPT_DIR/check-dmg-shippable.sh" "$DMG_PATH" \
    || die "refusing to upload — the artefact is not shippable (see above)"

LOCAL_SHA="$(shasum -a 256 "$DMG_PATH" | cut -d' ' -f1)"
ok "local sha256 ${LOCAL_SHA:0:12}…"

if [ "$DRY_RUN" = "1" ]; then
    say "Dry run — plan only"
    echo "    stage    $REMOTE_DIR/$STAGING"
    echo "    verify   remote sha256 == $LOCAL_SHA"
    echo "    chmod    644"
    echo "    swap     mv -> $REMOTE_DIR/$DMG_NAME"
    echo "    redirect /dmg/Bristlenose.dmg -> /dmg/$DMG_NAME"
    echo "    retain   newest $KEEP versioned artefacts"
    exit 0
fi

# ---------------------------------------------------------------------------
# 2. Upload to a staging name in the TARGET directory
# ---------------------------------------------------------------------------
# Trap-clean the staging file on ANY non-zero exit. Nothing else ever will:
# deploy.sh protects dmg/ from rsync --delete, so a failed run would otherwise
# leave ~644 MB on a shared host permanently, once per failure.
cleanup_staging() {
    ssh "${SSH_OPTS[@]}" "$REMOTE_HOST" "rm -f '$REMOTE_DIR/$STAGING'" 2>/dev/null || true
}
trap 'rc=$?; [ "$rc" -ne 0 ] && cleanup_staging; exit $rc' EXIT

say "Upload"
ssh "${SSH_OPTS[@]}" "$REMOTE_HOST" true \
    || die "cannot reach the host over ssh (BatchMode: is the agent loaded?)"

# rsync over scp for --partial: a dropped connection resumes instead of
# restarting 644 MB from zero, and shared-host idle timeouts mid-transfer are
# routine. --inplace targets the staging name, never the live file.
rsync -e "ssh ${SSH_OPTS[*]}" --partial --inplace --progress \
    "$DMG_PATH" "$REMOTE_HOST:$REMOTE_DIR/$STAGING" \
    || die "upload failed"
ok "uploaded to $STAGING"

# ---------------------------------------------------------------------------
# 3. Verify what actually landed, then swap
# ---------------------------------------------------------------------------
say "Verify + swap"
REMOTE_SHA="$(ssh "${SSH_OPTS[@]}" -n "$REMOTE_HOST" \
    "shasum -a 256 '$REMOTE_DIR/$STAGING' 2>/dev/null | cut -d' ' -f1" | tr -d '[:space:]')"

DECISION="$(swap_decision "$LOCAL_SHA" "$REMOTE_SHA")"
[ "$DECISION" = "swap" ] || die "${DECISION#abort: }"
ok "remote sha256 matches"

# chmod BEFORE the rename. Writing a new file creates a NEW inode, whose mode is
# 0666 & ~umask rather than the mode the old live file had — on a host with a
# tightened umask that publishes a 0600 file and the download 403s. The fix for
# a truncated-download bug would otherwise introduce a fresh way to break the
# download, on the first ship, in the dark.
ssh "${SSH_OPTS[@]}" "$REMOTE_HOST" \
    "chmod 644 '$REMOTE_DIR/$STAGING' && mv -f '$REMOTE_DIR/$STAGING' '$REMOTE_DIR/$DMG_NAME'" \
    || die "swap failed — the live download is unchanged"
ok "swapped in atomically"

# ---------------------------------------------------------------------------
# 4. Repoint the stable URL
# ---------------------------------------------------------------------------
# A redirect, not a symlink or a copy: browsers name a download from the FINAL
# url after redirects, so the file that lands in someone's Downloads folder
# carries its version. Rollback is repointing this one line at a previous
# versioned file — no re-upload, which is why there's no separate .prev.
say "Redirect"
HT="$(mktemp "${TMPDIR:-/tmp}/bn-htaccess.XXXXXX")"
trap 'rc=$?; rm -f "$HT"; [ "$rc" -ne 0 ] && cleanup_staging; exit $rc' EXIT
cat > "$HT" <<EOF
# Generated by desktop/scripts/upload-dmg.sh — do not edit by hand.
# /dmg/Bristlenose.dmg is the permalink handed out in posts and on the site;
# it always resolves to the current alpha. Rollback = point it at an older file.
Redirect 302 /dmg/Bristlenose.dmg /dmg/$DMG_NAME
EOF
rsync -e "ssh ${SSH_OPTS[*]}" "$HT" "$REMOTE_HOST:$REMOTE_DIR/.htaccess.part" || die "redirect upload failed"
ssh "${SSH_OPTS[@]}" "$REMOTE_HOST" \
    "chmod 644 '$REMOTE_DIR/.htaccess.part' && mv -f '$REMOTE_DIR/.htaccess.part' '$REMOTE_DIR/.htaccess'" \
    || die "redirect swap failed"
ok "/dmg/Bristlenose.dmg → /dmg/$DMG_NAME"

# ---------------------------------------------------------------------------
# 5. Retention
# ---------------------------------------------------------------------------
say "Retention"
REMOTE_LIST="$(ssh "${SSH_OPTS[@]}" -n "$REMOTE_HOST" \
    "ls -1 '$REMOTE_DIR' 2>/dev/null | grep '^Bristlenose-.*\.dmg$' | sort -t- -k2 -Vr" || true)"
# shellcheck disable=SC2046
DOOMED="$(retention_plan "$KEEP" $(printf '%s ' $REMOTE_LIST))"
if [ -n "$DOOMED" ]; then
    while IFS= read -r victim; do
        [ -n "$victim" ] || continue
        ssh "${SSH_OPTS[@]}" "$REMOTE_HOST" "rm -f '$REMOTE_DIR/$victim'" && ok "reaped $victim"
    done <<< "$DOOMED"
else
    ok "nothing to reap (keeping newest $KEEP)"
fi

trap - EXIT
rm -f "$HT"

cat <<EOF

──────────────────────────────────────────────────────────────
✓ published  ·  $DMG_NAME  ·  $(du -h "$DMG_PATH" | cut -f1)
  stable    https://bristlenose.app/dmg/Bristlenose.dmg
  versioned https://bristlenose.app/dmg/$DMG_NAME
  sha256    $LOCAL_SHA

  Next: deploy the website so the docs match this build.
  Undo:  point the Redirect line in $REMOTE_DIR/.htaccess at a previous file.
──────────────────────────────────────────────────────────────
EOF
