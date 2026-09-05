#!/usr/bin/env bash
# Preflight: is this tree in a fit state to be released?
#
# The mechanical half of docs/design-bn-release-skill.md. Everything here is
# deterministic and assertable, which is why it is a script rather than part of
# the skill — a precondition inside a script is structurally unskippable, whereas
# one in a skill is an instruction a model can misread.
#
# WHAT IT DELIBERATELY DOES NOT DO
#
# It does not judge whether the CHANGELOG entry is any GOOD, or whether new
# user-facing surface reached the docs. Those need reading a diff against prose
# and are the skill's job. This asserts the entry EXISTS and is well-formed; it
# cannot tell you it says the right thing.
#
# It does not decide whether to bump minor or patch. A point release means "the
# user needs telling something is different" — a product judgement that belongs
# to a person, and one that cannot be inferred from paths or line counts. A month
# of refactoring can be invisible; one sentence in an LLM prompt re-judges every
# analysis anyone runs.
#
# It does not re-run pytest. CI owns that, release.yml gates on it (`needs: ci`),
# so PyPI cannot publish untested code. What this does instead is ask whether
# HEAD actually has a green run — which is the real question, and is also the one
# that matters for the Mac channels, since those build LOCALLY and never pass
# through CI at all.
#
# Usage:
#   check-release-ready.sh              # against the version in __init__.py
#   check-release-ready.sh 0.26.0       # against a version you intend to bump to
#   check-release-ready.sh --mac        # only the Mac-channel checks
#   check-release-ready.sh --cli        # only the CLI-channel checks
#
# Exit codes:
#   0  Ready.
#   1  Not ready — at least one check failed; each prints why.
#   2  Usage error.
set -uo pipefail

# verdict_shippable <last_tag> <wheel_diff> <desktop_diff> — PURE, no git.
#   Extracted so scripts/test-preflight-substance.sh can drive every branch with
#   synthetic input instead of manufacturing repositories. Same probe/decide split
#   verify-channels.sh and test-upload-dmg.sh use.
#   Prints one of: no-tag | release | rebuild | nothing
verdict_shippable() {
    local tag="${1-}" wheel="${2-}" desk="${3-}"
    [ -z "$tag" ]   && { echo no-tag;  return; }
    [ -n "$wheel" ] && { echo release; return; }
    [ -n "$desk" ]  && { echo rebuild; return; }
    echo nothing
}

# Sourcing hook: CHECK_RELEASE_READY_LIB=1 exposes the pure verdict_* helpers
# without running a single check. Placed before argument parsing so a caller's
# own $@ is never interpreted as ours.
[ "${CHECK_RELEASE_READY_LIB:-0}" = "1" ] && return 0 2>/dev/null


ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Project identity. This file's own header claimed it sourced project.conf and
# it did not — it carried the PyPI URL, both GitHub repos and the advisory
# workflow list as literals, which is precisely the drift project.conf exists to
# end. Below the LIB guard on purpose: a caller sourcing this for verdict_* gets
# the pure functions and nothing else.
# shellcheck source=scripts/project.conf
. "$ROOT/scripts/project.conf"

SCOPE=all
VERSION=""
for arg in "$@"; do
    case "$arg" in
        --mac) SCOPE=mac ;;
        --cli) SCOPE=cli ;;
        -h|--help) sed -n '2,/^set -uo/p' "$0" | sed 's/^# \{0,1\}//;$d'; exit 0 ;;
        [0-9]*) VERSION="$arg" ;;
        *) echo "unknown argument: $arg" >&2; exit 2 ;;
    esac
done

FAIL=0
WARN=0
ALREADY_RELEASED=0
# Every row is also a sink line (docs/design-release-board.md §1.1) when a
# release run exported BN_EVENT_SINK; sink_line is a no-op otherwise.
if [ -f "$ROOT/desktop/scripts/sink.sh" ]; then . "$ROOT/desktop/scripts/sink.sh"; else sink_line() { :; }; fi
ok()   { printf '  \033[32m✓\033[0m %-26s %s\n' "$1" "${2:-}"; sink_line row src=preflight label="$1" result=ok evidence="${2:-}"; }
warn() { printf '  \033[33m⚠\033[0m %-26s %s\n' "$1" "${2:-}"; WARN=$((WARN+1)); sink_line row src=preflight label="$1" result=warn evidence="${2:-}"; }
bad()  { printf '  \033[31m✗\033[0m %-26s %s\n' "$1" "${2:-}" >&2; FAIL=$((FAIL+1)); sink_line row src=preflight label="$1" result=bad evidence="${2:-}"; }
head_() { printf '\n\033[1m%s\033[0m\n' "$1"; }

CURRENT=$(sed -n "$VERSION_REGEX" "$VERSION_FILE" | head -1)
[ -n "$CURRENT" ] || { echo "could not read __version__" >&2; exit 2; }
TARGET="${VERSION:-$CURRENT}"
PRE_BUMP=0
[ "$TARGET" != "$CURRENT" ] && PRE_BUMP=1

printf '\n\033[1mRELEASE READY?\033[0m  %s' "$TARGET"
[ "$PRE_BUMP" -eq 1 ] && printf '  \033[2m(tree is at %s — pre-bump check)\033[0m' "$CURRENT"
printf '\n'

# ---------------------------------------------------------------------------
head_ "Tree"
# ---------------------------------------------------------------------------
BRANCH=$(git rev-parse --abbrev-ref HEAD)
[ "$BRANCH" = "main" ] && ok "branch" "main" || bad "branch" "on '$BRANCH', not main"

DIRTY=$(git status --porcelain --untracked-files=no | wc -l | tr -d ' ')
[ "$DIRTY" = "0" ] && ok "working tree" "clean" || bad "working tree" "$DIRTY uncommitted change(s)"

# A file marked skip-worktree is invisible to `git status`, so the row above can
# report a clean tree while carrying the modification most likely to stop a
# release. That is not hypothetical: on 22 Aug 2026 both entitlements files were
# marked S and carried com.apple.developer.associated-domains for the parked Zoom
# import. This preflight said "working tree clean", and the Xcode archive then
# failed eleven minutes into the build on a capability the Mac App Store profile
# does not have. The entitlements file's own comment had predicted it in writing
# — "Release will not self-heal" — and nothing was in a position to read it.
#
# The FLAG is not the defect and this must not nag about it: skip-worktree is set
# deliberately, and a marked file matching HEAD is exactly right. The DIVERGENCE
# is the defect. `git diff` cannot see it either — skip-worktree tells git to
# trust the index and stop stat-ing the file — so compare content hashes, which
# is the only reading that does not go through the mechanism being bypassed.
#
# Graded `bad`, harder than the `warn` used for untracked files one row down, and
# deliberately so: an untracked file cannot change a build, and this one did.
SKIPPED=$(git ls-files -v | sed -n 's/^S //p' || true)
if [ -z "$SKIPPED" ]; then
    ok "skip-worktree" "none"
