#!/usr/bin/env python3
"""Per-stage wall-time and LLM-time breakdown for a completed pipeline run.

Usage: scripts/perf-breakdown.py <output-dir>
  where <output-dir> contains .bristlenose/pipeline-manifest.json
  and .bristlenose/bristlenose.log

Wall time comes from the manifest's per-stage started_at/completed_at.
LLM time is the sum of `llm_request | ... | elapsed_ms=N` log lines,
bucketed into the stage whose interval contains the log timestamp.
LLM time is a cost *proxy* — real $ needs token counts the log doesn't have.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

LOG_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
LLM_LINE = re.compile(r"llm_request \| .* \| elapsed_ms=(\d+)")


def parse_log_ts(line: str) -> datetime | None:
    m = LOG_TS.match(line)
    if not m:
        return None
    # Log is naive local time; caller compares against manifest stages converted
    # to naive local (see main()).
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")


def main(out_dir: Path) -> int:
    manifest_path = out_dir / ".bristlenose" / "pipeline-manifest.json"
    log_path = out_dir / ".bristlenose" / "bristlenose.log"
    if not manifest_path.exists() or not log_path.exists():
        print(f"missing manifest or log in {out_dir}/.bristlenose/", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text())
    stages: list[tuple[str, datetime, datetime]] = []
    for name, s in manifest["stages"].items():
        if s.get("status") != "complete" or not s.get("started_at") or not s.get("completed_at"):
            continue
        # Manifest is tz-aware UTC; log is naive local. Convert both sides to
        # naive local so comparisons work regardless of system timezone.
        start = datetime.fromisoformat(s["started_at"]).astimezone().replace(tzinfo=None)
        end = datetime.fromisoformat(s["completed_at"]).astimezone().replace(tzinfo=None)
        stages.append((name, start, end))
    stages.sort(key=lambda x: x[1])

    llm_ms_by_stage: dict[str, int] = {n: 0 for n, _, _ in stages}
    llm_calls_by_stage: dict[str, int] = {n: 0 for n, _, _ in stages}
    unattributed_ms = 0
    unattributed_calls = 0

    for line in log_path.read_text().splitlines():
        m = LLM_LINE.search(line)
        if not m:
            continue
        ts = parse_log_ts(line)
        if ts is None:
            continue
        ms = int(m.group(1))
        matched = False
        for name, start, end in stages:
            if start <= ts <= end:
                llm_ms_by_stage[name] += ms
                llm_calls_by_stage[name] += 1
                matched = True
                break
        if not matched:
            unattributed_ms += ms
            unattributed_calls += 1

    total_wall = sum((e - s).total_seconds() for _, s, e in stages)
    total_llm = sum(llm_ms_by_stage.values()) / 1000.0

    print(f"project: {manifest.get('project_name')}   version: {manifest.get('pipeline_version')}")
    print(f"total wall: {total_wall:>7.1f}s     total llm: {total_llm:>7.1f}s   "
          f"({total_llm / total_wall * 100:.1f}% of wall)")
    print()
    print(f"{'stage':<22} {'wall s':>8} {'wall %':>7}   {'llm s':>7} {'llm %':>7} {'calls':>6}")
    print("-" * 64)
    for name, start, end in stages:
        wall = (end - start).total_seconds()
        llm = llm_ms_by_stage[name] / 1000.0
        wp = wall / total_wall * 100 if total_wall else 0
        lp = llm / total_llm * 100 if total_llm else 0
        print(f"{name:<22} {wall:>8.1f} {wp:>6.1f}%   {llm:>7.1f} {lp:>6.1f}% {llm_calls_by_stage[name]:>6}")
    if unattributed_calls:
        print(f"{'(unattributed)':<22} {'':>8} {'':>7}   {unattributed_ms / 1000:>7.1f} {'':>7} {unattributed_calls:>6}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1])))
