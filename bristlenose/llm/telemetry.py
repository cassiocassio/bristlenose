"""Per-LLM-call telemetry — appends one JSONL row per terminal outcome.

Writes ``<run_dir>/llm-calls.jsonl`` where ``run_dir`` is the project's
``.bristlenose/`` directory (set by ``run_lifecycle`` via a ``ContextVar``).
Schema is OTel-aligned (``gen_ai.usage.input_tokens`` etc.) for forward
compatibility with vendor exporters; field aliases are configured on
:class:`LLMCallEvent`.

**Trust boundary.** The JSONL is a re-identification key — it carries
session ids, prompt shas, and timing fingerprints. Mode ``0o600`` and
``O_NOFOLLOW`` apply; never include this file in any export, support
bundle, or shareable archive (mirrors the ``pii_summary.txt`` discipline).

**Atomicity.** Rows are ~700 B in practice, well under macOS/Linux
``PIPE_BUF`` (≥4 KB). A single ``os.write()`` of an appended line is
atomic on local filesystems, so multiple concurrent writers do not
interleave. We do **not** ``fsync`` per call — telemetry is statistical,
not forensic. ``fsync`` happens at run terminus via :func:`trim_to_cap`.

**Kill switch.** Set ``BRISTLENOSE_LLM_TELEMETRY=0`` to short-circuit
:func:`record_call` to a no-op. The read path tolerates missing/empty
JSONL.

**Retention.** ``BRISTLENOSE_LLM_CALLS_RETAIN`` (default 1000) caps the
file. Trim is invoked from ``run_lifecycle`` at run terminus.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .cohort_normalise import normalise_model

JSONL_FILENAME = "llm-calls.jsonl"
DEFAULT_RETENTION = 1000

_run_id: ContextVar[str | None] = ContextVar("_run_id", default=None)
_run_dir: ContextVar[Path | None] = ContextVar("_run_dir", default=None)
_stage_id: ContextVar[str | None] = ContextVar("_stage_id", default=None)
_session_id: ContextVar[str | None] = ContextVar("_session_id", default=None)


class LLMCallEvent(BaseModel):
    """One terminal LLM call outcome — schema for ``llm-calls.jsonl`` rows.

    OTel-aligned dotted aliases are used on the wire (e.g.
    ``"gen_ai.usage.input_tokens"``); Python attribute names use
    underscores. Both forms round-trip via ``populate_by_name=True``.
    """

    model_config = ConfigDict(populate_by_name=True)

    schema_version: int = 1
    ts: str
    run_id: str
    session_id: str | None = None
    stage: str
    gen_ai_system: str = Field(alias="gen_ai.system")
    gen_ai_operation_name: str = Field(default="chat", alias="gen_ai.operation.name")
    gen_ai_request_model: str = Field(alias="gen_ai.request.model")
    gen_ai_response_model: str | None = Field(default=None, alias="gen_ai.response.model")
    model_family: str
    model_major: str
    prompt_id: str | None = None
    prompt_version: str | None = None
    prompt_path: str | None = None
    prompt_sha: str | None = None
    input_chars: int
    input_tokens: int | None = Field(default=None, alias="gen_ai.usage.input_tokens")
    output_tokens: int | None = Field(default=None, alias="gen_ai.usage.output_tokens")
    cache_read_input_tokens: int | None = Field(
        default=None, alias="gen_ai.usage.cache_read_input_tokens"
    )
    cache_creation_input_tokens: int | None = Field(
        default=None, alias="gen_ai.usage.cache_creation_input_tokens"
    )
    elapsed_ms: int
    retry_count: int = 0
    finish_reason: str | None = None
    outcome: Literal["ok", "truncated", "error", "cancelled"]
    usage_source: Literal["reported", "missing"] = "reported"
    price_table_version: str
    cost_usd_actual_estimate: float | None = None
    cost_usd_predicted: float | None = None


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def set_run_context(run_id: str, run_dir: Path) -> tuple[object, object]:
    """Set the run-level contextvars; return reset tokens.

    Caller must invoke :func:`reset_run_context` with the returned tokens
    in a ``finally`` block to avoid leaking state across runs.
    """
    return _run_id.set(run_id), _run_dir.set(run_dir)


def reset_run_context(tokens: tuple[object, object]) -> None:
    """Restore run-level contextvars from tokens returned by :func:`set_run_context`."""
    run_id_token, run_dir_token = tokens
    _run_id.reset(run_id_token)  # type: ignore[arg-type]
    _run_dir.reset(run_dir_token)  # type: ignore[arg-type]


@contextmanager
def stage(name: str) -> Iterator[None]:
    """Bind ``_stage_id`` for the duration of the block."""
    token = _stage_id.set(name)
    try:
        yield
    finally:
        _stage_id.reset(token)


@contextmanager
def session(participant_id: str) -> Iterator[None]:
    """Bind ``_session_id`` for the duration of the block."""
    token = _session_id.set(participant_id)
    try:
        yield
    finally:
        _session_id.reset(token)


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def _telemetry_enabled() -> bool:
    return os.environ.get("BRISTLENOSE_LLM_TELEMETRY", "1") != "0"


def _retention_cap() -> int:
    raw = os.environ.get("BRISTLENOSE_LLM_CALLS_RETAIN")
    if raw is None:
        return DEFAULT_RETENTION
    try:
        cap = int(raw)
    except ValueError:
        return DEFAULT_RETENTION
    return cap if cap > 0 else DEFAULT_RETENTION


def record_call(
    *,
    provider: str,
    request_model: str,
    response_model: str | None,
    input_chars: int,
    elapsed_ms: int,
    outcome: Literal["ok", "truncated", "error", "cancelled"],
    price_table_version: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cache_read_input_tokens: int | None = None,
    cache_creation_input_tokens: int | None = None,
    retry_count: int = 0,
    finish_reason: str | None = None,
    usage_source: Literal["reported", "missing"] = "reported",
    prompt_id: str | None = None,
    prompt_version: str | None = None,
    prompt_path: str | None = None,
    prompt_sha: str | None = None,
    cost_usd_actual_estimate: float | None = None,
    cost_usd_predicted: float | None = None,
    operation_name: str = "chat",
    run_dir: Path | None = None,
    run_id: str | None = None,
    stage_override: str | None = None,
    session_id_override: str | None = None,
) -> None:
    """Append one terminal LLM-call event to ``<run_dir>/llm-calls.jsonl``.

    Silently no-ops when telemetry is disabled, when no run context is
    active, or when the contextvar-derived ``run_dir`` is missing. The
    caller-side overrides (``run_dir``, ``run_id``, ``stage_override``,
    ``session_id_override``) exist for tests; production code relies on
    the contextvars set by ``run_lifecycle`` and the ``stage`` / ``session``
    context managers.
    """
    if not _telemetry_enabled():
        return

    target_dir = run_dir if run_dir is not None else _run_dir.get()
    if target_dir is None:
        return

    rid = run_id if run_id is not None else _run_id.get()
    if rid is None:
        return

    stg = stage_override if stage_override is not None else _stage_id.get()
    if stg is None:
        return

    sid = session_id_override if session_id_override is not None else _session_id.get()

    family, major = normalise_model(provider, response_model or request_model)

    event = LLMCallEvent(
        ts=datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        ),
        run_id=rid,
        session_id=sid,
        stage=stg,
        **{  # type: ignore[arg-type]
            "gen_ai.system": provider,
            "gen_ai.operation.name": operation_name,
            "gen_ai.request.model": request_model,
            "gen_ai.response.model": response_model,
            "gen_ai.usage.input_tokens": input_tokens,
            "gen_ai.usage.output_tokens": output_tokens,
            "gen_ai.usage.cache_read_input_tokens": cache_read_input_tokens,
            "gen_ai.usage.cache_creation_input_tokens": cache_creation_input_tokens,
        },
        model_family=family,
        model_major=major,
        prompt_id=prompt_id,
        prompt_version=prompt_version,
        prompt_path=prompt_path,
        prompt_sha=prompt_sha,
        input_chars=input_chars,
        elapsed_ms=elapsed_ms,
        retry_count=retry_count,
        finish_reason=finish_reason,
        outcome=outcome,
        usage_source=usage_source,
        price_table_version=price_table_version,
        cost_usd_actual_estimate=cost_usd_actual_estimate,
        cost_usd_predicted=cost_usd_predicted,
    )

    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / JSONL_FILENAME
    line = event.model_dump_json(by_alias=True, exclude_none=False) + "\n"
    data = line.encode("utf-8")

    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


def trim_to_cap(path: Path, cap: int | None = None) -> int:
    """Trim ``path`` in place to the last ``cap`` lines.

    Atomic-rewrite: writes to a sibling tempfile then ``os.replace``.
    Fsyncs the tempfile and the parent directory before replace so the
    final state survives crashes (one fsync per run, not per call).
    Returns the number of lines retained. No-op if file missing or
    already within cap.
    """
    if cap is None:
        cap = _retention_cap()
    if cap <= 0:
        return 0
    if not path.exists():
        return 0

    with path.open("rb") as f:
        lines = f.readlines()
    if len(lines) <= cap:
        return len(lines)

    keep = lines[-cap:]
    parent = path.parent
    fd, tmp_name = tempfile.mkstemp(prefix=".llm-calls.", suffix=".tmp", dir=parent)
    tmp_path = Path(tmp_name)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, b"".join(keep))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp_path, path)
    # Best-effort directory fsync — not portable on every FS but safe
    # to skip if EINVAL etc.
    try:
        dir_fd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass
    return len(keep)


def trim_run_terminus(run_dir: Path | None = None) -> int:
    """Trim the active run's JSONL. Convenience wrapper for ``run_lifecycle``."""
    target = run_dir if run_dir is not None else _run_dir.get()
    if target is None:
        return 0
    return trim_to_cap(target / JSONL_FILENAME)


def iter_rows(run_dir: Path) -> Iterator[dict[str, object]]:
    """Yield parsed JSON rows from ``<run_dir>/llm-calls.jsonl``.

    Read-side helper for the forecast (Slice C) and tests. Tolerates
    missing file, blank lines, and malformed rows (the latter are
    skipped, not raised — telemetry is statistical).
    """
    path = run_dir / JSONL_FILENAME
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
