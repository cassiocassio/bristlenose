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
import logging
import os
import platform
import subprocess
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from bristlenose.output_paths import project_output_dir
from bristlenose.screen_text import export_folder
from bristlenose.screen_text.shots import shot_list
from bristlenose.server.export_core import ExportableQuote, extract_quotes_for_export
from bristlenose.server.grounding import quote_dom_id
from bristlenose.server.models import Project, Quote, QuoteState
from bristlenose.server.routes.miro import BoardBuild, build_snapshot
from bristlenose.server.routes.screens import (
    StillError,
    derive_project_screens,
    render_still,
    screens_enabled,
)
from bristlenose.server.scene_strips import video_sessions
from bristlenose.utils.timecodes import parse_timecode

logger = logging.getLogger(__name__)

# `open -R` / `xdg-open` return at once; one that does not must not hold the reveal
# request (and, called from an async handler, the server) open with it.
_REVEAL_TIMEOUT_S = 10.0

router = APIRouter(prefix="/api")

_jobs: dict[int, dict[str, Any]] = {}  # project_id → job state
FOLDER = export_folder.FOLDER
_plain_name = export_folder.plain_name


def _hidden_dom_ids(db: Any, project_id: int) -> set[str]:
    quotes = {q.id: q for q in db.query(Quote).filter_by(project_id=project_id).all()}
    return {
        quote_dom_id(quotes[s.quote_id].participant_id, quotes[s.quote_id].start_timecode,
                     quotes[s.quote_id].ordinal)
        for s in db.query(QuoteState).filter(
            QuoteState.quote_id.in_(quotes), QuoteState.is_hidden.is_(True),
        ).all()
        if s.quote_id in quotes
    }


def _quotes_by_dom_id(db: Any, project_id: int) -> dict[str, ExportableQuote]:
    """Every export row by its quote's DOM id, the key the board's journey names quotes by."""
    return {quote_dom_id(q.participant_code, parse_timecode(q.timecode), q.ordinal): q
            for q in extract_quotes_for_export(db, project_id)}


def _write_inside(folder: Path, name: str, data: bytes) -> None:
    """Write ``data`` as ``folder/name`` without following a link left at that name: a temporary
    file in the folder, then a rename over the name, which replaces a link rather than writing
    through it."""
    if not _plain_name(name):
        raise OSError(f"not a plain file name: {name!r}")
    tmp = folder / f".{name}.{os.getpid()}.tmp"
    tmp.write_bytes(data)
    os.replace(tmp, folder / name)


def _remove_previous_export(folder: Path) -> None:
    """Delete the files the last export's manifest names; anything else in the folder stays."""
    files, _ = export_folder.read_manifest(folder)
    for name in files:
        try:
            (folder / name).unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove earlier still %s", name, exc_info=True)
    (folder / export_folder.MANIFEST_NAME).unlink(missing_ok=True)


