"""Export the Screens lens's stills as a folder of images.

One still per participant per screen, full size, named so Finder's sort is time order per
participant (`screen_text/shots.py`), written to ``bristlenose-output/screens/``. The clip
export is the sibling: a folder not a zip, files removed by the last export's manifest (never a
glob), a cancellable job, Show in Finder. The Mac app's clipboard copy is this folder's files on
the pasteboard (`docs/design-screens-export.md` §4–§5).

The manifest is a dotfile, unlike the clips': selecting everything in the folder and copying it,
the browser's way to the clipboard copy, must not carry it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from bristlenose.output_paths import project_output_dir
from bristlenose.screen_text.shots import shot_list
from bristlenose.server.models import Project, Quote, QuoteState
from bristlenose.server.routes.screens import (
    StillError,
    derive_project_screens,
    render_still,
    screens_enabled,
)
from bristlenose.server.scene_strips import video_sessions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

_jobs: dict[int, dict[str, Any]] = {}  # project_id → job state
_MANIFEST_NAME = ".screens_manifest.json"
FOLDER = "screens"


def _hidden_dom_ids(db: Any, project_id: int) -> set[str]:
    quotes = {q.id: q for q in db.query(Quote).filter_by(project_id=project_id).all()}
    return {
        f"q-{quotes[s.quote_id].participant_id}-{int(quotes[s.quote_id].start_timecode)}"
        for s in db.query(QuoteState).filter(
            QuoteState.quote_id.in_(quotes), QuoteState.is_hidden.is_(True),
        ).all()
        if s.quote_id in quotes
    }


def _remove_previous_export(folder: Path) -> None:
    """Delete the files the last export's manifest names; anything else in the folder stays."""
    path = folder / _MANIFEST_NAME
    try:
        entries = json.loads(path.read_text(encoding="utf-8")).get("files", [])
    except FileNotFoundError:
        return
    except (OSError, ValueError, AttributeError):
        logger.warning("Unreadable %s; earlier stills left in place", _MANIFEST_NAME, exc_info=True)
        return
    for name in entries if isinstance(entries, list) else []:
        if isinstance(name, str) and name and name == Path(name).name and not name.startswith("."):
            try:
                (folder / name).unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove earlier still %s", name, exc_info=True)
    path.unlink(missing_ok=True)


def _write_manifest(folder: Path, files: list[str]) -> None:
    tmp = folder / f"{_MANIFEST_NAME}.tmp"
    tmp.write_text(json.dumps({
        "exported_at": datetime.now(timezone.utc).isoformat(), "files": files,
    }, indent=2, ensure_ascii=True), encoding="utf-8")
    os.replace(tmp, folder / _MANIFEST_NAME)


async def _run(project_id: int, job: dict[str, Any], out_dir: Path, folder: Path,
               shots: list[dict[str, Any]], videos: dict[str, Path]) -> None:
    written: list[str] = []
    try:
        _remove_previous_export(folder)
        for shot in shots:
            if job["status"] == "cancelled":
                break
            job["current"] = shot["filename"]
            video = videos.get(shot["session_id"])
            try:
                if video is None:
                    raise StillError("No recording")
                jpg = await asyncio.to_thread(
                    render_still, out_dir, shot["session_id"], video, shot["t"],
                    tuple(shot["crop"]), None,
                )
                (folder / shot["filename"]).write_bytes(jpg)
                written.append(shot["filename"])
                job["completed_count"] += 1
                _write_manifest(folder, written)  # as each lands, so a death part-way still names it
            except (StillError, OSError):
                logger.warning("Skipped still %s", shot["filename"], exc_info=True)
                job["skipped_count"] += 1
            job["progress"] += 1
        if _jobs.get(project_id) is job:
            _write_manifest(folder, written)
        job["status"] = "cancelled" if job["status"] == "cancelled" else "completed"
    except Exception:
        logger.exception("Screens export failed")
        job["status"] = "failed"
    job["files"] = written
    job["output_dir"] = str(folder)
    job["current"] = ""


