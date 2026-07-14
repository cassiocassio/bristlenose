#!/usr/bin/env bash
# Build the bristlenose desktop sidecar via PyInstaller (Track C), PER-LAYER
# INCREMENTAL: each layer (Frontend / Venv / PyInstaller) rebuilds only when its
# own inputs changed, so a Swift-only or one-line-Python iteration doesn't pay the
# from-scratch venv-recreate cost. `--force` reproduces the original always-full
# behaviour (and is what build-all.sh / release uses).
#
# Produces a --onedir bundle at desktop/Bristlenose/Resources/bristlenose-sidecar/.
# Signing is a separate step (sign-sidecar.sh / sign-ffmpeg.sh); the orchestrator
# is ensure-sidecar.sh. See docs/design-desktop-build-orchestration.md.
#
# CORE PRINCIPLE (from review): stamps attest INPUTS; every skip path also makes
# an OUTPUT-side check the stamp can't fake (built artefact present + non-empty).
# A frontend rebuild forces a PyInstaller rebuild (the bundle's baked static/ is a
# copy, not a live reference) — closing the "static/ wiped, stamp still green" hole.
#
# Layers + their stamps:
#   F  frontend   → bristlenose/server/static/.frontend-stamp   (frontend_source_hash)
#   V  venv       → .venv-sidecar/.deps-stamp + .deps-ok         (pyproject + pip freeze)
#   P  pyinstaller→ <bundle>/.source-stamp                       (sidecar_source_hash)
#
# Usage: build-sidecar.sh [--force] [--dry-run]
#   --force    rebuild every layer from scratch (original behaviour; release uses this)
#   --dry-run  report what WOULD rebuild and why; do no work; exit 0
#
# Prerequisites: python3.12 + Node 24 on PATH; frontend deps installed.
# The dedicated .venv-sidecar carries only .[serve,apple,desktop] so contributor
# packages never reach PyInstaller's analysis.

set -euo pipefail

FORCE=0
DRY_RUN=0
for arg in "$@"; do
    case "$arg" in
        --force)   FORCE=1 ;;
        --dry-run) DRY_RUN=1 ;;
        *) echo "error: unknown argument: $arg (expected --force / --dry-run)" >&2; exit 2 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="$(cd "$DESKTOP_DIR/.." && pwd)"
SIDECAR_VENV="$ROOT/.venv-sidecar"
PYTHON="$SIDECAR_VENV/bin/python"
SPEC="$DESKTOP_DIR/bristlenose-sidecar.spec"
DIST="$DESKTOP_DIR/Bristlenose/Resources"
WORK="$DESKTOP_DIR/build/pyinstaller"
BUNDLE="$DIST/bristlenose-sidecar"
FRONTEND_DIR="$ROOT/frontend"
STATIC_DIR="$ROOT/bristlenose/server/static"

FRONTEND_STAMP="$STATIC_DIR/.frontend-stamp"
DEPS_STAMP="$SIDECAR_VENV/.deps-stamp"
DEPS_OK="$SIDECAR_VENV/.deps-ok"

_say() { echo "==> $*"; }
_layer() { echo "    [$1] $2"; }   # e.g. _layer F "REBUILD — frontend source moved"

# Robust recursive delete for large trees on a Spotlight-indexed volume (rm races
# mdworker/fseventsd → ENOTEMPTY). Rename out of the way (atomic), then rm with
# retries; sweep orphans a prior failed run left.
robust_rmrf() {
    local target="$1"
    rm -rf "${target}".delete-* 2>/dev/null || true
    [ -e "$target" ] || return 0
    local trash="${target}.delete-$$"
    mv "$target" "$trash" 2>/dev/null || trash="$target"
    local n
    for n in 1 2 3 4 5; do
        rm -rf "$trash" 2>/dev/null && return 0
        sleep 1
    done
    rm -rf "$trash" || echo "warning: could not fully remove $trash (left for next run)" >&2
}

# ---------------------------------------------------------------------------
# Preconditions — run UNCONDITIONALLY, before any skip decision (a missing tool
# must be a loud error, never a quiet skip). Per review finding 6.
# ---------------------------------------------------------------------------
# Xcode build phases run with a stripped PATH (/usr/bin:/bin:/usr/sbin:/sbin +
# the developer dir) that omits whatever toolchain installs python3.12 / node —
# so these resolve in a login shell but not when ensure-sidecar.sh calls us from
# the "Ensure Sidecar Fresh" build phase. We RESPECT an already-resolvable tool
# (a correctly-configured PATH wins untouched) and only fall back to this
# project's documented Mac toolchain — the Homebrew prefix (.tool-versions /
# desktop/CLAUDE.md) — when the tool is missing. A contributor on a different
# toolchain (mise/asdf/pyenv/python.org) just needs their python3.12 + node on
# the build's PATH; we never override it. Not a universal resolver by design —
# the loud errors below tell a non-Homebrew setup exactly what to do.
if ! command -v python3.12 >/dev/null 2>&1; then
    for _brew_bin in /opt/homebrew/bin /usr/local/bin; do
        [ -d "$_brew_bin" ] && PATH="$_brew_bin:$PATH"
    done