async def _run(project_id: int, job: dict[str, Any], out_dir: Path, folder: Path,
               shots: list[dict[str, Any]], videos: dict[str, Path]) -> None:
    written: list[str] = []
    sessions: dict[str, str] = {}
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
                _write_inside(folder, shot["filename"], jpg)
            except (StillError, OSError):
                logger.warning("Skipped still %s", shot["filename"], exc_info=True)
                job["skipped_count"] += 1
            else:
                written.append(shot["filename"])
                sessions[shot["filename"]] = shot["session_id"]
                job["completed_count"] += 1
                try:
                    # As each lands, so a death part-way still names it; with its session, so
                    # removing that interview from the project removes it too.
                    export_folder.write_manifest(folder, written, sessions)
                except OSError:
                    logger.warning("Could not record %s in the manifest", shot["filename"], exc_info=True)
            job["progress"] += 1
        if _jobs.get(project_id) is job:
            export_folder.write_manifest(folder, written, sessions)
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
    #: This export's own id, repeated by every status read (as for clips: a window carrying the
    #: chip across a reload knows by it that the export is still the one it started).
    job_id: str | None = None


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
    #: The export the server holds (``None`` when it holds none).
    job_id: str | None = None


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

    def read() -> tuple[list[dict[str, Any]], dict[str, Path]]:
        db = request.app.state.db_factory()
        try:
            if not db.get(Project, project_id):
                raise HTTPException(status_code=404, detail="Project not found")
            state, owner = derive_project_screens(request, db, project_id)
            return shot_list(state["screens"], owner, _hidden_dom_ids(db, project_id)), video_sessions(db)
        finally:
            db.close()

    # Deriving screens reads every index: off the event loop, which also streams the video.
    shots, videos = await asyncio.to_thread(read)
    if not shots:
        return ScreensExportStart(status="no_screens", total=0)
    folder = out_dir / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    if folder.is_symlink() or not folder.resolve().is_relative_to(out_dir.resolve()):
        raise HTTPException(status_code=409, detail="The screens folder is not inside the output folder")
    job: dict[str, Any] = {"job_id": uuid.uuid4().hex,
                           "status": "running", "progress": 0, "total": len(shots),
                           "completed_count": 0, "skipped_count": 0, "current": "",
                           "output_dir": None, "files": []}
    _jobs[project_id] = job
    # Held by the job: the loop keeps only a weak reference to a bare task.
    job["task"] = asyncio.create_task(_run(project_id, job, out_dir, folder, shots, videos))
    return ScreensExportStart(status="started", total=len(shots), job_id=job["job_id"])


@router.get("/projects/{project_id}/export/screens/status")
async def screens_export_status(project_id: int) -> ScreensExportStatus:
    job = _jobs.get(project_id) or {}
    return ScreensExportStatus(
        status=job.get("status", "idle"), progress=job.get("progress", 0),
        total=job.get("total", 0), completed_count=job.get("completed_count", 0),
        skipped_count=job.get("skipped_count", 0), current=job.get("current", ""),
        output_dir=job.get("output_dir"), files=job.get("files", []),
        job_id=job.get("job_id"),
    )


class ExportCancelRequest(BaseModel):
    #: The export the chip stands for; as for clips, a named cancel stops only that one (RE#38).
    job_id: str | None = None


@router.post("/projects/{project_id}/export/screens/cancel")
async def cancel_screens_export(project_id: int, body: ExportCancelRequest | None = None) -> dict[str, Any]:
    """Stop after the still being written; those already written stay. A cancel naming another
    export than the one held is refused (409): a newer export replaced the chip's."""
    job = _jobs.get(project_id)
    if job is not None and body is not None and body.job_id and body.job_id != job.get("job_id"):
        raise HTTPException(status_code=409, detail="That screens export has been replaced")
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
    files = [folder / f for f in job.get("files", []) if _plain_name(f) and (folder / f).is_file()]
    target = files[0] if files else folder
    system = platform.system()
    if system == "Darwin":
        command = ["open", "-R", str(target)]
    elif system == "Linux":
        command = ["xdg-open", str(folder)]
    else:
        return {"revealed": False, "path": str(folder)}
    # A sandboxed sidecar (the Mac app) may not be allowed to run it: not revealed, not a
    # 500. The app reveals through its own bridge (R72).
    try:
        # Not capture_output: a file manager xdg-open starts can inherit the pipe and
        # hold it open, and the read would wait for it to quit.
        code = subprocess.run(command, check=False, timeout=_REVEAL_TIMEOUT_S).returncode
    except OSError:
        logger.warning("Reveal screens: %s could not be run", command[0], exc_info=True)
        return {"revealed": False, "path": str(target)}
    except subprocess.TimeoutExpired:
        logger.warning("Reveal screens: %s still running after %g s", command[0], _REVEAL_TIMEOUT_S)
        return {"revealed": False, "path": str(target)}
    if code != 0:
        logger.warning("Reveal screens: %s exited %d", command[0], code)
    done = code == 0
    return {"revealed": done, "path": str(target)}


# ---------------------------------------------------------------------------
# The screens as a Miro board — a frame per screen (docs/design-screens-export.md §6)
# ---------------------------------------------------------------------------

_miro_jobs: dict[int, dict[str, Any]] = {}


def _attribution(q: Any) -> str:
    from bristlenose.board_layout import attribution

    return attribution(q.participant_code, parse_timecode(q.timecode))


