"""AutoCode API endpoints — start jobs, poll status, review proposals."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy.orm import Session

from bristlenose.config import load_settings
from bristlenose.server.autocode import (
    coding_ended,
    coding_started,
    recut_made,
    run_autocode_job,
    snap_cutoff,
)
from bristlenose.server.autocode_catch_up import note_quotes_counting
from bristlenose.server.busy import working
from bristlenose.server.codebook import get_template
from bristlenose.server.grounding import quote_dom_id
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
from bristlenose.server.speaker_slots import analysis_quotes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Strong references to in-flight AutoCode tasks. The event loop only weakly
# references a bare ``create_task`` result, so a suspended one can be GC'd
# mid-flight — stranding the job "running" (its finally never runs). Mirrors
# ``_CATCH_UP_TASKS`` in routes/data.py. Discard on completion.
_AUTOCODE_TASKS: set[asyncio.Task[Any]] = set()

#: One row of the proposals query in get_proposals, in the order it selects: the proposal;
#: the quote's text, participant, session, start and ordinal; the tag's name, id and group
#: id; the group's name and colour set. Positional reads below index into this, so a column
#: added to the query is added here too (the ordinal's arrival in R86 shifted the group id
#: from 7 to 8 and the colour_index lookup read tag ids as group ids until 2 Nov 2026).
_ProposalRow = tuple[ProposedTag, str, str, str, float, int, str, int, int, str, str]

# The runner each (project, framework) has in flight. A Stop sets the row
# "cancelled" at once, but the batch already sent still answers and its runner
# goes on until it reads the Stop; an Apply in between started a second runner on
# the same row, both sent the same quotes, and the loser's collision marked the
# job failed (#127 review). The task, never the row, says whether one is live,
# as ``autocode.live_reapply`` does for re-applies.
_AUTOCODE_LIVE: dict[tuple[int, str], asyncio.Task[Any]] = {}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ConfidenceBin(BaseModel):
    """One 0.05-wide band of a job's proposals, by where each one sits now."""

    #: The band's lower edge (0.00, 0.05 … 0.95); the top band takes 1.00 too.
    lower: float
    accepted: int = 0
    #: Still pending: proposed, not decided.
    tentative: int = 0
    #: Denied, by a line or by a researcher.
    excluded: int = 0


class AutoCodeJobOut(BaseModel):
    id: int
    framework_id: str
    status: str
    total_quotes: int
    processed_quotes: int
    proposed_count: int
    #: The last on-enable catch-up's own counts (sent, answered). The catch-up
    #: chip reads these: the cumulative pair above keeps any earlier shortfall.
    catch_up_total: int = 0
    catch_up_processed: int = 0
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
    #: The job's proposals by confidence, 20 bands of 0.05, each split by disposition,
    #: over the quotes that count (the ones the review lists). Only on a status read
    #: that asks for it (``?counts=true``), so the chip's two-second poll stays cheap.
    confidence_counts: list[ConfidenceBin] | None = None


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
    #: How ``status`` was decided: "threshold", "researcher" or "unknown" (decided
    #: before migration 027); None while pending.
    decided_by: str | None = None


class ProposalsResponse(BaseModel):
    proposals: list[ProposedTagOut]
    total: int


class BulkActionRequest(BaseModel):
    group_id: int | None = None
    min_confidence: float = 0.5
    max_confidence: float | None = None

    @field_validator("min_confidence", "max_confidence")
    @classmethod
    def _on_the_review_grid(cls, value: float | None) -> float | None:
        """Cutoffs are stored and reused by the catch-up, so only the review's own
        0.05 grid gets in, with the slider's float drift removed (N188)."""
        return None if value is None else snap_cutoff(value)

    @model_validator(mode="after")
    def _no_null_exclude_cutoff(self) -> BulkActionRequest:
        """An absent ``max_confidence`` means "deny from min_confidence up"; an explicit
        null (what ``JSON.stringify`` writes for a NaN the slider computed) would flip a
        deny-below-the-cutoff into that, denying the proposals the researcher meant to keep."""
        if "max_confidence" in self.model_fields_set and self.max_confidence is None:
            raise ValueError("max_confidence is a number, or left out")
        return self


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class RecutRequest(BaseModel):
    """The review dialog's two lines: accept at or above ``upper``, exclude below ``lower``."""

    lower: float
    upper: float

    @field_validator("lower", "upper")
    @classmethod
    def _on_the_review_grid(cls, value: float) -> float:
        """Stored and reused by the catch-up, so only the review's 0.05 grid (N188)."""
        return snap_cutoff(value)

    @model_validator(mode="after")
    def _lower_not_above_upper(self) -> RecutRequest:
        if self.lower > self.upper:
            raise ValueError("the exclude line must be at or below the accept line")
        return self


