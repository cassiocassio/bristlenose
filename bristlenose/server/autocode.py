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

from bristlenose.llm.failure_classifier import classify_exception
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
                # Commit incremental progress via a separate short-lived session so
                # the status endpoint sees the counter tick (the main session holds
                # the proposals transaction until all batches finish). Two rules make
                # this safe under concurrency:
                #
                #  1. A **write-only atomic UPDATE** (no SELECT-then-modify). A
                #     read-then-write transaction takes a read snapshot and then
                #     upgrades to a writer — and if another connection is writing,
                #     SQLite returns "database is locked" *immediately* (it can't wait
                #     without risking deadlock), which no busy_timeout can rescue. A
                #     bare UPDATE is write-only, so busy_timeout serialises it cleanly.
                #  2. **Never fatal.** The proposals are the payload; this counter is
                #     cosmetic. A failed progress write must not propagate out of the
                #     batch — doing so made `gather` treat the batch as failed and
                #     discard its proposals, so a full LLM batch landed as
                #     "0 proposals" (verified 26 Jul 2026 against Bristlenose UXR /
                #     JJG on the IKEA data: 38 proposals returned, all lost).
                async with progress_lock:
                    progress_db = db_factory()
                    try:
                        progress_db.query(AutoCodeJob).filter_by(
                            project_id=project_id, framework_id=framework_id
                        ).update(
                            {AutoCodeJob.processed_quotes: processed_count},
                            synchronize_session=False,
                        )
                        progress_db.commit()
                    except Exception:
                        progress_db.rollback()
                        logger.warning(
                            "AutoCode progress update skipped (non-fatal): %d/%d",
                            processed_count,
                            job.total_quotes,
                        )
                    finally:
                        progress_db.close()
                return proposals

        # Gather all batches
        batch_results = await asyncio.gather(
            *(_process_batch(b) for b in batches),
            return_exceptions=True,
        )

        # Store results, handling per-batch errors gracefully.
        #
        # ``return_exceptions=True`` means a batch failure never reaches the
        # outer ``except``, so nothing below it runs — including the classifier.
        # Keeping the first exception is what lets a swallowed failure still be
        # named. Without it, 33 quotes' worth of "credit balance is too low"
        # wrote status="completed", failure_kind=NULL, and the toast reported a
        # partial success whose partial was zero.
        batch_errors = 0
        first_error: BaseException | None = None
        for batch_result in batch_results:
            if isinstance(batch_result, BaseException):
                logger.error("Batch failed: %s", batch_result)
                batch_errors += 1
                if first_error is None:
                    first_error = batch_result
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

        # Every batch died ⇒ the job FAILED. "completed" with processed=0 is a
        # total failure wearing a partial-success costume: the toast rendered
        # "Tagged 0 of 33 quotes — some batches failed" (a warning) and offered
        # View Report, which opened an empty modal. Name it instead — the
        # classifier already knows out-of-credit from rate-limited, and
        # autocodeFailure.ts already has the sentence for each.
        #
        # A genuine partial (some batches landed) stays "completed" — it has
        # usable proposals — but carries failure_kind so the surface can say
        # *why* the rest are missing rather than leaving it to be guessed.
        if batch_errors and first_error is not None:
            job.failure_kind = classify_exception(
                job.llm_provider or None, first_error
            ).value
            job.error_message = str(first_error)
        nothing_landed = processed_count == 0 and bool(batch_errors)
        job.status = "failed" if nothing_landed else "completed"
        job.processed_quotes = processed_count
        job.proposed_count = proposed_count
        job.input_tokens = llm_client.tracker.input_tokens
        job.output_tokens = llm_client.tracker.output_tokens
        # `completed_at` is NOT a timestamp of "the job stopped" — it is the
        # applied watermark, and three things read it that way. It gates
        # `reapply_active_frameworks`' ever-applied set; it is the cutoff
        # `reapply_to_new_quotes` codes the delta *after*; and its presence is
        # how `reconcile_orphaned_jobs` tells an initial-apply orphan from an
        # interrupted catch-up.
        #
        # So stamping it on a job that coded nothing is worse than cosmetic: the
        # framework joins the maintained set having applied nothing, and every
        # future catch-up codes only sessions imported *since the failure* — the
        # quotes it was installed for sit before the watermark and are never
        # revisited. Left NULL, the job is exactly the shape the rest of the
        # system already calls an initial-apply orphan, and a retry codes the
        # whole corpus as it should.
        #
        # A genuine partial keeps its stamp: some quotes really were coded, so
        # the delta is the right unit of work from here.
        if not nothing_landed:
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
                # Name the failure. str(exc) cannot tell an exhausted account
                # from a rate limit — Anthropic returns 400 for both — and
                # telling a bankrupt researcher to "try again shortly" is the
                # specific bug the classifier was written for.
                job.failure_kind = classify_exception(
                    job.llm_provider or None, exc
                ).value
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