class ScreensExportStart(BaseModel):
    status: str
    total: int


class ScreensExportStatus(BaseModel):
    status: str
    progress: int
    total: int
    completed_count: int
    skipped_count: int
    current: str
    output_dir: str | None
    #: The files written, in export order — for the Mac app's clipboard copy.
    files: list[str]


@router.post("/projects/{project_id}/export/screens")
async def start_screens_export(request: Request, project_id: int) -> ScreensExportStart:
    """Start writing every still to ``bristlenose-output/screens/``."""
    existing = _jobs.get(project_id)
    if existing and existing.get("status") == "running":
        raise HTTPException(status_code=409, detail="A screens export is already running")
    task = existing.get("task") if existing else None
    if task is not None and not task.done():
        raise HTTPException(status_code=409, detail="The last screens export is still stopping")
    project_dir = getattr(request.app.state, "project_dir", None)
    if project_dir is None:
        raise HTTPException(status_code=400, detail="No project directory configured")
    if not screens_enabled(request):
        raise HTTPException(status_code=404, detail="Screens are off")
    out_dir = project_output_dir(Path(project_dir))
    db = request.app.state.db_factory()
    try:
        if not db.get(Project, project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        state, owner = derive_project_screens(request, db, project_id)
        shots = shot_list(state["screens"], owner, _hidden_dom_ids(db, project_id))
        videos = video_sessions(db)
    finally:
        db.close()
    if not shots:
        return ScreensExportStart(status="no_screens", total=0)
    folder = out_dir / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    job: dict[str, Any] = {"status": "running", "progress": 0, "total": len(shots),
                           "completed_count": 0, "skipped_count": 0, "current": "",
                           "output_dir": None, "files": []}
    _jobs[project_id] = job
    # Held by the job: the loop keeps only a weak reference to a bare task.
    job["task"] = asyncio.create_task(_run(project_id, job, out_dir, folder, shots, videos))
    return ScreensExportStart(status="started", total=len(shots))


@router.get("/projects/{project_id}/export/screens/status")
async def screens_export_status(project_id: int) -> ScreensExportStatus:
    job = _jobs.get(project_id) or {}
    return ScreensExportStatus(
        status=job.get("status", "idle"), progress=job.get("progress", 0),
        total=job.get("total", 0), completed_count=job.get("completed_count", 0),
        skipped_count=job.get("skipped_count", 0), current=job.get("current", ""),
        output_dir=job.get("output_dir"), files=job.get("files", []),
    )


@router.post("/projects/{project_id}/export/screens/cancel")
async def cancel_screens_export(project_id: int) -> dict[str, Any]:
    """Stop after the still being written; those already written stay."""
    job = _jobs.get(project_id)
    if job is None or job.get("status") != "running":
        raise HTTPException(status_code=404, detail="No screens export in progress")
    job["status"] = "cancelled"
    return {"cancelled": True}


@router.post("/projects/{project_id}/export/screens/reveal")
async def reveal_screens(request: Request, project_id: int) -> dict[str, Any]:
    """Show the folder in the system file manager, its first still selected."""
    job = _jobs.get(project_id)
    project_dir = getattr(request.app.state, "project_dir", None)
    if job is None or job.get("output_dir") is None or project_dir is None:
        raise HTTPException(status_code=404, detail="No finished screens export")
    folder = Path(job["output_dir"]).resolve()
    if not folder.is_relative_to(project_output_dir(Path(project_dir)).resolve()):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not folder.is_dir():
        raise HTTPException(status_code=404, detail="Screens folder not found")
    files = [folder / f for f in job.get("files", []) if (folder / f).is_file()]
    target = files[0] if files else folder
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", "-R", str(target)], check=False)
    elif system == "Linux":
        subprocess.run(["xdg-open", str(folder)], check=False)
    else:
        return {"revealed": False, "path": str(folder)}
    return {"revealed": True, "path": str(target)}


# ---------------------------------------------------------------------------
# The screens as a Miro board — a frame per screen (docs/design-screens-export.md §6)
# ---------------------------------------------------------------------------

_miro_jobs: dict[int, dict[str, Any]] = {}
_MAX_QUOTE_CHARS = 300


def _sticky_html(q: Any) -> str:
    from html import escape

    from bristlenose.board_layout import attribution, quoted
    from bristlenose.utils.timecodes import parse_timecode

    body = q.text if len(q.text) <= _MAX_QUOTE_CHARS else q.text[: _MAX_QUOTE_CHARS - 1].rstrip() + "…"
    return f"{escape(quoted(body))}<br><i>{escape(attribution(q.participant_code, parse_timecode(q.timecode)))}</i>"


def _run_miro_sync(job: dict[str, Any], token: str, title: str, out_dir: Path,
                   screens: list[dict[str, Any]], videos: dict[str, Path],
                   quotes: dict[str, Any], colour_by: str) -> None:
    """Render each screen's still, lay the board out, and build it on Miro. Runs in a worker
    thread; the job dict is its only output. A board left part-built names its link, as the quotes
    board does."""
    from bristlenose import miro_client
    from bristlenose.board_layout import DEFAULT_QUOTE_TOKEN, SENTIMENT_TOKEN, STICKY_SHAPE
    from bristlenose.screens_board import STICKY_H, STICKY_W, jpeg_size, lay_out_board

    stills: dict[str, bytes] = {}
    sizes: dict[str, tuple[int, int]] = {}
    for shot in screens:
        if job["status"] == "cancelled":
            return
        job["current"] = shot["filename"]
        video = videos.get(shot["session_id"])
        try:
            if video is None:
                raise StillError("No recording")
            jpg = render_still(out_dir, shot["session_id"], video, shot["t"], tuple(shot["crop"]), None)
        except StillError:
            logger.warning("Skipped still %s", shot["filename"], exc_info=True)
            job["skipped_count"] += 1
            continue
        size = jpeg_size(jpg)
        if size is None:
            job["skipped_count"] += 1
            continue
        stills[shot["filename"]] = jpg
        sizes[shot["filename"]] = size
    frames = lay_out_board(screens, sizes, known=set(quotes))
    job["total"] = len(frames)
    if not frames:
        job["status"] = "completed"
        return
    board = miro_client.create_board(token, title)
    board_id = board.get("id")
    if not board_id:
        raise miro_client.MiroError("Miro did not return a board id", reason="no_board_id")
    job["board_url"] = board.get("viewLink") or f"https://miro.com/app/board/{board_id}/"
    for frame in frames:
        if job["status"] == "cancelled":
            return
        job["current"] = frame.filename
        made = miro_client.create_frame(token, board_id, frame.title, frame.x + frame.width / 2,
                                        frame.y + frame.height / 2, frame.width, frame.height)
        fid = made["id"]
        sx, sy, sw, sh = frame.shot
        miro_client.upload_image(token, board_id, stills[frame.filename], frame.filename,
                                 title=frame.title, x=sx + sw / 2, y=sy + sh / 2, width=sw, parent_id=fid)
        items = []
        for st in frame.stickies:
            q = quotes[st.dom_id]
            colour = (SENTIMENT_TOKEN.get(q.sentiment, DEFAULT_QUOTE_TOKEN) if colour_by == "sentiment"
                      else DEFAULT_QUOTE_TOKEN)
            items.append({"type": "sticky_note", "data": {"content": _sticky_html(q), "shape": STICKY_SHAPE},
                          "style": {"fillColor": colour},
                          "position": {"x": st.x + STICKY_W / 2, "y": st.y + STICKY_H / 2},
                          "geometry": {"width": STICKY_W}, "parent": {"id": fid}})
        for i in range(0, len(items), 20):
            miro_client.bulk_create_items(token, board_id, items[i:i + 20])
        job["completed_count"] += 1
        job["progress"] += 1
    job["status"] = "completed"


async def _run_miro(project_id: int, job: dict[str, Any], *args: Any) -> None:
    from bristlenose import miro_client

    try:
        await asyncio.to_thread(_run_miro_sync, job, *args)
        if job["status"] == "running":
            job["status"] = "completed"
    except miro_client.MiroError as exc:
        logger.warning("Screens Miro board failed: %s", exc)
        job["status"] = "failed"
        job["reason"] = exc.reason or ("board_incomplete" if job.get("board_url") else "miro_error")
    except Exception:
        logger.exception("Screens Miro board failed")
        job["status"] = "failed"
        job["reason"] = "board_incomplete" if job.get("board_url") else "miro_error"
    job["current"] = ""


class ScreensMiroStart(BaseModel):
    board_name: str | None = None
    locale: str = "en"
    colour_by: str = "sentiment"


class ScreensMiroStatus(BaseModel):
    status: str
    progress: int
    total: int
    completed_count: int
    skipped_count: int
    current: str
    board_url: str | None
    reason: str | None


@router.post("/projects/{project_id}/export/screens/miro")
async def start_screens_miro(request: Request, project_id: int,
                             body: ScreensMiroStart | None = None) -> ScreensExportStart:
    """Build the screens as a new Miro board: a frame per screen, in journey order, everyone's
    quotes stacked beneath its still by participant."""
    from bristlenose.i18n import t_in
    from bristlenose.screen_text.shots import journey
    from bristlenose.server.export_core import extract_quotes_for_export
    from bristlenose.server.routes.miro import _miro_token
    from bristlenose.utils.timecodes import parse_timecode

    body = body or ScreensMiroStart()
    existing = _miro_jobs.get(project_id)
    if existing and existing.get("status") == "running":
        raise HTTPException(status_code=409, detail="A screens board is already being built")
    token = _miro_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Miro is not connected")
    project_dir = getattr(request.app.state, "project_dir", None)
    if project_dir is None:
        raise HTTPException(status_code=400, detail="No project directory configured")
    if not screens_enabled(request):
        raise HTTPException(status_code=404, detail="Screens are off")
    out_dir = project_output_dir(Path(project_dir))
    db = request.app.state.db_factory()
    try:
        project = db.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        state, owner = derive_project_screens(request, db, project_id)
        screens = journey(state["screens"], owner, _hidden_dom_ids(db, project_id))
        videos = video_sessions(db)
        quotes = {f"q-{q.participant_code}-{int(parse_timecode(q.timecode))}": q
                  for q in extract_quotes_for_export(db, project_id)}
        title = (body.board_name or "").strip() or f"{project.name} · {t_in(body.locale, 'common.screens.title')}"
    finally:
        db.close()
    if not screens:
        return ScreensExportStart(status="no_screens", total=0)
    job: dict[str, Any] = {"status": "running", "progress": 0, "total": len(screens), "completed_count": 0,
                           "skipped_count": 0, "current": "", "board_url": None, "reason": None}
    _miro_jobs[project_id] = job
    job["task"] = asyncio.create_task(_run_miro(
        project_id, job, token, title, out_dir, screens, videos, quotes, body.colour_by))
    return ScreensExportStart(status="started", total=len(screens))


@router.get("/projects/{project_id}/export/screens/miro/status")
async def screens_miro_status(project_id: int) -> ScreensMiroStatus:
    job = _miro_jobs.get(project_id) or {}
    return ScreensMiroStatus(
        status=job.get("status", "idle"), progress=job.get("progress", 0), total=job.get("total", 0),
        completed_count=job.get("completed_count", 0), skipped_count=job.get("skipped_count", 0),
        current=job.get("current", ""), board_url=job.get("board_url"), reason=job.get("reason"),
    )


@router.post("/projects/{project_id}/export/screens/miro/cancel")
async def cancel_screens_miro(project_id: int) -> dict[str, Any]:
    """Stop after the frame being built; a board already begun stays, with what it has."""
    job = _miro_jobs.get(project_id)
    if job is None or job.get("status") != "running":
        raise HTTPException(status_code=404, detail="No screens board being built")
    job["status"] = "cancelled"
    return {"cancelled": True}
