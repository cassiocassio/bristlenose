#!/usr/bin/env python3
"""What changed between passes — the Jul 2026 metrics, on whatever run.py wrote.

THE TWO RECOVERY RULES, AND WHY THERE ARE TWO

A star (or a tag, or an edit) is pinned to a quote. Re-extract the interview and
the model may return that quote with slightly different boundaries, split into
two, or not at all. The merge rule in `docs/design-incremental-analysis.md` has
to decide whether the star survives.

  single best-overlap  the ONE re-run quote overlapping the reference quote most
                       covers >=70% of it. This is the naive reading, and the
                       Jul run is its empirical refutation: 80.9-83.5%, so about
                       one star in five was at risk.
  union / split-credit  ALL re-run quotes overlapping it together cover >=70%.
                       This credits a quote that got split, and it is what
                       cleared the >=90% target at 94.6%.

The gap between the two lines is the value of the union rule. The quotes no rule
recovers are the fragile tail — ~9% in Jul, and no boundary logic reaches them
because the model simply did not return them that time.

Pass 1 is the reference; every later pass is a re-extraction of it. Comparisons
are within a session, on the transcript timeline.

    ./analyse.py                      every model directory under out/
    ./analyse.py --model anthropic_claude-sonnet-4-6
"""

from __future__ import annotations

import argparse
import difflib
import json
import statistics
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
THRESHOLD = 0.70


def span(q: dict) -> tuple[float, float]:
    return float(q.get("start_timecode") or 0.0), float(q.get("end_timecode") or 0.0)


def overlap(a: dict, b: dict) -> float:
    """Fraction of ``a``'s duration covered by ``b``.

    A zero-length reference span is a real thing in the corpus -- one FOSSDA
    quote has ``start == end`` -- and returning 0 for it made a pass compared
    against ITSELF score 98.6% instead of 100%. That is a metric quietly
    understating recovery, which in this experiment is the direction that looks
    like a finding. The limit as the span shrinks to a point is "does the
    candidate contain the point", so that is what it returns.
    """
    a0, a1 = span(a)
    b0, b1 = span(b)
    if a1 <= a0:
        return 1.0 if b0 <= a0 <= b1 else 0.0
    return max(0.0, min(a1, b1) - max(a0, b0)) / (a1 - a0)


def by_session(quotes: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for q in quotes:
        out.setdefault(q.get("session_id", "?"), []).append(q)
    return out


def compare(ref: list[dict], run: list[dict]) -> dict:
    """One reference pass against one re-extraction."""
    run_by = by_session(run)
    single = union = text_same = 0
    drifts: list[tuple[float, float]] = []
    sims: list[float] = []
    recovered_ids: set[int] = set()

    for i, q in enumerate(ref):
        cands = run_by.get(q.get("session_id", "?"), [])
        overlaps = [(overlap(q, c), c) for c in cands]
        best, best_c = max(overlaps, default=(0.0, None), key=lambda t: t[0])
        # Union credits every overlapping fragment, which is the point of the
        # rule: a reference quote split in two is still that quote.
        total = min(1.0, sum(o for o, _ in overlaps))
        if best >= THRESHOLD:
            single += 1
        if total >= THRESHOLD:
            union += 1
            recovered_ids.add(i)
        if best_c is not None and best > 0:
            r0, r1 = span(q)
            c0, c1 = span(best_c)
            drifts.append((c0 - r0, c1 - r1))
            sim = difflib.SequenceMatcher(
                None, q.get("text", ""), best_c.get("text", "")).ratio()
            sims.append(sim)
            # The stricter reading, and the one a researcher experiences.
            # Overlap is measured on the TIMELINE, and a model that anchors
            # timecodes to segment boundaries scores a high overlap while
            # returning materially different text -- on gemini-3.8-flash, 29 of
            # 61 quotes were "recovered" at >=70% overlap with text similarity
            # below 0.90. The star survives; the words under it moved.
            if best >= THRESHOLD and sim >= 0.90:
                text_same += 1

    n = len(ref) or 1
    return {
        "n_ref": len(ref), "n_run": len(run),
        "single_pct": 100 * single / n,
        "union_pct": 100 * union / n,
        "text_pct": 100 * text_same / n,
        "median_start_drift": statistics.median([d[0] for d in drifts]) if drifts else None,
        "median_end_drift": statistics.median([d[1] for d in drifts]) if drifts else None,
        "median_similarity": statistics.median(sims) if sims else None,
        "recovered": recovered_ids,
    }


def report(name: str, passes: list[list[dict]]) -> None:
    print(f"\n\033[1m{name}\033[0m")
    if len(passes) < 2:
        print("  only one pass on disk — nothing to compare")
        return
    ref, runs = passes[0], passes[1:]
    print(f"  reference pass: {len(ref)} quotes")
    print(f"  {'pass':<6}{'quotes':>8}{'single':>9}{'union':>8}{'+text':>8}"
          f"{'Δstart':>9}{'Δend':>8}{'text sim':>10}")
    singles, unions, texts, counts = [], [], [], [len(ref)]
    ever: set[int] = set()
    for i, run in enumerate(runs, start=2):
        r = compare(ref, run)
        ever |= r["recovered"]
        singles.append(r["single_pct"])
        unions.append(r["union_pct"])
        texts.append(r["text_pct"])
        counts.append(r["n_run"])
        ds, de = r["median_start_drift"], r["median_end_drift"]
        print(f"  {i:<6}{r['n_run']:>8}{r['single_pct']:>8.1f}%{r['union_pct']:>7.1f}%"
              f"{r['text_pct']:>7.1f}%"
              f"{ds if ds is None else f'{ds:+.1f}s':>9}"
              f"{de if de is None else f'{de:+.1f}s':>8}"
              f"{r['median_similarity'] or 0:>10.2f}")

    fragile = [i for i in range(len(ref)) if i not in ever]
    print(f"  {'-' * 56}")
    print(f"  single best-overlap >={THRESHOLD:.0%}  : "
          f"{statistics.mean(singles):.1f}%  (worst {min(singles):.1f}%)")
    print(f"  union / split-credit >={THRESHOLD:.0%} : "
          f"{statistics.mean(unions):.1f}%  (worst {min(unions):.1f}%)")
    print(f"  ...and text also >=0.90     : "
          f"{statistics.mean(texts):.1f}%  (worst {min(texts):.1f}%) "
          f"<- what the researcher reads")
    print(f"  quote count across passes   : {counts}  "
          f"(spread {max(counts) - min(counts)})")
    print(f"  fragile tail                : {len(fragile)}/{len(ref)} "
          f"({100 * len(fragile) / (len(ref) or 1):.1f}%) recovered by NO pass")
    print("  Jul 2026 baseline           : 80.9–83.5% single · 94.6% union · ~9% fragile")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", help="one out/ subdirectory; default is all of them")
    args = ap.parse_args()

    dirs = [OUT / args.model] if args.model else sorted(d for d in OUT.glob("*") if d.is_dir())
    if not dirs:
        raise SystemExit(f"error: nothing under {OUT} — run.py has not been run")
    for d in dirs:
        files = sorted(d.glob("pass_*.json"), key=lambda p: int(p.stem.split("_")[1]))
        report(d.name, [json.loads(f.read_text()) for f in files])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
