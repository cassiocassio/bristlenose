#!/bin/bash
# Fails if any TRACKED file matches a .gitignore rule — i.e. a file that was
# committed *before* its ignore rule existed (or force-added with `git add -f`)
# and is therefore silently public despite looking ignored.
#
# This is the exact failure mode that exposed the entire docs/private/ corpus:
# `.gitignore` listed `docs/private/`, but the files had been committed earlier,
# so git kept tracking them and the gitignore gave false confidence.
#
# Usage: scripts/check-tracked-vs-gitignore.sh
# Wired into .pre-commit-config.yaml; also safe to run manually or in CI.

set -euo pipefail

# `git ls-files -ci --exclude-standard` lists tracked files that the ignore
# rules say should be ignored. Empty output = clean.
offenders="$(git ls-files -ci --exclude-standard)"

if [ -n "$offenders" ]; then
  echo "✗ Tracked files that match a .gitignore rule (they are PUBLIC despite looking ignored):"
  echo "$offenders" | sed 's/^/    /'
  echo
  echo "  These were committed before their ignore rule existed, or force-added."
  echo "  The .gitignore entry is NOT protecting them. To fix each:"
  echo "      git rm --cached <path>   # untrack, keep the file on disk"
  echo "  then commit. If the content was ever pushed to a public remote, also"
  echo "  consider a history scrub (see docs/private/history-scrub-runbook.md)."
  exit 1
fi

echo "✓ No tracked files match .gitignore rules."
