"""Build a session-tapestry page from a real Bristlenose output folder.

    .venv/bin/python experiments/session-tapestry/build.py <output-dir> [-o page.html]

Reads the pipeline's own intermediates (topic boundaries, extracted quotes, theme groups),
the raw transcripts (speaker turns) and people.yaml, samples one mean colour per video
keyframe with ffmpeg, and writes a self-contained HTML page. The page carries participant
content, so write it somewhere private (the default is beside this script's scratch use:
pass -o). Exploratory: design reference is docs/mockups/session-tapestry-scale.html.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

import yaml

from bristlenose.stages.s12_render.theme_assets import load_default_css
from bristlenose.utils.markdown import format_finder_date, format_finder_filename
from bristlenose.utils.timecodes import format_duration_human

HERE = Path(__file__).parent
TC = re.compile(r"^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s*\[([^\]]+)\]")
HEAD = re.compile(r"^# (Duration|Source|Date): (.+)$")


def _secs(a: str, b: str, c: str | None) -> int:
    return int(a) * 3600 + int(b) * 60 + int(c) if c else int(a) * 60 + int(b)


def read_transcript(path: Path) -> tuple[float, str | None, str | None, list[dict]]:
    """Return (duration, source file, date, turns). A turn merges consecutive same-speaker segments."""
    dur, source, date, segs = 0.0, None, None, []
    for line in path.read_text(errors="replace").splitlines():
        if m := HEAD.match(line):
            if m.group(1) == "Duration":
                dur = _secs(*re.match(r"(\d+):(\d{2})(?::(\d{2}))?", m.group(2)).groups())
            elif m.group(1) == "Date":
                date = m.group(2).strip()
            else:
                source = m.group(2).strip()
        elif m := TC.match(line):
            segs.append((_secs(*m.groups()[:3]), m.group(4)))
    turns: list[dict] = []
    for t, code in segs:
        if turns and turns[-1]["code"] == code:
            continue
        if turns:
            turns[-1]["t1"] = t
        turns.append({"t0": t, "t1": dur, "code": code})
    return float(dur), source, date, turns


def keyframe_colours(video: Path) -> list[list[float]]:
    """[[t, r, g, b], ...] — mean colour of each keyframe (area-scaled to 1×1)."""
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "info", "-skip_frame", "nokey",
         "-i", str(video), "-an", "-vf", "scale=1:1:flags=area,showinfo",
         "-fps_mode", "vfr", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=False,
    )
    times = [float(x) for x in re.findall(rb"pts_time:([\d.]+)", proc.stderr)]
    px = proc.stdout
    return [[round(t, 1), px[i * 3], px[i * 3 + 1], px[i * 3 + 2]]
            for i, t in enumerate(times) if i * 3 + 2 < len(px)]


def turn_colour(frames: list[list[float]], t0: float, t1: float) -> list[int] | None:
    """Mean keyframe colour inside [t0, t1); the nearest keyframe when none falls inside."""
    if not frames:
        return None
    inside = [f for f in frames if t0 <= f[0] < t1] or [min(frames, key=lambda f: abs(f[0] - t0))]
    return [round(sum(f[i] for f in inside) / len(inside)) for i in (1, 2, 3)]


def build(out_dir: Path) -> dict:
    inter = out_dir / ".bristlenose" / "intermediate"
    boundaries = json.loads((inter / "topic_boundaries.json").read_text())
    quotes = json.loads((inter / "extracted_quotes.json").read_text())
    themes = json.loads((inter / "theme_groups.json").read_text())
    clusters = sorted(json.loads((inter / "screen_clusters.json").read_text()), key=lambda c: c.get("display_order", 0))
    people = (yaml.safe_load((out_dir / "people.yaml").read_text()) or {}).get("participants", {})

    def name(code: str) -> str:
        ed = (people.get(code) or {}).get("editable", {})
        return ed.get("short_name") or ed.get("full_name") or code

    # theme membership keyed by (session, start, first 60 chars of text)
    theme_of: dict[tuple, str] = {}
    for th in themes:
        for q in th["quotes"]:
            theme_of[(q["session_id"], q["start_timecode"], q["text"][:60])] = th["theme_label"]

    # Sections (screen clusters) — the report's other grouping. Quote exclusivity: a quote is in one
    # section or one theme, never both.
    section_of: dict[tuple, str] = {}
    for c in clusters:
        for q in c["quotes"]:
            section_of[(q["session_id"], q["start_timecode"], q["text"][:60])] = c["screen_label"]
    order = {c["screen_label"]: i for i, c in enumerate(clusters)}

    sessions = []
    paths = sorted((out_dir / "transcripts-raw").glob("s*.txt"), key=lambda p: int(p.stem[1:]))
    for path in paths:
        sid = path.stem
        dur, source, date, turns = read_transcript(path)
        if not turns:
            continue
        video = (out_dir.parent / source) if source else None
        frames = keyframe_colours(video) if video and video.exists() else []
        topics = [{"t0": b["timecode_seconds"], "label": b["topic_label"]}
                  for e in boundaries if e["session_id"] == sid for b in e["boundaries"]]
        # The panel shows four lines and the click opens the transcript, so 600 characters is plenty.
        sq = [{"t0": q["start_timecode"], "t1": q["end_timecode"], "text": q["text"][:600],
               "sentiment": q.get("sentiment"), "intensity": q.get("intensity") or 1,
               "theme": theme_of.get((sid, q["start_timecode"], q["text"][:60])),
               "section": section_of.get((sid, q["start_timecode"], q["text"][:60])),
               "topic": q.get("topic_label")}
              for q in quotes if q["session_id"] == sid]
        codes = sorted({t["code"] for t in turns}, key=lambda c: (c[0] != "m", c))
        # Section flags: each section's first quote in this session — the anchor the row's User
        # journey chain links to (server/journey.py), so flags and chain agree.
        firsts: dict[str, float] = {}
        for q in sq:
            if q["section"] and (q["section"] not in firsts or q["t0"] < firsts[q["section"]]):
                firsts[q["section"]] = q["t0"]
        journey = sorted(firsts, key=lambda lab: order.get(lab, 99))
        thumb = out_dir / "assets" / "thumbnails" / f"{sid}.jpg"
        when = None
        if date:
            try:
                when = format_finder_date(datetime.fromisoformat(date))
            except ValueError:
                when = date
        sessions.append({
            "id": sid, "number": int(sid[1:]), "duration": dur, "duration_human": format_duration_human(dur),
            "date": when, "file": format_finder_filename(Path(source).name) if source else None,
            "thumb": str(thumb) if thumb.exists() else None,   # copied beside the page in main()
            "journey": journey, "sections": sorted(({"t0": t, "label": lab} for lab, t in firsts.items()), key=lambda x: x["t0"]),
            "turns": [dict(t, rgb=turn_colour(frames, t["t0"], t["t1"])) for t in turns],
            "topics": sorted(topics, key=lambda t: t["t0"]), "quotes": sorted(sq, key=lambda q: q["t0"]),
            "speakers": [{"code": c, "name": name(c)} for c in codes],
        })
    project = (json.loads((inter / "metadata.json").read_text()) or {}).get("project_name", out_dir.parent.name)
    return {"project": project, "sessions": sessions}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("output_dir", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    args = ap.parse_args()
    data = build(args.output_dir)
    # Self-contained: the shipped theme inlined with comments and whitespace stripped (423 → ~215 KB),
    # thumbnails as data URIs. Opens from file:// in any browser and in the app's preview pane.
    import base64
    for sess in data["sessions"]:
        if sess["thumb"]:
            # Down to the 96×54 the grid shows (×2 for Retina) before inlining.
            small = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", sess["thumb"], "-vf", "scale=192:-2",
                                    "-q:v", "6", "-f", "mjpeg", "-"], capture_output=True, check=True).stdout
            sess["thumb"] = "data:image/jpeg;base64," + base64.b64encode(small).decode()
    theme = re.sub(r"\s+", " ", re.sub(r"/\*.*?\*/", "", load_default_css(), flags=re.S))
    # Escape for embedding in <script>: ensure_ascii alone does not cover < > & (see root CLAUDE.md).
    blob = (json.dumps(data, ensure_ascii=True)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
    html = (HERE / "template.html").read_text().replace("/*__THEME__*/", theme).replace("/*__DATA__*/null", blob)
    args.out.write_text(html)
    n = len(data["sessions"])
    print(f"{args.out}  ·  {n} sessions  ·  {sum(len(s['quotes']) for s in data['sessions'])} quotes")


if __name__ == "__main__":
    main()
