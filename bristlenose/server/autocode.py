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
import contextlib
import difflib
import functools
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bristlenose.llm.failure_classifier import classify_exception
from bristlenose.server.busy import note_progress, tracked
from bristlenose.server.codebook import CodebookTemplate, TemplateGroup, TemplateTag

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from sqlalchemy import ColumnElement
    from sqlalchemy.orm import Session as SASession

    from bristlenose.config import BristlenoseSettings
    from bristlenose.server.models import AutoCodeJob

logger = logging.getLogger(__name__)

#: Number of quotes per LLM call.  Fixed batches give predictable token
#: budgets regardless of session length.
BATCH_SIZE = 25

#: A first apply's opening batches, before the rest go in batches of ``BATCH_SIZE``
#: (docs/design-autocode-landing-plan.md D24, Phase 0b): a call costs about 3 s plus
#: 1.9 s a quote, so the first tags land in about 12 s instead of about 49 s, for about
#: $0.06 more a run. Catch-up passes keep ``BATCH_SIZE``: a researcher is not watching
#: them land from nothing. Each is capped at ``BATCH_SIZE``.
FIRST_APPLY_BATCH_RAMP = (5, 10)

#: How many times one batch's save is tried before the batch is kept in memory and
#: saved with the end of the run, and the wait before each retry (seconds). Each try
#: also waits out the connection's ``busy_timeout`` for the write lock first.
SAVE_ATTEMPTS = 4
SAVE_BACKOFF_S = (0.05, 0.2, 0.5)
#: How long one try waits for the write lock (ms), in place of the connection's 5 s: a
#: long writer elsewhere (a re-import) then costs a batch a deferral of seconds.
SAVE_BUSY_TIMEOUT_MS = 500

#: What a job's stored message says when the database, not the provider, failed it.
#: A database error's text carries SQL and the row it was writing, a participant's words
#: among them, and the message is served by /status: never stored.
NOT_SAVED_MESSAGE = "AutoCode could not save what it coded. Run it again to code the rest."

#: One proposal as a batch answered it: (quote id, tag definition id, confidence,
#: rationale). Plain values, not rows: a save that rolls back leaves an ORM row in a
#: state another session cannot simply take, so each attempt builds its own.
ProposalValues = tuple[int, int, float, str]


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
# Saving a batch as it answers
# ---------------------------------------------------------------------------


@dataclass
class _Answered:
    """A batch the model answered: its proposals (one per quote, the most confident)
    and every quote it sent, tagged or not. ``saved`` is False while it waits in
    memory for the end of the run, its own save having found the database locked."""

    proposals: list[ProposalValues]
    quote_ids: list[int]
    saved: bool = False


def _best_per_quote(rows: Iterable[ProposalValues]) -> list[ProposalValues]:
    """One proposal per quote, the most confident. ``ProposedTag`` is unique on (job,
    quote), and a model asked for "the single best" tag can still return two, which
    failed the commit and took every proposal with it (gotchas.md § AutoCode)."""
    best: dict[int, ProposalValues] = {}
    for row in rows:
        prev = best.get(row[0])
        if prev is None or row[2] > prev[2]:
            best[row[0]] = row
    return list(best.values())


def _is_lock_error(exc: BaseException) -> bool:
    message = str(getattr(exc, "orig", exc)).lower()
    return "locked" in message or "busy" in message


def _db_error_name(exc: BaseException) -> str:
    """An exception's type and SQLite's error name: what a log line may say about a
    failed save. Never its text, which carries the statement and the row."""
    orig = getattr(exc, "orig", None)
    code = getattr(orig, "sqlite_errorname", None) if orig is not None else None
    return f"{type(exc).__name__}{f' {code}' if code else ''}"


def failure_text(provider: str | None, exc: BaseException) -> tuple[str, str]:
    """(stored message, ``failure_kind``) for a pass that failed with ``exc``. A
    database failure (or a save that never took) gets a fixed message and no kind: it is
    not the provider's, and its text is not for a stored, served field."""
    from sqlalchemy.exc import SQLAlchemyError

    if isinstance(exc, (SQLAlchemyError, _NotSavedError)):
        return NOT_SAVED_MESSAGE, ""
    from bristlenose.llm.client import failure_summary

    return failure_summary(exc), classify_exception(provider, exc).value


def _is_db_error(exc: BaseException) -> bool:
    from sqlalchemy.exc import SQLAlchemyError

    return isinstance(exc, (SQLAlchemyError, _NotSavedError))


class _NotSavedError(Exception):
    """A save that ran out of tries: what it held stays owed."""


def _in_memory(db_factory: Callable[[], SASession]) -> bool:
    """An in-memory database is one connection a worker thread cannot share (each thread
    gets its own, empty), so its saves stay on the loop."""
    probe = db_factory()
    try:
        return probe.get_bind().engine.url.database in (None, "", ":memory:")
    finally:
        probe.close()


def _try_save(
    db_factory: Callable[[], SASession], write: Callable[[SASession], Any],
) -> tuple[str, Any, str]:
    """One try, on whatever thread: ("saved", value, ""), or ("locked" | "failed", None,
    the error's name). Never raises. The write-lock wait is ``SAVE_BUSY_TIMEOUT_MS`` for
    the try, and the connection's own is put back before it returns to the pool."""
    from sqlalchemy.exc import OperationalError

    db: SASession | None = None
    restore: Any = None
    try:
        db = db_factory()
        conn = db.connection()
        restore = conn.exec_driver_sql("PRAGMA busy_timeout").scalar()
        conn.exec_driver_sql(f"PRAGMA busy_timeout={int(SAVE_BUSY_TIMEOUT_MS)}")
        value = write(db)
        db.commit()
        return "saved", value, ""
    except Exception as exc:
        if db is not None:
            with contextlib.suppress(Exception):
                db.rollback()
        locked = isinstance(exc, OperationalError) and _is_lock_error(exc)
        return ("locked" if locked else "failed"), None, _db_error_name(exc)
    finally:
        if db is not None:
            if restore is not None:
                with contextlib.suppress(Exception):
                    db.connection().exec_driver_sql(f"PRAGMA busy_timeout={int(restore)}")
            with contextlib.suppress(Exception):
                db.close()


async def _save_batch(
    db_factory: Callable[[], SASession],
    write: Callable[[SASession], Any],
    what: str,
) -> tuple[bool, Any]:
    """Save one answered batch in its own short transaction: ``(True, write's value)``,
    or ``(False, None)`` when it could not be saved and the caller must keep it. Never
    raises: a paid, answered batch must never become a batch failure, still less one
    named as the provider's.

    The save reads before it writes (the register skips a quote already on it; a
    catch-up reads the lines it sorts by), and SQLite refuses such a transaction at
    once when another connection has written since its read, whatever the
    ``busy_timeout`` (gotchas.md § AutoCode). So a locked or busy database rolls back,
    closes, waits a moment and tries again in a fresh session; when the tries run out
    the batch stays with the caller. Any other failure is not retried. Each try runs
    on a worker thread (a file database), so a wait for the lock never holds the event
    loop, and the serve's other routes, /status and /api/background-work, answer.
    """
    try:
        off_loop = not _in_memory(db_factory)
        for attempt in range(SAVE_ATTEMPTS):
            if off_loop:
                outcome, value, why = await asyncio.to_thread(_try_save, db_factory, write)
            else:
                outcome, value, why = _try_save(db_factory, write)
            if outcome == "saved":
                return True, value
            if outcome == "failed":
                logger.warning("AutoCode %s: the save failed (%s); the batch is kept", what, why)
                return False, None
            if attempt + 1 < SAVE_ATTEMPTS:
                await asyncio.sleep(SAVE_BACKOFF_S[min(attempt, len(SAVE_BACKOFF_S) - 1)])
        logger.warning(
            "AutoCode %s: the database stayed locked through %d tries; the batch is kept",
            what, SAVE_ATTEMPTS,
        )
    except Exception as exc:
        logger.warning("AutoCode %s: the save could not run (%s)", what, _db_error_name(exc))
    return False, None


def first_apply_batches(items: list[QuoteBatchItem]) -> list[list[QuoteBatchItem]]:
    """A first apply's quotes in batches, in the order given: ``FIRST_APPLY_BATCH_RAMP``
    first (each capped at ``BATCH_SIZE``), then ``BATCH_SIZE`` each (D24)."""
    sizes = [min(size, BATCH_SIZE) for size in FIRST_APPLY_BATCH_RAMP]
    batches: list[list[QuoteBatchItem]] = []
    start = 0
    while start < len(items):
        size = sizes[len(batches)] if len(batches) < len(sizes) else BATCH_SIZE
        batches.append(items[start : start + size])
        start += size
    return batches


def _store_pending_batch(db: SASession, job_id: int, answered: _Answered) -> int:
    """A first apply's batch: its proposals, its quotes on the register, the job's
    proposal count, and the live acceptance its arrival allows (``accept_live``), in one
    transaction (uncommitted). Answers how many proposals were accepted live."""
    from bristlenose.server.models import AutoCodeJob, ProposedTag

    for quote_id, tag_def_id, confidence, rationale in answered.proposals:
        db.add(ProposedTag(
            job_id=job_id, quote_id=quote_id, tag_definition_id=tag_def_id,
            confidence=confidence, rationale=rationale,
        ))
    record_sent(db, job_id, answered.quote_ids)
    if answered.proposals:
        # Followed per batch so a crash between batches leaves the count true: the boot
        # sweep (reconcile_orphaned_jobs) keeps the row's counts as they are.
        db.query(AutoCodeJob).filter(AutoCodeJob.id == job_id).update(
            {AutoCodeJob.proposed_count: AutoCodeJob.proposed_count + len(answered.proposals)},
            synchronize_session=False,
        )
    # With the batch, in its transaction: a batch's proposals and the acceptance they allow
    # land together, and this save's retries are the acceptance's. In a savepoint, so it can
    # never cost the batch its save: one that fails rolls back alone, the proposals are
    # saved, and the run's end cut accepts what it missed (``begin_nested`` flushes the
    # batch's rows first: flushed here, so their own errors still fail the save as before).
    db.flush()
    try:
        with db.begin_nested():
            return accept_live(db, job_id)
    except Exception as exc:
        logger.warning(
            "AutoCode job %d: live acceptance skipped for a batch (%s); its end cut catches up",
            job_id, _db_error_name(exc),
        )
        return 0


