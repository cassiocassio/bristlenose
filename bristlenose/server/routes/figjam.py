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

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from bristlenose.board_manifest import to_json
from bristlenose.server import miro_export
from bristlenose.server.export_core import attachment_disposition
from bristlenose.server.routes.miro import _check_project, _get_db, _project_name
from bristlenose.server.routes.quotes_export import _parse_quote_ids
from bristlenose.utils.text import safe_filename

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/projects/{project_id}/export/figjam-board.json")
def export_figjam_board(
    request: Request,
    project_id: int,
    quote_ids: str | None = Query(None, description="Comma-separated DOM IDs"),
    lang: str = Query("en", description="The board's language (the caller's UI locale)"),
    clips_base: str = Query("", description="Opt-in http(s) folder of exported clips"),
) -> Response:
    """The project's (optionally scoped) quotes as a FigJam board document."""
    db = _get_db(request)
    try:
        project = _check_project(db, project_id)
        name = _project_name(project)
        manifest = miro_export.build_figjam_manifest(
            db, project_id, name, _parse_quote_ids(quote_ids),
            clips_base=clips_base, locale=lang,
        )
        n = sum(len(c["quotes"]) for f in manifest["frames"] for c in f["columns"])
        if n == 0:
            # The reason both clients already localise for the Miro export.
            return JSONResponse(
                status_code=404,
                content={"detail": "No quotes match the filter",
                         "reason": "no_quotes_selected"},
            )
        logger.info("figjam_board_export quotes=%d locale=%s", n, manifest["locale"])
        return Response(
            content=to_json(manifest),
            media_type="application/json",
            headers={
                "Content-Disposition": attachment_disposition(
                    f"{safe_filename(name)}-figjam-board.json"
                ),
            },
        )
    finally:
        db.close()
