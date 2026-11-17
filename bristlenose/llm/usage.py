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

**Survives a Re-analyse.** ``run --clean`` sets the output folder aside; the
ledger is copied into the new one at once (``cli.py``), so the study's total is
right while the run is going, and whichever tree is thrown away at the end is
merged into the one kept (:func:`merge_ledger`, from ``output_backup``'s export
carry), by row id. The merge is what makes the total right, whatever the
carry did.

**What is not counted.** A process killed outright (SIGKILL, a power cut)
never reaches its flush, so its tokens are lost; a counted run is never
inflated, only an uncounted one is possible. A call whose provider reported no
usage is counted in ``calls`` and ``calls_without_usage``, with no tokens.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
from collections import OrderedDict
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
    #: Unique per row written. A restore's append repeats rows byte for byte,
    #: id included, so a repeat is recognised by this and nothing else: a
    #: timestamp cannot tell two rows written in one millisecond apart.
    row_id: str
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


class InFlight(BaseModel):
    """A job's use so far, before its row is written: what a live surface reads."""

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


class _Job(BaseModel):
    run_dir: str  # realpath, so two spellings of one folder compare equal
    kind: str


# (run_id, provider, model) -> tally. A lock, not a contextvar: a pipeline
# stage's calls run in asyncio tasks and a serve's jobs in threads, and they
# all add to the same run's tally.
_tallies: dict[tuple[str, str, str], _Tally] = {}
# Jobs that have begun and not yet flushed: where they write, and what they are.
_jobs: dict[str, _Job] = {}
# Jobs already flushed, newest last, so a call that lands after its job ended
# (a cancelled task finishing, a late thread) is written as a row of its own
# instead of sitting in a tally nothing will flush.
_flushed: OrderedDict[str, _Job] = OrderedDict()
_FLUSHED_KEPT = 256
_lock = threading.Lock()


_odd_count_warned = False


def _count_or_none(value: object) -> int | None:
    """A token count as an int, or None when it is not one.

    An SDK object a test fakes with MagicMock, or a provider returning a
    string, would otherwise turn the tally into something that adds wrong or
    cannot be written. Not a count is treated as not reported (the call is
    still counted, in ``calls_without_usage`` when nothing else was reported),
    and said once per process at WARNING.
    """
    global _odd_count_warned
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    if not _odd_count_warned:
        _odd_count_warned = True
        logger.warning("usage: a token count that is not a count (%r) was treated as "
                       "not reported", type(value).__name__)
    return None


def _real(run_dir: Path) -> str:
    return os.path.realpath(run_dir)


def begin(run_id: str, run_dir: Path, kind: str) -> None:
    """Register a job as it starts, so its use so far can be read (:func:`peek`).

    Optional for correctness — :func:`flush` writes a tally whether or not it
    began — but a job that never begins is invisible until it ends.
    """
    with _lock:
        _jobs[run_id] = _Job(run_dir=_real(run_dir), kind=kind)
        # A new job reusing a finished one's id (AutoCode and elaboration mint
        # theirs to the second) is not a late call of the old one.
        _flushed.pop(run_id, None)