class RecutResponse(BaseModel):
    """How many proposals the re-cut moved into each zone."""

    accepted: int
    tentative: int
    excluded: int


def _get_db(request: Request) -> Session:
    db: Session = request.app.state.db_factory()
    return db


def _counted_quote_ids(db: Session, project_id: int) -> set[int]:
    """The quotes that count: not hidden, and still evidence (``analysis_quotes``).

    A proposal on any other quote is not listed in the review and is left alone
    by the bulk actions: the researcher cannot see it, and it counts nowhere
    (owner, 22 Oct 2026; N175). It stays pending, so unhiding the quote brings
    it back to the review."""
    return {q.id for q in analysis_quotes(db, project_id)}


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
        catch_up_total=job.catch_up_total or 0,
        catch_up_processed=job.catch_up_processed or 0,
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


def _azure_key_set(settings: object) -> bool:
    return bool(getattr(settings, "azure_api_key", ""))


def _has_api_key(settings: object) -> bool:
    """Whether the configured provider can be called: a key, plus an endpoint and a
    deployment for Azure, or a ready any-llm (``config.provider_not_ready``)."""
    from bristlenose.config import provider_not_ready

    if getattr(settings, "llm_provider", "") == "local":
        return False
    return provider_not_ready(settings) == ""  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# POST /projects/{id}/autocode/{framework_id} — start job
# ---------------------------------------------------------------------------


def current_settings() -> Any:
    """The settings a start would use; one name for the house default to call."""
    return load_settings()


def refuse_an_unchosen_provider(settings: Any) -> None:
    """Refuse (409 ``PROVIDER_AMBIGUOUS``) when two or more providers have keys and none
    was ever chosen, rather than letting the field default silently pick a vendor."""
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


def require_provider_ready(settings: Any) -> None:
    """Refuse (``RefusalError``) unless the chosen provider can run AutoCode: one chosen,
    a cloud one, and a key (or a ready any-llm). The start route and the house default share
    it, so the default never installs a codebook it cannot then run."""
    refuse_an_unchosen_provider(settings)

    if settings.llm_provider == "local":
        raise RefusalError(
            503,
            RefusalReason.PROVIDER_LOCAL,
            "AutoCode requires a cloud LLM provider. "
            "Local models (Ollama) cannot fit the full codebook "
            "taxonomy in their context window.",
        )

    require_provider_callable(settings)


def require_provider_callable(settings: Any) -> None:
    """Refuse (``RefusalError``) unless the provider has what a call needs: a key, plus an
    endpoint and a deployment for Azure, or a ready any-llm. The keyed half of
    ``require_provider_ready``, shared with the codebook builder, which (unlike AutoCode)
    does not refuse a local model."""
    refuse_an_unchosen_provider(settings)
    if settings.llm_provider == "local":
        return
    no_key = RefusalError(
        503,
        RefusalReason.NO_API_KEY,
        "No API key configured for the current LLM provider "
        f"({settings.llm_provider}). Set the appropriate key "
        "in your .env file.",
    )
    if settings.llm_provider == "anyllm":
        # Through any-llm "not ready" is not always a missing key: a model not chosen,
        # one that is malformed, or the add-on not installed. "Add an API key" sent the
        # researcher to the wrong place (review finding 13); the existing "choose a
        # provider" wording is the nearest true one, and nothing new is added to the
        # screen. Asked once: a refusal is a keystore lookup.
        from bristlenose.llm import anyllm

        ready = anyllm.readiness(settings)
        if not ready.ready:
            if ready.status == "no-key":
                raise no_key
            lines = anyllm.explain(ready)
            raise RefusalError(
                503,
                RefusalReason.PROVIDER_AMBIGUOUS,
                lines[0] if lines else f"any-llm is not ready ({ready.status}).",
            )
    elif settings.llm_provider == "azure" and _azure_key_set(settings):
        # A key without an endpoint or a deployment is not a missing key: the job
        # would start and then fail on the first call. "Add an API key" sends the
        # researcher to the wrong field; "choose a provider in Settings" is the
        # nearest true sentence already on screen (as for any-llm above).
        from bristlenose.config import provider_not_ready

        reason = provider_not_ready(settings)
        if reason:
            raise RefusalError(503, RefusalReason.PROVIDER_AMBIGUOUS, reason)
    elif not _has_api_key(settings):
        raise no_key


