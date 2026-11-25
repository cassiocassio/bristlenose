#!/usr/bin/env python3
"""How long CI makes a change wait: a MEASUREMENT, not a gate.

Nothing calls this and nothing should say a number is "enforced by" it. It
reads recent `ci.yml` runs through `gh` and prints, per run and as medians:

  verdict   push → the last BLOCKING job finished (the run's real answer)
  c1        push → the first finished blocking verdict on a run of the SAME
            event whose head contains this run's head (differs from `verdict`
            only when a later run answers first, e.g. after cancellation; a
            dispatch that answers a push first is not seen)
  macq      median wait of the macOS cells for a runner
  green     push → run conclusion (what the green tick waits for)

Blocking vs informational is classified BY NAME, because the API does not
expose `continue-on-error`: the `mypy` cell (`ci.yml::gates`, a ratchet) is
informational on every event. Before 25 Nov 2026 the `test (*, macos-latest)`
cells also ran, informational, on push and pull_request; they are still
classed informational there so older runs measure the same way, and since then
they don't run on a push at all. Scheduled (nightly) runs are their own event,
so they never enter the push medians.
Attempt 1 only; re-run and unfinished runs are counted, not measured. Green,
red and cancelled runs are counted separately. Until e2e stopped needing the
test matrix (25 Nov 2026) a red test cell skipped e2e, so red-run medians from
before that date finish early for the wrong reason.

Plan and metric definitions: the test-speed plan (C1, C3, C4).

    scripts/ci-timing.py                       # last 30 push runs
    scripts/ci-timing.py --event workflow_dispatch --limit 5
    scripts/ci-timing.py --json                # machine-readable
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from datetime import datetime
from typing import Any

WORKFLOW = "ci.yml"
GH_TIMEOUT_S = 60


def gh_json(args: list[str]) -> Any:
    out = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=GH_TIMEOUT_S, check=True
    ).stdout
    return json.loads(out)


def ts(value: str | None) -> datetime | None:
    if not value or value.startswith("0001"):
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def minutes(start: datetime, end: datetime | None) -> float | None:
    return None if end is None else round((end - start).total_seconds() / 60, 1)


def is_informational(job_name: str, event: str) -> bool:
    job_name = job_name.split(" / ")[-1]  # a reusable-workflow call prefixes `ci / `
    if job_name == "mypy":
        return True
    return event != "workflow_dispatch" and job_name.endswith("macos-latest)")


def is_ancestor(old: str, new: str) -> bool | None:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", old, new], capture_output=True, timeout=30
    )
    if proc.returncode in (0, 1):
        return proc.returncode == 0
    return None  # a sha this clone doesn't have


def measure(event: str, limit: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    runs = gh_json([
        "run", "list", "--workflow", WORKFLOW, "--event", event, "--limit", str(limit),
        "--json", "databaseId,headSha,createdAt,updatedAt,conclusion,status,attempt",
    ])
    rows = []
    skipped = {"in_progress": 0, "reruns": 0}
    for run in runs:
        if run["status"] != "completed":
            skipped["in_progress"] += 1
            continue
        if run.get("attempt", 1) != 1:
            skipped["reruns"] += 1
            continue
        created = ts(run["createdAt"])
        assert created is not None
        jobs = gh_json(["run", "view", str(run["databaseId"]), "--json", "jobs"])["jobs"]
        blocking_ends, mac_waits = [], []
        for job in jobs:
            started, done = ts(job.get("startedAt")), ts(job.get("completedAt"))
            if job["name"].endswith("macos-latest)") and started:
                mac_waits.append((started - created).total_seconds() / 60)
            if job.get("conclusion") == "skipped" or is_informational(job["name"], event):
                continue
            if done:
                blocking_ends.append(done)
        rows.append({
            "run": run["databaseId"],
            "sha": run["headSha"],
            "conclusion": run["conclusion"],
            "created": created,
            "verdict_at": max(blocking_ends) if blocking_ends else None,
            "verdict": minutes(created, max(blocking_ends)) if blocking_ends else None,
            "macq": round(statistics.median(mac_waits), 1) if mac_waits else None,
            "green": minutes(created, ts(run["updatedAt"])),
        })
    rows.sort(key=lambda r: r["created"])
    unknown = 0
    for i, row in enumerate(rows):
        answers = []
        for later in rows[i:]:
            if later["conclusion"] == "cancelled" or later["verdict_at"] is None:
                continue
            if later is row:
                answers.append(later["verdict_at"])
                continue
            contains = is_ancestor(row["sha"], later["sha"])
            unknown += contains is None
            if contains is True:
                answers.append(later["verdict_at"])
        row["c1"] = minutes(row["created"], min(answers)) if answers else None
    return rows, {**skipped, "unknown_ancestry": unknown}


def med(rows: list[dict[str, Any]], key: str) -> float | None:
    vals = [r[key] for r in rows if r[key] is not None]
    return round(statistics.median(vals), 1) if vals else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--event", default="push", choices=["push", "workflow_dispatch", "pull_request"])
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        rows, not_measured = measure(args.event, args.limit)
    except (subprocess.SubprocessError, OSError, ValueError) as exc:
        print(f"could not read CI runs through gh: {exc}", file=sys.stderr)
        return 2
    by = {c: [r for r in rows if r["conclusion"] == c] for c in ("success", "failure", "cancelled")}
    summary = {
        "event": args.event,
        "runs": len(rows),
        "counts": {c: len(v) for c, v in by.items()},
        "not_measured": not_measured,
        "median_green_runs": {k: med(by["success"], k) for k in ("verdict", "c1", "macq", "green")},
        "median_all_runs": {k: med(rows, k) for k in ("verdict", "c1", "macq", "green")},
    }
    if args.json:
        out = [{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in r.items()} for r in rows]
        print(json.dumps({"summary": summary, "runs": out}, indent=2))
        return 0
    print(f"{'run':>12}  {'conclusion':10} {'verdict':>8} {'c1':>6} {'macq':>6} {'green':>6}  (minutes)")
    for r in rows:
        cells = [r[k] if r[k] is not None else "-" for k in ("verdict", "c1", "macq", "green")]
        print(f"{r['run']:>12}  {r['conclusion']:10} {cells[0]:>8} {cells[1]:>6} {cells[2]:>6} {cells[3]:>6}")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
