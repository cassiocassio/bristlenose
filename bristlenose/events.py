"""Run-level event log — Phase 4a-pre.

Append-only NDJSON at ``<output_dir>/.bristlenose/pipeline-events.jsonl``.
One JSON object per line; every mutation is an event.

This is the **single source of truth for run-level outcome data**. The
manifest (``manifest.py``) keeps its existing per-stage-resume job;
"current run state" is derived by tail-reading this log.

See ``docs/design-pipeline-resilience.md`` §"Run outcomes and intent" for
the full design.
"""

from __future__ import annotations

import json
import math
import os
import secrets
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from bristlenose.manifest import (
    PipelineManifest,
    StageStatus,
    load_manifest,
)

EVENTS_FILENAME = "pipeline-events.jsonl"
SCHEMA_VERSION = 1

# 4 KB cap on cause.message — protects Swift's 64 KB readLogTail window.
CAUSE_MESSAGE_MAX = 4096

# Max StageFailure entries persisted per StageOutcome.failed list. With
# CAUSE_MESSAGE_MAX (4 KB), a 50-failure stage could otherwise produce a
# 200 KB terminus line and bust the desktop's 64 KB readLogTail window
# (silent event drop → "state unknown" pill). 10 keeps the worst-case
# line under 64 KB while still surfacing enough per-session detail for
# the diagnostic-pill popover. The truncation appends a synthetic
# placeholder entry recording the dropped count, so the desktop can show
# "+ N more failures" without re-reading the original log.
STAGE_FAILED_MAX = 10


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class KindEnum(str, Enum):
    """What was attempted. Render is intentionally absent — see design doc."""

    RUN = "run"
    ANALYZE = "analyze"
    TRANSCRIBE_ONLY = "transcribe-only"


class OutcomeEnum(str, Enum):
    """Terminus outcome. No `running` — in-flight is absence of terminus."""

    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ReflowScopeEnum(str, Enum):
    """How much the report display must change after an incremental run.

    Drives the desktop idle-flag reflow hold (design-incremental-analysis §9):
    ``none`` skips the hold entirely (nothing changed downstream of
    transcription); ``additive`` can reflow immediately (new quotes landed but
    no pre-existing quote's section/theme membership shifted); ``restructure``
    waits for the user to be idle (membership may move underneath them). Emit
    ``restructure`` conservatively when additive-vs-restructure can't be
    distinguished — the UX just holds longer than strictly necessary.
    """

    NONE = "none"
    ADDITIVE = "additive"
    RESTRUCTURE = "restructure"


class CauseCategoryEnum(str, Enum):
    """Dispatch enum for failure / cancellation cause.

    Names match shipped Swift ``PipelineFailureCategory`` exactly so there
    is no rename across the boundary. Existing cases (auth, network, quota,
    disk, whisper, unknown) preserved; Phase 1f extends additively.
    """

    USER_SIGNAL = "user_signal"
    AUTH = "auth"
    OUT_OF_CREDIT = "out_of_credit"  # billing exhausted; terminal until top-up
    QUOTA = "quota"  # rate-limited / transient quota; back off and retry
    API_REQUEST = "api_request"
    API_SERVER = "api_server"
    NETWORK = "network"
    WHISPER = "whisper"
    MISSING_DEP = "missing_dep"
    MISSING_INPUT = "missing_input"
    MISSING_BINARY = "missing_binary"
    DISK = "disk"
    OUTPUT_TRUNCATED = "output_truncated"
    UNKNOWN = "unknown"


class EventTypeEnum(str, Enum):
    RUN_STARTED = "run_started"
    RUN_PROGRESS = "run_progress"
    RUN_COMPLETED = "run_completed"
    RUN_CANCELLED = "run_cancelled"
    RUN_FAILED = "run_failed"


