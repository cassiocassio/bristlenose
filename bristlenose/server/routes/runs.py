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

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from bristlenose.server.models import Project
from bristlenose.server.models import Session as SessionModel  # noqa: F401

router = APIRouter(prefix="/api")


class LastRunResponse(BaseModel):
    """Most recent terminal run for a project. Pinned: do not extend."""

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
