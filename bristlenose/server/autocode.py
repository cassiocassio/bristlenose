"""AutoCode engine — LLM-assisted codebook tag application.

Builds prompt text from codebook YAML templates, batches quotes, calls the
LLM, and stores proposed tag assignments for researcher review.

Public API::

    build_tag_taxonomy(template)      → formatted prompt text
    build_quote_batch(quotes)         → formatted quote text
    resolve_tag_name_to_id(name, map) → TagDefinition.id or None
    run_autocode_job(...)             → top-level async job runner
"""

from __future__ import annotations

import asyncio
import difflib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from bristlenose.server.codebook import CodebookTemplate, TemplateGroup, TemplateTag

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session as SASession

    from bristlenose.config import BristlenoseSettings

logger = logging.getLogger(__name__)

#: Number of quotes per LLM call.  Fixed batches give predictable token
#: budgets regardless of session length.
BATCH_SIZE = 25


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class QuoteBatchItem:
    """A quote ready for batching into an LLM prompt."""

    db_id: int  # Quote.id — for creating ProposedTag rows
    text: str
    session_id: str
    participant_id: str
    topic_label: str
    sentiment: str


# ---------------------------------------------------------------------------
# Taxonomy formatting
# ---------------------------------------------------------------------------


def build_tag_taxonomy(template: CodebookTemplate) -> str:
    """Format a codebook template's groups and tags as LLM prompt text.

    Groups become ``### Group Name — subtitle`` headers.  Tags get their
    discrimination prompts (definition, apply_when, not_this) indented
    below.  Tags without discrimination prompts get a name-only entry.
    """
    parts: list[str] = []
    for group in template.groups:
        parts.append(_format_group(group))
    return "\n\n".join(parts)


def _format_group(group: TemplateGroup) -> str:
    """Format one group and its tags."""
    lines: list[str] = [f"### {group.name} — {group.subtitle}"]
    for tag in group.tags:
        lines.append(_format_tag(tag))
    return "\n\n".join(lines)


