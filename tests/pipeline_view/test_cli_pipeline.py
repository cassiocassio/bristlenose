"""Narrow CLI wiring tests for `bristlenose pipeline`.

Behaviour-level dispatch is covered by test_render.py — these tests confirm the
Typer command exists, parses --json / --stage, and exits non-zero for unknown
stages.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from bristlenose.cli import app

runner = CliRunner()


def test_pipeline_command_exits_zero() -> None:
    result = runner.invoke(app, ["pipeline"])
    assert result.exit_code == 0
    assert "Transcription" in result.output


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