else
    SKIP_N=$(grep -c . <<<"$SKIPPED" | tr -d ' ')
    DIVERGED=""
    while IFS= read -r f; do
        [ -n "$f" ] && [ -f "$f" ] || continue
        have=$(git hash-object -- "$f" 2>/dev/null || echo "")
        want=$(git rev-parse "HEAD:$f" 2>/dev/null || echo "")
        if [ -n "$have" ] && [ -n "$want" ] && [ "$have" != "$want" ]; then
            DIVERGED="${DIVERGED}${f}"$'\n'
        fi
    done <<<"$SKIPPED"
    if [ -z "$DIVERGED" ]; then
        ok "skip-worktree" "$SKIP_N file(s), all match HEAD"
    else
        bad "skip-worktree" "$(grep -c . <<<"$DIVERGED") of $SKIP_N differ from HEAD — git status cannot see this:"
        grep . <<<"$DIVERGED" | sed 's/^/        /' >&2
    fi
fi

# Untracked files are NOT a failure — most are legitimately ignored-adjacent
# scratch. But they are listed, because a release went out on 7 Aug 2026
# alongside an untracked design doc that nobody had decided about. Silence is
# how that happens; a name is enough to make it a decision.
UNTRACKED=$(git status --porcelain --untracked-files=all | grep '^??' | sed 's/^?? //' || true)
if [ -z "$UNTRACKED" ]; then
    ok "untracked" "none"
else
    warn "untracked" "$(wc -l <<<"$UNTRACKED" | tr -d ' ') file(s) — decide, don't ignore:"
    sed 's/^/        /' <<<"$UNTRACKED"
fi

VENV_PY=$(.venv/bin/python -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "")
PINNED=$(sed -n 's/^python *//p' .tool-versions | cut -d. -f1,2)
if [ -z "$VENV_PY" ]; then
    warn "venv" "no .venv/bin/python — cannot verify the toolchain pin"
elif [ "$VENV_PY" = "$PINNED" ]; then
    ok "venv python" "$VENV_PY matches .tool-versions"
else
    bad "venv python" "$VENV_PY but .tool-versions pins $PINNED — env has drifted"
fi

# .venv is the dev env; .venv-sidecar is what SHIPS. They are separate venvs
# (build-sidecar.sh:45) and only one of them was ever checked here, so a sidecar
# left on the old minor by a .tool-versions bump reached the bundle with every
# row above it green. The deps fingerprint cannot see it either: it hashes
# pyproject + `pip freeze`, both identical across minors.
SIDECAR_PY=$(.venv-sidecar/bin/python -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "")
if [ -z "$SIDECAR_PY" ]; then
    warn "sidecar venv" "no .venv-sidecar — nothing built here yet, so nothing to verify"
elif [ "$SIDECAR_PY" = "$PINNED" ]; then
    ok "sidecar venv python" "$SIDECAR_PY matches .tool-versions"
else
    bad "sidecar venv python" "$SIDECAR_PY but .tool-versions pins $PINNED — rebuild the sidecar (build-sidecar.sh --force); the bundle carries this one"
fi

# ---------------------------------------------------------------------------
head_ "Version consistency"
# ---------------------------------------------------------------------------
# Four files carry the version. They drift silently, and the failure surfaces as
# an App Store rejection or a man page that lies.
MAN_VER=$(sed -n 's/^\.TH BRISTLENOSE 1 "[^"]*" "bristlenose \([0-9.]*\)".*/\1/p' bristlenose/data/bristlenose.1 | head -1)
PBX_MKT=$(sed -n 's/.*MARKETING_VERSION = \([0-9.]*\);.*/\1/p' desktop/Bristlenose/Bristlenose.xcodeproj/project.pbxproj | head -1)
PBX_BUILD=$(sed -n 's/.*CURRENT_PROJECT_VERSION = \([0-9]*\);.*/\1/p' desktop/Bristlenose/Bristlenose.xcodeproj/project.pbxproj | head -1)

if [ "$PRE_BUMP" -eq 1 ]; then
    # Pre-bump the three files legitimately still hold the OLD version; all that
    # matters is that they agree with each other, so the bump moves them together.
    if [ "$MAN_VER" = "$CURRENT" ] && [ "$PBX_MKT" = "$CURRENT" ]; then
        ok "pre-bump consistency" "all at $CURRENT — bump will move them together"
    else
        bad "pre-bump consistency" "__init__=$CURRENT man=$MAN_VER pbxproj=$PBX_MKT — already drifted"
    fi
else
    [ "$MAN_VER" = "$TARGET" ] && ok "man page .TH" "$MAN_VER" \
        || bad "man page .TH" "says $MAN_VER, expected $TARGET"
    [ "$PBX_MKT" = "$TARGET" ] && ok "pbxproj MARKETING" "$PBX_MKT" \
        || bad "pbxproj MARKETING" "says $PBX_MKT, expected $TARGET"
fi
ok "pbxproj build number" "$PBX_BUILD"

# ---------------------------------------------------------------------------
head_ "Prose (existence and format only — the skill judges content)"
# ---------------------------------------------------------------------------
# House format: **X.Y.Z** — _D Mon YYYY_   (em dash, italic date, no leading zero)
# Day is 1-31 with NO leading zero (house rule), month is a 3-letter abbreviation,
# and the separator is an em dash. '_08 Aug 2026_' must be rejected — [0-9]{1,2}
# was too loose and let it through.
ENTRY_RE="^\*\*${TARGET//./\\.}\*\* — _([1-9]|[12][0-9]|3[01]) [A-Z][a-z]{2} [0-9]{4}_$"

