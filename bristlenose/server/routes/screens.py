"""The Screens lens's data: screens derived from each recording's screen-text index, and stills.

``GET /api/projects/{id}/screens`` answers what the lens draws: every screen, each participant's
still on it (time and crop), the quotes pinned to on-screen lines and the quotes said there with no
pin. Quotes travel as DOM ids; the SPA joins them to the quotes store, so star, hide and tags are
the report's own. ``GET …/screens/still`` returns one cropped frame as a data URI, cached on disk.
``GET …/screens/status`` is the Mac app's progress row and the lens's switch: counts, recording
seconds, the reading rate and whether any screen was found, from the database and a stat per
recording. It decodes nothing, and derives screens only when the indexes change.

Why something cannot be read travels as a reason code (``bristlenose.screen_text.Unavailable`` /
``ReadFailure``), never a sentence; the SPA and the Mac app say it in the researcher's language.
A recording with no index, no failure and an idle job is ``not_read``, so a poller always stops.

All three are about participants' screens: behind the bearer, never under ``/report/assets/``,
server-only in an export (``routes/export.py``). The job that writes the indexes runs only when
switched on (``screen_text.wanted``: the Mac app's default, or ``serve --dev``). Switched off,
``/screens`` and ``/screens/status`` answer 200 with ``enabled: false`` (the lens and the progress
row must be able to see "off"), and ``/screens/still`` answers 404.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
import subprocess
import threading
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose import screen_text
from bristlenose.output_paths import project_output_dir
from bristlenose.screen_text import ReadFailure, Unavailable
from bristlenose.screen_text.index import cache_key, index_dir, read_index, stored_key
from bristlenose.screen_text.screens import SessionInput, derive_screens
from bristlenose.server import speaker_slots
from bristlenose.server.models import Project
from bristlenose.server.scene_strips import video_sessions
from bristlenose.server.screen_text_job import session_durations
from bristlenose.utils.bundled_binary import binary_command
from bristlenose.utils.fs import CloudFetchTimeoutError, ensure_materialised

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

_CACHE: dict[tuple, list[dict[str, Any]]] = {}
#: Whether the indexes show any screen, by their identity (the first part of ``_CACHE``'s key). Not
#: keyed on the quotes: they place and pin on screens, they never make or remove one.
_HAS_SCREENS: dict[tuple[Any, ...], bool] = {}
_DERIVE_LOCK = threading.Lock()
_STILL_MAX_W = 1600


def _get_db(request: Request) -> Session:
    db: Session = request.app.state.db_factory()
    return db


def _output_dir(request: Request) -> Path | None:
    project_dir: Path | None = getattr(request.app.state, "project_dir", None)
    return None if project_dir is None else project_output_dir(project_dir)


def screens_enabled(request: Request) -> bool:
    return screen_text.wanted(bool(getattr(request.app.state, "dev", False)))


def _ident(project_id: int, mtimes: dict[str, int]) -> tuple[Any, ...]:
    """The indexes' identity: which sessions have a current one, and when each was written."""
    return (project_id, tuple(sorted(mtimes.items())))


def _remember_has_screens(ident: tuple[Any, ...], screens: list[dict[str, Any]]) -> None:
    _HAS_SCREENS.clear()  # one project per server; the latest identity is all that is wanted
    _HAS_SCREENS[ident] = bool(screens)


# The shape ``screen_text/screens.py``'s ``derive_screens`` returns, field for field.
# ``tests/test_screens_status.py::test_the_models_carry_every_field_derive_screens_returns`` pins
# the two against each other.


class ScreenPin(BaseModel):
    dom_id: str
    #: x, y, w, h in the still's crop coordinates (0–1 of the cropped page).
    box: list[float]
    phrase: str
    line: str


class ScreenTab(BaseModel):
    """One session's view of one screen."""

    session_id: str
    code: str
    #: The still's time in the recording, seconds.
    t: float
    #: x0, y0, x1, y1 of the page within the frame, 0–1.
    crop: list[float]
    heading: str
    #: [t0, t1] for each time the session was on this screen.
    visits: list[list[float]]
    pins: list[ScreenPin]
    #: DOM ids of the quotes said on this screen that are pinned to no line.
    loose: list[str]


