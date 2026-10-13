"""Which "sticky" rule removes screen chrome (names under tiles, bookmarks) without removing content?

    python3 experiments/screen-text/sticky_eval.py <private-root>

Uses the dense sweep (Vision accurate, one frame every 2 s, with boxes) and truth.json. A line is
judged over the session's text-dense frames (≥ 25 lines). Rules:

  line      the folded line occurs, as a whole line, on ≥ 50% of dense frames (what pipeline_spike.py did)
  text      the folded line occurs anywhere in the frame's text on ≥ 50% (survives line regrouping)
  place     some line on ≥ 50% of dense frames contains this text AND overlaps this line's box
            (IoU ≥ 0.3): chrome stays where it is, content moves with the page
  word      per WORD: a folded word at the same place (its x estimated from its character offset in
            the line's box, bucketed to 2% of the frame, ±1 bucket) on ≥ 50% of dense frames. Survives
            Vision regrouping a bookmark bar differently from frame to frame. A target is removed when
            every word of it is sticky in every line that carries it.

A truth target counts as **removed** when every line that carries it in its frame is sticky. Prints
personal targets removed and content targets lost per rule, aggregates only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from score import fold  # noqa: E402

DENSE = 25


def iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, bx1, by1 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw = max(0.0, min(ax1, bx1) - max(a[0], b[0]))
    ih = max(0.0, min(ay1, by1) - max(a[1], b[1]))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union else 0.0


def word_places(f: str, box: list[float]) -> list[tuple[str, int, int]]:
    out, i = [], 0
    for w in f.split():
        j = f.index(w, i)
        x = box[0] + box[2] * (j + len(w) / 2) / max(len(f), 1)
        out.append((w, round(x / 0.02), round((box[1] + box[3] / 2) / 0.02)))
        i = j + len(w)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    args = ap.parse_args()
    truth = json.loads((args.root / "truth.json").read_text())
    totals = {r: {"pii": [0, 0], "content": [0, 0]} for r in ("line", "text", "place", "word")}
    for d in ("p3", "teams"):
        dense = json.loads((args.root / d / "ocr" / "vision_accurate-dense.json").read_text())
        frames = [[(fold(ln["text"]), ln["box"]) for ln in dense[n]["lines"] if ln["conf"] >= 0.5]
                  for n in sorted(dense) if len(dense[n]["lines"]) >= DENSE]
        joined = [" " + " ".join(f for f, _ in fr) + " " for fr in frames]
        whole = [{f for f, _ in fr} for fr in frames]
        n = len(frames)
        wcount: dict[tuple[str, int, int], int] = {}
        for fr in frames:
            here = {wp for f, b in fr for wp in word_places(f, b)}
            for wp in here:
                wcount[wp] = wcount.get(wp, 0) + 1

        def word_sticky(wp: tuple[str, int, int]) -> bool:
            w, x, y = wp
            return max(wcount.get((w, x + dx, y + dy), 0) for dx in (-1, 0, 1) for dy in (-1, 0, 1)) / n >= 0.5

        def sticky(rule: str, f: str, box: list[float]) -> bool:
            if rule == "line":
                return sum(f in w for w in whole) / n >= 0.5
            if rule == "text":
                return sum((" " + f + " ") in j for j in joined) / n >= 0.5
            hits = 0
            for fr in frames:
                if any(f in g and iou(box, b) >= 0.3 for g, b in fr):
                    hits += 1
            return hits / n >= 0.5

        own = json.loads((args.root / d / "ocr" / "vision_accurate.json").read_text())
        for frame, spec in truth.items():
            if not frame.startswith(d + "/"):
                continue
            lines = [(fold(ln["text"]), ln["box"]) for ln in own[frame.split("/")[-1]]["lines"]]
            for kind, targets in spec["t"].items():
                for t in targets:
                    ft = fold(t)
                    carriers = [(f, b) for f, b in lines if ft in f]
                    if not carriers:
                        continue
                    key = "pii" if kind == "pii" else "content"
                    for rule in totals:
                        totals[rule][key][1] += 1
                        if rule == "word":
                            gone = all(all(word_sticky(wp) for wp in word_places(f, b) if wp[0] in ft.split())
                                       for f, b in carriers)
                        else:
                            gone = all(sticky(rule, f, b) for f, b in carriers)
                        totals[rule][key][0] += gone
    for rule, v in totals.items():
        print(f"{rule:<6} personal removed {v['pii'][0]}/{v['pii'][1]}   content lost {v['content'][0]}/{v['content'][1]}")


if __name__ == "__main__":
    main()