# Retryable rule — single source of truth (Swift mirrors).
_RETRYABLE: dict[CauseCategoryEnum, bool] = {
    CauseCategoryEnum.USER_SIGNAL: True,
    CauseCategoryEnum.AUTH: False,
    # Out of credit — re-running before a top-up fails identically, like AUTH.
    CauseCategoryEnum.OUT_OF_CREDIT: False,
    CauseCategoryEnum.QUOTA: True,
    CauseCategoryEnum.API_REQUEST: True,  # depends on `code`; default true
    CauseCategoryEnum.API_SERVER: True,
    CauseCategoryEnum.NETWORK: True,
    CauseCategoryEnum.WHISPER: True,  # depends on `code`; default true
    CauseCategoryEnum.MISSING_DEP: False,
    CauseCategoryEnum.MISSING_INPUT: False,
    CauseCategoryEnum.MISSING_BINARY: False,
    CauseCategoryEnum.DISK: False,
    # Re-running the same provider/model truncates again deterministically;
    # recovery requires switching model or pre-segmenting, so not retryable.
    CauseCategoryEnum.OUTPUT_TRUNCATED: False,
    CauseCategoryEnum.UNKNOWN: True,
}


def is_retryable(category: CauseCategoryEnum) -> bool:
    """Return whether a cause category is retryable.

    Swift mirrors this rule. Don't store on disk — derive from category.
    """
    return _RETRYABLE[category]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Cause(BaseModel):
    """Structured forensic cause for cancelled / failed runs."""

    category: CauseCategoryEnum
    code: str | None = None
    message: str | None = None
    provider: str | None = None
    stage: str | None = None
    session_id: str | None = None
    exit_code: int | None = None
    signal: int | None = None
    signal_name: str | None = None

    @field_validator("message", mode="before")
    @classmethod
    def _cap_message(cls, v: object) -> object:
        """Cap message at 4 KB at write time — protects Swift's read window."""
        if isinstance(v, str) and len(v.encode("utf-8")) > CAUSE_MESSAGE_MAX:
            # Truncate by bytes, not chars, to keep the cap honest.
            encoded = v.encode("utf-8")[:CAUSE_MESSAGE_MAX]
            # Drop a trailing partial UTF-8 sequence (rare edge case).
            v = encoded.decode("utf-8", errors="ignore")
        return v


class StageFailure(BaseModel):
    """One per-session (or stage-wide) failure caught inside a stage.

    ``session_id`` is None for stage-wide failures that aren't session-scoped
    (e.g. a single LLM call across all quotes in s11). The Cause carries the
    same shape used at run-level so the desktop can reuse its rendering.
    """

    session_id: str | None = None
    cause: Cause


class StageOutcome(BaseModel):
    """Per-stage rollup: how many were attempted, how many succeeded, what failed.

    ``duration_ms`` is the wall-clock the orchestrator spent in this stage on
    *this* run (not cumulative across resumes). The Swift popover renders it
    Xcode-build-log-style in a monospace trailing column. ``None`` when the
    stage didn't run (cache hit on every entry, or the stage was skipped) —
    distinct from ``0`` which would mean "ran but instantaneous".
    """

    attempted: int = 0
    succeeded: int = 0
    failed: list[StageFailure] = Field(default_factory=list)
    duration_ms: int | None = None


class PipelineSummary(BaseModel):
    """Per-pipeline-stage outcome rollup attached to terminus events.

    Each field is None when the corresponding stage didn't run (e.g.
    transcripts is None for ``analyze``; quotes / themes are None for
    ``transcribe-only``). Empty ``failed`` list means full success.
    """

    transcripts: StageOutcome | None = None
    topics: StageOutcome | None = None
    quotes: StageOutcome | None = None
    themes: StageOutcome | None = None
    # Incremental-run deltas — None on a first/full run. ``new_sessions`` drives
    # the desktop "+N new sessions" post-completion subtitle; ``reflow_scope``
    # drives the idle-flag reflow hold. Counts only (re-id-safe). Contract:
    # docs/private/handoffs/incremental-ux-glue.md.
    new_sessions: int | None = None
    reflow_scope: ReflowScopeEnum | None = None


class PipelineAbandonedError(Exception):
    """Pipeline produced no usable data; report MUST NOT be written.

    Raised when an entire stage's attempts all failed (e.g. every session's
    transcription raised, or every quote-extraction LLM call raised). The
    ``summary`` carries whatever partial outcome data was accumulated up to
    the abandon point so the terminus event can render a useful diagnostic.
    """

    def __init__(self, cause: Cause, summary: PipelineSummary) -> None:
        super().__init__(cause.message or "Pipeline abandoned")
        self.cause = cause
        self.summary = summary