if grep -qE "$ENTRY_RE" CHANGELOG.md; then
    ok "CHANGELOG entry" "$(grep -m1 -E "$ENTRY_RE" CHANGELOG.md)"
    # An entry with a heading and no body is the failure mode worth catching:
    # it satisfies a naive "does it exist" check and tells the user nothing.
    # index(), not a regex match: '**0.25.1**' is full of regex metacharacters,
    # and `$0 ~ v` made awk choke on its own version string.
    BODY=$(awk -v v="**$TARGET**" 'index($0,v)==1 {f=1;next} f && /^\*\*[0-9]/ {exit} f' CHANGELOG.md | grep -cE '\S' || true)
    [ "${BODY:-0}" -gt 0 ] && ok "CHANGELOG body" "$BODY non-empty line(s)" \
        || bad "CHANGELOG body" "heading present but nothing under it"
elif grep -qE "^\*\*${TARGET//./\\.}\*\*" CHANGELOG.md; then
    bad "CHANGELOG entry" "present but malformed — house format is: **$TARGET** — _8 Aug 2026_"
else
    bad "CHANGELOG entry" "no entry for $TARGET in CHANGELOG.md"
fi

grep -qE "$ENTRY_RE" README.md \
    && ok "README changelog" "agrees with CHANGELOG.md" \
    || bad "README changelog" "README's changelog section has no entry for $TARGET"

# ---------------------------------------------------------------------------
head_ "Not already released"
# ---------------------------------------------------------------------------
# PyPI versions are IMMUTABLE. This is the highest-value mechanical check here:
# everything else is recoverable, and this one is not.
# PyPI is probed FIRST because the tag check below needs to know it: a tag that
# has drifted from HEAD is routine after a published release and alarming before
# one, and reporting both cases the same way would be crying wolf.
PYPI_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
    "$(printf "$PYPI_JSON" "$TARGET")" 2>/dev/null || echo "000")
case "$PYPI_CODE" in
    404) ok "PyPI" "$TARGET not published — free to use" ;;
    200) if [ "$PRE_BUMP" -eq 1 ]; then
             bad "PyPI" "$TARGET IS ALREADY PUBLISHED — immutable, pick another version"
         else
             ALREADY_RELEASED=1
             ok "PyPI" "$TARGET already published — this version is done"
         fi ;;
    *)   warn "PyPI" "could not reach PyPI (HTTP $PYPI_CODE) — unverified" ;;
esac

# The tag check used to pass on EXISTENCE alone — "v$TARGET exists (already
# bumped)" — and never asked where it points. Run against the 0.25.2 mid-flight
# state (tag on the partial fix, main carrying the correction, PyPI never
# published) it printed a green tick and reached READY, so the one hazard the
# maintainer had paused on was invisible to the tool whose job is release-state
# hazards. Re-running the skill is the documented resume mechanism, so a resume
# flowed straight through the blind spot.
#
# Severity depends on whether the version shipped, which is why PyPI goes first:
#   published + tag≠HEAD  → routine. You have committed since the release.
#   unpublished + tag≠HEAD → publish-pending with an ambiguous tag. Which commit
#                            ships is genuinely unclear and only a human can say.
if git rev-parse -q --verify "refs/tags/v$TARGET" >/dev/null; then
    if [ "$PRE_BUMP" -eq 1 ]; then
        bad "git tag" "v$TARGET already exists — pick another version"
    else
        TAG_SHA=$(git rev-parse "refs/tags/v$TARGET^{commit}" 2>/dev/null || echo "")
        HEAD_SHA=$(git rev-parse HEAD 2>/dev/null || echo "")
        if [ -z "$TAG_SHA" ] || [ -z "$HEAD_SHA" ]; then
            bad "git tag" "could not resolve v$TARGET or HEAD — cannot compare"
        elif [ "$TAG_SHA" = "$HEAD_SHA" ]; then
            ok  "git tag" "v$TARGET points at HEAD ($(git rev-parse --short HEAD))"
        elif [ "$ALREADY_RELEASED" -eq 1 ]; then
            ok  "git tag" "v$TARGET at $(git rev-parse --short "$TAG_SHA") · published; HEAD has moved on"
        else
            bad "git tag" "v$TARGET points at $(git rev-parse --short "$TAG_SHA"), HEAD is $(git rev-parse --short HEAD) — unpublished, so decide which ships"
        fi
    fi
else
    ok "git tag" "v$TARGET is free"
fi

# ---------------------------------------------------------------------------
if [ "$SCOPE" != "cli" ]; then
head_ "Mac channels"
# ---------------------------------------------------------------------------
# These build LOCALLY and never pass through CI, so nothing else checks them.
security find-identity -v -p codesigning 2>/dev/null | grep -q 'Apple Distribution' \
    && ok "Apple Distribution" "present" \
    || bad "Apple Distribution" "no signing identity — build-all.sh will fail"

security find-identity -v 2>/dev/null | grep -q '3rd Party Mac Developer Installer' \
    && ok "installer cert" "present" \
    || bad "installer cert" "no Mac Installer Distribution cert — the .pkg cannot be signed"

security find-identity -v 2>/dev/null | grep -q 'Developer ID Application' \
    && ok "Developer ID" "present" \
    || warn "Developer ID" "absent — .dmg channel unavailable"

# The two build scripts want DIFFERENT certificates and used to read the same
# variable, so exporting the one build-all.sh needs silently mis-signed the
# .dmg — caught only by a Gatekeeper assertion 30 minutes and one notarisation
# round-trip later (27 Aug 2026). They now read SIGN_IDENTITY_APPSTORE and
# SIGN_IDENTITY_DEVELOPER_ID. This row exists so a stale exported SIGN_IDENTITY
# is a preflight warning at second zero rather than a build failure at minute
# thirty.
# Escalation (31 Aug 2026): when .ship-local.conf provides both per-purpose
# identities, an ambient generic SIGN_IDENTITY has no legitimate reader left —
# and release.sh run now REFUSES it at the confirmation. Preflight matches:
# warn becomes bad the moment the conf makes the generic name pure hazard.
_SIG_CONF="$ROOT/desktop/scripts/.ship-local.conf"
_conf_has_both=0
if [ -f "$_SIG_CONF" ] \
    && grep -q '^SIGN_IDENTITY_APPSTORE=' "$_SIG_CONF" 2>/dev/null \
    && grep -q '^SIGN_IDENTITY_DEVELOPER_ID=' "$_SIG_CONF" 2>/dev/null; then
    _conf_has_both=1
