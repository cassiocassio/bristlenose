#!/usr/bin/env bash
# Negative fixtures for check-sidecar-appstore-strings.sh.
#
# App Store Connect's static scan rejects any binary CONTAINING `itms-services`, even when the code
# never runs, and the literal sits marshalled inside a zlib-compressed PYZ where `strings` returns a
# false negative. A gate that cannot fail would ship that rejection reading "clean", so this builds
# tiny real PyInstaller bundles, one clean and one per needle in a frozen module, plus an on-disk
# literal, and drives the gate over each.
#
# Needs an interpreter that can import PyInstaller (.venv-sidecar, as the gate does) and takes about
# a minute; without one every case is skipped, loudly, and the exit code stays 0.
#
# BN_REPORT=0 turns off the report renderer, which would otherwise swallow the gate's own lines.
#
# Usage: test-check-sidecar-appstore-strings.sh
# Exit:  0 all cases behaved (or none could run) · 1 at least one gate failed to fail
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
GATE="$SCRIPT_DIR/check-sidecar-appstore-strings.sh"
[ -x "$GATE" ] || { echo "gate not executable: $GATE" >&2; exit 2; }

PY=""
for cand in "$REPO_ROOT/.venv-sidecar/bin/python" "$REPO_ROOT/.venv/bin/python"; do
    if [ -x "$cand" ] && "$cand" -c "import PyInstaller" 2>/dev/null; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
    echo "check-sidecar-appstore-strings: skipped — no interpreter with PyInstaller (.venv-sidecar / .venv)"
    exit 0
fi

TMP=$(mktemp -d "${TMPDIR:-/tmp}/bn-appstore-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0

# urllib.parse is excluded on purpose: this Python's copy carries `itms-services` (gh-120522), which the
# real sidecar spec strips at freeze time and this gate rightly flags, so a "clean" fixture must not
# freeze it and every hit below must come from the literal the case planted.
# Freeze a one-folder app named bristlenose-sidecar (the name the gate looks for) whose helper module
# holds <literal> (or nothing). Each case gets its own dist directory. Echoes the bundle dir.
freeze() {  # <case> <literal-or-empty>
    local case="$1" lit="$2" src="$TMP/src-$1"
    mkdir -p "$src"
    printf 'VALUE = %s\n' "$( [ -n "$lit" ] && printf '"%s"' "$lit" || printf '"nothing"' )" > "$src/helper_mod.py"
    printf 'import helper_mod\nprint(helper_mod.VALUE)\n' > "$src/entry.py"
    ( cd "$src" && "$PY" -m PyInstaller --noconfirm --log-level ERROR --onedir --name bristlenose-sidecar --exclude-module urllib.parse \
        --distpath "$TMP/dist-$case" --workpath "$TMP/work-$case" --specpath "$TMP/spec-$case" \
        --paths "$src" "$src/entry.py" >/dev/null 2>&1 ) || { echo "freeze failed for $case" >&2; return 1; }
    echo "$TMP/dist-$case/bristlenose-sidecar"
}

expect() {  # <label> <want-exit> <want-substring-or-empty> <args...>
    local label="$1" want="$2" needle="$3"; shift 3
    local out rc
    out=$(BN_REPORT=0 "$GATE" "$@" 2>&1); rc=$?
    if [ "$rc" -ne "$want" ]; then
        echo "  ✗ $label: exit $rc, wanted $want"; echo "$out" | sed 's/^/      /' | head -6; FAIL=$((FAIL+1)); return
    fi
    if [ -n "$needle" ] && ! printf '%s' "$out" | grep -qF -- "$needle"; then
        echo "  ✗ $label: exit $rc but no \"$needle\""; echo "$out" | sed 's/^/      /' | head -6; FAIL=$((FAIL+1)); return
    fi
    echo "  ✓ $label"; PASS=$((PASS+1))
}

echo "check-sidecar-appstore-strings negative fixtures (freezing four tiny bundles…)"

clean=$(freeze probeclean "") || exit 2
expect "a bundle with none of the literals is clean" 0 "clean" "$clean"

a=$(freeze probea "itms-services://download-manifest") || exit 2
expect "itms-services frozen into a module is found in the PYZ" 1 "PYZ frozen module" "$a"
expect "...and the carrier module is named" 1 "helper_mod" "$a"

b=$(freeze probeb "https://github.com/explosion/spacy-models/releases/download/x") || exit 2
expect "the spaCy model download URL is found in the PYZ" 1 "spacy-models/releases/download" "$b"

c=$(freeze probec "https://raw.githubusercontent.com/explosion/spacy-models/master/compatibility.json") || exit 2
expect "the spaCy compatibility URL is found in the PYZ" 1 "spacy-models/master/compatibility.json" "$c"

# A literal that is on disk but not in the PYZ: the clean bundle plus a data file carrying it.
mkdir -p "$TMP/dist-disk" && cp -R "$clean" "$TMP/dist-disk/bristlenose-sidecar"
printf 'see itms-services for details\n' > "$TMP/dist-disk/bristlenose-sidecar/note.txt"
expect "a literal in a file on disk beside the frozen app is found" 1 "on-disk file" "$TMP/dist-disk/bristlenose-sidecar"

expect "a path that does not exist is a usage error" 2 "path not found" "$TMP/nope"
expect "...and it says nothing was checked, not that a literal was found" 2 "nothing was checked" "$TMP/nope"
mkdir -p "$TMP/emptydir"
expect "a directory with no sidecar executable is a usage error, not a pass" 2 "could not locate a sidecar executable" "$TMP/emptydir"
expect "no argument is a usage error" 2 "usage"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
