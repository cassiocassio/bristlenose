"""Tests for the run_progress event (Phase 0b determinate progress).

Invariants worth pinning (per the Bach review): the new event round-trips;
non-finite ETAs never produce invalid JSON; lifecycle-state readers skip a
trailing progress line (so a live/crashed run is still detected); and a
progress-write I/O failure never fails the run. We deliberately do NOT assert
emit cadence or exact field sets — those are implementation detail.
"""

from __future__ import annotations

import json
import math

from bristlenose.events import (
    KindEnum,
    Process,
    RunCompletedEvent,
    RunProgressEvent,
    RunStartedEvent,
    _now_iso,
    append_event,
    events_path,
    read_events,
    tail_run_state,
)
from bristlenose.run_lifecycle import RunHandle, _reconcile_stranded_run


def _started(run_id: str = "RUN0001") -> RunStartedEvent:
    return RunStartedEvent(
        ts=_now_iso(), run_id=run_id, kind=KindEnum.RUN, started_at=_now_iso(),
        process=Process(
            pid=1234, start_time=_now_iso(), hostname="h", user="u",
            bristlenose_version="0.0.0", python_version="3.12.0",
            os="darwin-arm64",
        ),
    )


def _progress(**kw: object) -> RunProgressEvent:
    base: dict[str, object] = dict(
        ts=_now_iso(), run_id="RUN0001", kind=KindEnum.RUN, started_at=_now_iso(),
    )
    base.update(kw)
    return RunProgressEvent(**base)  # type: ignore[arg-type]


def _completed(run_id: str = "RUN0001") -> RunCompletedEvent:
    return RunCompletedEvent(
        ts=_now_iso(), run_id=run_id, kind=KindEnum.RUN, started_at=_now_iso(),
        ended_at=_now_iso(),
    )


def test_run_progress_round_trip(tmp_path):
    f = events_path(tmp_path)
    append_event(f, _started())
    append_event(f, _progress(
        stage="transcribe", sessions_complete=1, sessions_total=3,
        stage_fraction=0.33, eta_remaining_seconds=120.0,
        predicted_total_seconds=200.0,
    ))
    events = read_events(f)
    progress = [e for e in events if isinstance(e, RunProgressEvent)]
    assert len(progress) == 1
    p = progress[0]
    assert p.stage == "transcribe"
    assert p.sessions_complete == 1
    assert p.sessions_total == 3
    assert p.stage_fraction == 0.33
    assert p.eta_remaining_seconds == 120.0


def test_non_finite_eta_coerced_to_none_and_valid_json(tmp_path):
    # A degenerate Welford profile can yield inf/nan; that must never reach
    # the wire as bare Infinity/NaN (invalid JSON Swift silently rejects).
    ev = _progress(
        eta_remaining_seconds=float("inf"),
        stage_fraction=float("nan"),
        predicted_total_seconds=float("-inf"),
    )
    assert ev.eta_remaining_seconds is None
    assert ev.stage_fraction is None
    assert ev.predicted_total_seconds is None

    f = events_path(tmp_path)
    append_event(f, ev)
    line = f.read_text().strip().splitlines()[-1]
    # Strict parse raises on Infinity/NaN — proves the line is valid JSON.
    parsed = json.loads(
        line, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)),
    )
    assert parsed["eta_remaining_seconds"] is None
    assert not any(
        isinstance(v, float) and not math.isfinite(v) for v in parsed.values()
    )


def test_tail_state_skips_trailing_progress_for_in_flight(tmp_path):
    # run_started followed by progress lines: the run is still in flight,
    # and the progress tail must not mask that (Finding 1).
    f = events_path(tmp_path)
    append_event(f, _started())
    append_event(f, _progress(stage="transcribe", sessions_complete=2, sessions_total=3))
    state = tail_run_state(f)
    assert state.in_flight is True
    assert isinstance(state.last_event, RunStartedEvent)


def test_tail_state_finds_terminus_under_trailing_progress(tmp_path):
    # A late progress line after the terminus must not shadow the terminus —
    # else a completed run reads as "still running" forever.
    f = events_path(tmp_path)
    append_event(f, _started())
    append_event(f, _completed())
    append_event(f, _progress(stage="render", stage_fraction=0.99))
    state = tail_run_state(f)
    assert state.in_flight is False
    assert isinstance(state.last_event, RunCompletedEvent)


def test_reconcile_fires_under_trailing_progress(tmp_path):
    # Crash mid-run: run_started + progress lines, no terminus, PID dead.
    # Reconciliation must still synthesise a terminus despite the trailing
    # progress (without the skip, the stranded run is never recovered).
    f = events_path(tmp_path)
    append_event(f, _started())
    append_event(f, _progress(stage="transcribe", sessions_complete=1, sessions_total=3))
    _reconcile_stranded_run(f)
    state = tail_run_state(f)
    assert state.in_flight is False
    assert state.last_event is not None
    assert state.last_event.event.value == "run_failed"


def test_progress_sink_swallows_oserror(tmp_path, monkeypatch):
    # A progress-write I/O failure must never fail the run. The swallow is
    # narrow (OSError only) and logged once — here we assert it doesn't raise.
    import bristlenose.run_lifecycle as rl

    def _boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(rl, "append_event", _boom)
    handle = RunHandle(
        "RUN0001", events_file=events_path(tmp_path), kind=KindEnum.RUN,
        started_at=_now_iso(),
    )
    # Must not raise.
    handle.progress(stage="transcribe", sessions_complete=1, sessions_total=3)


def test_progress_sink_noop_without_events_file():
    # No envelope → no-op (test/render-only paths that never set a sink).
    handle = RunHandle("RUN0001")
    handle.progress(stage="transcribe")  # must not raise
