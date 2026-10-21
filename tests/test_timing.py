"""Tests for bristlenose.timing — Welford's algorithm, estimates, persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from bristlenose.timing import (
    _SESSION_STAGES,
    ALL_STAGES,
    STAGE_CLUSTER,
    STAGE_DISCUSSION,
    STAGE_PII,
    STAGE_QUOTES,
    STAGE_RENDER,
    STAGE_SPEAKERS,
    STAGE_TOPICS,
    STAGE_TRANSCRIBE,
    Estimate,
    StageActual,
    StageBudget,
    TimingEstimator,
    WelfordStat,
    _fmt,
    load_timing_data,
    save_timing_data,
)

# ---------------------------------------------------------------------------
# WelfordStat
# ---------------------------------------------------------------------------


class TestWelfordStat:
    """Welford's online algorithm: mean, variance, stddev."""

    def test_single_observation(self) -> None:
        s = WelfordStat()
        s.update(10.0)
        assert s.mean == pytest.approx(10.0)
        assert s.n == 1
        # Variance undefined with 1 observation — returns 0.
        assert s.variance == pytest.approx(0.0)
        assert s.stddev == pytest.approx(0.0)

    def test_two_observations(self) -> None:
        s = WelfordStat()
        s.update(10.0)
        s.update(20.0)
        assert s.mean == pytest.approx(15.0)
        assert s.n == 2
        assert s.variance == pytest.approx(50.0)
        assert s.stddev == pytest.approx(50.0 ** 0.5)

    def test_known_sequence(self) -> None:
        """Mean and stddev of [2, 4, 4, 4, 5, 5, 7, 9]."""
        values = [2, 4, 4, 4, 5, 5, 7, 9]
        s = WelfordStat()
        for v in values:
            s.update(v)
        assert s.mean == pytest.approx(5.0)
        assert s.n == 8
        # Sample variance = 32/7 ≈ 4.571, sample stddev ≈ 2.138
        assert s.variance == pytest.approx(32.0 / 7.0)
        assert s.stddev == pytest.approx((32.0 / 7.0) ** 0.5)

    def test_identical_values(self) -> None:
        s = WelfordStat()
        for _ in range(5):
            s.update(7.0)
        assert s.mean == pytest.approx(7.0)
        assert s.variance == pytest.approx(0.0)

    def test_round_trip(self) -> None:
        s = WelfordStat()
        s.update(3.0)
        s.update(7.0)
        d = s.to_dict()
        s2 = WelfordStat.from_dict(d)
        assert s2.mean == pytest.approx(s.mean)
        assert s2.m2 == pytest.approx(s.m2)
        assert s2.n == s.n

    def test_empty_stat(self) -> None:
        s = WelfordStat()
        assert s.mean == 0.0
        assert s.n == 0
        assert s.variance == 0.0
        assert s.stddev == 0.0


# ---------------------------------------------------------------------------
# Estimate formatting
# ---------------------------------------------------------------------------


class TestEstimate:
    def test_range_str_minutes(self) -> None:
        e = Estimate(total_seconds=480.0, stddev_seconds=120.0)
        assert e.range_str == "~8 min (±2 min)"

    def test_range_str_seconds(self) -> None:
        e = Estimate(total_seconds=45.0, stddev_seconds=10.0)
        assert e.range_str == "~45 sec (±10 sec)"

    def test_range_str_boundary(self) -> None:
        """90 seconds rounds to 2 min."""
        e = Estimate(total_seconds=90.0, stddev_seconds=30.0)
        assert e.range_str == "~2 min (±30 sec)"

    def test_range_str_small_stddev(self) -> None:
        e = Estimate(total_seconds=300.0, stddev_seconds=0.4)
        assert "±1 sec" in e.range_str

    def test_range_str_without_range(self) -> None:
        """When show_range=False, only the point estimate is shown."""
        e = Estimate(total_seconds=480.0, stddev_seconds=120.0, show_range=False)
        assert e.range_str == "~8 min"
        assert "±" not in e.range_str


