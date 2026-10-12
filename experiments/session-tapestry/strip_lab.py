"""Scene-strip lab: sample every distinct recording under a folder densely, for tuning the
scene stripes drawn inside the tapestry's speaker clips (strip-lab.html).

    .venv/bin/python experiments/session-tapestry/strip_lab.py <folder-of-projects> -o <private>/strip-lab.html

Per recording, two passes, both timed so the page shows the cost:
- keyframes only, exactly as the pipeline samples them today (``scene_colour.sample_keyframes``);
- every frame at 4 fps, which is one sample per pixel at the tapestry's maximum zoom (0.25 s/px).

Each sample is the mean OKLab of the frame's kept pixels (black bars cropped, near-black dropped,
as the pipeline does), quantised to three bytes. The per-turn colour is the shipped algorithm's
(most colourful eligible cluster of the keyframes inside the turn), with its raw cluster colour
alongside so the page can re-tone stripes and clips together. Turns come from the transcript
where there is one, otherwise a fixed moderator/participant alternation stands in.

The page carries the colour of every second of participants' screens, so write it somewhere
private (``trial-runs/_tapestry/`` is gitignored).
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import re
import subprocess
import time
from pathlib import Path

from build import read_transcript
from colour_lab import EXT, SKIP, duration, transcript_index

from bristlenose.utils.scene_colour import (
    FRAME_H,
    FRAME_W,
    MAX_PIXELS_PER_TURN,
    MIN_SHARE,
    Lab,
    frame_pixels,
    kmeans,
    oklab_to_hex,
    sample_keyframes,
    tone,
)

HERE = Path(__file__).parent
FPS = 4  # one sample per pixel at 0.25 s/px, the tapestry's maximum zoom
SIZE = FRAME_W * FRAME_H * 3


def dense_frames(video: Path, fps: int) -> list[Lab | None]:
    """Mean kept-pixel OKLab of every frame at *fps*; None for a frame with nothing kept (black)."""
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(video), "-an",
         "-vf", f"fps={fps},scale={FRAME_W}:{FRAME_H}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, timeout=3600,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[-300:])
    data = proc.stdout
    return [mean_lab(frame_pixels(data[i:i + SIZE])) for i in range(0, len(data) - SIZE + 1, SIZE)]


def mean_lab(points: list[Lab]) -> Lab | None:
    if not points:
        return None
    n = len(points)
    return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n, sum(p[2] for p in points) / n)


def q8(v: float, lo: float, hi: float) -> int:
    return max(0, min(255, round((v - lo) / (hi - lo) * 255)))


def pack(labs: list[Lab | None]) -> str:
    """Three bytes per sample: L over 0..1, a and b over -0.4..0.4. A black frame packs as (0,128,128)."""
    out = bytearray()
    for lab in labs:
        L, a, b = lab if lab else (0.0, 0.0, 0.0)
        out += bytes((q8(L, 0, 1), q8(a, -0.4, 0.4), q8(b, -0.4, 0.4)))
    return base64.b64encode(bytes(out)).decode()


def turn_colour(points: list[Lab]) -> tuple[str, Lab] | None:
    """The shipped pick (``scene_colour.pick_colour``) with its raw cluster colour: (hex toned, raw lab)."""
    if not points:
        return None
    if len(points) > MAX_PIXELS_PER_TURN:
        step = len(points) / MAX_PIXELS_PER_TURN
        points = [points[int(i * step)] for i in range(MAX_PIXELS_PER_TURN)]
    clusters = kmeans(points)
    eligible = [c for c in clusters if c[1] >= MIN_SHARE] or clusters[:1]
    lab, _ = max(eligible, key=lambda c: math.hypot(c[0][1], c[0][2]))
    return oklab_to_hex(tone(lab)), lab


def synthetic_turns(dur: float) -> list[dict]:
    """A stand-in alternation for a recording with no transcript: 15 s moderator, 45 s participant."""
    turns, t, i = [], 0.0, 0
    while t < dur:
        mod = i % 2 == 0
        length = 15.0 if mod else 45.0
        turns.append({"t0": t, "t1": min(dur, t + length), "code": "m1" if mod else "p1"})
        t += length
        i += 1
    return turns


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--only", help="substring of a path, to build a subset quickly")
    ap.add_argument("--fps", type=int, default=FPS)
    args = ap.parse_args()

    idx = transcript_index(args.root)
    seen: dict[int, Path] = {}
    for v in sorted(args.root.rglob("*")):
        if v.suffix.lower() not in EXT or not v.is_file() or any(s in str(v) for s in SKIP):
            continue
        if args.only and args.only not in str(v):
            continue
        size = v.stat().st_size
        if size < 3_000_000:
            continue
        if size not in seen or (v.resolve() in idx and seen[size].resolve() not in idx):
            seen[size] = v

    videos = []
    for _size, v in sorted(seen.items(), key=lambda kv: str(kv[1])):
        dur = duration(v)
        if dur < 5:
            continue
        rel = re.sub(r"\s+", " ", str(v.relative_to(args.root)))
        t0 = time.perf_counter()
        try:
            keyframes = sample_keyframes(v)
        except RuntimeError as exc:
            print(f"  skip (keyframes): {rel}: {exc}")
            continue
        kf_s = time.perf_counter() - t0
        t0 = time.perf_counter()
        try:
            dense = dense_frames(v, args.fps)
        except RuntimeError as exc:
            print(f"  skip (dense): {rel}: {exc}")
            continue
        dense_s = time.perf_counter() - t0

        raw_turns = idx.get(v.resolve())
        turns = [dict(t) for t in raw_turns] if raw_turns else synthetic_turns(dur)
        for t in turns:
            inside = [px for kt, px in keyframes if t["t0"] <= kt < t["t1"]]
            if not inside and keyframes:
                inside = [min(keyframes, key=lambda k: abs(k[0] - t["t0"]))[1]]
            picked = turn_colour([p for frame in inside for p in frame])
            t["colour"] = picked[0] if picked else None
            t["lab"] = [round(c, 4) for c in picked[1]] if picked else None

        gaps = sorted(b - a for a, b in zip([k[0] for k in keyframes], [k[0] for k in keyframes][1:]))
        videos.append({
            "name": rel, "duration": round(dur, 1), "has_turns": bool(raw_turns), "turns": turns,
            "kf_gap": round(gaps[len(gaps) // 2], 2) if gaps else None,
            "cost": {"keyframes_s": round(kf_s, 1), "dense_s": round(dense_s, 1)},
            "kf": {"t": [round(k[0], 2) for k in keyframes], "lab": pack([mean_lab(k[1]) for k in keyframes])},
            "dense": {"fps": args.fps, "n": len(dense), "lab": pack(dense)},
        })
        print(f"{len(keyframes):5} kf  gap {videos[-1]['kf_gap']!s:>5}s  {kf_s:5.1f}s   {len(dense):6} dense  {dense_s:5.1f}s"
              f"   {'turns' if raw_turns else '     '}  {rel}")

    blob = (json.dumps({"videos": videos}, ensure_ascii=True)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
    args.out.write_text((HERE / "strip-lab.html").read_text().replace("/*__DATA__*/null", blob))
    print(f"{args.out}  ·  {len(videos)} videos  ·  {args.out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
