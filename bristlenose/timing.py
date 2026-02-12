"""Time estimation using Welford's online algorithm.

Learns from each pipeline run to estimate future run times. Stores per-metric
running statistics (mean, variance, count) keyed by hardware+config profile.

The estimator prints an upfront estimate after ingest and recalculates the
remaining time as each stage completes. A future visual UI can consume the
same data via the PipelineEvent callback.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bristlenose.config import BristlenoseSettings

logger = logging.getLogger(__name__)

# Stages that contribute meaningfully to runtime, in pipeline order.
# Each maps to one rate metric in the timing profile.
STAGE_TRANSCRIBE = "transcribe"
STAGE_SPEAKERS = "speakers"
STAGE_TOPICS = "topics"
STAGE_QUOTES = "quotes"
STAGE_CLUSTER = "cluster"
STAGE_RENDER = "render"

# Stages driven by session count (1 LLM call per session).
_SESSION_STAGES = (STAGE_SPEAKERS, STAGE_TOPICS, STAGE_QUOTES)

# All stages in pipeline order (used for remaining-time recalculation).
ALL_STAGES = (
    STAGE_TRANSCRIBE,
    STAGE_SPEAKERS,
    STAGE_TOPICS,
    STAGE_QUOTES,
    STAGE_CLUSTER,
    STAGE_RENDER,
)


# ---------------------------------------------------------------------------
# Welford's online algorithm
# ---------------------------------------------------------------------------


@dataclass
class WelfordStat:
    """Running mean and variance via Welford's online algorithm.

    Stores three values: mean, M2 (sum of squared differences), and count.
    Variance = M2 / (n - 1) when n >= 2.
    """

    mean: float = 0.0
    m2: float = 0.0
    n: int = 0

    def update(self, value: float) -> None:
        """Incorporate a new observation."""
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        delta2 = value - self.mean
        self.m2 += delta * delta2

    @property
    def variance(self) -> float:
        if self.n < 2:
            return 0.0
        return self.m2 / (self.n - 1)

    @property
    def stddev(self) -> float:
        return self.variance ** 0.5

    def to_dict(self) -> dict[str, float | int]:
        return {"mean": self.mean, "m2": self.m2, "n": self.n}

    @classmethod
    def from_dict(cls, d: dict[str, float | int]) -> WelfordStat:
        return cls(mean=float(d["mean"]), m2=float(d["m2"]), n=int(d["n"]))


# ---------------------------------------------------------------------------
# Estimate result
# ---------------------------------------------------------------------------


@dataclass
class Estimate:
    """A time estimate with uncertainty."""

    total_seconds: float
    stddev_seconds: float
    breakdown: dict[str, float] = field(default_factory=dict)

    @property
    def range_str(self) -> str:
        """Format as '~8 min (±2 min)' or '~45 sec (±10 sec)'."""
        return f"~{_fmt(self.total_seconds)} (±{_fmt(self.stddev_seconds)})"


def _fmt(seconds: float) -> str:
    """Format seconds for estimate display: '8 min' or '45 sec'."""
    if seconds >= 90:
        m = round(seconds / 60)
        return f"{m} min"
    return f"{max(1, round(seconds))} sec"


# ---------------------------------------------------------------------------
# Pipeline event (for future UI)
# ---------------------------------------------------------------------------


@dataclass
class PipelineEvent:
    """Lightweight event emitted by the pipeline at key points.

    A CLI handler prints estimate lines. A future GUI/web UI can use the same
    events to drive a progress bar.
    """

    kind: str  # "estimate", "stage_start", "stage_complete", "progress"
    stage: str = ""
    elapsed: float | None = None
    estimate: Estimate | None = None
    detail: str = ""


# ---------------------------------------------------------------------------
# Hardware key
# ---------------------------------------------------------------------------


def build_hardware_key(settings: BristlenoseSettings) -> str:
    """Build a profile key from hardware + config.

    Estimates are only meaningful for the same hardware+config combo.
    """
    from bristlenose.utils.hardware import detect_hardware

    hw = detect_hardware()
    chip = hw.chip_name or hw.accelerator.value
    backend = settings.whisper_backend
    if backend == "auto":
        backend = hw.recommended_whisper_backend
    return (
        f"{chip} | {backend} | {settings.whisper_model}"
        f" | {settings.llm_provider} | {settings.llm_model}"
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

_TIMING_FILENAME = "timing.json"


def _timing_path(config_dir: Path) -> Path:
    return config_dir / _TIMING_FILENAME


def load_timing_data(config_dir: Path) -> dict:
    """Load timing profiles from disk. Returns empty structure on error."""
    path = _timing_path(config_dir)
    if not path.exists():
        return {"version": 1, "profiles": {}}
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or "profiles" not in data:
            return {"version": 1, "profiles": {}}
        return data
    except (json.JSONDecodeError, OSError):
        logger.debug("Could not load timing data from %s", path)
        return {"version": 1, "profiles": {}}


def save_timing_data(data: dict, config_dir: Path) -> None:
    """Write timing profiles to disk."""
    path = _timing_path(config_dir)
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n")
    except OSError:
        logger.debug("Could not save timing data to %s", path)


# ---------------------------------------------------------------------------
# TimingEstimator
# ---------------------------------------------------------------------------


@dataclass
class StageActual:
    """Actual timing for one stage after completion."""

    elapsed: float  # seconds
    input_size: float  # audio_minutes, session_count, or 1.0 for fixed stages


class TimingEstimator:
    """Learns from past runs to estimate future pipeline duration.

    Tracks rate-based metrics (e.g. seconds per audio minute for transcription,
    seconds per session for LLM stages) using Welford's online algorithm.
    """

    def __init__(self, hardware_key: str, config_dir: Path) -> None:
        self.hardware_key = hardware_key
        self.config_dir = config_dir
        self._data = load_timing_data(config_dir)
        self._profile = self._load_profile()
        # Input sizes set by caller after ingest.
        self.audio_minutes: float = 0.0
        self.session_count: int = 0
        # Track completed stages for remaining-time recalculation.
        self._completed: dict[str, float] = {}
        # Pipeline start time (set externally).
        self._pipeline_start: float = 0.0

    def _load_profile(self) -> dict[str, WelfordStat]:
        """Load or create the profile for this hardware key."""
        raw = self._data["profiles"].get(self.hardware_key, {})
        profile: dict[str, WelfordStat] = {}
        for metric, stat_dict in raw.items():
            if isinstance(stat_dict, dict) and "mean" in stat_dict:
                profile[metric] = WelfordStat.from_dict(stat_dict)
        return profile

    def _input_size_for(self, stage: str) -> float:
        """Return the input size that drives a stage's duration."""
        if stage == STAGE_TRANSCRIBE:
            return self.audio_minutes
        if stage in _SESSION_STAGES:
            return float(self.session_count)
        # cluster and render are less predictable; use session count as proxy.
        return float(max(self.session_count, 1))

    def _estimate_stage(self, stage: str) -> tuple[float, float]:
        """Estimate seconds and stddev for a single stage."""
        stat = self._profile.get(stage)
        if stat is None or stat.n == 0:
            return 0.0, 0.0
        size = self._input_size_for(stage)
        return stat.mean * size, stat.stddev * size

    def has_history(self) -> bool:
        """True if we have at least one historical run for this profile."""
        return any(s.n > 0 for s in self._profile.values())

    def initial_estimate(
        self,
        audio_minutes: float,
        session_count: int,
        *,
        skip_transcription: bool = False,
    ) -> Estimate | None:
        """Compute upfront estimate after ingest. Returns None if no history."""
        self.audio_minutes = audio_minutes
        self.session_count = session_count

        if not self.has_history():
            return None

        total = 0.0
        var_total = 0.0
        breakdown: dict[str, float] = {}

        for stage in ALL_STAGES:
            if skip_transcription and stage == STAGE_TRANSCRIBE:
                continue
            secs, sd = self._estimate_stage(stage)
            total += secs
            var_total += sd ** 2
            breakdown[stage] = secs

        if total < 1.0:
            return None

        return Estimate(
            total_seconds=total,
            stddev_seconds=var_total ** 0.5,
            breakdown=breakdown,
        )

    def stage_completed(self, stage: str, elapsed: float) -> Estimate | None:
        """Record a stage completion and return revised remaining estimate.

        Returns None if no useful revision is available.
        """
        self._completed[stage] = elapsed

        if not self.has_history():
            return None

        remaining_total = 0.0
        remaining_var = 0.0
        breakdown: dict[str, float] = {}

        for s in ALL_STAGES:
            if s in self._completed:
                continue
            secs, sd = self._estimate_stage(s)
            remaining_total += secs
            remaining_var += sd ** 2
            breakdown[s] = secs

        if remaining_total < 10.0:
            return None

        return Estimate(
            total_seconds=remaining_total,
            stddev_seconds=remaining_var ** 0.5,
            breakdown=breakdown,
        )

    def record_run(self, actuals: dict[str, StageActual]) -> None:
        """Update stored statistics with actual timings from this run."""
        for stage, actual in actuals.items():
            if actual.input_size <= 0:
                continue
            rate = actual.elapsed / actual.input_size
            if stage not in self._profile:
                self._profile[stage] = WelfordStat()
            self._profile[stage].update(rate)

        # Persist.
        self._data["profiles"][self.hardware_key] = {
            metric: stat.to_dict() for metric, stat in self._profile.items()
        }
        save_timing_data(self._data, self.config_dir)
