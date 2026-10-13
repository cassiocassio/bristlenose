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
from bristlenose.utils.scene_strip import _de, sample_dense, scene_edges, strip_record

HERE = Path(__file__).parent
FRAME_AT = 0.25  # how far into a participant turn its frame is taken
# Per-scene frames, measured 13 Oct 2026 on the two mockup sessions: at the notch threshold (ΔE 14)
# scenes are not colour-stable inside (p90 spread 8.5), at ΔE 8 they are (≤ 0.4); a frame at the
# change itself is mid-transition in 13–22% of scenes, 1–2 s in in 0–6%, 5 s in worse again because
# some scenes last 6 s. So: scenes at ΔE 8, frame 2 s in, capped at half the scene.
SCENE_DE = 8.0
SCENE_IN = 2.0
MIN_SCENE = 2.0  # a flicker shorter than this gets no frame of its own


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
            for t in ppt:
                ft = t["t0"] + FRAME_AT * (t["t1"] - t["t0"])
                src = frame(video, ft, args.frame_width)
                if src:
                    t["frame"] = {"t": round(ft, 1), "src": src}
            # Scenes: each change carries the strength of its change (the before/after window ΔE), so the
            # page can show the scenes a coarser threshold would keep. Frames at the change and 2 s in.
            fps = rec["fps"]
            edges = scene_edges(means, fps, SCENE_DE)
            w = round(2.0 * fps)
            def strength(e: float) -> float:
                i = round((e - t0) * fps)
                a, b = means[max(0, i - w):i], means[i:i + w]
                if not a or not b:
                    return 0.0
                m = lambda xs: tuple(sum(x[c] for x in xs) / len(xs) for c in range(3))
                return round(_de(m(a), m(b)), 1)
            end = t0 + rec["n"] / fps
            starts = [t0] + edges
            scenes = []
            for j, a in enumerate(starts):
                b = starts[j + 1] if j + 1 < len(starts) else end
                if b - a < MIN_SCENE:
                    continue
                at, inn = a, a + min(SCENE_IN, (b - a) / 2)
                f0, f2 = frame(video, at, args.frame_width), frame(video, inn, args.frame_width)
                if f0 and f2:
                    scenes.append({"t": round(a, 2), "d": None if j == 0 else strength(a),
                                   "f0": {"t": round(at, 1), "src": f0}, "f2": {"t": round(inn, 1), "src": f2}})
            s["scenes"] = scenes
            if s.get("thumb"):
                small = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", s["thumb"], "-vf", "scale=192:-2",
                                        "-q:v", "6", "-f", "mjpeg", "-"], capture_output=True).stdout
                s["thumb"] = "data:image/jpeg;base64," + base64.b64encode(small).decode() if small else None
            s["id"] = f"p{k}{s['id']}"  # distinct across projects
            s["number"] = len(sessions) + 1
            sessions.append(s)
            print(f"{out_dir.parent.name} {s['id']}: {len(ppt)} participant turns, {len(scenes)} scenes at ΔE {SCENE_DE:g}, {rec['n']} strip samples")

    theme = re.sub(r"\s+", " ", re.sub(r"/\*.*?\*/", "", load_default_css(), flags=re.S))
    blob = (json.dumps({"sessions": sessions}, ensure_ascii=True)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
    html = (HERE / "thumb-mockup.html").read_text().replace("/*__THEME__*/", theme).replace("/*__DATA__*/null", blob)
    args.out.write_text(html)
    print(f"{args.out}  ·  {len(sessions)} sessions  ·  {args.out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
