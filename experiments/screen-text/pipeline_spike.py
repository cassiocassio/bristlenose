"""Spike of the build plan's step 1: one recording in, a screen-text index out, nothing written but the index.

    <ocr-venv>/bin/python experiments/screen-text/pipeline_spike.py <video> -o <private>/index.json [--every 4] [--no-pool]

One ffmpeg pass decodes a frame every --every seconds at full resolution to raw BGRA on a pipe, with
`showinfo` giving each frame's real time (the scene strip's rule: never assume the first frame is at 0).
Each frame goes to Apple Vision (accurate, language correction on) as a CGImage built from the bytes, so
no frame touches the disk. Lines are folded as search folds them; episodes are built per line (a line on
screen in consecutive samples, one missing sample bridged); lines present on at least half of the
text-dense samples are flagged sticky (chrome: names under tiles, bookmarks). The kept "moments" are the
samples whose line set differs from the last kept one by Jaccard < 0.6.

Reports wall time, CPU time, peak RSS, and RSS every 100 frames, so a leak shows as a climb. --no-pool
runs without an autorelease pool per frame, to measure whether one is needed in a long-lived loop.
"""

from __future__ import annotations

import argparse
import json
import re
import resource
import subprocess
import sys
import threading
import time
from pathlib import Path

import Foundation
import objc
import Quartz
import Vision

sys.path.insert(0, str(Path(__file__).parent))
from score import fold  # noqa: E402

JACCARD = 0.6
STICKY = 0.5
DENSE_LINES = 25


def probe(video: Path) -> tuple[int, int]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", str(video)], capture_output=True, text=True, check=True).stdout
    w, h = (int(v) for v in out.strip().split(",")[:2])
    return w, h


def ocr(buf: bytes, w: int, h: int) -> list[dict]:
    # A CFData copy, not CGDataProviderCreateWithData over the Python buffer: the latter leaked one
    # whole frame per call (measured, ~8 MB a 1080p frame, pool or no pool).
    provider = Quartz.CGDataProviderCreateWithCFData(Foundation.NSData.dataWithBytes_length_(buf, len(buf)))
    img = Quartz.CGImageCreate(w, h, 8, 32, w * 4, Quartz.CGColorSpaceCreateDeviceRGB(),
                               Quartz.kCGBitmapByteOrder32Little | Quartz.kCGImageAlphaPremultipliedFirst,
                               provider, None, False, Quartz.kCGRenderingIntentDefault)
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(0)
    req.setUsesLanguageCorrection_(True)
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise RuntimeError(str(err))
    out = []
    for obs in req.results() or []:
        c = obs.topCandidates_(1)[0]
        bb = obs.boundingBox()
        out.append({"text": str(c.string()), "conf": round(float(c.confidence()), 3),
                    "box": [round(bb.origin.x, 4), round(1 - bb.origin.y - bb.size.height, 4),
                            round(bb.size.width, 4), round(bb.size.height, 4)]})
    return out


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20  # bytes on macOS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--every", type=float, default=4.0)
    ap.add_argument("--no-pool", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many frames (0 = all)")
    args = ap.parse_args()
    w, h = probe(args.video)
    size = w * h * 4

    t_start = time.perf_counter()
    cpu0 = resource.getrusage(resource.RUSAGE_SELF)
    proc = subprocess.Popen(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "info", "-i", str(args.video), "-an",
                             "-vf", f"fps=1/{args.every},showinfo", "-f", "rawvideo", "-pix_fmt", "bgra", "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    times: list[float] = []

    def read_err() -> None:
        for line in proc.stderr:
            m = re.search(rb"pts_time:(-?[\d.]+(?:e-?\d+)?)", line)
            if m:
                times.append(float(m.group(1)))
    t_err = threading.Thread(target=read_err, daemon=True)
    t_err.start()

    samples: list[dict] = []
    ocr_s = 0.0
    rss_trace = []
    while True:
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        t0 = time.perf_counter()
        if args.no_pool:
            lines = ocr(buf, w, h)
        else:
            with objc.autorelease_pool():
                lines = ocr(buf, w, h)
        ocr_s += time.perf_counter() - t0
        samples.append({"lines": lines})
        if len(samples) % 100 == 0:
            rss_trace.append((len(samples), round(rss_mb())))
        if args.limit and len(samples) >= args.limit:
            proc.kill()
            break
    proc.wait()
    t_err.join(timeout=5)
    if len(times) < len(samples):
        sys.exit(f"refusing to pair {len(samples)} frames with {len(times)} times")
    for s, t in zip(samples, times):
        s["t"] = round(t, 2)

    # Episodes per folded line, with the text and box of its first sighting.
    seen = []
    for s in samples:
        keep = {}
        for ln in s["lines"]:
            f = fold(ln["text"])
            if ln["conf"] >= 0.5 and len(f) >= 2 and f not in keep:
                keep[f] = ln
        seen.append(keep)
    dense = [k for k in seen if len(k) >= DENSE_LINES]
    freq: dict[str, int] = {}
    for k in dense:
        for f in k:
            freq[f] = freq.get(f, 0) + 1
    sticky = {f for f, c in freq.items() if dense and c / len(dense) >= STICKY}
    episodes: dict[str, dict] = {}
    for i, k in enumerate(seen):
        t = samples[i]["t"]
        for f, ln in k.items():
            e = episodes.setdefault(f, {"text": ln["text"], "box": ln["box"], "sticky": f in sticky, "runs": []})
            if e["runs"] and t - e["runs"][-1][1] <= 2 * args.every + 0.01:
                e["runs"][-1][1] = t
            else:
                e["runs"].append([t, t])
    moments, last = [], None
    for i, k in enumerate(seen):
        body = set(k) - sticky
        if last is None or (body | last and len(body & last) / len(body | last) < JACCARD):
            moments.append(samples[i]["t"])
            last = body
    wall = time.perf_counter() - t_start
    cpu1 = resource.getrusage(resource.RUSAGE_SELF)
    cpu_self = (cpu1.ru_utime - cpu0.ru_utime) + (cpu1.ru_stime - cpu0.ru_stime)
    ch = resource.getrusage(resource.RUSAGE_CHILDREN)
    index = {"version": 0, "every": args.every, "size": [w, h], "moments": moments,
             "episodes": list(episodes.values())}
    blob = json.dumps(index, ensure_ascii=False)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(blob)
    dur = samples[-1]["t"] if samples else 0
    print(json.dumps({
        "video_min": round(dur / 60, 1), "frames": len(samples), "wall_s": round(wall, 1),
        "ocr_s": round(ocr_s, 1), "ocr_per_frame_s": round(ocr_s / max(len(samples), 1), 3),
        "cpu_python_s": round(cpu_self, 1), "cpu_ffmpeg_s": round(ch.ru_utime + ch.ru_stime, 1),
        "wall_per_video_hour_min": round(wall / max(dur, 1) * 60, 1),
        "peak_rss_mb": round(rss_mb()), "rss_trace": rss_trace,
        "episodes": len(episodes), "sticky_lines": len(sticky), "moments": len(moments),
        "index_kb": len(blob.encode()) // 1024, "pool": not args.no_pool}, indent=1))


if __name__ == "__main__":
    main()