# ---------------------------------------------------------------------------
# Job runner
# ---------------------------------------------------------------------------


#: First applies whose runner is still coding or settling, by (project, framework): a Stop
#: marks the job "cancelled" at once, but its batches out still answer and its cut lands
#: after them (D27). The status read reports it (``ending``), so the page refreshes its
#: lenses once the cut has landed rather than at the Stop.
_FIRST_APPLY_CODING: dict[tuple[int, str], int] = {}


def first_apply_ending(project_id: int, framework_id: str) -> bool:
    """Whether a first apply's runner for this codebook has not yet finished."""
    return bool(_FIRST_APPLY_CODING.get((project_id, framework_id)))


@tracked("autocode")
async def run_autocode_job(
    db_factory: Callable[[], SASession],
    project_id: int,
    framework_id: str,
    settings: BristlenoseSettings,
    project_dir: Path | None = None,
) -> int:
    """Execute an AutoCode job: load quotes, batch, call LLM, store proposals.

    Answers how many tags the run's settle made when it ended without finishing (a Stop,
    a failure): its caller asks Signals for a rebuild only if that changed what Signals
    reads (D31). 0 for a run that completed, or whose settle made none.

    This is the top-level coroutine spawned by ``asyncio.create_task()``
    from the API endpoint.  It manages its own DB sessions and handles
    errors gracefully — the caller does not await this.

    A job that a Stop or a failure left never applied keeps what it coded when
    Apply runs it again (#127): only quotes that count and are not on the job's
    register of sent quotes are sent, so nothing is paid for twice and a tag
    the researcher denied stays denied. A first apply has an empty register, and
    sends every quote that counts; one with nothing left to send completes
    without an LLM call.

    When ``project_dir`` is provided, telemetry contextvars are bound for
    the duration of the job so per-call rows land in
    ``<output_dir>/.bristlenose/llm-calls.jsonl``.
    """
    from bristlenose.llm import telemetry
    from bristlenose.llm.client import LLMClient
    from bristlenose.llm.prompts import get_prompt_template
    from bristlenose.llm.structured import AutoCodeBatchResult
    from bristlenose.server.codebook import get_template
    from bristlenose.server.models import (
        AutoCodeJob,
        ProposedTag,
        TagDefinition,
    )
    from bristlenose.server.speaker_slots import analysis_quotes

    # Bind telemetry context for the duration of the job. ``project_dir``
    # may be either the project root or the bristlenose-output dir; resolve
    # to the canonical .bristlenose/ run dir.
    telemetry_tokens: tuple[object, object] | None = None
    if project_dir is not None:
        from bristlenose.output_paths import project_output_dir

        run_dir = project_output_dir(project_dir) / ".bristlenose"
        run_id = f"autocode-{project_id}-{framework_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        telemetry_tokens = telemetry.set_run_context(run_id, run_dir)

    key = (project_id, framework_id)
    _FIRST_APPLY_CODING[key] = _FIRST_APPLY_CODING.get(key, 0) + 1
    #: Tags the settle made, when the run ends without finishing (the outcome's save may be
    #: tried more than once: the try that commits writes it last).
    settled_tags = [0]
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
            return 0

        # If cancelled before the async task started, exit immediately.
        if job.status == "cancelled":
            return 0

        job.status = "running"
        db.commit()

        # Load template
        template = get_template(framework_id)
        if not template:
            job.status = "failed"
            job.error_message = f"Template '{framework_id}' not found"
            # What an earlier pass coded settles, as every end without a finish does.
            out = cut_first_apply(db, job.id, stopped=True)
            db.commit()
            return out.tagged if out is not None else 0

        # Load the quotes that count: a hidden quote is discounted evidence and
        # counts nowhere, a recoded speaker's quotes have left the evidence
        # (owner, 22 Oct 2026; N175). Sending them paid for tags nobody sees.
        quotes_rows = analysis_quotes(db, project_id)
        if not quotes_rows:
            job.status = "completed"
            job.total_quotes = 0
            job.completed_at = datetime.now(timezone.utc)
            cut_first_apply(db, job.id)  # with the outcome, as below
            db.commit()
            return 0

        # What a Stop or a failure left this job is kept (#127): a quote on its
        # register of sent quotes, or with a proposal on it, was paid for, and
        # sending it again paid twice and brought tags the researcher denied back
        # as pending. Until 22 Oct 2026 Apply deleted the job and sent everything.
        sent_ids = sent_quote_ids(db, job.id)
        proposed_ids = {
            row[0] for row in db.query(ProposedTag.quote_id).filter(ProposedTag.job_id == job.id)
        }
        # In stored order, never shuffled (D25, Phase 0c): mixing sessions in a batch moved
        # the answers more than the model's own run-to-run noise. The read has no ORDER BY.
        to_send = sorted((q for q in quotes_rows if q.id not in sent_ids), key=lambda q: q.id)
        already_done = len(quotes_rows) - len(to_send)
        kept_proposals = len(proposed_ids)
        kept_tokens = (job.input_tokens or 0, job.output_tokens or 0)

        job.total_quotes = len(quotes_rows)
        job.processed_quotes = already_done
        if not to_send:
            job.proposed_count = kept_proposals
            db.flush()
            db.expire(job, ["status"])
            # Nothing was left to send, so a Stop since it started had nothing to stop (N94):
            # finished and applied, as for a Stop that lands once every batch has answered.
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            # The cut in the outcome's transaction (a resumed stop's: at its stored lines).
            cut_first_apply(db, job.id)
            db.commit()
            logger.info(
                "AutoCode job %s: every quote was coded by an earlier pass, nothing sent",
                framework_id,
            )
            return 0

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
            for q in to_send
        ]

        job.llm_provider = settings.llm_provider
        job.llm_model = settings.llm_model
        # What the job holds now; each batch adds its own as it saves.
        job.proposed_count = kept_proposals
        db.commit()

        # Build taxonomy text (once, shared across all batches)
        taxonomy_text = build_tag_taxonomy(template)

        logger.info(
            "AutoCode job started: framework=%s quotes=%d (%d coded already) model=%s",
            framework_id,
            len(batch_items),
            already_done,
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
        # Committed now, not with the proposals: left pending, the next read of
        # ``job`` autoflushed it, and this session then held SQLite's one write
        # lock across every batch. Each progress UPDATE below waited out
        # busy_timeout and was skipped, so the counter never moved, and a Stop or
        # a star in the same minutes would have hit the same lock (23 Oct 2026).
        job.prompt_version = prompt_tmpl.version
        db.commit()

        # 5, then 10, then 25 a batch (D24): the first tags land in seconds.
        batches = first_apply_batches(batch_items)

        # Process batches with bounded concurrency
        semaphore = asyncio.Semaphore(settings.llm_concurrency)
        proposed_count = 0
        processed_count = already_done
        progress_lock = asyncio.Lock()
        # Read into locals: ``job`` is reassigned later in this function, so
        # its not-None narrowing does not reach the closure below.
        job_id = job.id
        total_quotes = job.total_quotes

        async def _process_batch(batch: list[QuoteBatchItem]) -> _Answered | None:
            nonlocal processed_count
            async with semaphore:
                # Cancellation checkpoint — check DB before starting LLM call.
                # None = not sent, which neither answered nor failed: its
                # quotes stay off the register, so they stay owed (RE#66).
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
                # Map assignments to proposals
                values: list[ProposalValues] = []
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
                    values.append((
                        quote_item.db_id, tag_def_id, assignment.confidence,
                        assignment.rationale,
                    ))
                answered = _Answered(
                    proposals=_best_per_quote(values),
                    quote_ids=[item.db_id for item in batch],
                )
                # Saved now, with its register entries, so the page can show it while
                # the run goes on and a run cut off later keeps it. Until 23 Nov 2026
                # every batch waited for the last, and a run stopped by a crash at 90%
                # lost them all (docs/design-autocode-landing-plan.md Phase 1).
                answered.saved, live_accepted = await _save_batch(
                    db_factory,
                    lambda session: _store_pending_batch(session, job_id, answered),
                    f"job {framework_id}",
                )
                processed_count += len(batch)
                note_progress(len(batch))
                logger.info(
                    "AutoCode batch done: %d/%d quotes, %d proposals, %d accepted live%s",
                    processed_count,
                    total_quotes,
                    len(answered.proposals),
                    live_accepted or 0,
                    "" if answered.saved else " (kept for the end of the run)",
                )
                # Commit incremental progress via a separate short-lived session so
                # the status endpoint sees the counter tick. Two rules make this safe
                # under concurrency:
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
                            exc_info=True,
                        )
                    finally:
                        progress_db.close()
                return answered

        # Gather all batches
        batch_results = await asyncio.gather(
            *(_process_batch(b) for b in batches),
            return_exceptions=True,
        )

        # Count the results, handling per-batch errors gracefully.
        #
        # ``return_exceptions=True`` means a batch failure never reaches the
        # outer ``except``, so nothing below it runs — including the classifier.
        # Keeping the first exception is what lets a swallowed failure still be
        # named. Without it, 33 quotes' worth of "credit balance is too low"
        # wrote status="completed", failure_kind=NULL, and the toast reported a
        # partial success whose partial was zero.
        #
        # Each answered batch saved itself (one proposal per quote, its register
        # entries with it). A batch whose save found the database locked through
        # every try is saved here, with the end of the run, never dropped.
        batch_errors = 0
        first_error: BaseException | None = None
        for batch_result in batch_results:
            if isinstance(batch_result, BaseException):
                logger.error("Batch failed: %s", batch_result)
                batch_errors += 1
                if first_error is None:
                    first_error = batch_result
        # A batch whose own save found the database locked through every try is tried
        # again now, each in its own transaction with its own retries. One that still
        # cannot be saved is not on the register, so its quotes stay owed, and the run
        # says it fell short (#127 shape: a partial, or failed when nothing landed).
        answered = [r for r in batch_results if isinstance(r, _Answered)]
        for kept in answered:
            if not kept.saved:
                kept.saved, _ = await _save_batch(
                    db_factory, functools.partial(
                        _store_pending_batch, job_id=job_id, answered=kept),
                    f"job {framework_id}, at the end of the run",
                )
        unsaved = [a for a in answered if not a.saved]
        processed_count -= sum(len(a.quote_ids) for a in unsaved)
        proposed_count = sum(len(a.proposals) for a in answered if a.saved)

        logger.info(
            "AutoCode job finished: %d proposals from %d quotes (%d batch errors, "
            "%d batches not saved)",
            proposed_count,
            len(batch_items),
            batch_errors,
            len(unsaved),
        )

        # A Stop that landed while the last batches were out found nothing left to stop:
        # every quote was sent, answered and saved, so the apply finishes as if it had not
        # come (N94). Left cancelled it was never applied, and the codebook it had fully
        # coded stopped following new sessions with nothing to say so. A batch that failed,
        # was never sent or could not be saved leaves quotes owed, and that Stop stands.
        every_quote_answered = all(
            isinstance(r, _Answered) and r.saved for r in batch_results
        )
        # This pass's own batches: what an earlier pass coded does not make a
        # pass that coded nothing a partial success (#127).
        nothing_landed = processed_count == already_done and bool(batch_errors or unsaved)
        # Every batch died ⇒ the job FAILED. "completed" with processed=0 is a
        # total failure wearing a partial-success costume: the toast rendered
        # "Tagged 0 of 33 quotes — some batches failed" (a warning) and offered
        # View Report, which opened an empty modal. Name it instead — the
        # classifier already knows out-of-credit from rate-limited, and
        # autocodeFailure.ts already has the sentence for each.
        #
        # A genuine partial (some batches landed) stays "completed" — it has
        # usable proposals — but carries failure_kind so the surface can say
        # *why* the rest are missing rather than leaving it to be guessed. Never
        # ``str(exc)``: a provider's error is its whole body, which can carry the
        # prompt (participants' quotes) and an echoed key.
        failure: tuple[str, str] | None = None
        if first_error is not None:
            failure = failure_text(job.llm_provider or None, first_error)
        elif unsaved:
            failure = (NOT_SAVED_MESSAGE, "")
        tokens = (
            kept_tokens[0] + llm_client.tracker.input_tokens,
            kept_tokens[1] + llm_client.tracker.output_tokens,
        )

        def _finish(session: SASession) -> str:
            """The job's outcome, in its own transaction, apart from the batches: a
            failure here costs the outcome a retry, never a saved batch."""
            settled_tags[0] = 0
            j = session.get(AutoCodeJob, job_id)
            if j is None:
                return "gone"
            j.processed_quotes = processed_count
            j.proposed_count = kept_proposals + proposed_count
            j.input_tokens, j.output_tokens = tokens
            if j.status == "cancelled" and not every_quote_answered:
                # Keep "cancelled", with what it saved, and settle its cut now that its last
                # batches have answered (D27): no ``completed_at``, so it stays resumable and
                # the house default's marker is not written (D35).
                settle = cut_first_apply(session, job_id, stopped=True)
                settled_tags[0] = settle.tagged if settle is not None else 0
                return "cancelled"
            if failure is not None:
                j.error_message, j.failure_kind = failure
            j.status = "failed" if nothing_landed else "completed"
            # `completed_at` is NOT a timestamp of "the job stopped" — it means
            # "applied at least once", and three things read it that way. It gates
            # `reapply_active_frameworks`' ever-applied set and every re-apply; its
            # presence is how `reconcile_orphaned_jobs` tells an initial-apply orphan
            # from an interrupted catch-up; and Apply refuses a job that has it. Which
            # quotes are coded is the register's job, not this one's (RE#66).
            #
            # So setting it on a job that coded nothing is worse than cosmetic: the
            # framework would join the maintained set having applied nothing, and
            # Apply would refuse the retry. Left NULL, the job is exactly the shape
            # the rest of the system already calls an initial-apply orphan, and a
            # retry codes what no pass has coded yet (#127).
            #
            # A genuine partial sets it: some quotes really were coded, and the
            # ones in its failed or unsaved batches are not on the register, so the
            # next re-apply sends them.
            if not nothing_landed:
                j.completed_at = datetime.now(timezone.utc)
                # The end-of-run cut, in this transaction: no reader sees the run completed
                # before its cut (D5), and this save's retries are the cut's.
                cut_first_apply(session, job_id)
            else:
                # A failed run settles as a stopped one does (D27, extended by the lead to
                # every end without a finish): the exact cut over what earlier passes coded,
                # stored lines, the tags of its acceptances, and no ``completed_at``, so a
                # retry resumes at those lines.
                settle = cut_first_apply(session, job_id, stopped=True)
                settled_tags[0] = settle.tagged if settle is not None else 0
            return j.status

        finished, _ = await _save_batch(db_factory, _finish, f"job {framework_id}, its outcome")
        if not finished:
            raise _NotSavedError
        return settled_tags[0]

    except Exception as exc:
        if _is_db_error(exc):
            # Its text carries the statement and the row: the type and code only.
            logger.error("AutoCode job failed: the database (%s)", _db_error_name(exc))
        else:
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
                # Name the failure. str(exc) cannot tell an exhausted account
                # from a rate limit — Anthropic returns 400 for both — and
                # telling a bankrupt researcher to "try again shortly" is the
                # specific bug the classifier was written for. A database failure
                # is not the provider's, and its text is never stored.
                job.error_message, job.failure_kind = failure_text(
                    job.llm_provider or None, exc,
                )
            if job and job.completed_at is None:
                # Failed, or a Stop whose outcome could not be saved: settled with it, in the
                # same transaction, as every end without a finish is (D27, extended). If this
                # cannot be saved either, the job stays "running" and the boot sweep settles it.
                settle = cut_first_apply(db, job.id, stopped=True)
                settled_tags[0] = settle.tagged if settle is not None else 0
            if job:
                db.commit()
        except Exception:
            settled_tags[0] = 0
            logger.exception("Failed to mark job as failed")
        return settled_tags[0]
    finally:
        db.close()
        _FIRST_APPLY_CODING[key] -= 1
        if not _FIRST_APPLY_CODING[key]:
            del _FIRST_APPLY_CODING[key]
        if telemetry_tokens is not None:
            try:
                telemetry.trim_run_terminus()
            except Exception:
                logger.debug("telemetry trim failed", exc_info=True)
            telemetry.reset_run_context(telemetry_tokens)