def _run_miro_sync(job: dict[str, Any], token: str, title: str, out_dir: Path,
                   screens: list[dict[str, Any]], videos: dict[str, Path],
                   quotes: dict[str, Any], colour_by: str, split: bool = True,
                   shape: str = "rectangle",
                   pauses: dict[str, dict[int, float]] | None = None,
                   languages: dict[str, str] | None = None) -> None:
    """Render each screen's still, lay the board out, and build it on Miro. Runs in a worker
    thread; the job dict is its only output. A board left part-built names its link, as the quotes
    board does."""
    from html import escape

    from bristlenose import miro_client
    from bristlenose.board_layout import (
        DEFAULT_QUOTE_TOKEN,
        SENTIMENT_TOKEN,
        fit_miro_sticky,
        quote_parts,
    )
    from bristlenose.board_progress import BoardCancelledError, BoardProgress
    from bristlenose.screens_board import jpeg_size, lay_out_board
    from bristlenose.server.miro_export import batches, group_sets, split_sets

    tracker = job.setdefault("tracker", BoardProgress("screens"))
    tracker.enter("preparing", sum(len(sc["versions"]) for sc in screens))
    stills: dict[str, bytes] = {}
    sizes: dict[str, tuple[int, int]] = {}
    for sc in screens:
        rendered = 0
        for v in sc["versions"]:
            if job["status"] == "cancelled":
                return
            job["current"] = v["filename"]
            video = videos.get(v["session_id"])
            tracker.counted()
            try:
                if video is None:
                    raise StillError("No recording")
                jpg = render_still(out_dir, v["session_id"], video, v["t"], tuple(v["crop"]), None)
            except StillError:
                logger.warning("Skipped still %s", v["filename"], exc_info=True)
                continue
            size = jpeg_size(jpg)
            if size is None:
                logger.warning("Skipped still %s: not a readable JPEG", v["filename"])
                continue
            stills[v["filename"]] = jpg
            sizes[v["filename"]] = size
            rendered += 1
        if not rendered:
            # `total` stays the screens asked for; a screen with no still at all is counted, which
            # both clients say, rather than vanishing with its quotes.
            job["skipped_count"] += 1
    parts = {d: quote_parts(q.text, _attribution(q), split, shape, (pauses or {}).get(d),
                            languages.get(q.session) if languages else None)
             for d, q in quotes.items()}
    frames = lay_out_board(screens, sizes, parts)
    if not frames:
        raise miro_client.MiroError("No screengrab could be made", reason="no_stills")
    # Every call, counted before the first: the board, then per frame the frame, its screengrabs,
    # its sticky batches and a group per split quote.
    tracker.plan({"board": 1, "frame": len(frames),
                  "image": sum(len(f.stills) for f in frames),
                  "bulk": sum(batches(len(f.stickies)) for f in frames),
                  "group": sum(split_sets([st.set_id for st in f.stickies]) for f in frames)})

    def call(kind: str) -> None:
        tracker.call_done(kind)
        if job["status"] == "cancelled":
            raise BoardCancelledError

    with miro_client.observe_waits(tracker.waiting_for):
        tracker.enter("opening")
        board = miro_client.create_board(token, title)
        board_id = board.get("id")
        if not board_id:
            raise miro_client.MiroError("Miro did not return a board id", reason="no_board_id")
        job["board_url"] = board.get("viewLink") or f"https://miro.com/app/board/{board_id}/"
        call("board")
        for frame in frames:
            if job["status"] == "cancelled":
                return
            job["current"] = frame.title
            made = miro_client.create_frame(token, board_id, frame.title, frame.x + frame.width / 2,
                                            frame.y + frame.height / 2, frame.width, frame.height)
            call("frame")
            if tracker.phase == "opening":  # the board takes frames now: the build proper
                tracker.enter("screens", len(frames))
            fid = made["id"]
            front = frame.stills[-1]
            for still in frame.stills:  # back first, so the front one is drawn on top
                try:
                    miro_client.upload_image(token, board_id, stills[still.filename], still.filename,
                                             title=still.title, x=still.x + still.width / 2,
                                             y=still.y + still.height / 2, width=still.width, parent_id=fid)
                except miro_client.MiroError:
                    # A screengrab behind the front one is a choice offered, not the frame: one Miro
                    # refused is left out, as a still that could not be rendered is. The front one
                    # failing still fails the board, which then names its link.
                    if still is front:
                        raise
                    logger.warning("Left out %s: Miro refused the upload", still.filename, exc_info=True)
                    tracker.call_done("image", timed=False)  # a refusal can be a timeout: no rate
                    continue
                call("image")
            items = []
            for st in frame.stickies:
                q = quotes[st.dom_id]
                colour = (SENTIMENT_TOKEN.get(q.sentiment, DEFAULT_QUOTE_TOKEN) if colour_by == "sentiment"
                          else DEFAULT_QUOTE_TOKEN)
                rest = f"<br><i>{escape(_attribution(q))}</i>" if st.attributed else ""
                items.append({"type": "sticky_note",
                              "data": {"content": fit_miro_sticky(st.text, rest), "shape": shape},
                              "style": {"fillColor": colour},
                              "position": {"x": st.x + st.width / 2, "y": st.y + st.height / 2},
                              "geometry": {"width": st.width}, "parent": {"id": fid}})
            made_items: list[dict[str, Any]] = []
            for i in range(0, len(items), 20):
                made_items += miro_client.bulk_create_items(token, board_id, items[i:i + 20])
                call("bulk")
            set_ids = [st.set_id for st in frame.stickies]
            grouped = group_sets(token, board_id, set_ids, made_items, each=lambda: call("group"))
            tracker.unplan("group", split_sets(set_ids) - grouped)
            job["completed_count"] += 1
            job["progress"] += 1
            tracker.counted()
    job["status"] = "completed"


