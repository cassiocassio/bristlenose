"""The project-condition reducer against its shared contract and its invariants.

Three layers, per docs/design-project-condition.md §3.3–3.4:

* the shared fixture (``tests/fixtures/run-condition-contract.json``) — real
  event lines, hand-written expectations, each case named for the defect it
  would have caught; the Swift twin reads the same file in phase D;
* property tests — seeded random event sequences asserting the invariants
  (no Hypothesis dependency: a fixed seed list keeps failures reproducible);
* the PID-file liveness adapter, matched to ``run_id``.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

import pytest

from bristlenose.events import (
    Cause,
    CauseCategoryEnum,
    KindEnum,
    Process,
    RunCancelledEvent,
    RunCompletedEvent,
    RunFailedEvent,
    RunProgressEvent,
    RunStartedEvent,
    events_path,
)
from bristlenose.run_condition import (
    ReportRef,
    RunStateEnum,
    read_condition,
    reduce_lines,
)

FIXTURE = Path(__file__).parent / "fixtures" / "run-condition-contract.json"
CASES = json.loads(FIXTURE.read_text())["cases"]


def _pin_latest(ref) -> dict | None:
    if ref is None:
        return None
    cause = None
    if ref.cause is not None:
        cause = {"category": ref.cause.category, "stage": ref.cause.stage}
    return {"run_id": ref.run_id, "kind": ref.kind.value, "state": ref.state.value,
            "degraded": ref.degraded, "cause": cause}


def _pin_report(ref) -> dict | None:
    if ref is None:
        return None
    return {"run_id": ref.run_id, "kind": ref.kind.value, "degraded": ref.degraded}


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_contract_case(case: dict) -> None:
    alive = set(case["alive"])
    legacy = case.get("legacy_report")
    cond = reduce_lines(
        case["lines"], liveness=lambda rid: rid in alive,
        legacy_report=ReportRef(**legacy) if legacy else None,
    )
    exp = case["expect"]
    assert cond.decodable is exp["decodable"], case["catches"]
    assert _pin_latest(cond.latest) == exp["latest"], case["catches"]
    assert _pin_report(cond.report) == exp["report"], case["catches"]
    assert cond.history.stranded == exp["history_stranded"], case["catches"]


def test_fixture_names_are_unique_and_explained() -> None:
    names = [c["name"] for c in CASES]
    assert len(names) == len(set(names))
    assert all(c["catches"].strip() for c in CASES)


# ---------------------------------------------------------------------------
# Property tests — generated sequences, invariants from §3.3
# ---------------------------------------------------------------------------

_PROC = Process(pid=1, start_time="1.0", hostname="h", user="u",
                bristlenose_version="0", python_version="3.12", os="darwin-arm64")
_KINDS = [KindEnum.RUN, KindEnum.RUN, KindEnum.ANALYZE, KindEnum.TRANSCRIBE_ONLY]


def _gen(rng: random.Random, n_runs: int) -> tuple[list[str], dict[str, str]]:
    """A plausible log: runs in order, each started then (usually) ended,
    with progress lines sprinkled in. Returns lines and run_id→outcome."""
    lines: list[str] = []
    outcomes: dict[str, str] = {}
    t = 0
    for i in range(n_runs):
        rid, kind = f"R{i}", rng.choice(_KINDS)
        t += 1
        ts = f"2026-09-01T00:00:{t:02d}Z"
        lines.append(RunStartedEvent(ts=ts, run_id=rid, kind=kind, started_at=ts,
                                     process=_PROC).model_dump_json())
        for _ in range(rng.randint(0, 3)):
            lines.append(RunProgressEvent(ts=ts, run_id=rid, kind=kind,
                                          started_at=ts).model_dump_json())
        end = rng.choice(["completed", "completed", "failed", "cancelled", None])
        if end is None and i < n_runs - 1:
            outcomes[rid] = "open"
            continue
        if end == "completed":
            lines.append(RunCompletedEvent(ts=ts, run_id=rid, kind=kind, started_at=ts,
                                           ended_at=ts).model_dump_json())
        elif end == "failed":
            lines.append(RunFailedEvent(ts=ts, run_id=rid, kind=kind, started_at=ts,
                                        ended_at=ts, cause=Cause(
                                            category=CauseCategoryEnum.API_SERVER,
                                            message="x")).model_dump_json())
        elif end == "cancelled":
            lines.append(RunCancelledEvent(ts=ts, run_id=rid, kind=kind, started_at=ts,
                                           ended_at=ts, cause=Cause(
                                               category=CauseCategoryEnum.USER_SIGNAL)
                                           ).model_dump_json())
        outcomes[rid] = end or "open"
    return lines, outcomes


SEEDS = list(range(300))


@pytest.mark.parametrize("seed", SEEDS[:: 30])
def test_invariants_hold_on_generated_logs(seed: int) -> None:
    # Each parametrised case sweeps 30 seeds, so 300 logs run in 10 test ids.
    for s in range(seed, seed + 30):
        rng = random.Random(s)
        lines, outcomes = _gen(rng, rng.randint(1, 6))
        alive_last = rng.random() < 0.5
        last_id = f"R{len(outcomes) - 1}"
        def live(rid: str, a: bool = alive_last, last: str = last_id) -> bool:
            return a and rid == last
        cond = reduce_lines(lines, liveness=live)

        # 5. total, and decodable on well-formed input
        assert cond.decodable, s
        # 6. deterministic
        assert cond == reduce_lines(lines, liveness=live), s
        # 1. progress lines never change the answer
        stripped = [ln for ln in lines if '"run_progress"' not in ln]
        assert cond == reduce_lines(stripped, liveness=live), s
        # 4. latest is the run of the last lifecycle event
        last_lifecycle = json.loads(stripped[-1])["run_id"]
        assert cond.latest is not None and cond.latest.run_id == last_lifecycle, s
        # 2. report only ever names a completed run/analyze
        if cond.report is not None:
            rid = cond.report.run_id
            assert outcomes[rid] == "completed", s
            assert cond.report.kind in (KindEnum.RUN, KindEnum.ANALYZE), s


def test_appending_a_non_completion_never_removes_the_report() -> None:
    # 3. only a newer completion replaces the report.
    rng = random.Random(7)
    for _ in range(200):
        lines, _ = _gen(rng, rng.randint(1, 5))
        before = reduce_lines(lines).report
        rid = "Z"
        ts = "2026-09-02T00:00:00Z"
        tail = [RunStartedEvent(ts=ts, run_id=rid, kind=KindEnum.RUN, started_at=ts,
                                process=_PROC).model_dump_json(),
                RunFailedEvent(ts=ts, run_id=rid, kind=KindEnum.RUN, started_at=ts,
                               ended_at=ts, cause=Cause(category=CauseCategoryEnum.AUTH,
                                                        message="x")).model_dump_json()]
        after = reduce_lines(lines + tail).report
        assert after == before


# ---------------------------------------------------------------------------
# PID-file liveness, matched to run_id
# ---------------------------------------------------------------------------


def _write_log(output_dir: Path, lines: list[str]) -> None:
    p = events_path(output_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(ln + "\n" for ln in lines))


def test_read_condition_missing_dir_is_no_runs(tmp_path: Path) -> None:
    cond = read_condition(tmp_path / "bristlenose-output")
    assert cond.decodable and cond.latest is None and cond.report is None


def test_pid_liveness_must_match_run_id(tmp_path: Path) -> None:
    from bristlenose.run_lifecycle import _ps_start_time, _write_pid_file

    out = tmp_path / "bristlenose-output"
    ts = "2026-09-01T00:00:00Z"
    _write_log(out, [RunStartedEvent(ts=ts, run_id="B", kind=KindEnum.RUN, started_at=ts,
                                     process=_PROC).model_dump_json()])
    me = _ps_start_time(os.getpid())
    # Readable on every platform we test on; a None here is a failure, not a skip.
    assert me is not None, "process start time unavailable"

    # A PID file naming a different run — this process is alive, but not B's owner.
    _write_pid_file(out, "A", me)
    assert read_condition(out).latest.state == RunStateEnum.STRANDED

    # The PID file names B and this (live) process — B is in progress.
    _write_pid_file(out, "B", me)
    assert read_condition(out).latest.state == RunStateEnum.IN_PROGRESS
