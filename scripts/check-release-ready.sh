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

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

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
ok()   { printf '  \033[32m✓\033[0m %-26s %s\n' "$1" "${2:-}"; }
warn() { printf '  \033[33m⚠\033[0m %-26s %s\n' "$1" "${2:-}"; WARN=$((WARN+1)); }
bad()  { printf '  \033[31m✗\033[0m %-26s %s\n' "$1" "${2:-}" >&2; FAIL=$((FAIL+1)); }
head_() { printf '\n\033[1m%s\033[0m\n' "$1"; }

CURRENT=$(sed -n 's/^__version__ *= *"\(.*\)"/\1/p' bristlenose/__init__.py | head -1)
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
    "https://pypi.org/pypi/bristlenose/$TARGET/json" 2>/dev/null || echo "000")
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
    RUN=$(gh run list --commit "$SHA" --workflow ci.yml --limit 1 \
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

# The publish hold lives in repo SETTINGS (Environments ▸ pypi ▸ required
# reviewers), not in any file — nothing in the tree proves it exists, and a
# fresh fork or a deleted environment silently reverts to publish-on-tag. The
# release ordering (tag pushed EARLY, uploads after both CI verdicts, publish
# waiting for approval) leans on this setting, so probe it rather than remember
# it. Deliberately NOT nested in the CI-status branches above: this must report
# regardless of whether HEAD is pushed or a run exists. Warn, not fail — the
# flow degrades to pre-hold behaviour, which is worse but not wrong; the
# operator just needs to know which world they are in before pushing the tag.
if command -v gh >/dev/null 2>&1; then
    HOLD=$(gh api repos/cassiocassio/bristlenose/environments/pypi \
           --jq '[.protection_rules[]? | select(.type == "required_reviewers")] | length' \
           2>/dev/null || echo "QUERY_FAILED")
    case "$HOLD" in
        QUERY_FAILED) warn "publish hold" "could not query the pypi environment — state unknown" ;;
        0)            warn "publish hold" "NO required reviewer on the pypi environment — a tag push publishes IMMEDIATELY" ;;
        *)            ok   "publish hold" "pypi environment requires approval before publish" ;;
    esac
else
    warn "publish hold" "gh not installed — cannot verify the pypi environment"
fi

RUFF=$( .venv/bin/ruff check . 2>&1 | tail -1 )
grep -q 'All checks passed' <<<"$RUFF" && ok "ruff" "clean" || bad "ruff" "$RUFF"
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