def _set_job_status(
    db: SASession,
    project_id: int,
    framework_id: str,
    status: str,
    error: str | None = None,
    when: str | None = None,
) -> None:
    """Best-effort update of an AutoCodeJob's status for the on-enable catch-up chip.

    ``when`` guards the write to fire only if the job is currently in that status —
    used by the finally-restore, which flips a *still-"running"* job to "completed"
    but leaves an already-terminal (failed/completed) one alone. Never raises.
    """
    from bristlenose.server.models import AutoCodeJob

    try:
        j = (
            db.query(AutoCodeJob)
            .filter_by(project_id=project_id, framework_id=framework_id)
            .first()
        )
        if j is None or (when is not None and j.status != when):
            return
        j.status = status
        if error is not None:
            j.error_message = error
        db.commit()
    except Exception:
        logger.exception("Could not set catch-up job status for %s", framework_id)
        db.rollback()


def reconcile_orphaned_jobs(db: SASession, project_id: int | None = None) -> int:
    """Reset AutoCodeJob rows stranded ``pending``/``running`` by a crash.

    An AutoCode job lives only as an in-process ``asyncio`` task, so no job can
    survive a serve restart. Any row still ``pending``/``running`` at startup was
    orphaned by a crash (SIGKILL, parent-death mid-LLM, mid-catch-up): its
    ``finally`` restore never ran, so its persisted status is a lie the UI keeps
    showing forever — CodebookPanel renders that framework's AutoCode button
    disabled/"running" until a successful catch-up or manual re-run resets it.

    Two orphan classes, told apart by ``completed_at`` — the same watermark
    ``reapply_active_frameworks`` already trusts over ``status`` (see ca944a0a):

    - **Initial-apply orphan** (``completed_at IS NULL``): ``run_autocode_job``
      crashed before finishing the first pass, so nothing usable was produced →
      mark ``failed`` with a retryable ``error_message``. The start-job guard
      treats ``failed`` as a dead job and clears it on the next run.
    - **Catch-up orphan** (``completed_at IS NOT NULL``): the on-enable catch-up
      transiently flipped an already-completed job to ``running`` and crashed
      before its ``finally`` restored ``completed``. The initial apply DID finish
      → restore ``completed`` (exactly what the finally would have done). Marking
      it ``failed`` would misreport a framework that has real applied tags.

    Runs synchronously at startup, before the event watcher and before any new
    job can be created in this process, so an unconditional sweep is safe — there
    is no genuinely in-flight job to misclassify, hence no time threshold. Returns
    the number of rows changed.
    """
    from bristlenose.server.models import AutoCodeJob

    query = db.query(AutoCodeJob).filter(
        AutoCodeJob.status.in_(("pending", "running"))
    )
    if project_id is not None:
        query = query.filter(AutoCodeJob.project_id == project_id)

    changed = 0
    for job in query.all():
        if job.completed_at is not None:
            # Catch-up orphan: the initial apply finished; only the transient
            # chip-status flip was interrupted. Restore the true state.
            job.status = "completed"
        else:
            # Initial-apply orphan: never completed. Fail it so the UI stops
            # showing "running" and offers a retry.
            job.status = "failed"
            job.error_message = (
                "AutoCode was interrupted before it finished (the app closed "
                "or crashed mid-run). Run it again to retry."
            )
        changed += 1

    if changed:
        db.commit()
    return changed


