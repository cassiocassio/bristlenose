"""Token usage ledger: what a study has used, counted, never priced.

Layer 1 of three (``docs/design-llm-usage.md``): **counting**. Layer 2 turns
tokens into money in the researcher's currency; layer 3 decides where any of it
is shown. Nothing here knows a price, a currency or a surface, on purpose: the
counts are facts the provider returned, and they stay true when a price table
goes stale.

**Shape.** ``<output>/.bristlenose/usage.jsonl``, one row per job, provider
and model, appended when the job ends. A job is anything that spends tokens and
ends: a pipeline run, an AutoCode pass, a Signals elaboration, a chat-lens
question, a codebook-builder call. The study's total is the sum of its rows.

**How the counting reaches it.** ``telemetry.record_call`` (every provider's
calls pass through it) calls :func:`note_call`, which adds to an in-memory
tally keyed by run id. The job's end calls :func:`flush`, which writes the
tally out and forgets it. The per-call log ``llm-calls.jsonl`` is not read
back: it is capped at 1000 rows, so a total built from it would shrink.

**Not switched off with telemetry.** ``BRISTLENOSE_LLM_TELEMETRY=0`` stops the
per-call log, which can re-identify participants (session ids, prompt shas,
timings). These rows carry none of that, and a researcher who switched the one
off has not asked to lose the other.

**Survives a Re-analyse.** ``run --clean`` sets the output folder aside, so the
ledger is carried into the new one (``cli.py``), and a restored report gets a
failed run's rows back through ``output_backup._APPEND_ONLY``. That append
repeats the rows the carry copied, so :func:`read_rows` drops a row it has
already seen byte for byte (see its docstring for the key).

**What is not counted.** A process killed outright (SIGKILL, a power cut)
never reaches its flush, so its tokens are lost; a counted run is never
inflated, only an uncounted one is possible. A call whose provider reported no
usage is counted in ``calls`` and ``calls_without_usage``, with no tokens.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ValidationError

from bristlenose.utils.fs import open_private

logger = logging.getLogger(__name__)

USAGE_FILENAME = "usage.jsonl"
SCHEMA_VERSION = 1


class UsageRow(BaseModel):
    """One job's use of one model. The wire format of ``usage.jsonl``.

    ``model`` is the model the request named, which is the one the researcher
    chose: a response's snapshot name differs between calls of one run, and a
    failed call has none, so keying on it would split one choice into rows.
    """

    schema_version: int = SCHEMA_VERSION
    ts: str
    run_id: str
    kind: str
    provider: str
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    calls_without_usage: int


class UsageTotal(BaseModel):
    """A study's use of one provider and model, summed over its rows."""

    provider: str
    model: str
    jobs: int
    calls: int
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    calls_without_usage: int


class _Tally(BaseModel):
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    calls_without_usage: int = 0


# (run_id, provider, model) -> tally. A lock, not a contextvar: a pipeline
# stage's calls run in asyncio tasks and a serve's jobs in threads, and they
# all add to the same run's tally.
_tallies: dict[tuple[str, str, str], _Tally] = {}
_lock = threading.Lock()


