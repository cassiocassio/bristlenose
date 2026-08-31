"""AutoCode API endpoints — start jobs, poll status, review proposals."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose.config import load_settings
from bristlenose.server.autocode import run_autocode_job
from bristlenose.server.codebook import get_template
from bristlenose.server.models import (
    AutoCodeJob,
    CodebookGroup,
    Project,
    ProposedTag,
    Quote,
    QuoteTag,
    TagDefinition,
)
from bristlenose.server.refusal import RefusalError, RefusalReason

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Strong references to in-flight AutoCode tasks. The event loop only weakly
# references a bare ``create_task`` result, so a suspended one can be GC'd
# mid-flight — stranding the job "running" (its finally never runs). Mirrors
# ``_CATCH_UP_TASKS`` in routes/data.py. Discard on completion.
_AUTOCODE_TASKS: set = set()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class AutoCodeJobOut(BaseModel):
    id: int
    framework_id: str
    status: str
    total_quotes: int
    processed_quotes: int
    proposed_count: int
    error_message: str
    #: ``LLMFailureKind`` value, or "" when the job did not fail or the
    #: classifier declined to name it. The UI localises from this; it must never
    #: display ``error_message``, which is raw exception text written for a log.
    failure_kind: str = ""
    llm_provider: str
    llm_model: str
    #: The cutoffs the researcher actually applied, or None before any apply.
    #: Stored on the job since it was written; exposed so the review modal can
    #: draw the thresholds that were used rather than resetting to its own
    #: defaults and describing a run that never happened.
    applied_lower_threshold: float | None = None
    applied_upper_threshold: float | None = None
    input_tokens: int
    output_tokens: int
    started_at: str
    completed_at: str | None


class ProposedTagOut(BaseModel):
    id: int
    quote_id: int
    dom_id: str
    session_id: str
    speaker_code: str
    start_timecode: float
    quote_text: str
    tag_definition_id: int
    tag_name: str
    group_name: str
    colour_set: str
    colour_index: int
    confidence: float
    rationale: str
    status: str


class ProposalsResponse(BaseModel):
    proposals: list[ProposedTagOut]
    total: int


class BulkActionRequest(BaseModel):
    group_id: int | None = None
    min_confidence: float = 0.5
    max_confidence: float | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db(request: Request) -> Session:
    return request.app.state.db_factory()


def _check_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_job(db: Session, project_id: int, framework_id: str) -> AutoCodeJob:
    job = (
        db.query(AutoCodeJob)
        .filter_by(project_id=project_id, framework_id=framework_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="AutoCode job not found")
    return job


def _job_to_out(job: AutoCodeJob) -> AutoCodeJobOut:
    return AutoCodeJobOut(
        id=job.id,
        framework_id=job.framework_id,
        status=job.status,
        total_quotes=job.total_quotes,
        processed_quotes=job.processed_quotes,
        proposed_count=job.proposed_count,
        error_message=job.error_message,
        failure_kind=job.failure_kind,
        llm_provider=job.llm_provider,
        llm_model=job.llm_model,
        applied_lower_threshold=job.applied_lower_threshold,
        applied_upper_threshold=job.applied_upper_threshold,
        input_tokens=job.input_tokens,
        output_tokens=job.output_tokens,
        started_at=job.started_at.isoformat() if job.started_at else "",
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


def _has_api_key(settings: object) -> bool:
    """Check if the configured LLM provider has an API key set."""
    provider = getattr(settings, "llm_provider", "")
    if provider == "anthropic":
        return bool(getattr(settings, "anthropic_api_key", ""))
    if provider == "openai":
        return bool(getattr(settings, "openai_api_key", ""))
    if provider == "azure":
        return bool(getattr(settings, "azure_api_key", ""))
    if provider == "google":
        return bool(getattr(settings, "google_api_key", ""))
    return False


# ---------------------------------------------------------------------------
# POST /projects/{id}/autocode/{framework_id} — start job
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/autocode/{framework_id}")
async def start_autocode_job(
    project_id: int,
    framework_id: str,
    request: Request,
) -> AutoCodeJobOut:
    """Start an AutoCode job for the given project and framework.

    Guards:
    - 404 if project not found
    - 400 if framework template not found
    - 400 if project has no quotes
    - 409 if job already exists for this framework
    - 503 if LLM provider is "local" (Ollama can't fit taxonomy)
    - 503 if no API key configured
    """

    db = _get_db(request)
    try:
        _check_project(db, project_id)

        # Check template exists
        template = get_template(framework_id)
        if not template:
            raise RefusalError(
                400,
                RefusalReason.TEMPLATE_MISSING,
                f"Framework template '{framework_id}' not found",
            )

        # Check for an existing job. A *cancelled* or *failed* job produced no
        # usable result, so it must not permanently block a retry — otherwise the
        # Apply button stays enabled (acDisabled only covers running/completed) yet
        # every click 409s and the frontend swallows it, so the button "does
        # nothing". Clear the dead job below and let a fresh run proceed. A
        # pending/running job is genuinely in flight, and a completed job has
        # results (the UI morphs to "View Report") — both keep the 409.
        existing = (
            db.query(AutoCodeJob)
            .filter_by(project_id=project_id, framework_id=framework_id)
            .first()
        )
        if existing and existing.status in ("pending", "running"):
            raise RefusalError(
                409,
                RefusalReason.ALREADY_RUNNING,
                f"AutoCode is already running for framework '{framework_id}'",
            )
        if existing and existing.status == "completed":
            raise RefusalError(
                409,
                RefusalReason.ALREADY_APPLIED,
                f"AutoCode already run for framework '{framework_id}'",
            )

        # Check project has quotes
        quote_count = db.query(Quote).filter_by(project_id=project_id).count()
        if quote_count == 0:
            raise RefusalError(
                400, RefusalReason.NO_QUOTES, "Project has no quotes to tag"
            )

        # Load settings and check provider
        settings = load_settings()

        # A server can't prompt: if 2+ providers have keys and none was ever
        # chosen (no --llm/env/current-provider), refuse rather than letting
        # the field default silently pick a vendor. Recomputed statelessly —
        # the module-global from load_settings() may belong to another context.
        from bristlenose.config import provider_resolution_for

        resolution = provider_resolution_for(settings)
        if resolution.status == "ambiguous":
            raise RefusalError(
                409,
                RefusalReason.PROVIDER_AMBIGUOUS,
                "Multiple AI providers are configured and none is "
                "selected. Pick one: bristlenose use <provider> (or set "
                "BRISTLENOSE_LLM_PROVIDER), then retry.",
            )

        if settings.llm_provider == "local":
            raise RefusalError(
                503,
                RefusalReason.PROVIDER_LOCAL,
                "AutoCode requires a cloud LLM provider. "
                "Local models (Ollama) cannot fit the full codebook "
                "taxonomy in their context window.",
            )

        if not _has_api_key(settings):
            raise RefusalError(
                503,
                RefusalReason.NO_API_KEY,
                "No API key configured for the current LLM provider "
                f"({settings.llm_provider}). Set the appropriate key "
                "in your .env file.",
            )

        # A cancelled/failed job (the only survivors of the guards above) is
        # discarded now — along with any partial proposals — so the
        # (project_id, framework_id) unique constraint doesn't block the retry.
        if existing:
            db.query(ProposedTag).filter_by(job_id=existing.id).delete(
                synchronize_session=False
            )
            db.delete(existing)
            db.flush()

        # Create job row
        job = AutoCodeJob(
            project_id=project_id,
            framework_id=framework_id,
            status="pending",
        )
        db.add(job)
        db.commit()

        # Spawn background task — fire and forget, but hold a strong reference
        # so a suspended task isn't GC'd mid-run (which would strand the job
        # "running"). Discard on completion.
        db_factory = request.app.state.db_factory
        project_dir = request.app.state.project_dir
        task = asyncio.create_task(
            run_autocode_job(
                db_factory, project_id, framework_id, settings,
                project_dir=project_dir,
            )
        )
        _AUTOCODE_TASKS.add(task)
        task.add_done_callback(_AUTOCODE_TASKS.discard)

        return _job_to_out(job)

    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /projects/{id}/autocode/{framework_id}/status — poll progress
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/autocode/{framework_id}/status")
def get_autocode_status(
    project_id: int,
    framework_id: str,
    request: Request,
) -> AutoCodeJobOut:
    """Get the current status of an AutoCode job."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        job = _get_job(db, project_id, framework_id)
        return _job_to_out(job)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /projects/{id}/autocode/{framework_id}/cancel — cancel running job
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/autocode/{framework_id}/cancel")
def cancel_autocode_job(
    project_id: int,
    framework_id: str,
    request: Request,
) -> AutoCodeJobOut:
    """Cancel a running AutoCode job.

    Sets the job status to "cancelled".  The background job runner checks
    this between batches and stops gracefully — in-progress LLM calls
    complete, but no further batches are started.

    Guards:
    - 404 if project or job not found
    - 409 if job is not in a cancellable state (already completed/failed/cancelled)
    """
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        job = _get_job(db, project_id, framework_id)

        if job.status not in ("pending", "running"):
            raise HTTPException(
                status_code=409,
                detail=f"Job cannot be cancelled (status: {job.status})",
            )

        job.status = "cancelled"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        return _job_to_out(job)

    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /projects/{id}/autocode/{framework_id}/proposals — list proposals
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/autocode/{framework_id}/proposals")
def get_proposals(
    project_id: int,
    framework_id: str,
    request: Request,
    min_confidence: float = 0.5,
) -> ProposalsResponse:
    """List proposed tag assignments above the confidence threshold."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        job = _get_job(db, project_id, framework_id)

        # Query proposals above threshold, joined with quote text and tag info
        proposals = (
            db.query(
                ProposedTag,
                Quote.text,
                Quote.participant_id,
                Quote.session_id,
                Quote.start_timecode,
                TagDefinition.name,
                TagDefinition.id,
                TagDefinition.codebook_group_id,
                CodebookGroup.name,
                CodebookGroup.colour_set,
            )
            .join(Quote, ProposedTag.quote_id == Quote.id)
            .join(TagDefinition, ProposedTag.tag_definition_id == TagDefinition.id)
            .join(
                CodebookGroup,
                TagDefinition.codebook_group_id == CodebookGroup.id,
            )
            .filter(
                ProposedTag.job_id == job.id,
                ProposedTag.confidence >= min_confidence,
            )
            .order_by(ProposedTag.confidence.desc())
            .all()
        )

        # Build colour_index lookup: position of each tag within its group
        group_ids = {row[7] for row in proposals}  # codebook_group_id
        group_td_order: dict[int, list[int]] = {}
        for gid in group_ids:
            tds = (
                db.query(TagDefinition.id)
                .filter_by(codebook_group_id=gid)
                .order_by(TagDefinition.id)
                .all()
            )
            group_td_order[gid] = [td_id for (td_id,) in tds]

        items = [
            ProposedTagOut(
                id=p.id,
                quote_id=p.quote_id,
                dom_id=f"q-{participant_id}-{int(start_tc)}",
                session_id=session_id,
                speaker_code=participant_id,
                start_timecode=start_tc,
                quote_text=quote_text,
                tag_definition_id=p.tag_definition_id,
                tag_name=tag_name,
                group_name=group_name,
                colour_set=colour_set,
                colour_index=(
                    group_td_order.get(cg_id, []).index(td_id)
                    if td_id in group_td_order.get(cg_id, [])
                    else 0
                ),
                confidence=p.confidence,
                rationale=p.rationale,
                status=p.status,
            )
            for p, quote_text, participant_id, session_id, start_tc,
                tag_name, td_id, cg_id, group_name, colour_set in proposals
        ]

        return ProposalsResponse(proposals=items, total=len(items))

    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /projects/{id}/autocode/proposals/{proposal_id}/accept
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/autocode/proposals/{proposal_id}/accept")
def accept_proposal(
    project_id: int,
    proposal_id: int,
    request: Request,
) -> dict[str, str]:
    """Accept a proposed tag — creates a QuoteTag row."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        proposal = db.get(ProposedTag, proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        if proposal.status != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Proposal already {proposal.status}",
            )

        # Create the QuoteTag (may fail on unique constraint if already exists)
        existing_qt = (
            db.query(QuoteTag)
            .filter_by(
                quote_id=proposal.quote_id,
                tag_definition_id=proposal.tag_definition_id,
            )
            .first()
        )
        if not existing_qt:
            db.add(QuoteTag(
                quote_id=proposal.quote_id,
                tag_definition_id=proposal.tag_definition_id,
                source="autocode",
            ))

        proposal.status = "accepted"
        proposal.reviewed_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "ok"}

    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /projects/{id}/autocode/proposals/{proposal_id}/deny
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/autocode/proposals/{proposal_id}/deny")
def deny_proposal(
    project_id: int,
    proposal_id: int,
    request: Request,
) -> dict[str, str]:
    """Deny a proposed tag — keeps the row for telemetry."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        proposal = db.get(ProposedTag, proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        if proposal.status != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Proposal already {proposal.status}",
            )

        proposal.status = "denied"
        proposal.reviewed_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "ok"}

    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /projects/{id}/autocode/{framework_id}/accept-all — bulk accept
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/autocode/{framework_id}/accept-all")
def accept_all_proposals(
    project_id: int,
    framework_id: str,
    request: Request,
    body: BulkActionRequest | None = None,
) -> dict[str, int]:
    """Bulk-accept all pending proposals above min_confidence.

    Optionally filter by codebook group_id.
    """
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        job = _get_job(db, project_id, framework_id)

        min_conf = body.min_confidence if body else 0.5
        group_filter_id = body.group_id if body else None

        # Record the accept cutoff so a later re-apply reuses the same upper
        # threshold (only when an explicit cutoff was supplied — not the default).
        if body is not None:
            job.applied_upper_threshold = min_conf

        query = (
            db.query(ProposedTag)
            .filter(
                ProposedTag.job_id == job.id,
                ProposedTag.status == "pending",
                ProposedTag.confidence >= min_conf,
            )
        )

        # Optional group filter
        if group_filter_id is not None:
            tag_ids = [
                td.id
                for td in db.query(TagDefinition)
                .filter_by(codebook_group_id=group_filter_id)
                .all()
            ]
            query = query.filter(ProposedTag.tag_definition_id.in_(tag_ids))

        proposals = query.all()
        accepted = 0
        now = datetime.now(timezone.utc)

        for proposal in proposals:
            # Create QuoteTag if not already present
            existing_qt = (
                db.query(QuoteTag)
                .filter_by(
                    quote_id=proposal.quote_id,
                    tag_definition_id=proposal.tag_definition_id,
                )
                .first()
            )
            if not existing_qt:
                db.add(QuoteTag(
                    quote_id=proposal.quote_id,
                    tag_definition_id=proposal.tag_definition_id,
                    source="autocode",
                ))

            proposal.status = "accepted"
            proposal.reviewed_at = now
            accepted += 1

        db.commit()
        return {"accepted": accepted}

    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /projects/{id}/autocode/{framework_id}/deny-all — bulk deny
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/autocode/{framework_id}/deny-all")
def deny_all_proposals(
    project_id: int,
    framework_id: str,
    request: Request,
    body: BulkActionRequest | None = None,
) -> dict[str, int]:
    """Bulk-deny all pending proposals.

    Optionally filter by codebook group_id and min_confidence.
    """
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        job = _get_job(db, project_id, framework_id)

        min_conf = body.min_confidence if body else 0.0
        max_conf = body.max_confidence if body else None
        group_filter_id = body.group_id if body else None

        # Record the exclude cutoff ("deny below X") so a later re-apply reuses
        # the same lower threshold. Only the review dialog sends max_confidence.
        if max_conf is not None:
            job.applied_lower_threshold = max_conf

        query = db.query(ProposedTag).filter(
            ProposedTag.job_id == job.id,
            ProposedTag.status == "pending",
        )

        if max_conf is not None:
            # "deny everything below X" — used by threshold review dialog
            query = query.filter(ProposedTag.confidence < max_conf)
        else:
            # Original behaviour: deny everything at or above min_confidence
            query = query.filter(ProposedTag.confidence >= min_conf)

        if group_filter_id is not None:
            tag_ids = [
                td.id
                for td in db.query(TagDefinition)
                .filter_by(codebook_group_id=group_filter_id)
                .all()
            ]
            query = query.filter(ProposedTag.tag_definition_id.in_(tag_ids))

        proposals = query.all()
        denied = 0
        now = datetime.now(timezone.utc)

        for proposal in proposals:
            proposal.status = "denied"
            proposal.reviewed_at = now
            denied += 1

        db.commit()
        return {"denied": denied}

    finally:
        db.close()
