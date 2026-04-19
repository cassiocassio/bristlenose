#!/usr/bin/env bash
# Sign every Mach-O inside the PyInstaller sidecar bundle (Track C C2).
#
# Split from build-sidecar.sh so CI can re-sign cached PyInstaller output
# without rebuilding. Parallelises the inner Mach-O sign loop via a bash
# `wait -n` job pool. We don't use `xargs -P` — BSD xargs (the macOS
# default) drops child exit codes when running concurrent jobs, so a
# single failed codesign could be masked in interleaved stderr.
#
# Inner binaries (dylib / .so) are signed first and in parallel. The
# outer bristlenose-sidecar executable is signed last and sequentially;
# codesign requires leaf-first ordering and the outer only has one entry.
#
# Usage:
#   desktop/scripts/sign-sidecar.sh
#
# Environment:
#   SIGN_IDENTITY  codesign identity. Default "-" = ad-hoc.
#                  Alpha release: "Apple Distribution: Martin Storey (Z56GZVA2QB)"
#   TIMESTAMP_FLAG explicit --timestamp argument. Default is --timestamp
#                  (real Apple TSA) for any non-ad-hoc identity and
#                  --timestamp=none for ad-hoc signing.
#   SIGN_JOBS      parallelism; default $(sysctl -n hw.ncpu).
#                  TSA calls are I/O-bound so oversubscription is fine
#                  on M-series; Keychain contention becomes visible at
#                  SIGN_JOBS >= 16.
#   ALLOW_RESIGN   set to 1 to permit re-signing a bundle that already
#                  carries a non-ad-hoc signature. Default is fail-fast
#                  — Developer-ID → Apple-Distribution swap with --force
#                  leaves stale CDHashes inside framework plists.
#
# Outputs:
#   desktop/build/codesign-logs/<sanitised>.log   per-file codesign output
#   desktop/build/sign-manifest.json              path/sha256/identity
#                                                 per signed Mach-O

set -euo pipefail

# `wait -n` is bash 4.3+. macOS ships /bin/bash 3.2 by default — the
# shebang uses env bash so Homebrew's bash (brew install bash) is
# picked up. Fail fast with a clear message on older bash rather than
# limping with a sliding-pool substitute that halves throughput.
if (( BASH_VERSINFO[0] < 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] < 3) )); then
    echo "error: bash 4.3+ required (got $BASH_VERSION)." >&2
    echo "  brew install bash  # then restart your shell" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENTITLEMENTS="$DESKTOP_DIR/bristlenose-sidecar.entitlements"
BUNDLE="$DESKTOP_DIR/Bristlenose/Resources/bristlenose-sidecar"
LOG_DIR="$DESKTOP_DIR/build/codesign-logs"
MANIFEST="$DESKTOP_DIR/build/sign-manifest.json"

SIGN_IDENTITY="${SIGN_IDENTITY:--}"
SIGN_JOBS="${SIGN_JOBS:-$(sysctl -n hw.ncpu)}"
ALLOW_RESIGN="${ALLOW_RESIGN:-0}"

# Array so the flag expands safely under `set -u` regardless of content.
if [ -n "${TIMESTAMP_FLAG:-}" ]; then
    TIMESTAMP=("$TIMESTAMP_FLAG")
elif [ "$SIGN_IDENTITY" = "-" ]; then
    TIMESTAMP=(--timestamp=none)
else
    TIMESTAMP=(--timestamp)
fi

if [ ! -d "$BUNDLE" ]; then
    echo "error: bundle not found at $BUNDLE" >&2
    echo "run desktop/scripts/build-sidecar.sh first." >&2
    exit 1
fi

if [ ! -f "$ENTITLEMENTS" ]; then
    echo "error: entitlements not found at $ENTITLEMENTS" >&2
    exit 1
fi

OUTER="$BUNDLE/bristlenose-sidecar"
if [ ! -f "$OUTER" ]; then
    echo "error: outer binary missing at $OUTER" >&2
    exit 1
fi

echo "==> Collecting inner Mach-Os..."
INNER_FILES=()
while IFS= read -r -d '' f; do
    INNER_FILES+=("$f")
done < <(find "$BUNDLE" -type f \( -name "*.dylib" -o -name "*.so" \) -print0)
echo "    inner: ${#INNER_FILES[@]}, outer: 1, identity: $SIGN_IDENTITY"

# Pre-flight: refuse to re-sign a bundle that already carries a real
# identity. `--force` does not strip inner signatures, so identity
# swaps without a clean rebuild can leave stale CDHashes — desktop
# CLAUDE.md line 327 for the full gotcha.
if [ "$ALLOW_RESIGN" != "1" ]; then
    if codesign -dv "$OUTER" 2>&1 | grep -q "^Authority="; then
        echo "error: outer binary is already signed with a real identity." >&2
        echo "rebuild from scratch (desktop/scripts/build-sidecar.sh)" >&2
        echo "or set ALLOW_RESIGN=1 to override." >&2
        exit 1
    fi
