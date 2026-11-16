#!/usr/bin/env bash
# Negative fixtures for build-whisper-pack.sh --check-only (the source validation and the allowlist).
# Each bad source must be refused for ITS reason; the intact one must be accepted, so a validator
# that rejects everything cannot pass. Sparse files: nothing here writes a gigabyte.
# Not registered in tests/test_gate_selftests.py (that list is for gates named test-check-*); run it
# by hand, and by the pack builder's owner before a pack is built.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD="$SCRIPT_DIR/build-whisper-pack.sh"
[ -x "$BUILD" ] || { echo "not executable: $BUILD" >&2; exit 2; }
T=$(mktemp -d "${TMPDIR:-/tmp}/bn-pack-test.XXXXXX"); trap 'rm -rf "$T"' EXIT
PASS=0; FAIL=0

mk() {  # mk <dir> <weights-mode: ok|small|truncated|badheader|none> <config-mode: ok|bad|none> [extra file]
    local d="$1"; mkdir -p "$d"
    [ "$3" = ok ] && echo '{"n_mels": 128}' > "$d/config.json"
    [ "$3" = bad ] && echo 'not json' > "$d/config.json"
    python3 - "$d/weights.safetensors" "$2" <<'PY'
import json, struct, sys
path, mode = sys.argv[1:]
if mode == "none":
    sys.exit()
N = 1100 * 1024 * 1024
head = json.dumps({"a": {"dtype": "F16", "shape": [N // 2], "data_offsets": [0, N]}}).encode()
size = 8 + len(head) + N
with open(path, "wb") as f:
    if mode == "small":
        f.write(b"x" * 100)
    elif mode == "badheader":
        f.write(struct.pack("<Q", 10**12)); f.truncate(size)
    else:
        f.write(struct.pack("<Q", len(head)) + head)
        f.truncate(size - (4096 if mode == "truncated" else 0))
PY
    [ -n "${4:-}" ] && echo x > "$d/$4"
    return 0
}

case_() {  # case_ <label> <want-exit> <needle> <dir>
    local out rc
    out=$("$BUILD" --check-only --source "$4" --out "$T/out" 2>&1); rc=$?
    if [ "$rc" -ne "$2" ]; then echo "  ✗ $1: exit $rc, wanted $2"; echo "$out" | sed 's/^/      /' | head -4; FAIL=$((FAIL+1)); return; fi
    if ! grep -qF -- "$3" <<<"$out"; then echo "  ✗ $1: no \"$3\""; echo "$out" | sed 's/^/      /' | head -4; FAIL=$((FAIL+1)); return; fi
    echo "  ✓ $1"; PASS=$((PASS+1))
}

echo "build-whisper-pack negative fixtures"
mk "$T/ok" ok ok;                case_ "an intact source is accepted" 0 "source ok" "$T/ok"
mk "$T/npz" ok ok weights.npz;   case_ "a weights.npz beside it is named and left out" 0 "weights.npz exists and is NOT packaged" "$T/npz"
mk "$T/noweights" none ok;       case_ "no weights is refused" 1 "no weights.safetensors" "$T/noweights"
mk "$T/nocfg" ok none;           case_ "no config.json is refused" 1 "no config.json" "$T/nocfg"
mk "$T/badcfg" ok bad;           case_ "a config that is not JSON is refused" 1 "config.json is not valid JSON" "$T/badcfg"
mk "$T/small" small ok;          case_ "a stub weights file is refused" 1 "far too small" "$T/small"
mk "$T/trunc" truncated ok;      case_ "a truncated weights file is refused" 1 "truncated or padded" "$T/trunc"
mk "$T/hdr" badheader ok;        case_ "an implausible header is refused" 1 "not plausible" "$T/hdr"
case_ "a source that is not a directory is refused" 1 "not a directory" "$T/nope"

echo; echo "$PASS passed, $FAIL failed"; [ "$FAIL" -eq 0 ]
