#!/bin/bash
# PostToolUse hook: after an Edit/Write/MultiEdit to a frontend build input,
# remind that the bundled desktop .app's baked SPA is now STALE until the sidecar
# is rebuilt. The release/PyPI path is unaffected (CI builds the frontend on a
# clean checkout); this is purely about the locally-built .app, whose
# bristlenose/server/static/ is a point-in-time PyInstaller snapshot.
#
# Fires on the same inputs the sidecar source-fingerprint covers
# (sidecar-source-hash.sh): frontend/src (excluding tests), the Vite/TS config,
# package(-lock).json, index.html, and bristlenose/locales/** (bundled into the
# SPA via the @locales alias). Test files are excluded — they don't change the
# shipped bundle. Reminder only; never blocks. The Xcode freshness gate
# (check-sidecar-freshness.sh) is the hard enforcement.
#
# Matching is done on the full absolute path with `*/dir/*` globs — NOT a
# repo-relative slice — because the repo dir and the package dir are both named
# `bristlenose`, so `${path##*/bristlenose/}` over-strips (drops `bristlenose/`
# from `bristlenose/locales/...`). Glob-on-full-path sidesteps that entirely.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE_PATH" ] && exit 0

# Test files never change the shipped bundle — ignore them.
case "$FILE_PATH" in
  *.test.ts|*.test.tsx|*.test.js|*/__tests__/*) exit 0 ;;
esac

is_frontend_input=0
case "$FILE_PATH" in
  */frontend/src/*) is_frontend_input=1 ;;
  */frontend/index.html|*/frontend/vite.config.ts|*/frontend/tsconfig.json) is_frontend_input=1 ;;
  */frontend/package.json|*/frontend/package-lock.json) is_frontend_input=1 ;;
  */bristlenose/locales/*) is_frontend_input=1 ;;
esac
[ "$is_frontend_input" = "0" ] && exit 0

MSG="Frontend build input changed ($FILE_PATH). The bundled desktop .app bakes a snapshot of bristlenose/server/static/, so this edit is NOT in the .app until the sidecar is rebuilt: desktop/scripts/build-sidecar.sh (it runs npm build for you) [+ sign + clean build]. The Xcode 'Copy Sidecar Resources' freshness gate will now fail loudly until then. No action needed for: bristlenose serve --dev (Vite serves live source), browser QA, or PyPI/Homebrew/Snap (release CI builds the frontend on a clean checkout)."

# Surface as PostToolUse context for the model. Never blocks.
jq -n --arg msg "$MSG" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $msg}}'
exit 0
