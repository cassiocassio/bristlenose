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
from typing import TYPE_CHECKING, Any

from bristlenose.llm.failure_classifier import classify_exception
from bristlenose.server.codebook import CodebookTemplate, TemplateGroup, TemplateTag

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from sqlalchemy.orm import Session as SASession

    from bristlenose.config import BristlenoseSettings
    from bristlenose.server.models import AutoCodeJob

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
        from bristlenose.output_paths import project_output_dir

        run_dir = project_output_dir(project_dir) / ".bristlenose"
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
        # (framework groups have framework_id set on the CodebookGroup).
        # Sync first: the taxonomy above came from the YAML, and a tag the
        # YAML renamed since import would otherwise resolve to nothing.
        from bristlenose.server.codebook_sync import sync_framework_rows
        from bristlenose.server.models import CodebookGroup

        sync_framework_rows(db, template)
        db.commit()
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
        # Read into locals: ``job`` is reassigned later in this function, so
        # its not-None narrowing does not reach the closure below.
        job_id = job.id
        total_quotes = job.total_quotes

        async def _process_batch(batch: list[QuoteBatchItem]) -> list[ProposedTag] | None:
            nonlocal processed_count
            async with semaphore:
                # Cancellation checkpoint — check DB before starting LLM call.
                # None = not sent, which neither answered nor failed: its
                # sessions stay unstamped (RE#66).
                cancel_db = db_factory()
                try:
                    cancel_job = (
                        cancel_db.query(AutoCodeJob)
                        .filter_by(project_id=project_id, framework_id=framework_id)
                        .first()
                    )
                    if cancel_job and cancel_job.status == "cancelled":
                        return None
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
                            job_id=job_id,
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
                    total_quotes,
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
                            total_quotes,
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
        #
        # Collapse to one proposal per quote (keep highest confidence), as
        # ``reapply_to_new_quotes`` does. ProposedTag is unique on
        # (job_id, quote_id), and the prompt asking for "the single best" tag
        # does not stop a model returning two — so storing both raised
        # IntegrityError at commit and rolled back every batch's proposals.
        batch_errors = 0
        first_error: BaseException | None = None
        best_by_quote: dict[int, ProposedTag] = {}
        for batch_result in batch_results:
            if isinstance(batch_result, BaseException):
                logger.error("Batch failed: %s", batch_result)
                batch_errors += 1
                if first_error is None:
                    first_error = batch_result
                continue
            if batch_result is None:
                continue  # not sent: the job was stopped
            for proposal in batch_result:
                prev = best_by_quote.get(proposal.quote_id)
                if prev is None or proposal.confidence > prev.confidence:
                    best_by_quote[proposal.quote_id] = proposal
        for proposal in best_by_quote.values():
            db.add(proposal)
            proposed_count += 1
        # The sessions this pass coded, in the same transaction as their
        # proposals; a session in a batch that failed or was never sent stays
        # owed, and the next re-apply codes it (RE#66).
        stamp_sessions(
            db, job_id, _session_pks(db, project_id, _sessions_answered(batches, batch_results)),
        )

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
        # `completed_at` is NOT a timestamp of "the job stopped" — it means
        # "applied at least once", and three things read it that way. It gates
        # `reapply_active_frameworks`' ever-applied set and every re-apply; its
        # presence is how `reconcile_orphaned_jobs` tells an initial-apply orphan
        # from an interrupted catch-up; and Apply refuses a job that has it. Which
        # sessions are coded is the stamps' job, not this one's (RE#66).
        #
        # So setting it on a job that coded nothing is worse than cosmetic: the
        # framework would join the maintained set having applied nothing, and
        # Apply would refuse the retry. Left NULL, the job is exactly the shape
        # the rest of the system already calls an initial-apply orphan, and a
        # retry codes the whole corpus as it should.
        #
        # A genuine partial sets it: some quotes really were coded, and the
        # sessions in its failed batches carry no stamp, so the next re-apply
        # codes them.
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


def _sessions_answered(
    batches: list[list[QuoteBatchItem]], results: list[Any],
) -> set[str]:
    """The sessions whose every quote sent in this pass was in a batch that
    answered. A batch that failed (an exception) or was never sent (None) leaves
    each of its sessions owed, wherever else that session's quotes went."""
    answered: set[str] = set()
    missed: set[str] = set()
    for batch, result in zip(batches, results, strict=True):
        ok = result is not None and not isinstance(result, BaseException)
        (answered if ok else missed).update(item.session_id for item in batch)
    return answered - missed


