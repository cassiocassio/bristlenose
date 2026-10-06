"""Colour lab: sample frames from every distinct recording under a folder, for tuning the
speaker-colour algorithm in colour-lab.html.

    .venv/bin/python experiments/session-tapestry/colour_lab.py <folder-of-projects> -o <private>/colour-lab.html

Where a recording has a Bristlenose transcript, frames are drawn from inside moderator turns and
inside participant turns, so each speaker's colour is computed from moments they were speaking.
Otherwise frames are random. Each frame is area-scaled to 32×18 and shipped as raw RGB; all the
colour maths runs in the page so the handles can retune it live. The page carries frames of
participants — write it somewhere private.
"""

from __future__ import annotations

import argparse
import base64
import json
import random
import re
import subprocess
from pathlib import Path

from build import read_transcript

HERE = Path(__file__).parent
EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
SKIP = ("_acceptance-tmp", "stress-test", "/clips/", "bristlenose-output", "_tapestry")
FW, FH = 32, 18


def duration(video: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                         capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


def frame(video: Path, t: float) -> bytes | None:
    raw = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video),
                          "-frames:v", "1", "-vf", f"scale={FW}:{FH}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True).stdout
    return raw if len(raw) == FW * FH * 3 else None


def transcript_index(root: Path) -> dict[Path, list[dict]]:
    """Resolved video path → turns, from every transcripts-raw/*.txt under root."""
    idx: dict[Path, list[dict]] = {}
    for txt in root.rglob("transcripts-raw/s*.txt"):
        if any(s in str(txt) for s in ("stress-test", ".prev", "pre-phase")):
            continue
        _, source, _, turns = read_transcript(txt)
        if source and turns:
            out_dir = txt.parent.parent
            vid = (out_dir.parent / source).resolve()
            if vid.exists():
                idx.setdefault(vid, turns)
    return idx


def pick_times(rng: random.Random, turns: list[dict], role: str, n: int) -> list[float]:
    pool = [t for t in turns if (t["code"][0] in "mo") == (role == "moderator") and t["t1"] - t["t0"] > 3]
    if not pool:
        return []
    weights = [t["t1"] - t["t0"] for t in pool]
    out = []
    for t in rng.choices(pool, weights=weights, k=n):
        out.append(rng.uniform(t["t0"] + 1, t["t1"] - 1))
    return sorted(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--per-role", type=int, default=5)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    idx = transcript_index(args.root)
    seen: dict[int, Path] = {}
    for v in sorted(args.root.rglob("*")):
        if v.suffix.lower() not in EXT or not v.is_file() or any(s in str(v) for s in SKIP):
            continue
        size = v.stat().st_size
        if size < 3_000_000:
            continue
        # Prefer the copy that has a transcript.
        if size not in seen or (v.resolve() in idx and seen[size].resolve() not in idx):
            seen[size] = v

    videos = []
    for size, v in sorted(seen.items(), key=lambda kv: str(kv[1])):
        dur = duration(v)
        if dur < 5:
            continue
        turns = idx.get(v.resolve())
        frames = []
        if turns:
            for role in ("moderator", "participant"):
                for t in pick_times(rng, turns, role, args.per_role):
                    if (px := frame(v, t)):
                        frames.append({"t": round(t, 1), "role": role, "px": base64.b64encode(px).decode()})
        if not frames:
            for t in sorted(rng.uniform(dur * 0.05, dur * 0.95) for _ in range(args.per_role * 2)):
                if (px := frame(v, t)):
                    frames.append({"t": round(t, 1), "role": "unknown", "px": base64.b64encode(px).decode()})
        rel = str(v.relative_to(args.root))
        videos.append({"name": re.sub(r"\s+", " ", rel), "duration": round(dur), "has_turns": bool(turns), "frames": frames})
        print(f"{len(frames):3} frames  {'turns' if turns else '     '}  {rel}")

    blob = (json.dumps({"w": FW, "h": FH, "videos": videos}, ensure_ascii=True)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
    args.out.write_text((HERE / "colour-lab.html").read_text().replace("/*__DATA__*/null", blob))
    print(f"{args.out}  ·  {len(videos)} videos")


if __name__ == "__main__":
    main()
