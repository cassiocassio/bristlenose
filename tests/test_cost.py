"""Tests for bristlenose.cost — Slice 3 of Phase 1f."""

from __future__ import annotations

from pathlib import Path

import pytest

from bristlenose.cost import (
    RunCost,
    compute_run_cost,
    format_cost_estimate,
)
from bristlenose.events import (
    KindEnum,
    RunCancelledEvent,
    RunCompletedEvent,
    RunFailedEvent,
    events_path,
    read_events,
)
from bristlenose.llm.pricing import CURRENCY, PRICE_TABLE_VERSION
from bristlenose.run_lifecycle import _restore_signal_handlers, run_lifecycle


@pytest.fixture(autouse=True)
def _reset_signal_handlers():
    yield
    _restore_signal_handlers()


# ---------------------------------------------------------------------------
# compute_run_cost
# ---------------------------------------------------------------------------


def test_compute_run_cost_returns_none_when_no_tokens():
    assert compute_run_cost("claude-sonnet-4-20250514", 0, 0) is None


def test_compute_run_cost_known_model():
    rc = compute_run_cost("claude-sonnet-4-20250514", 1_000_000, 500_000)
    assert rc is not None
    # 1M @ $3 + 0.5M @ $15 = $3 + $7.50 = $10.50
    assert rc.cost_usd_estimate == pytest.approx(10.50)
    assert rc.input_tokens == 1_000_000
    assert rc.output_tokens == 500_000
    assert rc.price_table_version == PRICE_TABLE_VERSION
    assert rc.currency == CURRENCY


def test_compute_run_cost_unknown_model_keeps_token_counts():
    """Token counts are real even when we can't price the model."""
    rc = compute_run_cost("some-future-model-99b", 12000, 5000)
    assert rc is not None
    assert rc.cost_usd_estimate is None
    assert rc.input_tokens == 12000
    assert rc.output_tokens == 5000


def test_compute_run_cost_only_input_tokens():
    """Output 0 is a valid case (e.g. transcribe-only with token-counted prompt)."""
    rc = compute_run_cost("claude-sonnet-4-20250514", 100, 0)
    assert rc is not None
    assert rc.cost_usd_estimate is not None


# ---------------------------------------------------------------------------
# format_cost_estimate
# ---------------------------------------------------------------------------


def test_format_cost_estimate_typical():
    assert format_cost_estimate(0.46) == "~$0.46 (est.)"


def test_format_cost_estimate_uses_extra_precision_below_1c():
    """Tiny estimates shouldn't collapse to ~$0.00 (est.)."""
    assert format_cost_estimate(0.0042) == "~$0.0042 (est.)"


def test_format_cost_estimate_none():
    assert format_cost_estimate(None) == "unknown"


def test_format_cost_estimate_zero():
    assert format_cost_estimate(0.0) == "~$0.0000 (est.)"


# ---------------------------------------------------------------------------
# RunHandle integration with run_lifecycle
# ---------------------------------------------------------------------------


def test_run_lifecycle_yields_handle_with_set_cost(tmp_path: Path):
    rc = RunCost(
        input_tokens=12_000,
        output_tokens=5_000,
        cost_usd_estimate=0.42,
        price_table_version=PRICE_TABLE_VERSION,
    )
    with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False) as handle:
        handle.set_cost(rc)
    events = read_events(events_path(tmp_path))
    completed = [e for e in events if isinstance(e, RunCompletedEvent)]
    assert len(completed) == 1
    ev = completed[0]
    assert ev.input_tokens == 12_000
    assert ev.output_tokens == 5_000
    assert ev.cost_usd_estimate == pytest.approx(0.42)
    assert ev.price_table_version == PRICE_TABLE_VERSION


def test_run_lifecycle_no_set_cost_writes_none_fields(tmp_path: Path):
    """If the caller never sets cost (e.g. transcribe-only), fields stay None."""
    with run_lifecycle(tmp_path, KindEnum.TRANSCRIBE_ONLY, install_signal_handlers=False):
        pass
    completed = [
        e for e in read_events(events_path(tmp_path))
        if isinstance(e, RunCompletedEvent)
    ]
    assert len(completed) == 1
    assert completed[0].input_tokens is None
    assert completed[0].cost_usd_estimate is None


def test_run_lifecycle_cost_attached_on_failure(tmp_path: Path):
    """Cost incurred before failure is recorded — answers 'what did this cost me?'"""
    rc = RunCost(
        input_tokens=8_000,
        output_tokens=2_000,
        cost_usd_estimate=0.18,
        price_table_version=PRICE_TABLE_VERSION,
    )
    with pytest.raises(RuntimeError):
        with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False) as handle:
            handle.set_cost(rc)
            raise RuntimeError("boom")
    failed = [
        e for e in read_events(events_path(tmp_path))
        if isinstance(e, RunFailedEvent)
    ]
    assert len(failed) == 1
    assert failed[0].cost_usd_estimate == pytest.approx(0.18)


def test_run_lifecycle_cost_attached_on_cancel(tmp_path: Path):
    rc = RunCost(
        input_tokens=4_000,
        output_tokens=1_000,
        cost_usd_estimate=0.07,
        price_table_version=PRICE_TABLE_VERSION,
    )
    with pytest.raises(KeyboardInterrupt):
        with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False) as handle:
            handle.set_cost(rc)
            raise KeyboardInterrupt()
    cancelled = [
        e for e in read_events(events_path(tmp_path))
        if isinstance(e, RunCancelledEvent)
    ]
    assert len(cancelled) == 1
    assert cancelled[0].cost_usd_estimate == pytest.approx(0.07)
