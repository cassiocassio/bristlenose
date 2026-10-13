"""The Screens lens's data: screens derived from each recording's screen-text index, and stills.

``GET /api/projects/{id}/screens`` answers what the lens draws: every screen, each participant's
still on it (time and crop), the quotes pinned to on-screen lines and the quotes said there with no
pin. Quotes travel as DOM ids; the SPA joins them to the quotes store, so star, hide and tags are
the report's own. ``GET …/screens/still`` returns one cropped frame as a data URI, cached on disk.

Both are participants' screens: behind the bearer, never under ``/report/assets/``, server-only in
an export (``routes/export.py``). Diagnostics-only for now: the lens asks only with the Diagnostics
preference on, and the job that writes the indexes runs only when switched on.
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
from sqlalchemy.orm import Session

from bristlenose import screen_text
from bristlenose.output_paths import project_output_dir
from bristlenose.screen_text.index import cache_key, index_dir, read_index
from bristlenose.screen_text.screens import SessionInput, derive_screens
from bristlenose.server import speaker_slots
from bristlenose.server.models import Project
from bristlenose.server.scene_strips import video_sessions
from bristlenose.utils.bundled_binary import binary_command
from bristlenose.utils.fs import CloudFetchTimeoutError, ensure_materialised

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

_CACHE: dict[tuple, list[dict[str, Any]]] = {}
_DERIVE_LOCK = threading.Lock()
_STILL_MAX_W = 1600


def _get_db(request: Request) -> Session:
    db: Session = request.app.state.db_factory()
    return db


def _output_dir(request: Request) -> Path | None:
    project_dir: Path | None = getattr(request.app.state, "project_dir", None)
    return None if project_dir is None else project_output_dir(project_dir)


def screens_enabled(request: Request) -> bool:
    return screen_text.enabled() or bool(getattr(request.app.state, "dev", False))


@router.get("/projects/{project_id}/screens")
def get_screens(project_id: int, request: Request, db: Session = Depends(_get_db)) -> dict[str, Any]:
    """Every screen the recordings show, with each session's still, pins and unpinned quotes."""
    try:
        if not db.get(Project, project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        job = getattr(request.app.state, "screen_text", None)
        enabled = screens_enabled(request)
        unavailable = job.unavailable() if job is not None else "no screen-text job"
        out_dir = _output_dir(request)
        videos = video_sessions(db)
        failed = dict(getattr(job, "failed", {}) or {}) if job is not None else {}
        base = {"enabled": enabled, "unavailable": unavailable,
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
        key = (project_id, tuple(sorted((sid, m) for sid, (m, _) in indexes.items())),
               len(quotes), max((q.id for q in quotes), default=0),
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
        base["screens"] = screens
        return base
    finally:
        db.close()


_CROP = re.compile(r"^(0(\.\d+)?|1(\.0+)?),(0(\.\d+)?|1(\.0+)?),(0(\.\d+)?|1(\.0+)?),(0(\.\d+)?|1(\.0+)?)$")


@router.get("/projects/{project_id}/screens/still")
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
