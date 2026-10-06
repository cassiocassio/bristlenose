"""Scene colour: one colour per speaker turn, for the session tapestry's speaker clips.

The colour is *what was on screen* during the turn — camera, screen share, a white app — not a
colour for the speaker. Measured across 25 recordings, no call flipped its picture with the speaker
(gallery view and screen shares show the same frame whoever talks), so the track carries who
speaks and this colour carries the scene.

Algorithm (tuned in the colour lab, ``experiments/session-tapestry/colour-lab.html``; its defaults
are the constants below):

1. Sample every video keyframe, area-scaled to 32×18.
2. Crop black bars: drop an edge row/column when most of its pixels are near-black.
3. Ignore near-black pixels (call-grid gutters); keep whites (screen shares are information).
4. Cluster the turn's kept pixels in OKLab (k-means, deterministic).
5. Only a cluster holding at least ``MIN_SHARE`` of the pixels is eligible — the colour shown is
   one that genuinely fills that much of the frame. Pick the most colourful eligible cluster.
6. Tone it: map OKLab lightness into a lifted band and boost chroma, so a dim room reads as a
   colour rather than near-black. Both moves keep the hue.

Pure Python by design (no numpy): a turn's pixels are capped at ``MAX_PIXELS_PER_TURN``, which
keeps a whole session to a few seconds. Cosmetic, like thumbnails — any failure logs a warning
and the session simply gets no colours.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from bristlenose.utils.bundled_binary import bundled_binary_path
from bristlenose.utils.fs import CloudFetchTimeoutError, ensure_materialised

if TYPE_CHECKING:
    from bristlenose.models import FullTranscript, InputSession

logger = logging.getLogger(__name__)

VERSION = 1
FRAME_W, FRAME_H = 32, 18
BAR_LUMA = 30            # edge row/col counts as a black bar below this luma…
BAR_FRACTION = 0.85      # …for at least this share of its pixels
IGNORE_DARK_LUMA = 18    # pixels darker than this are ignored
K = 4                    # clusters
MIN_SHARE = 0.15         # a cluster must hold this share of the pixels to be picked
TONE_L_MIN, TONE_L_MAX = 0.42, 0.88
TONE_CHROMA_GAIN = 1.4
MAX_PIXELS_PER_TURN = 1500
KMEANS_ITERATIONS = 10

Lab = tuple[float, float, float]


# ── Colour maths (OKLab, Björn Ottosson 2020) ────────────────────────────


def _lin(c: int) -> float:
    v = c / 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _gam(v: float) -> float:
    v = min(1.0, max(0.0, v))
    return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def rgb_to_oklab(r: int, g: int, b: int) -> Lab:
    lr, lg, lb = _lin(r), _lin(g), _lin(b)
    l_ = (0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb) ** (1 / 3)
    m_ = (0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb) ** (1 / 3)
    s_ = (0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb) ** (1 / 3)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _oklab_to_linear(lab: Lab) -> tuple[float, float, float]:
    lightness, a, b = lab
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
        -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
        -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_,
    )


def oklab_to_hex(lab: Lab) -> str:
    """sRGB hex, gamut-mapped by reducing chroma (hue and lightness kept)."""
    lightness, a, b = lab
    for _ in range(40):
        rgb = _oklab_to_linear((lightness, a, b))
        if all(-1e-4 <= v <= 1 + 1e-4 for v in rgb):
            break
        a, b = a * 0.92, b * 0.92
    return "#" + "".join(f"{round(255 * _gam(v)):02x}" for v in _oklab_to_linear((lightness, a, b)))


def tone(lab: Lab) -> Lab:
    lightness, a, b = lab
    return (TONE_L_MIN + lightness * (TONE_L_MAX - TONE_L_MIN), a * TONE_CHROMA_GAIN, b * TONE_CHROMA_GAIN)


def _luma(r: int, g: int, b: int) -> float:
    return 0.299 * r + 0.587 * g + 0.114 * b


# ── Frames ───────────────────────────────────────────────────────────────


def frame_pixels(raw: bytes) -> list[Lab]:
    """Kept OKLab pixels of one 32×18 RGB frame: black bars cropped, near-black dropped."""
    w, h = FRAME_W, FRAME_H

    def px(x: int, y: int) -> tuple[int, int, int]:
        i = (y * w + x) * 3
        return raw[i], raw[i + 1], raw[i + 2]

    def dark(points: list[tuple[int, int]]) -> bool:
        if not points:
            return False
        n = sum(1 for x, y in points if _luma(*px(x, y)) < BAR_LUMA)
        return n / len(points) >= BAR_FRACTION

    top, bottom, left, right = 0, h - 1, 0, w - 1
    while top < bottom and dark([(x, top) for x in range(w)]):
        top += 1
    while bottom > top and dark([(x, bottom) for x in range(w)]):
        bottom -= 1
    while left < right and dark([(left, y) for y in range(top, bottom + 1)]):
        left += 1
    while right > left and dark([(right, y) for y in range(top, bottom + 1)]):
        right -= 1

    out: list[Lab] = []
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            c = px(x, y)
            if _luma(*c) >= IGNORE_DARK_LUMA:
                out.append(rgb_to_oklab(*c))
    return out


def sample_keyframes(video: Path) -> list[tuple[float, list[Lab]]]:
    """Every keyframe of *video* as (seconds, kept OKLab pixels). Decodes keyframes only."""
    ffmpeg = bundled_binary_path("ffmpeg") or "ffmpeg"
    proc = subprocess.run(
        [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "info", "-skip_frame", "nokey",
         "-i", str(video), "-an", "-vf", f"scale={FRAME_W}:{FRAME_H}:flags=area,showinfo",
         "-fps_mode", "vfr", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[-300:])
    times = [float(t) for t in re.findall(rb"pts_time:([\d.]+)", proc.stderr)]
    size = FRAME_W * FRAME_H * 3
    data = proc.stdout
    return [(t, frame_pixels(data[i * size:(i + 1) * size]))
            for i, t in enumerate(times) if (i + 1) * size <= len(data)]


# ── Clustering ───────────────────────────────────────────────────────────


def _d2(p: Lab, q: Lab) -> float:
    return (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2


def kmeans(points: list[Lab], k: int = K) -> list[tuple[Lab, float]]:
    """Deterministic k-means++ → [(centroid, share)], largest first."""
    if not points:
        return []
    seed = 12345

    def rnd() -> float:
        nonlocal seed
        seed = (seed * 16807) % 2147483647
        return seed / 2147483647

    cents = [points[int(rnd() * len(points))]]
    while len(cents) < min(k, len(points)):
        d = [min(_d2(p, c) for c in cents) for p in points]
        total = sum(d)
        if not total:
            break
        r = rnd() * total
        i = 0
        while r > d[i] and i < len(d) - 1:
            r -= d[i]
            i += 1
        cents.append(points[i])
    assign = [0] * len(points)
    for _ in range(KMEANS_ITERATIONS):
        for i, p in enumerate(points):
            assign[i] = min(range(len(cents)), key=lambda j: _d2(p, cents[j]))
        acc = [[0.0, 0.0, 0.0, 0] for _ in cents]
        for i, p in enumerate(points):
            a = acc[assign[i]]
            a[0] += p[0]
            a[1] += p[1]
            a[2] += p[2]
            a[3] += 1
        cents = [(a[0] / a[3], a[1] / a[3], a[2] / a[3]) if a[3] else c for a, c in zip(acc, cents)]
    counts = [0] * len(cents)
    for j in assign:
        counts[j] += 1
    out = [(c, n / len(points)) for c, n in zip(cents, counts) if n]
    return sorted(out, key=lambda cs: -cs[1])


def pick_colour(points: list[Lab]) -> tuple[str, float] | None:
    """The turn's colour: most colourful cluster holding at least MIN_SHARE, toned. (hex, share)."""
    if not points:
        return None
    if len(points) > MAX_PIXELS_PER_TURN:  # even stride, deterministic
        step = len(points) / MAX_PIXELS_PER_TURN
        points = [points[int(i * step)] for i in range(MAX_PIXELS_PER_TURN)]
    clusters = kmeans(points)
    eligible = [c for c in clusters if c[1] >= MIN_SHARE] or clusters[:1]
    lab, share = max(eligible, key=lambda c: math.hypot(c[0][1], c[0][2]))
    return oklab_to_hex(tone(lab)), round(share, 3)