def note_call(
    *,
    run_id: str,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    cache_read_input_tokens: int | None = None,
    cache_creation_input_tokens: int | None = None,
    cached_input_tokens_included: int | None = None,
) -> None:
    """Add one LLM call to its run's tally. Never raises into the caller.

    Normalises the providers to one meaning (the contract's
    ``field_meanings``): ``input_tokens`` is input billed at the full rate.
    Anthropic reports it that way, with cache reads and writes beside it.
    OpenAI, Azure and Gemini count cached input INSIDE their prompt count;
    the client passes that share as *cached_input_tokens_included*, and it
    moves here from ``input_tokens`` to ``cache_read_input_tokens``.
    """
    try:
        input_tokens = _count_or_none(input_tokens)
        output_tokens = _count_or_none(output_tokens)
        cache_read_input_tokens = _count_or_none(cache_read_input_tokens)
        cache_creation_input_tokens = _count_or_none(cache_creation_input_tokens)
        cached_input_tokens_included = _count_or_none(cached_input_tokens_included)
        reported = input_tokens is not None or output_tokens is not None
        cached = cached_input_tokens_included or 0
        if input_tokens is not None and cached:
            cached = min(cached, input_tokens)
            input_tokens -= cached
            cache_read_input_tokens = (cache_read_input_tokens or 0) + cached
        with _lock:
            tally = _tallies.setdefault((run_id, provider, model), _Tally())
            tally.calls += 1
            if not reported:
                tally.calls_without_usage += 1
            tally.input_tokens += input_tokens or 0
            tally.output_tokens += output_tokens or 0
            tally.cache_read_input_tokens += cache_read_input_tokens or 0
            tally.cache_creation_input_tokens += cache_creation_input_tokens or 0
            late = _flushed.get(run_id)
        if late is not None:
            flush(Path(late.run_dir), run_id, late.kind)
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
        # Under the same lock as the pop: a call landing after this moment
        # finds the job flushed and writes itself (see note_call).
        _jobs.pop(run_id, None)
        _flushed[run_id] = _Job(run_dir=_real(run_dir), kind=kind)
        _flushed.move_to_end(run_id)
        while len(_flushed) > _FLUSHED_KEPT:
            _flushed.popitem(last=False)
    if not taken:
        return 0
    try:
        ts = _now_iso()
        lines = [
            UsageRow(
                row_id=secrets.token_hex(8),
                ts=ts, run_id=run_id, kind=kind, provider=provider, model=model,
                **tally.model_dump(),
            ).model_dump_json() + "\n"
            for (_, provider, model), tally in taken
        ]
        run_dir.mkdir(parents=True, exist_ok=True)
        fd = open_private(run_dir / USAGE_FILENAME, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
        try:
            # One write: a job's rows land together or not at all, and a row
            # (~300 B) is far under PIPE_BUF, so writers do not interleave.
            os.write(fd, "".join(lines).encode("utf-8"))
        finally:
            os.close(fd)
    except Exception:
        # Never raises: it runs in `finally` blocks, where an escape would
        # replace the job's own failure. What was lost is said, in numbers.
        lost = {
            f"{prov}/{model}": (t.calls, t.input_tokens, t.output_tokens)
            for (_, prov, model), t in taken
        }
        logger.warning(
            "usage ledger not written run_id=%s kind=%s — uncounted (calls, in, out): %s",
            run_id, kind, lost, exc_info=True,
        )
        return 0
    return len(lines)


def discard(run_id: str) -> None:
    """Forget *run_id*'s tally without writing it (tests, and a job that has
    nowhere to write)."""
    with _lock:
        for key in [k for k in _tallies if k[0] == run_id]:
            del _tallies[key]
        _jobs.pop(run_id, None)


def peek(run_dir: Path) -> list[InFlight]:
    """The use so far of this process's jobs writing to *run_dir* that have
    begun and not ended. Another process's jobs are not visible here: a
    pipeline run in its own process reports through its progress lines."""
    want = _real(run_dir)
    with _lock:
        return [
            InFlight(run_id=rid, kind=job.kind, provider=prov, model=model,
                     **tally.model_dump())
            for (rid, prov, model), tally in _tallies.items()
            if (job := _jobs.get(rid)) is not None and job.run_dir == want
        ]


def run_totals(run_id: str) -> _Tally | None:
    """*run_id*'s use so far, summed over models; None before its first call."""
    with _lock:
        parts = [t for (rid, _, _), t in _tallies.items() if rid == run_id]
        if not parts:
            return None
        total = _Tally()
        for t in parts:
            for name in _Tally.model_fields:
                setattr(total, name, getattr(total, name) + getattr(t, name))
        return total


def read_rows(run_dir: Path) -> list[UsageRow]:
    """The ledger's rows, oldest first, each once (see :func:`read_rows_counted`)."""
    return read_rows_counted(run_dir)[0]


_unreadable_warned: set[str] = set()


def _row_key(raw: dict[str, object], line: str) -> str:
    """A row's identity: its ``row_id``, or for a row written before ids
    existed (the first commit of the ledger), a hash of its own bytes, which a
    restore's byte-for-byte repeat shares."""
    rid = raw.get("row_id")
    if isinstance(rid, str) and rid:
        return rid
    import hashlib

    return "legacy-" + hashlib.sha256(line.strip().encode("utf-8")).hexdigest()[:16]


def read_rows_counted(run_dir: Path) -> tuple[list[UsageRow], int]:
    """The ledger's rows, oldest first, each once, and how many lines could
    not be read.

    Skips blank lines; a line it cannot read is counted, not hidden: a torn
    line from a crash, or a row from a newer Bristlenose this one does not
    know, would otherwise shrink a total with nothing said. Logged at WARNING
    once per ledger per process. A row repeated (a restore appends what a
    carry copied) is dropped by its ``row_id``: a restore copies bytes, id
    included, while every row written gets a fresh one, so two jobs sharing a
    run id, or a late call flushed in the same millisecond as its job, are both
    kept.
    """
    path = run_dir / USAGE_FILENAME
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return [], 0
    except (OSError, UnicodeDecodeError):
        logger.warning("usage ledger unreadable at %s", path, exc_info=True)
        return [], 0
    rows: list[UsageRow] = []
    seen: set[str] = set()
    unreadable = 0
    for line in raw_lines:
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            if not isinstance(raw, dict):
                raise ValueError("not an object")
            key = _row_key(raw, line)
            row = UsageRow.model_validate({**raw, "row_id": key})
        except (ValueError, ValidationError):
            unreadable += 1
            continue
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    if unreadable and str(path) not in _unreadable_warned:
        _unreadable_warned.add(str(path))
        logger.warning("usage ledger %s: %d line(s) could not be read and are left out "
                       "of the totals", path, unreadable)
    return rows, unreadable


def merge_ledger(from_output: Path, into_output: Path) -> int:
    """Add the rows of one output folder's ledger that the other lacks.

    Called wherever a tree is about to be thrown away (``output_backup``'s
    export carry): a failed Re-analyse's tree into the restored report, a
    replaced report's into the new one. By ``row_id``, so it is idempotent: a
    row already carried is not added twice, and running it again adds nothing.
    Returns the rows added; raises ``OSError`` for the caller to log.
    """
    src = from_output / ".bristlenose" / USAGE_FILENAME
    if not src.is_file():
        return 0
    dest_dir = into_output / ".bristlenose"
    have: set[str] = set()
    dest = dest_dir / USAGE_FILENAME
    if dest.is_file():
        for line in dest.read_text(encoding="utf-8").splitlines():
            try:
                raw = json.loads(line)
            except ValueError:
                continue
            if isinstance(raw, dict):
                have.add(_row_key(raw, line))
    new: list[str] = []
    for line in src.read_text(encoding="utf-8").splitlines():
        try:
            raw = json.loads(line)
        except ValueError:
            continue
        if not isinstance(raw, dict):
            continue
        key = _row_key(raw, line)
        if key not in have:
            have.add(key)
            new.append(line.strip() + "\n")
    if not new:
        return 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    fd = open_private(dest, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    try:
        os.write(fd, "".join(new).encode("utf-8"))
    finally:
        os.close(fd)
    return len(new)


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
    """The ledger's bytes, read from a Re-analyse's stash once it is set aside,
    so a serve job that wrote just before the rename is in it.

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
