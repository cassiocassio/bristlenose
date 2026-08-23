#!/usr/bin/env bash
# check-doc-surfaces.sh — every CLI flag must reach all three doc surfaces.
#
# The skill has carried this as Phase 2 item 2 in prose, with a ⚠️ warning about
# roff escapes attached. A warning to a reader about a condition a script can
# assert is a missing gate — so this is the gate.
#
# THE ROFF TRAP, which is the whole reason this needs a script
#
#   roff escapes `-` as `\-`, INCLUDING inside option names: --whisper-model is
#   written \-\-whisper\-model. So the obvious grep for '--[a-z-]+' captures
#   almost nothing and reports nearly every flag as MISSING when it is present.
#   Measured on this tree: naive grep finds 2 flags, unescaped finds 30+.
#   That was a whole audit pass of false positives on 31 Jul 2026.
#
# Surfaces:
#   README.md                  in-repo, required
#   man/bristlenose.1          in-repo (symlink to bristlenose/data/), required
#   <website>/docs-src/cli.md  separate private repo — UNREACHABLE if absent,
#                              never "missing", because a machine without the
#                              deploy repo checked out has not learned anything
#                              about the flag.
#
# Usage:  check-doc-surfaces.sh [--website <path-to-website-repo>]
# Exit:   0 all covered (or only unreachable surfaces) · 1 a real gap · 2 usage
#
# Sourcing: DOC_SURFACES_LIB=1 source … → exposes normalise_roff / verdict_flag

set -uo pipefail

# normalise_roff — undo roff's escaping so option names are comparable.
#   \-  → -      (the trap: applies INSIDE option names)
#   \fB \fI \fR \fP → nothing (font changes)
#   \&  → nothing (zero-width, roff's "not a control char" marker)
normalise_roff() {
    sed -e 's/\\f[BIRP]//g' -e 's/\\&//g' -e 's/\\-/-/g'
}

# verdict_flag <flag> <in_readme:0|1> <in_man:0|1> <in_web:0|1|absent>
#   Prints: ok | missing | partial
verdict_flag() {
    local f="${1-}" r="${2-}" m="${3-}" w="${4-}"
    if [ "$r" = 1 ] && [ "$m" = 1 ] && { [ "$w" = 1 ] || [ "$w" = absent ]; }; then
        echo ok
    elif [ "$r" = 0 ] && [ "$m" = 0 ]; then
        echo missing
    else
        echo partial
    fi
}

[ "${DOC_SURFACES_LIB:-0}" = "1" ] && return 0 2>/dev/null

ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
WEBSITE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --website) WEBSITE="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,/^set -uo/p' "$0" | sed 's/^# \{0,1\}//;$d'; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
[ -n "$WEBSITE" ] || WEBSITE="$ROOT/../bristlenose-website"

# BN_BIN is a testability seam, not a feature: test-doc-surfaces.sh points it at
# a stub that prints no commands, to prove the trivial-pass guard below actually
# fires. Same shape as the plan's BN_EVENT_LOG — an override that makes a
# failure path reachable without manufacturing an environment.
BN="${BN_BIN:-$ROOT/.venv/bin/bristlenose}"
[ -x "$BN" ] || { echo "no bristlenose in .venv — cannot enumerate flags" >&2; exit 2; }

# Collect every long flag from the top level and every subcommand.
# Typer/Click renders help inside Rich box-drawing, so command rows begin with
# "\u2502 " and not whitespace. An earlier draft anchored on '^ +' , matched
# nothing, enumerated zero subcommands, and cheerfully reported "2 flags
# checked" on a CLI with thirty — a gate that passes by seeing almost nothing.
# Strip the box characters first, then anchor.
strip_box() { sed -e 's/[│┃┆┇┊┋|]/ /g' -e 's/[╭╮╰╯─━]//g'; }

COMMANDS=$("$BN" --help 2>/dev/null | strip_box \
    | sed -n '/Commands/,$p' | grep -oE '^ +[a-z][a-z-]+' | tr -d ' ' | sort -u)
FLAGS=$( { "$BN" --help 2>/dev/null
           for c in $COMMANDS; do "$BN" "$c" --help 2>/dev/null; done
         } | strip_box | grep -oE '(^|[^a-zA-Z0-9-])--[a-z][a-z0-9-]+' \
           | grep -oE '\-\-[a-z][a-z0-9-]+' | sort -u)

