#!/usr/bin/env python3
"""Regenerate tests/fixtures/run-condition-contract.json.

The fixture holds REAL event lines, built from the event models, so every
reader (pytest now, the Swift @Test in phase D of
docs/design-project-condition.md) parses the same bytes. Each case is named for
the defect it would have caught. Expected values are written by hand below —
never computed from the reducer, or the fixture would only pin the reducer to
itself.

Run:  .venv/bin/python scripts/make-run-condition-fixture.py
"""

from __future__ import annotations

import json
from pathlib import Path

from bristlenose.events import (
    Cause,
    CauseCategoryEnum,
    KindEnum,
    PipelineSummary,
    Process,
    RunCancelledEvent,
    RunCompletedEvent,
    RunFailedEvent,
    RunProgressEvent,
    RunStartedEvent,
    StageFailure,
    StageOutcome,
)

OUT = Path(__file__).resolve().parent.parent / "tests/fixtures/run-condition-contract.json"

_T = iter(f"2026-09-{d:02d}T{h:02d}:00:00Z" for d in range(1, 29) for h in range(24))


def _ts() -> str:
    return next(_T)


_PROC = Process(pid=4242, start_time="1790000000.000001", hostname="host",
                user="researcher", bristlenose_version="0.31.4", python_version="3.12.13",
                os="darwin-arm64")


def started(run: str, kind: KindEnum = KindEnum.RUN) -> str:
    t = _ts()
    return RunStartedEvent(ts=t, run_id=run, kind=kind, started_at=t,
                           process=_PROC).model_dump_json()


def progress(run: str, kind: KindEnum = KindEnum.RUN) -> str:
    t = _ts()
    return RunProgressEvent(ts=t, run_id=run, kind=kind, started_at=t,
                            stage="topics").model_dump_json()


def completed(run: str, kind: KindEnum = KindEnum.RUN, failed_sessions: int = 0) -> str:
    t = _ts()
    summary = None
    if failed_sessions:
        summary = PipelineSummary(quotes=StageOutcome(
            attempted=4, succeeded=4 - failed_sessions,
            failed=[StageFailure(session_id=f"s{i}", cause=Cause(
                category=CauseCategoryEnum.API_SERVER, message="upstream 529"))
                for i in range(failed_sessions)]))
    return RunCompletedEvent(ts=t, run_id=run, kind=kind, started_at=t, ended_at=t,
                             summary=summary).model_dump_json()


def failed(run: str, category: CauseCategoryEnum, kind: KindEnum = KindEnum.RUN,
           stage: str | None = None) -> str:
    t = _ts()
    return RunFailedEvent(ts=t, run_id=run, kind=kind, started_at=t, ended_at=t,
                          cause=Cause(category=category, stage=stage,
                                      message="English forensic text")).model_dump_json()


def cancelled(run: str, kind: KindEnum = KindEnum.RUN) -> str:
    t = _ts()
    return RunCancelledEvent(ts=t, run_id=run, kind=kind, started_at=t, ended_at=t,
                             cause=Cause(category=CauseCategoryEnum.USER_SIGNAL)
                             ).model_dump_json()


def drifted_completed(run: str) -> str:
    """A run_completed line whose field no longer fits the model."""
    obj = json.loads(completed(run))
    obj["ended_at"] = None  # the shape of the duration_ms:null incident
    return json.dumps(obj)


def latest(run, kind="run", state="completed", degraded=False, category=None,
           stage=None) -> dict:
    d = {"run_id": run, "kind": kind, "state": state, "degraded": degraded}
    d["cause"] = None if category is None else {"category": category, "stage": stage}
    return d


def report(run, kind="run", degraded=False) -> dict:
    return {"run_id": run, "kind": kind, "degraded": degraded}


E = CauseCategoryEnum

