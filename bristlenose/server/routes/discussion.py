"""Discussion lens — the stage's record, as the researcher's report shows it.

Read from ``.bristlenose/intermediate/discussion.json``, which the pipeline's
Discussion stage writes (``bristlenose/discussion/stage.py``). No tables yet:
they arrive with researcher overrides (plan §2.1), and until then the record is
the whole truth. Two things are layered on at serve time, so this lens never
disagrees with the Quotes lens about a quote: a hidden quote is left out, and
an edited quote shows its edit.

The payload carries speaker codes, never names (plan §9.C): the SPA resolves
names from ``/sessions``, which an anonymised export already blanks.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose.server.models import Project, Quote, QuoteEdit, QuoteState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# not_run: no record (the stage has not run, or is switched off).
# stale:   a record built from other quotes — re-analyse to rebuild it.
# ready / partial / failed: the record's own status.
DiscussionStatus = Literal["not_run", "stale", "ready", "partial", "failed"]


class DiscussionResponse(BaseModel):
    status: DiscussionStatus
    record: dict[str, Any] | None = None


def _output_dir(project_dir: Path) -> Path:
    # Mirrors app.py's own resolution: a project folder or its output folder.
    out = project_dir / "bristlenose-output"
    return out if out.is_dir() else project_dir


def _current_quotes_sha(intermediate: Path) -> str | None:
    """The hash the stage would compute from the quotes now on disk, or None
    when they cannot be read (then staleness is not claimed either way)."""
    from bristlenose.discussion.stage import quotes_sha
    from bristlenose.models import ExtractedQuote

    path = intermediate / "extracted_quotes.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return quotes_sha([ExtractedQuote.model_validate(q) for q in raw])
    except (OSError, ValueError):
        return None


def _quote_overlay(db: Session, project_id: int) -> dict[tuple[str, str, float], tuple[bool, str]]:
    """(session, participant, start rounded to 0.01 s) → (hidden, current text)."""
    rows = db.query(Quote).filter_by(project_id=project_id).all()
    hidden = {s.quote_id for s in db.query(QuoteState).join(Quote, QuoteState.quote_id == Quote.id)
              .filter(Quote.project_id == project_id, QuoteState.is_hidden).all()}
    edited: dict[int, str] = {}
    for e in (db.query(QuoteEdit).join(Quote, QuoteEdit.quote_id == Quote.id)
              .filter(Quote.project_id == project_id).order_by(QuoteEdit.edited_at).all()):
        edited[e.quote_id] = e.edited_text  # the latest edit wins
    return {
        (q.session_id, q.participant_id, round(q.start_timecode, 2)):
            (q.id in hidden, edited.get(q.id, q.text))
        for q in rows
    }


def get_discussion_payload(db: Session, project_id: int, project_dir: Path | None) -> DiscussionResponse:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project_dir is None:
        return DiscussionResponse(status="not_run")
    intermediate = _output_dir(project_dir) / ".bristlenose" / "intermediate"
    try:
        record: dict[str, Any] = json.loads(
            (intermediate / "discussion.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return DiscussionResponse(status="not_run")
    except (OSError, ValueError) as exc:
        logger.warning("discussion record unreadable: %s", type(exc).__name__)
        return DiscussionResponse(status="not_run")

    current = _current_quotes_sha(intermediate)
    if current is not None and record.get("quotes_sha") and record["quotes_sha"] != current:
        return DiscussionResponse(status="stale")

    overlay = _quote_overlay(db, project_id)
    shown: list[dict[str, Any]] = []
    for q in record.get("quotes", []):
        key = (q.get("session", ""), q.get("participant", ""), round(float(q.get("sec", 0.0)), 2))
        state = overlay.get(key)
        if state is not None:
            is_hidden, text = state
            if is_hidden:
                continue
            q["text"] = text
        shown.append(q)
    record["quotes"] = shown

    raw_status = record.get("status", "complete")
    status: DiscussionStatus = (
        "ready" if raw_status == "complete" else "partial" if raw_status == "partial" else "failed")
    return DiscussionResponse(status=status, record=record)


@router.get("/projects/{project_id}/discussion", response_model=DiscussionResponse)
def get_discussion(project_id: int, request: Request) -> DiscussionResponse:
    db: Session = request.app.state.db_factory()
    try:
        return get_discussion_payload(db, project_id, request.app.state.project_dir)
    finally:
        db.close()