def note_call(
    *,
    run_id: str,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    cache_read_input_tokens: int | None = None,
    cache_creation_input_tokens: int | None = None,
) -> None:
    """Add one LLM call to its run's tally. Never raises into the caller."""
    try:
        reported = input_tokens is not None or output_tokens is not None
        with _lock:
            tally = _tallies.setdefault((run_id, provider, model), _Tally())
            tally.calls += 1
            if not reported:
                tally.calls_without_usage += 1
            tally.input_tokens += input_tokens or 0
            tally.output_tokens += output_tokens or 0
            tally.cache_read_input_tokens += cache_read_input_tokens or 0
            tally.cache_creation_input_tokens += cache_creation_input_tokens or 0
    except Exception:
        logger.debug("usage note_call failed", exc_info=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def flush(run_dir: Path, run_id: str, kind: str) -> int:
    """Write *run_id*'s tally to ``<run_dir>/usage.jsonl`` and forget it.

    Returns the number of rows written: none when the job made no LLM call, so
    a run served from cache leaves the ledger as it was. Never raises: the end
    of a job is the wrong moment for bookkeeping to fail it, so a failure is
    logged at WARNING (the tokens are then uncounted, and the log says so).
    """
    with _lock:
        keys = [k for k in _tallies if k[0] == run_id]
        taken = [(k, _tallies.pop(k)) for k in keys]
    if not taken:
        return 0
    ts = _now_iso()
    lines = [
        UsageRow(
            ts=ts, run_id=run_id, kind=kind, provider=provider, model=model,
            **tally.model_dump(),
        ).model_dump_json() + "\n"
        for (_, provider, model), tally in taken
    ]
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        fd = open_private(run_dir / USAGE_FILENAME, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
        try:
            # One write: a job's rows land together or not at all, and a row
            # (~300 B) is far under PIPE_BUF, so writers do not interleave.
            os.write(fd, "".join(lines).encode("utf-8"))
        finally:
            os.close(fd)
    except OSError:
        logger.warning(
            "usage ledger not written run_id=%s kind=%s — this job's tokens are uncounted",
            run_id, kind, exc_info=True,
        )
        return 0
    return len(lines)


def discard(run_id: str) -> None:
    """Forget *run_id*'s tally without writing it (tests, and a job that has
    nowhere to write)."""
    with _lock:
        for key in [k for k in _tallies if k[0] == run_id]:
            del _tallies[key]


def read_rows(run_dir: Path) -> list[UsageRow]:
    """The ledger's rows, oldest first, one per (run id, provider, model).

    Tolerates a missing file, blank lines and rows it cannot read (skipped: a
    torn line from a crash must not hide the rest of the study's use). A row
    repeated by a restore's append is dropped, the first one kept.

    The repeat is recognised by (run id, provider, model, ts): a restore copies
    bytes, so its repeat is identical to the millisecond, while two jobs that
    share a run id (AutoCode and elaboration mint theirs to the second) flush
    at different moments and are both kept.
    """
    path = run_dir / USAGE_FILENAME
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError):
        logger.warning("usage ledger unreadable at %s", path, exc_info=True)
        return []
    rows: list[UsageRow] = []
    seen: set[tuple[str, str, str, str]] = set()
    for line in raw_lines:
        if not line.strip():
            continue
        try:
            row = UsageRow.model_validate(json.loads(line))
        except (json.JSONDecodeError, ValidationError):
            continue
        key = (row.run_id, row.provider, row.model, row.ts)
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


def study_totals(rows: list[UsageRow]) -> list[UsageTotal]:
    """Sum *rows* per (provider, model), in the order each first appears."""
    totals: dict[tuple[str, str], UsageTotal] = {}
    jobs: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        key = (row.provider, row.model)
        total = totals.get(key)
        if total is None:
            total = totals[key] = UsageTotal(
                provider=row.provider, model=row.model, jobs=0, calls=0,
                input_tokens=0, output_tokens=0, cache_read_input_tokens=0,
                cache_creation_input_tokens=0, calls_without_usage=0,
            )
            jobs[key] = set()
        jobs[key].add(row.run_id)
        total.jobs = len(jobs[key])
        total.calls += row.calls
        total.input_tokens += row.input_tokens
        total.output_tokens += row.output_tokens
        total.cache_read_input_tokens += row.cache_read_input_tokens
        total.cache_creation_input_tokens += row.cache_creation_input_tokens
        total.calls_without_usage += row.calls_without_usage
    return list(totals.values())


def carry_bytes(output_dir: Path) -> bytes | None:
    """The ledger's bytes, read before a Re-analyse sets the output aside.

    ``None`` when there is nothing to carry or it cannot be read; a carry is an
    improvement, never a reason to stop a run (the same rule as the study id's).
    """
    path = output_dir / ".bristlenose" / USAGE_FILENAME
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        logger.warning("usage ledger could not be read to carry: %s", path, exc_info=True)
        return None


def write_carried(output_dir: Path, data: bytes | None) -> None:
    """Start the new output's ledger with the carried bytes. Raises ``OSError``
    for the caller to log beside the other carries."""
    if not data:
        return
    run_dir = output_dir / ".bristlenose"
    run_dir.mkdir(parents=True, exist_ok=True)
    fd = open_private(run_dir / USAGE_FILENAME, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    try:
        os.write(fd, data if data.endswith(b"\n") else data + b"\n")
    finally:
        os.close(fd)