CASES = [
    dict(name="empty-log", catches="serve started mid-run told the user to start a run",
         lines=[], alive=[],
         expect=dict(decodable=True, latest=None, report=None, stranded=0)),
    dict(name="first-run-in-progress", catches="no in-progress state anywhere in serve",
         lines=[started("A"), progress("A")], alive=["A"],
         expect=dict(decodable=True, latest=latest("A", state="in_progress"),
                     report=None, stranded=0)),
    dict(name="first-run-stranded", catches="stranded run invisible on web until next run",
         lines=[started("A"), progress("A")], alive=[],
         expect=dict(decodable=True, latest=latest("A", state="stranded"),
                     report=None, stranded=1)),
    dict(name="rerun-fails-after-report", catches="F4 — watcher blind to failure; report kept",
         lines=[started("A"), completed("A"), started("B"),
                failed("B", E.OUT_OF_CREDIT, stage="topic_segmentation")], alive=[],
         expect=dict(decodable=True,
                     latest=latest("B", state="failed", category="out_of_credit",
                                   stage="topic_segmentation"),
                     report=report("A"), stranded=0)),
    dict(name="rerun-cancelled-after-report", catches="F1/F2 — cancel read as never-run",
         lines=[started("A"), completed("A"), started("B"), cancelled("B")], alive=[],
         expect=dict(decodable=True,
                     latest=latest("B", state="cancelled", category="user_signal"),
                     report=report("A"), stranded=0)),
    dict(name="cancelled-after-failed", catches="title from one run, cause from another",
         lines=[started("A"), failed("A", E.OUT_OF_CREDIT), started("B"), cancelled("B")],
         alive=[],
         expect=dict(decodable=True,
                     latest=latest("B", state="cancelled", category="user_signal"),
                     report=None, stranded=0)),
    dict(name="transcribe-only-is-not-a-report", catches="N20/N49 — serve ignores kind",
         lines=[started("A"), completed("A"),
                started("B", KindEnum.TRANSCRIBE_ONLY),
                completed("B", KindEnum.TRANSCRIBE_ONLY)], alive=[],
         expect=dict(decodable=True, latest=latest("B", kind="transcribe-only"),
                     report=report("A"), stranded=0)),
    dict(name="transcribe-only-alone", catches="N20 — empty SPA after transcribe",
         lines=[started("A", KindEnum.TRANSCRIBE_ONLY),
                completed("A", KindEnum.TRANSCRIBE_ONLY)], alive=[],
         expect=dict(decodable=True, latest=latest("A", kind="transcribe-only"),
                     report=None, stranded=0)),
    dict(name="analyze-replaces-report", catches="analyze is a report kind",
         lines=[started("A"), completed("A"), started("B", KindEnum.ANALYZE),
                completed("B", KindEnum.ANALYZE)], alive=[],
         expect=dict(decodable=True, latest=latest("B", kind="analyze"),
                     report=report("B", kind="analyze"), stranded=0)),
    dict(name="old-stranded-new-completed",
         catches="liveness must be matched to run_id; old run is history, not in flight",
         lines=[started("X"), started("B"), completed("B")], alive=["X"],
         expect=dict(decodable=True, latest=latest("B"), report=report("B"), stranded=1)),
    dict(name="trailing-progress-after-terminus", catches="Finding 1 — progress masked terminus",
         lines=[started("A"), completed("A"), progress("A")], alive=[],
         expect=dict(decodable=True, latest=latest("A"), report=report("A"), stranded=0)),
    dict(name="drifted-known-event-fails-closed",
         catches="a well-formed line that doesn't fit the model must not be walked past",
         lines=[started("A"), completed("A"), started("B"), drifted_completed("B")],
         alive=[],
         expect=dict(decodable=False, latest=None, report=None, stranded=0)),
    dict(name="unknown-future-event-skipped", catches="forward-compat: additive event types",
         lines=[started("A"), json.dumps({"event": "stage_started", "run_id": "A"}),
                completed("A")], alive=[],
         expect=dict(decodable=True, latest=latest("A"), report=report("A"), stranded=0)),
    dict(name="torn-final-line-skipped", catches="crash residue is not drift",
         lines=[started("A"), completed("A"), '{"event": "run_started", "run_id": "B", "ki'],
         alive=[],
         expect=dict(decodable=True, latest=latest("A"), report=report("A"), stranded=0)),
    dict(name="degraded-completion", catches="completedPartial must survive the reducer",
         lines=[started("A"), completed("A", failed_sessions=2)], alive=[],
         expect=dict(decodable=True, latest=latest("A", degraded=True),
                     report=report("A", degraded=True), stranded=0)),
    dict(name="legacy-project-without-log",
         catches="a project analysed before the events log existed read as never-run",
         lines=[], alive=[],
         legacy_report={"run_id": "legacy", "kind": "run", "ended_at": None,
                        "degraded": False, "source": "manifest"},
         expect=dict(decodable=True, latest=None,
                     report={"run_id": "legacy", "kind": "run", "degraded": False},
                     stranded=0)),
    dict(name="legacy-evidence-never-overrides-the-log",
         catches="manifest fallback applies only when the log records no runs",
         lines=[started("A"), failed("A", E.AUTH)], alive=[],
         legacy_report={"run_id": "legacy", "kind": "run", "ended_at": None,
                        "degraded": False, "source": "manifest"},
         expect=dict(decodable=True, latest=latest("A", state="failed", category="auth"),
                     report=None, stranded=0)),
    dict(name="terminus-without-started",
         catches="a terminus carries its own kind and started_at",
         lines=[completed("A")], alive=[],
         expect=dict(decodable=True, latest=latest("A"), report=report("A"), stranded=0)),
    dict(name="duplicate-started-then-completed",
         catches="a repeated run_started must not un-complete a run",
         lines=[started("A"), completed("A"), started("A")], alive=[],
         expect=dict(decodable=True, latest=latest("A"), report=report("A"), stranded=0)),
    dict(name="restore-shaped-log",
         catches="output_backup.restore appends the failed run's history to the old log",
         lines=[started("A"), completed("A"), started("B"),
                failed("B", E.OUT_OF_CREDIT)], alive=[],
         expect=dict(decodable=True, latest=latest("B", state="failed",
                                                   category="out_of_credit"),
                     report=report("A"), stranded=0)),
    dict(name="malformed-progress-is-noise",
         catches="a torn run_progress line must not veto the answer",
         lines=[started("A"), json.dumps({"event": "run_progress", "run_id": "A"}),
                completed("A")], alive=[],
         expect=dict(decodable=True, latest=latest("A"), report=report("A"), stranded=0)),
    dict(name="report-beyond-64kb-tail",
         catches="Swift reads only a 64 KB tail; a long in-flight run hides the report",
         lines=[started("A"), completed("A"), started("B")] + [progress("B")] * 400,
         alive=["B"],
         expect=dict(decodable=True, latest=latest("B", state="in_progress"),
                     report=report("A"), stranded=0)),
]


def main() -> None:
    for c in CASES:
        # Expected run refs carry only the fields the contract pins.
        c["expect"]["history_stranded"] = c["expect"].pop("stranded")
    OUT.write_text(json.dumps({
        "version": 1,
        "doc": "docs/design-project-condition.md §3.4 — generated by "
               "scripts/make-run-condition-fixture.py; expectations are hand-written.",
        "cases": CASES,
    }, indent=1, ensure_ascii=True) + "\n")
    print(f"wrote {len(CASES)} cases to {OUT}")


if __name__ == "__main__":
    main()
