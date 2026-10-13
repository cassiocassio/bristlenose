"""Can RapidOCR be made cheap enough for the channels without Apple Vision?

    <ocr-venv>/bin/python experiments/screen-text/rapid_levers.py <private-root>

Runs RapidOCR variants at 2 threads (how a polite background job would run it) on the truth frames and
scores them with score.py's rule (folded phrase from a word start), non-personal targets only. Variants:
the default (PP-OCRv6 small, multilingual), PP-OCRv5 mobile det with the Latin-script mobile recogniser,
and detection input capped at 960 px on the long side (the default floors the SHORT side at 736, so a
1080p frame is never shrunk). Non-default models are fetched by RapidOCR at first use from
modelscope.cn; a product would pin and host them.
"""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

sys.path.insert(0, str(Path(__file__).parent))
from score import fold  # noqa: E402

THREADS = {"EngineConfig.onnxruntime.intra_op_num_threads": 2, "EngineConfig.onnxruntime.inter_op_num_threads": 1}
CAP = {"Det.limit_type": "max", "Det.limit_side_len": 960}
V5_LATIN = {"Det.ocr_version": OCRVersion.PPOCRV5, "Det.model_type": ModelType.MOBILE,
            "Rec.ocr_version": OCRVersion.PPOCRV5, "Rec.model_type": ModelType.MOBILE, "Rec.lang_type": LangRec.LATIN}
VARIANTS = {
    "v6 small (default)": {},
    "v6 small, det ≤960": CAP,
    "v5 mobile latin": V5_LATIN,
    "v5 mobile latin, det ≤960": {**V5_LATIN, **CAP},
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    args = ap.parse_args()
    truth = json.loads((args.root / "truth.json").read_text())
    for name, extra in VARIANTS.items():
        engine = RapidOCR(params={**THREADS, **extra})
        engine(str(args.root / next(iter(truth))))  # warm
        hit = n = 0
        secs = []
        cpu0 = resource.getrusage(resource.RUSAGE_SELF)
        for frame, spec in truth.items():
            t = time.perf_counter()
            res = engine(str(args.root / frame))
            secs.append(time.perf_counter() - t)
            hay = " " + fold(" ".join(res.txts or ())) + " "
            for kind, targets in spec["t"].items():
                if kind == "pii":
                    continue
                for target in targets:
                    n += 1
                    hit += (" " + fold(target)) in hay
        cpu1 = resource.getrusage(resource.RUSAGE_SELF)
        cpu = (cpu1.ru_utime - cpu0.ru_utime + cpu1.ru_stime - cpu0.ru_stime) / len(secs)
        secs.sort()
        print(f"{name:<28} found {hit}/{n} ({100 * hit / n:.0f}%)   median {secs[len(secs) // 2]:.2f} s/frame   "
              f"{cpu:.2f} CPU-s/frame")


if __name__ == "__main__":
    main()
