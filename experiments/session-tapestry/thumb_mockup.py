"""Hover-thumbnail mockup: the Sessions grid's timeline with a preview frame per participant turn.

    .venv/bin/python experiments/session-tapestry/thumb_mockup.py <output-dir> [<output-dir> …] -o <private>/thumb-mockup.html

Builds on build.py (the session data, the shipped theme, the real row markup) and adds, per session:
the shipped scene strip (utils/scene_strip.py) and one frame per participant turn, taken 25% into the
turn and encoded as a JPEG data URL. Only sessions with video and at least --min-turns participant
turns are kept, so the stepping can be felt. The page shows participants' screens — write it somewhere
private (``trial-runs/_tapestry/`` is gitignored).
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
from pathlib import Path

from build import build, read_transcript

from bristlenose.stages.s12_render.theme_assets import load_default_css
from bristlenose.utils.fs import is_dataless
from bristlenose.utils.scene_strip import sample_dense, scene_edges, strip_record

HERE = Path(__file__).parent
FRAME_AT = 0.25  # how far into a participant turn its frame is taken
# Frames at colour changes inside a participant turn (13 Oct 2026). Measured on the two mockup sessions:
# scenes at ΔE 8 are colour-stable inside (the notches' ΔE 14 are not); a frame at the change itself is
# mid-transition in 13–22% of cases, 1–2 s in in 0–6%. So: changes at ΔE 8, frame 2 s in, or halfway
# through a stretch shorter than 4 s. A turn with no change inside it is one stretch, framed as before.
CHANGE_DE = 8.0
CHANGE_IN = 2.0
EDGE_MARGIN = 2.0  # a change within this of the turn's start belongs to the handover, not the turn


def frame(video: Path, t: float, width: int) -> str | None:
    jpg = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
         "-vf", f"scale={width}:-2", "-q:v", "6", "-f", "mjpeg", "-"],
        capture_output=True,
    ).stdout
    return "data:image/jpeg;base64," + base64.b64encode(jpg).decode() if jpg else None


def aspect(video: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout.strip()
    w, h = (int(v) for v in out.split(",")[:2])
    return h / w


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("output_dirs", type=Path, nargs="+")
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--min-turns", type=int, default=5)
    ap.add_argument("--frame-width", type=int, default=480, help="asset width; 2× the 240 px largest option")
    args = ap.parse_args()

    sessions = []
    for k, out_dir in enumerate(args.output_dirs):
        data = build(out_dir)
        for s in data["sessions"]:
            _, source, _, _ = read_transcript(out_dir / "transcripts-raw" / f"{s['id']}.txt")
            video = (out_dir.parent / source) if source else None
            ppt = [t for t in s["turns"] if t["code"][:1] not in ("m", "o")]
            if not video or not video.exists() or is_dataless(video) or len(ppt) < args.min_turns:
                continue
            t0, means = sample_dense(video)
            rec = strip_record(means, t0=t0)
            s["strip"] = {"fps": rec["fps"], "n": rec["n"], "t0": rec["t0"],
                          "png": "data:image/png;base64," + rec["png"]}
            s["aspect"] = aspect(video)
            edges = scene_edges(means, rec["fps"], CHANGE_DE)
            for t in ppt:
                ft = t["t0"] + FRAME_AT * (t["t1"] - t["t0"])
                src = frame(video, ft, args.frame_width)
                if src:
                    t["frame"] = {"t": round(ft, 1), "src": src}
                # Stretches inside the turn, split at its colour changes.
                cuts = [e for e in edges if t["t0"] + EDGE_MARGIN < e < t["t1"]]
                bounds = [t["t0"]] + cuts + [t["t1"]]
                frames = []
                for j, (a, b) in enumerate(zip(bounds, bounds[1:])):
                    at = a + FRAME_AT * (b - a) if j == 0 else a + min(CHANGE_IN, (b - a) / 2)
                    fsrc = src if j == 0 and not cuts else frame(video, at, args.frame_width)
                    if fsrc:
                        frames.append({"t": round(at, 1), "a": round(a, 2), "b": round(b, 2), "change": j > 0, "src": fsrc})
                t["frames"] = frames
            if s.get("thumb"):
                small = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", s["thumb"], "-vf", "scale=192:-2",
                                        "-q:v", "6", "-f", "mjpeg", "-"], capture_output=True).stdout
                s["thumb"] = "data:image/jpeg;base64," + base64.b64encode(small).decode() if small else None
            s["id"] = f"p{k}{s['id']}"  # distinct across projects
            s["number"] = len(sessions) + 1
            sessions.append(s)
            n_frames = sum(len(t.get("frames", [])) for t in ppt)
            print(f"{out_dir.parent.name} {s['id']}: {len(ppt)} participant turns, {n_frames} frames with changes inside turns, {rec['n']} strip samples")

    theme = re.sub(r"\s+", " ", re.sub(r"/\*.*?\*/", "", load_default_css(), flags=re.S))
    blob = (json.dumps({"sessions": sessions}, ensure_ascii=True)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
    html = (HERE / "thumb-mockup.html").read_text().replace("/*__THEME__*/", theme).replace("/*__DATA__*/null", blob)
    args.out.write_text(html)
    print(f"{args.out}  ·  {len(sessions)} sessions  ·  {args.out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