class TestFmt:
    def test_minutes(self) -> None:
        assert _fmt(480.0) == "8 min"

    def test_seconds(self) -> None:
        assert _fmt(45.0) == "45 sec"

    def test_minimum_one_second(self) -> None:
        assert _fmt(0.1) == "1 sec"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_load_missing_file(self, tmp_path: Path) -> None:
        data = load_timing_data(tmp_path)
        assert data == {"version": 1, "profiles": {}}

    def test_round_trip(self, tmp_path: Path) -> None:
        data = {
            "version": 1,
            "profiles": {
                "test-key": {
                    "transcribe": {"mean": 4.2, "m2": 1.8, "n": 7},
                },
            },
        }
        save_timing_data(data, tmp_path)
        loaded = load_timing_data(tmp_path)
        assert loaded["profiles"]["test-key"]["transcribe"]["mean"] == pytest.approx(4.2)
        assert loaded["profiles"]["test-key"]["transcribe"]["n"] == 7

    def test_corrupt_file(self, tmp_path: Path) -> None:
        (tmp_path / "timing.json").write_text("not json {{{", encoding="utf-8")
        data = load_timing_data(tmp_path)
        assert data == {"version": 1, "profiles": {}}

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b"
        save_timing_data({"version": 1, "profiles": {}}, nested)
        assert (nested / "timing.json").exists()


# ---------------------------------------------------------------------------
# TimingEstimator
# ---------------------------------------------------------------------------


def _seed_profile(
    config_dir: Path,
    hardware_key: str,
    *,
    transcribe_rate: float = 4.0,
    llm_rate: float = 15.0,
    cluster_rate: float = 5.0,
    render_rate: float = 0.5,
    n: int = 5,
) -> None:
    """Write a pre-seeded timing profile to disk."""
    def _stat(mean: float) -> dict:
        # Fake M2 for some variance (stddev ≈ mean * 0.2).
        m2 = (mean * 0.2) ** 2 * (n - 1) if n >= 2 else 0.0
        return {"mean": mean, "m2": m2, "n": n}

    data = {
        "version": 1,
        "profiles": {
            hardware_key: {
                STAGE_TRANSCRIBE: _stat(transcribe_rate),
                STAGE_SPEAKERS: _stat(llm_rate),
                STAGE_TOPICS: _stat(llm_rate),
                STAGE_QUOTES: _stat(llm_rate),
                STAGE_CLUSTER: _stat(cluster_rate),
                STAGE_RENDER: _stat(render_rate),
            },
        },
    }
    save_timing_data(data, config_dir)