def _settle_first_apply(
    db_factory: Callable[[], Session], project_id: int, framework_id: str,
    after_apply: Callable[[], None] | None,
) -> str | None:
    """What a first apply's end asks of Signals: the snapshot source, or None.

    A completed apply runs ``after_apply`` (the house default's cut) and asks for a
    rebuild. A stopped or failed one asks only if it has accepted tags (review 9):
    nothing is accepted by a run itself before Phase 3, but a researcher can accept a
    tentative tag while it codes. Never raises."""
    db = db_factory()
    try:
        job = db.query(AutoCodeJob).filter_by(
            project_id=project_id, framework_id=framework_id,
        ).first()
        if job is None:
            return None
        if job.status == "completed":
            if after_apply is not None:
                try:
                    after_apply()
                except Exception:
                    logger.exception("After-apply step for AutoCode %s failed", framework_id)
            return "codebook_apply"
        if job.status in ("cancelled", "failed") and db.query(ProposedTag.id).filter(
            ProposedTag.job_id == job.id, ProposedTag.status == "accepted",
        ).first() is not None:
            return "codebook_stopped" if job.status == "cancelled" else "codebook_failed"
        return None
    except Exception:
        logger.exception("Could not read how AutoCode %s ended", framework_id)
        return None
    finally:
        db.close()


@router.post("/projects/{project_id}/autocode/{framework_id}")
async def start_autocode_job(
    project_id: int,
    framework_id: str,
    request: Request,
) -> AutoCodeJobOut:
    """Start an AutoCode job for the given project and framework (see ``start_autocode``)."""
    return await start_autocode(request.app, project_id, framework_id)


