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
# Test files are excluded — they don't change the shipped bundle, so editing one
# must not force a sidecar rebuild.
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
        find bristlenose/locales -type f -print0
        find frontend/src -type f \
            -not -name '*.test.ts' -not -name '*.test.tsx' \
            -not -name '*.test.js' -not -path '*/__tests__/*' -print0
        find frontend/index.html frontend/vite.config.ts frontend/tsconfig.json \
            frontend/package.json frontend/package-lock.json -type f -print0
      } | LC_ALL=C sort -z | xargs -0 shasum -a 256 ) | shasum -a 256 | cut -d ' ' -f1
}