class TestTimingEstimator:
    def test_cold_start_no_estimate(self, tmp_path: Path) -> None:
        """First run ever — no history, no estimate."""
        est = TimingEstimator("new-key", tmp_path)
        result = est.initial_estimate(10.0, 3)
        assert result is None

    def test_initial_estimate_with_history(self, tmp_path: Path) -> None:
        key = "test-hw"
        _seed_profile(tmp_path, key, transcribe_rate=4.0, llm_rate=15.0)
        est = TimingEstimator(key, tmp_path)
        result = est.initial_estimate(10.0, 5)
        assert result is not None
        # transcribe: 4 * 10 = 40s, speakers/topics/quotes: 15 * 5 * 3 = 225s,
        # cluster: 5 * 5 = 25s, render: 0.5 * 5 = 2.5s → total ≈ 292.5
        assert result.total_seconds == pytest.approx(292.5)
        assert result.stddev_seconds > 0

    def test_skip_transcription(self, tmp_path: Path) -> None:
        key = "test-hw"
        _seed_profile(tmp_path, key, transcribe_rate=4.0)
        est = TimingEstimator(key, tmp_path)
        full = est.initial_estimate(10.0, 5)
        est2 = TimingEstimator(key, tmp_path)
        skip = est2.initial_estimate(10.0, 5, skip_transcription=True)
        assert full is not None
        assert skip is not None
        # Skipping transcription should reduce the estimate.
        assert skip.total_seconds < full.total_seconds

    def test_stage_completed_revises_remaining(self, tmp_path: Path) -> None:
        key = "test-hw"
        _seed_profile(tmp_path, key, transcribe_rate=4.0, llm_rate=15.0)
        est = TimingEstimator(key, tmp_path)
        initial = est.initial_estimate(10.0, 5)
        assert initial is not None

        # After transcription completes (took 50s actual), remaining drops.
        remaining = est.stage_completed(STAGE_TRANSCRIBE, 50.0)
        assert remaining is not None
        assert remaining.total_seconds < initial.total_seconds

    def test_entering_a_stage_retires_the_cached_stages_before_it(self, tmp_path: Path) -> None:
        """A resumed run: every stage before cluster came from cache, so only
        cluster and render are left — not the whole-run 292.5 s."""
        key = "test-hw"
        _seed_profile(tmp_path, key, transcribe_rate=4.0, llm_rate=15.0)
        est = TimingEstimator(key, tmp_path)
        assert est.initial_estimate(10.0, 5).total_seconds == pytest.approx(292.5)

        changed, remaining = est.skip_to(STAGE_CLUSTER)
        assert changed and remaining is not None
        assert remaining.total_seconds == pytest.approx(27.5)  # cluster 25 + render 2.5
        assert est.skip_to(STAGE_CLUSTER) == (False, None)  # nothing new to retire

    def test_a_resume_opens_on_what_will_run_and_never_climbs_back(self, tmp_path: Path) -> None:
        """No estimate offered that counts work the cache will do: the opening
        figure leaves the cached stages out, and so does every update after."""
        key = "test-hw"
        _seed_profile(tmp_path, key, transcribe_rate=4.0, llm_rate=15.0)
        est = TimingEstimator(key, tmp_path)
        cached = {STAGE_TRANSCRIBE, STAGE_SPEAKERS, STAGE_TOPICS, STAGE_QUOTES}
        opening = est.initial_estimate(10.0, 5, likely_cached=cached)
        assert opening is not None and opening.total_seconds == pytest.approx(27.5)  # cluster + render
        figures = [est.skip_to(s)[1] for s in (STAGE_SPEAKERS, STAGE_TOPICS, STAGE_QUOTES, STAGE_CLUSTER)]
        assert all(f is None or f.total_seconds <= opening.total_seconds for f in figures)

    def test_a_stage_guessed_cached_that_starts_is_counted(self, tmp_path: Path) -> None:
        key = "test-hw"
        _seed_profile(tmp_path, key, transcribe_rate=4.0, llm_rate=15.0)
        est = TimingEstimator(key, tmp_path)
        est.initial_estimate(10.0, 5, likely_cached={STAGE_TRANSCRIBE, STAGE_SPEAKERS, STAGE_TOPICS, STAGE_QUOTES})
        est.skip_to(STAGE_SPEAKERS)
        assert est.skip_to(STAGE_TOPICS)[1] is not None  # entry alone: still left out
        assert est.skip_to(STAGE_TOPICS) == (False, None)
        changed, remaining = est.stage_runs(STAGE_TOPICS)  # wrong guess: topics really runs
        assert changed and remaining is not None
        assert remaining.total_seconds == pytest.approx(75 + 25 + 2.5)  # topics + cluster + render

    def test_skip_to_keeps_a_stage_that_ran(self, tmp_path: Path) -> None:
        key = "test-hw"
        _seed_profile(tmp_path, key, transcribe_rate=4.0, llm_rate=15.0)
        est = TimingEstimator(key, tmp_path)
        est.initial_estimate(10.0, 5)
        est.stage_completed(STAGE_TRANSCRIBE, 50.0)  # really ran
        est.skip_to(STAGE_SPEAKERS)
        assert est._completed[STAGE_TRANSCRIBE] == 50.0

    def test_stage_completed_returns_none_near_end(self, tmp_path: Path) -> None:
        """When only trivial work remains, returns None (don't print)."""
        key = "test-hw"
        _seed_profile(tmp_path, key, transcribe_rate=0.1, llm_rate=0.1,
                       cluster_rate=0.1, render_rate=0.1)
        est = TimingEstimator(key, tmp_path)
        est.initial_estimate(1.0, 1)
        for stage in ALL_STAGES[:-1]:
            est.stage_completed(stage, 0.1)
        # Only render left, estimated at ~0.1s — too small to print.
        result = est.stage_completed(STAGE_RENDER, 0.1)
        assert result is None

    def test_record_run_persists(self, tmp_path: Path) -> None:
        key = "test-hw"
        est = TimingEstimator(key, tmp_path)
        est.record_run({
            STAGE_TRANSCRIBE: StageActual(elapsed=40.0, input_size=10.0),
            STAGE_SPEAKERS: StageActual(elapsed=30.0, input_size=3.0),
        })

        # Reload and check it was saved.
        est2 = TimingEstimator(key, tmp_path)
        profile = est2._profile
        assert profile[STAGE_TRANSCRIBE].mean == pytest.approx(4.0)
        assert profile[STAGE_TRANSCRIBE].n == 1
        assert profile[STAGE_SPEAKERS].mean == pytest.approx(10.0)

    def test_record_run_accumulates(self, tmp_path: Path) -> None:
        """Multiple runs refine the estimate."""
        key = "test-hw"
        for rate in [4.0, 6.0]:
            est = TimingEstimator(key, tmp_path)
            est.record_run({
                STAGE_TRANSCRIBE: StageActual(elapsed=rate * 10, input_size=10.0),
            })
        est3 = TimingEstimator(key, tmp_path)
        assert est3._profile[STAGE_TRANSCRIBE].n == 2
        assert est3._profile[STAGE_TRANSCRIBE].mean == pytest.approx(5.0)

    def test_zero_input_size_ignored(self, tmp_path: Path) -> None:
        key = "test-hw"
        est = TimingEstimator(key, tmp_path)
        est.record_run({
            STAGE_TRANSCRIBE: StageActual(elapsed=10.0, input_size=0.0),
        })
        assert not est.has_history()

    def test_has_history(self, tmp_path: Path) -> None:
        key = "test-hw"
        est = TimingEstimator(key, tmp_path)
        assert not est.has_history()

        # Need MIN_N_ESTIMATE (4) runs before has_history() is True.
        for i in range(3):
            e = TimingEstimator(key, tmp_path)
            e.record_run({
                STAGE_TRANSCRIBE: StageActual(elapsed=40.0 + i, input_size=10.0),
            })
        assert not TimingEstimator(key, tmp_path).has_history()

        # Fourth run crosses the threshold.
        e = TimingEstimator(key, tmp_path)
        e.record_run({
            STAGE_TRANSCRIBE: StageActual(elapsed=44.0, input_size=10.0),
        })
        assert TimingEstimator(key, tmp_path).has_history()

    def test_show_range_requires_enough_data(self, tmp_path: Path) -> None:
        """Estimate hides ±range until n >= MIN_N_RANGE (8)."""
        key = "test-hw"
        # n=5: enough for an estimate, not enough for ±range.
        _seed_profile(tmp_path, key, n=5)
        est = TimingEstimator(key, tmp_path)
        result = est.initial_estimate(10.0, 5)
        assert result is not None
        assert result.show_range is False
        assert "±" not in result.range_str

        # n=8: range should now appear.
        _seed_profile(tmp_path, key, n=8)
        est2 = TimingEstimator(key, tmp_path)
        result2 = est2.initial_estimate(10.0, 5)
        assert result2 is not None
        assert result2.show_range is True
        assert "±" in result2.range_str

    def test_estimate_breakdown_keys(self, tmp_path: Path) -> None:
        key = "test-hw"
        _seed_profile(tmp_path, key)
        est = TimingEstimator(key, tmp_path)
        result = est.initial_estimate(10.0, 5)
        assert result is not None
        # PII and Discussion are conditional — the estimator counts them only
        # when told they will run, and this call does not say so: every OTHER
        # stage is in the breakdown, and those two are deliberately not.
        for stage in ALL_STAGES:
            if stage in (STAGE_PII, STAGE_DISCUSSION):
                assert stage not in result.breakdown
            else:
                assert stage in result.breakdown