fi

rm -rf "$LOG_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$(dirname "$MANIFEST")"

# Sanitise a bundle-relative path into a log filename.
_log_for() {
    local rel="${1#$BUNDLE/}"
    echo "$LOG_DIR/${rel//\//_}.log"
}

# Per-file sign + local verify. Runs in a subshell so errors don't
# take the parent down; the pool catches non-zero via wait -n.
sign_one() {
    local f="$1"
    local log
    log="$(_log_for "$f")"
    {
        echo "=== codesign --sign $SIGN_IDENTITY $f"
        codesign --force --options=runtime "${TIMESTAMP[@]}" \
            --sign "$SIGN_IDENTITY" "$f"
        # Timestamp assertion — guards against codesign silently falling
        # back to --timestamp=none when timestamp.apple.com is
        # unreachable. Un-notarisable signatures otherwise surface
        # hours later during submission.
        if [ "$SIGN_IDENTITY" != "-" ]; then
            if ! codesign -dvv "$f" 2>&1 | grep -q "Timestamp="; then
                echo "ERROR: no trusted timestamp on $f" >&2
                exit 2
            fi
        fi
        echo "=== strict-verify"
        codesign -v --strict "$f"
    } >"$log" 2>&1
}

echo "==> Parallel-signing ${#INNER_FILES[@]} inner Mach-O(s) (SIGN_JOBS=$SIGN_JOBS)..."

FAILED=0
RUNNING=0

# `if wait -n` — set -e skips errexit on commands in if-conditions, so
# a failing child doesn't abort the parent; we count failures instead.
for f in "${INNER_FILES[@]}"; do
    while (( RUNNING >= SIGN_JOBS )); do
        if wait -n; then :; else FAILED=$((FAILED + 1)); fi
        RUNNING=$((RUNNING - 1))
    done
    sign_one "$f" &
    RUNNING=$((RUNNING + 1))
done

while (( RUNNING > 0 )); do
    if wait -n; then :; else FAILED=$((FAILED + 1)); fi
    RUNNING=$((RUNNING - 1))
done

if [ "$FAILED" -gt 0 ]; then
    echo >&2
    echo "FAIL: $FAILED inner sign(s) failed." >&2
    echo "per-file logs: $LOG_DIR/" >&2
    # Surface the first few failure logs so the user doesn't have to
    # hunt through 550 files.
    grep -l "ERROR\|error:" "$LOG_DIR"/*.log 2>/dev/null | head -5 | while read -r badlog; do
        echo "--- $badlog ---" >&2
        tail -20 "$badlog" >&2
    done
    exit 1
fi

echo "==> Signing outer bristlenose-sidecar executable..."
OUTER_LOG="$LOG_DIR/__outer.log"
{
    codesign --force --options=runtime "${TIMESTAMP[@]}" \
        --entitlements "$ENTITLEMENTS" \
        --sign "$SIGN_IDENTITY" "$OUTER"
    if [ "$SIGN_IDENTITY" != "-" ]; then
        codesign -dvv "$OUTER" 2>&1 | grep -q "Timestamp=" || {
            echo "ERROR: no trusted timestamp on outer" >&2
            exit 2
        }
    fi
} >"$OUTER_LOG" 2>&1 || {
    cat "$OUTER_LOG" >&2
    echo "FAIL: outer sign failed" >&2
    exit 1
}

echo "==> Verifying outer signature (full output)..."
codesign -dv --entitlements :- "$OUTER" 2>&1

echo "==> Deep-verifying outer bundle (Gatekeeper-equivalent)..."
codesign --verify --deep --strict --verbose=2 "$OUTER"

echo "==> Emitting sign-manifest.json..."
BUNDLE="$BUNDLE" SIGN_IDENTITY="$SIGN_IDENTITY" \
    /usr/bin/python3 - >"$MANIFEST" <<'PYEOF'
import datetime
import hashlib
import json
import os
import pathlib

bundle = pathlib.Path(os.environ["BUNDLE"])
identity = os.environ["SIGN_IDENTITY"]

files = []
for path in sorted(
    list(bundle.rglob("*.dylib"))
    + list(bundle.rglob("*.so"))
    + [bundle / "bristlenose-sidecar"]
):
    if not path.is_file():
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    files.append(
        {
            "path": str(path.relative_to(bundle)),
            "sha256": digest,
        }
    )

print(
    json.dumps(
        {
            "identity": identity,
            "signed_at": datetime.datetime.now(datetime.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "file_count": len(files),
            "files": files,
        },
        indent=2,
    )
)
PYEOF

echo "==> Done."
echo "    Signed: ${#INNER_FILES[@]} inner + 1 outer"
echo "    Logs:   $LOG_DIR/"
echo "    Manifest: $MANIFEST"
