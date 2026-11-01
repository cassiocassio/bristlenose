"""`analyze` that yields no quotes exits 1 (N151, owner ruling 1 Nov 2026).

It printed "Finished with errors - 0 quotes extracted" and exited 0, so a script or the Mac
host read a run that produced nothing as a success. The line is unchanged (no new words);
the exit code is what a caller reads.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from bristlenose.cli import app


@pytest.fixture
def cli_to_pipeline(monkeypatch):
    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", lambda s: None)
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None)
    return CliRunner()


def _result(*, llm_calls: int, total_quotes: int) -> SimpleNamespace:
    return SimpleNamespace(
        participants=[], screen_clusters=[], theme_groups=[], total_quotes=total_quotes,
        llm_calls=llm_calls, llm_input_tokens=0, llm_output_tokens=0, llm_model="m",
        llm_provider="anthropic", elapsed_seconds=1.0, pipeline_warning="", pipeline_error="",
        pipeline_error_link="", summary=None,
    )


def _analyze(cli, tmp_path: Path, monkeypatch, result: SimpleNamespace):
    transcripts = tmp_path / "transcripts-raw"
    transcripts.mkdir()
    (transcripts / "s1.txt").write_text("# Transcript: s1\n", encoding="utf-8")

    async def fake(*_a, **_k):
        return result

    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run_analysis_only", fake)
    return cli.invoke(app, ["analyze", str(transcripts), "--llm", "claude"])


def test_a_run_that_extracted_no_quotes_exits_1_with_the_existing_line(
    cli_to_pipeline, tmp_path: Path, monkeypatch
) -> None:
    out = _analyze(cli_to_pipeline, tmp_path, monkeypatch, _result(llm_calls=3, total_quotes=0))
    assert "Finished with errors" in out.output and "0 quotes extracted" in out.output
    assert out.exit_code == 1, out.output


def test_a_run_with_quotes_still_exits_0(cli_to_pipeline, tmp_path: Path, monkeypatch) -> None:
    out = _analyze(cli_to_pipeline, tmp_path, monkeypatch, _result(llm_calls=3, total_quotes=4))
    assert out.exit_code == 0, out.output


def test_a_run_that_never_called_the_model_is_not_an_error(
    cli_to_pipeline, tmp_path: Path, monkeypatch
) -> None:
    # The summary's own rule: "finished with errors" is for a run whose LLM ran and found nothing.
    out = _analyze(cli_to_pipeline, tmp_path, monkeypatch, _result(llm_calls=0, total_quotes=0))
    assert out.exit_code == 0, out.output
