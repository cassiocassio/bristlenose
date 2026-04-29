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


class CauseCategoryEnum(str, Enum):
    """Dispatch enum for failure / cancellation cause.

    Names match shipped Swift ``PipelineFailureCategory`` exactly so there
    is no rename across the boundary. Existing cases (auth, network, quota,
    disk, whisper, unknown) preserved; Phase 1f extends additively.
    """

    USER_SIGNAL = "user_signal"
    AUTH = "auth"
    QUOTA = "quota"
    API_REQUEST = "api_request"
    API_SERVER = "api_server"
    NETWORK = "network"
    WHISPER = "whisper"
    MISSING_DEP = "missing_dep"
    DISK = "disk"
    UNKNOWN = "unknown"


class EventTypeEnum(str, Enum):
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_CANCELLED = "run_cancelled"
    RUN_FAILED = "run_failed"


# Retryable rule — single source of truth (Swift mirrors).
_RETRYABLE: dict[CauseCategoryEnum, bool] = {
    CauseCategoryEnum.USER_SIGNAL: True,
    CauseCategoryEnum.AUTH: False,
    CauseCategoryEnum.QUOTA: True,
    CauseCategoryEnum.API_REQUEST: True,  # depends on `code`; default true
    CauseCategoryEnum.API_SERVER: True,
    CauseCategoryEnum.NETWORK: True,
    CauseCategoryEnum.WHISPER: True,  # depends on `code`; default true
    CauseCategoryEnum.MISSING_DEP: False,
    CauseCategoryEnum.DISK: False,
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


class _TerminusEvent(_EventBase):
    ended_at: str
    outcome: OutcomeEnum
    cause: Cause | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd_estimate: float | None = None
    price_table_version: str | None = None


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
    RunStartedEvent | RunCompletedEvent | RunCancelledEvent | RunFailedEvent
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


def append_event(events_file: Path, event: AnyEvent) -> None:
    """Append one event line atomically.

    Uses ``O_APPEND`` + ``fsync``. POSIX guarantees seek-to-end-and-write
    is atomic per ``write()`` call on regular files; concurrent appenders
    that single-write a line under PIPE_BUF (4 KB on macOS) don't tear.
    The 4 KB cap on ``Cause.message`` keeps run-level events under that
    bound; the ``ConcurrentRunError`` PID-file check is the real guard
    against parallel writers, since the manifest and SQLite DB also race.

    Mode 0o600 + O_NOFOLLOW: events log contains the OS username +
    hostname in the process envelope; restrict readability to the
    project owner and refuse to follow symlink-attacked paths.

    Survives process crashes (fsync). Power-loss durability is NOT
    promised on macOS — that requires F_FULLFSYNC, deferred per design doc.
    """
    events_file.parent.mkdir(parents=True, exist_ok=True)
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

    # Walk from the tail to find the most recent run_* event.
    for ev in reversed(events):
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