async def start_autocode(
    app: Any,
    project_id: int,
    framework_id: str,
    *,
    after_apply: Callable[[], None] | None = None,
) -> AutoCodeJobOut:
    """Start an AutoCode job for the given project and framework.

    One path for the route and for the house default (``autocode_house_default``).
    ``after_apply``, when given, runs once the job's batches are done and it is
    ``completed``, before the Signals snapshot: the house default uses it to apply the
    default cutoff, since no researcher is there to open the review.

    Guards:
    - 404 if project not found
    - 400 if framework template not found
    - 400 if project has no quotes
    - 409 if job already exists for this framework
    - 503 if LLM provider is "local" (Ollama can't fit taxonomy)
    - 503 if no API key configured
    """

    db = app.state.db_factory()
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

        # Check for an existing job. A *cancelled* or *failed* job that was never
        # applied must not permanently block a retry — otherwise the Apply button
        # stays enabled (acDisabled only covers running/completed) yet every click
        # 409s and the frontend swallows it, so the button "does nothing". It is
        # run again below, keeping what it coded (#127). A pending/running job is
        # genuinely in flight, and an applied job has results — both keep the
        # 409. Applied is ``completed_at``, not status: a failed or stopped
        # catch-up leaves an applied job "failed" or "cancelled", and clearing it
        # deleted every proposal of the original apply and coded the whole corpus
        # again (#64, RE#66).
        existing = (
            db.query(AutoCodeJob)
            .filter_by(project_id=project_id, framework_id=framework_id)
            .first()
        )
        live = _AUTOCODE_LIVE.get((project_id, framework_id))
        if (existing and existing.status in ("pending", "running")) or (
            live is not None and not live.done()
        ):
            raise RefusalError(
                409,
                RefusalReason.ALREADY_RUNNING,
                f"AutoCode is already running for framework '{framework_id}'",
            )
        if existing and (existing.status == "completed" or existing.completed_at is not None):
            raise RefusalError(
                409,
                RefusalReason.ALREADY_APPLIED,
                f"AutoCode already run for framework '{framework_id}'",
            )

        # Check project has quotes
        # Quotes that count: a project whose every quote is hidden has none to tag (N175).
        quote_count = len(analysis_quotes(db, project_id))
        if quote_count == 0:
            raise RefusalError(
                400, RefusalReason.NO_QUOTES, "Project has no quotes to tag"
            )

        # Load settings and check provider
        settings = load_settings()
        require_provider_ready(settings)

        # A cancelled/failed job that was never applied (the only survivors of
        # the guards above) is run again, keeping its proposals and register rows: the
        # job sends only what no pass has coded (#127). Until 22 Oct 2026 it was
        # deleted, and the quotes it had coded were paid for twice, with the
        # tags the researcher had denied back as pending. Its last failure goes.
        if existing:
            job = existing
            job.status = "pending"
            job.error_message = ""
            job.failure_kind = ""
            job.started_at = datetime.now(timezone.utc)
        else:
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
        db_factory = app.state.db_factory
        project_dir = app.state.project_dir

        async def _run_and_snapshot() -> None:
            # The first report is withheld from the lens from the moment this
            # starts, not when the job ends: for a study with no report with cards
            # the lens would otherwise be lit through the whole job, dim for the
            # build and lit again. A study that has a report is never withheld
            # (the lens reads "no report with cards AND a build in flight").
            from bristlenose.server.signal_snapshots import (
                begin_signals_preparing,
                end_signals_preparing,
            )

            begin_signals_preparing(app.state)
            try:
                # Paid work end to end: the gaps between the job's chunks and the
                # snapshot build that follows count as busy too.
                with working("autocode"):
                    await _apply_and_snapshot()
            finally:
                end_signals_preparing(app.state)

        async def _apply_and_snapshot() -> None:
            source: str | None = None
            try:
                await run_autocode_job(
                    db_factory, project_id, framework_id, settings,
                    project_dir=project_dir,
                )
                # A quote that began to count while this ran (an unhide, a recode back
                # in) was not in its batches and, the job not yet applied then, armed
                # nothing: the codebook owes it now, so ask (ruling 4).
                note_quotes_counting(app, project_id)
                source = _settle_first_apply(db_factory, project_id, framework_id, after_apply)
            finally:
                # Signals is rebuilt once the last of the project's passes ends (D21):
                # this one's build waits while another apply or catch-up still codes.
                await coding_ended(app, project_id, snapshot_source=source, own_build=True)

        task = asyncio.create_task(_run_and_snapshot())
        coding_started(project_id, task)
        _AUTOCODE_TASKS.add(task)
        task.add_done_callback(_AUTOCODE_TASKS.discard)
        key = (project_id, framework_id)
        _AUTOCODE_LIVE[key] = task

        def _forget(t: asyncio.Task[Any]) -> None:
            if _AUTOCODE_LIVE.get(key) is t:
                del _AUTOCODE_LIVE[key]

        task.add_done_callback(_forget)

        return _job_to_out(job)

    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /projects/{id}/autocode/jobs — the runs in flight
# ---------------------------------------------------------------------------


class AutoCodeJobSummary(BaseModel):
    framework_id: str
    #: The codebook's title, for the chip's label; the id if the template is gone.
    title: str
    status: str
    #: Set on a catch-up (a finished run re-coding new sessions), None on a first run.
    completed_at: str | None
    #: Quotes answered so far and in all, for the Mac's project row ("AutoCode · 25 of 101").
    #: Written per batch on a first run; a catch-up adds its batches to the codebook's
    #: running totals, so the row reads these only for a job with no ``completed_at``.
    processed_quotes: int = 0
    total_quotes: int = 0


class AutoCodeJobsResponse(BaseModel):
    jobs: list[AutoCodeJobSummary]


class AutoCodeEndedJobSummary(AutoCodeJobSummary):
    """A first apply that ended without finishing, or finished with batches missing:
    what the Mac's project row needs to say "Stopped", "Out of credit", "Provider key
    issue" or "Partial run" (docs/design-autocode-landing-plan.md D23, Phase 5)."""

    #: ``LLMFailureKind`` value, or "" (a Stop, or a failure the classifier did not name).
    failure_kind: str = ""


