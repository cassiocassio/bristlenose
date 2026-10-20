"""A folder with nothing Bristlenose can read is a failed run, not "Done" (R116).

`run` on an empty folder, or one holding only unsupported files, printed "No
supported files found." and then "✓ Done.", exited 0 and wrote `run_completed`,
so the Mac app showed an empty report as a finished analysis. `transcribe` has
always stopped there with `MISSING_INPUT`; `run` now takes the same path.

Drives the real CLI and the real `Pipeline.run` — ingest finds nothing, so no
stage past it, and no LLM, is reached.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bristlenose.cli import app


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", lambda s: None)
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None)
    return CliRunner()


def _terminus(input_dir: Path) -> dict:
    events = input_dir / "bristlenose-output" / ".bristlenose" / "pipeline-events.jsonl"
    lines = [json.loads(ln) for ln in events.read_text(encoding="utf-8").splitlines() if ln]
    return lines[-1]


@pytest.mark.parametrize("contents", [{}, {"guide.pdf": "x", "notes.xlsx": "y"}])
def test_a_folder_with_nothing_to_read_fails_rather_than_finishing(
    runner, tmp_path: Path, contents: dict[str, str]
) -> None:
    input_dir = tmp_path / "interviews"
    input_dir.mkdir()
    for name, text in contents.items():
        (input_dir / name).write_text(text, encoding="utf-8")

    result = runner.invoke(app, ["run", str(input_dir), "--no-serve"])

    assert result.exit_code == 1, result.output
    assert "Done" not in result.output, result.output
    assert "No supported files found" in result.output
    terminus = _terminus(input_dir)
    assert terminus["event"] == "run_failed", terminus
    assert terminus["cause"]["category"] == "missing_input", terminus