async def reapply_to_new_quotes(
    db_factory: Callable[[], SASession],
    project_id: int,
    framework_id: str,
    settings: BristlenoseSettings,
    track_status: bool = False,
) -> int:
    """Re-apply an already-applied framework to the quotes it hasn't seen yet.

    Codes ONLY the delta — quotes with no ``ProposedTag`` from the framework's
    existing job (i.e. newly-added ones) — and auto-accepts at the researcher's
    stored cutoff, with no review modal. Existing quotes and human tags are never
    touched (the accept is non-clobbering). Returns the number of new QuoteTags
    created (0 if there's nothing to do).

    Safe no-op when the framework was never applied (no completed job) — so it
    can be fired unconditionally per linked framework after a re-run.

    ``track_status`` (the on-enable catch-up path) makes this own the job's terminal
    status so a frontend activity chip can poll it: the caller sets ``running``
    *synchronously* (to win the chip's first poll), and this restores ``completed``
    on success — or on the no-delta early return — and sets ``failed`` on error.
    The default (the silent ``run_completed`` path) never touches job status.
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
    failed = False
    try:
        # One job per (project, framework) — the unique constraint — so no status
        # filter is needed to pick it out. We deliberately DON'T filter status here:
        # the on-enable catch-up sets the job to "running" before this runs (to win
        # the activity chip's first poll), and a status filter would then miss it.
        # "Never applied" is caught by the completed_at guard below, not by status.
        job = (
            db.query(AutoCodeJob)
            .filter_by(project_id=project_id, framework_id=framework_id)
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

        # Collapse to one proposal per quote (keep highest confidence). The
        # ProposedTag unique constraint is (job_id, quote_id) — one tag per quote
        # per job — so an LLM that returns two assignments for the same quote would
        # otherwise raise IntegrityError at commit, rolling back the ENTIRE re-apply
        # including the completed_at watermark advance below. That makes the same
        # new sessions re-selected and re-fail on every subsequent run, forever,
        # silently. Deduping here keeps the collision from ever forming.
        best_by_quote: dict[int, tuple[int, int, float, str]] = {}
        for res in results:
            if isinstance(res, BaseException):
                logger.error("Re-apply batch failed: %s", res)
                continue
            for quote_id, tag_def_id, confidence, rationale in res:
                prev = best_by_quote.get(quote_id)
                if prev is None or confidence > prev[2]:
                    best_by_quote[quote_id] = (quote_id, tag_def_id, confidence, rationale)

        for quote_id, tag_def_id, confidence, rationale in best_by_quote.values():
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
        if track_status:
            # Route set this to "running" for the chip; restore it now.
            job.status = "completed"
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
        failed = True
        if track_status:
            _set_job_status(db, project_id, framework_id, "failed", str(exc)[:500])
        return 0
    finally:
        # Any early `return 0` left the job as the route set it ("running"); restore
        # it so the chip's poll resolves and never spins forever. No-op on success
        # (already "completed"). Guarded by `failed` so a genuinely-failed run whose
        # "failed" write had to retry (DB lock) is never silently upgraded to
        # "completed" here — a false success signal on lost work.
        if track_status and not failed:
            _set_job_status(db, project_id, framework_id, "completed", when="running")
        db.close()


async def reapply_active_frameworks(
    db_factory: Callable[[], SASession],
    project_id: int,
    settings: BristlenoseSettings,
) -> dict[str, int]:
    """Re-apply every already-applied, still-installed, **enabled** framework.

    Called after a re-run that added sessions: for each framework that has a
    completed AutoCode job, is still linked into this project (at least one of its
    groups in ``project_codebook_groups``), and is **not disabled**, code the delta
    at that job's stored cutoff. Each is a safe no-op if there are no new quotes.
    Returns ``{framework_id: n_accepted}``.

    The gate is **ever-applied ∩ currently linked ∩ enabled**. Disable means
    off ("off means off", design-codebook-state-model.md §8): a disabled codebook
    stops maintaining new sessions, so a run while it's off leaves the new quotes
    uncoded. Its watermark (`AutoCodeJob.completed_at`) freezes; re-enabling fires a
    one-shot catch-up over everything added since (routes/data.py `put_framework_
    states`). "Stop tracking entirely" is still **Remove** (drops the link). Runs
    the frameworks sequentially so spend stays legible in the logs.
    """
    from bristlenose.server.models import (
        AutoCodeJob,
        CodebookGroup,
        ProjectCodebookGroup,
        ProjectFrameworkState,
    )

    db = db_factory()
    try:
        # Frameworks still installed in this project (≥1 linked group).
        linked_framework_ids = {
            row[0]
            for row in db.query(CodebookGroup.framework_id)
            .join(
                ProjectCodebookGroup,
                ProjectCodebookGroup.codebook_group_id == CodebookGroup.id,
            )
            .filter(
                ProjectCodebookGroup.project_id == project_id,
                CodebookGroup.framework_id.isnot(None),
            )
            .distinct()
        }
        # Frameworks explicitly turned OFF (enabled=False). Absence of a row means
        # enabled (the default) — so this only ever *excludes*, never requires a row.
        disabled_framework_ids = {
            row[0]
            for row in db.query(ProjectFrameworkState.framework_id).filter_by(
                project_id=project_id, enabled=False
            )
        }
        # Gate = ever-applied ∩ currently linked ∩ enabled. "Ever-applied" is
        # ``completed_at IS NOT NULL``, NOT ``status == "completed"``: the on-enable
        # catch-up transiently sets a healthy job to "running", and a crash in that
        # window (SIGKILL, parent-death mid-LLM) would leave it stuck "running"
        # forever. Gating on status would then SILENTLY drop that framework from all
        # future maintenance — new sessions never coded, no error. completed_at is
        # the real "has been applied at least once" predicate and survives the
        # transient status, so a crashed catch-up self-heals on the next run.
        framework_ids = [
            row[0]
            for row in db.query(AutoCodeJob.framework_id)
            .filter(
                AutoCodeJob.project_id == project_id,
                AutoCodeJob.completed_at.isnot(None),
            )
            .distinct()
            if row[0] in linked_framework_ids
            and row[0] not in disabled_framework_ids
        ]
    finally:
        db.close()

    results: dict[str, int] = {}
    for framework_id in framework_ids:
        results[framework_id] = await reapply_to_new_quotes(
            db_factory, project_id, framework_id, settings
        )
    return results