async def _run_miro(project_id: int, job: dict[str, Any], *args: Any) -> None:
    from bristlenose import miro_client
    from bristlenose.board_progress import BoardCancelledError, BoardProgress

    tracker = job.setdefault("tracker", BoardProgress("screens"))
    try:
        await asyncio.to_thread(_run_miro_sync, job, *args)
        if job["status"] == "running":
            job["status"] = "completed"
    except BoardCancelledError:
        pass  # the status already says cancelled; the board keeps what it has
    except miro_client.MiroError as exc:
        logger.warning("Screens Miro board failed: %s", exc)
        if job["status"] != "cancelled":  # a cancel stays a cancel, whatever the call in hand did
            job["status"] = "failed"
            # As the quotes board, in the same order: once the board exists, any failure is
            # board_incomplete with its link (miro_export wraps post-creation errors that way);
            # before it, a refused token is named rather than shown as "check your connection".
            # Anything else unnamed reads as the clients' generic export error.
            job["reason"] = exc.reason or (
                "board_incomplete" if job.get("board_url")
                else "token_rejected" if exc.status in (401, 403) else None)
    except Exception:
        logger.exception("Screens Miro board failed")
        if job["status"] != "cancelled":
            job["status"] = "failed"
            job["reason"] = "board_incomplete" if job.get("board_url") else None
    job["current"] = ""
    tracker.log_summary(job["status"])
    await asyncio.to_thread(tracker.remember)


class ScreensMiroStart(BaseModel):
    board_name: str | None = None
    locale: str = "en"
    colour_by: str = "none"
    #: Break a long quote into up to three grouped stickies, as on the quotes board.
    split_long_quotes: bool = True
    sticky_shape: Literal["rectangle", "square"] = "rectangle"


class ScreensMiroStatus(BaseModel):
    status: str
    progress: int
    total: int
    completed_count: int
    skipped_count: int
    current: str
    board_url: str | None
    reason: str | None
    #: How far the build has got (the quotes board's shape): screengrabs prepared, then the board
    #: opening, then screens added, with a fraction of its Miro calls and an earned estimate.
    build: BoardBuild | None = None