# Default accept cutoff when a framework was applied without an explicit
# threshold (mirrors the review dialog's DEFAULT_UPPER = 0.70).
DEFAULT_ACCEPT_THRESHOLD = 0.70

# Default lower cutoff when a framework was applied without one stored (mirrors
# the review dialog's DEFAULT_LOWER = 0.30 in
# frontend/src/components/ThresholdReviewModal.tsx).
DEFAULT_DENY_THRESHOLD = 0.30

#: The review dialog's cutoffs sit on a 0.05 grid (``frontend/src/utils/confidenceStep.ts``).
CONFIDENCE_STEPS_PER_UNIT = 20

# The default cut at the end of a first apply: the hybrid (docs/design-autocode-landing-plan.md
# D5). The most confident ``HYBRID_ACCEPT_PERCENT`` per cent of the run's proposals are
# accepted, never below ``HYBRID_ACCEPT_FLOOR``; those below ``HYBRID_EXCLUDE_BELOW`` are
# excluded; the band between stays pending for the review. Phase 0a measured every AutoCode run
# in the trial studies (15 runs, 23 Nov 2026): a fixed 0.70 accepted about half of a typical
# UXR run (the overwhelm); the top 30% alone accepted every proposal of a poorly fitting
# codebook whose proposals all sat at 0.10; the hybrid took 31 to 35% of most fitting runs and
# 0 to 3% of poorly fitting ones. Literal values, not the dialog's defaults above: those are
# where a slider starts, these are a measured rule, and they may part.
#
# The line accepted at is the stored one, the rank's confidence rounded UP to the review's
# 0.05 grid (D41, D46), so every accepted row sits in the stored line's accepted zone and every
# pending row below it. When the rank falls between two grid values (0.72), the proposals from
# it up to the next one (0.72 to 0.75) stay pending, so such a run takes a little under 30%.
HYBRID_ACCEPT_PERCENT = 30
HYBRID_ACCEPT_FLOOR = 0.70
HYBRID_EXCLUDE_BELOW = 0.30


