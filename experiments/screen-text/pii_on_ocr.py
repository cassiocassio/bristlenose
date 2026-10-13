"""Does the shipped PII stage catch personal data in screen text, and what does it damage?

    .venv/bin/python experiments/screen-text/pii_on_ocr.py trial-runs/_screen-text [--engine vision_accurate]

Runs stage 7's own redactor (``s07_pii_removal._redact_text``, Presidio + en_core_web_lg, the shipped
thresholds) over each OCR line of the ground-truth frames, as a transcript segment would be, and over
each frame's lines joined (more context for the NER model). Then, using truth.json: a ``pii`` target
is **caught** when it no longer appears in the redacted text; any other target is **damaged** when it
appeared before redaction and does not after. Prints counts by entity type and aggregates only.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from score import fold  # noqa: E402

from bristlenose.config import BristlenoseSettings  # noqa: E402
from bristlenose.stages.s07_pii_removal import _init_presidio, _redact_text  # noqa: E402


def present(target: str, text: str) -> bool:
    return (" " + fold(target)) in (" " + fold(text) + " ")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--engine", default="vision_accurate")
    args = ap.parse_args()
    settings = BristlenoseSettings()
    analyzer, anonymizer = _init_presidio(settings)
    truth = json.loads((args.root / "truth.json").read_text())
    for mode in ("per line", "per frame"):
        kinds: Counter[str] = Counter()
        caught = [0, 0]
        damaged = [0, 0]
        for frame, spec in truth.items():
            sub, name = frame.split("/frames/") if "/frames/" in frame else ("", frame.split("/", 1)[1])
            path = args.root / sub / "ocr" / f"{args.engine}.json" if sub else args.root / "ocr" / f"{args.engine}-extra.json"
            lines = [ln["text"] for ln in json.loads(path.read_text())[name]["lines"]]
            before = " ".join(lines)
            if mode == "per line":
                out = []
                for ln in lines:
                    red, recs = _redact_text(ln, 0.0, analyzer, anonymizer, settings)
                    out.append(red)
                    kinds.update(r.entity_type for r in recs)
                after = " ".join(out)
            else:
                after, recs = _redact_text("\n".join(lines), 0.0, analyzer, anonymizer, settings)
                kinds.update(r.entity_type for r in recs)
            for kind, targets in spec["t"].items():
                for t in targets:
                    if not present(t, before):
                        continue
                    if kind == "pii":
                        caught[1] += 1
                        caught[0] += not present(t, after)
                    else:
                        damaged[1] += 1
                        damaged[0] += not present(t, after)
        print(f"{mode}: personal data caught {caught[0]}/{caught[1]}; other targets damaged "
              f"{damaged[0]}/{damaged[1]}; detections by type {dict(kinds)}")


if __name__ == "__main__":
    main()