# ── Turns and sessions ───────────────────────────────────────────────────


def turns_of(transcript: FullTranscript) -> list[tuple[float, float, str]]:
    """Consecutive same-speaker segments merged: [(start, end, speaker_code)]."""
    turns: list[tuple[float, float, str]] = []
    for seg in transcript.segments:
        code = seg.speaker_code or (seg.speaker_label or "")
        if turns and turns[-1][2] == code:
            t0, t1, _ = turns[-1]
            turns[-1] = (t0, max(t1, seg.end_time), code)
        else:
            turns.append((seg.start_time, seg.end_time, code))
    # A turn lasts until the next one starts.
    return [(t0, max(t1, nxt[0]) if nxt else t1, code)
            for (t0, t1, code), nxt in zip(turns, [*turns[1:], None])]


def session_scene_colours(
    keyframes: list[tuple[float, list[Lab]]], turns: list[tuple[float, float, str]],
) -> list[dict[str, float | str]]:
    out: list[dict[str, float | str]] = []
    for t0, t1, code in turns:
        inside = [px for t, px in keyframes if t0 <= t < t1]
        if not inside and keyframes:  # a short turn between keyframes: the nearest one
            inside = [min(keyframes, key=lambda k: abs(k[0] - t0))[1]]
        picked = pick_colour([p for frame in inside for p in frame])
        if picked:
            out.append({"t0": round(t0, 2), "t1": round(t1, 2), "speaker": code,
                        "colour": picked[0], "share": picked[1]})
    return out


