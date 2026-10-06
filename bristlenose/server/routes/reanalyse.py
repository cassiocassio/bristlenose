"""Re-analyse one session after a recode into or out of participant (§J7 R3).

A recode is held on the slot and re-analyses nothing (R1, R2). When it moves a
speaker into or out of participant, the session's evidence is wrong: its quotes
were extracted from the wrong speaker, and only the pipeline can extract the
right ones. That is paid, so it is the researcher's act, behind a confirm.

``POST`` writes **role pins** into the session registry (``SessionRegistry.pins``):
per speaker label, the role the researcher set, the turns it was set on, and the
person their pick pointed at. The next run — the Mac's Analyse, or
``bristlenose run`` — honours them before codes are assigned, so only this
session's topics and quotes are extracted again (the transcript changed, so its
caches miss) while sections, themes and the Discussion guide are rebuilt for
the whole study, since the evidence they group changed. The importer then
carries each pick to the speaker's new code.

``GET`` says whether a session needs it, and what it would cost.
"""

from __future__ import annotations

import shlex
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose.server import speaker_slots
from bristlenose.server.models import Project, TranscriptSegment
from bristlenose.server.models import Session as SessionModel

router = APIRouter(prefix="/api")


class ReanalyseInfo(BaseModel):
    #: A speaker here was recoded into or out of participant, and the run that
    #: would extract the right quotes has not happened.
    needed: bool
    #: What the run is likely to cost in US dollars, from this machine's own
    #: history or the shipped baselines; null when nothing can say.
    cost_usd: float | None = None
    #: A pipeline run owns the project now; pins cannot be written until it ends.
    running: bool = False
    #: The command that runs it, for a researcher outside the Mac app.
    command: str


class ReanalyseResult(BaseModel):
    pinned: int
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
    except Exception:  # an estimate never blocks the act; it is just not shown
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


@router.post("/projects/{project_id}/sessions/{session_id}/reanalyse",
             response_model=ReanalyseResult)
def post_reanalyse(project_id: int, session_id: str, request: Request) -> ReanalyseResult:
    """Pin this session's speakers as the researcher has them, for the next run.

    Every slot recoded into or out of participant is pinned; a pin whose
    speaker has since been recoded back is taken away, so a run never applies
    a role the researcher no longer holds. 409 while a run owns the project.
    """
    from bristlenose.run_lifecycle import run_in_progress
    from bristlenose.session_registry import RolePin, SessionRegistry, pin_starts

    db: Session = request.app.state.db_factory()
    try:
        project = _project(db, project_id)
        output_dir = Path(project.output_dir)
        if run_in_progress(output_dir):
            raise HTTPException(status_code=409, detail="An analysis is running")
        session = (
            db.query(SessionModel).filter_by(project_id=project_id, session_id=session_id).first()
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        try:
            registry = SessionRegistry.load(output_dir)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        pinned = 0
        for slot in speaker_slots.session_slots(db, project_id, session_id):
            label = registry.label_for(session_id, slot.slot_code)
            if label is None:
                continue
            held = registry.pins.get(session_id, {}).get(label)
            if needs_reanalysis(slot):
                starts = [
                    t for (t,) in db.query(TranscriptSegment.start_time).filter_by(
                        session_id=session.id, speaker_code=slot.slot_code,
                    )
                ]
                if not starts:
                    continue
                registry.pin(session_id, label, RolePin(
                    role=slot.row.speaker_role, starts=pin_starts(starts),
                    from_code=slot.slot_code,
                    person=slot.person.uuid if slot.person is not None else "",
                ))
                pinned += 1
            elif held is not None and held.role != slot.row.speaker_role:
                del registry.pins[session_id][label]
        if pinned == 0:
            raise HTTPException(status_code=409, detail="Nothing here needs re-analysing")
        registry.save()
        return ReanalyseResult(pinned=pinned, command=_command(project))
    finally:
        db.close()
