#!/usr/bin/env python3
"""Repair the minutes-as-hours defect in a project's cached topic boundaries.

For a project analysed BEFORE the 11 Sep 2026 prompt fix, whose
`topic_boundaries.json` carries 60x-too-large timecodes (FINDINGS.md § 3b). The
guard fixes new runs; it cannot reach data already on disk.

Repair, not re-run, and the difference matters: a fresh s08 call returns NEW
boundaries with NEW labels, and every cached quote's `topic_label` is an exact
boundary label string -- 106 of 106 in the FOSSDA corpus -- so replacing them
desynchronises the whole project. This corrects the 38 wrong timecodes and
touches nothing else.

Uses the SAME `repair_timecode` the pipeline uses, so what lands on disk is
exactly what the guard would have produced had it existed at the time.

    ./repair_cached_boundaries.py <project>              # dry run (default)
    ./repair_cached_boundaries.py <project> --apply

Refuses to write unless a snapshot exists, so the pre-repair state is always
recoverable and the measurements taken against it stay reproducible.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bristlenose.stages.timecode_guard import repair_timecode  # noqa: E402

SNAPSHOT_DIR = Path(__file__).resolve().parent / "out" / "_pinned-inputs"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path, help="project root (the folder holding bristlenose-output)")
    ap.add_argument("--apply", action="store_true", help="write the repair (default is a dry run)")
    ap.add_argument("--snapshot", action="store_true", help="write the pre-repair snapshot first")
    args = ap.parse_args()

    inter = args.project / "bristlenose-output" / ".bristlenose" / "intermediate"
    bpath, spath = inter / "topic_boundaries.json", inter / "session_segments.json"
    for p in (bpath, spath):
        if not p.exists():
            print(f"error: {p} not found", file=sys.stderr)
            return 1

    segs = json.loads(spath.read_text())
    dur = {s: max((r.get("end_time") or 0.0) for r in rows) for s, rows in segs.items()}
    tms = json.loads(bpath.read_text())

    snap = SNAPSHOT_DIR / f"{args.project.name}-topic_boundaries-preRepair.json"
    if args.snapshot:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        if snap.exists():
            print(f"snapshot already exists, left alone: {snap}")
        else:
            shutil.copy2(bpath, snap)
            print(f"snapshot written: {snap}")

    logging.disable(logging.CRITICAL)  # counting here; the pipeline does the logging
    scaled = dropped = untouched = 0
    for t in tms:
        sid, d = t["session_id"], dur.get(t["session_id"], 0.0)
        kept = []
        for b in t["boundaries"]:
            new, outcome = repair_timecode(
                b["timecode_seconds"], d, session_id=sid, field="timecode",
                raw=str(b["timecode_seconds"]), kind="boundary", out_of_range="drop",
            )
            if outcome == "dropped":
                dropped += 1
                continue
            if outcome == "scaled":
                scaled += 1
                b["timecode_seconds"] = new
            else:
                untouched += 1
            kept.append(b)
        t["boundaries"] = sorted(kept, key=lambda x: x["timecode_seconds"])
    logging.disable(logging.NOTSET)

    total = scaled + dropped + untouched
    print(f"\n{total} boundaries: {scaled} repaired, {dropped} dropped, {untouched} untouched")

    if not args.apply:
        print("\nDRY RUN — nothing written. Re-run with --apply (and --snapshot the first time).")
        return 0
    if not snap.exists():
        print(f"\nrefusing to write: no snapshot at {snap}\n"
              f"re-run with --snapshot so the pre-repair state stays recoverable",
              file=sys.stderr)
        return 1

    bpath.write_text(json.dumps(tms, indent=1))
    print(f"written: {bpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
