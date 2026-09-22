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

**Kill switch.** Set ``BRISTLENOSE_LLM_TELEMETRY=0`` *before launching
the process* to short-circuit :func:`record_call` to a no-op. The env
var is read on every call but processes inherit a fixed env at fork
time, so flipping the variable in a sibling shell does **not** affect
an already-running ``bristlenose serve`` or pipeline run. The read
path tolerates missing/empty JSONL.

**Retention.** ``BRISTLENOSE_LLM_CALLS_RETAIN`` (default 1000) caps the
file. Trim is invoked from ``run_lifecycle`` at run terminus.
"""

from __future__ import annotations

import json
import logging
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

logger = logging.getLogger(__name__)

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
    # SHA of the on-disk prompt template file (before user-data
    # substitution). Identifies the prompt version, never hashes
    # rendered prompt content with transcripts in it.
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
def serve_run_context(project_dir: Path | None, run_id: str) -> Iterator[None]:
    """Bind the run context for a SERVE-time LLM call, then restore it.

    Serve mode has no pipeline run to inherit from, so anything that calls an
    LLM from a request has to bind its own — and if it does not, `record_call`
    finds no `_run_dir`, logs at DEBUG and returns. **A whole surface's spend
    then goes unrecorded with no error anywhere**, which is how signal
    elaboration ran for a week logging nothing: it bound `stage(...)`, which is
    the visible half, and never the run context, which is the half that decides
    whether the row has anywhere to go.

    `project_dir` may be the project root or the output dir; both are accepted
    because callers have one or the other and guessing wrong writes the file
    somewhere nobody looks. A `None` is not an error — it means the app was not
    started with a project — and yields without binding, which restores the old
    silent-skip for that case alone.

    NB `server/autocode.py` still inlines this; it predates the helper and works.
    A third serve-time LLM caller should use this rather than a third copy.
    """
    if project_dir is None:
        yield
        return
    output_dir = project_dir / "bristlenose-output"
    if not output_dir.is_dir():
        output_dir = project_dir
    tokens = set_run_context(run_id, output_dir / ".bristlenose")
    try:
        yield
    finally:
        reset_run_context(tokens)


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


def _price_with_either_model(
    request_model: str,
    response_model: str | None,
    input_tokens: int,
    output_tokens: int,
) -> float | None:
    """Price against the response model, falling back to the request model.

    The response model is what was billed, but it is frequently unpriced or
    absent: a provider may answer ``gpt-4o`` with ``gpt-4o-2024-08-06``, and
    an errored call has no response model at all. The request model is what
    the user chose and is always in the table for a supported provider.
    """
    from .pricing import estimate_cost  # local: pricing imports iter_rows here

    for candidate in (response_model, request_model):
        if not candidate:
            continue
        cost = estimate_cost(candidate, input_tokens, output_tokens)
        if cost is not None:
            return cost
    return None


def _actual_cost(
    request_model: str,
    response_model: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    """Cost of the tokens this call actually reported.

    Still an *estimate* — provider billing carries invisible adjustments
    (cache discounts, batch tiers, custom contracts), which is why the field
    is ``cost_usd_actual_estimate`` and never ``cost_usd_actual``.
    """
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        return None
    return _price_with_either_model(
        request_model, response_model, input_tokens, output_tokens,
    )


def _predicted_cost(
    request_model: str,
    response_model: str | None,
    family: str,
    major: str,
    stage_id: str,
) -> float | None:
    """What the shipped baseline expected this call to cost.

    ``cost_usd_actual_estimate - cost_usd_predicted`` is the residual, which
    is the point of recording it: the median residual per cohort is a
    systematic-bias signal on the forecast, and its spread says whether a
    cohort wants splitting. Reads only the lru-cached baselines — never the
    JSONL — because this runs on every LLM call.
    """
    from .pricing import cohort_medians  # local: pricing imports iter_rows here

    medians = cohort_medians(family, major, stage_id)
    if medians is None:
        return None
    return _price_with_either_model(
        request_model, response_model, medians[0], medians[1],
    )


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

    ``cost_usd_actual_estimate`` and ``cost_usd_predicted`` are derived here
    when the caller leaves them ``None``, which every caller does. They were
    declared on the schema from Slice A and written by nothing until
    2026-09-21, so no row in any ``llm-calls.jsonl`` carried a cost —
    deriving them centrally covers every call site, pipeline and serve-mode
    alike, rather than asking each to remember. Either stays ``None`` when
    the model is unpriced (an Azure deployment name, a local Ollama tag) or
    when no baseline covers the cohort; the token counts are still worth
    recording, so that is not an error.
    """
    if not _telemetry_enabled():
        return

    target_dir = run_dir if run_dir is not None else _run_dir.get()
    if target_dir is None:
        logger.debug("record_call: no _run_dir contextvar set, skipping")
        return

    rid = run_id if run_id is not None else _run_id.get()
    if rid is None:
        logger.debug("record_call: no _run_id contextvar set, skipping")
        return

    stg = stage_override if stage_override is not None else _stage_id.get()
    if stg is None:
        logger.debug(
            "record_call: no _stage_id contextvar set "
            "(missing 'with telemetry.stage(...)' wrapper?), skipping"
        )
        return

    sid = session_id_override if session_id_override is not None else _session_id.get()

    family, major = normalise_model(provider, response_model or request_model)

    if cost_usd_actual_estimate is None:
        cost_usd_actual_estimate = _actual_cost(
            request_model, response_model, input_tokens, output_tokens,
        )
    if cost_usd_predicted is None:
        cost_usd_predicted = _predicted_cost(
            request_model, response_model, family, major, stg,
        )

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
