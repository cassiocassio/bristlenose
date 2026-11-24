"""The tag sidebar's AutoCode overview: what it draws and what it remembers.

docs/design-autocode-landing-plan.md Phase 6 (D12, D17, D22). The overview is a small
confidence chart at the top of the tag sidebar, over every codebook a researcher can
review: one with an AutoCode run, never Sentiment (machine-applied on every run, never
reviewed) and never the researcher's own tags (they have no run).

``GET`` answers, in one read, the remembered state (open, split, and whether it has
opened by itself yet) and, for each reviewable codebook, its proposals in 20 bands of
0.05 split by where each one sits now, the lines it was last cut at, and whether its
first apply is still coding (Review is inactive then, D17; the server refuses it, D49).
``PATCH`` remembers what the researcher changed, naming only that.

Server-only in an export (``routes/export.py``): proposals never leave the server
there, and the exported sidebar shows the summary line alone.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from bristlenose.server.autocode import first_apply_ending
from bristlenose.server.models import AutoCodeJob, Project, TagOverviewState
from bristlenose.server.routes.autocode import (
    ConfidenceBin,
    _counted_quote_ids,
    confidence_counts,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

#: Machine-applied on every run and never reviewed (owner, 23 Nov 2026): not on the overview.
_NOT_REVIEWABLE = frozenset({"sentiment"})


class OverviewCodebook(BaseModel):
    framework_id: str
    #: The first apply is coding or settling: Review is inactive (D17, D49). A catch-up on
    #: an applied codebook is not (D20).
    coding: bool
    #: The lines the run was last cut at; None before any cut.
    lower: float | None
    upper: float | None
    #: A first apply's live accept line (D47, D50): the upper tick while the run codes and
    #: before its cut stores the lines. None before its first batch is saved.
    live_accept_line: float | None
    bins: list[ConfidenceBin]


class TagOverviewOut(BaseModel):
    open: bool
    split: bool
    #: The overview has opened by itself once, after a first run (D12): it never does again.
    auto_opened: bool
    codebooks: list[OverviewCodebook]


class TagOverviewPatch(BaseModel):
    """What the researcher changed: only the fields named are written."""

    model_config = ConfigDict(extra="forbid")

    open: bool | None = None
    split: bool | None = None
    auto_opened: bool | None = None


def _get_db(request: Request) -> Session:
    db: Session = request.app.state.db_factory()
    return db


def _check_project(db: Session, project_id: int) -> None:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


def _coding(job: AutoCodeJob) -> bool:
    """As the Review refusal reads it (``routes/autocode._refuse_while_first_apply_codes``)."""
    return job.completed_at is None and (
        job.status in ("pending", "running")
        or first_apply_ending(job.project_id, job.framework_id)
    )


@router.get(
    "/projects/{project_id}/tag-overview",
    response_model=TagOverviewOut,
)
def get_tag_overview(project_id: int, request: Request) -> TagOverviewOut:
    """The overview's remembered state and, per reviewable codebook, its chart."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        state = db.query(TagOverviewState).filter_by(project_id=project_id).first()
        jobs = (
            db.query(AutoCodeJob)
            .filter(AutoCodeJob.project_id == project_id)
            .order_by(AutoCodeJob.started_at)
            .all()
        )
        codebooks = []
        # Worked out once for every job this read lists.
        counted = _counted_quote_ids(db, project_id)
        for job in jobs:
            if job.framework_id in _NOT_REVIEWABLE:
                continue
            bins = confidence_counts(db, project_id, job.id, counted)
            coding = _coding(job)
            # A run that ended with nothing to show (a failure before any batch answered)
            # has nothing to review; one still coding is on the line, Review inactive.
            if not coding and not any(b.accepted or b.tentative or b.excluded for b in bins):
                continue
            codebooks.append(
                OverviewCodebook(
                    framework_id=job.framework_id,
                    coding=coding,
                    lower=job.applied_lower_threshold,
                    upper=job.applied_upper_threshold,
                    live_accept_line=job.live_accept_line,
                    bins=bins,
                )
            )
        return TagOverviewOut(
            open=bool(state and state.open),
            split=bool(state and state.split),
            auto_opened=bool(state and state.auto_opened),
            codebooks=codebooks,
        )
    finally:
        db.close()


@router.patch("/projects/{project_id}/tag-overview")
def patch_tag_overview(
    project_id: int, request: Request, data: TagOverviewPatch
) -> dict[str, str]:
    """Remember the fields named (open, split, auto_opened), and no others.

    The row is made with an insert that yields to one already there, then updated, so
    two windows writing a study's first state at once both land (no unique-index refusal).
    """
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        db.execute(
            sqlite_insert(TagOverviewState)
            .values(project_id=project_id)
            .on_conflict_do_nothing(index_elements=["project_id"])
        )
        values: dict[Any, Any] = {
            name: getattr(data, name)
            for name in ("open", "split", "auto_opened")
            if getattr(data, name) is not None
        }
        values["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
        db.query(TagOverviewState).filter_by(project_id=project_id).update(
            values, synchronize_session=False
        )
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()