def _session_pks(db: SASession, project_id: int, session_ids: set[str]) -> list[int]:
    """Session row ids for a project's ``"s1"``-style session ids."""
    from bristlenose.server.models import Session as SessionModel

    if not session_ids:
        return []
    return [
        row[0]
        for row in db.query(SessionModel.id).filter(
            SessionModel.project_id == project_id,
            SessionModel.session_id.in_(sorted(session_ids)),
        )
    ]


def stamp_sessions(db: SASession, job_id: int, session_pks: Iterable[int]) -> None:
    """Record the sessions ``job_id`` has coded. Uncommitted: the caller commits
    them with the proposals they stand for."""
    from bristlenose.server.models import AutoCodeSessionStamp

    for pk in session_pks:
        db.add(AutoCodeSessionStamp(job_id=job_id, session_id=pk))


def owed_sessions(db: SASession, job: AutoCodeJob) -> dict[str, int]:
    """The sessions ``job`` still owes, ``{"s1": Session.id}``: a session with at
    least one quote and no stamp from this job (RE#66).

    This replaced the watermark (``first_imported_at > completed_at``), which a
    partial failure moved past the sessions it never coded. A session with no
    quotes is not owed: nothing would be sent, and a catch-up chip over it would
    say "Re-coded" over nothing.
    """
    from sqlalchemy import exists, select

    from bristlenose.server.models import AutoCodeSessionStamp, Quote
    from bristlenose.server.models import Session as SessionModel

    stamped = select(AutoCodeSessionStamp.session_id).where(
        AutoCodeSessionStamp.job_id == job.id
    )
    has_quote = exists().where(
        Quote.project_id == SessionModel.project_id,
        Quote.session_id == SessionModel.session_id,
    )
    return {
        row[0]: row[1]
        for row in db.query(SessionModel.session_id, SessionModel.id).filter(
            SessionModel.project_id == job.project_id,
            SessionModel.id.not_in(stamped),
            has_quote,
        )
    }


def delete_jobs(db: SASession, job_ids: list[int]) -> None:
    """Delete AutoCode jobs with their proposals and stamps (uncommitted): an
    uninstall, or Apply replacing a job that was never applied."""
    from bristlenose.server.models import AutoCodeJob, AutoCodeSessionStamp, ProposedTag

    if not job_ids:
        return
    for model in (AutoCodeSessionStamp, ProposedTag):
        db.query(model).filter(model.job_id.in_(job_ids)).delete(synchronize_session=False)
    db.query(AutoCodeJob).filter(AutoCodeJob.id.in_(job_ids)).delete(
        synchronize_session=False
    )


# The live re-apply task per (project, framework). Both re-apply paths register
# here: the on-enable catch-up (routes/data.py `_schedule_catch_up`) and a
# finished run's (`reapply_active_frameworks`). Each asks before coding a
# framework, so two never code the same new sessions at once; the loser of that
# race hit the (job, quote) unique constraint and rolled back (R12 wave 6). The
# task, never the job row, answers: a row can say "running" with no task behind
# it (a failed status write, a schedule that raised), 06cceb97.
_REAPPLY_IN_FLIGHT: dict[tuple[int, str], Any] = {}


def live_reapply(project_id: int, framework_id: str) -> Any | None:
    """The re-apply task still coding this framework, or None."""
    task = _REAPPLY_IN_FLIGHT.get((project_id, framework_id))
    return task if task is not None and not task.done() else None


def register_reapply(project_id: int, framework_id: str, task: Any) -> None:
    """Record ``task`` as the one coding this framework until it ends."""
    key = (project_id, framework_id)
    _REAPPLY_IN_FLIGHT[key] = task

    def _forget(t: Any) -> None:
        if _REAPPLY_IN_FLIGHT.get(key) is t:
            del _REAPPLY_IN_FLIGHT[key]

    task.add_done_callback(_forget)


