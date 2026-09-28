"""Pipeline-run readiness endpoint.

Exposes the most recent ``run_completed`` for a project, populated by
``event_watcher`` AFTER the post-completion SQLite re-import finishes.
The SPA polls this endpoint and refetches its content stores when the
``run_id`` changes — see ``frontend/src/contexts/LastRunStore.ts``.

Response shape is intentionally minimal — the events log is sibling to
PII / LLM-call re-identification keys; only what the SPA needs to keep
itself in sync is exposed.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from bristlenose.server.models import Project
from bristlenose.server.models import Session as SessionModel  # noqa: F401

router = APIRouter(prefix="/api")


class LastRunResponse(BaseModel):
    """The DATA VERSION: the run whose import the database holds. Pinned: do not extend.

    Set only after a successful re-import (or seeded from the report at
    startup). It is not "the latest run" — that is ``/condition`` — and a failed
    or running re-run never moves it.
    """

    run_id: str
    outcome: str
    completed_at: str


@router.get(
    "/projects/{project_id}/last-run",
    response_model=LastRunResponse | None,
)
def get_last_run(
    project_id: int,
    request: Request,
) -> LastRunResponse | None:
    """Return the latest ``run_completed`` info, or ``null`` if none yet."""
    db = request.app.state.db_factory()
    try:
        if not db.get(Project, project_id):
            raise HTTPException(status_code=404, detail="Project not found")
    finally:
        db.close()

    last_run = getattr(request.app.state, "last_run", {}) or {}
    entry = last_run.get(project_id)
    if entry is None:
        return None
    return LastRunResponse(**entry)


class ConditionResponse(BaseModel):
    """What the project is doing — the reducer's answer plus server-only facts.

    ``condition`` is ``bristlenose.run_condition.Condition.to_wire()``: the same
    shape the shared fixture pins, so the SPA and the Mac read one vocabulary.
    ``importing`` / ``import_failed_run_id`` are the server's overlay: facts the
    events log cannot carry because only this process knows them.
    ``/last-run`` stays the data version — do not fold this into it.
    """

    condition: dict[str, Any]
    importing: str | None = None
    import_failed_run_id: str | None = None
    policy: str


@router.get(
    "/projects/{project_id}/condition",
    response_model=ConditionResponse,
)
def get_condition(project_id: int, request: Request) -> ConditionResponse:
    """The project's condition, as the status page and banner see it."""
    from bristlenose.output_paths import project_output_dir
    from bristlenose.server.status_page import policy_from_env

    db = request.app.state.db_factory()
    try:
        if not db.get(Project, project_id):
            raise HTTPException(status_code=404, detail="Project not found")
    finally:
        db.close()

    state = request.app.state
    project_dir = getattr(state, "project_dir", None)
    if project_dir is None:
        raise HTTPException(status_code=404, detail="No project directory")
    from bristlenose.server.app import current_condition

    condition = current_condition(request.app, project_output_dir(project_dir))
    overlay = getattr(state, "import_overlay", None) or {}
    return ConditionResponse(
        condition=condition.to_wire(),
        importing=overlay.get("importing"),
        import_failed_run_id=overlay.get("failed_run_id"),
        policy=policy_from_env().value,
    )