fi
if [ -n "${SIGN_IDENTITY:-}" ]; then
    case "$SIGN_IDENTITY" in
        *"Apple Distribution"*)
            if [ "$_conf_has_both" = 1 ]; then
                bad "SIGN_IDENTITY exported" "generic name with per-purpose conf entries present — release.sh run refuses this (27 Aug vector). unset it"
            else
                warn "SIGN_IDENTITY exported" "Apple Distribution — build-all reads it, build-dmg ignores it. Prefer SIGN_IDENTITY_APPSTORE and unset this"
            fi ;;
        *"Developer ID"*)
            bad  "SIGN_IDENTITY exported" "Developer ID — build-all.sh will REFUSE this. unset it, or use SIGN_IDENTITY_APPSTORE" ;;
        -)  warn "SIGN_IDENTITY exported" "ad-hoc (-) — build-all will skip the identity, profile and notarytool checks" ;;
        *)  bad  "SIGN_IDENTITY exported" "unrecognised: $SIGN_IDENTITY" ;;
    esac
else
    ok "SIGN_IDENTITY" "not exported — each build script resolves its own"
fi

PROFILE="$HOME/Library/MobileDevice/Provisioning Profiles/Bristlenose_Mac_App_Store.provisionprofile"
if [ ! -f "$PROFILE" ]; then
    bad "provisioning profile" "missing at the expected path"
else
    # PlistBuddy cannot read /dev/stdin — it needs a real file on disk.
    PTMP=$(mktemp "${TMPDIR:-/tmp}/bn-prof.XXXXXX")
    security cms -D -i "$PROFILE" > "$PTMP" 2>/dev/null || true
    EXP=$(/usr/libexec/PlistBuddy -c 'Print :ExpirationDate' "$PTMP" 2>/dev/null || echo "")
    rm -f "$PTMP"
    if [ -z "$EXP" ]; then
        warn "provisioning profile" "present, expiry unreadable"
    else
        EPOCH=$(date -j -f "%a %b %d %T %Z %Y" "$EXP" "+%s" 2>/dev/null || echo 0)
        DAYS=$(( (EPOCH - $(date +%s)) / 86400 ))
        if [ "$EPOCH" -eq 0 ];  then warn "provisioning profile" "unparseable expiry: $EXP"
        elif [ "$DAYS" -lt 0 ]; then bad  "provisioning profile" "EXPIRED ${DAYS#-} days ago"
        elif [ "$DAYS" -lt 30 ];then warn "provisioning profile" "expires in $DAYS days — renew soon"
        else                          ok   "provisioning profile" "$DAYS days left"; fi
    fi
fi

CONF="$ROOT/desktop/scripts/.ship-local.conf"
if [ -f "$CONF" ]; then
    # shellcheck source=/dev/null
    . "$CONF"
    MISSING=""
    for v in BRISTLENOSE_ASC_KEY_ID BRISTLENOSE_ASC_ISSUER_ID BRISTLENOSE_ASC_APPLE_ID; do
        [ -n "${!v:-}" ] || MISSING="$MISSING $v"
    done
    [ -z "$MISSING" ] && ok "ASC config" "key, issuer and app id present" \
                      || bad "ASC config" "missing:$MISSING"
    [ -n "${BRISTLENOSE_DMG_REMOTE:-}" ] && ok "dmg remote" "configured" \
                                         || warn "dmg remote" "BRISTLENOSE_DMG_REMOTE unset — .dmg publish unavailable"
    # Identity resolution (31 Aug 2026) — the row that was missing the night
    # SIGN_IDENTITY_APPSTORE halted a release four steps in: presence of a
    # cert TYPE in the keychain says nothing about whether the value the build
    # will use RESOLVES. Names and SHA-1 fingerprints both accepted; the
    # installer type needs the basic policy (-p codesigning hides it).
    _resolve_row() { # _resolve_row <label> <value> <type> <policy-flags...>
        local _lab="$1" _val="$2" _type="$3"; shift 3
        local _list; _list=$(security find-identity -v "$@" 2>/dev/null)
        if [ -z "$_val" ]; then
            warn "$_lab" "unset — release.sh run will refuse; pin it in .ship-local.conf"
        elif printf '%s' "$_val" | grep -qiE '^[0-9a-f]{40}$'; then
            printf '%s' "$_list" | grep -iF " $_val " | grep -qF "\"$_type" \
                && ok "$_lab" "fingerprint resolves: $(printf '%s' "$_list" | grep -iF " $_val " | sed 's/^[^\"]*\"//; s/\".*$//')" \
                || bad "$_lab" "fingerprint $_val does not resolve to a valid $_type identity"
        else
            case $(printf '%s' "$_list" | grep -cF "\"$_val\"") in
                1) ok "$_lab" "name resolves uniquely" ;;
                0) bad "$_lab" "'$_val' is not in the keychain" ;;
                *) bad "$_lab" "'$_val' matches MULTIPLE identities (renewal twins?) — pin the fingerprint instead" ;;
            esac
        fi
    }
    _resolve_row "identity: App Store" "${SIGN_IDENTITY_APPSTORE:-}" "Apple Distribution" -p codesigning
    _resolve_row "identity: Developer ID" "${SIGN_IDENTITY_DEVELOPER_ID:-}" "Developer ID Application" -p codesigning

    KEYFILE="$HOME/.private_keys/AuthKey_${BRISTLENOSE_ASC_KEY_ID:-none}.p8"
    if [ -f "$KEYFILE" ]; then
        MODE=$(stat -f%Lp "$KEYFILE")
        [ "$MODE" = "600" ] && ok "ASC private key" "present, mode 600" \
                            || warn "ASC private key" "present but mode $MODE — should be 600"
    else
        bad "ASC private key" "not at $KEYFILE"
    fi
else
    bad ".ship-local.conf" "absent — no channel credentials configured"
fi
fi

# ---------------------------------------------------------------------------
if [ "$SCOPE" != "mac" ]; then
head_ "CI"
# ---------------------------------------------------------------------------
# Deliberately asks whether HEAD has a green run rather than re-running pytest.
# release.yml gates on CI (`needs: ci`) so PyPI cannot publish untested code —
# but the Mac artefacts are built locally and bypass CI entirely, which is
# exactly why an un-run HEAD is worth saying out loud.
# Five distinct evidence-absent states used to collapse into one warn labelled
# "no CI run found for this commit" — which was true for exactly one of them.
# gh missing, gh unauthenticated, a failed query and an IN-PROGRESS run all read
# the same, and an in-progress run really does return an empty conclusion, so the
# label was actively false. A line that talks nonsense in four cases out of five
# gets skimmed, which is the whole failure: the operator stops reading the one
# check standing between a local Mac build and code CI has never seen.
SHA=$(git rev-parse HEAD)
SHORT=$(git rev-parse --short HEAD)
if ! command -v gh >/dev/null 2>&1; then
    warn "CI status" "gh not installed — CI state unknown"