# A gate that enumerates nothing passes trivially. Refuse to report success on
# an implausibly small surface — this CLI has ten-plus commands.
# NOT `grep -c . || echo 0`: grep prints the count AND exits non-zero when the
# count is zero, so the || arm appends a SECOND line and the numeric test below
# silently mis-evaluates. The guard against passing-by-seeing-nothing then passed
# by seeing nothing. Caught by test-doc-surfaces.sh's stub injection.
_ncmd=$(printf '%s\n' $COMMANDS | sed '/^$/d' | wc -l | tr -d ' ')
if [ "$_ncmd" -lt 5 ]; then
    echo "error: enumerated only $_ncmd subcommand(s) — help parsing is broken," >&2
    echo "       so this check would pass by seeing almost nothing. Refusing." >&2
    exit 2
fi

README=$(cat README.md 2>/dev/null || true)
MAN=$(normalise_roff < man/bristlenose.1 2>/dev/null || true)
if [ -f "$WEBSITE/docs-src/cli.md" ]; then
    WEB=$(cat "$WEBSITE/docs-src/cli.md"); WEB_STATE=present
else
    WEB=""; WEB_STATE=absent
fi

# Flags that are Typer/Click machinery, not product surface.
IGNORE='--help|--install-completion|--show-completion'

# WHICH SURFACE OWES WHAT — the distinction that keeps this gate quiet.
#
# A first cut warned on every flag absent from README or cli.md and produced 16
# warnings on a clean tree, forever. That is docs/design-bn-release-skill.md's
# Risk 2 ("if it flags six advisory things every run, it gets waved through")
# manufactured by a new gate, and it would have been switched off inside two
# releases.
#
# The surfaces are not peers:
#   man/bristlenose.1  the COMPLETE reference. Every flag, always. Hard gate.
#   README.md          curated. A tour, not an index.
#   docs-src/cli.md    curated, same.
#
# So README/cli.md are only asked about flags that are NEW since the last tag —
# which is what the skill actually says ("did NEW user-facing surface reach all
# three doc surfaces?"). On a tree with no new flags this prints nothing at all.
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
NEW_FLAGS=""
if [ -n "$LAST_TAG" ]; then
    NEW_FLAGS=$(git diff "$LAST_TAG"..HEAD -- bristlenose/ 2>/dev/null \
        | grep -E '^\+' | grep -oE '"--[a-z][a-z0-9-]+"' | tr -d '"' | sort -u)
fi
is_new() { [ -n "$NEW_FLAGS" ] && printf '%s\n' $NEW_FLAGS | grep -qxF "$1"; }

GAPS=0; TOTAL=0; PARTIAL=0
printf '\n\033[1mDoc surfaces\033[0m  (README · man · %s)\n\n' \
    "$([ "$WEB_STATE" = present ] && echo "cli.md" || echo "cli.md \033[2munreachable\033[0m")"

for f in $FLAGS; do
    printf '%s' "$f" | grep -qE "^($IGNORE)$" && continue
    TOTAL=$((TOTAL+1))
    r=0; m=0; w=absent
    # Whole-token, not substring: a README mentioning --tiered would otherwise
    # report --tier as documented. Same class as CLAUDE.md's .badge-accept /
    # .badge-accept-flash note, and the sibling script solved it an hour earlier.
    _fq=$(printf '%s' "$f" | sed 's/[][\.^$*+?(){}|\/]/\\&/g')
    printf '%s' "$README" | grep -qE -- "(^|[^a-zA-Z0-9-])${_fq}([^a-zA-Z0-9-]|\$)" && r=1
    printf '%s' "$MAN"    | grep -qE -- "(^|[^a-zA-Z0-9-])${_fq}([^a-zA-Z0-9-]|\$)" && m=1
    if [ "$WEB_STATE" = present ]; then
        w=0; printf '%s' "$WEB" | grep -qE -- "(^|[^a-zA-Z0-9-])${_fq}([^a-zA-Z0-9-]|\$)" && w=1
    fi
    # The man page owes every flag — that is a hard gate on any tree.
    if [ "$m" = 0 ]; then
        GAPS=$((GAPS+1))
        printf '  \033[31m✗\033[0m %-26s absent from the man page (the complete reference)\n' "$f"
        continue
    fi
    # README and cli.md are curated: asked only about flags new since the tag.
    if is_new "$f" && { [ "$r" = 0 ] || [ "$w" = 0 ]; }; then
        PARTIAL=$((PARTIAL+1))
        _miss=""
        [ "$r" = 0 ] && _miss="$_miss README"
        [ "$w" = 0 ] && _miss="$_miss cli.md"
        printf '  \033[33m⚠\033[0m %-26s NEW since %s, missing:%s\n' "$f" "$LAST_TAG" "$_miss"
    fi
done

printf '\n  %d flag(s) checked · %d gap(s) · %d partial\n' "$TOTAL" "$GAPS" "$PARTIAL"
[ "$WEB_STATE" = absent ] && printf '  \033[2mcli.md not checked — website repo not at %s\033[0m\n' "$WEBSITE"
printf '\n'
[ "$GAPS" -eq 0 ]
