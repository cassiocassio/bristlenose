#!/bin/bash
# SessionStart hook: report the size of this project's MEMORY.md hot index.
#
# The index is loaded into context every session, so its size is a standing
# cost nobody is otherwise obliged to look at. It has drifted back to ~85% of
# budget twice after hand compaction (12 Sep 2026, 22 Sep 2026) because the
# only thing watching it was somebody remembering to look.
#
# Deliberately a REPORT, not a gate -- it never blocks a session and never
# edits anything. Growth is usually legitimate; what was missing was the
# number, not permission.
#
# Two things it refuses to do quietly, per CLAUDE.md's gate policy:
#   - if it cannot find the index it SAYS SO rather than printing nothing
#     (a silent check is indistinguishable from a passing one)
#   - it names the directory it read. Worktrees do NOT share a memory dir:
#     each project slug gets its own, and a worktree's holds 1-3 files while
#     the main repo's holds ~476. A size read in the wrong one is meaningless,
#     so the path is part of the answer, not a detail.

budget=24576   # 24 KiB -- the read limit the index has been sized against.
               # UNVERIFIED: no hook or doc in this tree enforces it; it is the
               # figure the 13 Sep 2026 compaction note cited. Treat as a
               # yardstick, not a contract.

root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$root" ] || exit 0

# Claude Code's project slug: the absolute path with '/' replaced by '-'.
slug=$(printf '%s' "$root" | tr '/' '-')
index="$HOME/.claude/projects/$slug/memory/MEMORY.md"

if [ ! -f "$index" ]; then
  # Not an error on a fresh clone or a worktree that has no memory yet --
  # but say which path was tried, so "no output" never means "fine".
  echo "memory: no index at ~/.claude/projects/$slug/memory/MEMORY.md"
  exit 0
fi

bytes=$(wc -c < "$index" | tr -d ' ')
files=$(find "$(dirname "$index")" -maxdepth 1 -name '*.md' | wc -l | tr -d ' ')
pct=$(( bytes * 100 / budget ))

line="memory: MEMORY.md ${bytes} B (${pct}% of ${budget}) · ${files} files · $slug"
if [ "$pct" -ge 90 ]; then
  echo "$line  <-- COMPACT IT"
elif [ "$pct" -ge 80 ]; then
  echo "$line  <-- getting full"
else
  echo "$line"
fi