class Screen(BaseModel):
    key: str
    name: str
    tabs: list[ScreenTab]
    #: The version shown first: the one on which the most quotes, anyone's, find their line.
    default_tab: int
    quotes: int


class ScreensResponse(BaseModel):
    enabled: bool
    unavailable: Unavailable | None
    pending: bool
    reading: str | None
    videos: int
    indexed: int
    failed: dict[str, ReadFailure]
    blank: list[str]
    screens: list[Screen]


class StillResponse(BaseModel):
    src: str


class ScreensStatusResponse(BaseModel):
    enabled: bool
    unavailable: Unavailable | None
    running: bool
    #: Recordings not waiting to be read: a current index, or a reason why there is none.
    done: int
    #: Sessions with a video recording.
    total: int
    #: Recording seconds, from the database's session durations (unknown counts 0).
    seconds_done: float
    seconds_total: float
    #: Recording seconds read per wall-clock second by the current (or last) pass; null until
    #: that pass has read one recording.
    rate: float | None
    #: At least one screen derived from this study's indexes. False with nothing indexed, and for
    #: recordings that are all talking heads (text, but no address or title to key a screen on).
    has_screens: bool


@router.get("/projects/{project_id}/screens", response_model=ScreensResponse)
def get_screens(project_id: int, request: Request, db: Session = Depends(_get_db)) -> dict[str, Any]:
    """Every screen the recordings show, with each session's still, pins and unpinned quotes."""
    try:
        if not db.get(Project, project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        job = getattr(request.app.state, "screen_text", None)
        enabled = screens_enabled(request)
        # Off is its own answer, as on /screens/status: why it could not run is moot.
        unavailable: Unavailable | None = (None if not enabled
                                           else job.unavailable() if job is not None else "no_job")
        out_dir = _output_dir(request)
        videos = video_sessions(db)
        failed = dict(getattr(job, "failed", {}) or {}) if job is not None else {}
        base: dict[str, Any] = {"enabled": enabled, "unavailable": unavailable,
                "pending": bool(job is not None and job.running),
                "reading": job.current if job is not None else None,
                "videos": len(videos), "indexed": 0,
                "failed": {sid: why for sid, why in failed.items() if sid in videos},
                "blank": [], "screens": []}
        if not enabled or out_dir is None:
            return base
        idir = index_dir(out_dir)
        indexes: dict[str, tuple[int, dict[str, Any]]] = {}
        for sid in videos:
            path = idir / f"{sid}.json"
            try:
                mtime = path.stat().st_mtime_ns
            except OSError:
                continue
            rec = read_index(path)
            if rec is None:
                continue
            if job is not None:
                # An index of a recording that has since changed is not this recording's: the
                # job will read it again, and until then it is pending, not indexed.
                try:
                    if rec["key"] != cache_key(videos[sid], job.engine):
                        continue
                except OSError:
                    continue
            indexes[sid] = (mtime, rec)
            if not rec.get("raw_lines") and rec.get("samples"):
                base["blank"].append(sid)  # the engine read frames and found no text in any
        base["indexed"] = len(indexes)
        if job is not None:
            in_run = job.run_in_progress()
            for sid in videos:
                if sid not in indexes:
                    why = job.why_unread(sid, in_run)
                    if why is not None:
                        base["failed"][sid] = why
        if not indexes:
            return base

        quotes = speaker_slots.evidence_quotes(db, project_id)
        by_session: dict[str, list[dict[str, Any]]] = {}
        codes: dict[str, Counter] = {}
        for q in quotes:
            by_session.setdefault(q.session_id, []).append({
                "dom_id": f"q-{q.participant_id}-{int(q.start_timecode)}",
                "start": float(q.start_timecode), "end": float(q.end_timecode),
                "text": q.verbatim_excerpt or q.text,
            })
            codes.setdefault(q.session_id, Counter())[q.participant_id] += 1
        ident = _ident(project_id, {sid: m for sid, (m, _) in indexes.items()})
        key = (*ident, len(quotes), max((q.id for q in quotes), default=0),
               max((str(q.last_imported_at) for q in quotes), default=""))
        screens = _CACHE.get(key)
        if screens is None:
            with _DERIVE_LOCK:  # one derivation at a time: a second request waits for the first's
                screens = _CACHE.get(key)
                if screens is None:
                    sessions = [SessionInput(sid, codes[sid].most_common(1)[0][0] if sid in codes else sid,
                                             rec, by_session.get(sid, []))
                                for sid, (_, rec) in indexes.items()]
                    screens = derive_screens(sessions)
                    _CACHE.clear()  # one project per server; the latest derivation is all that is wanted
                    _CACHE[key] = screens
                    _remember_has_screens(ident, screens)
        base["screens"] = screens
        return base
    finally:
        db.close()


_CROP = re.compile(r"^(0(\.\d+)?|1(\.0+)?),(0(\.\d+)?|1(\.0+)?),(0(\.\d+)?|1(\.0+)?),(0(\.\d+)?|1(\.0+)?)$")


@router.get("/projects/{project_id}/screens/still", response_model=StillResponse)
def get_still(
    project_id: int,
    request: Request,
    session_id: str = Query(..., max_length=64),
    t: float = Query(..., ge=0, le=86400),
    w: int = Query(1200, ge=80, le=_STILL_MAX_W),
    crop: str = Query("0,0,1,1", max_length=80),
    db: Session = Depends(_get_db),
) -> dict[str, str]:
    """One frame of a session's recording, cropped to the page and scaled, as a data URI."""
    try:
        if not db.get(Project, project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        if not screens_enabled(request):
            raise HTTPException(status_code=404, detail="Screens are off")
        if not _CROP.match(crop):
            raise HTTPException(status_code=422, detail="crop is x0,y0,x1,y1 in 0–1")
        x0, y0, x1, y1 = (float(v) for v in crop.split(","))
        if x1 - x0 < 0.05 or y1 - y0 < 0.05:
            raise HTTPException(status_code=422, detail="crop is too small")
        video = video_sessions(db).get(session_id)
        out_dir = _output_dir(request)
        if video is None or out_dir is None:
            raise HTTPException(status_code=404, detail="No recording")
    finally:
        db.close()
    try:
        st = video.stat()
    except OSError as exc:
        raise HTTPException(status_code=404, detail="No recording") from exc
    # Keyed on the session and the file's identity, not its name: two sessions' recordings are
    # often both called zoom_0.mp4, and a trimmed re-drop keeps its name. Named for the session so
    # the pipeline's per-session prune removes a withdrawn participant's stills.
    ident = f"{session_id}|{video}|{st.st_size}|{int(st.st_mtime)}|{t:.2f}|{w}|{crop}"
    tag = hashlib.sha256(ident.encode()).hexdigest()[:16]
    cache = index_dir(out_dir) / "stills" / f"{session_id}_{tag}.jpg"
    if not cache.exists():
        try:
            ensure_materialised(video)
            vf = f"crop=iw*{x1 - x0:.4f}:ih*{y1 - y0:.4f}:iw*{x0:.4f}:ih*{y0:.4f},scale={w}:-2"
            jpg = subprocess.run(
                [binary_command("ffmpeg"), "-nostdin", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video),
                 "-frames:v", "1", "-vf", vf, "-q:v", "3", "-f", "mjpeg", "-"],
                capture_output=True, check=True, timeout=60).stdout
        except CloudFetchTimeoutError as exc:
            raise HTTPException(status_code=404, detail="The recording is still downloading") from exc
        except subprocess.CalledProcessError as exc:
            err = exc.stderr.decode("utf-8", "replace")[-300:] if isinstance(exc.stderr, bytes) else ""
            logger.warning("No still for %s at %.1f: ffmpeg exit %s %s", session_id, t, exc.returncode, err)
            raise HTTPException(status_code=404, detail="ffmpeg could not read that frame") from exc
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("No still for %s at %.1f: %s", session_id, t, type(exc).__name__)
            raise HTTPException(status_code=404, detail="No still") from exc
        if not jpg:
            raise HTTPException(status_code=404, detail="No still")
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache.with_name(f"{cache.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_bytes(jpg)
            tmp.replace(cache)
        except OSError:
            pass  # a cache miss next time, not an error now
    else:
        jpg = cache.read_bytes()
    return {"src": "data:image/jpeg;base64," + base64.b64encode(jpg).decode("ascii")}


@router.get("/projects/{project_id}/screens/status", response_model=ScreensStatusResponse)
def get_screens_status(project_id: int, request: Request,
                       db: Session = Depends(_get_db)) -> dict[str, Any]:
    """How far the screen-text job has got, for the Mac app's progress row, and whether the lens
    has anything to show. Polled every 3 s, so cheap by design: the database and a stat per
    recording (an index parsed only when it has been rewritten). It never decodes a frame or reads
    a recording's bytes, and derives screens only when the indexes' identity changes — once per
    index the job writes, never per poll; with nothing indexed, ``has_screens`` is false without
    deriving.

    The SPA and the Mac app show the Screens lens iff
    ``enabled and unavailable is None and (has_screens or (total > 0 and (running or done < total)))``:
    a study with screens, or one still being read. A study read to the end with no screen in it
    (talking heads, or no recordings) has no lens."""
    try:
        if not db.get(Project, project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        job = getattr(request.app.state, "screen_text", None)
        out: dict[str, Any] = {"enabled": screens_enabled(request),
               "unavailable": job.unavailable() if job is not None else "no_job",
               "running": False, "done": 0, "total": 0, "seconds_done": 0.0, "seconds_total": 0.0,
               "rate": None, "has_screens": False}
        out_dir = _output_dir(request)
        if not out["enabled"]:
            out["unavailable"] = None  # off is its own answer; why it could not run is moot
            return out
        videos = video_sessions(db)
        # Not filtered by project, like video_sessions: the two must agree on which sessions
        # count, or a database holding a forked second row reads a total with no durations.
        durations = session_durations(db)
    finally:
        db.close()
    out["total"] = len(videos)
    out["seconds_total"] = sum(durations.get(sid, 0.0) for sid in videos)
    if job is None or out_dir is None:
        return out
    out["running"] = bool(job.running)
    out["rate"] = job.rate
    idir = index_dir(out_dir)
    in_run = job.run_in_progress()
    mtimes: dict[str, int] = {}
    for sid, video in videos.items():
        path = idir / f"{sid}.json"
        try:
            current = stored_key(path) == cache_key(video, job.engine)
            if current:
                mtimes[sid] = path.stat().st_mtime_ns
        except OSError:
            current = False
        if current or job.why_unread(sid, in_run) is not None:
            out["done"] += 1
            out["seconds_done"] += durations.get(sid, 0.0)
    out["has_screens"] = _has_screens(project_id, idir, mtimes)
    return out


def _has_screens(project_id: int, idir: Path, mtimes: dict[str, int]) -> bool:
    """Whether the current indexes show any screen: cached on their identity, which ``/screens``
    shares, so a poll costs a lookup and a derivation runs once per change to the indexes."""
    if not mtimes:
        return False
    ident = _ident(project_id, mtimes)
    hit = _HAS_SCREENS.get(ident)
    if hit is not None:
        return hit
    with _DERIVE_LOCK:
        hit = _HAS_SCREENS.get(ident)
        if hit is not None:
            return hit
        sessions = []
        for sid in mtimes:
            rec = read_index(idir / f"{sid}.json")
            if rec is None:
                return False  # replaced as we read; the next poll has a new identity
            sessions.append(SessionInput(sid, sid, rec, []))
        # Without quotes: they decide where a quote goes, never whether a screen exists.
        screens = derive_screens(sessions)
        _remember_has_screens(ident, screens)
        return bool(screens)
