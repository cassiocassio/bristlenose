#!/usr/bin/env bash
# App Store §2.5.2 static-string gate for the PyInstaller sidecar bundle.
#
# App Store Connect's automated static scan rejects any binary CONTAINING the
# literal `itms-services` — "the app uses the itms-services URL scheme to
# install an app" — even when the code never runs. CPython ships that literal
# in Lib/urllib/parse.py; Homebrew's python@3.12 is not built with
# `--with-app-store-compliance`, so it freezes into the sidecar's
# `urllib.parse`. The spec (desktop/bristlenose-sidecar.spec ::
# _strip_app_store_noncompliant_strings) strips it at freeze time; THIS gate is
# the independent backstop that the assembled bundle is actually clean.
#
# The literal is marshalled into a code object inside a zlib-compressed PYZ, so
# `strings`/`grep` on the bundle returns a FALSE NEGATIVE — the real check must
# decompress the PYZ and scan code-object constants. That work lives in the
# sibling Python helper (needs PyInstaller, which built the bundle); this shell
# wrapper resolves an interpreter and renders the phase-grouped report.
#
# Usage:
#   desktop/scripts/check-sidecar-appstore-strings.sh <sidecar|app|xcarchive>
#
# Exit codes:
#   0  Clean — no App-Store-noncompliant literals in the bundle.
#   1  Literal found (prints the carrier module/file).
#   2  Usage / environment error (no PyInstaller-capable interpreter, etc.).
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "usage: $(basename "$0") <sidecar|app|xcarchive>" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/report.sh"
bn_autowrap "$0" "$@"
trap '_bn_ec=$?; [ "$_bn_ec" -ne 0 ] && bn_trap_fail' EXIT
bn_meta title="App Store string scan" done_title="✓ App Store strings clean"
bn_step_start 1 Verify "App Store string scan" \
    narrative="Decompresses the sidecar PYZ and scans code-object constants for the itms-services literal (§2.5.2)."

TARGET="$1"

# Resolve an interpreter that can import PyInstaller (used to read the PYZ).
# Prefer the sidecar build venv (guaranteed PyInstaller); fall back to the
# contributor venv. Absolute paths only — never trust PATH here.
PY=""
for cand in "$REPO_ROOT/.venv-sidecar/bin/python" "$REPO_ROOT/.venv/bin/python"; do
    if [ -x "$cand" ] && "$cand" -c "import PyInstaller" 2>/dev/null; then
        PY="$cand"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "error: no interpreter with PyInstaller found (.venv-sidecar / .venv)." >&2
    echo "The gate needs PyInstaller to read the sidecar PYZ archive." >&2
    bn_step_fail 1 detail="no PyInstaller-capable interpreter"
    bn_done fail
    exit 2
fi

if "$PY" "$SCRIPT_DIR/check-sidecar-appstore-strings.py" "$TARGET"; then
    bn_step_ok 1 detail="no itms-services literal in PYZ or on disk"
    bn_done ok
else
    rc=$?
    bn_step_fail 1 detail="App-Store-noncompliant literal present — see errors above"
    bn_done fail
    exit "$rc"
fi
