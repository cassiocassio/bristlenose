"""Turn frames: still frames of the participant's screen, for the tapestry's hover thumbnail.

Hovering the participant track of a session's timeline shows what was on screen then: one frame
per participant turn, plus one at each colour change inside a turn, so a researcher looking for
the moment a dialog appeared can step through the session without opening the video. Stepped, not
scrubbed — the frame changes only when the pointer rests on another turn or stretch.

Decided in ``experiments/session-tapestry/thumb-mockup.html`` (13 Oct 2026), whose constants these
are. A turn with no change inside it is one stretch, framed 25% in. A change splits the turn into
stretches; each later stretch is framed 2 s after its change (a frame at the change itself is
mid-transition in 13–22% of cases, 1–2 s in in 0–6%), or halfway through a stretch shorter than
4 s. A change within 2 s of the turn's start belongs to the handover and is ignored. Changes come
from the scene strip's record at ΔE 8 (``scene_strip.CHANGE_DE``). Measured: 86–112 frames an hour.

Serve extracts them in the background after the strip (``server/scene_strips.py``), never the
pipeline. The frames are participants' screens: they are served behind the bearer token, never
from the unauthenticated ``/report/assets/``, and the HTML export leaves them out.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import subprocess
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path
from typing import TypedDict

from bristlenose.utils.bundled_binary import binary_command
from bristlenose.utils.fs import CloudFetchTimeoutError, ensure_materialised

logger = logging.getLogger(__name__)

VERSION = 1
FRAME_AT = 0.25  # how far into a turn's first stretch its frame is taken
CHANGE_IN = 2.0  # seconds after a change that a later stretch is framed
EDGE_MARGIN = 2.0  # a change this close to the turn's start belongs to the handover
WIDTH = 320  # 2× the 160 px the preview is drawn at
GRAB_TIMEOUT_S = 60


class Frame(TypedDict):
    t: float  # seconds of the frame
    a: float  # the stretch it stands for
    b: float
    change: bool  # the stretch begins at a colour change (a click lands 1 s before it)


def select_frames(turns: list[tuple[float, float]], changes: list[float]) -> list[Frame]:
    """The frames to take for these participant turns ``(t0, t1)``, given the scene changes."""
    out: list[Frame] = []
    for t0, t1 in turns:
        cuts = [c for c in changes if t0 + EDGE_MARGIN < c < t1]
        bounds = [t0, *cuts, t1]
        for j, (a, b) in enumerate(pairwise(bounds)):
            at = a + FRAME_AT * (b - a) if j == 0 else a + min(CHANGE_IN, (b - a) / 2)
            out.append({"t": round(at, 1), "a": round(a, 2), "b": round(b, 2), "change": j > 0})
    return out


def selection_key(frames: list[Frame]) -> str:
    """Identifies a selection: the route compares it with what is on disk to see a stale set."""
    return hashlib.sha256(json.dumps(frames, sort_keys=True).encode()).hexdigest()[:16]


def _video_key(video: Path, selection: str) -> str:
    st = video.stat()
    return hashlib.sha256(
        f"{VERSION}|{video.name}|{st.st_size}|{int(st.st_mtime)}|{selection}".encode()
    ).hexdigest()[:16]


def grab(video: Path, t: float, width: int = WIDTH) -> bytes | None:
    """One JPEG frame of *video* at *t* seconds, *width* wide, or None when there is none (past
    the end, an undecodable moment, a timeout). Raises OSError when ffmpeg cannot be run at all:
    that is not a missing frame, and must not be recorded as one."""
    try:
        proc = subprocess.run(
            [binary_command("ffmpeg"), "-nostdin", "-loglevel", "error", "-ss", f"{max(0.0, t):.2f}",
             "-i", str(video), "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "6",
             "-f", "mjpeg", "-"],
            capture_output=True, timeout=GRAB_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        logger.debug("No frame at %.2f s of %s: %s", t, video.name,
                     proc.stderr.decode("utf-8", "replace")[-200:])
        return None
    return proc.stdout or None


def read_record(path: Path) -> dict[str, object] | None:
    """A JSON record serve wrote (frames here, or the scene strip's), or None when absent or
    unreadable (serve may be writing it)."""
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        logger.warning("Unreadable record at %s: %s", path, exc)
        return None
    return rec if isinstance(rec, dict) else None


def extract_turn_frames(session_id: str, video: Path, frames: list[Frame], out_dir: Path,
                        grabber: Callable[[Path, float], bytes | None] = grab) -> Path | None:
    """Write ``<out_dir>/<session_id>.json`` holding a JPEG for each selected frame.

    Cached by the recording's identity and the selection, so a speaker edit that moves a turn
    takes new frames and nothing else does. A record is written whatever happens — the recording
    unreadable, its download timed out, ffmpeg missing, some frames not taken — carrying the
    selection and ``complete: false``. The route asks for a pass only when the selection on disk
    differs from the current one, so a failure written down cannot make it ask on every poll;
    and an incomplete record is never a cache hit, so the next pass the job makes for its own
    reasons (serve starting, a run completing) tries again. Written whole and renamed into
    place, so the route never reads a partial one.
    """
    path = out_dir / f"{session_id}.json"
    selection = selection_key(frames)
    taken: list[dict[str, object]] = []
    key: str | None = None
    complete = False
    try:
        key = _video_key(video, selection)
        held = read_record(path)
        if held is not None and held.get("key") == key and held.get("complete") is True:
            return path
        ensure_materialised(video)
        for f in frames:
            jpg = grabber(video, f["t"])
            if jpg:
                taken.append({**f, "jpg": base64.b64encode(jpg).decode("ascii")})
        complete = len(taken) == len(frames)
    except (CloudFetchTimeoutError, OSError) as exc:  # unreadable, not downloaded, no ffmpeg
        logger.warning("Turn frames for %s stopped: %s", session_id, exc)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"version": VERSION, "key": key, "selection": selection,
                                   "complete": complete, "frames": taken}, ensure_ascii=True),
                       encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:  # the output dir can vanish under a live serve (`run --clean`)
        logger.warning("No turn frames for %s: %s", session_id, exc)
        return None
    if complete:
        logger.info("Turn frames: %s · %d", session_id, len(taken))
    else:
        logger.warning("Turn frames: %s · %d of %d taken; the next pass tries again",
                       session_id, len(taken), len(frames))
    return path
