#!/usr/bin/env bash
# Source-vs-spec manifest check for the PyInstaller sidecar bundle.
#
# Walks bristlenose/ for directories that contain runtime data files
# (anything not *.py / *.pyc / __pycache__ / CLAUDE.md / *-archive/),
# parses desktop/bristlenose-sidecar.spec to extract datas entries,
# and asserts every runtime-data dir is covered.
#
# Prevents the C3-smoke-test BUG-3/4/5 class: "data file in source,
# missing from bundle." Unit tests can't catch this because they run
# against source with pip install -e .; this gate runs against the
# spec file directly and fails before the 3-minute PyInstaller build.
#
# Usage:
#   desktop/scripts/check-bundle-manifest.sh [<repo-root>]
#
# Exit codes:
#   0  Clean — every runtime-data dir is covered by spec datas.
#   1  Uncovered dir found, OR unparseable datas entry (fail-closed).
#   2  Usage / environment error.
#
# Runtime-data extensions: yaml yml json md html css js txt png svg ico
# csv toml mako 1 sqlite bin pt onnx ttf woff2.
#
# Exclusions: __pycache__, *-archive/ (historical), CLAUDE.md (docs).
# Exceptions: add entries to desktop/scripts/bundle-manifest-allowlist.md
# with BMAN-<N> markers.

set -euo pipefail

REPO_ROOT="${1:-}"
if [ -z "$REPO_ROOT" ]; then
    SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
    REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
fi

SOURCE_ROOT="$REPO_ROOT/bristlenose"
SPEC_FILE="$REPO_ROOT/desktop/bristlenose-sidecar.spec"
ALLOWLIST="$REPO_ROOT/desktop/scripts/bundle-manifest-allowlist.md"
PYTHON="${PYTHON:-$REPO_ROOT/.venv/bin/python}"

if [ ! -d "$SOURCE_ROOT" ]; then
    echo "error: source root not found: $SOURCE_ROOT" >&2
    exit 2
fi
if [ ! -f "$SPEC_FILE" ]; then
    echo "error: spec file not found: $SPEC_FILE" >&2
    exit 2
fi
if [ ! -x "$PYTHON" ]; then
    echo "error: python not executable: $PYTHON (override with PYTHON=...)" >&2
    exit 2
fi

# --- Collect allowlisted-regex entries from the markdown allowlist. --------
ALLOW_REGEXES=()
if [ -f "$ALLOWLIST" ]; then
    while IFS= read -r line; do
        pattern=$(echo "$line" | sed -E 's/^.*<!-- ci-allowlist: BMAN-[0-9]+ --> *//')
        [ -n "$pattern" ] && ALLOW_REGEXES+=("$pattern")
    done < <(grep -E 'ci-allowlist: BMAN-[0-9]+' "$ALLOWLIST" 2>/dev/null || true)
fi

is_allowlisted() {
    local path="$1"
    for pat in "${ALLOW_REGEXES[@]}"; do
        if echo "$path" | grep -qE "$pat"; then return 0; fi
    done
    return 1
}

# --- Parse spec datas via Python AST. Fail-closed on any unparseable entry. -
# Output: one covered-source-path per line (repo-relative, no trailing slash).
covered_paths_script=$(cat <<'PYEOF'
import ast
import os
import sys

spec_path = sys.argv[1]
repo_root = sys.argv[2]

with open(spec_path, "r", encoding="utf-8") as f:
    tree = ast.parse(f.read(), filename=spec_path)

# Find the Analysis(...) call and pull its datas= kwarg.
datas_node = None
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Analysis":
        for kw in node.keywords:
            if kw.arg == "datas":
                datas_node = kw.value
                break
        if datas_node is not None:
            break

if datas_node is None:
    print("FATAL: no Analysis(datas=[...]) call found in spec", file=sys.stderr)
    sys.exit(1)

if not isinstance(datas_node, ast.List):
    print("FATAL: datas is not a list literal (computed datas not supported)", file=sys.stderr)
    sys.exit(1)

# Each element should be a 2-tuple of os.path.join(PROJECT_ROOT, "bristlenose", ...), "bristlenose/...".
# We care about the source side only.
for i, elt in enumerate(datas_node.elts):
    if not isinstance(elt, ast.Tuple) or len(elt.elts) != 2:
        print(f"FATAL: datas[{i}] is not a 2-tuple literal (unparseable)", file=sys.stderr)
        sys.exit(1)
    src = elt.elts[0]
    # Expect Call(func=Attribute(value=Name('os'), attr='path'), attr='join', args=[...])
    # Fall through to any other shape = unparseable.
    if not isinstance(src, ast.Call):
        print(f"FATAL: datas[{i}] source is not a function call (unparseable)", file=sys.stderr)
        sys.exit(1)
    # Collect string arguments, skip PROJECT_ROOT Name node.
    parts = []
    for arg in src.args:
        if isinstance(arg, ast.Name) and arg.id == "PROJECT_ROOT":
            continue
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            parts.append(arg.value)
        else:
            print(f"FATAL: datas[{i}] source has non-string, non-PROJECT_ROOT arg (unparseable)", file=sys.stderr)
            sys.exit(1)
    rel_path = os.path.join(*parts) if parts else ""
    # Strip any trailing slash, normalise.
    rel_path = rel_path.rstrip("/")
    print(rel_path)
PYEOF
)

