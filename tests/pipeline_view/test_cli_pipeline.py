"""Narrow CLI wiring tests for `bristlenose pipeline`.

Behaviour-level dispatch is covered by test_render.py — these tests confirm the
Typer command exists, parses --json / --stage, and exits non-zero for unknown
stages.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from bristlenose.cli import app
from bristlenose.pipeline_view.cli import _collapse
from bristlenose.pipeline_view.render import ModelAvailability

runner = CliRunner()


def _row(
    *, model_id: str | None, available: bool, reason_key: str | None = None
) -> ModelAvailability:
    return ModelAvailability(
        provider_id="anthropic",
        model_id=model_id,
        display=model_id or "Claude",
        provider_display="Claude",
        available=available,
        reason_key=reason_key,
    )


def test_collapse_single_no_model_grain() -> None:
    """A provider with one row and no model_id IS the backend — collapse."""
    rows = [_row(model_id=None, available=True)]
    collapsed, rep = _collapse(rows)
    assert collapsed is True
    assert rep is rows[0]


def test_collapse_all_unavailable_uniform_reason() -> None:
    """Every model failing the same provider-level reason collapses to one line."""
    rows = [
        _row(model_id="claude-opus-4-20250514", available=False, reason_key="no_key"),
        _row(model_id="claude-sonnet-4-20250514", available=False, reason_key="no_key"),
    ]
    collapsed, rep = _collapse(rows)
    assert collapsed is True
    assert rep is rows[0]


def test_collapse_all_unavailable_divergent_reasons_expands() -> None:
    """Divergent per-model failure reasons must stay expanded — one line would
    lose the distinction between why each model is unavailable."""
    rows = [
        _row(model_id="claude-opus-4-20250514", available=False, reason_key="no_key"),
        _row(
            model_id="claude-sonnet-4-20250514",
            available=False,
            reason_key="not_in_account",
        ),
    ]
    collapsed, _ = _collapse(rows)
    assert collapsed is False


def test_pipeline_command_exits_zero() -> None:
    result = runner.invoke(app, ["pipeline"])
    assert result.exit_code == 0
    # The matrix renders stage-group headings in uppercase; transcription is
    # always its own single-stage group regardless of host facts.
    assert "TRANSCRIPTION" in result.output.upper()


def test_pipeline_json_parses() -> None:
    result = runner.invoke(app, ["pipeline", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "catalogue" in payload
    assert "host" in payload
    ids = [s["id"] for s in payload["catalogue"]]
    assert "quote_extraction" in ids


def test_pipeline_stage_filter() -> None:
    result = runner.invoke(app, ["pipeline", "--json", "--stage", "quote_extraction"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["catalogue"]) == 1
    assert payload["catalogue"][0]["id"] == "quote_extraction"


def test_pipeline_stage_unknown_exits_nonzero() -> None:
    result = runner.invoke(app, ["pipeline", "--stage", "not_a_stage"])
    assert result.exit_code != 0