fi
# node@24 is keg-only on Homebrew (never in the prefix bin above), so it needs
# its own keg prepend — again only when npm isn't already resolvable.
if ! command -v npm >/dev/null 2>&1 && [ -d /opt/homebrew/opt/node@24/bin ]; then
    PATH="/opt/homebrew/opt/node@24/bin:$PATH"
fi
if ! command -v npm >/dev/null 2>&1; then
    echo "error: npm/node not found on PATH. This project pins node 24 (.tool-versions)." >&2
    echo "       Install it (brew install node@24) or put your node 24 bin on the build's PATH." >&2
    exit 1
fi
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "error: frontend/node_modules missing — (cd frontend && npm ci --legacy-peer-deps)" >&2
    exit 1
fi
if ! command -v python3.12 >/dev/null; then
    echo "error: python3.12 not found on PATH. This project pins python 3.12 (.tool-versions)." >&2
    echo "       Install it (brew install python@3.12) or put your python3.12 on the build's PATH." >&2
    echo "       (Xcode build phases use a stripped PATH; this script falls back to the Homebrew prefix.)" >&2
    exit 1
fi

# shellcheck source=sidecar-source-hash.sh
. "$SCRIPT_DIR/sidecar-source-hash.sh"

FRONTEND_HASH="$(frontend_source_hash "$ROOT")"
SOURCE_HASH="$(sidecar_source_hash "$ROOT")"
# An empty/malformed hash must NEVER resolve to "skip" — fail loud (finding 6).
for h in "$FRONTEND_HASH" "$SOURCE_HASH"; do
    case "$h" in
        [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) : ;;
        *) echo "error: empty/malformed source fingerprint ('$h') — aborting rather than skipping" >&2; exit 1 ;;
    esac
done

# Deps fingerprint for the V gate: pyproject content + the ACTUALLY-installed
# package set. Catches a half-installed venv and a manual change; a transitive
# republish within the same >= floor is the documented residual that release
# --force covers. Only called when the venv exists.
_deps_fingerprint() {
    { shasum -a 256 "$ROOT/pyproject.toml"; "$PYTHON" -m pip freeze; } \
        | shasum -a 256 | cut -d ' ' -f1
}

# ---------------------------------------------------------------------------
# Layer F — frontend (npm run build → bristlenose/server/static/)
# ---------------------------------------------------------------------------
frontend_rebuilt=0
need_f=0; f_reason=""
if [ "$FORCE" = 1 ]; then need_f=1; f_reason="forced"
elif [ ! -s "$STATIC_DIR/index.html" ]; then need_f=1; f_reason="output missing (static/index.html absent)"
elif [ "$FRONTEND_HASH" != "$(cat "$FRONTEND_STAMP" 2>/dev/null || true)" ]; then need_f=1; f_reason="frontend source moved"
fi

if [ "$need_f" = 1 ]; then
    _layer F "REBUILD — $f_reason"
    frontend_rebuilt=1          # intent — drives the P cascade even under --dry-run
    if [ "$DRY_RUN" = 0 ]; then
        ( cd "$FRONTEND_DIR" && npm run build )
        mkdir -p "$STATIC_DIR"
        printf '%s\n' "$FRONTEND_HASH" > "$FRONTEND_STAMP"
    fi
else
    _layer F "skip (${FRONTEND_HASH:0:12} matches; output present)"
fi

# ---------------------------------------------------------------------------
# Layer V — sidecar venv (.venv-sidecar, .[serve,apple,desktop])
# ---------------------------------------------------------------------------
venv_rebuilt=0
need_v=0; v_reason=""
if [ "$FORCE" = 1 ]; then need_v=1; v_reason="forced"
elif [ ! -x "$PYTHON" ]; then need_v=1; v_reason="venv missing"
elif [ ! -f "$DEPS_OK" ]; then need_v=1; v_reason="no .deps-ok sentinel (half-install?)"
elif [ "$(_deps_fingerprint)" != "$(cat "$DEPS_STAMP" 2>/dev/null || true)" ]; then need_v=1; v_reason="deps changed (pyproject or installed set)"
fi

if [ "$need_v" = 1 ]; then
    _layer V "REBUILD — $v_reason"
    venv_rebuilt=1              # intent — drives the P cascade even under --dry-run
    if [ "$DRY_RUN" = 0 ]; then
        rm -f "$DEPS_OK"                 # clear sentinel BEFORE mutating — a crash mid-install leaves no false-OK
        _say "Recreating sidecar venv at $SIDECAR_VENV"
        robust_rmrf "$SIDECAR_VENV"
        python3.12 -m venv "$SIDECAR_VENV"
        # Incremental (Xcode/dev) recreates reuse pip's local wheel cache — every
        # wheel is already on disk, so no network. --force (release) keeps
        # --no-cache-dir so the closure re-resolves against live PyPI and picks up
        # a transitive republish within a >= floor (the documented release audit).
        cache_bypass=""
        [ "$FORCE" = 1 ] && cache_bypass="--no-cache-dir"
        "$SIDECAR_VENV/bin/pip" install $cache_bypass --quiet --upgrade pip
        "$SIDECAR_VENV/bin/pip" install $cache_bypass -e "$ROOT[serve,apple,desktop]"
        if ! "$PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
            echo "error: PyInstaller not installed in fresh sidecar venv (check the 'desktop' extra)." >&2
            exit 1
        fi
        # Stamp + sentinel LAST, only after a fully successful install + tool check.
        _deps_fingerprint > "$DEPS_STAMP"
        date -u +%Y-%m-%dT%H:%M:%SZ > "$DEPS_OK"
    fi
