"""FigJam board download — the file the Bristlenose FigJam plugin opens.

FigJam has no server write path, so this is a download rather than a push:
the researcher saves the file, runs the plugin in a FigJam board and picks it
(`docs/design-board-integrations.md`, F1–F3). No credential is involved, so
unlike `routes/miro.py` there is nothing to connect.

Shaped like its sibling, the quotes CSV (`routes/quotes_export.py`): a GET
under `/export/`, scope as comma-separated DOM ids, the board's language as
`lang`. Server-only in the HTML export (`routes/export.py`).
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.responses import Response

from bristlenose.board_manifest import FIGJAM_STICKY_SHAPE, to_json
from bristlenose.i18n import canonical_locale
from bristlenose.server import miro_export
from bristlenose.server.export_core import (
    attachment_disposition,
    parse_quote_ids,
    project_display_name,
)
from bristlenose.server.models import Project
from bristlenose.utils.text import safe_filename

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _get_db(request: Request) -> Session:
    db: Session = request.app.state.db_factory()
    return db


def _check_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _refusal(status: int, detail: str, reason: str) -> JSONResponse:
    """`detail` is English for the log; `reason` is what the clients translate."""
    return JSONResponse(status_code=status, content={"detail": detail, "reason": reason})


@router.get("/projects/{project_id}/export/figjam-board.json")
def export_figjam_board(
    request: Request,
    project_id: int,
    quote_ids: str | None = Query(None, description="Comma-separated DOM IDs"),
    lang: str = Query("en", description="The board's language (the caller's UI locale)"),
    clips_base: str = Query("", description="Opt-in http(s) folder of exported clips"),
    split_long_quotes: bool = Query(True, description="Long quotes as two or three stickies"),
    sticky_shape: Literal["square", "rectangle"] = Query(
        FIGJAM_STICKY_SHAPE, description="Square by default on FigJam"),
    board_name: str = Query("", max_length=200,
                            description="The board's name; the project's when empty"),
) -> Response:
    """The project's (optionally scoped) quotes as a FigJam board document."""
    # One normalised code for the words, the document's `locale` and the log,
    # so none of them can disagree with the others or carry a raw query value.
    locale = canonical_locale(lang)
    if clips_base and not miro_export.clips_base_ok(clips_base):
        # Asked for links and would silently get none: say so instead.
        return _refusal(400, "clips_base must be an http(s) folder", "clips_base_not_http")
    db = _get_db(request)
    try:
        project = _check_project(db, project_id)
        # The dialog arrives filled with the project's name, and the researcher
        # may change it; an empty one still falls back, as the Miro export does.
        name = board_name.strip() or project_display_name(project)
        manifest = miro_export.build_figjam_manifest(
            db, project_id, name, parse_quote_ids(quote_ids),
            clips_base=clips_base, locale=locale, split=split_long_quotes,
            sticky_shape=sticky_shape,
        )
        n = sum(len(c["quotes"]) for f in manifest["frames"] for c in f["columns"])
        if n == 0:
            # The reason both clients already localise for the Miro export.
            return _refusal(404, "No quotes match the filter", "no_quotes_selected")
        logger.info("figjam_board_export quotes=%d locale=%s", n, locale)
        return Response(
            content=to_json(manifest),
            media_type="application/json",
            headers={
                "Content-Disposition": attachment_disposition(
                    f"{safe_filename(name)}-figjam-board.json"
                ),
                # Participant quotes, never sniffed as anything else. (Every
                # /api response is already no-store, from create_app.)
                "X-Content-Type-Options": "nosniff",
            },
        )
    finally:
        db.close()
