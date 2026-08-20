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
ROOT="$(cd "$DESKTOP_DIR/.." && pwd)"
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

# --- Build identity -------------------------------------------------------
# Two surfaces ask different questions, so they get different answers:
#
#   manifest `version`  what Claude Desktop lists in its own UI. The app's
#                       release version, so "which build is this" is
#                       answerable there without opening anything.
#   proxy  `VERSION`    release + short content hash. Sent on every call as
#                       X-Bristlenose-Proxy-Version and shown in Settings
#                       > MCP Agents. The hash is the load-bearing half: a
#                       .mcpb never auto-updates, so the field question is
#                       never "which release" but "is the proxy that is
#                       RUNNING the one I just packed" — and only content
#                       answers that. Two packs from the same release with
#                       different proxy source get different hashes, which
#                       is the whole point.
#
# Hashed BEFORE the substitution: a file containing its own hash has no
# fixed point. So it identifies the post-strip proxy source — exactly the
# thing that changes when the proxy is edited.
#
# Fail-closed on a missing placeholder. A stamp that silently no-ops would
# ship a proxy claiming 0.0.0-dev forever, which is the failure this whole
# mechanism exists to make impossible.
APP_VERSION="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$ROOT/bristlenose/__init__.py")"
if [ -z "$APP_VERSION" ]; then
    echo "error: could not read __version__ from bristlenose/__init__.py" >&2
    exit 1
fi

STAMPED="$(node - "$STAGE" "$APP_VERSION" <<'NODEEOF'
const fs = require("fs");
const crypto = require("crypto");
const [stage, appVersion] = process.argv.slice(2);

const jsPath = stage + "/server/index.js";
const js = fs.readFileSync(jsPath, "utf8");
const hash = crypto.createHash("sha256").update(js).digest("hex").slice(0, 7);

const stamped = appVersion + "+" + hash;
const placeholder = 'const VERSION = "0.0.0-dev";';
if (!js.includes(placeholder)) {
    console.error("error: VERSION placeholder not found in proxy source");
    process.exit(1);
}
fs.writeFileSync(jsPath, js.replace(placeholder, "const VERSION = " + JSON.stringify(stamped) + ";"));

const mPath = stage + "/manifest.json";
const m = fs.readFileSync(mPath, "utf8");
if (!m.includes('"version": "0.0.0"')) {
    console.error("error: version placeholder not found in manifest.json");
    process.exit(1);
}
fs.writeFileSync(mPath, m.replace('"version": "0.0.0"', '"version": "' + appVersion + '"'));

// stdout is the value for the shell; stderr is for the human.
process.stdout.write(stamped);
console.error("stamped " + stamped);
NODEEOF
)"
if [ -z "$STAMPED" ]; then
    echo "error: stamping produced no version string" >&2
    exit 1
fi

# The strip is a whole-line delete inside an array literal — prove it left
# valid JS before packing (a broken proxy would otherwise surface as
# "Server disconnected" inside Claude Desktop with nothing in our logs).
node --check "$STAGE/server/index.js"

# ...but `node --check` is SYNTAX ONLY, and the worst bug this proxy has had
# was not a syntax error. On 20 Aug 2026 `callUpstream` read `hs.port` with
# `hs` unbound; it threw ReferenceError on every tool call, the try/catch
# swallowed it, and the user was told "Bristlenose is starting" for eleven
# days. `node --check` passes that file — verified. An unbound identifier is a
# static property, so `no-undef` catches the whole class here, at pack time,
# for nothing (review Finding 33).
#
# Lint the SOURCE, not the stage: identical for this purpose, and an error
# then names a path the developer can actually open.
#
# eslint is already a frontend devDependency — no new install, and the shipped
# archive is unaffected (the pack allowlist is manifest.json + server/index.js;
# eslint.config.mjs never enters it).
ESLINT="$ROOT/frontend/node_modules/.bin/eslint"
if [ -x "$ESLINT" ]; then
    (cd "$SRC" && "$ESLINT" server/) || {
        echo "error: proxy lint failed — see above" >&2
        exit 1
    }
else
    # Say so, loudly. A gate that skips in silence is worse than no gate —
    # this repo has the scars. A worktree without `npm ci` is the usual cause.
    echo "warning: eslint not found at $ESLINT — proxy NOT checked for" >&2
    echo "         unbound identifiers. Run 'npm ci' in frontend/ to enable." >&2
fi

rm -f "$OUT"
# -X: no extended attributes / uid / gid. NOT byte-stability across builds:
# the dev-strip rewrites index.js each run, so its mtime lands in the local
# header and two packs of identical sources differ. Reproducibility lives in
# the content hash stamped INTO the proxy, which is the part that matters.
(cd "$STAGE" && zip -q -X -r "$OUT" manifest.json server)

# Pass the expected version so the gate can assert EQUALITY, not merely
# "not the placeholder". Without the second argument a .mcpb packed at 0.25.3
# and left in Resources/ while the app bumps to 0.26.0 passes every check —
# which is precisely the state the Swift side used to assume was impossible.
"$SCRIPT_DIR/check-mcpb.sh" "$OUT" "$APP_VERSION"

# Install a copy into the Xcode staging dir so the existing Copy Sidecar
# Resources phase embeds it in Contents/Resources — the app copies it into
# the container and NSWorkspace.opens it from there (never from inside the
# bundle; §3.4). Gitignored, like ffmpeg/ffprobe beside it.
cp -p "$OUT" "$DESKTOP_DIR/Bristlenose/Resources/Bristlenose.mcpb"

# The stamp, in a form Swift can read.
#
# The app needs the packed proxy's `<release>+<hash>` to answer "is the copy
# running inside Claude Desktop the one I ship?" — and it cannot get it from
# the archive: CFBundleShortVersionString is release-only, and App Sandbox
# blocks shelling out to unzip. Without the hash, two packs of the SAME
# release are indistinguishable, which is precisely the case that cost six
# reinstall cycles on 20 Aug 2026.
#
# A sibling file was argued against in review as "a second artefact that can
# itself go stale, invisibly". That objection is answered by construction
# rather than by promise: this line and the cp above are the same script run,
# so the two cannot be written apart; ensure-sidecar.sh repacks on every
# Cmd+R, so neither can lag the source; and the Swift side requires BOTH to
# exist and to agree on the release half before it will use the hash,
# degrading to release-only rather than to a confident wrong answer.
STAMP_OUT="$OUT_DIR/Bristlenose.mcpb.version"
printf '%s\n' "$STAMPED" > "$STAMP_OUT"
cp -p "$STAMP_OUT" "$DESKTOP_DIR/Bristlenose/Resources/Bristlenose.mcpb.version"

echo "built $OUT ($STAMPED) (+ staged into Bristlenose/Resources)"
