#!/usr/bin/env bash
# Idempotent orchestrator: bring the bundled sidecar up to date + signed, doing
# only the work whose inputs changed. One entry point for BOTH the Xcode
# "Ensure Sidecar Fresh" build phase AND a human terminal. See
# docs/design-desktop-build-orchestration.md.
#
# Pipeline:
#   preconditions → escape hatches → ffmpeg presence → build-sidecar (F/V/P gated)
#   → sign (ffmpeg + sidecar) IF (P rebuilt OR identity changed OR deep-verify fails)
#   → deep-verify → atomic .sign-stamp → run-log line.
#
# bash-3.2-SAFE on purpose: it runs as an Xcode build phase under /bin/bash (3.2).
# It shells out to sign-sidecar.sh (which requires bash 4.3+) as a CHILD process.
# Note those children are launched via bare `bash <script>` below (114/135/136),
# which picks the FIRST `bash` on PATH and overrides their `#!/usr/bin/env bash`
# shebang — so the 4.3+ requirement is satisfied by the Homebrew-prefix PATH
# prepend just below (Xcode's stripped build-phase PATH omits Homebrew, leaving
# only /bin/bash 3.2). The same prepend makes python3.12 resolvable for
# build-sidecar.sh. Both were dead in-phase until this was added (29 Jun 2026).
#
# Usage:   ensure-sidecar.sh [--force] [--dry-run]
# Env:
#   SIGN_IDENTITY                codesign identity; default "-" (ad-hoc).
#   _BRISTLENOSE_RELEASE=1       set by build-all.sh — REQUIRED to use a real
#                                (non-ad-hoc) identity. The IDE inner loop must
#                                never auto-invoke Distribution signing; the
#                                shipping artifact comes from build-all.sh only.
#   BRISTLENOSE_ALLOW_STALE_SIDECAR=1   skip everything (Swift-only iteration).
#   BRISTLENOSE_SKIP_SIDECAR_ENSURE=1   skip (fast schemes: Dev Sidecar / External).

set -euo pipefail

# Xcode build phases run with a stripped PATH that omits this project's Mac
# toolchain (the Homebrew prefix — see .tool-versions / desktop/CLAUDE.md).
# Augment PATH with it ONLY when absent (don't reorder a PATH a contributor
# already configured) so the bare `bash <child>` calls below resolve to
# Homebrew bash 5.x (sign-sidecar.sh needs 4.3+) and build-sidecar.sh finds
# python3.12. A contributor on a different toolchain (mise/asdf/pyenv) with no
# Homebrew puts their python3.12 + bash 4.3+ on the build's PATH instead — this
# adds nothing and their tools win; build-sidecar.sh then errors loudly if the
# tools are still unreachable. 3.2-safe: string assignment + case glob only.
for _brew_bin in /opt/homebrew/bin /usr/local/bin; do
    if [ -d "$_brew_bin" ]; then
        case ":$PATH:" in
            *":$_brew_bin:"*) : ;;                 # already present — leave order
            *) PATH="$_brew_bin:$PATH" ;;          # stripped env — add as fallback
        esac
    fi
done
export PATH

FORCE=0
DRY_RUN=0
for arg in "$@"; do
    case "$arg" in
        --force)   FORCE=1 ;;
        --dry-run) DRY_RUN=1 ;;
        *) echo "error: unknown argument: $arg" >&2; exit 2 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="$(cd "$DESKTOP_DIR/.." && pwd)"
DIST="$DESKTOP_DIR/Bristlenose/Resources"
BUNDLE="$DIST/bristlenose-sidecar"
# Verify the OUTER EXECUTABLE, not the dir — a PyInstaller --onedir bundle is not an
# app bundle, so `codesign --verify` on the directory fails ("no resources but
# signature indicates they must be present"). sign-sidecar.sh verifies this path too.
BUNDLE_BIN="$BUNDLE/bristlenose-sidecar"
SIGN_STAMP="$DIST/.bristlenose-sidecar.sign-stamp"   # OUTSIDE the bundle (not under the seal)
LOG_DIR="$DESKTOP_DIR/build"
LOG="$LOG_DIR/ensure-sidecar.log"
mkdir -p "$LOG_DIR"

SIGN_IDENTITY="${SIGN_IDENTITY:--}"
RELEASE="${_BRISTLENOSE_RELEASE:-0}"

_started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
_log() { echo "$*" >> "$LOG"; }
_say() { echo "ensure-sidecar: $*"; }
_log "---- $_started  identity=$SIGN_IDENTITY force=$FORCE dry=$DRY_RUN release=$RELEASE"

# --- Escape hatches (must mirror check-sidecar-freshness.sh's bypass meaning) ---
if [ "${BRISTLENOSE_ALLOW_STALE_SIDECAR:-0}" = "1" ]; then
    _say "BRISTLENOSE_ALLOW_STALE_SIDECAR=1 — skipping (stale bundle accepted)"; _log "skip: allow-stale"; exit 0
fi
if [ "${BRISTLENOSE_SKIP_SIDECAR_ENSURE:-0}" = "1" ]; then
    _say "BRISTLENOSE_SKIP_SIDECAR_ENSURE=1 — skipping (fast scheme)"; _log "skip: skip-ensure"; exit 0
fi

# --- Distribution guard: never auto-invoke a real identity from the IDE loop ---
if [ "$SIGN_IDENTITY" != "-" ] && [ "$RELEASE" != "1" ]; then
    echo "error: refusing to sign with a real identity ('$SIGN_IDENTITY') outside build-all.sh." >&2
    echo "       The IDE path ad-hoc-signs for local validation only; ship via desktop/scripts/build-all.sh." >&2
    _log "abort: distribution-identity-without-release"
    exit 1
