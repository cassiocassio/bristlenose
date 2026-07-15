#!/usr/bin/env bash
# Single source of truth for the "what does the sidecar serve" fingerprint.
#
# Sourced by build-sidecar.sh (which writes the stamp into the bundle) and by
# check-sidecar-freshness.sh (which recomputes + compares at Xcode-build time).
# Keeping the recipe in one place means the writer and the checker cannot drift
# — drift between them would silently defeat the gate.
#
# SHA-256 over everything that determines what the sidecar SERVES, hashed with
# paths RELATIVE to the repo root (via `cd`), so the fingerprint is content-only
# and stable across worktrees with identical source. Three input sets:
#   1. bristlenose/**/*.py    — the Python the sidecar runs
#   2. bristlenose/locales/** — i18n JSON, bundled into the SPA via the @locales
#                               Vite alias AND read at runtime
#   3. frontend/ build inputs — src/ (minus tests), index.html, the Vite/TS
#                               config, package(-lock).json. These build into
#                               bristlenose/server/static/ (gitignored, NOT
#                               produced by PyInstaller). build-sidecar.sh runs
#                               `npm run build` so the bundled static/ matches
#                               them; a missed frontend build is caught here
#                               because this hash moves when frontend src does.
#   4. the PyInstaller spec    — desktop/bristlenose-sidecar.spec is the recipe
#                               for WHAT gets packaged (datas/binaries/hidden-
#                               imports). A spec-only edit changes bundle
#                               contents without touching any .py, so without
#                               this input the P-layer gate would skip the
#                               rebuild and re-ship the stale bundle. (Added
#                               14 Jul 2026 after a `collect_all("sqladmin")`
#                               fix silently didn't rebuild on Cmd+R.)
# Test files are excluded — they don't change the shipped bundle, so editing one
# must not force a sidecar rebuild. OS metadata (.DS_Store, AppleDouble ._*) is
# ALSO excluded — Finder touching a hashed dir must not drift the fingerprint
# (it did: a locales/.DS_Store made every build read "stale"; fixed 29 Jun 2026).
#
# Deterministic: paths are sorted before hashing, under `LC_ALL=C` so the
# byte-ordering is locale-independent (a locale-sensitive `sort` made the writer
# and checker disagree — caught 28 Jun 2026). bash 3.2-compatible (Xcode's
# default /bin/bash); BSD find/sort/xargs (-print0 / -z / -0).
#
# Usage:  source sidecar-source-hash.sh; h="$(sidecar_source_hash "$REPO_ROOT")"
sidecar_source_hash() {
    ( cd "$1" && {
        find bristlenose -name '*.py' -type f -print0
        find bristlenose/locales -type f \
            -not -name '.DS_Store' -not -name '._*' -print0
        _frontend_inputs_print0
        find desktop/bristlenose-sidecar.spec -type f -print0
      } | LC_ALL=C sort -z | xargs -0 shasum -a 256 ) | shasum -a 256 | cut -d ' ' -f1
}

# The frontend slice ONLY — the inputs that build into bristlenose/server/static/.
# Same recipe, sliced (one source of truth, per the single-fingerprint rationale
# above), so the per-layer F gate in build-sidecar.sh can decide "did the frontend
# move?" without re-resolving the Python half. Stays a strict subset of
# sidecar_source_hash's inputs.
frontend_source_hash() {
    ( cd "$1" && _frontend_inputs_print0 \
      | LC_ALL=C sort -z | xargs -0 shasum -a 256 ) | shasum -a 256 | cut -d ' ' -f1
}

# Shared find recipe for the frontend build inputs. NUL-delimited; callers pipe
# through `sort -z | xargs -0 shasum`. Defined once so the full-hash and the
# frontend-slice can never disagree on what "the frontend inputs" are.
_frontend_inputs_print0() {
    find frontend/src -type f \
        -not -name '*.test.ts' -not -name '*.test.tsx' \
        -not -name '*.test.js' -not -path '*/__tests__/*' \
        -not -name '.DS_Store' -not -name '._*' -print0
    find frontend/index.html frontend/vite.config.ts frontend/tsconfig.json \
        frontend/package.json frontend/package-lock.json -type f -print0
}