# `response_model` explicitly: the annotation admits the not-connected refusal's JSONResponse.
@router.post("/projects/{project_id}/export/screens/miro", response_model=ScreensExportStart)
async def start_screens_miro(request: Request, project_id: int,
                             body: ScreensMiroStart | None = None) -> ScreensExportStart | JSONResponse:
    """Build the screens as a new Miro board: a frame per screen, in journey order, everyone's
    quotes stacked beneath its still by participant."""
    from bristlenose.i18n import t_in
    from bristlenose.screen_text.shots import journey
    from bristlenose.server.export_core import project_display_name
    from bristlenose.server.miro_export import load_pauses, session_languages
    from bristlenose.server.routes.miro import _miro_token

    body = body or ScreensMiroStart()
    existing = _miro_jobs.get(project_id)
    if existing and existing.get("status") == "running":
        raise HTTPException(status_code=409, detail="A screens board is already being built")
    # A cancelled build finishes the frame in hand, which can take a minute of retries; a second
    # build meanwhile would share the token's rate limit with it.
    task = existing.get("task") if existing else None
    if task is not None and not task.done():
        raise HTTPException(status_code=409, detail="The last screens board is still stopping")
    token = _miro_token(request)
    if not token:
        # The quotes board's reason, so both clients say it in the reader's language (R94).
        return JSONResponse(status_code=401, content={
            "detail": "Miro is not connected", "reason": "not_connected", "vars": {}})
    project_dir = getattr(request.app.state, "project_dir", None)
    if project_dir is None:
        raise HTTPException(status_code=400, detail="No project directory configured")
    if not screens_enabled(request):
        raise HTTPException(status_code=404, detail="Screens are off")
    out_dir = project_output_dir(Path(project_dir))
    locale, board_name = body.locale, body.board_name

    def read() -> tuple[list[dict[str, Any]], dict[str, Path], dict[str, Any], str,
                        dict[str, dict[int, float]], dict[str, str]]:
        db = request.app.state.db_factory()
        try:
            project = db.get(Project, project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            state, owner = derive_project_screens(request, db, project_id)
            quotes = _quotes_by_dom_id(db, project_id)
            timed = load_pauses(db, project_id, list(quotes.values()))
            pauses = {d: timed[q.quote_id] for d, q in quotes.items() if q.quote_id in timed}
            title = ((board_name or "").strip()
                     or f"{project_display_name(project)} · {t_in(locale, 'common.screens.title')}")
            return (journey(state["screens"], owner, _hidden_dom_ids(db, project_id)), video_sessions(db),
                    quotes, title, pauses, session_languages(db, project_id))
        finally:
            db.close()

    screens, videos, quotes, title, pauses, languages = await asyncio.to_thread(read)
    if not screens:
        return ScreensExportStart(status="no_screens", total=0)
    from bristlenose.board_progress import BoardProgress, default_history_dir

    job: dict[str, Any] = {"status": "running", "progress": 0, "total": len(screens), "completed_count": 0,
                           "skipped_count": 0, "current": "", "board_url": None, "reason": None,
                           "tracker": BoardProgress("screens", history_dir=default_history_dir())}
    _miro_jobs[project_id] = job
    job["task"] = asyncio.create_task(_run_miro(
        project_id, job, token, title, out_dir, screens, videos, quotes, body.colour_by,
        body.split_long_quotes, body.sticky_shape, pauses, languages))
    return ScreensExportStart(status="started", total=len(screens))


@router.get("/projects/{project_id}/export/screens/miro/status")
async def screens_miro_status(project_id: int) -> ScreensMiroStatus:
    job = _miro_jobs.get(project_id) or {}
    return ScreensMiroStatus(
        status=job.get("status", "idle"), progress=job.get("progress", 0), total=job.get("total", 0),
        completed_count=job.get("completed_count", 0), skipped_count=job.get("skipped_count", 0),
        current=job.get("current", ""), board_url=job.get("board_url"), reason=job.get("reason"),
        build=build_snapshot(job),
    )


@router.post("/projects/{project_id}/export/screens/miro/cancel")
async def cancel_screens_miro(project_id: int) -> dict[str, Any]:
    """Stop after the frame being built; a board already begun stays, with what it has."""
    job = _miro_jobs.get(project_id)
    if job is None or job.get("status") != "running":
        raise HTTPException(status_code=404, detail="No screens board being built")
    job["status"] = "cancelled"
    return {"cancelled": True}