class TestStageBudget:
    """The ring slice a stage owns (R27): shares of the run's expected time,
    renormalised over the stages that run, from the same means as the ETA."""

    @staticmethod
    def _warm(tmp_path: Path) -> TimingEstimator:
        _seed_profile(tmp_path, "hw", transcribe_rate=4.0, llm_rate=15.0)
        return TimingEstimator("hw", tmp_path)

    def test_shares_follow_pipeline_order_and_sum_to_one(self, tmp_path: Path) -> None:
        est = self._warm(tmp_path)
        est.initial_estimate(10.0, 5)   # 40 + 75×3 + 25 + 2.5 = 292.5
        budgets = {s: est.stage_budget(s) for s in (
            STAGE_TRANSCRIBE, STAGE_SPEAKERS, STAGE_TOPICS, STAGE_QUOTES, STAGE_CLUSTER, STAGE_RENDER,
        )}
        assert all(b is not None for b in budgets.values())
        assert budgets[STAGE_TRANSCRIBE].base == 0.0
        assert budgets[STAGE_CLUSTER].base == pytest.approx(265 / 292.5)
        assert budgets[STAGE_CLUSTER].span == pytest.approx(25 / 292.5)
        assert budgets[STAGE_CLUSTER].expected_seconds == pytest.approx(25.0)
        assert budgets[STAGE_RENDER].base + budgets[STAGE_RENDER].span == pytest.approx(1.0)
        assert sum(b.span for b in budgets.values()) == pytest.approx(1.0)

    def test_a_completed_stage_keeps_its_expected_share(self, tmp_path: Path) -> None:
        """Quotes took twice its estimate; grouping still starts where the
        estimate said, so no stage can push the ring past its slice."""
        est = self._warm(tmp_path)
        est.initial_estimate(10.0, 5)
        for s, took in ((STAGE_TRANSCRIBE, 50.0), (STAGE_SPEAKERS, 70.0),
                        (STAGE_TOPICS, 80.0), (STAGE_QUOTES, 150.0)):
            est.stage_completed(s, took)
        assert est.stage_budget(STAGE_CLUSTER).base == pytest.approx(265 / 292.5)

    def test_skipped_transcription_gives_its_share_to_the_rest(self, tmp_path: Path) -> None:
        est = self._warm(tmp_path)
        est.initial_estimate(10.0, 5, skip_transcription=True)   # 252.5 s without transcribe
        assert est.stage_budget(STAGE_SPEAKERS).base == 0.0
        assert est.stage_budget(STAGE_CLUSTER).span == pytest.approx(25 / 252.5)
        assert est.stage_budget(STAGE_TRANSCRIBE).span == 0.0

    def test_cached_stages_leave_the_ring_to_the_stages_that_run(self, tmp_path: Path) -> None:
        """A resume: the opening guess says the four early stages are cached,
        and entering cluster confirms it. Cluster and render share the ring."""
        est = self._warm(tmp_path)
        est.initial_estimate(10.0, 5, likely_cached={STAGE_TRANSCRIBE, STAGE_SPEAKERS,
                                                     STAGE_TOPICS, STAGE_QUOTES})
        est.skip_to(STAGE_CLUSTER)
        b = est.stage_budget(STAGE_CLUSTER)
        assert b.base == 0.0 and b.span == pytest.approx(25 / 27.5)
        assert est.stage_budget(STAGE_RENDER).base == pytest.approx(25 / 27.5)

    def test_stages_the_cache_served_on_entry_drop_out(self, tmp_path: Path) -> None:
        """The opening guess had everything running; entering cluster with
        nothing completed says the four before it came from cache after all.
        They leave the ring: cluster starts at 0 and shares it with render."""
        est = self._warm(tmp_path)
        est.initial_estimate(10.0, 5)
        assert est.stage_budget(STAGE_CLUSTER).base == pytest.approx(265 / 292.5)
        est.skip_to(STAGE_CLUSTER)
        b = est.stage_budget(STAGE_CLUSTER)
        assert b.base == 0.0 and b.span == pytest.approx(25 / 27.5)

    def test_a_stage_the_cache_serves_holds_at_its_base(self, tmp_path: Path) -> None:
        """Entry to a stage the opening guess had cached: zero span at its
        base, so the ring holds rather than moving on work that takes no time."""
        est = self._warm(tmp_path)
        est.initial_estimate(10.0, 5, likely_cached={STAGE_TRANSCRIBE})
        est.skip_to(STAGE_SPEAKERS)
        b = est.stage_budget(STAGE_TRANSCRIBE)
        assert b == StageBudget(base=0.0, span=0.0, expected_seconds=0.0)
        assert est.stage_budget(STAGE_SPEAKERS).base == 0.0

    def test_a_stage_guessed_cached_that_runs_takes_its_share_back(self, tmp_path: Path) -> None:
        est = self._warm(tmp_path)
        est.initial_estimate(10.0, 5, likely_cached={STAGE_TRANSCRIBE, STAGE_SPEAKERS})
        est.skip_to(STAGE_SPEAKERS)
        assert est.stage_budget(STAGE_SPEAKERS).span == 0.0
        est.stage_runs(STAGE_SPEAKERS)
        assert est.stage_budget(STAGE_SPEAKERS).span == pytest.approx(75 / 252.5)

    def test_a_wrong_cache_guess_only_ever_moves_the_ring_forward(self, tmp_path: Path) -> None:
        """Speakers ran; topics was guessed cached and runs after all. The
        guessed stage keeps its weight in the frame throughout, so no base
        behind it shrinks when the guess is corrected: the ring, which never
        runs backwards, is not left waiting for the fill to catch up."""
        est = self._warm(tmp_path)
        est.initial_estimate(10.0, 5, likely_cached={STAGE_TOPICS})
        est.stage_completed(STAGE_TRANSCRIBE, 50.0)
        est.stage_completed(STAGE_SPEAKERS, 70.0)
        est.skip_to(STAGE_TOPICS)
        at_entry = est.stage_budget(STAGE_TOPICS)
        assert at_entry == StageBudget(base=(40 + 75) / 292.5, span=0.0, expected_seconds=0.0)
        est.stage_runs(STAGE_TOPICS)
        running = est.stage_budget(STAGE_TOPICS)
        assert running.base == at_entry.base
        assert running.span == pytest.approx(75 / 292.5)
        assert est.stage_budget(STAGE_QUOTES).base == pytest.approx((40 + 150) / 292.5)

    def test_a_completed_stage_reads_held_at_its_end(self, tmp_path: Path) -> None:
        est = self._warm(tmp_path)
        est.initial_estimate(10.0, 5)
        est.stage_completed(STAGE_TRANSCRIBE, 50.0)
        assert est.stage_budget(STAGE_TRANSCRIBE, completed=True) == StageBudget(
            base=40 / 292.5, span=0.0, expected_seconds=0.0)

    def test_thin_history_offers_no_budget(self, tmp_path: Path) -> None:
        """The same bar as the ETA: under four runs, the whole-run ring."""
        _seed_profile(tmp_path, "hw", n=3)
        est = TimingEstimator("hw", tmp_path)
        assert est.initial_estimate(10.0, 5) is None
        assert est.stage_budget(STAGE_CLUSTER) is None

    def test_a_configured_stage_with_no_data_withholds_the_budget_for_the_run(
        self, tmp_path: Path,
    ) -> None:
        """Redaction on for the first time: its share would be an invented
        zero, so no budget this run — decided at the opening estimate, so a
        later cache correction cannot switch the ring's model mid-run. The next
        run, with one observation, is weighted."""
        est = self._warm(tmp_path)
        est.initial_estimate(10.0, 5, pii_enabled=True, likely_cached={STAGE_PII})
        assert est.stage_budget(STAGE_CLUSTER) is None
        est.skip_to(STAGE_PII)
        est.stage_runs(STAGE_PII)
        assert est.stage_budget(STAGE_PII) is None
        est.record_run({STAGE_PII: StageActual(elapsed=8.0, input_size=5.0)})
        est.initial_estimate(10.0, 5, pii_enabled=True)
        assert est.stage_budget(STAGE_PII).span > 0

    def test_a_stage_that_is_off_is_not_in_the_ring(self, tmp_path: Path) -> None:
        est = self._warm(tmp_path)
        est.initial_estimate(10.0, 5)   # pii and discussion off
        assert est.stage_budget(STAGE_PII) == StageBudget(base=(40 + 75) / 292.5, span=0.0,
                                                          expected_seconds=0.0)
        assert est.stage_budget(STAGE_DISCUSSION).span == 0.0
        assert est.stage_budget("download") is None   # not an estimator stage