class AutoCodeJobsWithEndedResponse(BaseModel):
    jobs: list[AutoCodeEndedJobSummary]


@router.get("/projects/{project_id}/autocode/jobs", response_model=AutoCodeJobsResponse)
def list_autocode_jobs(
    project_id: int, request: Request, include_ended: bool = False,
) -> Any:
    """The project's AutoCode runs still pending or running.

    A reloaded report asks this once to put back the chips of runs it has no chip for
    (R14): a window carries its own chips across a reload (RE#38), but not another
    window's, and the per-framework status read cannot say which frameworks to ask
    about.

    ``include_ended=true`` (the Mac's project row, Phase 5) also lists the first
    applies that ended unfinished, stopped or failed (``completed_at`` unset), and the
    ones that finished with some batches failed (a partial run, still carrying its
    ``failure_kind``), each with its ``failure_kind``. Without it the answer is exactly
    the running list the web's ActivityStore rehydrates its chips from.
    """
    from sqlalchemy import ColumnElement, and_, or_

    db = _get_db(request)
    try:
        _check_project(db, project_id)
        wanted: ColumnElement[bool] = AutoCodeJob.status.in_(("pending", "running"))
        if include_ended:
            wanted = or_(
                wanted,
                and_(
                    AutoCodeJob.completed_at.is_(None),
                    AutoCodeJob.status.in_(("failed", "cancelled")),
                ),
                and_(AutoCodeJob.status == "completed", AutoCodeJob.failure_kind != ""),
            )
        rows = (
            db.query(AutoCodeJob)
            .filter(AutoCodeJob.project_id == project_id, wanted)
            .order_by(AutoCodeJob.started_at)
            .all()
        )
        jobs = []
        for job in rows:
            template = get_template(job.framework_id)
            if template is None:
                logger.warning("AutoCode job for framework %r has no template; titled by its id",
                               job.framework_id)
            fields: dict[str, Any] = {
                "framework_id": job.framework_id,
                "title": template.title if template else job.framework_id,
                "status": job.status,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "processed_quotes": job.processed_quotes,
                "total_quotes": job.total_quotes,
            }
            jobs.append(fields)
        if not include_ended:
            return AutoCodeJobsResponse(jobs=[AutoCodeJobSummary(**f) for f in jobs])
        # The wider answer is its own model: declared on the route, the running list's
        # model would drop ``failure_kind``, and adding it there changes the web's answer.
        from fastapi.encoders import jsonable_encoder
        from fastapi.responses import JSONResponse

        by_framework = {job.framework_id: job for job in rows}
        wide = AutoCodeJobsWithEndedResponse(jobs=[
            AutoCodeEndedJobSummary(
                **f, failure_kind=by_framework[f["framework_id"]].failure_kind or "",
            )
            for f in jobs
        ])
        return JSONResponse(jsonable_encoder(wide))
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
    counts: bool = False,
) -> AutoCodeJobOut:
    """Get the current status of an AutoCode job.

    ``counts=true`` adds ``confidence_counts`` (the tag sidebar's histogram), so the
    sidebar needs no second request; without it the read is the job row alone.
    """
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        job = _get_job(db, project_id, framework_id)
        out = _job_to_out(job)
        if counts:
            out.confidence_counts = confidence_counts(db, project_id, job.id)
        return out
    finally:
        db.close()


