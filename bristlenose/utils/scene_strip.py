"""Scene strip: the colour of what was on screen, moment by moment, for the session tapestry.

The tapestry's speaker clips each carry one scene colour (``scene_colour.py``). The strip runs
*inside* those clips at an opacity: one column per sample, so a change of environment during a
session — the call becoming a screen share, a browser becoming a terminal — shows as a change in
the bar, and a notch above the lane marks where it happened. A steady scene stays flat.

Sampling is every frame at ``FPS`` (4 fps), one sample per pixel at the tapestry's maximum zoom of
0.25 s/px. Measured 12 Oct 2026: about 8 s per hour of a call recording in software decode, the
expensive source being a 4K 120 fps screen capture at about 7 minutes per hour. Each sample is the
mean OKLab of the frame's kept pixels — black bars cropped, near-black dropped, as the per-turn
colour does — toned into a light band (the stripes sit over the clip, so they read as a wash,
not a block). Tuned in ``experiments/session-tapestry/strip-lab.html``; the constants below are
its defaults.

Serve computes the strip in the background after the report is readable, never the pipeline:
it is an enhancement that arrives later, and a run must not wait on it. Cosmetic like thumbnails
and scene colours — any failure logs a warning and the session simply has no strip.

The strip ships as a 1×N RGB PNG (written here without an image library) plus the notch times.
Changing a constant here changes every strip, so bump ``VERSION``: it is in the cache key.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import math
import os
import re
import struct
import subprocess
import zlib
from pathlib import Path
from typing import TypedDict

from bristlenose.utils.bundled_binary import binary_command
from bristlenose.utils.fs import CloudFetchTimeoutError, ensure_materialised
from bristlenose.utils.scene_colour import (
    FRAME_H,
    FRAME_W,
    Lab,
    _gam,
    _oklab_to_linear,
    frame_pixels,
)

logger = logging.getLogger(__name__)

VERSION = 2
FPS = 4
#: Tone for the stripes: lighter than the clip's band (0.42–0.88), since they sit over it.
STRIP_L_MIN, STRIP_L_MAX = 0.64, 1.0
STRIP_CHROMA_GAIN = 1.4
#: A notch where the mean colour of the two seconds before a moment and the two seconds after it
#: differ by at least this much (OKLab ΔE × 100, on the untoned means: the notch is about the
#: scene, not the display); the strongest within the window wins. Calibrated 12 Oct 2026 over
#: 28 recordings: at 14, a gallery call gets zero or one notch (its title card), a usability
#: session with page switches one every couple of minutes.
EDGE_DE = 14.0
EDGE_WINDOW_S = 2.0
#: Finer changes for the hover thumbnail's frames (``turn_frames.py``): at ΔE 8 a scene is
#: colour-stable inside (p90 spread 0.4 or less on the mockup sessions, 13 Oct 2026), which
#: the notches' ΔE 14 is not (8.5). Kept in the record so serve need not decode twice.
CHANGE_DE = 8.0
#: Decode budget per recording: the 4K worst case is about 7 minutes per hour of video.
DECODE_TIMEOUT_S = 3600

RGB = tuple[int, int, int]
_BLACK: Lab = (0.0, 0.0, 0.0)


class StripRecord(TypedDict):
    version: int
    fps: int
    n: int
    t0: float  # seconds of the first sample: the stream's start, not always zero
    png: str  # base64 of a 1×n RGB PNG
    edges: list[float]
    changes: list[float]  # finer scene changes (CHANGE_DE), for the hover thumbnail's frames


# ── Sampling ─────────────────────────────────────────────────────────────


def sample_dense(video: Path, fps: int = FPS) -> tuple[float, list[Lab]]:
    """(seconds of the first sample, mean kept-pixel OKLab of every frame of *video* at *fps*).

    A frame with nothing kept (a black screen) is black. The first sample's time is read from
    ffmpeg, never assumed to be zero: a stream that starts late (an edit list, a trimmed container)
    would otherwise put every stripe and notch early against the transcript."""
    proc = subprocess.run(
        [binary_command("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "info", "-i", str(video),
         "-an", "-vf", f"fps={fps},scale={FRAME_W}:{FRAME_H}:flags=area,showinfo",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, timeout=DECODE_TIMEOUT_S,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[-300:])
    times = [float(t) for t in re.findall(rb"pts_time:(-?[\d.]+(?:e-?\d+)?)", proc.stderr)]
    size = FRAME_W * FRAME_H * 3
    data = proc.stdout
    n = len(data) // size
    # Times (stderr) and frames (stdout) are paired by position, so a count that disagrees would
    # put every later stripe on the wrong moment. Refuse rather than mis-pair.
    if n == 0 or len(times) != n or len(data) != n * size:
        raise RuntimeError(f"dense sampling gave {len(times)} times for {n} frames")
    return times[0], [mean_lab(frame_pixels(data[i * size:(i + 1) * size])) for i in range(n)]


def mean_lab(points: list[Lab]) -> Lab:
    if not points:
        return _BLACK
    n = len(points)
    return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n, sum(p[2] for p in points) / n)


# ── Colour ───────────────────────────────────────────────────────────────


def tone_strip(lab: Lab) -> Lab:
    """Lightness into the stripes' band, chroma boosted; hue kept."""
    return (STRIP_L_MIN + lab[0] * (STRIP_L_MAX - STRIP_L_MIN),
            lab[1] * STRIP_CHROMA_GAIN, lab[2] * STRIP_CHROMA_GAIN)


