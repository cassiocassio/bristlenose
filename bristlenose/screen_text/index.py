"""One recording in, a screen-text index out.

One ffmpeg pass decodes a frame every ``EVERY`` seconds to raw BGRA on a pipe, with ``showinfo``
giving each frame's real time (never assume the first frame is at 0). Each frame goes to the engine.
Lines are folded as search folds them. An **episode** is one line at one place, with the runs of time
it was on screen (one missing sample bridged); a line that moves (the page scrolled) is a new
episode at its new place, so "what was on screen at t, and where" is the episodes whose runs cover t.
Lines on at least half of the text-dense samples are flagged **sticky** (chrome: names under call
tiles, bookmarks). **Moments** are the samples whose non-sticky lines differ from the last kept
moment by Jaccard < 0.6.

Measured (``experiments/screen-text/README.md``): about 2 minutes per hour of 1080p video with
Vision on an M2 Max, ~200 MB. Frames wider than ``MAX_WIDTH`` are scaled down first, which bounds
memory for 4K screen captures without costing legibility at 1920.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import threading
import unicodedata
from collections import deque
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from bristlenose.screen_text import INDEX_VERSION
from bristlenose.screen_text.engine import Frame, ScreenTextEngine
from bristlenose.utils.bundled_binary import binary_command

logger = logging.getLogger(__name__)

EVERY = 4.0
MAX_WIDTH = 1920
JACCARD = 0.6
STICKY = 0.5
DENSE_LINES = 25
MIN_CONF = 0.5
#: An episode is a line at a place; places are this coarse so OCR jitter is not a move.
PLACE_X, PLACE_Y = 0.04, 0.015

_KEEP = "@./:-_#&+%'"


def fold(s: str) -> str:
    """Fold text as search folds it: lower case, accents off, ß → ss, punctuation to spaces."""
    s = s.replace("ß", "ss").replace("’", "'").replace("‘", "'").replace("€", " € ").replace("£", " £ ")
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(c if c.isalnum() or c in _KEEP or c in "€£" else " " for c in s)
    return re.sub(r"\s+", " ", s).strip()


# ── Decoding ─────────────────────────────────────────────────────────────


def probe_size(video: Path) -> tuple[int, int]:
    """The frame size ffmpeg will decode, after rotation metadata."""
    out = subprocess.run(
        [binary_command("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height:stream_side_data=rotation",
         "-of", "json", str(video)], capture_output=True, text=True, timeout=60, check=True).stdout
    streams = json.loads(out).get("streams") or []
    if not streams or not streams[0].get("width") or not streams[0].get("height"):
        raise ValueError(f"{video.name} has no video stream")
    stream = streams[0]
    w, h = int(stream["width"]), int(stream["height"])
    rot = 0
    for sd in stream.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = abs(int(sd["rotation"])) % 360
    return (h, w) if rot in (90, 270) else (w, h)


def probe_duration(video: Path) -> float | None:
    """The container's duration in seconds, or None when it does not say."""
    out = subprocess.run(
        [binary_command("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video)],
        capture_output=True, text=True, timeout=60, check=True).stdout
    try:
        return float(json.loads(out)["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        return None


def scaled_size(w: int, h: int, max_width: int = MAX_WIDTH) -> tuple[int, int]:
    if w <= max_width:
        return w - w % 2, h - h % 2
    nh = round(h * max_width / w)
    return max_width, nh - nh % 2


def sample_frames(video: Path, every: float = EVERY, should_stop: Callable[[], bool] = lambda: False
                  ) -> Iterator[Frame]:
    """Yield a frame every *every* seconds, streamed (an hour of 1080p never sits in memory)."""
    w, h = scaled_size(*probe_size(video))
    duration = probe_duration(video)
    size = w * h * 4
    proc = subprocess.Popen(
        [binary_command("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "info", "-i", str(video), "-an",
         "-vf", f"fps=1/{every},scale={w}:{h}:flags=area,showinfo", "-f", "rawvideo", "-pix_fmt", "bgra", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    times: list[float] = []
    tail: deque[str] = deque(maxlen=12)
    got_time = threading.Condition()

    def read_err() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            m = re.search(rb"pts_time:(-?[\d.]+(?:e-?\d+)?)", line)
            if m:
                with got_time:
                    times.append(float(m.group(1)))
                    got_time.notify_all()
            elif line.strip():
                tail.append(line.decode("utf-8", "replace").strip())
        with got_time:
            got_time.notify_all()

    reader = threading.Thread(target=read_err, daemon=True)
    reader.start()
    n = 0
    try:
        assert proc.stdout is not None
        while True:
            if should_stop():
                return
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            # showinfo writes the frame's line before the frame leaves the filter graph, but the
            # two pipes are read independently: wait briefly for the matching time.
            with got_time:
                got_time.wait_for(lambda n=n: len(times) > n or not reader.is_alive(), timeout=10)
                if len(times) <= n:
                    raise RuntimeError(f"no time for frame {n}")
                t = times[n]
            n += 1
            yield Frame(width=w, height=h, bgra=buf, t=round(t, 2))
        # A decode that ends early is not an index: a cut-off file or a decoder error would
        # otherwise be cached as a recording with fewer screens than it has.
        rc = proc.wait(timeout=60)
        reader.join(timeout=5)
        if rc != 0:
            raise RuntimeError(f"ffmpeg exited {rc}: {' | '.join(tail)[-400:]}")
        last = times[n - 1] if n else None
        if duration and duration > every and (last is None or last < duration - 2 * every):
            got = f"{last:.0f}" if last is not None else "0"
            raise RuntimeError(f"decoded only {got} s of {duration:.0f} s")
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        reader.join(timeout=5)


# ── Indexing ─────────────────────────────────────────────────────────────


def _place(box: list[float]) -> tuple[int, int]:
    return round(box[0] / PLACE_X), round(box[1] / PLACE_Y)


def index_frames(frames: Iterator[Frame], engine: ScreenTextEngine, every: float = EVERY) -> dict[str, Any]:
    """Read every frame and build the index record (without its cache key)."""
    samples: list[tuple[float, dict[str, dict]]] = []
    size = [0, 0]
    raw = 0
    for fr in frames:
        size = [fr.width, fr.height]
        keep: dict[str, dict] = {}
        lines = engine.recognize(fr)
        raw += len(lines)
        for ln in lines:
            f = fold(ln["text"])
            if ln["conf"] >= MIN_CONF and len(f) >= 2 and f not in keep:
                keep[f] = dict(ln)
        samples.append((fr.t, keep))
    dense = [k for _, k in samples if len(k) >= DENSE_LINES]
    freq: dict[str, int] = {}
    for k in dense:
        for f in k:
            freq[f] = freq.get(f, 0) + 1
    sticky = {f for f, c in freq.items() if dense and c / len(dense) >= STICKY}
    episodes: dict[tuple[str, tuple[int, int]], dict] = {}
    for t, k in samples:
        for f, ln in k.items():
            key = (f, _place(ln["box"]))
            e = episodes.setdefault(key, {"text": ln["text"], "box": ln["box"], "sticky": f in sticky, "runs": []})
            if e["runs"] and t - e["runs"][-1][1] <= 2 * every + 0.01:
                e["runs"][-1][1] = t
            else:
                e["runs"].append([t, t])
    moments: list[float] = []
    last: set[str] | None = None
    for t, k in samples:
        body = set(k) - sticky
        if last is None or ((body | last) and len(body & last) / len(body | last) < JACCARD):
            moments.append(t)
            last = body
    return {"version": INDEX_VERSION, "engine": engine.name, "engine_version": engine.version,
            "every": every, "size": size, "samples": len(samples), "raw_lines": raw, "moments": moments,
            "episodes": list(episodes.values())}


# ── Files ────────────────────────────────────────────────────────────────


def index_dir(output_dir: Path) -> Path:
    return output_dir / ".bristlenose" / "intermediate" / "screen-text"


def cache_key(video: Path, engine: ScreenTextEngine) -> str:
    st = video.stat()
    raw = f"{INDEX_VERSION}|{engine.name}|{engine.version}|{video.name}|{st.st_size}|{int(st.st_mtime)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def read_index(path: Path) -> dict[str, Any] | None:
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not (isinstance(rec, dict) and rec.get("version") == INDEX_VERSION
            and isinstance(rec.get("episodes"), list) and isinstance(rec.get("moments"), list)
            and isinstance(rec.get("samples"), int) and isinstance(rec.get("key"), str)):
        return None
    return rec


def is_current(path: Path, video: Path, engine: ScreenTextEngine) -> bool:
    rec = read_index(path)
    try:
        return bool(rec and rec.get("key") == cache_key(video, engine))
    except OSError:
        return False


def write_index(path: Path, record: dict[str, Any]) -> None:
    """Written whole and renamed into place: a reader on another thread never sees half of one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=True), encoding="utf-8")
    os.replace(tmp, path)


def build_index(video: Path, engine: ScreenTextEngine, out_path: Path,
                should_stop: Callable[[], bool] = lambda: False) -> bool:
    """Index *video* into *out_path* unless a current index is there. True when one exists after.

    A pass stopped by *should_stop* writes nothing: a half-read recording is not an index."""
    if out_path.exists() and is_current(out_path, video, engine):
        return True
    key = cache_key(video, engine)
    stopped = False

    def stop() -> bool:
        nonlocal stopped
        stopped = stopped or should_stop()
        return stopped

    record = index_frames(sample_frames(video, should_stop=stop), engine)
    if stopped:
        return False
    write_index(out_path, {**record, "key": key})
    logger.info("Screen text: %s · %d samples · %d lines · %d moments", out_path.stem,
                record["samples"], len(record["episodes"]), len(record["moments"]))
    return True