elif ! gh auth status >/dev/null 2>&1; then
    warn "CI status" "gh is not authenticated — CI state unknown"
elif ! git branch -r --contains "$SHA" 2>/dev/null | grep -q origin; then
    warn "CI status" "HEAD is not pushed — CI has never seen this commit"
else
    # gh's built-in --jq, so no external jq dependency. `.[0] // {}` keeps an
    # empty run list from crashing the filter; the result is a bare "|".
    RUN=$(gh run list --commit "$SHA" --workflow "$WF_CI" --limit 1 \
          --json conclusion,status \
          --jq '.[0] // {} | "\(.status // "")|\(.conclusion // "")"' 2>/dev/null \
          || echo "QUERY_FAILED")
    case "$RUN" in
        QUERY_FAILED)      warn "CI status" "could not query GitHub — CI state unknown" ;;
        "|")               warn "CI status" "no CI run for $SHORT — not started yet" ;;
        completed\|success) ok  "CI status" "green for $SHORT" ;;
        completed\|*)      bad  "CI status" "conclusion '${RUN#*|}' for $SHORT" ;;
        *)                 warn "CI status" "run is ${RUN%%|*} for $SHORT — not finished" ;;
    esac
fi

# What gates PyPI, now that nothing human does.
#
# The pypi environment's required-reviewer hold was REMOVED on 23 Aug 2026, and
# this row changed shape with it. The old row warned when the hold was absent,
# because the release ordering leaned on it: the tag went out early precisely
# because it published nothing until a human approved.
#
# The hold was answering a question nobody could add information to. At the
# approval moment every fact is mechanical — both CI runs, the artefact's
# signature and staple, tag == HEAD — and a human clicking Approve at 11pm
# re-verifies none of it. 97 releases in 204 days made the ceremony expensive
# and the judgement empty.
#
# So the gate moved from a click to the job graph, and THAT is what this row
# now asserts: publish `needs: build` needs `ci`, and release.yml invokes ci.yml
# with strict-macos: true. PyPI cannot receive a version whose full matrix, e2e
# and strict macOS suite did not pass on the tagged commit. If that chain is
# ever broken, a tag push publishes untested code — which is the thing the hold
# was standing in for, and is worth failing over.
head_ "Publish gate"
if [ ! -f ".github/workflows/$WF_RELEASE" ]; then
    bad "publish gate" "no $WF_RELEASE"
else
    # PARSE, don't grep. Four text searches cannot establish a job graph:
    # `strict-macos:\s*true` was unanchored across the whole file (a comment
    # matched), `^\s*build:` matches a step key, and -A3 is a three-line window
    # so a `needs:` on line 5 read as a broken chain. Worse, the mechanism that
    # makes macOS blocking lives in ci.yml — the file these greps never opened.
    # Change ci.yml's continue-on-error to a bare `true` and the row still said
    # the chain was intact. Since the hold was removed this row is the only
    # thing between a tag push and PyPI.
    if [ ! -x .venv/bin/python ]; then
        warn "publish gate" "no venv — cannot parse the workflows"
    else
        _gate=$(.venv/bin/python - "$WF_RELEASE" "$WF_CI" "$WF_STRICT_INPUT" <<'GATEPY' 2>&1
import sys, yaml

REL_WF, CI_WF, STRICT = sys.argv[1], sys.argv[2], sys.argv[3]

def needs(job):
    n = job.get("needs", [])
    return [n] if isinstance(n, str) else list(n)

try:
    rel = yaml.safe_load(open(f".github/workflows/{REL_WF}"))["jobs"]
    ci = yaml.safe_load(open(f".github/workflows/{CI_WF}"))["jobs"]
except Exception as exc:
    sys.exit(f"could not parse: {exc}")

if "build" not in needs(rel.get("publish", {})):
    sys.exit("publish does not need build")
if "ci" not in needs(rel.get("build", {})):
    sys.exit("build does not need ci")
if rel.get("ci", {}).get("with", {}).get(STRICT) is not True:
    sys.exit(f"{REL_WF} does not invoke {CI_WF} with {STRICT}: true")

# The property "strict means macOS BLOCKS" is implemented in ci.yml, by a
# continue-on-error expression that must consult the input. A bare `true`
# there disarms the whole chain while every string above still matches.
coe = str(ci.get("test", {}).get("continue-on-error", ""))
if STRICT not in coe:
    sys.exit(f"{CI_WF} test.continue-on-error does not consult {STRICT}: {coe!r}")
print(f"publish -> build -> ci, and {CI_WF} honours {STRICT}")
GATEPY
        ); _gate_rc=$?
        case "$_gate_rc" in
            0) ok  "publish gate" "$_gate" ;;
            *) bad "publish gate" "$_gate" ;;
        esac
    fi

    # And record which world we are in, because the ordering depends on it.
    if command -v gh >/dev/null 2>&1; then
        _hold=$(gh api "repos/$GH_REPO/environments/pypi" \
                  --jq '[.protection_rules[] | select(.type=="required_reviewers")] | length' \
                  2>/dev/null || echo "QUERY_FAILED")
        case "$_hold" in
            QUERY_FAILED) warn "publish hold" "could not query the pypi environment — ordering unverified" ;;
            0)            ok   "publish hold" "none — the tag push is the release (release.sh run puts it last)" ;;
            *)            warn "publish hold" "a required reviewer EXISTS — the tag publishes nothing until approved, so release.sh run's tag-last order is wrong for this repo state" ;;
        esac
    fi
fi

RUFF=$( .venv/bin/ruff check . 2>&1 | tail -1 )
grep -q 'All checks passed' <<<"$RUFF" && ok "ruff" "clean" || bad "ruff" "$RUFF"
fi

# ---------------------------------------------------------------------------
head_ "Substance"

