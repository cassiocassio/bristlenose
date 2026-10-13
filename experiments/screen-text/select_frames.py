"""Pick the frames a screen-text index would read, extract them at full resolution, and measure storage.

    .venv/bin/python experiments/screen-text/select_frames.py <transcript.txt> <video> -o trial-runs/_screen-text/<tag>

The frame set is the thumbnail mockup's likely next step (experiments/session-tapestry/thumb_mockup.py):
one frame per participant turn, 25% in, plus one frame 2 s after each scene change (ΔE 8 on the scene
strip's 4 fps means) that falls inside a participant turn, capped at half the scene. Frames within 1 s of
one already taken are dropped. Each frame is written as a lossless PNG at the recording's resolution
(the OCR input) and re-encoded to measure the alternatives: JPEG q2/q5, HEIC (sips), a 1280 px JPEG, and the 320 px
thumbnail derived from the big frame. Writes frames.json (times, reasons) and sizes.json.

The output carries participants' screens: write it under trial-runs/ (gitignored), never into the tree.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "session-tapestry"))

from build import read_transcript  # noqa: E402

from bristlenose.utils.fs import is_dataless  # noqa: E402
from bristlenose.utils.scene_strip import sample_dense, scene_edges  # noqa: E402

FRAME_AT = 0.25
SCENE_DE = 8.0
SCENE_IN = 2.0
MIN_GAP = 1.0


def pick(turns: list[dict], edges: list[float], end: float) -> list[dict]:
    ppt = [t for t in turns if t["code"][:1] not in ("m", "o")]
    out = [{"t": t["t0"] + FRAME_AT * (t["t1"] - t["t0"]), "why": "turn"} for t in ppt]
    bounds = edges + [end]
    for j, e in enumerate(edges):
        if not any(t["t0"] <= e < t["t1"] for t in ppt):
            continue
        out.append({"t": e + min(SCENE_IN, (bounds[j + 1] - e) / 2), "why": "change"})
    out.sort(key=lambda f: f["t"])
    kept: list[dict] = []
    for f in out:
        if kept and f["t"] - kept[-1]["t"] < MIN_GAP:
            continue
        kept.append({"t": round(f["t"], 2), "why": f["why"]})
    return kept


def grab(video: Path, t: float, dest: Path) -> float:
    t0 = time.perf_counter()
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video),
                    "-frames:v", "1", str(dest)], check=True)
    return time.perf_counter() - t0


def size_of(cmd: list[str], dest: Path) -> int:
    subprocess.run(cmd, check=True, capture_output=True)
    n = dest.stat().st_size
    dest.unlink()
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript", type=Path)
    ap.add_argument("video", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--sizes", type=int, default=40, help="frames to re-encode for the size table")
    args = ap.parse_args()
    if is_dataless(args.video):
        sys.exit(f"{args.video} is an iCloud placeholder; not fetching it")

    dur, _, _, turns = read_transcript(args.transcript)
    t_dense = time.perf_counter()
    t0, means = sample_dense(args.video)
    t_dense = time.perf_counter() - t_dense
    edges_all = [t0 + e for e in scene_edges(means, 4, SCENE_DE)]
    frames = pick(turns, edges_all, t0 + len(means) / 4)

    fdir = args.out / "frames"
    fdir.mkdir(parents=True, exist_ok=True)
    seek = []
    for f in frames:
        f["png"] = f"{f['t']:08.2f}.png"
        if not (fdir / f["png"]).exists():
            seek.append(grab(args.video, f["t"], fdir / f["png"]))
    (args.out / "frames.json").write_text(json.dumps({
        "video": str(args.video), "duration": dur, "turns": turns, "edges": edges_all,
        "frames": frames}, indent=1))

    # Storage per format, on an even sample of the frames.
    step = max(1, len(frames) // args.sizes)
    sample = frames[::step][: args.sizes]
    tmp = args.out / "_tmp"
    tmp.mkdir(exist_ok=True)
    rows: dict[str, list[int]] = {k: [] for k in ("png", "jpeg_q2", "jpeg_q5", "heic", "jpeg1280_q4", "thumb320_jpeg")}
    for f in sample:
        src = fdir / f["png"]
        rows["png"].append(src.stat().st_size)
        rows["jpeg_q2"].append(size_of(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-q:v", "2", str(tmp / "a.jpg")], tmp / "a.jpg"))
        rows["jpeg_q5"].append(size_of(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-q:v", "5", str(tmp / "a.jpg")], tmp / "a.jpg"))
        rows["heic"].append(size_of(["sips", "-s", "format", "heic", "-s", "formatOptions", "70", str(src), "--out", str(tmp / "a.heic")], tmp / "a.heic"))
        rows["jpeg1280_q4"].append(size_of(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-vf", "scale=1280:-2", "-q:v", "4", str(tmp / "a.jpg")], tmp / "a.jpg"))
        rows["thumb320_jpeg"].append(size_of(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-vf", "scale=320:-2", "-q:v", "6", str(tmp / "a.jpg")], tmp / "a.jpg"))
    tmp.rmdir()
    sizes = {k: {"median_kb": round(statistics.median(v) / 1024, 1), "mean_kb": round(statistics.mean(v) / 1024, 1)}
             for k, v in rows.items() if v}
    summary = {
        "duration_s": dur, "participant_turns": sum(1 for t in turns if t["code"][:1] not in ("m", "o")),
        "edges_de8": len(edges_all), "frames": len(frames),
        "frames_turn": sum(1 for f in frames if f["why"] == "turn"),
        "frames_change": sum(1 for f in frames if f["why"] == "change"),
        "frames_per_hour": round(len(frames) / dur * 3600, 1),
        "dense_sample_s": round(t_dense, 1),
        "seek_png_s_median": round(statistics.median(seek), 3) if seek else None,
        "sizes": sizes, "size_sample": len(sample),
    }
    (args.out / "sizes.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
