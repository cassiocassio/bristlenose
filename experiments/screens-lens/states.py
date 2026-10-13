"""Can a dialog, panel or drop-down over a page be told apart from scrolling? Score one rule.

    python3 experiments/screens-lens/states.py <private screen-text dir>/<tag> [...]

The visit-level signals in identity.py cannot separate states within a page (AUC 0.45–0.69). This tries
a change-based rule instead, comparing each visit's first frame with the previous visit's last frame:

- a line is **retained** when the same text sits at the same place (±1.2% of the frame both ways);
- if at least RETAIN of the previous frame's lines are retained, the page underneath stayed put, so
  this is not a scroll or a new page;
- then the lines that are new, if there are at least 2 and their bounding box covers at most
  MAX_AREA of the frame, are an **overlay**, and its name is the tallest new line in the top third of
  that box;
- an overlay continues into the next visit while the background stays retained and the new block
  keeps overlapping the overlay's box;
- otherwise the visit is the page's **base** state.

Scored against the hand state labels, within each hand page label: adjusted Rand index, and how often
"is an overlay" agrees with the label having a "+". Aggregates only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from identity import ari  # noqa: E402

RETAIN, MAX_AREA, TOL = 0.35, 0.45, 0.012


def retained(prev: list, cur: list) -> set[int]:
    keep = set()
    for k, (t, x, y, _h) in enumerate(cur):
        if any(t == pt and abs(x - px) < TOL and abs(y - py) < TOL for pt, px, py, _ in prev):
            keep.add(k)
    return keep


def main() -> None:
    for root in map(Path, sys.argv[1:]):
        vs = json.loads((root / "screens" / "visits.json").read_text())
        lab = json.loads((root / "screens" / "labels.json").read_text())
        page = [lab["page"][str(v["v"])] for v in vs]
        state = [lab["state"][str(v["v"])] for v in vs]
        pred, overlay_box = [], None
        for i, v in enumerate(vs):
            cur = v["first"]
            name = "base"
            if i and page[i] == page[i - 1] and vs[i - 1]["last"]:
                prev = vs[i - 1]["last"]
                keep = retained(prev, cur)
                if len(keep) / len(prev) >= RETAIN:
                    new = [c for k, c in enumerate(cur) if k not in keep]
                    if len(new) >= 2:
                        x0 = min(c[1] for c in new); y0 = min(c[2] for c in new)
                        x1 = max(c[1] for c in new) + 0.05; y1 = max(c[2] + c[3] for c in new)
                        area = (x1 - x0) * (y1 - y0) / 0.83
                        if area <= MAX_AREA:
                            top = [c for c in new if c[2] <= y0 + (y1 - y0) / 3]
                            title = max(top, key=lambda c: c[3])[0]
                            if overlay_box and pred[-1] != "base" and not (x1 < overlay_box[0] or x0 > overlay_box[2]):
                                name = pred[-1]
                            else:
                                name = "overlay:" + title
                            overlay_box = (x0, y0, x1, y1)
                    elif pred and pred[-1] != "base":
                        name = pred[-1]
            if name == "base":
                overlay_box = None
            pred.append(name)
        # ARI within pages: key states by page + predicted name
        keys = [f"{p}|{s}" for p, s in zip(page, pred)]
        is_ov_true = ["+" in s for s in state]
        is_ov_pred = [s != "base" for s in pred]
        agree = sum(a == b for a, b in zip(is_ov_true, is_ov_pred))
        tp = sum(a and b for a, b in zip(is_ov_true, is_ov_pred))
        print(f"== {root.name}: {len(vs)} visits; overlay visits by hand {sum(is_ov_true)}, by rule {sum(is_ov_pred)}, "
              f"both {tp}; agreement {agree / len(vs):.0%}; state ARI {ari(state, keys):.2f} "
              f"(page labels alone {ari(state, page):.2f}); distinct predicted states {len(set(keys))} vs {len(set(state))}")


if __name__ == "__main__":
    main()