covered_paths_raw=$("$PYTHON" -c "$covered_paths_script" "$SPEC_FILE" "$REPO_ROOT") || {
    echo "error: spec parse failed (see messages above)" >&2
    echo "  Fix: restore a parseable datas= list, or add an allowlist entry" >&2
    echo "       in $ALLOWLIST with a BMAN-<N> marker if truly intentional." >&2
    exit 1
}

# Sort + dedupe covered paths.
mapfile -t covered_paths < <(echo "$covered_paths_raw" | sort -u | grep -v '^$' || true)

# --- Walk bristlenose/ for runtime-data files. -----------------------------
# A file qualifies if its extension matches the whitelist AND it's not in an
# excluded path. Per-file enumeration (rather than per-dir) lets a file-level
# datas entry cover exactly one file — and lets us catch a new uncovered
# file added to a dir whose siblings are already covered.
#
# macOS BSD find doesn't support -regextype, so filter via grep. `-prune` on
# __pycache__ + *-archive skips those subtrees cheaply before grep runs.
EXT_RE='\.(yaml|yml|json|md|html|css|js|txt|png|svg|ico|csv|toml|mako|1|sqlite|bin|pt|onnx|ttf|woff2)$'

candidate_files=$(
    cd "$REPO_ROOT" && \
    find bristlenose \
        \( -type d \( -name "__pycache__" -o -name "*-archive" \) -prune \) -o \
        \( -type f -not -name "CLAUDE.md" -print \) \
    2>/dev/null | \
    grep -E "$EXT_RE" | \
    sort -u
)

# Per-file enumeration (was per-dir until 29 Apr 2026): a file-level datas
# entry covers exactly one file, and a new uncovered file added to a
# partially-covered dir gets caught instead of being whitewashed.

# --- For each candidate file, check coverage. -----------------------------
# Coverage rules (cov is a datas source path from the spec):
#   - cov ends in a known data extension → file-level entry, covers iff
#     the candidate equals cov.
#   - otherwise → directory-level entry, covers iff candidate is inside
#     that tree (candidate startswith cov + "/").
# Allowlist patterns still match against the candidate's parent directory.
violations=0
while IFS= read -r candidate; do
    [ -z "$candidate" ] && continue
    cand_dir="${candidate%/*}"
    if is_allowlisted "$cand_dir"; then continue; fi

    covered=false
    for cov in "${covered_paths[@]}"; do
        if echo "$cov" | grep -qE "$EXT_RE"; then
            # File-level entry: must equal exactly.
            if [ "$candidate" = "$cov" ]; then
                covered=true
                break
            fi
        else
            # Directory-level entry: candidate must be inside that tree.
            if [[ "$candidate" == "$cov/"* ]]; then
                covered=true
                break
            fi
        fi
    done
    if ! $covered; then
        echo "UNCOVERED: $candidate"
        violations=$((violations + 1))
    fi
done <<< "$candidate_files"

if [ "$violations" -gt 0 ]; then
    echo "" >&2
    echo "bundle-manifest: $violations uncovered runtime-data file(s) found." >&2
    echo "Each listed file is data the PyInstaller bundle will miss unless" >&2
    echo "added to datas in:" >&2
    echo "  $SPEC_FILE" >&2
    echo "" >&2
    echo "Fixes:" >&2
    echo "  (a) Add a datas entry for the file (or its parent dir)." >&2
    echo "  (b) If the file is genuinely not runtime (e.g. archive), add an" >&2
    echo "      allowlist entry in $ALLOWLIST" >&2
    echo "      with a BMAN-<N> marker matching the parent dir + justification." >&2
    exit 1
fi

echo "bundle-manifest: clean (${#covered_paths[@]} datas entries cover all runtime-data files in $SOURCE_ROOT)"
