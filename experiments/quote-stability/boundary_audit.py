#!/usr/bin/env python3
"""Timecode sanity for TOPIC BOUNDARIES — the s09 audit, pointed at stage 8.

Same three columns and the same reasoning as `timecode_audit.py`; see that file.
The difference that matters: s09 has a range guard, so its saved quotes may have
been repaired before they hit disk. **s08 has no guard**, so what is written here
is exactly what the model returned -- no discriminator needed, and no repair to
see through.

    ./boundary_audit.py                 # the cached corpus + every out_s08/ arm
    ./boundary_audit.py --only cached
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CORPUS = ROOT / "trial-runs/fossda-opensource/bristlenose-output/.bristlenose/intermediate"
OUT_S08 = HERE / "out_s08"


def durations() -> dict[str, float]:
    segs = json.loads((CORPUS / "session_segments.json").read_text())
    return {s: max((r.get("end_time") or 0.0) for r in rows) for s, rows in segs.items()}


def audit(maps: list[dict], dur: dict[str, float], sessions: set[str] | None = None) -> None:
    print(f"  {'session':<9}{'dur':>8}{'bounds':>8}{'exact min':>11}"
          f"{'out of range':>14}{'/60 resolves':>14}")
    tot = over = exact = res = 0
    for m in sorted(maps, key=lambda x: (len(x["session_id"]), x["session_id"])):
        sid = m["session_id"]
        if sessions and sid not in sessions:
            continue
        d = dur.get(sid, 0.0)
        vals = [b["timecode_seconds"] for b in m["boundaries"]]
        o = [v for v in vals if v > d + 2.0]
        e = [v for v in vals if v and v % 60 == 0]
        r = [v for v in o if v % 60 == 0 and v / 60 <= d + 2.0]
        tot += len(vals)
        over += len(o)
        exact += len(e)
        res += len(r)
        print(f"  {sid:<9}{d:>8.0f}{len(vals):>8}{len(e):>11}{len(o):>14}{len(r):>14}")
    pct = 100 * over / tot if tot else 0.0
    print(f"  {'-' * 64}")
    verdict = "CLEAN" if over == 0 else f"{pct:.0f}% AFFECTED"
    print(f"  totals: {tot} boundaries, {exact} exact-minute, {over} out of range "
          f"({pct:.1f}%), {res} resolve under /60  -> {verdict}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="'cached', or an out_s08 subdirectory name")
    ap.add_argument("--sessions", nargs="*", help="restrict to these session ids")
    args = ap.parse_args()
    dur = durations()
    sessions = set(args.sessions) if args.sessions else None

    if args.only in (None, "cached"):
        print("\n\033[1mCACHED corpus (topic_boundaries.json)\033[0m")
        audit(json.loads((CORPUS / "topic_boundaries.json").read_text()), dur, sessions)

    if OUT_S08.exists():
        for d in sorted(OUT_S08.iterdir()):
            if not d.is_dir() or args.only == "cached" or (
                args.only is not None and d.name != args.only
            ):
                continue
            f = d / "boundaries.json"
            if f.exists():
                print(f"\n\033[1m{d.name}\033[0m")
                audit(json.loads(f.read_text()), dur, sessions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