# A8 · Nothing to ship.
#
# The skill's Phase 1 calls this "cheap and common" and gives the exact command —
# and nothing ran it. A week of docs, tooling and CI work produces a long git log
# and an empty diff where it counts, and the wheel would then be byte-identical to
# the version already on PyPI. That is a decision (re-use the tag) not a release,
# and it is the one check that can save the whole 1h55.
#
# Note the paths: bristlenose/ and frontend/ are what the wheel ships. desktop/
# is deliberately NOT here — a desktop-only change warrants a Mac rebuild even
# when the wheel is unchanged, so this row reports, it does not refuse.
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
_wheel_diff=""; _desk_diff=""
if [ -n "$LAST_TAG" ]; then
    _wheel_diff=$(git diff "$LAST_TAG"..HEAD --stat -- bristlenose/ frontend/ 2>/dev/null | tail -1)
    _desk_diff=$(git diff "$LAST_TAG"..HEAD --stat -- desktop/ 2>/dev/null | tail -1)
fi
case "$(verdict_shippable "$LAST_TAG" "$_wheel_diff" "$_desk_diff")" in
    no-tag)  warn "shippable diff" "no previous tag — cannot compare" ;;
    release) ok   "shippable diff" "$LAST_TAG..HEAD ·$(printf '%s' "$_wheel_diff" | sed 's/^ *//')" ;;
    rebuild) warn "shippable diff" "wheel byte-identical to $LAST_TAG — desktop-only, a rebuild not a release" ;;
    nothing) warn "shippable diff" "NOTHING SHIPPABLE since $LAST_TAG — re-use the tag, do not bump" ;;
esac

# A4 · Dependency drift.
#
# release-log 0.27.0 #5: openai>=1.50 resolved to 3.0.0 mid-release. The
# assessment (does every constructor still work?) is judgement and stays human.
# The TIMING was not: "10pm, mid-release" is the wrong moment to discover a major.
#
# build-all.sh already runs this exact check at step 2b and hard-fails on drift.
# Running it HERE moves discovery ~40 minutes earlier, into the step the skill
# calls "always first, always free". Same command, same artefact, no new machinery.
if [ ! -x .venv/bin/python ]; then
    warn "dependency drift" "no venv — cannot resolve"
elif [ ! -x .venv-sidecar/bin/python ]; then
    # Both scripts inventory the SIDECAR venv (the one the bundle is built
    # from), not .venv; without it they exit 2 and the rows below would only
    # say "unverified". Name the real precondition.
    warn "dependency drift" "no .venv-sidecar — run desktop/scripts/build-sidecar.sh first"
elif [ ! -f THIRD-PARTY-BINARIES.md ]; then
    warn "dependency drift" "no inventory to compare against"
else
    # Two questions, deliberately both asked.
    #
    #   generate-third-party-binaries.py --check  →  "is the file stale?"  yes/no
    #   check-dep-drift.py                        →  "what moved, and is any
    #                                                 of it a MAJOR?"
    #
    # The first is what build-all.sh hard-fails on and is the gate. The second
    # is what a human needs at the free first step: release-log 0.27.0 #5 is not
    # a complaint that openai moved, it is a complaint that the discovery moment
    # was "10pm, mid-release". A yes/no cannot move that moment; a named list can.
    # What these two rows measure is the sidecar venv AS IT STANDS — i.e. the
    # last sidecar build. build-all.sh --force recreates that venv (with
    # --no-cache-dir, a live re-resolve) AFTER this preflight, so a pyproject
    # edit made since the last build is invisible here and only surfaces at
    # step 2b, mid-release. This commit range was the worked example: the
    # anthropic ceiling lift read green at preflight and would have died at
    # 2b. The file-age test says so up front, without duplicating
    # build-sidecar.sh's deps fingerprint in a second file.
    if [ pyproject.toml -nt .venv-sidecar/pyvenv.cfg ]; then
        warn "dependency drift (age)" "pyproject.toml is newer than the sidecar venv — the two rows below describe the LAST build; step 2b will re-resolve"
    fi
    _drift=$(.venv/bin/python scripts/check-dep-drift.py 2>&1); _drift_rc=$?
    case "$_drift_rc" in
        1) bad  "dependency majors" "$(printf '%s' "$_drift" | grep '^MAJOR' | head -3 | tr '\n' ' ')" ;;
        # The script's own message is the diagnosis ("not a project venv",
        # "target interpreter not found — build the sidecar"); "unverified"
        # alone threw it away.
        2) warn "dependency majors" "could not compare — $(printf '%s' "$_drift" | tail -1 | sed 's/^::error:://' | cut -c1-140)" ;;
        0) # NAME what moved, not just a count. The whole reason this row exists
           # over the yes/no one below is that a count cannot help you decide.
           _moved=$(printf '%s' "$_drift" | grep -E '^(minor|patch|absent)' | head -3 | tr '\n' ' ')
           ok "dependency majors" "${_moved:-$(printf '%s' "$_drift" | tail -1)}" ;;
        # 127, 139, and any code this script has not been taught are NOT success.
        *) warn "dependency majors" "unexpected exit $_drift_rc — unverified" ;;
    esac

    _dep_out=$(.venv/bin/python scripts/generate-third-party-binaries.py --check 2>&1); _dep_rc=$?
    # WARN, not BAD, and the reasoning matters because the first draft had it wrong.
    # build-all.sh step 2b already runs this same check and HARD-FAILS on drift, so
    # a release physically cannot ship a stale inventory whatever this row says. The
    # preflight's job here is early warning — moving discovery from 10pm mid-build to
    # the free first step — not a second gate on the same condition.
    #
    # And the tool's own output says per-platform venv differences (mlx, av, torch)
    # can flag drift that isn't real on a non-canonical machine. A duplicate gate that
    # false-positives is exactly the "gate that cries wolf gets switched off" failure
    # from release-log 0.27.0 #4. Warn early, refuse late.
    case "$_dep_rc" in
        0) ok   "dependency drift" "inventory matches the resolved set" ;;
        1) warn "dependency drift" "inventory stale — regenerate now, or build-all will refuse later" ;;
        *) warn "dependency drift" "could not run the check (exit $_dep_rc) — unverified" ;;
    esac
fi