else
    _layer V "skip (deps unchanged; .deps-ok present)"
fi

# ---------------------------------------------------------------------------
# Layer P — PyInstaller bundle. ALWAYS --clean on rebuild (warm workpath
# reintroduces the stale-Mach-O class). A frontend rebuild forces P (the bundle's
# baked static/ is a copy). Source move / venv rebuild / missing bundle also force.
# ---------------------------------------------------------------------------
SOURCE_STAMP="$BUNDLE/.source-stamp"
need_p=0; p_reason=""
if [ "$FORCE" = 1 ]; then need_p=1; p_reason="forced"
elif [ ! -x "$BUNDLE/bristlenose-sidecar" ]; then need_p=1; p_reason="bundle missing"
elif [ "$venv_rebuilt" = 1 ]; then need_p=1; p_reason="venv rebuilt"
elif [ "$frontend_rebuilt" = 1 ]; then need_p=1; p_reason="frontend rebuilt (rebundle static/)"
elif [ "$SOURCE_HASH" != "$(head -1 "$SOURCE_STAMP" 2>/dev/null || true)" ]; then need_p=1; p_reason="python/locale/frontend source moved"
fi

if [ "$need_p" = 1 ]; then
    _layer P "REBUILD — $p_reason"
    if [ "$DRY_RUN" = 0 ]; then
        mkdir -p "$DIST"

        # Bake build provenance (git SHA + UTC date) into the package source so a
        # run/failure log self-identifies. git runs here in whatever env invoked us
        # (Xcode's build phase is stripped — warn if the SHA can't resolve).
        BUILD_INFO="$ROOT/bristlenose/_build_info.py"
        GIT_SHA="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
        [ "$GIT_SHA" = "unknown" ] && echo "warning: git SHA unresolved (stripped build-phase env?) — provenance will read 'unknown'" >&2
        BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        trap 'rm -f "$BUILD_INFO"' EXIT
        cat > "$BUILD_INFO" <<EOF
# Generated by desktop/scripts/build-sidecar.sh — do not edit, do not commit.
GIT_SHA = "$GIT_SHA"
BUILD_DATE = "$BUILD_DATE"
EOF
        _say "Baked build provenance: $GIT_SHA ($BUILD_DATE)"

        # Fresh-slate the bundle (repeated runs appended stale Mach-Os otherwise).
        robust_rmrf "$BUNDLE"
        _say "Building sidecar with PyInstaller (--clean)..."
        "$PYTHON" -m PyInstaller --distpath "$DIST" --workpath "$WORK" --clean --noconfirm "$SPEC"
        _say "Bundle size: $(du -sh "$BUNDLE" | cut -f1)"

        # Privacy manifest (Apple required-reason API coverage) — under the seal.
        PRIVACY_SRC="$DESKTOP_DIR/bristlenose-sidecar.PrivacyInfo.xcprivacy"
        if [ ! -f "$PRIVACY_SRC" ]; then
            echo "error: privacy manifest source missing at $PRIVACY_SRC" >&2; exit 1
        fi
        cp "$PRIVACY_SRC" "$BUNDLE/PrivacyInfo.xcprivacy"

        # Stamp the bundle with the full source fingerprint (the freshness gate
        # recomputes + compares; the gate ALSO checks output presence the stamp
        # can't fake). Written before signing so it's sealed.
        {
            echo "$SOURCE_HASH"
            echo "version=$("$PYTHON" -c 'import bristlenose; print(bristlenose.__version__)' 2>/dev/null || echo unknown)"
            echo "note=fingerprint of bristlenose/**/*.py + locales + frontend src; see check-sidecar-freshness.sh"
        } > "$SOURCE_STAMP"
        _say "Stamped .source-stamp: ${SOURCE_HASH:0:12}…"
    fi
else
    _layer P "skip (${SOURCE_HASH:0:12} matches; bundle present)"
fi

# ---------------------------------------------------------------------------
# Output-side assertion (real runs only) — the bundle binary must exist. The
# in-bundle static/ assertion lives in the freshness gate (it knows the bundle
# layout); here we guard the thing this script directly produces.
# ---------------------------------------------------------------------------
if [ "$DRY_RUN" = 0 ] && [ ! -x "$BUNDLE/bristlenose-sidecar" ]; then
    echo "error: post-build output check failed — $BUNDLE/bristlenose-sidecar absent/not executable" >&2
    exit 1
fi

if [ "$DRY_RUN" = 1 ]; then
    _say "dry-run: no work performed."
else
    _say "Done. Bundle: $BUNDLE   (next: sign via ensure-sidecar.sh / sign-sidecar.sh)"
fi
