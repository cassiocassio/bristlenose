"""`transcribe` and `analyze` give up the way `run` does: one line, no traceback (R121).

When a whole stage fails the pipeline raises `PipelineAbandonedError`. `run`
has always caught it and printed `_print_pipeline_failure`'s banner; the other
two commands let it escape, so typer printed some sixty lines of traceback
beneath an out-of-credit or rate-limited stop.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from bristlenose.cli import app
from bristlenose.events import Cause, CauseCategoryEnum, PipelineAbandonedError, PipelineSummary


@pytest.fixture
def cli_to_pipeline(monkeypatch):
    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", lambda s: None)
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None)
    return CliRunner()


def _abandon(*_a, **_k):
    raise PipelineAbandonedError(
        cause=Cause(category=CauseCategoryEnum.QUOTA, message="quote_extraction failed"),
        summary=PipelineSummary(),
    )


async def _abandon_async(*a, **k):
    _abandon()


def _assert_one_banner(result, verb: str, folder: str) -> None:
    assert result.exit_code == 1, result.output
    assert isinstance(result.exception, SystemExit), repr(result.exception)
    assert "Traceback" not in result.output
    assert "Rate-limited by" in result.output
    assert f"bristlenose {verb} {folder}/" in result.output


def test_analyze_prints_the_banner(cli_to_pipeline, tmp_path: Path, monkeypatch) -> None:
    transcripts = tmp_path / "transcripts-raw"
    transcripts.mkdir()
    (transcripts / "s1.txt").write_text("# Transcript: s1\n", encoding="utf-8")
    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run_analysis_only", _abandon_async)
    result = cli_to_pipeline.invoke(app, ["analyze", str(transcripts), "--llm", "claude"])
    _assert_one_banner(result, "analyze", "transcripts-raw")


def test_transcribe_prints_the_banner(cli_to_pipeline, tmp_path: Path, monkeypatch) -> None:
    interviews = tmp_path / "interviews"
    interviews.mkdir()
    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run_transcription_only", _abandon_async)
    result = cli_to_pipeline.invoke(app, ["transcribe", str(interviews)])
    _assert_one_banner(result, "transcribe", "interviews")