fi

# --- 1. ffmpeg / ffprobe presence (model is first-run-downloaded, not here) ---
ffmpeg_fetched=0
if [ ! -x "$DIST/ffmpeg" ] || [ ! -x "$DIST/ffprobe" ]; then
    _say "ffmpeg/ffprobe missing — fetching"
    if [ "$DRY_RUN" = 0 ]; then
        "$SCRIPT_DIR/fetch-ffmpeg.sh" >>"$LOG" 2>&1 || { echo "error: fetch-ffmpeg.sh failed (see $LOG)" >&2; exit 1; }
        ffmpeg_fetched=1
    fi
    _log "ffmpeg: fetched"
else
    _log "ffmpeg: present"
fi

# --- 2. Identity transition → force a clean P rebuild (never re-sign incrementally) ---
prev_identity=""
# TAB-delimited (NOT ':') — real Apple identities contain a colon
# ("Apple Distribution: Name (TEAM)"), which a ':' split would mangle into a
# permanent identity-mismatch. `cut -f1` defaults to TAB.
[ -f "$SIGN_STAMP" ] && prev_identity="$(head -1 "$SIGN_STAMP" 2>/dev/null | cut -f1 || true)"
identity_changed=0
if [ -n "$prev_identity" ] && [ "$prev_identity" != "$SIGN_IDENTITY" ]; then
    identity_changed=1
    _say "identity transition ($prev_identity → $SIGN_IDENTITY) — forcing clean rebuild"
    _log "identity: changed $prev_identity -> $SIGN_IDENTITY (force P)"
fi

# --- 3. build-sidecar (F/V/P gated). Force on --force OR identity transition. ---
build_args=""
[ "$FORCE" = 1 ] && build_args="$build_args --force"
[ "$identity_changed" = 1 ] && build_args="$build_args --force"
[ "$DRY_RUN" = 1 ] && build_args="$build_args --dry-run"

TMP_OUT="$(mktemp -t ensure-sidecar.XXXXXX)"
trap 'rm -f "$TMP_OUT"' EXIT
# Stream live (so a multi-minute rebuild isn't a silent freeze) AND capture for the
# P-rebuild detection + the log. `tee` shows it as it happens; PIPESTATUS keeps the
# real build-sidecar exit code (tee's success would otherwise mask a failure).
set +e
bash "$SCRIPT_DIR/build-sidecar.sh" $build_args 2>&1 | tee "$TMP_OUT"
build_rc=${PIPESTATUS[0]}
set -e
cat "$TMP_OUT" >> "$LOG"
if [ "$build_rc" -ne 0 ]; then
    echo "error: build-sidecar.sh failed (see $LOG)" >&2; exit 1
fi
p_rebuilt=0
grep -q '\[P\] REBUILD' "$TMP_OUT" && p_rebuilt=1 || true

# --- 4. Sign gate (sidecar + ffmpeg together). Skip work under --dry-run. ---
need_s=0; s_reason=""
if [ "$p_rebuilt" = 1 ]; then need_s=1; s_reason="bundle rebuilt"
elif [ "$identity_changed" = 1 ]; then need_s=1; s_reason="identity changed"
elif [ "$ffmpeg_fetched" = 1 ]; then need_s=1; s_reason="ffmpeg fetched"
elif [ "$DRY_RUN" = 0 ] && ! codesign --verify --deep --strict "$BUNDLE_BIN" >/dev/null 2>&1; then
    need_s=1; s_reason="deep-verify failed"
fi

if [ "$need_s" = 1 ] && [ "$DRY_RUN" = 0 ]; then
    _say "signing (ffmpeg + sidecar) — $s_reason — identity=$SIGN_IDENTITY"
    SIGN_IDENTITY="$SIGN_IDENTITY" bash "$SCRIPT_DIR/sign-ffmpeg.sh"  >>"$LOG" 2>&1 || { echo "error: sign-ffmpeg.sh failed (see $LOG)" >&2; exit 1; }
    SIGN_IDENTITY="$SIGN_IDENTITY" bash "$SCRIPT_DIR/sign-sidecar.sh" >>"$LOG" 2>&1 || { echo "error: sign-sidecar.sh failed (see $LOG)" >&2; exit 1; }
    # Deep-verify is the gate's truth, not shallow verify (stale inner CDHashes).
    if ! codesign --verify --deep --strict "$BUNDLE_BIN" >/dev/null 2>&1; then
        echo "error: post-sign codesign --verify --deep --strict failed on the sidecar binary" >&2
        _log "abort: post-sign deep-verify failed"
        exit 1
    fi
    # Atomic .sign-stamp, written ONLY after deep-verify passes. <identity>:<source_hash>
    src_hash="$(head -1 "$BUNDLE/.source-stamp" 2>/dev/null || echo unknown)"
    printf '%s\t%s\n' "$SIGN_IDENTITY" "$src_hash" > "$SIGN_STAMP.tmp" && mv -f "$SIGN_STAMP.tmp" "$SIGN_STAMP"
    _log "sign: done ($s_reason); .sign-stamp=$SIGN_IDENTITY:${src_hash:0:12}"
    _say "signed ✓"
elif [ "$DRY_RUN" = 1 ]; then
    _say "dry-run: would sign? $( [ "$need_s" = 1 ] && echo "yes ($s_reason)" || echo "no (already current)" )"
else
    _say "sign skip (identity matches, deep-verify ok)"
    _log "sign: skip"
fi

_done="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
_say "done ($_started → $_done)"
_log "==== done $_done"
