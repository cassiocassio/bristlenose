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
from unittest.mock import patch

import pytest

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
    STAGE_PII,
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
    base: dict[str, object] = {
        "ts": _now_iso(), "run_id": "RUN0001", "kind": KindEnum.RUN, "started_at": _now_iso(),
    }
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
        stage_base=float("nan"),
        stage_span=float("inf"),
        stage_expected_seconds=float("-inf"),
    )
    assert ev.eta_remaining_seconds is None
    assert ev.stage_fraction is None
    assert ev.predicted_total_seconds is None
    assert (ev.stage_base, ev.stage_span, ev.stage_expected_seconds) == (None, None, None)

    f = events_path(tmp_path)
    append_event(f, ev)
    line = f.read_text(encoding="utf-8").strip().splitlines()[-1]
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
    pipeline = Pipeline(BristlenoseSettings())
    pipeline.set_progress_sink(lambda **fields: collected.append(fields))

    for stage in (STAGE_SPEAKERS, STAGE_PII, STAGE_TOPICS, STAGE_QUOTES, STAGE_CLUSTER, STAGE_RENDER):
        pipeline._emit_stage_entry(stage)

    emitted = {c.get("stage") for c in collected}
    # Set membership — not count, ordering, or "eta is None" (Bach: detail).
    assert emitted == {"speakers", "pii", "topics", "quotes", "cluster", "render"}
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
    pipeline = Pipeline(BristlenoseSettings())
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

    def skip_to(self, stage: str) -> tuple[bool, None]:
        return False, None

    def stage_budget(self, stage: str, *, completed: bool = False) -> None:
        return None  # cold: no slice either


