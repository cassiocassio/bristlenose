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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


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
    llm_provider: str
    llm_model: str
    input_tokens: int
    output_tokens: int
    started_at: str
    completed_at: str | None


class ProposedTagOut(BaseModel):
    id: int
    quote_id: int
    quote_text: str
    tag_definition_id: int
    tag_name: str
    group_name: str
    confidence: float
    rationale: str
    status: str


class ProposalsResponse(BaseModel):
    proposals: list[ProposedTagOut]
    total: int


class BulkActionRequest(BaseModel):
    group_id: int | None = None
    min_confidence: float = 0.5


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
        llm_provider=job.llm_provider,
        llm_model=job.llm_model,
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
def start_autocode_job(
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
            raise HTTPException(
                status_code=400,
                detail=f"Framework template '{framework_id}' not found",
            )

        # Check for existing job (no re-runs)
        existing = (
            db.query(AutoCodeJob)
            .filter_by(project_id=project_id, framework_id=framework_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"AutoCode already run for framework '{framework_id}'",
            )

        # Check project has quotes
        quote_count = db.query(Quote).filter_by(project_id=project_id).count()
        if quote_count == 0:
            raise HTTPException(
                status_code=400, detail="Project has no quotes to tag"
            )

        # Load settings and check provider
        settings = load_settings()

        if settings.llm_provider == "local":
            raise HTTPException(
                status_code=503,
                detail=(
                    "AutoCode requires a cloud LLM provider. "
                    "Local models (Ollama) cannot fit the full codebook "
                    "taxonomy in their context window."
                ),
            )

        if not _has_api_key(settings):
            raise HTTPException(
                status_code=503,
                detail=(
                    "No API key configured for the current LLM provider "
                    f"({settings.llm_provider}). Set the appropriate key "
                    "in your .env file."
                ),
            )

        # Create job row
        job = AutoCodeJob(
            project_id=project_id,
            framework_id=framework_id,
            status="pending",
        )
        db.add(job)
        db.commit()

        # Spawn background task — fire and forget
        db_factory = request.app.state.db_factory
        asyncio.create_task(
            run_autocode_job(db_factory, project_id, framework_id, settings)
        )

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
            db.query(ProposedTag, Quote.text, TagDefinition.name, CodebookGroup.name)
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

        items = [
            ProposedTagOut(
                id=p.id,
                quote_id=p.quote_id,
                quote_text=quote_text,
                tag_definition_id=p.tag_definition_id,
                tag_name=tag_name,
                group_name=group_name,
                confidence=p.confidence,
                rationale=p.rationale,
                status=p.status,
            )
            for p, quote_text, tag_name, group_name in proposals
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
        group_filter_id = body.group_id if body else None

        query = (
            db.query(ProposedTag)
            .filter(
                ProposedTag.job_id == job.id,
                ProposedTag.status == "pending",
                ProposedTag.confidence >= min_conf,
            )
        )

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
