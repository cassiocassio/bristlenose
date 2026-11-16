#!/usr/bin/env bash
# Build the Whisper asset pack for Apple Background Assets (Apple-hosted, onDemand).
#
# WHAT IT MAKES
#   <out>/whisper-large-v3-turbo.aar   the archive App Store Connect receives
#   <out>/manifest.json                the ba-package manifest it was built from
#   <out>/pack-manifest.json           what the app pins and verifies after download:
#                                      file allowlist, sizes, SHA-256 (weights and archive),
#                                      source revision, packaging tool, build date
#
# WHAT IT NEVER DOES: upload. Uploading is a separate, deliberate, owner-run step (below).
#
# THE PACK (design: docs/private/background-assets-whisper-plan-2026-11.md §4)
#   One pack, id `whisper-large-v3-turbo`, policy onDemand (the app starts it, after the size
#   prompt; `prefetch` would start before our consent screen). Destination directory
#   `large-v3-turbo/` holding config.json and weights.safetensors ONLY. Every pack of an app
#   merges into one namespace, so the directory name is unique to this model. The allowlist is
#   enforced here and again in the app: no weights.npz (a second copy of 1.6 GB), no README,
#   no scripts. Weights are loaded as tensors, never imported or executed.
#
# USAGE
#   build-whisper-pack.sh [--source DIR] [--out DIR] [--check-only]
#     --source DIR   a directory holding config.json and weights.safetensors. Default: the
#                    newest snapshot of mlx-community/whisper-large-v3-turbo in the Hugging
#                    Face cache (HF_HUB_CACHE, HF_HOME, or ~/.cache/huggingface/hub).
#     --out DIR      default desktop/build/whisper-pack
#     --check-only   validate the source and print what would be packaged; make nothing
#
# UPLOADING (owner, by hand, once the pack is built and pack-manifest.json is committed to
# the app as the pinned manifest). Nothing here does it for you.
#   1. The pack rides the FIRST SUBMISSION: App Store Connect > the app > Asset Packs (or
#      Transporter / `xcrun iTMSTransporter`, with the app's ASC API key). Upload
#      <out>/whisper-large-v3-turbo.aar, id `whisper-large-v3-turbo`, policy onDemand.
#   2. Packs are reviewed with the app version that first includes them; select the pack
#      version on the build in the version page. Sandbox accounts cannot download packs.
#   3. A pack built with a BETA packaging tool cannot be submitted: this script refuses to
#      build under a beta Xcode (override: BN_ALLOW_BETA_PACKAGER=1, for local testing only).
#   4. After upload, TestFlight on macOS 26+ is the first place the OS will actually deliver
#      it. A local trial uses `xcrun ba-serve` and `ba-serve url-override` (see the learn
#      track's notes), with a development-signed, profile-carrying build.
#
# Exit codes: 0 ok · 1 refused / failed · 2 usage.
set -euo pipefail

PACK_ID="whisper-large-v3-turbo"
DEST_DIR="large-v3-turbo"
ALLOWED=("config.json" "weights.safetensors")
HF_REPO_DIR="models--mlx-community--whisper-large-v3-turbo"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SOURCE=""; OUT="$ROOT/desktop/build/whisper-pack"; CHECK_ONLY=0

while [ $# -gt 0 ]; do
    case "$1" in
        --source)     [ $# -ge 2 ] || { echo "--source needs a directory" >&2; exit 2; }; SOURCE="$2"; shift 2 ;;
        --out)        [ $# -ge 2 ] || { echo "--out needs a directory" >&2; exit 2; }; OUT="$2"; shift 2 ;;
        --check-only) CHECK_ONLY=1; shift ;;
        -h|--help)    sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)            echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

die() { echo "build-whisper-pack: $*" >&2; exit 1; }

# --- 1. find the source ---------------------------------------------------------------------
REVISION="unknown"
if [ -z "$SOURCE" ]; then
    HUB="${HF_HUB_CACHE:-${HF_HOME:+$HF_HOME/hub}}"; HUB="${HUB:-$HOME/.cache/huggingface/hub}"
    SNAPS="$HUB/$HF_REPO_DIR/snapshots"
    [ -d "$SNAPS" ] || die "no Hugging Face snapshot at $SNAPS — pass --source DIR"
    # Newest snapshot that has both files; a partial snapshot is skipped, not trusted.
    for d in $(ls -t "$SNAPS" 2>/dev/null); do
        if [ -e "$SNAPS/$d/config.json" ] && [ -e "$SNAPS/$d/weights.safetensors" ]; then
            SOURCE="$SNAPS/$d"; REVISION="$d"; break
        fi
    done
    [ -n "$SOURCE" ] || die "no complete snapshot (config.json + weights.safetensors) under $SNAPS"
fi
[ -d "$SOURCE" ] || die "source is not a directory: $SOURCE"

# --- 2. the allowlist, and what is in the source --------------------------------------------
for f in "${ALLOWED[@]}"; do
    [ -f "$SOURCE/$f" ] || die "source has no $f (a symlink into a cache counts: it is resolved)"
done
# Anything else that would be tempting to ship is named and refused, not silently left out of
# the manifest, so a person reading the output sees the decision.
[ ! -e "$SOURCE/weights.npz" ] || echo "note: $SOURCE/weights.npz exists and is NOT packaged (allowlist)"

# --- 3. validate the two files --------------------------------------------------------------
RESOLVED="$(mktemp -d "${TMPDIR:-/tmp}/bn-whisper-pack.XXXXXX")"
trap 'rm -rf "$RESOLVED"' EXIT
python3 - "$SOURCE" <<'PY' || die "source failed validation (see above)"
import json, os, struct, sys
src = sys.argv[1]
cfg = os.path.join(src, "config.json")
w = os.path.join(src, "weights.safetensors")
try:
    c = json.load(open(cfg, encoding="utf-8"))