class Process(BaseModel):
    """Diagnostics envelope captured once on run_started."""

    pid: int
    start_time: str  # ISO8601 — process creation time
    hostname: str
    user: str
    bristlenose_version: str
    python_version: str
    os: str  # e.g. "darwin-arm64"


class _EventBase(BaseModel):
    schema_version: int = SCHEMA_VERSION
    ts: str
    event: EventTypeEnum
    run_id: str
    kind: KindEnum
    started_at: str


class RunStartedEvent(_EventBase):
    event: EventTypeEnum = EventTypeEnum.RUN_STARTED
    process: Process


class RunProgressEvent(_EventBase):
    """In-flight progress — NOT a lifecycle/terminus event.

    Emitted per-stage and (for transcription) within-file. Carries counts
    and timings ONLY — never an id, filename, speaker label, or any
    transcript-derived string, so it never becomes a re-identification
    surface (sibling rule to ``pii_summary.txt`` / ``llm-calls.jsonl``).
    Readers that derive run *state* (in-flight vs terminus) MUST skip these
    — see ``tail_run_state`` / ``_reconcile_stranded_run`` and the Swift
    ``EventLogReader``. A trailing progress line is not a terminus.
    """

    event: EventTypeEnum = EventTypeEnum.RUN_PROGRESS
    stage: str | None = None
    sessions_complete: int | None = None
    sessions_total: int | None = None
    # Corpus-level new-vs-cached session breakdown for the whole run: how many
    # of the project's sessions are fresh work this run vs carried over from
    # cache. **Independent of the stage-scoped ``sessions_complete``/
    # ``sessions_total`` above** — those count only the current stage's batch
    # (e.g. transcription's batch excludes subtitle/docx sessions, which are
    # never re-transcribed), so ``sessions_new`` may exceed ``sessions_total``.
    # Matches ``PipelineSummary.new_sessions`` at completion. Counts only
    # (re-id-safe). None only on a full cache-hit run, which emits no progress.
    sessions_new: int | None = None
    sessions_cached: int | None = None
    # 0..1 measured within-stage progress where the backend exposes it
    # (e.g. within-file audio fraction on faster-whisper); None otherwise.
    stage_fraction: float | None = None
    eta_remaining_seconds: float | None = None
    predicted_total_seconds: float | None = None
    # Python-measured elapsed; reserved for the orphan-attach elapsed baseline
    # (Swift can't measure it from a mid-run attach). Not yet read Swift-side.
    elapsed_seconds: float | None = None

    @field_validator(
        "stage_fraction",
        "eta_remaining_seconds",
        "predicted_total_seconds",
        "elapsed_seconds",
        mode="before",
    )
    @classmethod
    def _finite_or_none(cls, v: object) -> object:
        """Coerce non-finite floats (inf/nan) to None.

        A degenerate Welford profile can yield inf/nan; pydantic would emit
        bare ``Infinity`` / ``NaN`` (invalid JSON) which Swift's JSONDecoder
        silently rejects. None makes "no estimate" explicit instead.
        """
        if isinstance(v, float) and not math.isfinite(v):
            return None
        return v


class _TerminusEvent(_EventBase):
    ended_at: str
    outcome: OutcomeEnum
    cause: Cause | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd_estimate: float | None = None
    price_table_version: str | None = None
    # Per-stage outcome rollup. None when the run didn't reach a stage that
    # would have populated it (e.g. crashed in ingest); also None on legacy
    # event lines emitted before this field existed (decode-compatible).
    summary: PipelineSummary | None = None


class RunCompletedEvent(_TerminusEvent):
    event: EventTypeEnum = EventTypeEnum.RUN_COMPLETED
    outcome: OutcomeEnum = OutcomeEnum.COMPLETED
    cause: None = None  # always null


class RunCancelledEvent(_TerminusEvent):
    event: EventTypeEnum = EventTypeEnum.RUN_CANCELLED
    outcome: OutcomeEnum = OutcomeEnum.CANCELLED
    cause: Cause = Field(...)  # required


