"""Whether a session is owed a re-analysis after a recode (§J7 R3).

A recode is held on the slot and re-analyses nothing (R1, R2). When it moves a
speaker into or out of participant, the session's evidence is wrong: its quotes
were extracted from the wrong speaker, and only the pipeline can extract the
right ones. Since 23 Oct 2026 that is the ordinary Analyse, not a per-session
act: the recode itself writes **role pins** into the session registry
(``routes/data.py`` ``sync_role_pins``), and the next run — the Mac's Analyse,
or ``bristlenose run`` — honours them before codes are assigned, so only this
session's topics and quotes are extracted again (the transcript changed, so its
caches miss) while sections, themes and the Discussion guide are rebuilt for
the whole study, since the evidence they group changed. The importer then
carries each pick to the speaker's new code.

``GET`` says whether a session is owed one, and what the run is likely to cost.
``needs_reanalysis`` is the predicate; the Mac counts owed sessions with the
same rule in SQL (``SourceFilesReader.swift``, held to this one by
``tests/test_swift_python_contract.py``).
"""

from __future__ import annotations

import logging
import shlex
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose.server import speaker_slots
from bristlenose.server.models import Project

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


class ReanalyseInfo(BaseModel):
    #: A speaker here was recoded into or out of participant, and the run that
    #: would extract the right quotes has not happened.
    needed: bool
    #: What the run is likely to cost in US dollars, from this machine's own
    #: history or the shipped baselines; null when nothing can say.
    cost_usd: float | None = None
    #: A pipeline run owns the project now; a recode (which writes the pins) is
    #: refused until it ends.
    running: bool = False
    #: The command that runs it, for a researcher outside the Mac app.
    command: str


def _project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _command(project: Project) -> str:
    return f"bristlenose run {shlex.quote(project.input_dir)}"


def needs_reanalysis(slot: speaker_slots.Slot) -> bool:
    """A slot whose speaker moved into or out of participant (R2): its role and
    its tag disagree on that line. Moderator ↔ observer never needs it (call 1)."""
    return (slot.slot_code[:1] == "p") != (speaker_slots.kind_prefix(slot.row) == "p")


def _cost(request: Request, project: Project) -> float | None:
    try:
        from bristlenose.config import load_settings
        from bristlenose.llm.pricing import estimate_pipeline_cost

        settings = getattr(request.app.state, "settings", None) or load_settings()
        run_dir = Path(project.output_dir) / ".bristlenose"
        return estimate_pipeline_cost(settings.llm_model, 1, run_dir)
    except Exception:  # an estimate never blocks the act — but say why it is missing
        logger.warning("Could not estimate a session re-analysis's cost", exc_info=True)
        return None


@router.get("/projects/{project_id}/sessions/{session_id}/reanalyse", response_model=ReanalyseInfo)
def get_reanalyse(project_id: int, session_id: str, request: Request) -> ReanalyseInfo:
    from bristlenose.run_lifecycle import run_in_progress

    db: Session = request.app.state.db_factory()
    try:
        project = _project(db, project_id)
        slots = speaker_slots.session_slots(db, project_id, session_id)
        needed = any(needs_reanalysis(s) for s in slots)
        return ReanalyseInfo(
            needed=needed,
            cost_usd=_cost(request, project) if needed else None,
            running=run_in_progress(Path(project.output_dir)),
            command=_command(project),
        )
    finally:
        db.close()
