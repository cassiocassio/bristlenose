"""Run candidate OCR engines over a frame set and record text, boxes, confidence and time per frame.

    <ocr-venv>/bin/python experiments/screen-text/ocr_bench.py trial-runs/_screen-text/<tag> [--engines vision_accurate,rapidocr,...]

Needs a scratch venv, not the project's: ``pip install rapidocr onnxruntime pillow pyobjc-framework-Vision``,
and ``brew install tesseract`` for the tesseract engines. Nothing here is a Bristlenose dependency.

Engines:
  vision_accurate / vision_fast  Apple Vision VNRecognizeTextRequest (macOS only), language correction on
  rapidocr                       RapidOCR 3.x on onnxruntime, its default PP-OCR det + rec models
  tesseract / tesseract_sparse   Tesseract 5 LSTM, page segmentation 3 (auto) and 11 (sparse text)

Writes <dir>/ocr/<engine>.json: per frame, the lines (text, confidence, normalised box with a top-left
origin) and the seconds it took. The engine is warmed on the first frame before timing starts.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


def vision(level: int):
    import Vision
    from Foundation import NSURL

    def run(path: Path) -> list[dict]:
        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(NSURL.fileURLWithPath_(str(path)), None)
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(level)  # 0 accurate, 1 fast
        req.setUsesLanguageCorrection_(True)
        ok, err = handler.performRequests_error_([req], None)
        if not ok:
            raise RuntimeError(str(err))
        out = []
        for obs in req.results() or []:
            cand = obs.topCandidates_(1)[0]
            bb = obs.boundingBox()
            out.append({"text": str(cand.string()), "conf": round(float(cand.confidence()), 3),
                        "box": [round(bb.origin.x, 4), round(1 - bb.origin.y - bb.size.height, 4),
                                round(bb.size.width, 4), round(bb.size.height, 4)]})
        return out
    return run


def rapidocr():
    from PIL import Image
    from rapidocr import RapidOCR
    engine = RapidOCR()

    def run(path: Path) -> list[dict]:
        w, h = Image.open(path).size
        res = engine(str(path))
        out = []
        if res.txts is None:
            return out
        for txt, score, box in zip(res.txts, res.scores, res.boxes):
            xs, ys = [float(p[0]) for p in box], [float(p[1]) for p in box]
            out.append({"text": txt, "conf": round(float(score), 3),
                        "box": [round(min(xs) / w, 4), round(min(ys) / h, 4),
                                round((max(xs) - min(xs)) / w, 4), round((max(ys) - min(ys)) / h, 4)]})
        return out
    return run


def tesseract(psm: int):
    def run(path: Path) -> list[dict]:
        tsv = subprocess.run(["tesseract", str(path), "-", "--psm", str(psm), "tsv"],
                             capture_output=True, text=True, check=True).stdout.splitlines()
        head = tsv[0].split("\t")
        rows = [dict(zip(head, r.split("\t"))) for r in tsv[1:]]
        W = H = None
        lines: dict[tuple, dict] = {}
        for r in rows:
            if r["level"] == "1":
                W, H = int(r["width"]), int(r["height"])
            if r["level"] != "5" or not r.get("text", "").strip():
                continue
            key = (r["block_num"], r["par_num"], r["line_num"])
            x, y, w, h = (int(r[k]) for k in ("left", "top", "width", "height"))
            ln = lines.setdefault(key, {"words": [], "confs": [], "x0": x, "y0": y, "x1": x + w, "y1": y + h})
            ln["words"].append(r["text"])
            ln["confs"].append(float(r["conf"]))
            ln["x0"], ln["y0"] = min(ln["x0"], x), min(ln["y0"], y)
            ln["x1"], ln["y1"] = max(ln["x1"], x + w), max(ln["y1"], y + h)
        return [{"text": " ".join(ln["words"]), "conf": round(sum(ln["confs"]) / len(ln["confs"]) / 100, 3),
                 "box": [round(ln["x0"] / W, 4), round(ln["y0"] / H, 4),
                         round((ln["x1"] - ln["x0"]) / W, 4), round((ln["y1"] - ln["y0"]) / H, 4)]}
                for ln in lines.values()]
    return run


ENGINES = {
    "vision_accurate": lambda: vision(0),
    "vision_fast": lambda: vision(1),
    "rapidocr": rapidocr,
    "tesseract": lambda: tesseract(3),
    "tesseract_sparse": lambda: tesseract(11),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", type=Path)
    ap.add_argument("--engines", default=",".join(ENGINES))
    ap.add_argument("--frames-dir", default="frames")
    args = ap.parse_args()
    frames = sorted((args.dir / args.frames_dir).glob("*.png")) + sorted((args.dir / args.frames_dir).glob("*.jpg"))
    (args.dir / "ocr").mkdir(exist_ok=True)
    for name in args.engines.split(","):
        run = ENGINES[name]()
        run(frames[0])  # warm: model load, first-call compilation
        res = {}
        for f in frames:
            t = time.perf_counter()
            lines = run(f)
            res[f.name] = {"s": round(time.perf_counter() - t, 3), "lines": lines}
        out = args.dir / "ocr" / f"{name}{'' if args.frames_dir == 'frames' else '-' + args.frames_dir}.json"
        out.write_text(json.dumps(res, ensure_ascii=False))
        secs = sorted(v["s"] for v in res.values())
        print(f"{name}: {len(frames)} frames, median {secs[len(secs) // 2]:.3f} s, "
              f"p90 {secs[int(len(secs) * 0.9)]:.3f} s, {sum(len(v['lines']) for v in res.values())} lines")


if __name__ == "__main__":
    main()