def _set_job_status(
    db: SASession,
    project_id: int,
    framework_id: str,
    status: str,
    error: str | None = None,
    when: str | None = None,
    failure_kind: str | None = None,
) -> None:
    """Best-effort update of an AutoCodeJob's status for the on-enable catch-up chip.

    ``when`` guards the write to fire only if the job is currently in that status —
    used by the finally-restore, which flips a *still-"running"* job to "completed"
    but leaves an already-terminal (failed/completed) one alone. A "cancelled" job
    is never overwritten: the researcher's Stop stands, whatever the catch-up then
    met. "completed" clears an earlier failure's ``error_message`` and
    ``failure_kind``. Never raises.
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
        if j.status == "cancelled":
            # Terminal: a catch-up that fails after a Stop wrote "failed" over it
            # (R12 wave 6).
            return
        j.status = status
        if status == "completed":
            # A catch-up that worked has nothing to report; the last failed one's
            # kind and message would be read as this one's (R12 wave 6).
            j.error_message = ""
            j.failure_kind = ""
        if error is not None:
            j.error_message = error
        if failure_kind is not None:
            j.failure_kind = failure_kind
        db.commit()
    except Exception:
        logger.exception("Could not set catch-up job status for %s", framework_id)
        db.rollback()


def _clear_failure_once_owed_nothing(db: SASession, job: AutoCodeJob) -> None:
    """A run's re-apply that leaves nothing owed has coded what a failed or
    stopped catch-up, or a partial first apply, left, so the job says so (#61,
    RE#66): it read "failed" with the old error until the next catch-up, and a
    partial first apply ("completed" with its failure) kept its failure for good.
    Uncommitted; one UPDATE that a running or pending row refuses, so a
    catch-up's own status is never written over."""
    from sqlalchemy import or_

    from bristlenose.server.models import AutoCodeJob

    if owed_sessions(db, job):
        return
    db.query(AutoCodeJob).filter(
        AutoCodeJob.id == job.id,
        AutoCodeJob.status.not_in(("running", "pending")),
        or_(
            AutoCodeJob.status.in_(("failed", "cancelled")),
            AutoCodeJob.failure_kind != "",
            AutoCodeJob.error_message != "",
        ),
    ).update(
        {AutoCodeJob.status: "completed", AutoCodeJob.error_message: "",
         AutoCodeJob.failure_kind: ""},
        synchronize_session=False,
    )


def reconcile_orphaned_jobs(db: SASession, project_id: int | None = None) -> int:
    """Reset AutoCodeJob rows stranded ``pending``/``running`` by a crash.

    An AutoCode job lives only as an in-process ``asyncio`` task, so no job can
    survive a serve restart. Any row still ``pending``/``running`` at startup was
    orphaned by a crash (SIGKILL, parent-death mid-LLM, mid-catch-up): its
    ``finally`` restore never ran, so its persisted status is a lie the UI keeps
    showing forever — CodebookPanel renders that framework's AutoCode button
    disabled/"running" until a successful catch-up or manual re-run resets it.

    Two orphan classes, told apart by ``completed_at`` — the "applied at least once"
    flag ``reapply_active_frameworks`` already trusts over ``status`` (see ca944a0a):

    - **Initial-apply orphan** (``completed_at IS NULL``): ``run_autocode_job``
      crashed before finishing the first pass, so nothing usable was produced →
      mark ``failed`` with a retryable ``error_message``. The start-job guard
      treats ``failed`` as a dead job and clears it on the next run.
    - **Catch-up orphan** (``completed_at IS NOT NULL``): the on-enable catch-up
      set an applied job ``running`` and was cut off before it finished → mark
      ``failed``, unclassified, so a chip still polling a restarted serve says
      "Tagging failed." rather than "Re-coded" over nothing (#63, RE#66). It wrote
      no stamp, so its sessions are still owed and the next run or re-enable
      codes them; ``completed_at`` keeps the codebook maintained, and Apply
      refuses an applied job, so ``failed`` no longer invites a re-Apply that
      would delete the original proposals. Until 22 Oct 2026 this restored
      ``completed`` with the catch-up's counts at zero.

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
            # Catch-up orphan: applied, but this catch-up never finished. Its
            # sessions carry no stamp, so they are owed whatever this says.
            job.status = "failed"
            job.failure_kind = ""
            job.error_message = (
                "Re-coding was interrupted before it finished (the app closed or "
                "crashed mid-run). The sessions it had not coded are coded next time."
            )
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
    """Re-apply an already-applied framework to the sessions it still owes.

    Codes ONLY the delta — the quotes of sessions with no stamp from the
    framework's job (``owed_sessions``) that have no proposal on it yet — and
    auto-accepts at the researcher's stored cutoff, with no review modal.
    Existing quotes and human tags are never touched (the accept is
    non-clobbering). A session is stamped when every quote sent from it was in a
    batch that answered; one in a batch that failed, or that a Stop or a switch
    turned off never sent, stays owed for the next re-apply (RE#66). Returns the
    number of new QuoteTags created (0 if there's nothing to do).

    Safe no-op when the framework was never applied (no completed job) — so it
    can be fired unconditionally per linked framework after a re-run.

    ``track_status`` (the on-enable catch-up path) makes this own the job's terminal
    status so a frontend activity chip can poll it: the caller sets ``running``
    *synchronously* (to win the chip's first poll), and this restores ``completed``
    on success — or on the no-delta early return — and sets ``failed`` on error.
    A Stop (the job set ``cancelled``) is read before each batch; what had already
    answered is kept and the job stays cancelled (#60).

    The default (the silent ``run_completed`` path) reads the codebook's switch
    before each batch instead, so one switched off mid-way stops at the next
    batch (#62). It touches job status only to clear a failed or stopped
    catch-up's failure once nothing is left owed (#61).
    """
    from sqlalchemy import select

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
        job_id = job.id

        template = get_template(framework_id)
        if not template:
            return 0

        threshold = job.applied_upper_threshold
        if threshold is None:
            threshold = DEFAULT_ACCEPT_THRESHOLD

        # Delta = the quotes of the sessions this job still owes (RE#66). A stamp
        # is per session and written once, so (a) a clean/full re-run of coded
        # sessions doesn't mark them new, and (b) a quote the LLM simply didn't
        # tag in a stamped session is never re-sent (in an owed one it is: the
        # stamp is a cost gate, §4a). Within an owed session, a quote that
        # already has a proposal on this job is skipped: a stopped or partial
        # pass coded it, and a second proposal would break (job, quote).
        # ``completed_at`` is "applied at least once"; never applied, nothing to do.
        if job.completed_at is None:
            return 0
        owed = owed_sessions(db, job)
        if not owed:
            # Nothing owed may still follow a Stop that landed on the last batch,
            # or a failed catch-up whose sessions a re-import withdrew (#61).
            if not track_status:
                _clear_failure_once_owed_nothing(db, job)
                db.commit()
            return 0
        proposed = select(ProposedTag.quote_id).where(ProposedTag.job_id == job_id)
        new_quotes = (
            db.query(Quote)
            .filter(
                Quote.project_id == project_id,
                Quote.session_id.in_(sorted(owed)),
                Quote.id.not_in(proposed),
            )
            .all()
        )
        # An owed session with nothing left to send was coded already.
        done_already = set(owed) - {q.session_id for q in new_quotes}
        if not new_quotes:
            stamp_sessions(db, job_id, [owed[sid] for sid in done_already])
            if not track_status:
                _clear_failure_once_owed_nothing(db, job)
            db.commit()
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
        from bristlenose.server.codebook_sync import sync_framework_rows

        sync_framework_rows(db, template)
        db.commit()
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

        def _halted() -> bool:
            """Read fresh before each batch. A catch-up's Stop sets its job
            "cancelled" (R12 wave 6); a run's re-apply has no Stop, but its
            codebook can be switched off while it codes ("off means off", #62).
            Either way an uninstall ends it: the job is gone, or the codebook no
            longer linked, and every batch after it was paid for and rolled back."""
            check = db_factory()
            try:
                j = check.get(AutoCodeJob, job_id)
                if j is None:
                    return True
                if track_status:
                    return j.status == "cancelled"
                return framework_id not in _maintained_framework_ids(check, project_id)
            finally:
                check.close()

        async def _batch(
            batch: list[QuoteBatchItem],
        ) -> list[tuple[int, int, float, str]] | None:
            async with semaphore:
                # Checked before each batch, as run_autocode_job does, so a Stop
                # or a switch-off ends the spending. None = not sent, which
                # neither answered nor failed: its sessions stay owed.
                if _halted():
                    return None
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
                        logger.warning(
                            "Re-apply %s: invalid quote_index %d in batch of %d",
                            framework_id, a.quote_index, len(batch),
                        )
                        continue
                    tag_def_id = resolve_tag_name_to_id(a.tag_name, tag_map)
                    if tag_def_id is None:
                        continue
                    out.append(
                        (batch[a.quote_index].db_id, tag_def_id, a.confidence, a.rationale)
                    )
                if result.assignments and not out:
                    # Its sessions are stamped all the same: the batch answered.
                    # Said, because a tag rename the sync missed looks like this.
                    logger.warning(
                        "Re-apply %s: a batch answered %d assignments and none named "
                        "a tag in the codebook", framework_id, len(result.assignments),
                    )
                return out

        results = await asyncio.gather(
            *(_batch(b) for b in batches), return_exceptions=True
        )
        # Every batch failing coded nothing: a failure, through the except below.
        # No session is stamped, so the next catch-up or run codes them. Recorded
        # as "completed", the chip said done (R12 review).
        # Uninstalled while it coded: nothing to keep, and nothing failed. Storing
        # against the deleted job hit the foreign key, which was logged as a
        # failed re-apply (RE#66 review).
        if db.query(AutoCodeJob.id).filter(AutoCodeJob.id == job_id).first() is None:
            logger.info("Re-apply %s: the codebook was removed, nothing kept", framework_id)
            return 0
        failures = [r for r in results if isinstance(r, BaseException)]
        if failures:
            # Each of these is sent again by the next run or re-enable; one that
            # fails every time is paid for every time, so it is said each time.
            missed = sorted({
                item.session_id
                for b, r in zip(batches, results, strict=True)
                if isinstance(r, BaseException)
                for item in b
            })
            logger.warning(
                "Re-apply %s: %d of %d batches failed; sessions still owed: %s",
                framework_id, len(failures), len(results), ", ".join(missed),
            )
        if failures and len(failures) == len(results):
            raise failures[0]
        # Only a batch that answered counts as processed, as in run_autocode_job:
        # the chip reads `processed < total` on a completed job as "some batches
        # failed", and the re-apply grew `total_quotes` alone, so every catch-up
        # that worked said it partly failed.
        processed = sum(
            len(b) for b, r in zip(batches, results, strict=True)
            if r is not None and not isinstance(r, BaseException)
        )

        accepted = 0
        new_proposed = 0
        now = datetime.now(timezone.utc)

        # Collapse to one proposal per quote (keep highest confidence). The
        # ProposedTag unique constraint is (job_id, quote_id) — one tag per quote
        # per job — so an LLM that returns two assignments for the same quote would
        # otherwise raise IntegrityError at commit, rolling back the ENTIRE re-apply
        # including its stamps. The same sessions would then be re-selected and
        # re-fail on every subsequent run, forever, silently. Deduping here keeps
        # the collision from ever forming.
        best_by_quote: dict[int, tuple[int, int, float, str]] = {}
        for res in results:
            if isinstance(res, BaseException):
                logger.error("Re-apply batch failed: %s", res)
                continue
            if res is None:
                continue  # not sent: the catch-up was stopped
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
                    job_id=job_id,
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

        # The sessions this pass coded, with the proposals they stand for; the
        # rest stay owed (RE#66).
        coded = done_already | _sessions_answered(batches, list(results))
        stamp_sessions(db, job_id, [owed[sid] for sid in sorted(coded)])

        # Sent, not selected: a Stop or a switch-off leaves batches unsent, and
        # counting them over-reported the denominator.
        sent = sum(len(b) for b, r in zip(batches, results, strict=True) if r is not None)
        counts: dict[Any, Any] = {
            AutoCodeJob.total_quotes: AutoCodeJob.total_quotes + sent,
            AutoCodeJob.processed_quotes: AutoCodeJob.processed_quotes + processed,
            AutoCodeJob.proposed_count: AutoCodeJob.proposed_count + new_proposed,
        }
        values: dict[Any, Any] = {**counts, AutoCodeJob.completed_at: now}
        finish = db.query(AutoCodeJob).filter(AutoCodeJob.id == job_id)
        if track_status:
            # Route set this to "running" for the chip; restore it now, with no
            # failure left from an earlier catch-up, and this catch-up's own
            # counts, which the chip reads: the cumulative pair above keeps any
            # earlier shortfall for good (R12 wave 6).
            values.update({
                AutoCodeJob.status: "completed",
                AutoCodeJob.error_message: "",
                AutoCodeJob.failure_kind: "",
                AutoCodeJob.catch_up_total: len(batch_items),
                AutoCodeJob.catch_up_processed: processed,
            })
            # Unless it was stopped: one UPDATE that a Stop's row refuses, so a
            # Stop landing at any moment before this commit is never written
            # over (an ORM assignment reloaded the job and replaced it).
            finish = finish.filter(AutoCodeJob.status != "cancelled")
        if finish.update(values, synchronize_session=False) == 0:
            # Stopped (#60): what answered is kept, with its stamps, and the job
            # stays cancelled. What the Stop never sent stays owed, so the next
            # catch-up or run codes it. Until 22 Oct 2026 a Stop kept nothing,
            # and the batches already paid for were sent again.
            db.query(AutoCodeJob).filter(AutoCodeJob.id == job_id).update(
                counts, synchronize_session=False,
            )
            db.commit()
            logger.info(
                "Re-apply %s: stopped, kept %d proposals", framework_id, new_proposed,
            )
            return accepted
        if not track_status:
            _clear_failure_once_owed_nothing(db, job)
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
            # Named as run_autocode_job names it, so the chip can say which failure
            # this was (out of credit, rate limited…) and not only "Tagging failed."
            _set_job_status(
                db, project_id, framework_id, "failed", str(exc)[:500],
                failure_kind=classify_exception(settings.llm_provider or None, exc).value,
            )
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


def _maintained_framework_ids(db: SASession, project_id: int) -> set[str]:
    """Frameworks still installed in this project (≥1 linked group) and not
    switched off. Absence of a state row means enabled (the default), so the
    switch only ever excludes."""
    from bristlenose.server.models import (
        CodebookGroup,
        ProjectCodebookGroup,
        ProjectFrameworkState,
    )

    linked = {
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
        if row[0] is not None
    }
    disabled = {
        row[0]
        for row in db.query(ProjectFrameworkState.framework_id).filter_by(
            project_id=project_id, enabled=False
        )
    }
    return linked - disabled


async def reapply_active_frameworks(
    db_factory: Callable[[], SASession],
    project_id: int,
    settings: BristlenoseSettings,
) -> dict[str, int]:
    """Re-apply every already-applied, still-installed, **enabled** framework.

    Called after a re-run that added sessions: for each framework that has an
    applied AutoCode job, is still linked into this project (at least one of its
    groups in ``project_codebook_groups``), and is **not disabled**, code the
    sessions it owes at that job's stored cutoff. Each is a safe no-op if nothing
    is owed. Returns ``{framework_id: n_accepted}``.

    The gate is **ever-applied ∩ currently linked ∩ enabled**, read again just
    before each framework's turn, so one switched off while an earlier one codes
    is not coded (#62, RE#66); ``reapply_to_new_quotes`` reads the switch before
    each batch too. Disable means off ("off means off",
    design-codebook-state-model.md §8): a disabled codebook stops maintaining new
    sessions, so a run while it's off leaves them owed, and re-enabling fires a
    one-shot catch-up over them (routes/data.py `put_framework_states`). "Stop
    tracking entirely" is still **Remove** (drops the link). Runs the frameworks
    one at a time so spend stays legible in the logs.

    A framework an on-enable catch-up is still coding waits for it, then is
    re-applied (finding nothing left, as a rule); every other framework goes
    first, so a long or stuck catch-up holds only its own codebook (#67). Each
    re-apply here is registered while it runs so no catch-up starts over it
    (``_REAPPLY_IN_FLIGHT``).
    """
    from bristlenose.server.models import AutoCodeJob

    db = db_factory()
    try:
        maintained = _maintained_framework_ids(db, project_id)
        # "Ever-applied" is ``completed_at IS NOT NULL``, NOT ``status ==
        # "completed"``: the on-enable catch-up sets a healthy job "running", and
        # a failed or stopped catch-up leaves it "failed" or "cancelled". Gating
        # on status would SILENTLY drop that framework from all future
        # maintenance — new sessions never coded, no error.
        pending = [
            row[0]
            for row in db.query(AutoCodeJob.framework_id)
            .filter(
                AutoCodeJob.project_id == project_id,
                AutoCodeJob.completed_at.isnot(None),
            )
            .order_by(AutoCodeJob.id)
            if row[0] in maintained
        ]
    finally:
        db.close()

    results: dict[str, int] = {}
    while pending:
        ready = [f for f in pending if live_reapply(project_id, f) is None]
        if not ready:
            # Every framework left has a catch-up coding it: wait for the first to
            # end. asyncio.wait never cancels the catch-ups if this is cancelled.
            live = {t for f in pending if (t := live_reapply(project_id, f)) is not None}
            if live:
                await asyncio.wait(live, return_when=asyncio.FIRST_COMPLETED)
            continue
        framework_id = ready[0]
        pending.remove(framework_id)
        db = db_factory()
        try:
            still_on = framework_id in _maintained_framework_ids(db, project_id)
        finally:
            db.close()
        if not still_on:
            logger.info("Re-apply %s: switched off or removed since the run ended", framework_id)
            continue
        task = asyncio.ensure_future(
            reapply_to_new_quotes(db_factory, project_id, framework_id, settings)
        )
        register_reapply(project_id, framework_id, task)
        results[framework_id] = await task
    return results
