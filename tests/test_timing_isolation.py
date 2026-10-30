"""Tests must never write the real ~/.config/bristlenose/timing.json (30 Oct 2026: ~200 suite
runs had taught it n≈16,000 observations of 0.02 s per session)."""

from pathlib import Path

import pytest

from bristlenose import cli
from bristlenose.timing import TimingEstimator


def test_the_run_timing_folder_is_not_the_real_one() -> None:
    assert cli._doctor_sentinel_dir().resolve() != Path("~/.config/bristlenose").expanduser().resolve()


def test_an_estimator_on_the_real_folder_is_refused() -> None:
    with pytest.raises(AssertionError, match="real ~/.config/bristlenose"):
        TimingEstimator("hw", Path("~/.config/bristlenose").expanduser())
