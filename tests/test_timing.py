"""Tests for bristlenose.timing — Welford's algorithm, estimates, persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from bristlenose.timing import (
    ALL_STAGES,
    STAGE_CLUSTER,
    STAGE_QUOTES,
    STAGE_RENDER,
    STAGE_SPEAKERS,
    STAGE_TOPICS,
    STAGE_TRANSCRIBE,
    Estimate,
    StageActual,
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
        (tmp_path / "timing.json").write_text("not json {{{")
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
        for stage in ALL_STAGES:
            assert stage in result.breakdown