def hybrid_rank_confidence(confidences: Iterable[float]) -> float:
    """The confidence the hybrid ranks at over a run's proposals (D5), before the grid.

    The confidence of the proposal ranked ``ceil(30% of n)`` (at least the first), never
    below ``HYBRID_ACCEPT_FLOOR``; a run with no proposals has only the floor. The rank is
    the lab's (``pctLines`` in ``experiments/autocode-landing/template.html``), in integer
    arithmetic. The line accepted at is ``hybrid_accept_line``.
    """
    ranked = sorted(confidences, reverse=True)
    if not ranked:
        return HYBRID_ACCEPT_FLOOR
    k = max(1, -(-len(ranked) * HYBRID_ACCEPT_PERCENT // 100))
    return max(ranked[k - 1], HYBRID_ACCEPT_FLOOR)


def accept_line_for(confidence: float) -> float:
    """``confidence`` rounded UP to the review's 0.05 grid (D41): ``n / 20``, as
    ``snap_cutoff`` returns a line. A confidence a hair over a grid value from float
    arithmetic (0.55 * 20 is 11.000000000000002) is that value."""
    steps = math.ceil(confidence * CONFIDENCE_STEPS_PER_UNIT - 1e-9)
    return min(steps, CONFIDENCE_STEPS_PER_UNIT) / CONFIDENCE_STEPS_PER_UNIT


def hybrid_accept_line(confidences: Iterable[float]) -> float:
    """The hybrid's accept line: the line it accepts at AND stores (D46). A proposal at or
    above it is accepted, ties with the rank included when the rank is on the grid; one
    below stays pending. Accepting at the rank itself left accepted rows in the stored
    line's tentative zone, where raising the line never reached them and lowering it
    counted moves that changed nothing."""
    return accept_line_for(hybrid_rank_confidence(confidences))


def grid_line_at_or_below(confidence: float) -> float:
    """The highest line on the review's 0.05 grid at or below ``confidence``: the line
    a proposal accepted at ``confidence`` sits at or above. Float noise as
    ``accept_line_for`` (0.55 * 20 is 11.000000000000002, 0.7 * 20 is 13.999999999999998)."""
    steps = math.floor(confidence * CONFIDENCE_STEPS_PER_UNIT + 1e-9)
    return max(0, min(steps, CONFIDENCE_STEPS_PER_UNIT)) / CONFIDENCE_STEPS_PER_UNIT


#: Live acceptance (docs/design-autocode-landing-plan.md D6): until this many proposals of
#: the run have landed, the running estimate of the cut is held at or above
#: ``LIVE_EARLY_FLOOR``. A handful of proposals says little about the run's top 30%, and a
#: tag accepted is never taken back. 0.75 (owner, 23 Nov 2026; was 0.80): on the real trial
#: runs 44% of a run's accepted tags then land live rather than 16%, with no overshoot of the
#: end's cut on any of them.
LIVE_EARLY_PROPOSALS = 25
LIVE_EARLY_FLOOR = 0.75


def live_accept_line(confidences: list[float], previous: float | None) -> float:
    """The line a first apply's batch accepts at as it lands (D6, refined by the lead on
    23 Nov 2026: the line never falls during a run).

    The estimate is the hybrid's own line over every counted proposal of the run so far
    (``hybrid_accept_line``: the 30% rank rounded up to the grid, never below 0.70), and
    not below ``LIVE_EARLY_FLOOR`` until ``LIVE_EARLY_PROPOSALS`` have landed. The line is
    the higher of that and every line used before (``previous``). Simulated over every
    trial run with batches answering out of order, the plain estimate accepted up to 47%
    of a run in unlucky timings (an early batch dragged it to 0.70, and the end's
    reconcile then accepted the whole 0.70 to 0.75 band); never falling, every run matched
    the end-only hybrid cut."""
    estimate = hybrid_accept_line(confidences)
    if len(confidences) < LIVE_EARLY_PROPOSALS:
        estimate = max(estimate, LIVE_EARLY_FLOOR)
    return estimate if previous is None else max(previous, estimate)


def accept_live(session: SASession, job_id: int) -> int:
    """Accept, as a batch lands, the run's pending proposals at or above the live line
    (D6), in the caller's transaction (uncommitted). Answers how many it accepted.

    A run with stored lines (a stop settled them, D27, or a review stored them) accepts at
    its stored accept line; otherwise at ``live_accept_line`` over the run's counted
    proposals, which is written back to the job so the next batch, and a resumed run,
    continue from it. Only quotes that count, and only a proposal still pending at write
    time (one conditional UPDATE): a researcher's decision, made meanwhile on the live page,
    is never overwritten (D2). Nothing is excluded live: exclusion below 0.30 is the end
    cut's (D5).

    No ``QuoteTag`` is made here. The ordinary readers of tags (quote cards, the export,
    Signals, the MCP tools) read ``QuoteTag`` with no job attached, so a tag made now would
    show a run still coding there, which D32 holds back until Phase 4's playback; the
    live page reads the proposals themselves. ``cut_first_apply`` makes the tags of every
    proposal accepted this way when the run completes or a stop settles it, in the same
    transaction as the outcome. A failed run keeps its live acceptances without tags until
    a retry completes it.
    """
    from bristlenose.server.models import AutoCodeJob, ProposedTag
    from bristlenose.server.speaker_slots import analysis_quotes

    session.flush()
    job = session.get(AutoCodeJob, job_id, populate_existing=True)
    if job is None:
        return 0
    counted = {q.id for q in analysis_quotes(session, job.project_id)}
    rows = [
        (pid, confidence, status)
        for pid, quote_id, confidence, status in session.query(
            ProposedTag.id, ProposedTag.quote_id, ProposedTag.confidence, ProposedTag.status,
        ).filter(ProposedTag.job_id == job_id)
        if quote_id in counted
    ]
    if job.applied_upper_threshold is not None or job.applied_lower_threshold is not None:
        line = stored_lines(job)[0]
    else:
        line = live_accept_line([c for _, c, _ in rows], job.live_accept_line)
        if line != job.live_accept_line:
            session.query(AutoCodeJob).filter(AutoCodeJob.id == job_id).update(
                {AutoCodeJob.live_accept_line: line}, synchronize_session=False,
            )
    wanted = [pid for pid, confidence, status in rows if status == "pending" and confidence >= line]
    if not wanted:
        return 0
    return int(session.query(ProposedTag).filter(
        ProposedTag.id.in_(wanted), ProposedTag.status == "pending",
    ).update(
        {ProposedTag.status: "accepted", ProposedTag.decided_by: "threshold",
         ProposedTag.reviewed_at: datetime.now(timezone.utc)},
        synchronize_session=False,
    ))


@dataclass
class CutOutcome:
    """What a first apply's end-of-run cut did: the lines it sorted by and what it moved."""

    accept_at: float
    exclude_below: float
    accepted: int = 0
    excluded: int = 0
    #: The lines were the job's own (a stop settled them, or a review stored them).
    from_stored: bool = False
    #: Tags it made (``QuoteTag`` rows added): what Signals reads changed only if this is
    #: above 0. A tag the quote already had, a researcher's own included, is not counted.
    tagged: int = 0


def cut_first_apply(
    session: SASession, job_id: int, *, stopped: bool = False,
) -> CutOutcome | None:
    """The end of a first apply, in the caller's transaction (uncommitted): the hybrid cut
    (docs/design-autocode-landing-plan.md D5, D27, D35, D41, D46).

    ``run_autocode_job`` runs it in the same transaction as the job's outcome, so no reader
    sees a completed run before its cut (a page refreshed by the chip's "completed" would
    otherwise draw the whole run as tentative), and the save's retries (worker thread,
    ``SAVE_ATTEMPTS``, the short lock wait) are the cut's. A first apply that ends without
    finishing (``stopped``: a Stop, a failure, an orphan the boot sweep finds, an outcome
    that could not be saved) settles the same way when its last batches have answered, so
    every paid proposal is ranked, and stays unfinished: this never sets ``completed_at``
    (D27, D35; the lead extended D27 to every terminal path on 23 Nov 2026, so no ended
    job holds a threshold acceptance without stored lines or without its tag).

    Over the run's proposals on quotes that count (accept-all's rule: a hidden quote's
    proposal is not ranked and not touched, and stays pending for when it counts again),
    the line is ``hybrid_accept_line``, lowered when the batches accepted something below
    it live (``accept_live``, D6) to the grid line at or below the lowest of those: an
    accepted tag is never taken back. Pending proposals at or above the line are accepted
    (the top-up), pending ones below 0.30 excluded, the rest left pending; then every
    threshold acceptance of the run, live or top-up, gets its tag (made as AutoCode's,
    unless the quote has it already). The same two lines are stored for the review and the
    catch-ups, so the review's Apply with the lines unmoved changes nothing (D26).

    A job that already has lines (a stop settled them, or a review stored them) is sorted
    by those, as a catch-up is (D27: a resumed run continues with the same lines), and they
    are not recomputed. A settle with nothing to rank and nothing accepted stores none, so
    its resumed run ranks what it then codes.

    Every change is a decision of the lines (``decided_by="threshold"``), written only on a
    proposal still pending (a conditional update): a decision made meanwhile, a
    researcher's or one from before decisions were recorded, is never touched (D2). None
    when the job is gone.
    """
    from bristlenose.server.models import AutoCodeJob, ProposedTag, QuoteTag
    from bristlenose.server.speaker_slots import analysis_quotes

    job = session.get(AutoCodeJob, job_id)
    if job is None:
        return None
    counted = {q.id for q in analysis_quotes(session, job.project_id)}
    proposals = [
        p for p in session.query(ProposedTag).filter(ProposedTag.job_id == job_id).all()
        if p.quote_id in counted
    ]
    if job.applied_upper_threshold is not None or job.applied_lower_threshold is not None:
        accept_at, exclude_below = stored_lines(job)
        exact = accept_at
        outcome = CutOutcome(accept_at=accept_at, exclude_below=exclude_below, from_stored=True)
    else:
        # Ranked over every proposal of the run, decided or not: the cut is a property of
        # the run, and a decision made meanwhile does not move it.
        exact = accept_at = hybrid_accept_line(p.confidence for p in proposals)
        # An accepted tag is never taken back (D6): the line stored is no higher than the
        # grid line at or below the lowest proposal the run accepted live, so every
        # accepted proposal sits at or above it, and the top-up below then leaves every
        # pending one below it (D46: no inversion). The live line never falls, so this
        # rarely bites; when it does, the run takes a little more than the exact cut.
        live = [
            confidence for (confidence,) in session.query(ProposedTag.confidence).filter(
                ProposedTag.job_id == job_id, ProposedTag.status == "accepted",
                ProposedTag.decided_by == "threshold",
            )
        ]
        if live:
            accept_at = min(accept_at, grid_line_at_or_below(min(live)))
        exclude_below = HYBRID_EXCLUDE_BELOW
        outcome = CutOutcome(accept_at=accept_at, exclude_below=exclude_below)
        # Stored whenever anything was ranked or accepted, so an ended job never holds a
        # threshold acceptance without lines (live ones on quotes hidden since included).
        if proposals or live or not stopped:
            job.applied_upper_threshold = accept_at
            job.applied_lower_threshold = exclude_below

    now = datetime.now(timezone.utc)
    overshoot = 0
    for proposal in proposals:
        if proposal.confidence >= accept_at:
            target = "accepted"
        elif proposal.confidence < exclude_below:
            target = "denied"
        else:
            continue
        # Conditional on pending, at write time (D2): the ORM object's status is what was
        # read, and a decision committed since must win.
        changed = session.query(ProposedTag).filter(
            ProposedTag.id == proposal.id, ProposedTag.status == "pending",
        ).update(
            {ProposedTag.status: target, ProposedTag.decided_by: "threshold",
             ProposedTag.reviewed_at: now},
            synchronize_session=False,
        )
        if not changed:
            continue
        if target == "denied":
            outcome.excluded += 1
        else:
            outcome.accepted += 1
            if not outcome.from_stored and proposal.confidence < exact:
                overshoot += 1
    if not outcome.from_stored and accept_at < exact:
        # The reconcile bit (D6): the batches accepted something live below the exact cut,
        # so the run takes more than the end-only hybrid would. On every real trial run it
        # never bites; on a well-fitting run whose early sessions are weaker it can. Said,
        # so a real case shows (lead, 23 Nov 2026).
        logger.info(
            "AutoCode job %s: stored line %.2f is below the exact cut %.2f (accepted live "
            "below it); the top-up accepted %d more because of it",
            job_id, accept_at, exact, overshoot,
        )
    # The tags: of the top-up's acceptances and of every one made live as the batches landed
    # (``accept_live`` makes none, so a run still coding shows nowhere but the live page,
    # D32). As ``_ensure_autocode_tag``: a tag the quote has already (the researcher's)
    # stays. Every threshold acceptance of the job, a hidden quote's included (the lead's
    # call, 23 Nov 2026): it was accepted live before the quote was hidden, an accepted tag
    # is never taken back, and a tag on a hidden quote counts nowhere until it is unhidden.
    from sqlalchemy import and_

    tagged = session.query(QuoteTag.quote_id, QuoteTag.tag_definition_id).join(
        ProposedTag, and_(
            ProposedTag.quote_id == QuoteTag.quote_id,
            ProposedTag.tag_definition_id == QuoteTag.tag_definition_id,
        ),
    ).filter(ProposedTag.job_id == job_id)
    has_tag: set[tuple[int, int]] = {(quote_id, tag_id) for quote_id, tag_id in tagged}
    for quote_id, tag_definition_id in session.query(
        ProposedTag.quote_id, ProposedTag.tag_definition_id,
    ).filter(
        ProposedTag.job_id == job_id, ProposedTag.status == "accepted",
        ProposedTag.decided_by == "threshold",
    ).all():
        if (quote_id, tag_definition_id) in has_tag:
            continue
        has_tag.add((quote_id, tag_definition_id))
        session.add(QuoteTag(
            quote_id=quote_id, tag_definition_id=tag_definition_id, source="autocode",
        ))
        outcome.tagged += 1
    return outcome


def snap_cutoff(value: float) -> float:
    """A review cutoff as exact as the label it was read from, or ``ValueError``.

    The slider's old arithmetic stored ``0.7000000000000001`` for "0.70", and a ``>=``
    against that denied a proposal at exactly 0.70 as already reviewed (N188). Anything
    that is not finite, not within [0, 1], or not on the 0.05 grid is refused; a value
    that is on the grid up to float noise comes back as ``n / 20``, the correctly
    rounded double of its label (as the web's ``snapToStep`` returns it).
    """
    if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("a confidence cutoff is a number from 0 to 1")
    steps = round(value * CONFIDENCE_STEPS_PER_UNIT)
    if abs(value * CONFIDENCE_STEPS_PER_UNIT - steps) > 1e-6:
        raise ValueError("a confidence cutoff is a multiple of 0.05")
    return steps / CONFIDENCE_STEPS_PER_UNIT


def stored_lines(job: AutoCodeJob) -> tuple[float, float]:
    """The (accept, exclude) lines a re-apply sorts its proposals by: the ones the
    review stored, or the dialog's defaults where none was stored.

    The catch-up applies the review dialog's three bands, not two: at or above the
    accept line is accepted, strictly below the exclude line is denied (the review's
    row override can take a denial back, but nobody would know to look), and the band
    between stays pending for the review, as in a first apply (#207: "the same
    thresholds that were in place at the last AutoCode"). A line stored by a build
    whose slider drifted (0.7000000000000001) is the line its label says: both are
    compared at two decimals (N188).

    Since Phase 3 of docs/design-autocode-landing-plan.md a first apply stores the
    hybrid's lines with its outcome (``cut_first_apply``): the line it accepted at, on
    the grid, and 0.30; a stop that coded nothing stores none. So a catch-up after it
    excludes below 0.30, which the house default's stored 0 used to prevent: intended
    (D5). A job applied before then keeps what it had (the house default's 0, or no
    lines for a researcher's).
    """
    upper = job.applied_upper_threshold
    if upper is None:
        upper = DEFAULT_ACCEPT_THRESHOLD
    lower = job.applied_lower_threshold
    if lower is None:
        lower = DEFAULT_DENY_THRESHOLD
    return round(upper, 2), round(lower, 2)


def _answered_quote_ids(
    batches: list[list[QuoteBatchItem]], results: list[Any],
) -> set[int]:
    """The quotes this pass sent in a batch that answered. A batch that failed (an
    exception) or was never sent (None) leaves each of its quotes owed."""
    answered: set[int] = set()
    for batch, result in zip(batches, results, strict=True):
        if result is not None and not isinstance(result, BaseException):
            answered.update(item.db_id for item in batch)
    return answered


def sent_quote_ids(db: SASession, job_id: int) -> set[int]:
    """The quotes ``job_id`` has paid for: its register, and any quote it holds a
    proposal on (a proposal is a quote that was sent, whatever wrote it)."""
    from bristlenose.server.models import AutoCodeSentQuote, ProposedTag

    sent = {
        row[0]
        for row in db.query(AutoCodeSentQuote.quote_id).filter(
            AutoCodeSentQuote.job_id == job_id
        )
    }
    sent.update(
        row[0] for row in db.query(ProposedTag.quote_id).filter(ProposedTag.job_id == job_id)
    )
    return sent


def record_sent(db: SASession, job_id: int, quote_ids: Iterable[int]) -> None:
    """Put ``quote_ids`` on ``job_id``'s register. Uncommitted: the caller commits
    them with the proposals they stand for. A quote already on it is skipped: the
    (job, quote) key is unique, and a duplicate would fail the commit and take
    the proposals it travels with."""
    from bristlenose.server.models import AutoCodeSentQuote

    wanted = set(quote_ids)
    if not wanted:
        return
    already = {
        row[0]
        for row in db.query(AutoCodeSentQuote.quote_id).filter(
            AutoCodeSentQuote.job_id == job_id
        )
    }
    for quote_id in sorted(wanted - already):
        db.add(AutoCodeSentQuote(job_id=job_id, quote_id=quote_id))


def of_applied_jobs() -> ColumnElement[bool]:
    """The filter every reader of tentative tags puts on ``ProposedTag``: proposals of
    applied jobs only (docs/design-autocode-landing-plan.md D32).

    Applied is ``completed_at`` or "completed", not status alone: a catch-up running,
    failed, cut off by a restart or stopped leaves an applied job "running", "failed"
    or "cancelled", and every pending proposal of the first apply vanished from the
    lens until the next catch-up worked (RE#66). A first apply still coding, stopped
    or failed has no ``completed_at``, and shows none: its batches are saved as they
    answer (Phase 1) and accepted live (Phase 4, ``accept_live``, which makes no
    ``QuoteTag`` until the run's cut), but no ordinary reader shows a run's proposals
    before it finishes, as shipped. Read by the quote cards (``/quotes``), the
    Codebook lens's tentative counts and Signals; the review dialog and the live page
    read their own job's proposals (``GET …/proposals``, ``live=true``) and do not use it.
    """
    from sqlalchemy import or_, select

    from bristlenose.server.models import AutoCodeJob, ProposedTag

    return ProposedTag.job_id.in_(
        select(AutoCodeJob.id).where(
            or_(AutoCodeJob.status == "completed", AutoCodeJob.completed_at.isnot(None)),
        )
    )


def owed_quotes(
    db: SASession, job: AutoCodeJob, counted: list[Any] | None = None,
) -> list[Any]:
    """The quotes ``job`` still owes: those that count and are not on its register
    (RE#66, ruling 4).

    This replaced the per-session stamp, which said a session was done whatever it
    held. The unit is the quote: one added to a coded session (N89) and one that
    was hidden or recoded out when the codebook ran (N175) are owed, and one the
    model answered no tag for is not. ``analysis_quotes`` is the predicate the
    passes send by, so a quote that does not count is never owed, and cannot be
    marked as sent having gone nowhere. A catch-up chip over nothing would say
    "Re-coded" over nothing, so no quotes owed means nothing to start.

    ``counted`` is ``analysis_quotes`` for the project when the caller has it
    already (it is the same list for every codebook).
    """
    from bristlenose.server.speaker_slots import analysis_quotes

    sent = sent_quote_ids(db, job.id)
    quotes = counted if counted is not None else analysis_quotes(db, job.project_id)
    return [q for q in quotes if q.id not in sent]


def delete_jobs(db: SASession, job_ids: list[int]) -> None:
    """Delete AutoCode jobs with their proposals and registers (uncommitted): an
    uninstall. Apply on a never-applied job keeps it (#127)."""
    from bristlenose.server.models import AutoCodeJob, AutoCodeSentQuote, ProposedTag

    if not job_ids:
        return
    for model in (AutoCodeSentQuote, ProposedTag):
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


# A run's import rebuilds the quote rows, and a re-apply writes its proposals against the ids
# it read (in one commit at the end until 23 Nov 2026, now as each batch answers). One still coding when the next run's import landed lost the
# commit to a foreign-key failure after every batch was paid for (N92). So an import asks the
# re-applies to stop at their next batch (what answered is kept, the rest stays owed: the Stop
# and switch-off path) and waits for them, for a bounded time, before it starts. A serve holds
# one project, so the pause is not keyed by project.
_IMPORTS_RUNNING = 0
#: The longest an import waits for the batches already out to answer. A re-apply that has not
#: ended by then (a hung call) is left to the old outcome: rolled back, and coded again later.
IMPORT_WAIT_S = 60.0


@contextlib.asynccontextmanager
async def reapplies_paused_for_import() -> Any:
    """Hold every re-apply at its next batch while a run's import rewrites the quotes.

    Waits, up to ``IMPORT_WAIT_S``, for the live ones to bank what answered and end, so the
    import never meets a commit in flight. A re-apply that starts meanwhile finds the pause at its
    first batch and sends nothing. The registry's tasks are never cancelled here.
    """
    global _IMPORTS_RUNNING
    _IMPORTS_RUNNING += 1
    try:
        live = [t for t in list(_REAPPLY_IN_FLIGHT.values()) if not t.done()]
        if live:
            _, still = await asyncio.wait(live, timeout=IMPORT_WAIT_S)
            if still:
                logger.warning(
                    "Import started with %d re-apply(s) still coding after %.0f s; "
                    "their pass may be rolled back and coded again", len(still), IMPORT_WAIT_S,
                )
        yield
    finally:
        _IMPORTS_RUNNING -= 1


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

    if owed_quotes(db, job):
        return
    db.query(AutoCodeJob).filter(
        AutoCodeJob.id == job.id,
        AutoCodeJob.status.not_in(("running", "pending")),
        or_(
            AutoCodeJob.status.in_(("failed", "cancelled")),
            AutoCodeJob.failure_kind != "",
            AutoCodeJob.error_message != "",
            # A catch-up with some batches failed ends "completed" and says so only
            # in its own counts, which the codebook pages read (24 Nov 2026).
            AutoCodeJob.catch_up_total != AutoCodeJob.catch_up_processed,
        ),
    ).update(
        {AutoCodeJob.status: "completed", AutoCodeJob.error_message: "",
         AutoCodeJob.failure_kind: "",
         AutoCodeJob.catch_up_processed: AutoCodeJob.catch_up_total},
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
      crashed before finishing the first pass → mark ``failed`` with a retryable
      ``error_message``. The batches it saved are kept, with their counts (each
      batch saves its proposals and ``proposed_count`` as it answers), and settled
      (``cut_first_apply``, as a Stop's settle: its live acceptances get stored lines and
      their tags). The start-job guard lets Apply run a never-applied ``failed`` job
      again, keeping what it coded (#127), at the lines it settled.
    - **Catch-up orphan** (``completed_at IS NOT NULL``): the on-enable catch-up
      set an applied job ``running`` and was cut off before it finished → mark
      ``failed``, unclassified, so a chip still polling a restarted serve says
      "Tagging failed." rather than "Re-coded" over nothing (#63, RE#66). The
      batches it saved before the cut are kept, with their register rows and
      counts (each batch is saved as it answers, since 23 Nov 2026); the quotes of
      the rest are still owed and the next run or re-enable codes them;
      ``completed_at`` keeps the codebook maintained, and Apply
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
            # Catch-up orphan: applied, but this catch-up never finished. The
            # quotes of the batches it had not saved are not on the register, so
            # they are owed whatever this says.
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
            # Settled as every end without a finish is (D27, extended by the lead, 23 Nov
            # 2026): what its batches coded and accepted live gets its cut, stored lines and
            # tags, so a retry resumes at those lines and no ended job holds an acceptance
            # without them.
            cut_first_apply(db, job.id, stopped=True)
        changed += 1

    if changed:
        db.commit()
    return changed


@tracked("autocode")
async def reapply_to_new_quotes(
    db_factory: Callable[[], SASession],
    project_id: int,
    framework_id: str,
    settings: BristlenoseSettings,
    track_status: bool = False,
) -> int:
    """Re-apply a framework to the quotes it owes, bound as a run.

    Binds the pass to the project's output folder (read from its row), so its
    calls reach ``llm-calls.jsonl``. Until 17 Nov 2026 it bound only
    ``telemetry.stage(...)``, and no re-apply after a run, and no catch-up, was
    recorded. The work is :func:`_reapply_to_new_quotes`.
    """
    from bristlenose.events import new_run_id
    from bristlenose.llm import telemetry
    from bristlenose.server.models import Project

    db = db_factory()
    try:
        project = db.get(Project, project_id)
        output_dir = project.output_dir if project is not None else None
    finally:
        db.close()
    work = _reapply_to_new_quotes(
        db_factory, project_id, framework_id, settings, track_status=track_status,
    )
    if not output_dir:
        return await work
    # The row's `output_dir` is already the output folder: bound directly, not
    # through `serve_run_context`'s project-root resolution, which would look
    # for a nested `bristlenose-output/` in a custom-named output folder.
    tokens = telemetry.set_run_context(
        f"autocode-reapply-{project_id}-{framework_id}-{new_run_id()}",
        Path(output_dir) / ".bristlenose",
    )
    try:
        return await work
    finally:
        telemetry.reset_run_context(tokens)


def _note_catch_up_total(db: SASession, job_id: int, total: int) -> None:
    """Write an on-enable catch-up's own total as it starts, its processed count at 0, so the
    Mac's row can count the pass while it codes (D40; each saved batch adds to the count).
    Write-only and non-fatal (``bristlenose/server/gotchas.md`` § AutoCode): a locked
    database costs the row its count, never the pass. A Stop that landed first is left alone."""
    from sqlalchemy.exc import SQLAlchemyError

    from bristlenose.server.models import AutoCodeJob

    try:
        db.query(AutoCodeJob).filter(
            AutoCodeJob.id == job_id, AutoCodeJob.status != "cancelled",
        ).update(
            {AutoCodeJob.catch_up_total: total, AutoCodeJob.catch_up_processed: 0},
            synchronize_session=False,
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("Catch-up count not written at the start of the pass (%s)",
                       type(exc).__name__)


async def _reapply_to_new_quotes(
    db_factory: Callable[[], SASession],
    project_id: int,
    framework_id: str,
    settings: BristlenoseSettings,
    track_status: bool = False,
) -> int:
    """Re-apply an already-applied framework to the quotes it still owes.

    Codes ONLY the delta — the quotes that count and are not on the framework's
    register of sent quotes (``owed_quotes``): a new session's, a quote added to
    a coded session, one hidden or recoded out until now — and auto-accepts at
    the researcher's stored cutoff, with no review modal. Existing quotes and
    human tags are never touched (the accept is non-clobbering). A quote goes on
    the register when it was in a batch that answered, whether or not the model
    tagged it; one in a batch that failed, or that a Stop or a switch turned off
    never sent, stays owed for the next re-apply (RE#66). Returns the number of
    new QuoteTags created (0 if there's nothing to do).

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
        QuoteTag,
        TagDefinition,
    )

    db = db_factory()
    failed = False
    try:
        # A run's import is rewriting the quotes: read nothing and sync nothing. A pass that
        # starts in that window used to read a half-rebuilt table and contend for the write
        # lock, and failed the chip with "database is locked" (N92 review). Nothing is
        # owed-and-lost: what the pass would have sent stays owed for the run's own re-apply.
        if _IMPORTS_RUNNING:
            return 0
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

        # The lines the review stored, read again as each batch is saved (review 8):
        # a re-cut made while this pass codes applies to the batches saved after it.
        threshold, lower_threshold = stored_lines(job)

        # Delta = the quotes this job still owes (RE#66, ruling 4): those that
        # count (as in the first apply, N175) and are not on its register. The
        # register is per quote and written when a batch answers, so (a) a clean
        # or full re-run of coded sessions doesn't mark them new, (b) a quote the
        # LLM simply didn't tag is never re-sent, the register being the cost
        # gate (§4a), and (c) a quote that did not count when the codebook ran, or
        # that a re-run added to a coded session, is sent now. A quote that
        # already has a proposal on this job is on the register too: a stopped or
        # partial pass coded it, and a second proposal would break (job, quote).
        # ``completed_at`` is "applied at least once"; never applied, nothing to do.
        if job.completed_at is None:
            return 0
        # In stored order, as a first apply sends them (D25).
        new_quotes = sorted(owed_quotes(db, job), key=lambda q: q.id)
        if not new_quotes:
            # Nothing owed may still follow a Stop that landed on the last batch,
            # or a failed catch-up whose sessions a re-import withdrew (#61).
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
        if track_status:
            _note_catch_up_total(db, job_id, len(batch_items))

        def _halted() -> bool:
            """Read fresh before each batch. A catch-up's Stop sets its job
            "cancelled" (R12 wave 6), and any re-apply, a catch-up included, ends
            when its codebook is switched off while it codes ("off means off", #62,
            N93: the catch-up read only the Stop, and went on paying after a
            switch-off). An uninstall ends it too: the job is gone, or the codebook
            no longer linked, and every batch after it was paid for and rolled back."""
            if _IMPORTS_RUNNING:
                return True  # a run's import is rewriting the quotes (N92)
            check = db_factory()
            try:
                j = check.get(AutoCodeJob, job_id)
                if j is None:
                    return True
                if track_status and j.status == "cancelled":
                    return True
                return framework_id not in _maintained_framework_ids(check, project_id)
            finally:
                check.close()

        tally = {"accepted": 0, "proposed": 0}
        lines_used = {(threshold, lower_threshold)}

        def _store(
            session: SASession, answered: _Answered,
        ) -> tuple[int, int, tuple[float, float]] | None:
            """One answered batch: its proposals sorted into the review's bands by
            the lines stored NOW, accepted tags made (never over an existing tag),
            its quotes on the register and the job's counts, in one transaction
            (uncommitted). Answers (tags made, proposals, the lines used), which the
            caller counts only once the save has committed: a try that rolls back
            and is tried again would otherwise count twice. A job gone meanwhile
            (an uninstall) takes nothing and answers None."""
            j = session.get(AutoCodeJob, job_id, populate_existing=True)
            if j is None:
                return None
            upper, lower = stored_lines(j)
            now = datetime.now(timezone.utc)
            accepted = 0
            for quote_id, tag_def_id, confidence, rationale in answered.proposals:
                # The dialog's inequalities exactly (``zoneAt`` in frontend/src/utils/
                # recut.ts, and the re-cut, accept-all and deny-all routes): ``>= upper``
                # accepts, ``< lower`` denies. After a first apply's hybrid cut the lower
                # line is 0.30, so a catch-up excludes below it unwatched: D5 intends it
                # (the first apply's own end did the same), and the review's row override
                # takes one back.
                status: str
                reviewed_at: datetime | None
                decided_by: str | None
                if confidence >= upper:
                    status, reviewed_at, decided_by = "accepted", now, "threshold"
                elif confidence < lower:
                    status, reviewed_at, decided_by = "denied", now, "threshold"
                else:
                    status, reviewed_at, decided_by = "pending", None, None
                # Record the proposal on the existing job — audit trail, and it
                # marks the quote as "seen" so a later re-apply won't re-code it.
                session.add(ProposedTag(
                    job_id=job_id, quote_id=quote_id, tag_definition_id=tag_def_id,
                    confidence=confidence, rationale=rationale, status=status,
                    reviewed_at=reviewed_at, decided_by=decided_by,
                ))
                if status == "accepted":
                    # Non-clobbering: never overwrite an existing (human or
                    # autocode) tag on this quote.
                    existing = (
                        session.query(QuoteTag)
                        .filter_by(quote_id=quote_id, tag_definition_id=tag_def_id)
                        .first()
                    )
                    if existing is None:
                        session.add(QuoteTag(
                            quote_id=quote_id, tag_definition_id=tag_def_id,
                            source="autocode",
                        ))
                        accepted += 1
            # The quotes this batch sent, with the proposals they stand for (RE#66).
            record_sent(session, job_id, answered.quote_ids)
            n = len(answered.quote_ids)
            grown: dict[Any, Any] = {
                AutoCodeJob.total_quotes: AutoCodeJob.total_quotes + n,
                AutoCodeJob.processed_quotes: AutoCodeJob.processed_quotes + n,
                AutoCodeJob.proposed_count:
                    AutoCodeJob.proposed_count + len(answered.proposals),
            }
            if track_status:
                # The pass's own count, per batch, so the Mac's row reads "AutoCode · N of M"
                # over this pass's quotes while it codes (landing plan D40). Never past the
                # total: if the total's write at the start failed, the count stays at 0 and the
                # row shows none (Phase 5a review). The pass's end writes the final pair.
                from sqlalchemy import case

                added = AutoCodeJob.catch_up_processed + n
                grown[AutoCodeJob.catch_up_processed] = case(
                    (added > AutoCodeJob.catch_up_total, AutoCodeJob.catch_up_total),
                    else_=added,
                )
            session.query(AutoCodeJob).filter(AutoCodeJob.id == job_id).update(
                grown, synchronize_session=False,
            )
            return accepted, len(answered.proposals), (upper, lower)

        def _count(stored: tuple[int, int, tuple[float, float]] | None) -> None:
            if stored is not None:
                tally["accepted"] += stored[0]
                tally["proposed"] += stored[1]
                lines_used.add(stored[2])

        async def _batch(batch: list[QuoteBatchItem]) -> _Answered | None:
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
                out: list[ProposalValues] = []
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
                    # Its quotes are on the register all the same: the batch answered.
                    # Said, because a tag rename the sync missed looks like this.
                    logger.warning(
                        "Re-apply %s: a batch answered %d assignments and none named "
                        "a tag in the codebook", framework_id, len(result.assignments),
                    )
                # One proposal per quote (keep highest confidence): the (job, quote)
                # key is unique, and a duplicate failed the commit, rolled back the
                # pass with its register rows, and the same quotes re-failed on every
                # later run, silently.
                answered = _Answered(
                    proposals=_best_per_quote(out),
                    quote_ids=[item.db_id for item in batch],
                )
                # Saved as it answers (review 8): the lines it is sorted by are the
                # ones stored when it saves, and a pass cut off keeps what it saved.
                answered.saved, stored = await _save_batch(
                    db_factory, functools.partial(_store, answered=answered),
                    f"re-apply {framework_id}",
                )
                if answered.saved:
                    _count(stored)
                note_progress(len(batch))
                return answered

        results = await asyncio.gather(
            *(_batch(b) for b in batches), return_exceptions=True
        )
        # Every batch failing coded nothing: a failure, through the except below.
        # No quote is registered, so the next catch-up or run codes them. Recorded
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
                "Re-apply %s: %d of %d batches failed; sessions with quotes still owed: %s",
                framework_id, len(failures), len(results), ", ".join(missed),
            )
        if failures and len(failures) == len(results):
            raise failures[0]
        for res in results:
            if isinstance(res, BaseException):
                logger.error("Re-apply batch failed: %s", res)
        # A batch whose own save found the database locked through every try is tried
        # again now, each in its own transaction with its own retries. One that still
        # cannot be saved is not on the register: its quotes stay owed and the pass
        # reads as short (catch_up_processed < catch_up_total).
        answered = [r for r in results if isinstance(r, _Answered)]
        for kept in answered:
            if not kept.saved:
                kept.saved, stored = await _save_batch(
                    db_factory, functools.partial(_store, answered=kept),
                    f"re-apply {framework_id}, at the end of the pass",
                )
                if kept.saved:
                    _count(stored)
        if answered and not any(a.saved for a in answered) and not any(
            r is None for r in results
        ):
            raise _NotSavedError  # nothing landed: a failure, with nothing registered
        # Only a batch that answered and was saved counts as processed, as in
        # run_autocode_job: the chip reads `processed < total` on a completed job as
        # "some batches failed", and the re-apply grew `total_quotes` alone, so every
        # catch-up that worked said it partly failed.
        processed = sum(len(a.quote_ids) for a in answered if a.saved)
        accepted = tally["accepted"]
        new_proposed = tally["proposed"]

        # Sent, not selected: a Stop or a switch-off leaves batches unsent, and
        # counting them over-reported the denominator. Each saved batch added its own
        # quotes to both counts and its proposals; what is left is the quotes of the
        # batches that were sent and failed or could not be saved.
        sent = sum(len(b) for b, r in zip(batches, results, strict=True) if r is not None)

        def _finish(session: SASession) -> str:
            """The pass's outcome, in its own transaction, apart from its batches."""
            now = datetime.now(timezone.utc)
            counts: dict[Any, Any] = {
                AutoCodeJob.total_quotes: AutoCodeJob.total_quotes + (sent - processed),
            }
            values: dict[Any, Any] = {**counts, AutoCodeJob.completed_at: now}
            finish = session.query(AutoCodeJob).filter(AutoCodeJob.id == job_id)
            if track_status:
                # Route set this to "running" for the chip; restore it now, with no
                # failure left from an earlier catch-up, and this catch-up's own
                # counts, which the chip reads: the cumulative pair above keeps any
                # earlier shortfall for good (R12 wave 6).
                values.update({
                    AutoCodeJob.status: "completed",
                    AutoCodeJob.error_message: "",
                    AutoCodeJob.failure_kind: "",
                    # The quotes this pass sent, not the quotes it was asked about: a
                    # switch-off or an import halts it with batches unsent, which stay
                    # owed, and the chip reads total > processed as "some batches
                    # failed" when nothing failed.
                    AutoCodeJob.catch_up_total: sent,
                    AutoCodeJob.catch_up_processed: processed,
                })
                # Unless it was stopped: one UPDATE that a Stop's row refuses, so a
                # Stop landing at any moment before this commit is never written
                # over (an ORM assignment reloaded the job and replaced it).
                finish = finish.filter(AutoCodeJob.status != "cancelled")
            if finish.update(values, synchronize_session=False) == 0:
                # Stopped (#60): what answered is kept, with its register rows, and
                # the job stays cancelled. What the Stop never sent stays owed, so the
                # next catch-up or run codes it. Until 22 Oct 2026 a Stop kept
                # nothing, and the batches already paid for were sent again.
                session.query(AutoCodeJob).filter(AutoCodeJob.id == job_id).update(
                    counts, synchronize_session=False,
                )
                return "stopped"
            if not track_status:
                j = session.get(AutoCodeJob, job_id)
                if j is not None:
                    _clear_failure_once_owed_nothing(session, j)
            return "finished"

        done, outcome = await _save_batch(db_factory, _finish, f"re-apply {framework_id}, its outcome")
        if not done:
            raise _NotSavedError
        if outcome == "stopped":
            logger.info(
                "Re-apply %s: stopped, kept %d proposals", framework_id, new_proposed,
            )
            return accepted
        logger.info(
            "Re-apply %s: %d new quotes, %d proposals, %d auto-accepted; lines used "
            "(accept at or above, deny below): %s",
            framework_id,
            len(batch_items),
            new_proposed,
            accepted,
            ", ".join(f"{u:.2f}/{lo:.2f}" for u, lo in sorted(lines_used)),
        )
        return accepted

    except Exception as exc:
        if _is_db_error(exc):
            logger.error("Re-apply failed for %s: the database (%s)", framework_id,
                         _db_error_name(exc))
        else:
            logger.exception("Re-apply failed for %s: %s", framework_id, exc)
        with contextlib.suppress(Exception):
            db.rollback()
        failed = True
        if track_status:
            # Named as run_autocode_job names it, so the chip can say which failure
            # this was (out of credit, rate limited…) and not only "Tagging failed."
            # Never ``str(exc)``: it is stored and served by /status, and a provider's
            # error is its whole body, which can carry the prompt and an echoed key.
            message, kind = failure_text(settings.llm_provider or None, exc)
            _set_job_status(
                db, project_id, framework_id, "failed", message, failure_kind=kind,
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
    from bristlenose.server.active_codebooks import maintained_framework_ids

    return maintained_framework_ids(db, project_id)


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


# ---------------------------------------------------------------------------
# When Signals is rebuilt after AutoCode (D21, review 9)
# ---------------------------------------------------------------------------

# The AutoCode passes coding each project now, as their tasks: first applies, catch-ups
# and a run's re-apply. Read and written on the event loop only, so no lock. A task, not
# a count: a task that ended without saying so, or whose loop is gone, is not coding.
_LIVE_CODING: dict[int, set[asyncio.Task[Any]]] = {}
# A Signals rebuild a pass asked for while another of the project's passes still coded,
# by project, with the loop it was asked on and the source the last asker gave. The
# last pass to end builds it.
_SNAPSHOT_OWED: dict[int, tuple[asyncio.AbstractEventLoop, str]] = {}
# The pending rebuild after a re-cut, per project, and the builds in flight (a bare
# task can be collected mid-flight, gotchas.md § AutoCode).
_RECUT_TIMERS: dict[int, asyncio.TimerHandle] = {}
_SNAPSHOT_TASKS: set[asyncio.Task[Any]] = set()
#: A burst of re-cuts (a researcher may Apply the review's lines twice in a row, and
#: accept-all and deny-all are a pair) rebuilds Signals once, this long after the last.
RECUT_SNAPSHOT_DEBOUNCE_S = 5.0


def coding_started(project_id: int, task: asyncio.Task[Any]) -> None:
    """``task`` codes this project until it ends; it calls ``coding_ended`` when it does.
    On the loop."""
    _LIVE_CODING.setdefault(project_id, set()).add(task)


def _others_coding(project_id: int, me: asyncio.Task[Any] | None) -> bool:
    loop = asyncio.get_running_loop()
    live = _LIVE_CODING.get(project_id, set())
    live.difference_update({t for t in live if t.done() or t.get_loop() is not loop})
    if not live:
        _LIVE_CODING.pop(project_id, None)
    return any(t is not me for t in live)


def _owe_snapshot(project_id: int, source: str) -> None:
    _SNAPSHOT_OWED[project_id] = (asyncio.get_running_loop(), source)


def _take_owed_snapshot(project_id: int) -> str | None:
    owed = _SNAPSHOT_OWED.pop(project_id, None)
    if owed is None or owed[0] is not asyncio.get_running_loop():
        return None
    return owed[1]


async def coding_ended(
    app: Any, project_id: int, *, snapshot_source: str | None, own_build: bool = False,
) -> None:
    """The calling pass has ended; ``snapshot_source`` says it changed what Signals reads.

    When others of the project's passes still code, the rebuild is owed and the last
    of them to end starts it, once (D21): until 23 Nov 2026 each finished apply built
    its own, so three codebooks applied at once paid for three builds, the first two
    over tags the third was still changing. The build is its own task: a catch-up
    that happens to end last must not run another pass's paid build inside its own
    task, which the import pause, a run's re-apply and the debounced trigger all wait
    on. ``own_build`` (an apply that asked for the build itself) awaits it, so its busy
    mark covers it.
    """
    me = asyncio.current_task()
    if me is not None:
        _LIVE_CODING.get(project_id, set()).discard(me)
    if snapshot_source is not None:
        _owe_snapshot(project_id, snapshot_source)
    if _others_coding(project_id, me):
        return
    source = _take_owed_snapshot(project_id)
    if source is None:
        return
    build = _start_snapshot_build(app, project_id, source)
    if own_build and snapshot_source is not None:
        await build


def _start_snapshot_build(app: Any, project_id: int, source: str) -> asyncio.Task[Any]:
    task = asyncio.ensure_future(build_signal_snapshot(app, project_id, source))
    _SNAPSHOT_TASKS.add(task)
    task.add_done_callback(_SNAPSHOT_TASKS.discard)
    return task


async def build_signal_snapshot(app: Any, project_id: int, source: str) -> None:
    """Materialise the project's Signals report now. Never raises: a codebook stays
    applied whatever its optional synthesis meets, and the next trigger tries again.

    Cost: ``materialise_completed_signal_snapshot`` elaborates the report's cards, one
    LLM call per codebook with a card whose evidence changed since its cached
    narrative, and none when every card is cached (``elaboration.generate_elaborations``).
    """
    from bristlenose.server.signal_snapshots import (
        begin_signals_preparing,
        end_signals_preparing,
    )

    begin_signals_preparing(app.state)
    db: SASession | None = None
    try:
        from bristlenose.server.routes.signals import materialise_completed_signal_snapshot

        db = app.state.db_factory()
        await materialise_completed_signal_snapshot(
            db, project_id, source=source,
            project_dir=getattr(app.state, "project_dir", None),
        )
    except Exception as exc:
        if db is not None:
            with contextlib.suppress(Exception):
                db.rollback()
        if _is_db_error(exc):
            logger.error("Signal snapshot (%s) for project %s failed: the database (%s)",
                         source, project_id, _db_error_name(exc))
        else:
            logger.exception("Signal snapshot (%s) for project %s failed", source, project_id)
    finally:
        if db is not None:
            with contextlib.suppress(Exception):
                db.close()
        end_signals_preparing(app.state)


def recut_made(app: Any, project_id: int) -> None:
    """The review's lines were applied (the dialog's re-cut, or accept-all or deny-all
    with the dialog's lines) and moved at least one proposal; a call that moved none
    does not come here (D31)."""
    signals_changed(app, project_id, "codebook_recut")


def signals_changed(app: Any, project_id: int, source: str) -> None:
    """Accepted tags changed outside a first apply (a re-cut; never a catch-up pass,
    D31): rebuild Signals once the burst settles, or, while a pass still
    codes, when the last one ends. Callable from a route's worker thread or the loop;
    never raises."""
    try:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            from anyio import from_thread

            from_thread.run_sync(_arm_recut_snapshot, app, project_id, source)
            return
        _arm_recut_snapshot(app, project_id, source)
    except Exception:
        logger.warning("Could not schedule a Signals rebuild (%s)", source, exc_info=True)


def _arm_recut_snapshot(app: Any, project_id: int, source: str) -> None:
    loop = asyncio.get_running_loop()
    handle = _RECUT_TIMERS.pop(project_id, None)
    if handle is not None:
        handle.cancel()
    _RECUT_TIMERS[project_id] = loop.call_later(
        RECUT_SNAPSHOT_DEBOUNCE_S, _fire_recut_snapshot, app, project_id, source,
    )


def _fire_recut_snapshot(app: Any, project_id: int, source: str) -> None:
    _RECUT_TIMERS.pop(project_id, None)
    if _others_coding(project_id, None):
        _owe_snapshot(project_id, source)
        return
    _start_snapshot_build(app, project_id, source)
