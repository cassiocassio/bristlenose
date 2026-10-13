"""Score OCR engines against hand-written targets: could a researcher find this frame by typing the words?

    python3 experiments/screen-text/score.py trial-runs/_screen-text [--show-misses ENGINE]

truth.json (private, beside the frames) maps a frame to target strings grouped by kind: head, body,
button, nav, small, dim (behind a modal's scrim), dark (dark mode), term (terminal), chrome (browser
chrome), pii (names, bookmarks, postcodes: what a researcher would NOT want indexed by accident).
Targets were chosen from what is legible on the frame at 100%, each within one visual line.

A target is **found** when its folded form occurs in the frame's folded OCR text starting at a word
start, which is the shipped search's rule (docs/design-search.md §3, searchMatch.ts): case, diacritics
and punctuation fold, whitespace collapses. **Token recall** is the share of the target's words present
anywhere in the frame's text, which shows near-misses (one misread letter) that a phrase search loses.
Prints aggregates only, so the output can go in a tracked README.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ENGINES = ["vision_accurate", "vision_fast", "rapidocr", "tesseract", "tesseract_sparse"]
_KEEP = "#@%&"


def fold(s: str) -> str:
    s = s.replace("ß", "ss").replace("’", "'").replace("‘", "'").replace("€", " € ").replace("£", " £ ")
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(c if c.isalnum() or c in _KEEP or c in "€£" else " " for c in s)
    return re.sub(r"\s+", " ", s).strip()


def load(root: Path, engine: str, frame: str) -> str | None:
    sub, name = frame.split("/frames/") if "/frames/" in frame else ("", frame.split("/", 1)[1])
    path = root / sub / "ocr" / f"{engine}.json" if sub else root / "ocr" / f"{engine}-extra.json"
    data = json.loads(path.read_text())
    if name not in data:
        return None
    return " ".join(line["text"] for line in data[name]["lines"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--show-misses", default=None, help="print this engine's missed targets (private: stdout only)")
    args = ap.parse_args()
    truth = json.loads((args.root / "truth.json").read_text())
    found: dict[str, dict[str, list[int]]] = {e: defaultdict(lambda: [0, 0]) for e in ENGINES}
    tokens: dict[str, list[float]] = {e: [0.0, 0] for e in ENGINES}
    by_frame: dict[str, dict[str, list[int]]] = {e: defaultdict(lambda: [0, 0]) for e in ENGINES}
    for frame, spec in truth.items():
        for e in ENGINES:
            text = load(args.root, e, frame)
            if text is None:
                continue
            hay = " " + fold(text) + " "
            words = set(hay.split())
            for kind, targets in spec["t"].items():
                for target in targets:
                    ft = fold(target)
                    hit = (" " + ft) in hay
                    found[e][kind][0] += hit
                    found[e][kind][1] += 1
                    by_frame[e][spec["kind"]][0] += hit
                    by_frame[e][spec["kind"]][1] += 1
                    toks = ft.split()
                    if kind != "pii":
                        tokens[e][0] += sum(t in words for t in toks) / len(toks)
                        tokens[e][1] += 1
                    if not hit and args.show_misses == e:
                        print(f"  MISS [{kind}] {frame}: {target!r}")
    kinds = sorted({k for spec in truth.values() for k in spec["t"]})
    ENG = [e for e in ENGINES if any(v[1] for v in found[e].values())]  # engines with results here
    print("Phrase found (from a word start, folded), by kind of text:\n")
    print(f"{'kind':<8}" + "".join(f"{e:>18}" for e in ENG))
    for k in kinds:
        n = found[ENG[0]][k][1]
        print(f"{k:<8}" + "".join(f"{found[e][k][0]:>9}/{n:<3} {100 * found[e][k][0] / n:>3.0f}%" for e in ENG))
    print(f"{'ALL−pii':<8}" + "".join(
        f"{sum(v[0] for k, v in found[e].items() if k != 'pii'):>9}/{sum(v[1] for k, v in found[e].items() if k != 'pii'):<3} "
        f"{100 * sum(v[0] for k, v in found[e].items() if k != 'pii') / sum(v[1] for k, v in found[e].items() if k != 'pii'):>3.0f}%"
        for e in ENG))
    print(f"{'tokens':<8}" + "".join(f"{'':>9}{100 * tokens[e][0] / tokens[e][1]:>8.0f}%" for e in ENG))
    print("\nPhrase found, by frame type (all kinds incl. pii):\n")
    for kind in by_frame[ENG[0]]:
        n = by_frame[ENG[0]][kind][1]
        print(f"{kind[:48]:<50}" + "".join(f"{100 * by_frame[e][kind][0] / n:>6.0f}%" for e in ENG) + f"  (n={n})")


if __name__ == "__main__":
    main()