class RunFailedEvent(_TerminusEvent):
    event: EventTypeEnum = EventTypeEnum.RUN_FAILED
    outcome: OutcomeEnum = OutcomeEnum.FAILED
    cause: Cause = Field(...)  # required

    @field_validator("cause")
    @classmethod
    def _message_required_for_non_user_signal(cls, v: Cause) -> Cause:
        """Writer rule: message must be populated for non-user_signal causes."""
        if v.category != CauseCategoryEnum.USER_SIGNAL and not v.message:
            raise ValueError(
                "Cause.message is required when category != user_signal "
                "(use str(exc) if nothing better is available)",
            )
        return v


# Convenience union — discriminate by `event` field on read.
AnyEvent = (
    RunStartedEvent
    | RunProgressEvent
    | RunCompletedEvent
    | RunCancelledEvent
    | RunFailedEvent
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def events_path(output_dir: Path) -> Path:
    return output_dir / ".bristlenose" / EVENTS_FILENAME


# Crockford base32 alphabet — ULID spec.
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_run_id() -> str:
    """Generate a fresh ULID — 26-char Crockford-base32, sortable by time.

    No external dep — ULIDs are 128 bits = 48-bit ms timestamp + 80 bits
    randomness, encoded in Crockford base32.
    """
    ts_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand_bits = secrets.randbits(80)
    value = (ts_ms << 80) | rand_bits
    out: list[str] = []
    for _ in range(26):
        out.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(out))


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def _truncate_failed(outcome: StageOutcome | None) -> StageOutcome | None:
    """Cap ``outcome.failed`` at STAGE_FAILED_MAX and append a placeholder.

    Returns the (possibly new) StageOutcome — caller should swap it in.
    Pure: never mutates the input.
    """
    if outcome is None or len(outcome.failed) <= STAGE_FAILED_MAX:
        return outcome
    dropped = len(outcome.failed) - STAGE_FAILED_MAX
    placeholder = StageFailure(
        session_id=None,
        cause=Cause(
            category=CauseCategoryEnum.UNKNOWN,
            message=f"... and {dropped} more failures truncated",
        ),
    )
    return outcome.model_copy(update={
        "failed": [*outcome.failed[:STAGE_FAILED_MAX], placeholder],
    })


def _truncate_event_summary(event: AnyEvent) -> AnyEvent:
    """Apply STAGE_FAILED_MAX to a terminus event's per-stage failed lists.

    No-op for RunStartedEvent (no summary field) and for events whose
    summary.{transcripts,topics,quotes,themes} all stay under the cap.
    """
    summary = getattr(event, "summary", None)
    if summary is None:
        return event
    new_t = _truncate_failed(summary.transcripts)
    new_topics = _truncate_failed(summary.topics)
    new_q = _truncate_failed(summary.quotes)
    new_th = _truncate_failed(summary.themes)
    if (
        new_t is summary.transcripts
        and new_topics is summary.topics
        and new_q is summary.quotes
        and new_th is summary.themes
    ):
        return event  # nothing changed
    new_summary = summary.model_copy(update={
        "transcripts": new_t,
        "topics": new_topics,
        "quotes": new_q,
        "themes": new_th,
    })
    return event.model_copy(update={"summary": new_summary})


