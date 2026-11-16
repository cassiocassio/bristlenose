"""BR-27: a headless `run` must not start the report server; `--no-serve` is in --help.

`run` ended by serving the report and blocking until Ctrl-C. From cron, a pipe or CI
that never exits. With no terminal on stdin/stdout the run now prints its summary and
returns; an interactive run still serves, and `--no-serve` opts out of that.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from bristlenose.cli import app


class _Result(SimpleNamespace):
    """Any attribute the tail reads that is not set is None."""

    def __getattr__(self, name: str):
        return None


@pytest.fixture
def tail(monkeypatch, tmp_path: Path):
    """Run to the end of `run` with a fake pipeline; record what the tail did."""
    monkeypatch.setattr("bristlenose.cli._print_header", lambda *a, **k: None)
    monkeypatch.setattr("bristlenose.cli._build_estimator", lambda *a, **k: (None, None))
    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", lambda s: None)
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None)

    async def fake_run(self, *a, **k):
        return _Result(llm_calls=1, total_quotes=3, sessions=[])

    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", fake_run)
    served: list[Path] = []
    monkeypatch.setattr("bristlenose.cli._start_server", lambda p, **k: served.append(p))
    monkeypatch.setattr("bristlenose.cli._find_open_port", lambda: 8150)
    monkeypatch.setattr("bristlenose.cli._print_pipeline_summary", lambda *a, **k: None)
    input_dir = tmp_path / "interviews"
    input_dir.mkdir()
    return input_dir, served


def _invoke(input_dir: Path, *extra: str):
    result = CliRunner().invoke(app, ["run", str(input_dir), *extra])
    assert result.exit_code == 0, result.output
    return result


def test_a_headless_run_does_not_start_the_server(monkeypatch, tail) -> None:
    input_dir, served = tail
    monkeypatch.setattr("bristlenose.cli._stdin_is_a_terminal", lambda: False)
    _invoke(input_dir)
    assert served == []


def test_an_interactive_run_still_serves(monkeypatch, tail) -> None:
    input_dir, served = tail
    monkeypatch.setattr("bristlenose.cli._stdin_is_a_terminal", lambda: True)
    _invoke(input_dir)
    assert len(served) == 1


def test_no_serve_skips_the_server_even_with_a_terminal(monkeypatch, tail) -> None:
    input_dir, served = tail
    monkeypatch.setattr("bristlenose.cli._stdin_is_a_terminal", lambda: True)
    _invoke(input_dir, "--no-serve")
    assert served == []


def test_no_serve_is_listed_in_run_help() -> None:
    result = CliRunner().invoke(app, ["run", "--help"], env={"COLUMNS": "200"})
    assert "--no-serve" in result.output
