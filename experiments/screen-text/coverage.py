"""Is OCR on change-point frames enough? Compare frame-selection strategies against a dense OCR sweep.

    python3 experiments/screen-text/coverage.py trial-runs/_screen-text/<tag> [--show-misses]

Inputs (from select_frames.py and ocr_bench.py --frames-dir dense): frames.json (turns, ΔE 8 edges)
and ocr/vision_accurate-dense.json (Vision accurate on one frame every 2 s, frame n at (n-1)·2 s).

The dense sweep is the oracle. A **line** is an OCR line folded as search folds it (conf ≥ 0.5, at
least 6 characters, some letters). An **episode** is a run of dense frames in which a line is on
screen (one missing frame bridged, since OCR flickers). A strategy **covers** an episode when one of
its frames, snapped to the nearest dense frame, sees that line within the episode (±2 s). Every
strategy is judged on the same oracle, so the comparison is fair even though only the proposed set
was OCR'd at its exact times. Lines on screen for more than half the session (tab bars, bookmarks,
names under video tiles) are reported apart: any strategy covers them, and they are mostly chrome.

Strategies: turn (participant turns, 25% in); proposed (turn + 2 s after each ΔE 8 change inside a
participant turn — the thumbnail plan); all_changes (every turn of every speaker + every ΔE 8 change);
every_Ns (a fixed interval, for the same budget); edge_diff_<th> (pixel_diff.py's
kept frames, if present); text_diff (a frame whenever the set of lines differs
from the last kept frame's by Jaccard < 0.6 — OCR itself as the change detector; it needs the dense
sweep, so it is an upper bound at 2 s sampling, not a free option). Prints aggregates only, unless
--show-misses, which prints the missed episodes' text to stdout (private: do not paste it anywhere).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from score import fold  # noqa: E402

STEP = 2.0


def lines_of(frame: dict) -> set[str]:
    out = set()
    for ln in frame["lines"]:
        f = fold(ln["text"])
        if ln["conf"] >= 0.5 and len(f) >= 6 and re.search(r"[a-z]", f):
            out.add(f)
    return out


def episodes(seen: list[set[str]]) -> list[tuple[str, int, int]]:
    """(line, first index, last index) for every run, bridging one missing frame."""
    runs: dict[str, list[list[int]]] = {}
    for i, s in enumerate(seen):
        for ln in s:
            r = runs.setdefault(ln, [])
            if r and i - r[-1][1] <= 2:
                r[-1][1] = i
            else:
                r.append([i, i])
    return [(ln, a, b) for ln, rs in runs.items() for a, b in rs]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", type=Path)
    ap.add_argument("--show-misses", action="store_true")
    args = ap.parse_args()
    meta = json.loads((args.dir / "frames.json").read_text())
    dense = json.loads((args.dir / "ocr" / "vision_accurate-dense.json").read_text())
    names = sorted(dense)
    seen = [lines_of(dense[n]) for n in names]
    n = len(seen)
    times = [i * STEP for i in range(n)]
    eps = episodes(seen)
    freq: dict[str, int] = {}
    for s in seen:
        for ln in s:
            freq[ln] = freq.get(ln, 0) + 1
    persistent = {ln for ln, c in freq.items() if c > n / 2}

    def snap(t: float) -> int:
        return max(0, min(n - 1, round(t / STEP)))

    turns, edges = meta["turns"], meta["edges"]
    ppt = [t for t in turns if t["code"][:1] not in ("m", "o")]
    in_ppt = [e for e in edges if any(t["t0"] <= e < t["t1"] for t in ppt)]
    strategies: dict[str, list[float]] = {
        "turn": [t["t0"] + 0.25 * (t["t1"] - t["t0"]) for t in ppt],
        "proposed": [f["t"] for f in meta["frames"]],
        "all_changes": [t["t0"] + 0.25 * (t["t1"] - t["t0"]) for t in turns] + [e + 2 for e in edges],
    }
    budget = len(strategies["proposed"])
    for secs in (10, 20, 30):
        strategies[f"every_{secs}s"] = [k * secs + secs / 2 for k in range(int(times[-1] // secs) + 1)]
    for every in (1, 2, 3):  # OCR every 2, 4, 6 s
        kept, last = [], None
        for i in range(0, n, every):
            body = seen[i] - persistent
            if last is None or (len(body | last) and len(body & last) / len(body | last) < 0.6):
                kept.append(times[i])
                last = body
        strategies["text_diff" if every == 1 else f"text_diff_{every * STEP:g}s"] = kept
    pd = args.dir / "pixel_diff.json"
    if pd.exists():  # pixel_diff.py: edge-map change, no OCR in the loop
        for th, ts in json.loads(pd.read_text()).items():
            strategies[f"edge_diff_{th}"] = ts
    _ = in_ppt

    print(f"{args.dir.name}: {n} dense frames ({n * STEP / 60:.0f} min), {len(eps)} episodes, "
          f"{len(persistent)} persistent lines; proposed budget {budget} frames\n")
    buckets = [("2 s (one frame)", 0, 0), ("4–8 s", 1, 3), ("10–30 s", 4, 14), ("> 30 s", 15, 10 ** 9)]
    head = f"{'strategy':<13}{'frames':>7}{'/h':>6}" + "".join(f"{b[0]:>17}" for b in buckets) + f"{'all ≥4 s':>12}"
    print(head)
    for name, ts in strategies.items():
        idx = sorted({snap(t) for t in ts})
        cells, tot = [], [0, 0]
        for label, lo, hi in buckets:
            hit = cnt = 0
            for ln, a, b in eps:
                if ln in persistent or not (lo <= b - a <= hi):
                    continue
                cnt += 1
                if any(a - 1 <= i <= b + 1 and ln in seen[i] for i in idx):
                    hit += 1
                elif args.show_misses and name == "proposed" and b - a >= 2:
                    print(f"  MISS {times[a]:7.0f}s +{(b - a) * STEP:4.0f}s  {ln[:70]}")
            cells.append(f"{hit:>7}/{cnt:<5}{100 * hit / max(cnt, 1):>3.0f}%")
            if lo >= 1:
                tot[0] += hit
                tot[1] += cnt
        print(f"{name:<13}{len(idx):>7}{len(idx) / (n * STEP) * 3600:>6.0f}" + "".join(f"{c:>17}" for c in cells)
              + f"{100 * tot[0] / max(tot[1], 1):>11.0f}%")

    # Text changes with no colour change nearby: the white-popover-on-a-white-page case.
    tchg = strategies["text_diff"][1:]
    quiet = [t for t in tchg if not any(abs(t - e) <= 3 for e in edges)]
    print(f"\ntext changes (Jaccard < 0.6): {len(tchg)}; with no ΔE 8 colour edge within ±3 s: {len(quiet)} "
          f"({100 * len(quiet) / max(len(tchg), 1):.0f}%)")


if __name__ == "__main__":
    main()