def confidence_counts(db: Session, project_id: int, job_id: int) -> list[ConfidenceBin]:
    """The job's proposals on quotes that count, in 20 bands of 0.05 by confidence,
    each split into accepted, tentative (pending) and excluded (denied). One query of
    three columns over the job's proposals; a confidence of 1.00 is in the top band."""
    from bristlenose.server.autocode import CONFIDENCE_STEPS_PER_UNIT

    bins = [
        ConfidenceBin(lower=i / CONFIDENCE_STEPS_PER_UNIT)
        for i in range(CONFIDENCE_STEPS_PER_UNIT)
    ]
    counted = _counted_quote_ids(db, project_id)
    rows = db.query(ProposedTag.quote_id, ProposedTag.status, ProposedTag.confidence).filter(
        ProposedTag.job_id == job_id
    )
    for quote_id, status, confidence in rows:
        if quote_id not in counted:
            continue
        # Rounded before the floor, as the dialog's grid is: 0.7000000000000001 and
        # 0.6999999999999999 are both the 0.70 band (N188).
        steps = math.floor(round((confidence or 0.0) * CONFIDENCE_STEPS_PER_UNIT, 6))
        band = bins[min(max(steps, 0), CONFIDENCE_STEPS_PER_UNIT - 1)]
        if status == "accepted":
            band.accepted += 1
        elif status == "denied":
            band.excluded += 1
        else:
            band.tentative += 1
    return bins


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
        # A Stop never sets completed_at, which means "applied at least once". A
        # stopped first apply is not an applied one: set, it joined maintenance,
        # so the next run auto-accepted new sessions at the default cutoff and the
        # quotes the Stop cut off were never coded (#65, RE#66). A catch-up's job
        # keeps the time it has.
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
    since_id: int | None = None,
) -> ProposalsResponse:
    """List proposed tag assignments above the confidence threshold.

    ``since_id`` lists only proposals saved after the one with that id, so a page
    following a run (batches are saved as they answer) reads what is new and not the
    whole run again. Ids only grow, so the largest id it has seen is its cursor.
    """
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
                Quote.ordinal,
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
                *([ProposedTag.id > since_id] if since_id is not None else []),
            )
            .order_by(ProposedTag.confidence.desc())
            .all()
        )
        counted = _counted_quote_ids(db, project_id)
        rows: list[_ProposalRow] = [
            tuple(row) for row in proposals if row[0].quote_id in counted
        ]

        # Build colour_index lookup: position of each tag within its group
        group_ids = {row[8] for row in rows}  # TagDefinition.codebook_group_id
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
                dom_id=quote_dom_id(participant_id, start_tc, ordinal),
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
                decided_by=p.decided_by,
            )
            for p, quote_text, participant_id, session_id, start_tc, ordinal,
                tag_name, td_id, cg_id, group_name, colour_set in rows
        ]

        return ProposalsResponse(proposals=items, total=len(items))

    finally:
        db.close()


def _ensure_autocode_tag(db: Session, proposal: ProposedTag) -> None:
    """Give the proposal's quote its tag, as AutoCode's, unless the quote has it already
    (a tag the researcher added by hand stays theirs). Uncommitted."""
    existing = (
        db.query(QuoteTag)
        .filter_by(quote_id=proposal.quote_id, tag_definition_id=proposal.tag_definition_id)
        .first()
    )
    if existing is None:
        db.add(QuoteTag(
            quote_id=proposal.quote_id,
            tag_definition_id=proposal.tag_definition_id,
            source="autocode",
        ))


def _drop_autocode_tag(db: Session, proposal: ProposedTag) -> None:
    """Take the proposal's tag off its quote, only when AutoCode made it: a tag the
    researcher added by hand that the proposal happens to match is never touched
    (docs/design-autocode-landing-plan.md, review 1). Uncommitted."""
    db.query(QuoteTag).filter_by(
        quote_id=proposal.quote_id,
        tag_definition_id=proposal.tag_definition_id,
        source="autocode",
    ).delete(synchronize_session=False)


def _already_reviewed(status: str) -> RefusalError:
    """409 for a proposal reviewed already, naming which way it went."""
    reason = (
        RefusalReason.PROPOSAL_ACCEPTED if status == "accepted" else RefusalReason.PROPOSAL_DENIED
    )
    return RefusalError(409, reason, f"Proposal already {status}")


class ReviewRequest(BaseModel):
    """The body of a per-row accept or deny.

    ``override`` is the review dialog's row button on a proposal already decided
    (D34): it changes that decision instead of being refused. Every other caller
    (a quote card, the dialog's buttons on a pending row) sends none, and a decided
    proposal stays refused with 409 "reviewed elsewhere", which both clients handle
    (a stale window, a double click)."""

    override: bool = False