class TestConditionalPIIStage:
    """`pii` is in the vocabulary but runs only when redaction is on.

    Until 12 Sep 2026 the estimator omitted it entirely — the ring froze
    through redaction and every warm total was short by its duration. Adding a
    conditional stage has one subtlety: it must be skipped in BOTH loops, or a
    disabled PII is counted as *remaining* until the run ends.
    """

    @staticmethod
    def _warm(tmp_path: Path, key: str, *, with_pii: bool) -> TimingEstimator:
        _seed_profile(tmp_path, key)
        est = TimingEstimator(key, tmp_path)
        if with_pii:
            # Seed pii's own rate the way a real run would, four times over.
            for _ in range(4):
                est.record_run({STAGE_PII: StageActual(elapsed=8.0, input_size=4.0)})
        return est

    def test_vocabulary_order_and_scaling(self) -> None:
        assert ALL_STAGES.index(STAGE_PII) == ALL_STAGES.index(STAGE_SPEAKERS) + 1
        assert STAGE_PII in _SESSION_STAGES, "per-transcript, so it scales by session count"

    def test_off_by_default_is_not_predicted(self, tmp_path: Path) -> None:
        est = self._warm(tmp_path, "hw", with_pii=True)
        result = est.initial_estimate(10.0, 5)
        assert result is not None and STAGE_PII not in result.breakdown

    def test_on_is_predicted(self, tmp_path: Path) -> None:
        est = self._warm(tmp_path, "hw", with_pii=True)
        result = est.initial_estimate(10.0, 5, pii_enabled=True)
        assert result is not None and STAGE_PII in result.breakdown
        assert result.breakdown[STAGE_PII] > 0

    def test_off_is_not_counted_as_remaining(self, tmp_path: Path) -> None:
        """The second loop. Without this skip a disabled PII inflates every ETA."""
        est = self._warm(tmp_path, "hw", with_pii=True)
        est.initial_estimate(10.0, 5, pii_enabled=False)
        remaining = est.stage_completed(STAGE_SPEAKERS, 5.0)
        assert remaining is not None and STAGE_PII not in remaining.breakdown

    def test_on_is_counted_as_remaining_until_done(self, tmp_path: Path) -> None:
        est = self._warm(tmp_path, "hw", with_pii=True)
        est.initial_estimate(10.0, 5, pii_enabled=True)
        after_speakers = est.stage_completed(STAGE_SPEAKERS, 5.0)
        assert after_speakers is not None and STAGE_PII in after_speakers.breakdown
        after_pii = est.stage_completed(STAGE_PII, 8.0)
        assert after_pii is not None and STAGE_PII not in after_pii.breakdown

    def test_old_profile_without_pii_stays_warm(self, tmp_path: Path) -> None:
        """A timing.json written before pii existed must not cold-start the estimator.

        `_estimate_stage` returns (0, 0) for a stage with no history and
        `has_history` is any(), so the estimate is simply missing pii's share
        until four redacted runs have taught it — graceful, not None.
        """
        est = self._warm(tmp_path, "hw", with_pii=False)
        result = est.initial_estimate(10.0, 5, pii_enabled=True)
        assert result is not None
        assert result.breakdown.get(STAGE_PII, 0.0) == 0.0
