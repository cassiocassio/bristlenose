#!/usr/bin/env bash
# check-release-freeze.sh — refuse a commit while a release run is live.
#
# Run by pre-commit (.pre-commit-config.yaml). A `release.sh run` holds
# .release/<version>/.lock/pid in the main checkout for as long as the driver
# is running. A commit landing on main in that window moves HEAD under the
# release: the run's moved-HEAD guard then rebuilds the app and the .dmg and
# re-dispatches strict CI (safe, but 30-40 minutes), and new work landing that
# way changes what the release contains — 0.34.0 was planned as 0.33.1 and
# became a minor because a feature reached main first, with sessions frozen
# only by messages sent between them.
#
# What it does NOT cover, so nobody reads it as a full freeze:
#   - the time before `run` starts and after the driver exits, including a run
#     stopped by a failed step and waiting for `release.sh retry` (that is when
#     a fix is supposed to land);
#   - pushes of commits made earlier, `git commit --no-verify`, and commits on
#     another machine or in a cloud session — it guards local commits only;
#   - a run started from a worktree, whose lock lives in that worktree.
#
# Lets through:
#   - the release's own commits (release.sh exports BN_RELEASE_RUN to its steps)
#   - a deliberate fix landed mid-release: BN_RELEASE_FREEZE_OK=1 git commit …
#   - a lock whose pid is dead, or now belongs to some other program (a driver
#     killed with -9 cannot remove its lock, and macOS reuses pids)
#
# Exit 0 = commit may proceed; 1 = refused, with the reason and the way out.

set -uo pipefail

[ -n "${BN_RELEASE_RUN:-}" ] && exit 0
[ "${BN_RELEASE_FREEZE_OK:-}" = 1 ] && exit 0

# .release/ lives beside the MAIN checkout's .git, so a worktree commit is
# frozen by a run started in the main repo too.
common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || exit 0
root="$(dirname "$common")"

live=""
for pidfile in "$root"/.release/*/.lock/pid; do
    [ -f "$pidfile" ] || continue
    pid="$(tr -cd '0-9' < "$pidfile")"
    [ -n "$pid" ] || continue
    kill -0 "$pid" 2>/dev/null || continue
    ps -p "$pid" -o command= 2>/dev/null | grep -qF 'release.sh run' || continue
    v="${pidfile#"$root"/.release/}"; v="${v%%/*}"
    live="$v (pid $pid)"
    break
done

[ -z "$live" ] && exit 0

cat >&2 <<EOF
✗ release $live is running — main is frozen while it runs.
  A commit now moves HEAD under the release: it rebuilds the app and the .dmg
  and re-runs strict CI, and new work can change what the release contains.
  Wait for the run to finish, or, for a fix the release needs:
    BN_RELEASE_FREEZE_OK=1 git commit …
  If no release is actually running (a crashed driver), remove the stale lock:
    rm -rf "$root/.release/${live%% *}/.lock"
EOF
exit 1
