#!/usr/bin/env python3
"""Timecode sanity per pass — the FINDINGS.md § 3 table, for any out/ directory.

The § 3 measurement was computed ad hoc. This makes it an instrument, so a
before/after comparison is the SAME calculation on both sides rather than two
readings that merely sound alike.

Three columns, and the third is the one that identified the defect:

  on exact minute   start AND end are whole minutes. The minutes-as-hours
                    mistake appends `:00`, so an affected value is always
                    divisible by 60. A real boundary lands there ~1 time in 60.
  out of range      end is past the end of the recording. Impossible, whatever
                    the cause.
  same set          whether those two sets are IDENTICAL. Four passes with no
                    exceptions is what made the mechanism certain rather than
                    suspected — two independent symptoms picking out one set of
                    quotes is not a coincidence.

    ./timecode_audit.py                        # every out/ directory
    ./timecode_audit.py --model openai_gpt-5.6-terra__padded
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
CORPUS = ROOT / "trial-runs/fossda-opensource/bristlenose-output/.bristlenose/intermediate"


def session_durations() -> dict[str, float]:
    """Each session's own last end_time — the same ceiling run.py reconstructs."""
    segs = json.loads((CORPUS / "session_segments.json").read_text())
    return {sid: max((r.get("end_time") or 0.0) for r in rows) for sid, rows in segs.items()}


def audit_pass(quotes: list[dict], durations: dict[str, float]) -> dict:
    exact, over, spans = set(), set(), []
    for i, q in enumerate(quotes):
        start = float(q.get("start_timecode") or 0.0)
        end = float(q.get("end_timecode") or 0.0)
        spans.append(end - start)
        if start % 60 == 0 and end % 60 == 0:
            exact.add(i)
        # +2s matches the guard's grace: a model may name an end a beat past the
        # last segment, and that is not this defect.
        if end > durations.get(q.get("session_id", "?"), 0.0) + 2.0:
            over.add(i)
    return {
        "n": len(quotes),
        "exact": len(exact),
        "over": len(over),
        "same_set": exact == over,
        "median_span": statistics.median(spans) if spans else 0.0,
    }


def report(name: str, passes: list[list[dict]], durations: dict[str, float]) -> None:
    print(f"\n\033[1m{name}\033[0m")
    print(f"  {'pass':<6}{'quotes':>8}{'exact min':>11}{'out of range':>14}"
          f"{'same set':>10}{'median span':>13}")
    tot_n = tot_over = 0
    for i, quotes in enumerate(passes, start=1):
        r = audit_pass(quotes, durations)
        tot_n += r["n"]
        tot_over += r["over"]
        print(f"  {i:<6}{r['n']:>8}{r['exact']:>11}{r['over']:>14}"
              f"{('yes' if r['same_set'] else 'NO'):>10}{r['median_span']:>12.1f}s")
    pct = 100 * tot_over / tot_n if tot_n else 0.0
    verdict = "CLEAN" if tot_over == 0 else f"{pct:.0f}% AFFECTED"
    print(f"  {'-' * 60}")
    print(f"  out of range, all passes    : {tot_over}/{tot_n}  ({pct:.1f}%)  -> {verdict}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", help="one out/ subdirectory; default is all of them")
    args = ap.parse_args()

    durations = session_durations()
    dirs = [OUT / args.model] if args.model else sorted(d for d in OUT.iterdir() if d.is_dir())
    if not dirs:
        print("no output directories -- run.py first", file=sys.stderr)
        return 1

    for d in dirs:
        files = sorted(d.glob("pass_*.json"), key=lambda p: int(p.stem.split("_")[1]))
        if not files:
            continue
        report(d.name, [json.loads(f.read_text()) for f in files], durations)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
