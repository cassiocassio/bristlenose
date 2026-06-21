#!/usr/bin/env bash
# Workflow skill logger — shared by new-feature / close-feature / new-branch /
# close-branch / new-release. Appends one JSON line per call to the workflow log.
#
# Usage:   bash .claude/skills/_shared/wflog.sh <skill> <step> [detail...]
# Env:
#   BRISTLENOSE_WORKFLOW_LOG    log path (default: .claude/workflow-log.jsonl)
#   BRISTLENOSE_WORKFLOW_DEBUG  if "1", also echo the line to stderr (debug mode)
#
# Never fails the caller: always exits 0, even if logging can't write.

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH"
hash -r 2>/dev/null || true
set -u

skill="${1:-?}"
step="${2:-?}"
shift 2 2>/dev/null || true
detail="${*:-}"

log="${BRISTLENOSE_WORKFLOW_LOG:-.claude/workflow-log.jsonl}"
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)"
branch="$(git branch --show-current 2>/dev/null || echo '?')"

mkdir -p "$(dirname "$log")" 2>/dev/null || true

line="$(python3 -c 'import json,sys; print(json.dumps({"ts":sys.argv[1],"skill":sys.argv[2],"step":sys.argv[3],"branch":sys.argv[4],"detail":sys.argv[5]}))' \
  "$ts" "$skill" "$step" "$branch" "$detail" 2>/dev/null)"

# Fallback if python3 is unavailable: write a minimal, still-valid JSON line.
if [ -z "$line" ]; then
  line="{\"ts\":\"$ts\",\"skill\":\"$skill\",\"step\":\"$step\",\"branch\":\"$branch\",\"detail\":\"(unescaped)\"}"
fi

printf '%s\n' "$line" >> "$log" 2>/dev/null || true

if [ "${BRISTLENOSE_WORKFLOW_DEBUG:-0}" = "1" ]; then
  printf '  ▸ [%s] %s/%s %s\n' "$ts" "$skill" "$step" "$detail" >&2
fi

exit 0
