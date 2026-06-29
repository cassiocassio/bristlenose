#!/usr/bin/env bash
# Build the bristlenose desktop sidecar via PyInstaller (Track C).
#
# Produces a --onedir bundle at
#   desktop/Bristlenose/Resources/bristlenose-sidecar/
#
# Signing is a separate step: desktop/scripts/sign-sidecar.sh. Splitting
# build from sign (C2) lets CI re-sign cached PyInstaller output without
# paying the ~60 s rebuild cost on every signing-identity change.
#
# Xcode's "Copy Sidecar Resources" build phase picks the bundle up from
# the Resources directory at archive time.
#
# Prerequisites:
#   - python3.12 on PATH. The script builds its own dedicated venv at
#     $ROOT/.venv-sidecar, recreated from scratch on every run, with only
#     `.[serve,apple,desktop]` extras — keeping contributor-installed
#     packages (BERTopic spike deps, dev-only tools) out of the bundle.
#     The contributor's `.venv` (with `dev` extras) is left alone.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="$(cd "$DESKTOP_DIR/.." && pwd)"
SIDECAR_VENV="$ROOT/.venv-sidecar"
PYTHON="$SIDECAR_VENV/bin/python"
SPEC="$DESKTOP_DIR/bristlenose-sidecar.spec"
DIST="$DESKTOP_DIR/Bristlenose/Resources"
WORK="$DESKTOP_DIR/build/pyinstaller"
BUNDLE="$DIST/bristlenose-sidecar"

# Robust recursive delete for large trees on a Spotlight-indexed volume.
# `rm -rf` on a 400 MB+ bundle races mdworker/fseventsd: while rm unlinks
# entries, the indexer re-creates directory entries, so rm's final rmdir hits
# ENOTEMPTY ("Directory not empty") and `set -e` aborts the build — the papercut
# where the *second* invocation succeeds because the tree is mostly gone by then.
# Fix: rename out of the way first (atomic, frees the canonical path instantly so
# the rebuild proceeds regardless), then rm the renamed trash with retries. Sweep
# any trash orphans a prior failed run left behind.
robust_rmrf() {
    local target="$1"
    # Clear leftovers from an earlier interrupted delete (best-effort).
    rm -rf "${target}".delete-* 2>/dev/null || true
    [ -e "$target" ] || return 0
    local trash="${target}.delete-$$"
    mv "$target" "$trash" 2>/dev/null || trash="$target"
    local n
    for n in 1 2 3 4 5; do
        rm -rf "$trash" 2>/dev/null && return 0
        sleep 1
    done
    # Final attempt surfaces the real error if it still fails. The canonical
    # path is already free (renamed), so the build can proceed even on failure.
    rm -rf "$trash" || echo "warning: could not fully remove $trash (left for next run)" >&2
}

# ---------------------------------------------------------------------------
# Build the React SPA into bristlenose/server/static FIRST — before fingerprint,
# venv recreate, and PyInstaller analysis. The bundle ships server/static/ (the
# SPA: gitignored, NOT produced by PyInstaller), so without this a missed
# `npm run build` silently ships a STALE frontend. Doing it here makes every
# sidecar build self-heal the SPA — standalone or via build-all.sh — and the
# source fingerprint (sidecar-source-hash.sh) now covers frontend src + locales,
# so the Xcode freshness gate fails loudly if this is ever skipped. Fail-fast
# (cheap) before the ~100 s PyInstaller work. Mirrors release.yml's build.
# ---------------------------------------------------------------------------
FRONTEND_DIR="$ROOT/frontend"
# Prefer the repo-pinned Node (.tool-versions: node 24). mise/asdf aren't
# installed locally, so add the Homebrew keg to PATH when it's present.
if [ -d /opt/homebrew/opt/node@24/bin ]; then
    PATH="/opt/homebrew/opt/node@24/bin:$PATH"
fi
if ! command -v npm >/dev/null 2>&1; then
    echo "error: npm not found on PATH — install Node 24 (see .tool-versions):" >&2
    echo "  brew install node@24" >&2
    exit 1
fi
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "error: frontend/node_modules missing — install deps first:" >&2
    echo "  (cd frontend && npm ci --legacy-peer-deps)" >&2
    exit 1
fi
echo "==> Building React SPA (npm run build) into bristlenose/server/static..."
( cd "$FRONTEND_DIR" && npm run build )