def _format_tag(tag: TemplateTag) -> str:
    """Format one tag with its discrimination prompts.

    Tags with full prompts get definition + apply_when + not_this.
    Tags with partial prompts get whatever is available.
    Tags with no prompts get just the bolded name.
    """
    lines: list[str] = []
    if tag.definition:
        lines.append(f"**{tag.name}** — {tag.definition}")
    else:
        lines.append(f"**{tag.name}**")

    if tag.apply_when:
        lines.append(f"  Apply when: {tag.apply_when}")
    if tag.not_this:
        lines.append(f"  Not this: {tag.not_this}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Quote batching
# ---------------------------------------------------------------------------


def build_quote_batch(quotes: list[QuoteBatchItem]) -> str:
    """Format a batch of quotes as numbered text for the LLM prompt.

    Each quote gets a 0-based index, session/participant metadata, and
    any available context (topic label, sentiment).
    """
    lines: list[str] = []
    for i, q in enumerate(quotes):
        parts = [f"{i}. [{q.session_id}/{q.participant_id}]"]
        if q.topic_label:
            parts.append(f"[{q.topic_label}]")
        if q.sentiment:
            parts.append(f"[{q.sentiment}]")
        parts.append(f'"{q.text}"')
        lines.append(" ".join(parts))
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Tag name resolution
# ---------------------------------------------------------------------------


def resolve_tag_name_to_id(
    tag_name: str,
    tag_map: dict[str, int],
) -> int | None:
    """Map an LLM-returned tag name to a TagDefinition.id.

    Tries exact match (case-insensitive) first, then fuzzy match with
    a high cutoff (0.9).  Returns ``None`` for unrecognised names.
    """
    # Exact match (case-insensitive)
    lower = tag_name.lower().strip()
    if lower in tag_map:
        return tag_map[lower]

    # Fuzzy match — catches minor LLM variations like "info arch" vs
    # "information architecture"
    candidates = list(tag_map.keys())
    matches = difflib.get_close_matches(lower, candidates, n=1, cutoff=0.9)
    if matches:
        logger.info("Fuzzy-matched LLM tag '%s' → '%s'", tag_name, matches[0])
        return tag_map[matches[0]]

    logger.warning("Unrecognised LLM tag name: '%s'", tag_name)
    return None


def build_tag_name_map(
    template: CodebookTemplate,
    tag_id_lookup: dict[str, int],
) -> dict[str, int]:
    """Build a lowercase tag name → TagDefinition.id mapping.

    ``tag_id_lookup`` maps lowercase tag names to DB IDs (built from
    the TagDefinition rows created when the framework was imported).
    """
    result: dict[str, int] = {}
    for group in template.groups:
        for tag in group.tags:
            lower = tag.name.lower().strip()
            if lower in tag_id_lookup:
                result[lower] = tag_id_lookup[lower]
    return result


# ---------------------------------------------------------------------------
# Job runner
# ---------------------------------------------------------------------------


async def run_autocode_job(
    db_factory: Callable[[], SASession],
    project_id: int,
    framework_id: str,
    settings: BristlenoseSettings,
    project_dir: Path | None = None,
) -> None:
    """Execute an AutoCode job: load quotes, batch, call LLM, store proposals.

    This is the top-level coroutine spawned by ``asyncio.create_task()``
    from the API endpoint.  It manages its own DB sessions and handles
    errors gracefully — the caller does not await this.

    When ``project_dir`` is provided, telemetry contextvars are bound for
    the duration of the job so per-call rows land in
    ``<output_dir>/.bristlenose/llm-calls.jsonl``.
    """
    from bristlenose.llm import telemetry
    from bristlenose.llm.client import LLMClient
    from bristlenose.llm.prompts import get_prompt_template
    from bristlenose.llm.structured import AutoCodeBatchResult
    from bristlenose.server.codebook import get_template
    from bristlenose.server.models import AutoCodeJob, ProposedTag, Quote, TagDefinition

    # Bind telemetry context for the duration of the job. ``project_dir``
    # may be either the project root or the bristlenose-output dir; resolve
    # to the canonical .bristlenose/ run dir.
    telemetry_tokens: tuple[object, object] | None = None
    if project_dir is not None:
        _output_dir = project_dir / "bristlenose-output"
        if not _output_dir.is_dir():
            _output_dir = project_dir
        run_dir = _output_dir / ".bristlenose"
        run_id = f"autocode-{project_id}-{framework_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        telemetry_tokens = telemetry.set_run_context(run_id, run_dir)

    db = db_factory()
    try:
        # Load the job row
        job = (
            db.query(AutoCodeJob)
            .filter_by(project_id=project_id, framework_id=framework_id)
            .first()
        )
        if not job:
            logger.error("AutoCodeJob not found: project=%d framework=%s", project_id, framework_id)
            return

        # If cancelled before the async task started, exit immediately.
        if job.status == "cancelled":
            return

        job.status = "running"
        db.commit()

        # Load template
        template = get_template(framework_id)
        if not template:
            job.status = "failed"
            job.error_message = f"Template '{framework_id}' not found"
            db.commit()
            return

        # Load quotes
        quotes_rows = db.query(Quote).filter_by(project_id=project_id).all()
        if not quotes_rows:
            job.status = "completed"
            job.total_quotes = 0
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        # Build batch items
        batch_items = [
            QuoteBatchItem(
                db_id=q.id,
                text=q.text,
                session_id=q.session_id,
                participant_id=q.participant_id,
                topic_label=q.topic_label or "",
                sentiment=q.sentiment or "",
            )
            for q in quotes_rows
        ]

        job.total_quotes = len(batch_items)
        job.llm_provider = settings.llm_provider
        job.llm_model = settings.llm_model
        db.commit()

        # Build taxonomy text (once, shared across all batches)
        taxonomy_text = build_tag_taxonomy(template)

        logger.info(
            "AutoCode job started: framework=%s quotes=%d model=%s",
            framework_id,
            len(batch_items),
            settings.llm_model,
        )

        # Build tag name → TagDefinition.id map from DB
        # (framework groups have framework_id set on the CodebookGroup)
        from bristlenose.server.models import CodebookGroup

        framework_groups = (
            db.query(CodebookGroup).filter_by(framework_id=framework_id).all()
        )
        group_ids = [g.id for g in framework_groups]
        tag_defs = (
            db.query(TagDefinition)
            .filter(TagDefinition.codebook_group_id.in_(group_ids))
            .all()
        )
        tag_id_lookup = {td.name.lower().strip(): td.id for td in tag_defs}
        tag_map = build_tag_name_map(template, tag_id_lookup)

        # Create LLM client (tracker is built-in as llm_client.tracker)
        llm_client = LLMClient(settings)

        # Load prompt template
        prompt_tmpl = get_prompt_template("autocode")
        # Record the prompt version so a later re-apply can reproduce this run.
        job.prompt_version = prompt_tmpl.version

        # Chunk into batches
        batches: list[list[QuoteBatchItem]] = []
        for i in range(0, len(batch_items), BATCH_SIZE):
            batches.append(batch_items[i : i + BATCH_SIZE])

        # Process batches with bounded concurrency
        semaphore = asyncio.Semaphore(settings.llm_concurrency)
        proposed_count = 0
        processed_count = 0
        progress_lock = asyncio.Lock()

        async def _process_batch(batch: list[QuoteBatchItem]) -> list[ProposedTag]:
            nonlocal processed_count
            async with semaphore:
                # Cancellation checkpoint — check DB before starting LLM call.
                cancel_db = db_factory()
                try:
                    cancel_job = (
                        cancel_db.query(AutoCodeJob)
                        .filter_by(project_id=project_id, framework_id=framework_id)
                        .first()
                    )
                    if cancel_job and cancel_job.status == "cancelled":
                        return []
                finally:
                    cancel_db.close()

                from bristlenose.llm.boundary import wrap_untrusted

                quote_text = build_quote_batch(batch)
                user_prompt = prompt_tmpl.user.format(
                    codebook_title=template.title,
                    codebook_preamble=template.preamble,
                    formatted_tag_taxonomy=taxonomy_text,
                    formatted_quotes=wrap_untrusted("quotes", quote_text),
                )
                with telemetry.stage("serve_autocode"):
                    result = await llm_client.analyze(
                        system_prompt=prompt_tmpl.system,
                        user_prompt=user_prompt,
                        response_model=AutoCodeBatchResult,
                        prompt_template=prompt_tmpl,
                    )
                # Map assignments to ProposedTag rows
                proposals: list[ProposedTag] = []
                for assignment in result.assignments:
                    if assignment.quote_index < 0 or assignment.quote_index >= len(batch):
                        logger.warning(
                            "Invalid quote_index %d in batch of %d",
                            assignment.quote_index,
                            len(batch),
                        )
                        continue
                    quote_item = batch[assignment.quote_index]
                    tag_def_id = resolve_tag_name_to_id(assignment.tag_name, tag_map)
                    if tag_def_id is None:
                        continue
                    proposals.append(
                        ProposedTag(
                            job_id=job.id,
                            quote_id=quote_item.db_id,
                            tag_definition_id=tag_def_id,
                            confidence=assignment.confidence,
                            rationale=assignment.rationale,
                        )
                    )
                processed_count += len(batch)
                logger.info(
                    "AutoCode batch done: %d/%d quotes, %d proposals",
                    processed_count,
                    job.total_quotes,
                    len(proposals),
                )
                # Commit progress via a separate short-lived session so the
                # status endpoint sees incremental updates (the main session
                # holds the proposals transaction until all batches finish).
                async with progress_lock:
                    progress_db = db_factory()
                    try:
                        progress_job = (
                            progress_db.query(AutoCodeJob)
                            .filter_by(
                                project_id=project_id, framework_id=framework_id
                            )
                            .first()
                        )
                        if progress_job:
                            progress_job.processed_quotes = processed_count
                            progress_db.commit()
                    finally:
                        progress_db.close()
                return proposals

        # Gather all batches
        batch_results = await asyncio.gather(
            *(_process_batch(b) for b in batches),
            return_exceptions=True,
        )

        # Store results, handling per-batch errors gracefully
        batch_errors = 0
        for batch_result in batch_results:
            if isinstance(batch_result, BaseException):
                logger.error("Batch failed: %s", batch_result)
                batch_errors += 1
                continue
            for proposal in batch_result:
                db.add(proposal)
                proposed_count += 1

        logger.info(
            "AutoCode job finished: %d proposals from %d quotes (%d batch errors)",
            proposed_count,
            len(batch_items),
            batch_errors,
        )

        # Re-read job status — it may have been cancelled during processing.
        db.expire(job)
        if job.status == "cancelled":
            # Keep "cancelled" status but save any partial results.
            job.processed_quotes = processed_count
            job.proposed_count = proposed_count
            job.input_tokens = llm_client.tracker.input_tokens
            job.output_tokens = llm_client.tracker.output_tokens
            db.commit()
            return

        job.status = "completed"
        job.processed_quotes = processed_count
        job.proposed_count = proposed_count
        job.input_tokens = llm_client.tracker.input_tokens
        job.output_tokens = llm_client.tracker.output_tokens
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as exc:
        logger.exception("AutoCode job failed: %s", exc)
        try:
            db.rollback()
            job = (
                db.query(AutoCodeJob)
                .filter_by(project_id=project_id, framework_id=framework_id)
                .first()
            )
            if job and job.status != "cancelled":
                job.status = "failed"
                job.error_message = str(exc)
                db.commit()
        except Exception:
            logger.exception("Failed to mark job as failed")
    finally:
        db.close()
        if telemetry_tokens is not None:
            try:
                telemetry.trim_run_terminus()
            except Exception:
                logger.debug("telemetry trim failed", exc_info=True)
            telemetry.reset_run_context(telemetry_tokens)


# Default accept cutoff when a framework was applied without an explicit
# threshold (mirrors the review dialog's DEFAULT_UPPER = 0.70).
DEFAULT_ACCEPT_THRESHOLD = 0.70


async def reapply_to_new_quotes(
    db_factory: Callable[[], SASession],
    project_id: int,
    framework_id: str,
    settings: BristlenoseSettings,
) -> int:
    """Re-apply an already-applied framework to the quotes it hasn't seen yet.

    Codes ONLY the delta — quotes with no ``ProposedTag`` from the framework's
    existing job (i.e. newly-added ones) — and auto-accepts at the researcher's
    stored cutoff, with no review modal. Existing quotes and human tags are never
    touched (the accept is non-clobbering). Returns the number of new QuoteTags
    created (0 if there's nothing to do).

    Safe no-op when the framework was never applied (no completed job) — so it
    can be fired unconditionally per linked framework after a re-run.
    """
    from bristlenose.llm import telemetry
    from bristlenose.llm.boundary import wrap_untrusted
    from bristlenose.llm.client import LLMClient
    from bristlenose.llm.prompts import get_prompt_template
    from bristlenose.llm.structured import AutoCodeBatchResult
    from bristlenose.server.codebook import get_template
    from bristlenose.server.models import (
        AutoCodeJob,
        CodebookGroup,
        ProposedTag,
        Quote,
        QuoteTag,
        TagDefinition,
    )
    from bristlenose.server.models import (
        Session as SessionModel,
    )

    db = db_factory()
    try:
        job = (
            db.query(AutoCodeJob)
            .filter_by(
                project_id=project_id, framework_id=framework_id, status="completed"
            )
            .first()
        )
        if job is None:
            return 0  # framework never applied → nothing to reproduce

        template = get_template(framework_id)
        if not template:
            return 0

        threshold = job.applied_upper_threshold
        if threshold is None:
            threshold = DEFAULT_ACCEPT_THRESHOLD

        # Delta = quotes from sessions imported AFTER this framework was applied.
        # ``Session.first_imported_at`` is set once per session and never updated,
        # so (a) a clean/full re-run of existing sessions doesn't falsely mark
        # them new, and (b) an existing quote the LLM simply didn't tag is never
        # re-sent — both would happen with a "quote has no proposal" heuristic.
        # ``completed_at`` advances to each re-apply's time (below), so each new
        # session is coded exactly once.
        if job.completed_at is None:
            return 0
        new_session_ids = [
            row[0]
            for row in db.query(SessionModel.session_id).filter(
                SessionModel.project_id == project_id,
                SessionModel.first_imported_at.isnot(None),
                SessionModel.first_imported_at > job.completed_at,
            )
        ]
        if not new_session_ids:
            return 0
        new_quotes = (
            db.query(Quote)
            .filter(
                Quote.project_id == project_id,
                Quote.session_id.in_(new_session_ids),
            )
            .all()
        )
        if not new_quotes:
            return 0

        batch_items = [
            QuoteBatchItem(
                db_id=q.id,
                text=q.text,
                session_id=q.session_id,
                participant_id=q.participant_id,
                topic_label=q.topic_label or "",
                sentiment=q.sentiment or "",
            )
            for q in new_quotes
        ]

        taxonomy_text = build_tag_taxonomy(template)
        framework_groups = (
            db.query(CodebookGroup).filter_by(framework_id=framework_id).all()
        )
        group_ids = [g.id for g in framework_groups]
        tag_defs = (
            db.query(TagDefinition)
            .filter(TagDefinition.codebook_group_id.in_(group_ids))
            .all()
        )
        tag_id_lookup = {td.name.lower().strip(): td.id for td in tag_defs}
        tag_map = build_tag_name_map(template, tag_id_lookup)

        llm_client = LLMClient(settings)
        prompt_tmpl = get_prompt_template("autocode")

        batches = [
            batch_items[i : i + BATCH_SIZE]
            for i in range(0, len(batch_items), BATCH_SIZE)
        ]
        semaphore = asyncio.Semaphore(settings.llm_concurrency)

        async def _batch(
            batch: list[QuoteBatchItem],
        ) -> list[tuple[int, int, float, str]]:
            async with semaphore:
                user_prompt = prompt_tmpl.user.format(
                    codebook_title=template.title,
                    codebook_preamble=template.preamble,
                    formatted_tag_taxonomy=taxonomy_text,
                    formatted_quotes=wrap_untrusted("quotes", build_quote_batch(batch)),
                )
                with telemetry.stage("serve_autocode_reapply"):
                    result = await llm_client.analyze(
                        system_prompt=prompt_tmpl.system,
                        user_prompt=user_prompt,
                        response_model=AutoCodeBatchResult,
                        prompt_template=prompt_tmpl,
                    )
                out: list[tuple[int, int, float, str]] = []
                for a in result.assignments:
                    if a.quote_index < 0 or a.quote_index >= len(batch):
                        continue
                    tag_def_id = resolve_tag_name_to_id(a.tag_name, tag_map)
                    if tag_def_id is None:
                        continue
                    out.append(
                        (batch[a.quote_index].db_id, tag_def_id, a.confidence, a.rationale)
                    )
                return out

        results = await asyncio.gather(
            *(_batch(b) for b in batches), return_exceptions=True
        )

        accepted = 0
        new_proposed = 0
        now = datetime.now(timezone.utc)
        for res in results:
            if isinstance(res, BaseException):
                logger.error("Re-apply batch failed: %s", res)
                continue
            for quote_id, tag_def_id, confidence, rationale in res:
                is_accept = confidence >= threshold
                # Record the proposal on the existing job — audit trail, and it
                # marks the quote as "seen" so a later re-apply won't re-code it.
                db.add(
                    ProposedTag(
                        job_id=job.id,
                        quote_id=quote_id,
                        tag_definition_id=tag_def_id,
                        confidence=confidence,
                        rationale=rationale,
                        status="accepted" if is_accept else "denied",
                        reviewed_at=now,
                    )
                )
                new_proposed += 1
                if is_accept:
                    # Non-clobbering: never overwrite an existing (human or
                    # autocode) tag on this quote.
                    existing = (
                        db.query(QuoteTag)
                        .filter_by(quote_id=quote_id, tag_definition_id=tag_def_id)
                        .first()
                    )
                    if existing is None:
                        db.add(
                            QuoteTag(
                                quote_id=quote_id,
                                tag_definition_id=tag_def_id,
                                source="autocode",
                            )
                        )
                        accepted += 1

        job.total_quotes += len(batch_items)
        job.proposed_count += new_proposed
        job.completed_at = now
        db.commit()
        logger.info(
            "Re-apply %s: %d new quotes, %d proposals, %d auto-accepted at >=%.2f",
            framework_id,
            len(batch_items),
            new_proposed,
            accepted,
            threshold,
        )
        return accepted

    except Exception as exc:
        logger.exception("Re-apply failed for %s: %s", framework_id, exc)
        db.rollback()
        return 0
    finally:
        db.close()


async def reapply_active_frameworks(
    db_factory: Callable[[], SASession],
    project_id: int,
    settings: BristlenoseSettings,
) -> dict[str, int]:
    """Re-apply every already-applied framework in a project to its new quotes.

    Called after a re-run that added sessions: for each framework with a
    completed AutoCode job, code the delta at that job's stored cutoff. Each is a
    safe no-op if there are no new quotes. Returns ``{framework_id: n_accepted}``.

    Runs the frameworks sequentially so spend stays legible in the logs. Note:
    "previously applied" is the gate today; once the enable/disable toggle is
    persisted this should also skip disabled frameworks.
    """
    from bristlenose.server.models import AutoCodeJob

    db = db_factory()
    try:
        framework_ids = [
            row[0]
            for row in db.query(AutoCodeJob.framework_id)
            .filter_by(project_id=project_id, status="completed")
            .distinct()
        ]
    finally:
        db.close()

    results: dict[str, int] = {}
    for framework_id in framework_ids:
        results[framework_id] = await reapply_to_new_quotes(
            db_factory, project_id, framework_id, settings
        )
    return results
