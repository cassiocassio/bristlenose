#!/usr/bin/env bash
# Reset Bristlenose to a "clean-ish profile" feel without macOS user switching.
#
# ⚠️  HAZARD — read before running on a sandboxed build:
# This script calls reset-sandbox-state.sh, which wipes
# ~/Library/Containers/app.bristlenose/ wholesale. Under a sandboxed build
# that container holds:
#   • projects.json    — your project list (USER DATA)
#   • consentLog       — AI-disclosure audit trail (legally significant,
#                        Apple guideline 5.1.2(i))
#   • aiConsentVersion — consent tracking
# A run will lose all three. For Track A sandbox iteration that's intentional.
# For a "clean-ish UX walk" run on a build with real projects, snapshot these
# manually first or extend with a --keep-projects flag.
#
# Unsandboxed Debug builds: same data lives at
# ~/Library/Application Support/Bristlenose/projects.json and
# ~/Library/Preferences/app.bristlenose.plist — this script does NOT touch
# those paths, so unsandboxed projects survive.
#
# Why this exists: a real fresh-profile walkthrough is high cost (fast user
# switching is sluggish on a 32 GB machine with everything open, and you can't
# paste between profiles). For most regression sweeps, clearing the sandbox
# container + dev caches + browser site-data gets ~80% of the clean-profile
# signal in ~2 minutes. The TestFlight cohort is the right venue for the
# remaining 20% (holistic first-impression feel).
#
# What this does:
#   1. Calls reset-sandbox-state.sh   (processes, ports, container, defaults)
#   2. Wipes Xcode DerivedData for Bristlenose
#   3. Wipes Python __pycache__ across the repo
#   4. Wipes frontend Vite cache + dist
#   5. Optional flags for heavier resets (model caches, per-project output)
#   6. Prints browser-clear instructions (can't automate cleanly)
#
# What this does NOT touch:
#   - Keychain entries (user-managed; never scripted — see CLAUDE.md memory)
#   - HuggingFace / whisper model caches (use --models)
#   - Per-project bristlenose-output dirs (use --project <path>)
#   - pip cache (rarely the cause of stale-state bugs)
#
# Usage:
#   ./reset-app-state.sh                   # default: container + dev caches
#   ./reset-app-state.sh --models          # also clear model caches (slow re-download)
#   ./reset-app-state.sh --project <path>  # also wipe that project's output dir
#   ./reset-app-state.sh --dry-run         # show what would be deleted

set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "reset-app-state.sh: macOS only." >&2
  exit 2
fi

DRY_RUN=0
CLEAR_MODELS=0
PROJECT_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --models)  CLEAR_MODELS=1; shift ;;
    --project) PROJECT_PATH="${2:-}"; shift 2 ;;
    -h|--help)
      sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

run() {
  if [[ $DRY_RUN -eq 1 ]]; then
    printf '  [dry-run] %s\n' "$*"
  else
    printf '  %s\n' "$*"
    eval "$@"
  fi
}

note() { printf '\n=== %s ===\n' "$*"; }

note "1. Sandbox container + processes + UserDefaults"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "  [dry-run] $SCRIPT_DIR/reset-sandbox-state.sh --dry-run"
  "$SCRIPT_DIR/reset-sandbox-state.sh" --dry-run || true
else
  "$SCRIPT_DIR/reset-sandbox-state.sh"
fi

note "2. Xcode DerivedData (Bristlenose only)"
DERIVED_GLOB="$HOME/Library/Developer/Xcode/DerivedData/Bristlenose-*"
for d in $DERIVED_GLOB; do
  [[ -e "$d" ]] || continue
  run "rm -rf '$d'"
done

note "3. Python __pycache__ across repo"
if [[ $DRY_RUN -eq 1 ]]; then
  COUNT=$(find "$ROOT" -name __pycache__ -type d 2>/dev/null | wc -l | tr -d ' ')
  echo "  [dry-run] would remove $COUNT __pycache__ dirs under $ROOT"
else
  find "$ROOT" -name __pycache__ -type d -prune -exec rm -rf {} +
  echo "  done"
fi

note "4. Frontend Vite cache + dist"
for p in "$ROOT/frontend/node_modules/.vite" "$ROOT/frontend/dist"; do
  [[ -e "$p" ]] || continue
  run "rm -rf '$p'"
done

if [[ $CLEAR_MODELS -eq 1 ]]; then
  note "5. Whisper / HuggingFace model caches (slow re-download)"
  for p in "$HOME/.cache/whisper" "$HOME/.cache/huggingface"; do
    [[ -e "$p" ]] || continue
    run "rm -rf '$p'"
  done
fi

if [[ -n "$PROJECT_PATH" ]]; then
  note "6. Per-project output: $PROJECT_PATH"
  if [[ ! -d "$PROJECT_PATH" ]]; then
    echo "  warning: $PROJECT_PATH not a directory, skipping" >&2
  else
    OUT="$PROJECT_PATH/bristlenose-output"
    if [[ -e "$OUT" ]]; then
      run "rm -rf '$OUT'"
    else
      echo "  no bristlenose-output dir found; nothing to do"
    fi
  fi
fi

cat <<'EOF'

=== Browser site-data (manual — can't be automated cleanly) ===
  Safari:  Develop > Empty Caches, then Settings > Privacy > Manage Website Data
           > search "localhost" > Remove
  Chrome:  DevTools (⌥⌘I) > Application > Storage > Clear site data
           on http://localhost:8150 and http://localhost:5173
  Firefox: Settings > Privacy > Cookies and Site Data > Manage Data > localhost

=== Not touched (by design) ===
  - Keychain entries (manage in Passwords.app)
  - pip cache (~/Library/Caches/pip)
  - PyInstaller build/dist (rebuild via desktop/scripts/build-sidecar.sh)

Done.
EOF