def lab_to_rgb(lab: Lab) -> RGB:
    """sRGB bytes, gamut-mapped by pulling chroma in."""
    light, a, b = lab
    lin = _oklab_to_linear((light, a, b))
    for _ in range(30):
        if all(-1e-4 <= v <= 1 + 1e-4 for v in lin):
            break
        a *= 0.92
        b *= 0.92
        lin = _oklab_to_linear((light, a, b))
    return tuple(max(0, min(255, round(255 * _gam(min(1.0, max(0.0, v)))))) for v in lin)  # type: ignore[return-value]


def _de(p: Lab, q: Lab) -> float:
    return 100 * math.sqrt((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2)


# ── Notches ──────────────────────────────────────────────────────────────


def scene_edges(means: list[Lab], fps: int = FPS, threshold: float = EDGE_DE,
                window_s: float = EDGE_WINDOW_S) -> list[float]:
    """Seconds at which the scene changed: the mean of the window before a sample against the
    mean of the window after it, above *threshold*, keeping the strongest within a window either
    side. A fade or a slow transition is spread over several samples, so neighbours alone miss it.
    Measured on the untoned means — toning compresses lightness and would hide a call becoming
    a white page."""
    n = len(means)
    w = max(1, round(window_s * fps))
    if n < 2 * w:
        return []
    # Prefix sums per channel make every window mean O(1).
    pre = [(0.0, 0.0, 0.0)]
    for lab in means:
        last = pre[-1]
        pre.append((last[0] + lab[0], last[1] + lab[1], last[2] + lab[2]))

    def mean(a: int, b: int) -> Lab:
        k = b - a
        return ((pre[b][0] - pre[a][0]) / k, (pre[b][1] - pre[a][1]) / k, (pre[b][2] - pre[a][2]) / k)

    d = [0.0] * n
    for i in range(w, n - w + 1):
        d[i] = _de(mean(i - w, i), mean(i, i + w))
    edges: list[float] = []
    for i in range(w, n - w + 1):
        if d[i] < threshold:
            continue
        lo, hi = max(0, i - w), min(n - 1, i + w)
        if all(d[j] < d[i] or (d[j] == d[i] and j >= i) for j in range(lo, hi + 1) if j != i):
            edges.append(round(i / fps, 2))
    return edges


# ── PNG ──────────────────────────────────────────────────────────────────


def encode_png_row(pixels: list[RGB]) -> bytes:
    """A 1×N 8-bit RGB PNG, filter type 0 on its one row. No image library needed."""
    n = len(pixels)
    raw = b"\x00" + b"".join(bytes(p) for p in pixels)

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", n, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


# ── Files ────────────────────────────────────────────────────────────────


def _cache_key(video: Path) -> str:
    st = video.stat()
    return hashlib.sha256(f"{VERSION}|{video.name}|{st.st_size}|{int(st.st_mtime)}".encode()).hexdigest()[:16]


def strip_record(means: list[Lab], fps: int = FPS, t0: float = 0.0) -> StripRecord:
    """The on-disk record for one session's samples (without the cache key)."""
    toned = [tone_strip(lab) for lab in means]
    png = encode_png_row([lab_to_rgb(lab) for lab in toned])
    return {"version": VERSION, "fps": fps, "n": len(means), "t0": round(t0, 3),
            "png": base64.b64encode(png).decode("ascii"),
            "edges": [round(t0 + e, 2) for e in scene_edges(means, fps)],
            "changes": [round(t0 + e, 2) for e in scene_edges(means, fps, CHANGE_DE)]}


def is_current(path: Path, video: Path) -> bool:
    """True when *path* holds a strip for *video* as it is now."""
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("key") == _cache_key(video))
    except (OSError, ValueError):
        return False


def extract_scene_strips(videos: dict[str, Path], out_dir: Path) -> dict[str, Path]:
    """Write ``<out_dir>/<session_id>.json`` for every session in *videos*; return what exists.

    Cached by the recording's identity. Each file is written whole and renamed into place, so a
    reader (the tapestry route, on another thread) never sees a partial one.
    """
    written: dict[str, Path] = {}
    for session_id, video in videos.items():
        path = out_dir / f"{session_id}.json"
        if not video.exists():
            continue
        try:
            key = _cache_key(video)
        except OSError as exc:  # one unreadable recording must not stop the rest
            logger.warning("No scene strip for %s: %s", session_id, exc)
            continue
        if path.exists() and is_current(path, video):
            written[session_id] = path
            continue
        try:
            ensure_materialised(video)
            t0, means = sample_dense(video)
        except (CloudFetchTimeoutError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            logger.warning("No scene strip for %s: %s", session_id, exc)
            continue
        record = strip_record(means, t0=t0)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({**record, "key": key}, ensure_ascii=True), encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:  # the output dir can vanish under a live serve (`run --clean`)
            logger.warning("No scene strip for %s: %s", session_id, exc)
            continue
        logger.info("Scene strip: %s · %d samples · %d notches", session_id, len(means), len(record["edges"]))
        written[session_id] = path
    return written