# ---------------------------------------------------------------------------
# POST /projects/{id}/autocode/proposals/{proposal_id}/accept
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/autocode/proposals/{proposal_id}/accept")
def accept_proposal(
    project_id: int,
    proposal_id: int,
    request: Request,
    body: ReviewRequest | None = None,
) -> dict[str, str]:
    """Accept a proposed tag, as the researcher's decision: its QuoteTag is made.

    A proposal already decided is refused (409, which way it went) unless the body
    says ``override``: then an exclusion, the lines' or the researcher's own, is
    taken back, and accepting one already accepted pins it as the researcher's, so
    no re-cut moves it (D2, D34; landing plan Phase 2).
    """
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        proposal = db.get(ProposedTag, proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        if proposal.status != "pending" and not (body is not None and body.override):
            raise _already_reviewed(proposal.status)

        _ensure_autocode_tag(db, proposal)

        proposal.status = "accepted"
        proposal.decided_by = "researcher"
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
    body: ReviewRequest | None = None,
) -> dict[str, str]:
    """Exclude a proposed tag, as the researcher's decision; the row is kept for telemetry.

    Refused for a decided proposal as accept is, unless ``override``: then excluding
    one that was accepted takes its tag off the quote when AutoCode made it, never a
    tag the researcher added by hand (review 1).
    """
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        proposal = db.get(ProposedTag, proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        if proposal.status != "pending":
            if not (body is not None and body.override):
                raise _already_reviewed(proposal.status)
            _drop_autocode_tag(db, proposal)

        proposal.status = "denied"
        proposal.decided_by = "researcher"
        proposal.reviewed_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "ok"}

    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /projects/{id}/autocode/{framework_id}/accept-all — bulk accept
# ---------------------------------------------------------------------------


def _accept_pending(db: Session, project_id: int, query: Any) -> int:
    """Accept the pending proposals ``query`` selects that still count: make each one's
    QuoteTag (source "autocode") and mark it accepted. Uncommitted; returns how many."""
    counted = _counted_quote_ids(db, project_id)
    proposals = [p for p in query.all() if p.quote_id in counted]
    accepted = 0
    now = datetime.now(timezone.utc)

    for proposal in proposals:
        _ensure_autocode_tag(db, proposal)
        proposal.status = "accepted"
        proposal.decided_by = "threshold"
        proposal.reviewed_at = now
        accepted += 1
    return accepted


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

        accepted = _accept_pending(db, project_id, query)
        db.commit()
        if body is not None and accepted:
            # The review dialog's lines moved something: Signals follows, once the
            # burst settles. A line that accepted nothing asks nothing (D31).
            recut_made(request.app, project_id)
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

        counted = _counted_quote_ids(db, project_id)
        proposals = [p for p in query.all() if p.quote_id in counted]
        denied = 0
        now = datetime.now(timezone.utc)

        for proposal in proposals:
            proposal.status = "denied"
            proposal.decided_by = "threshold"
            proposal.reviewed_at = now
            denied += 1

        db.commit()
        if max_conf is not None and denied:
            # The review dialog's exclude line (accept-all's twin) moved something: one
            # rebuild per burst. A line that denied nothing asks nothing (D31).
            recut_made(request.app, project_id)
        return {"denied": denied}

    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /projects/{id}/autocode/{framework_id}/recut — the review dialog's Apply
# ---------------------------------------------------------------------------

#: The three zones a pair of lines makes, by the dialog's inequalities.
_ACCEPT, _TENTATIVE, _EXCLUDE = "accepted", "tentative", "excluded"

#: Where each status sits today.
_STATUS_ZONE = {"accepted": _ACCEPT, "pending": _TENTATIVE, "denied": _EXCLUDE}


def zone_at(confidence: float, lower: float, upper: float) -> str:
    """The zone a confidence falls in: at or above ``upper`` is accepted, strictly
    below ``lower`` excluded, the band between tentative (the catch-up's and the
    bulk actions' own inequalities)."""
    if confidence >= upper:
        return _ACCEPT
    if confidence < lower:
        return _EXCLUDE
    return _TENTATIVE


def recut_target(
    proposal: ProposedTag, before: tuple[float, float] | None, lower: float, upper: float,
) -> str | None:
    """The zone a re-cut to (``lower``, ``upper``) puts ``proposal`` in, or None when it
    stays where it is.

    A decision the researcher made, or one made before decisions were recorded
    ("unknown"), never moves (D2). A threshold decision or a pending proposal moves
    only when its zone under the stored lines ``before`` differs from its zone under
    the new ones (D26): Apply with the lines unmoved changes nothing, whatever an
    earlier pass left. ``before`` is None for a job no lines were ever stored on: no
    cut has been made, so where each proposal sits now is its status, and the first
    Apply is a plain cut, as it always was.
    """
    if proposal.decided_by in ("researcher", "unknown"):
        return None
    after = zone_at(proposal.confidence, lower, upper)
    was = (
        _STATUS_ZONE.get(proposal.status, _TENTATIVE)
        if before is None
        else zone_at(proposal.confidence, before[1], before[0])
    )
    if was == after:
        return None
    return after