def append_event(events_file: Path, event: AnyEvent) -> None:
    """Append one event line atomically.

    Uses ``O_APPEND`` + ``fsync``. POSIX guarantees seek-to-end-and-write
    is atomic per ``write()`` call on regular files; concurrent appenders
    that single-write a line under PIPE_BUF (4 KB on macOS) don't tear.
    The 4 KB cap on ``Cause.message`` keeps individual messages bounded;
    ``STAGE_FAILED_MAX`` (10) caps each per-stage ``failed`` list so a
    50-session failure doesn't produce a 200 KB terminus line that would
    bust the desktop's 64 KB ``readLogTail`` window. The
    ``ConcurrentRunError`` PID-file check is the real guard against
    parallel writers, since the manifest and SQLite DB also race.

    Mode 0o600 + O_NOFOLLOW: events log contains the OS username +
    hostname in the process envelope; restrict readability to the
    project owner and refuse to follow symlink-attacked paths.

    Survives process crashes (fsync). Power-loss durability is NOT
    promised on macOS — that requires F_FULLFSYNC, deferred per design doc.
    """
    events_file.parent.mkdir(parents=True, exist_ok=True)
    event = _truncate_event_summary(event)
    line = event.model_dump_json(exclude_none=False) + "\n"
    data = line.encode("utf-8")

    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW
    fd = os.open(events_file, flags, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------
# Reader / tail
# ---------------------------------------------------------------------------


class RunState(BaseModel):
    """Derived current state from tail of events log + manifest.

    ``stages_complete`` is read from the manifest at display time, not
    stored in the events log (manifest is single source of truth for
    stage state — see design doc).
    """

    # The most recent run_* event, parsed. None if log missing/empty.
    last_event: AnyEvent | None = None
    # True when the tail is run_started without a following terminus.
    in_flight: bool = False
    # Stages marked complete in the manifest (derived at read time).
    stages_complete: list[str] = Field(default_factory=list)


def _parse_event_line(line: str) -> AnyEvent | None:
    """Parse one JSONL line into the right event model. None on malformed."""
    line = line.strip()
    if not line or line.startswith("\x00"):
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    event_type = obj.get("event")
    try:
        if event_type == EventTypeEnum.RUN_STARTED.value:
            return RunStartedEvent.model_validate(obj)
        if event_type == EventTypeEnum.RUN_PROGRESS.value:
            return RunProgressEvent.model_validate(obj)
        if event_type == EventTypeEnum.RUN_COMPLETED.value:
            return RunCompletedEvent.model_validate(obj)
        if event_type == EventTypeEnum.RUN_CANCELLED.value:
            return RunCancelledEvent.model_validate(obj)
        if event_type == EventTypeEnum.RUN_FAILED.value:
            return RunFailedEvent.model_validate(obj)
    except Exception:
        return None
    return None


def _iter_event_lines(events_file: Path) -> list[str]:
    """Read all lines, discard NUL-padded / malformed trailing line.

    JSONL recovery recipe — power-loss can leave the trailing line as
    NULs; crash mid-write can leave it un-newline-terminated. Either way:
    drop and recover.
    """
    if not events_file.exists():
        return []
    raw = events_file.read_bytes()
    # Strip trailing NUL padding (power-loss tail).
    raw = raw.rstrip(b"\x00")
    if not raw:
        return []
    text = raw.decode("utf-8", errors="replace")
    lines = text.split("\n")
    # If the file didn't end with \n, the last entry is a partial line — drop it.
    if not text.endswith("\n") and lines:
        lines = lines[:-1]
    return [ln for ln in lines if ln.strip()]


def read_events(events_file: Path) -> list[AnyEvent]:
    """Read and parse all valid event lines. Skips malformed."""
    out: list[AnyEvent] = []
    for line in _iter_event_lines(events_file):
        ev = _parse_event_line(line)
        if ev is not None:
            out.append(ev)
    return out


def tail_run_state(events_file: Path, manifest_file: Path | None = None) -> RunState:
    """Derive current state from the tail of the events log + manifest.

    The most recent ``run_*`` event determines the state. If it is
    ``run_started`` with no following terminus, the run is in flight
    (PID liveness check happens in Slice 2 / Swift).
    """
    events = read_events(events_file)
    last_event: AnyEvent | None = None
    in_flight = False

    # Walk from the tail to find the most recent *lifecycle* event.
    # run_progress lines are in-flight telemetry, not state — skip them, or
    # a trailing progress line would mask the real terminus and mark a live
    # run as "not in flight" (Finding 1).
    for ev in reversed(events):
        if isinstance(ev, RunProgressEvent):
            continue
        last_event = ev
        in_flight = isinstance(ev, RunStartedEvent)
        break

    stages_complete: list[str] = []
    if manifest_file is not None and manifest_file.exists():
        # Derive stages_complete from manifest — single source of truth.
        manifest_dir = manifest_file.parent.parent  # .bristlenose/ -> output_dir
        loaded: PipelineManifest | None = load_manifest(manifest_dir)
        if loaded is not None:
            stages_complete = [
                name
                for name, rec in loaded.stages.items()
                if rec.status == StageStatus.COMPLETE
            ]

    return RunState(
        last_event=last_event,
        in_flight=in_flight,
        stages_complete=stages_complete,
    )
