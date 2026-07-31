#!/usr/bin/env bash
# Pack desktop/mcpb/ into desktop/build/Bristlenose.mcpb.
#
# A .mcpb is a plain zip (spike-verified: 4 KB, no node_modules, no
# @anthropic-ai/mcpb CLI — that repo is 8 months stale with structural bugs
# open, design §4/§5c). The pack is an explicit ALLOWLIST — manifest.json +
# server/index.js — so nothing can ride along; .mcpbignore only matters if
# someone ever runs `mcpb pack` by hand.
#
# Release strip: lines marked `// mcpb-dev-only` are removed from the packed
# copy. Today that is the BRISTLENOSE_DEV_MCP_HANDSHAKE override, which is
# attacker-settable via `launchctl setenv` and must never ship (design
# §3.1). The unpacked desktop/mcpb/ dir keeps it for the dev loop
# ("Install Unpacked Extension").
#
# Usage: build-mcpb.sh
# Output: desktop/build/Bristlenose.mcpb (self-checked via check-mcpb.sh)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC="$DESKTOP_DIR/mcpb"
OUT_DIR="$DESKTOP_DIR/build"
OUT="$OUT_DIR/Bristlenose.mcpb"

# node is only needed for the post-strip syntax check. Xcode build phases
# run under a stripped PATH — augment with the Homebrew keg only when node
# isn't already resolvable (same pattern as build-sidecar.sh; a configured
# PATH is respected, never reordered).
if ! command -v node >/dev/null 2>&1; then
    for p in /opt/homebrew/opt/node@24/bin /opt/homebrew/bin; do
        [ -x "$p/node" ] && PATH="$p:$PATH" && break
    done
fi
if ! command -v node >/dev/null 2>&1; then
    echo "error: node not found — needed for the post-strip syntax check" >&2
    exit 1
fi

mkdir -p "$OUT_DIR"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/server"
cp "$SRC/manifest.json" "$STAGE/manifest.json"
grep -v 'mcpb-dev-only' "$SRC/server/index.js" > "$STAGE/server/index.js"

# The strip is a whole-line delete inside an array literal — prove it left
# valid JS before packing (a broken proxy would otherwise surface as
# "Server disconnected" inside Claude Desktop with nothing in our logs).
node --check "$STAGE/server/index.js"

rm -f "$OUT"
# -X: no extended attributes — the zip should be byte-stable across builds
# of identical sources.
(cd "$STAGE" && zip -q -X -r "$OUT" manifest.json server)

"$SCRIPT_DIR/check-mcpb.sh" "$OUT"
echo "built $OUT"