def _stored_lines_or_none(job: AutoCodeJob) -> tuple[float, float] | None:
    """The (accept, exclude) lines stored on ``job``, the dialog's defaults standing in
    for one that is missing; None when neither was ever stored."""
    if job.applied_upper_threshold is None and job.applied_lower_threshold is None:
        return None
    from bristlenose.server.autocode import stored_lines

    return stored_lines(job)


@router.post("/projects/{project_id}/autocode/{framework_id}/recut")
def recut_proposals(
    project_id: int,
    framework_id: str,
    request: Request,
    body: RecutRequest,
) -> RecutResponse:
    """Move the run's lines to ``body`` and re-sort what the move changes (Phase 2 of
    docs/design-autocode-landing-plan.md: D2, D3, D26).

    Each movable proposal (a threshold decision, or pending) whose zone changes is set
    to its new zone: accepted (a tag made as AutoCode's, unless the quote has it),
    tentative (pending again, undecided; AutoCode's tag taken off), or excluded
    (AutoCode's tag taken off). A tag the researcher added by hand is never removed.
    Only quotes that count are touched, as the bulk actions do; the lines are stored
    for the catch-up. One transaction, no confirmation (D3).
    """
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        job = _get_job(db, project_id, framework_id)
        before = _stored_lines_or_none(job)
        counted = _counted_quote_ids(db, project_id)
        moved = {_ACCEPT: 0, _TENTATIVE: 0, _EXCLUDE: 0}
        now = datetime.now(timezone.utc)

        for proposal in db.query(ProposedTag).filter(ProposedTag.job_id == job.id).all():
            if proposal.quote_id not in counted:
                continue
            target = recut_target(proposal, before, body.lower, body.upper)
            if target is None:
                continue
            if target == _ACCEPT:
                _ensure_autocode_tag(db, proposal)
                proposal.status = "accepted"
                proposal.decided_by = "threshold"
                proposal.reviewed_at = now
            elif target == _EXCLUDE:
                _drop_autocode_tag(db, proposal)
                proposal.status = "denied"
                proposal.decided_by = "threshold"
                proposal.reviewed_at = now
            else:
                _drop_autocode_tag(db, proposal)
                proposal.status = "pending"
                proposal.decided_by = None
                proposal.reviewed_at = None
            moved[target] += 1

        job.applied_lower_threshold = body.lower
        job.applied_upper_threshold = body.upper
        db.commit()
        if any(moved.values()):
            # Accepted tags changed: Signals follows, once the burst settles (review 9).
            recut_made(request.app, project_id)
        return RecutResponse(
            accepted=moved[_ACCEPT], tentative=moved[_TENTATIVE], excluded=moved[_EXCLUDE],
        )
    finally:
        db.close()


def accept_at_default_cutoff(db_factory: Callable[[], Session], project_id: int,
                             framework_id: str, cutoff: float) -> int:
    """Apply a finished first job at ``cutoff`` as Accept all would: pending proposals at or
    above it are accepted and the cutoff is stored for later re-applies (the catch-up reuses
    it). The band below stays pending for the review; nothing is denied, since a denial
    is the review's to make. Returns how many were accepted."""
    db = db_factory()
    try:
        job = db.query(AutoCodeJob).filter_by(
            project_id=project_id, framework_id=framework_id).first()
        if job is None:
            return 0
        job.applied_upper_threshold = cutoff
        # No lower line either: unset, the later re-applies deny below the dialog's default, and
        # nobody watched that denial. 0 leaves everything under the cutoff pending, for the review.
        job.applied_lower_threshold = 0.0
        query = db.query(ProposedTag).filter(
            ProposedTag.job_id == job.id,
            ProposedTag.status == "pending",
            ProposedTag.confidence >= cutoff,
        )
        accepted = _accept_pending(db, project_id, query)
        db.commit()
        return accepted
    finally:
        db.close()