# Fingerprint the source (Python + frontend src + locales) NOW — before pip/
# PyInstaller run — so the stamp reflects exactly what gets bundled, uncontaminated
# by any transient file a build step might drop under bristlenose/ (which would
# otherwise make the stamp disagree with check-sidecar-freshness.sh's clean-tree
# recompute). The frontend was built just above, so server/static/ already matches
# this fingerprint's frontend inputs. Written to the bundle near the end. See
# sidecar-source-hash.sh for the shared recipe.
# shellcheck source=sidecar-source-hash.sh
. "$SCRIPT_DIR/sidecar-source-hash.sh"
SOURCE_HASH="$(sidecar_source_hash "$ROOT")"

if ! command -v python3.12 >/dev/null; then
    echo "error: python3.12 not found on PATH" >&2
    echo "run: brew install python@3.12" >&2
    exit 1
fi

# Recreate the sidecar venv from scratch every build. The whole point is a
# bundle whose contents are deterministic — keep the contributor's `.venv`
# (with dev extras and any spike packages) out of PyInstaller's analysis.
echo "==> Recreating sidecar venv at $SIDECAR_VENV"
robust_rmrf "$SIDECAR_VENV"
python3.12 -m venv "$SIDECAR_VENV"
"$SIDECAR_VENV/bin/pip" install --no-cache-dir --quiet --upgrade pip
"$SIDECAR_VENV/bin/pip" install --no-cache-dir -e "$ROOT[serve,apple,desktop]"

if ! "$PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
    echo "error: PyInstaller not installed in fresh sidecar venv." >&2
    echo "(the 'desktop' extra in pyproject.toml should carry pyinstaller — check it.)" >&2
    exit 1
fi

mkdir -p "$DIST"

# Fresh-slate the bundle. Repeated C1 runs appended stale Mach-Os into
# the old tree, which then failed verification without a clear cause.
robust_rmrf "$BUNDLE"

# Bake build provenance into the sidecar so any run / failure log can
# self-identify the source it was built from (mirrors the Swift host's
# GeneratedBuildInfo.swift). The bundled sidecar has no git repo at runtime,
# so the SHA must be frozen here. Written into the editable-installed package
# source (PyInstaller analyses it from there), then removed afterwards so
# subsequent dev runs fall back to live git instead of this frozen value.
BUILD_INFO="$ROOT/bristlenose/_build_info.py"
GIT_SHA="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
cleanup_build_info() { rm -f "$BUILD_INFO"; }
trap cleanup_build_info EXIT
cat > "$BUILD_INFO" <<EOF
# Generated by desktop/scripts/build-sidecar.sh — do not edit, do not commit.
GIT_SHA = "$GIT_SHA"
BUILD_DATE = "$BUILD_DATE"
EOF
echo "==> Baked build provenance: $GIT_SHA ($BUILD_DATE)"

echo "==> Building sidecar with PyInstaller..."
"$PYTHON" -m PyInstaller \
    --distpath "$DIST" \
    --workpath "$WORK" \
    --clean --noconfirm \
    "$SPEC"

echo "==> Bundle size:"
du -sh "$BUNDLE"

# Privacy manifest. Apple requires a PrivacyInfo.xcprivacy at the bundle
# root covering required-reason API usage by the embedded Python interpreter
# and vendored packages. Source kept at desktop/bristlenose-sidecar.PrivacyInfo.xcprivacy
# so it travels with the spec. C4 (28 Apr 2026).
PRIVACY_SRC="$DESKTOP_DIR/bristlenose-sidecar.PrivacyInfo.xcprivacy"
PRIVACY_DST="$BUNDLE/PrivacyInfo.xcprivacy"
if [ ! -f "$PRIVACY_SRC" ]; then
    echo "error: privacy manifest source missing at $PRIVACY_SRC" >&2
    exit 1
fi
cp "$PRIVACY_SRC" "$PRIVACY_DST"
echo "==> Privacy manifest: $PRIVACY_DST"

# Stamp the bundle with the source fingerprint captured at build START (above).
# The Xcode "Copy Sidecar Resources" phase recomputes it (check-sidecar-freshness.sh)
# and fails the build if a later Python OR frontend change left the bundle stale —
# the desktop app runs the bundled sidecar (and the SPA baked into it), not live
# source, so a missed rebuild silently ships old code. Written BEFORE
# sign-sidecar.sh so it's covered by the seal.
{
    echo "$SOURCE_HASH"
    echo "version=$("$PYTHON" -c 'import bristlenose; print(bristlenose.__version__)' 2>/dev/null || echo unknown)"
    echo "note=fingerprint of bristlenose/**/*.py + locales + frontend src; see check-sidecar-freshness.sh"
} > "$BUNDLE/.source-stamp"
echo "==> Stamped .source-stamp: $(head -1 "$BUNDLE/.source-stamp" | cut -c1-12)…"

echo "==> Done. Bundle: $BUNDLE"
echo "    Next: desktop/scripts/sign-sidecar.sh"
