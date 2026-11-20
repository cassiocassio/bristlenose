#!/usr/bin/env bash
#
# check-release-closeout.sh <X.Y.Z> — is the release COMPLETE, not just published?
#
# verify-channels.sh asks whether each channel serves the version. This asks the
# questions it cannot: did the prose and the records catch up? Added 20 Nov 2026
# after 0.47.0 was tagged with the release log, the CLAUDE.md status lines and the
# website's cli.md all still owed, and noticed only because the maintainer asked
# whether the process covered them. A release is not done until this exits 0.
#
# Read-only. Exit 0 = complete, 1 = something owed, 2 = usage.
# Called by Phase 8 of .claude/skills/bn-release/SKILL.md.

set -u
cd "$(dirname "$0")/.."

V="${1:-}"
[ -n "$V" ] || { echo "usage: $0 <X.Y.Z>" >&2; exit 2; }
WEB="${BN_WEBSITE_DIR:-$HOME/Code/bristlenose-website}"
BAD=0

ok()   { printf '  ✓ %-24s %s\n' "$1" "$2"; }
bad()  { printf '  ✗ %-24s %s\n' "$1" "$2"; BAD=1; }
warn() { printf '  ! %-24s %s\n' "$1" "$2"; }

echo "Close-out · $V"

# 1. The release log has this version's entry (Phase 7).
if grep -q "^## $V " docs/release-log.md; then
    ok "release log" "entry for $V"
else
    bad "release log" "no '## $V' entry in docs/release-log.md (Phase 7)"
fi

# 2. CLAUDE.md's two status lines name this version (not a paragraph: two lines).
if grep -q "^\*\*Latest release: $V," CLAUDE.md && grep -q "shipping build \*\*$V (" CLAUDE.md; then
    ok "CLAUDE.md status" "shipping-build and latest-release lines name $V"
else
    bad "CLAUDE.md status" "update 'shipping build' and 'Latest release' for $V"
fi

# 3. Every long option of `run` is documented in the website's cli.md.
#    Roff would hide these from grep in the man page; the website is plain Markdown.
if [ -f "$WEB/docs-src/cli.md" ] && [ -x .venv/bin/bristlenose ]; then
    FLAGS=$(NO_COLOR=1 COLUMNS=200 .venv/bin/bristlenose run --help 2>/dev/null \
        | sed 's/\x1b\[[0-9;]*m//g' | grep -oE -- '--[a-z][a-z0-9-]+' | sort -u | grep -vxE -- '--help|--dev|--verbose')   # -v documents --verbose; --dev is not a user option
    MISSING=""
    for f in $FLAGS; do
        grep -q -- "$f" "$WEB/docs-src/cli.md" || MISSING="$MISSING $f"
    done
    if [ -z "$MISSING" ]; then
        ok "website cli.md" "every 'run' option is documented"
    else
        bad "website cli.md" "'run' options missing from docs-src/cli.md:$MISSING"
    fi
else
    warn "website cli.md" "website repo or .venv/bin/bristlenose not found — unchecked"
fi

# 4. The website repo has nothing committed-but-unpushed, and the changelog is live.
if [ -d "$WEB/.git" ]; then
    AHEAD=$(git -C "$WEB" rev-list --count '@{u}..HEAD' 2>/dev/null || echo "?")
    if [ "$AHEAD" = "0" ]; then
        ok "website pushed" "main matches origin"
    else
        bad "website pushed" "$AHEAD commit(s) on the website's main not pushed — review, push, deploy (Phase 8)"
    fi
fi
HITS=$(curl -s --max-time 20 https://bristlenose.app/docs/changelog.html | grep -c "$(printf '%s' "$V" | sed 's/\./\\./g')")
if [ "${HITS:-0}" -gt 0 ] 2>/dev/null; then
    ok "website changelog" "live page names $V"
else
    bad "website changelog" "live changelog does not name $V — the deploy has not run since the entry existed"
fi

echo
if [ "$BAD" -eq 0 ]; then echo "  complete"; else echo "  NOT COMPLETE — the release is published but the close-out is owed"; fi
exit "$BAD"