except Exception as e:
    sys.exit(f"config.json is not valid JSON: {e}")
if not isinstance(c, dict) or not c:
    sys.exit("config.json is empty or not an object")
size = os.path.getsize(w)
if size < 1024 * 1024 * 1024:
    sys.exit(f"weights.safetensors is {size} bytes: far too small for large-v3-turbo (expected > 1 GiB)")
with open(w, "rb") as f:
    head = f.read(8)
    if len(head) < 8:
        sys.exit("weights.safetensors is shorter than a header")
    (n,) = struct.unpack("<Q", head)
    if n <= 0 or n > 100 * 1024 * 1024 or 8 + n > size:
        sys.exit(f"weights.safetensors header length {n} is not plausible")
    try:
        h = json.loads(f.read(n))
    except Exception as e:
        sys.exit(f"weights.safetensors header is not JSON: {e}")
# The last tensor's end offset must equal the data length: catches a truncated copy.
end = 0
for k, v in h.items():
    if k == "__metadata__":
        continue
    end = max(end, v["data_offsets"][1])
if 8 + n + end != size:
    sys.exit(f"weights.safetensors is truncated or padded: header says {8 + n + end} bytes, file is {size}")
print(f"source ok: {size} bytes of weights, {len(h) - ('__metadata__' in h)} tensors")
PY

if [ "$CHECK_ONLY" = 1 ]; then
    echo "check-only: would package ${ALLOWED[*]} from $SOURCE as $PACK_ID (onDemand) into $OUT"
    exit 0
fi

# --- 4. the packaging tool ------------------------------------------------------------------
xcrun --find ba-package >/dev/null 2>&1 || die "xcrun cannot find ba-package (needs Xcode 26+)"
XCODE_PATH="$(xcode-select -p 2>/dev/null || echo '')"
XCODE_VER="$(xcodebuild -version 2>/dev/null | tr '\n' ' ' || true)"
if [ "${BN_ALLOW_BETA_PACKAGER:-}" != 1 ]; then
    case "$XCODE_PATH $XCODE_VER" in
        *[Bb]eta*|*"Release Candidate"*|*" RC"*)
            die "Xcode looks like a beta ($XCODE_PATH): a pack from a beta packager cannot be submitted. BN_ALLOW_BETA_PACKAGER=1 for a local-only pack." ;;
    esac
fi

# --- 5. stage only the allowlist (APFS clone: instant, no extra 1.6 GB) ---------------------
STAGE="$RESOLVED/stage"; mkdir -p "$STAGE/$DEST_DIR"
for f in "${ALLOWED[@]}"; do
    cp -cL "$SOURCE/$f" "$STAGE/$DEST_DIR/$f" 2>/dev/null || cp -L "$SOURCE/$f" "$STAGE/$DEST_DIR/$f"
done
# Belt and braces: the stage holds exactly the allowlist.
GOT="$(cd "$STAGE" && find . -type f | sed 's|^\./||' | sort | tr '\n' ' ')"
WANT="$(for f in "${ALLOWED[@]}"; do echo "$DEST_DIR/$f"; done | sort | tr '\n' ' ')"
[ "$GOT" = "$WANT" ] || die "stage differs from the allowlist: have [$GOT], want [$WANT]"

mkdir -p "$OUT"
MANIFEST="$OUT/manifest.json"
# fileSource is relative to the stage directory, where ba-package runs (it rejects absolute paths).
python3 - "$PACK_ID" "$DEST_DIR" "${ALLOWED[@]}" > "$MANIFEST" <<'PY'
import json, sys
pack, dest, *files = sys.argv[1:]
print(json.dumps({
    "assetPackID": pack,
    "downloadPolicy": {"onDemand": {}},
    "fileSelectors": [
        {"fileSource": f"{dest}/{f}", "fileDestination": f"{dest}/{f}"} for f in files
    ],
    "platforms": ["macOS"],
}, indent=2))
PY

# --- 6. package -----------------------------------------------------------------------------
AAR="$OUT/$PACK_ID.aar"; rm -f "$AAR"
( cd "$STAGE" && xcrun ba-package package "$MANIFEST" --output-path "$AAR" ) || die "ba-package failed"
[ -s "$AAR" ] || die "ba-package produced no archive"

# --- 7. the manifest the app pins -----------------------------------------------------------
python3 - "$PACK_ID" "$DEST_DIR" "$STAGE" "$AAR" "$REVISION" "$XCODE_VER" "${ALLOWED[@]}" > "$OUT/pack-manifest.json" <<'PY'
import datetime, hashlib, json, os, sys
pack, dest, stage, aar, rev, xcode, *files = sys.argv[1:]
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()
print(json.dumps({
    "assetPackID": pack,
    "directory": dest,
    "files": [
        {"name": f, "bytes": os.path.getsize(f"{stage}/{dest}/{f}"), "sha256": sha(f"{stage}/{dest}/{f}")}
        for f in files
    ],
    "archive": {"name": os.path.basename(aar), "bytes": os.path.getsize(aar), "sha256": sha(aar)},
    "sourceRepo": "mlx-community/whisper-large-v3-turbo",
    "sourceRevision": rev,
    "packager": xcode.strip(),
    "builtAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}, indent=2))
PY

echo "built $AAR ($(du -h "$AAR" | cut -f1)) and $OUT/pack-manifest.json"
echo "NOT uploaded. Upload procedure: see this script's header."