def _cache_key(video: Path, turns: list[tuple[float, float, str]]) -> str:
    st = video.stat()
    h = hashlib.sha256(f"{VERSION}|{video.name}|{st.st_size}|{int(st.st_mtime)}".encode())
    for t in turns:
        h.update(f"|{t[0]:.2f},{t[1]:.2f},{t[2]}".encode())
    return h.hexdigest()[:16]


def extract_scene_colours(
    sessions: list[InputSession],
    transcripts: list[FullTranscript],
    out_dir: Path,
) -> dict[str, Path]:
    """Write ``<out_dir>/<session_id>.json`` for every video session; return what exists.

    Cached by video identity and turn boundaries, so a re-run costs nothing until the recording
    or the transcript's speaker turns change.
    """
    from bristlenose.models import FileType

    by_sid = {t.session_id: t for t in transcripts}
    written: dict[str, Path] = {}
    for session in sessions:
        transcript = by_sid.get(session.session_id)
        video = next((f.path for f in session.files if f.file_type == FileType.VIDEO), None)
        if transcript is None or video is None or not video.exists():
            continue
        turns = turns_of(transcript)
        if not turns:
            continue
        path = out_dir / f"{session.session_id}.json"
        key = _cache_key(video, turns)
        try:
            if path.exists() and json.loads(path.read_text(encoding="utf-8")).get("key") == key:
                written[session.session_id] = path
                continue
        except (OSError, ValueError):
            pass  # unreadable cache: recompute
        try:
            ensure_materialised(video)
            keyframes = sample_keyframes(video)
        except (CloudFetchTimeoutError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            logger.warning("No scene colours for %s: %s", session.session_id, exc)
            continue
        turns_out = session_scene_colours(keyframes, turns)
        out_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": VERSION, "key": key, "keyframes": len(keyframes),
                                    "turns": turns_out}, ensure_ascii=False), encoding="utf-8")
        logger.info("Scene colours: %s · %d turns from %d keyframes",
                    session.session_id, len(turns_out), len(keyframes))
        written[session.session_id] = path
    return written
