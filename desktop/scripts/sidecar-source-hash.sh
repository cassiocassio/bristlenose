#!/usr/bin/env bash
# Single source of truth for the "which Python is in the sidecar" fingerprint.
#
# Sourced by build-sidecar.sh (which writes the stamp into the bundle) and by
# check-sidecar-freshness.sh (which recomputes + compares at Xcode-build time).
# Keeping the recipe in one place means the writer and the checker cannot drift
# — drift between them would silently defeat the gate.
#
# SHA-256 over every `bristlenose/**/*.py`, hashed with paths RELATIVE to the
# repo root (via `cd`), so the fingerprint is content-only and stable across
# worktrees with identical source. Deterministic: paths are sorted before
# hashing, under `LC_ALL=C` so the byte-ordering is locale-independent (a
# locale-sensitive `sort` made the writer and checker disagree — caught
# 28 Jun 2026). bash 3.2-compatible (Xcode's default /bin/bash).
#
# Usage:  source sidecar-source-hash.sh; h="$(sidecar_source_hash "$REPO_ROOT")"
sidecar_source_hash() {
    ( cd "$1" && find bristlenose -name '*.py' -type f -print0 \
        | LC_ALL=C sort -z | xargs -0 shasum -a 256 ) | shasum -a 256 | cut -d ' ' -f1
}
