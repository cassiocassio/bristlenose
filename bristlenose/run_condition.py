"""The project's condition — one answer to "what state is this project in?".

A pure reducer over the pipeline events log. Every reader that needs to say
whether a project has a report, is being analysed, or failed last time asks
this module instead of interpreting the log itself. Three readers used to do
that separately (the Mac's ``EventLogReader``, the serve's watcher +
``status_page``, and the SPA through ``/last-run``) and every one of them got a
different subset of cases wrong. Design: ``docs/design-project-condition.md``.

The reducer answers two questions and only two:

* ``latest`` — what happened most recently (in progress, completed, failed,
  cancelled, or stranded: started, no terminus, owner dead);
* ``report`` — which completed ``run``/``analyze`` produced the report on disk.

It is pure: the caller supplies the lines and a liveness function. The
shared fixture ``tests/fixtures/run-condition-contract.json`` pins its
behaviour and is meant to be read by the Swift twin too.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from bristlenose.events import (
    EventTypeEnum,
    KindEnum,
    PipelineSummary,
    RunCancelledEvent,
    RunCompletedEvent,
    RunFailedEvent,
    RunProgressEvent,
    RunStartedEvent,
    _iter_event_lines,
    _parse_event_line,
    events_path,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# Kinds whose completion leaves a report on disk. ``transcribe-only`` stops
# before analysis, so its completion is a fact about transcripts, not a report.
REPORT_KINDS = frozenset({KindEnum.RUN, KindEnum.ANALYZE})

Liveness = Callable[[str], "bool | None"]


class RunStateEnum(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STRANDED = "stranded"


class ConditionCause(BaseModel):
    """What went wrong, as data. No ``message``: wording belongs to the cause
    table, and the English forensic text stays in the log for "Show details"."""

    category: str
    reason: str | None = None
    stage: str | None = None


class RunRef(BaseModel):
    run_id: str
    kind: KindEnum
    state: RunStateEnum
    started_at: str | None = None
    ended_at: str | None = None
    degraded: bool = False
    cause: ConditionCause | None = None


class ReportRef(BaseModel):
    run_id: str
    kind: KindEnum
    ended_at: str | None = None
    degraded: bool = False
    # "log" — a run_completed in the events log. "manifest" — a project
    # analysed before the log existed: the manifest records a finished render
    # and the log records nothing (see ``legacy_report``).
    source: str = "log"


class History(BaseModel):
    runs: int = 0
    stranded: int = 0


class Condition(BaseModel):
    schema_version: int = Field(default=SCHEMA_VERSION, alias="schema")
    decodable: bool = True
    latest: RunRef | None = None
    report: ReportRef | None = None
    history: History = Field(default_factory=History)

    model_config = {"populate_by_name": True}

    def to_wire(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True)


def summary_is_degraded(summary: PipelineSummary | None) -> bool:
    """A completion is degraded when any session failed in any stage.

    Mirrors Swift ``PipelineSummary.totalFailureCount > 0``.
    """
    if summary is None:
        return False
    for bucket in (summary.ingest, summary.transcripts, summary.topics,
                   summary.quotes, summary.themes):
        if bucket is not None and bucket.failed:
            return True
    return False


_LIFECYCLE_EVENTS = frozenset(
    e.value for e in EventTypeEnum if e != EventTypeEnum.RUN_PROGRESS
)


def _is_drift(line: str) -> bool:
    """True when an unparseable line is contract drift rather than noise.

    Three kinds of line fail to parse, and they want different handling:

    * not JSON at all — a torn write from a crash or power loss. Skip it.
    * JSON naming an event type this reader doesn't know — a newer writer's
      additive event (the Swift reader swallows these too). Skip it.
    * JSON naming a KNOWN event that doesn't fit the model — the contract has
      drifted. Answering from an older line would describe the wrong run, which
      is how a successful run once read as "stopped unexpectedly". Fail closed.
    """
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return False
    # A malformed run_progress line is telemetry noise, not drift: progress
    # never changes the answer, so it must not be able to veto one either.
    return isinstance(obj, dict) and obj.get("event") in _LIFECYCLE_EVENTS


class _Run:
    __slots__ = ("run_id", "kind", "started_at", "terminus", "last_seq")

    def __init__(self, run_id: str, kind: KindEnum) -> None:
        self.run_id = run_id
        self.kind = kind
        self.started_at: str | None = None
        self.terminus: RunCompletedEvent | RunFailedEvent | RunCancelledEvent | None = None
        self.last_seq = -1


def reduce_lines(
    lines: Iterable[str],
    liveness: Liveness | None = None,
    legacy_report: ReportRef | Callable[[], ReportRef | None] | None = None,
) -> Condition:
    """Reduce raw JSONL lines to a :class:`Condition`.

    ``legacy_report`` is evidence from outside the log, used only when the log
    records no runs at all (a callable is only called then, so a damaged
    manifest can never cost an answer the log could give): a project analysed
    before the events log existed
    has a finished report and an empty history, and without this it read as
    "no run yet" on the web (2 of 30 real output folders on the maintainer's
    Mac, measured 28 Sep 2026). It never overrides anything the log says.

    ``liveness(run_id)`` answers whether the process owning that run is alive;
    ``None`` or an unknown answer means "not known to be alive". Only the
    latest run is ever asked — an older run with no terminus is stranded
    history whatever its PID says, because a newer run has started since.
    """
    runs: dict[str, _Run] = {}
    decodable = True
    last_lifecycle: _Run | None = None
    # A snapshot, not a reference: a later event for the same run_id must not
    # be able to rewrite which report is on disk.
    report: ReportRef | None = None

    for seq, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        ev = _parse_event_line(line)
        if ev is None:
            # Valid JSON that doesn't fit the model is contract drift: refuse to
            # answer from an older event rather than answer about the wrong one.
            if _is_drift(line):
                decodable = False
            continue
        if isinstance(ev, RunProgressEvent):
            continue
        run = runs.get(ev.run_id)
        if run is None:
            run = _Run(ev.run_id, ev.kind)
            runs[ev.run_id] = run
        run.last_seq = seq
        if isinstance(ev, RunStartedEvent):
            run.started_at = ev.started_at
            run.kind = ev.kind
        else:
            run.terminus = ev
            if run.started_at is None:
                run.started_at = ev.started_at
            if isinstance(ev, RunCompletedEvent) and ev.kind in REPORT_KINDS:
                report = ReportRef(
                    run_id=ev.run_id, kind=ev.kind, ended_at=ev.ended_at,
                    degraded=summary_is_degraded(ev.summary),
                )
        last_lifecycle = run

    if not decodable:
        # Fail closed: a reader that cannot trust the log must not guess.
        return Condition(decodable=False, history=History(runs=len(runs)))

    if not runs:
        legacy = legacy_report() if callable(legacy_report) else legacy_report
        if legacy is not None:
            return Condition(report=legacy)

    stranded = sum(
        1 for r in runs.values()
        if r.terminus is None and r is not last_lifecycle
    )
    latest_ref: RunRef | None = None
    if last_lifecycle is not None:
        latest_ref = _run_ref(last_lifecycle, liveness)
        if latest_ref.state == RunStateEnum.STRANDED:
            stranded += 1

    return Condition(
        decodable=True,
        latest=latest_ref,
        report=report,
        history=History(runs=len(runs), stranded=stranded),
    )


def _run_ref(run: _Run, liveness: Liveness | None) -> RunRef:
    t = run.terminus
    if t is None:
        alive = liveness(run.run_id) if liveness is not None else None
        return RunRef(
            run_id=run.run_id,
            kind=run.kind,
            state=RunStateEnum.IN_PROGRESS if alive else RunStateEnum.STRANDED,
            started_at=run.started_at,
        )
    if isinstance(t, RunCompletedEvent):
        state = RunStateEnum.COMPLETED
    elif isinstance(t, RunCancelledEvent):
        state = RunStateEnum.CANCELLED
    else:
        state = RunStateEnum.FAILED
    cause = None
    if t.cause is not None:
        cause = ConditionCause(
            category=t.cause.category.value,
            reason=t.cause.reason.value if t.cause.reason is not None else None,
            stage=t.cause.stage,
        )
    return RunRef(
        run_id=run.run_id,
        kind=run.kind,
        state=state,
        started_at=run.started_at,
        ended_at=t.ended_at,
        degraded=summary_is_degraded(t.summary),
        cause=cause,
    )


def pid_file_liveness(output_dir: Path) -> Liveness:
    """Liveness backed by the Python run's PID file, matched to ``run_id``.

    True only when ``run.pid`` names this run AND its ``(pid, start_time)``
    belongs to a live process — the start-time match defeats PID reuse.
    """
    from bristlenose.run_lifecycle import _is_alive_owned, _read_pid_file

    def _alive(run_id: str) -> bool | None:
        pid = _read_pid_file(output_dir)
        if pid is None or pid.get("run_id") != run_id:
            return False
        return _is_alive_owned(pid)

    return _alive


def manifest_legacy_report(output_dir: Path) -> ReportRef | None:
    """A report the manifest vouches for — the pre-events-log fallback."""
    from bristlenose.manifest import StageStatus, load_manifest

    try:
        manifest = load_manifest(output_dir)
    except Exception:  # noqa: BLE001 — fallback evidence must never cost an answer
        logger.warning("manifest unreadable at %s — no legacy report", output_dir,
                       exc_info=True)
        return None
    if manifest is None:
        return None
    render = manifest.stages.get("render")
    if render is None or render.status != StageStatus.COMPLETE:
        return None
    return ReportRef(run_id="legacy", kind=KindEnum.RUN,
                     ended_at=render.completed_at, source="manifest")


def read_condition(output_dir: Path, liveness: Liveness | None = None) -> Condition:
    """The condition for the project whose output lives at ``output_dir``.

    A missing directory or log is a valid answer — no runs yet — unless the
    manifest records a finished render from before the log existed.
    """
    try:
        lines = _iter_event_lines(events_path(output_dir))
    except OSError:
        # The log vanished between exists() and read — ``--clean`` moving the
        # output folder aside. Not an answer; the caller retries next poll.
        logger.info("events log unreadable at %s — condition unknown", output_dir)
        return Condition(decodable=False)
    return reduce_lines(
        lines,
        liveness if liveness is not None else pid_file_liveness(output_dir),
        legacy_report=lambda: manifest_legacy_report(output_dir),
    )
