"""Tests for the run_progress event (Phase 0b determinate progress) and the
estimator-independent stage-entry emit (cached-run-progress-emit).

Invariants worth pinning (per the Bach review): the new event round-trips;
non-finite ETAs never produce invalid JSON; lifecycle-state readers skip a
trailing progress line (so a live/crashed run is still detected); a
progress-write I/O failure never fails the run; and the stage-entry emit puts
the timing verb vocabulary on the wire (never a manifest name that the Swift
RunProgressSubtitle.knownStages silently drops) while carrying the last-known
ETA — and clearing it when the estimate goes cold — so warm-run ring fill can't
regress. We deliberately do NOT assert emit cadence — that is implementation detail.
"""

from __future__ import annotations

import json
import math

from bristlenose.config import BristlenoseSettings
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
from bristlenose.manifest import (
    STAGE_CLUSTER_AND_GROUP,
    STAGE_IDENTIFY_SPEAKERS,
    STAGE_QUOTE_EXTRACTION,
    STAGE_TOPIC_SEGMENTATION,
)
from bristlenose.pipeline import Pipeline
from bristlenose.run_lifecycle import RunHandle, _reconcile_stranded_run
from bristlenose.timing import (
    STAGE_CLUSTER,
    STAGE_QUOTES,
    STAGE_RENDER,
    STAGE_SPEAKERS,
    STAGE_TOPICS,
)


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


def test_emit_stage_entry_emits_verb_vocabulary_not_manifest_names():
    # The estimator-independent stage-entry emit is the ONLY per-stage signal
    # on cache-verified / cold-estimator runs (_emit_remaining never fires
    # there). It must put the timing verb on the wire ("speakers"), not the
    # manifest name ("identify_speakers") — RunProgressSubtitle.knownStages
    # silently drops the latter (no verb, no error). Real sink, not a stub,
    # so a zero-emit regression can't pass vacuously (silent-failure-hunter).
    collected: list[dict[str, object]] = []
    pipeline = Pipeline(BristlenoseSettings(), skip_confirm=True)
    pipeline.set_progress_sink(lambda **fields: collected.append(fields))

    for stage in (STAGE_SPEAKERS, STAGE_TOPICS, STAGE_QUOTES, STAGE_CLUSTER, STAGE_RENDER):
        pipeline._emit_stage_entry(stage)

    emitted = {c.get("stage") for c in collected}
    # Set membership — not count, ordering, or "eta is None" (Bach: detail).
    assert emitted == {"speakers", "topics", "quotes", "cluster", "render"}
    # Negative: no manifest name reached the wire. render's manifest name IS
    # "render" (shared and correct), so it is excluded from the trap set.
    manifest_names = {
        STAGE_IDENTIFY_SPEAKERS,
        STAGE_TOPIC_SEGMENTATION,
        STAGE_QUOTE_EXTRACTION,
        STAGE_CLUSTER_AND_GROUP,
    }
    assert emitted.isdisjoint(manifest_names)


def test_emit_stage_entry_carries_last_known_eta():
    # Warm path: a last-known ETA must be re-emitted on stage entry so the
    # determinate ring keeps its fill (no backward jump, no blank) as the verb
    # advances. The only warm-path coverage needed — _emit_remaining unchanged.
    collected: list[dict[str, object]] = []
    pipeline = Pipeline(BristlenoseSettings(), skip_confirm=True)
    pipeline.set_progress_sink(lambda **fields: collected.append(fields))
    pipeline._last_eta_remaining = 90.0
    pipeline._last_predicted_total = 300.0

    pipeline._emit_stage_entry(STAGE_QUOTES)

    assert len(collected) == 1
    emitted = collected[0]
    assert emitted["stage"] == "quotes"
    assert emitted["eta_remaining_seconds"] == 90.0
    assert emitted["predicted_total_seconds"] == 300.0


class _ColdEstimator:
    """Estimator whose stage_completed always returns None — the cold-start
    (<4 history) / late-run (remaining<10s) condition that drives HIGH-3."""

    def stage_completed(self, stage: str, elapsed: float) -> None:
        return None


def test_emit_remaining_clears_carried_eta_when_estimate_goes_cold():
    # HIGH-3 regression guard. When the estimator returns None (cold start, or
    # late-run remaining<10s), _emit_remaining must CLEAR the carried ETA so a
    # stale, too-large estimate from an earlier stage isn't propagated onto the
    # next stage-entry emit. This drives the real _emit_remaining clear branch
    # (not just asserting pass-through), so deleting the `= None` lines in that
    # branch fails this test — which the carry test alone would not catch.
    collected: list[dict[str, object]] = []
    pipeline = Pipeline(
        BristlenoseSettings(), skip_confirm=True, estimator=_ColdEstimator(),
    )
    pipeline.set_progress_sink(lambda **fields: collected.append(fields))
    # An earlier stage left a carried ETA in place:
    pipeline._last_eta_remaining = 90.0
    pipeline._last_predicted_total = 300.0

    # A stage completes but the estimator has no usable estimate → must clear,
    # and must not emit a progress event on the cold path:
    pipeline._emit_remaining(STAGE_QUOTES, elapsed=12.0)
    assert collected == []

    # The next stage entry must NOT carry the stale 90/300:
    pipeline._emit_stage_entry(STAGE_CLUSTER)
    assert len(collected) == 1
    emitted = collected[0]
    assert emitted["stage"] == "cluster"
    assert emitted["eta_remaining_seconds"] is None
    assert emitted["predicted_total_seconds"] is None