# A5 · Gate freshness — resolved by RUNNING, not by remembering.
#
# The design doc proposed a stamp ledger (.release/gates.jsonl, appended by each
# gate, compared against HEAD) so the preflight could tell whether a gate was
# stale. Building it revealed the ledger was unnecessary: these gates cost ~2s in
# total, so the honest answer to "has this gate run against current source?" is
# to run it, here, now.
#
# That is the same principle D1 already applies to channels — probe, do not
# remember — and it removes the ledger's whole problem surface: no per-version vs
# cross-version storage, no absent-vs-stale decision, no stamp call to retrofit
# into thirteen scripts, and no possibility of a stamp disagreeing with reality.
#
# Why it matters: 0.27.0's build failure 1 was check-window-surfaces becoming
# UNSATISFIABLE after 037b371e renamed the symbol it asserts on. It had been
# broken for two days and nothing noticed, because the gate only runs during a
# build and nobody cut one. It cost 11 minutes of build to discover. Running it
# here costs 2 seconds and finds it before the bump.
#
# Only source-only gates are listed. check-release-binary, check-mcpb,
# check-sidecar-appstore-strings and check-sidecar-freshness need a built
# artefact or an argument, so they stay build-time and are NOT silently omitted
# — they are named here so the omission is a decision rather than an oversight.
# A3 · The publish hold, as a state rather than an existence claim.
#
# The existing "publish hold" row proves the required-reviewer GATE exists.
# This one asks a different question: is a deployment CURRENTLY waiting?
# release-log 0.27.0 #6 — the maintainer reported having approved and
# pending_deployments still showed pending, because the confirm button is
# "Approve and deploy" and ticking the environment is not pressing it.
#
# Tri-state, and this is the row where it matters most: `gh api` with expired
# auth returns empty and exits non-zero. Folding empty to "nothing pending"
# would be a NETWORK FAULT READING AS A HUMAN APPROVAL.
if ! command -v gh >/dev/null 2>&1; then
    warn "publish state" "gh not installed — unverified"
else
    _run=$(gh run list --workflow="$WF_RELEASE" --limit 1 --json databaseId,status \
             --jq '.[0] | select(.status=="waiting") | .databaseId' 2>/dev/null || echo "QUERY_FAILED")
    case "$_run" in
        QUERY_FAILED) warn "publish state" "could not query release runs — unverified" ;;
        "")           ok   "publish state" "no run waiting on approval" ;;
        *)            warn "publish state" "run $_run is WAITING on the pypi approval" ;;
    esac
fi

head_ "Gates (source-only — the rest need a built artefact)"

for _g in check-window-surfaces check-appearance-seam check-menu-routing \
          check-logging-hygiene check-bundle-manifest; do
    _gs="desktop/scripts/$_g.sh"
    if [ ! -x "$_gs" ]; then
        warn "$_g" "missing"
        continue
    fi
    _t0=$SECONDS
    if _out=$(bash "$_gs" 2>&1); then
        ok "$_g" "$(( SECONDS - _t0 ))s"
    else
        # A gate that fires here is either a real defect or a gate that has
        # become unsatisfiable. Both are worth 11 minutes of not-building.
        bad "$_g" "$(printf '%s' "$_out" | grep -vE '^\s*$' | tail -1 | cut -c1-58)"
    fi
done

# Tap-workflow drift.
#
# .github/workflows/homebrew-tap/update-formula.yml is a COPY. The workflow that
# actually runs lives in cassiocassio/homebrew-bristlenose, and nothing compared
# them — so the provenance gate added here on 23 Aug 2026 was inert until the
# file was pushed to the tap, and there was no way to notice.
#
# Homebrew is the channel with the least platform defence: no notarisation, no
# Gatekeeper, no sandbox. A silent divergence between what this repo believes the
# tap does and what it does is worth one HTTP request per release.
if ! command -v gh >/dev/null 2>&1; then
    warn "tap workflow" "gh not installed — drift unverified"
else
    _local_wf=".github/workflows/homebrew-tap/update-formula.yml"
    _live_sha=$(gh api "repos/$TAP_REPO/contents/.github/workflows/update-formula.yml" \
                  --jq .sha 2>/dev/null || echo "QUERY_FAILED")
    case "$_live_sha" in
        QUERY_FAILED|"") warn "tap workflow" "could not read the tap repo — drift unverified" ;;
        *)
            _local_sha=$(git hash-object "$_local_wf" 2>/dev/null || echo "")
            if [ "$_live_sha" = "$_local_sha" ]; then
                ok "tap workflow" "tap repo matches this copy"
            else
                bad "tap workflow" "DIVERGED from the tap repo — push $_local_wf"
            fi ;;
    esac
fi

# The Fedora Copr API token.
#
# Gated on CHANNELS rather than on the file existing, so it activates on the day
# `copr` is added to project.conf and there is no second thing to remember. It
# renders nothing while the channel is off — same shape as the dmg block in
# verify-channels.sh.
#
# Why this belongs in a release gate at all: Copr tokens expire after 180 days,
# and this channel ships a few times a year. A calendar reminder for something
# that matters *at release time* is a reminder that fires while you are doing
# something else; this fires while you are releasing.
case " $CHANNELS " in *" copr "*)
    _copr_conf="$HOME/.config/copr"
    if [ ! -f "$_copr_conf" ]; then
        bad "copr token" "no ~/.config/copr — the Copr build cannot be triggered"
    else
        # Copr writes "# expiration date: YYYY-MM-DD" into the config it hands
        # you. Read only that line: nothing here should touch the token itself.
        _copr_exp=$(sed -n 's/^#[[:space:]]*expiration date:[[:space:]]*//p' "$_copr_conf" | head -1)
        if [ -z "$_copr_exp" ]; then
            warn "copr token" "present, no expiry recorded — regenerate to get one"
        else
            # BSD first (this runs on the Mac), GNU second, so the check is not
            # silently wrong if it ever runs on a Linux release box.
            _copr_epoch=$(date -j -f "%Y-%m-%d" "$_copr_exp" "+%s" 2>/dev/null \
                          || date -d "$_copr_exp" "+%s" 2>/dev/null || echo 0)
            _copr_days=$(( (_copr_epoch - $(date +%s)) / 86400 ))
            if   [ "$_copr_epoch" -eq 0 ]; then warn "copr token" "unparseable expiry: $_copr_exp"
            elif [ "$_copr_days" -lt 0 ];  then bad  "copr token" "EXPIRED ${_copr_days#-} days ago — regenerate at copr.fedorainfracloud.org/api/"
            elif [ "$_copr_days" -lt 30 ]; then warn "copr token" "expires in $_copr_days days — regenerate before it bites"
            else                                ok   "copr token" "$_copr_days days left"
            fi
        fi

        # An expiry comment is a CLAIM about the token, not evidence about it —
        # a hand-edited file, a revoked token or a wrong username all read fine
        # above. Read it back when the client is available. (Same discipline as
        # CredentialStore.set() returning cleanly not proving anything.)
        if ! command -v copr-cli >/dev/null 2>&1; then
            warn "copr auth" "copr-cli not installed — expiry checked, token unverified"
        else
            _copr_who=$(copr-cli whoami 2>/dev/null | tr -d "[:space:]")
            case "$_copr_who" in
                "")            bad "copr auth" "copr-cli whoami failed — token does not authenticate" ;;
                "$COPR_OWNER") ok  "copr auth" "authenticates as $COPR_OWNER" ;;
                *)             bad "copr auth" "authenticates as $_copr_who, but project.conf says $COPR_OWNER" ;;
            esac
        fi
    fi