def test_emit_remaining_clears_carried_eta_when_estimate_goes_cold():
    # HIGH-3 regression guard. When the estimator returns None (cold start, or
    # late-run remaining<10s), _emit_remaining must CLEAR the carried ETA so a
    # stale, too-large estimate from an earlier stage isn't propagated onto the
    # next stage-entry emit. This drives the real _emit_remaining clear branch
    # (not just asserting pass-through), so deleting the `= None` lines in that
    # branch fails this test — which the carry test alone would not catch.
    collected: list[dict[str, object]] = []
    pipeline = Pipeline(
        BristlenoseSettings(), estimator=_ColdEstimator(),
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


def test_resumed_run_shows_only_the_time_left_to_run(tmp_path):
    """Analyse on an analysed project: every stage before Discussion is cached,
    so the ETA on entering it covers Discussion and Render, not the whole run
    (the Mac showed ~14 min for a step that takes ~4)."""
    from bristlenose.timing import (
        STAGE_DISCUSSION,
        TimingEstimator,
        save_timing_data,
    )

    def stat(mean: float) -> dict:
        return {"mean": mean, "m2": 1.0, "n": 5}

    save_timing_data({"version": 1, "profiles": {"hw": {
        "transcribe": stat(4.0), "speakers": stat(15.0), "topics": stat(15.0),
        "quotes": stat(15.0), "cluster": stat(5.0), "discussion": stat(20.0),
        "render": stat(0.5),
    }}}, tmp_path)
    est = TimingEstimator("hw", tmp_path)
    initial = est.initial_estimate(10.0, 3, discussion_enabled=True)
    assert initial is not None

    collected: list[dict[str, object]] = []
    pipeline = Pipeline(BristlenoseSettings(), estimator=est)
    pipeline.set_progress_sink(lambda **fields: collected.append(fields))
    pipeline._last_eta_remaining = initial.total_seconds
    pipeline._last_predicted_total = initial.total_seconds

    for stage in (STAGE_SPEAKERS, STAGE_TOPICS, STAGE_QUOTES, STAGE_CLUSTER):
        pipeline._emit_stage_entry(stage)  # cache hits: entry, never completion
    pipeline._emit_stage_entry(STAGE_DISCUSSION)

    eta = collected[-1]["eta_remaining_seconds"]
    assert collected[-1]["stage"] == "discussion"
    assert eta == pytest.approx(20.0 * 3 + 0.5 * 3)  # discussion + render only


def _manifest(**stages):
    from bristlenose.manifest import SessionRecord, StageRecord, StageStatus, create_manifest
    m = create_manifest("t", "0")
    for name, (sessions, inputs) in stages.items():
        m.stages[name] = StageRecord(
            status=StageStatus.COMPLETE,
            sessions=None if sessions is None else {
                sid: SessionRecord(status=StageStatus.COMPLETE, session_id=sid) for sid in sessions},
            input_hashes=inputs)
    return m


def test_likely_cached_stages_reads_the_previous_run_in_order():
    from bristlenose import manifest as m
    from bristlenose.pipeline import _likely_cached_stages
    from bristlenose.timing import STAGE_CLUSTER, STAGE_DISCUSSION, STAGE_TRANSCRIBE

    ids = {"s1", "s2"}
    full = {m.STAGE_TRANSCRIBE: (ids, None), m.STAGE_IDENTIFY_SPEAKERS: (ids, None),
            m.STAGE_TOPIC_SEGMENTATION: (ids, None), m.STAGE_QUOTE_EXTRACTION: (ids, None),
            m.STAGE_CLUSTER_AND_GROUP: (None, None), m.STAGE_DISCUSSION: (None, {"guide": "g1"})}
    kw = {"pii_enabled": False, "discussion_enabled": True}
    everything = _likely_cached_stages(_manifest(**full), ids, guide_sha="g1", **kw)
    assert STAGE_DISCUSSION in everything and STAGE_CLUSTER in everything  # PII off is no break
    # a new guide: discussion will run
    assert STAGE_DISCUSSION not in _likely_cached_stages(_manifest(**full), ids, guide_sha="g2", **kw)
    # a new session: transcription runs, and so does everything after it
    assert _likely_cached_stages(_manifest(**full), ids | {"s3"}, guide_sha="g1", **kw) == set()
    # no previous run: nothing is cached
    assert _likely_cached_stages(None, ids, guide_sha="g1", **kw) == set()
    assert STAGE_TRANSCRIBE in everything


def test_a_resume_offers_only_the_work_left_and_rises_only_when_a_stage_really_runs(tmp_path):
    from bristlenose.timing import STAGE_TOPICS, STAGE_TRANSCRIBE, TimingEstimator, save_timing_data

    def stat(mean: float) -> dict:
        return {"mean": mean, "m2": 1.0, "n": 5}

    save_timing_data({"version": 1, "profiles": {"hw": {
        "transcribe": stat(4.0), "speakers": stat(15.0), "topics": stat(15.0),
        "quotes": stat(15.0), "cluster": stat(5.0), "render": stat(0.5),
    }}}, tmp_path)
    est = TimingEstimator("hw", tmp_path)
    cached = {STAGE_TRANSCRIBE, STAGE_SPEAKERS, STAGE_TOPICS, STAGE_QUOTES}
    opening = est.initial_estimate(10.0, 3, likely_cached=cached)
    assert opening is not None and opening.total_seconds < 20  # cluster + render, not the whole run

    collected: list[dict[str, object]] = []
    pipeline = Pipeline(BristlenoseSettings(), estimator=est)
    pipeline.set_progress_sink(lambda **fields: collected.append(fields))
    pipeline._carry_eta(opening)
    for stage in (STAGE_SPEAKERS, STAGE_TOPICS):
        pipeline._emit_stage_entry(stage)
    etas = [c["eta_remaining_seconds"] for c in collected]
    assert all(e is None or e <= opening.total_seconds for e in etas)  # never climbs on a cache hit
    pipeline._stage_runs(STAGE_TOPICS)  # the guess was wrong: topics really runs
    assert collected[-1]["eta_remaining_seconds"] > opening.total_seconds


# ---------------------------------------------------------------------------
# R27 — the ring slice a stage owns rides on its progress events
# ---------------------------------------------------------------------------


def _warm_estimator(tmp_path, **overrides):
    """A seeded profile: transcribe 4 s/min, LLM stages 15 s/session, cluster
    5, render 0.5 — the fixture `tests/test_timing.py` uses. With 10 audio
    minutes and 5 sessions that is 40 + 225 + 25 + 2.5 = 292.5 s."""
    from bristlenose.timing import TimingEstimator, save_timing_data

    def stat(mean: float) -> dict:
        return {"mean": mean, "m2": 1.0, "n": 5}

    profile = {
        "transcribe": stat(4.0), "speakers": stat(15.0), "topics": stat(15.0),
        "quotes": stat(15.0), "cluster": stat(5.0), "render": stat(0.5),
    }
    profile.update(overrides)
    save_timing_data({"version": 1, "profiles": {"hw": profile}}, tmp_path)
    return TimingEstimator("hw", tmp_path)


def test_a_stage_entry_carries_the_ring_slice_the_stage_owns(tmp_path):
    """R27. A ring driven by elapsed over the whole predicted total races to its
    cap as soon as the last big stage starts, because that stage's estimate is
    small and high-variance (docs/design-progress-ring-estimate.md). So every
    estimator-stage event carries the slice the stage owns — where it starts,
    how much of the ring is its, and its expected seconds — from the same
    Welford means the ETA uses. Grouping then fills grouping's slice and
    structurally cannot reach the cap."""
    from bristlenose.timing import STAGE_TRANSCRIBE

    est = _warm_estimator(tmp_path)
    assert est.initial_estimate(10.0, 5).total_seconds == pytest.approx(292.5)
    collected: list[dict[str, object]] = []
    pipeline = Pipeline(BristlenoseSettings(), estimator=est)
    pipeline.set_progress_sink(lambda **fields: collected.append(fields))

    # The run as it happens: each stage enters, then reports its time. Quotes
    # ran long (120 s against 75 expected) — a completed stage still keeps its
    # expected share, so an overrun cannot push the ring past its slice.
    for stage, took in ((STAGE_TRANSCRIBE, 50.0), (STAGE_SPEAKERS, 70.0),
                        (STAGE_TOPICS, 80.0), (STAGE_QUOTES, 120.0)):
        pipeline._emit_stage_entry(stage)
        pipeline._emit_remaining(stage, took)
    # The completion line reads the stage held at its end: base + span, no span.
    quotes_done = collected[-1]
    assert quotes_done["stage"] == "quotes"
    assert quotes_done["stage_base"] == pytest.approx((40 + 225) / 292.5)
    assert quotes_done["stage_span"] == 0.0
    assert quotes_done["stage_expected_seconds"] == 0.0

    pipeline._emit_stage_entry(STAGE_CLUSTER)

    e = collected[-1]
    assert e["stage"] == "cluster"
    assert e["stage_base"] == pytest.approx((40 + 225) / 292.5)   # everything before it
    assert e["stage_span"] == pytest.approx(25 / 292.5)           # its own share
    assert e["stage_expected_seconds"] == pytest.approx(25.0)
    # The ETA figures on the same event are what they were: the prose is untouched.
    assert e["eta_remaining_seconds"] == pytest.approx(27.5)       # cluster + render
    assert all("stage_base" in c for c in collected), "every estimator-stage line carries its slice"


def test_the_budget_rides_the_sink_to_the_events_file(tmp_path):
    """The sink is the one writer of the wire; a field the pipeline sets that
    the sink drops never reaches the Mac, with nothing red."""
    handle = RunHandle(
        "RUN0001", events_file=events_path(tmp_path), kind=KindEnum.RUN,
        started_at=_now_iso(),
    )
    handle.progress(stage="cluster", stage_base=0.8, stage_span=0.15,
                    stage_expected_seconds=20.0)
    line = json.loads(events_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()[-1])
    assert (line["stage_base"], line["stage_span"], line["stage_expected_seconds"]) == (0.8, 0.15, 20.0)
    ev = [e for e in read_events(events_path(tmp_path)) if isinstance(e, RunProgressEvent)][-1]
    assert (ev.stage_base, ev.stage_span, ev.stage_expected_seconds) == (0.8, 0.15, 20.0)


def test_the_people_file_is_timed_as_render(tmp_path):
    """The people-file merge and the scene colours used to run between grouping
    and render in no stage at all: the estimate never counted that tail and
    the ring sat through it (R27). They are inside render's window now, so the
    row says "Rendering" when they start and render's rate learns their time."""
    import time

    import bristlenose.people as people_mod
    import bristlenose.pipeline as pipeline_mod
    from tests.test_pipeline_command_caches import _drive

    entered: list[str] = []
    stage_when_people_written: list[str | None] = []
    steps: list[tuple[str, float]] = []
    real_entry = Pipeline._emit_stage_entry
    real_write = people_mod.write_people_file
    real_step = pipeline_mod._print_step

    def _entry(self, stage):
        entered.append(stage)
        return real_entry(self, stage)

    def _write(*a, **kw):
        stage_when_people_written.append(entered[-1] if entered else None)
        time.sleep(1.0)  # a slow people file: render's time must include it
        return real_write(*a, **kw)

    def _step(message, elapsed):
        steps.append((message, elapsed))
        return real_step(message, elapsed)

    with (
        patch.object(Pipeline, "_emit_stage_entry", new=_entry),
        patch.object(people_mod, "write_people_file", new=_write),
        patch.object(pipeline_mod, "_print_step", new=_step),
    ):
        _drive(tmp_path, "run", 2, {})

    assert stage_when_people_written == [STAGE_RENDER], (
        f"people file written under stage {stage_when_people_written}, entered {entered}"
    )
    rendered = [e for m, e in steps if m == "Rendered report"]
    assert rendered and rendered[0] >= 1.0, f"render's time leaves the people file out: {steps}"


def test_a_failed_discussion_stage_still_reports_its_completion(tmp_path):
    """The discussion lens never abandons the run, so its failure branch used
    to return without telling the estimator the stage was over. The next
    entry then retired it as cache-served: its share left the ring and render
    started below where the ring already was, a stall through the tail; and
    the ETA went on counting a stage that had already run."""
    import asyncio
    from unittest.mock import ANY, MagicMock

    settings = BristlenoseSettings(discussion_lens=True)
    estimator = MagicMock()
    estimator.stage_completed.return_value = None
    estimator.stage_runs.return_value = (False, None)
    estimator.skip_to.return_value = (False, None)
    estimator.stage_budget.return_value = None
    pipeline = Pipeline(settings, estimator=estimator)

    with patch("bristlenose.discussion.stage.run_discussion",
               side_effect=RuntimeError("the model refused")):
        asyncio.run(pipeline._run_discussion(
            [], [], tmp_path, tmp_path, MagicMock(), None, None,
        ))

    estimator.stage_completed.assert_any_call("discussion", ANY)
