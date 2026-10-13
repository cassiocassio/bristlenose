"""A cheap text-change detector: compare edge maps of small greyscale frames, no OCR needed to decide when to OCR.

    <ocr-venv>/bin/python experiments/screen-text/pixel_diff.py trial-runs/_screen-text/<tag> [--width 480] [--thresholds 0.2,0.3,...]

For each dense frame (one every 2 s), downscale to --width, take the gradient magnitude, mark edge pixels
(magnitude above a fixed level) and compare with the last KEPT frame: the share of edge pixels that
differ, over the union of edge pixels. Text is mostly edges, so a white popover on a white page, which
moves the mean colour very little, moves this a lot. A frame is kept when the share exceeds the
threshold. Writes pixel_diff.json ({threshold: [kept times]}) for coverage.py, and the decode-side cost.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

STEP = 2.0
EDGE = 24.0


def edges(path: Path, width: int) -> np.ndarray:
    im = Image.open(path).convert("L")
    im = im.resize((width, round(width * im.height / im.width)), Image.BILINEAR)
    a = np.asarray(im, dtype=np.float32)
    gx = np.abs(np.diff(a, axis=1))[:-1, :]
    gy = np.abs(np.diff(a, axis=0))[:, :-1]
    return (gx + gy) > EDGE


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", type=Path)
    ap.add_argument("--width", type=int, default=480)
    ap.add_argument("--thresholds", default="0.15,0.2,0.3,0.4,0.5")
    args = ap.parse_args()
    files = sorted((args.dir / "dense").glob("*.jpg"))
    t = time.perf_counter()
    maps = [edges(f, args.width) for f in files]
    per = (time.perf_counter() - t) / len(files)
    out = {}
    for th in (float(x) for x in args.thresholds.split(",")):
        kept, last = [], None
        for i, m in enumerate(maps):
            if last is None:
                kept.append(i * STEP)
                last = m
                continue
            union = np.count_nonzero(m | last)
            if union and np.count_nonzero(m ^ last) / union > th:
                kept.append(i * STEP)
                last = m
        out[f"{th:g}"] = kept
        print(f"threshold {th:g}: {len(kept)} frames ({len(kept) / (len(files) * STEP) * 3600:.0f}/h)")
    (args.dir / "pixel_diff.json").write_text(json.dumps(out))
    print(f"{per * 1000:.1f} ms per frame (JPEG decode + resize + edges, {args.width} px)")


if __name__ == "__main__":
    main()