;; esac

# Advisory workflows that have been red for a while.
#
# release-log 0.27.0 #7: perf.yml had been red for FOUR consecutive runs and
# nobody knew, including on the abandoned 0.26.0 tag. It is deliberately
# non-blocking — post-merge only, so runner noise cannot stall a release — and
# that decision is right. The consequence is that nothing surfaces a sustained
# red, which is the same "nobody is looking" shape as the gate that went
# unsatisfiable for two days.
#
# One failure is noise. Three in a row is a signal, and the threshold is the
# whole design: a row that fires on every flake gets ignored, which is how the
# advisory workflow became invisible in the first place.
if ! command -v gh >/dev/null 2>&1; then
    warn "advisory workflows" "gh not installed — unverified"
else
    for _wf in $WF_ADVISORY; do
        _runs=$(gh run list --workflow="$_wf" --branch main --limit 5 \
                  --json conclusion --jq '[.[].conclusion] | join(" ")' 2>/dev/null \
                || echo "QUERY_FAILED")
        case "$_runs" in
            QUERY_FAILED|"") warn "${_wf%.yml} streak" "could not query — unverified" ;;
            *)
                _streak=0
                for _c in $_runs; do
                    case "$_c" in failure|timed_out) _streak=$((_streak+1)) ;; *) break ;; esac
                done
                if [ "$_streak" -ge "$ADVISORY_STREAK_MAX" ]; then
                    bad  "${_wf%.yml} streak" "red for the last $_streak runs on main — advisory, so nothing else says so"
                elif [ "$_streak" -gt 0 ]; then
                    warn "${_wf%.yml} streak" "red for the last $_streak run(s) on main"
                else
                    ok   "${_wf%.yml} streak" "latest run on main is not red"
                fi ;;
        esac
    done
fi

# A10 · Doc-surface parity.
#
# Phase 2 item 2 of the skill, made mechanical. The man page is the COMPLETE
# reference and is hard-gated; README and the website's cli.md are curated and
# are only asked about flags new since the last tag — otherwise this prints 16
# warnings on a clean tree forever, which is Risk 2 (preflight fatigue) built by
# hand. The roff-unescaping the skill warned about in prose lives in that script.
# Live provider check — the one question no mocked suite can ask.
#
#   check-providers-live.py  →  for every SHIPPED (provider, model): is the key
#                               alive, does the model still exist, does our
#                               request shape come back as a valid result?
#
# Added 4 Sep 2026 after one run of it found, the same afternoon: the freshly
# moved Claude default double-encoding its tool input, and BOTH Gemini picker
# models soft-retired ("no longer available to new users" — a status the
# vendor's deprecations page does not carry, so no doc could have caught it).
# The app's Settings "Online" light validates only the key, with a fixed cheap
# model, so it saw none of that either. Releases happen most weeks, which makes
# this the cadence that needs no remembering. Costs pence; needs keys, so a
# missing key is WARN (unverified), never OK.
_live=$(.venv/bin/python scripts/check-providers-live.py 2>/dev/null); _live_rc=$?
case "$_live_rc" in
    0) ok   "providers live" "$(printf '%s' "$_live" | tail -1)" ;;
    1) bad  "providers live" "$(printf '%s' "$_live" | grep ' FAIL ' | awk '{print $2" ("$4")"}' | head -3 | tr '\n' ' ')" ;;
    2) warn "providers live" "could not enumerate or no keys — unverified" ;;
    *) warn "providers live" "unexpected exit $_live_rc — unverified" ;;
esac

if [ ! -x scripts/check-doc-surfaces.sh ]; then
    warn "doc surfaces" "checker missing"
else
    _ds=$(bash scripts/check-doc-surfaces.sh 2>&1); _ds_rc=$?
    _ds_tail=$(printf '%s' "$_ds" | grep -E 'flag\(s\) checked' | sed 's/^ *//')
    case "$_ds_rc" in
        0) ok   "doc surfaces" "${_ds_tail:-all flags documented}" ;;
        2) warn "doc surfaces" "could not enumerate the CLI — unverified" ;;
        *) bad  "doc surfaces" "$(printf '%s' "$_ds" | grep -c 'absent from the man page') flag(s) absent from the man page" ;;
    esac
fi

# ---------------------------------------------------------------------------
printf '\n'
if [ "$FAIL" -eq 0 ] && [ "$ALREADY_RELEASED" -eq 1 ]; then
    printf '  \033[2mNOTHING TO RELEASE\033[0m  %s is already published and tagged.\n' "$TARGET"
    printf '  Bump first:  ./scripts/bump-version.py minor|patch\n'
    printf '  Or re-ship the same release:  ./scripts/bump-version.py --build-only\n\n'
    exit 0
fi
if [ "$FAIL" -eq 0 ]; then
    printf '  \033[32mREADY\033[0m  %s' "$TARGET"
    [ "$WARN" -gt 0 ] && printf '  ·  %d warning(s) to decide about' "$WARN"
    printf '\n\n'
    printf '  \033[2mMechanical checks only. Whether the CHANGELOG says the right thing,\n'
    printf '  and whether the docs cover it, is a reading task this cannot do.\033[0m\n\n'
    exit 0
fi
printf '  \033[31mNOT READY\033[0m  %d check(s) failed' "$FAIL"
[ "$WARN" -gt 0 ] && printf ', %d warning(s)' "$WARN"
printf '\n\n'
exit 1
