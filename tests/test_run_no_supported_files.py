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
    # An empty folder keeps its line; one with refused files names them and
    # then says nothing in it could be analysed (decision #81).
    expected = "No analysable interviews found." if contents else "No supported files found"
    assert expected in result.output, result.output
    terminus = _terminus(input_dir)
    assert terminus["event"] == "run_failed", terminus
    assert terminus["cause"]["category"] == "missing_input", terminus


def test_analyze_on_a_folder_with_no_transcripts_fails_rather_than_finishing(
    runner, tmp_path: Path
) -> None:
    """The same class on `analyze`: an empty transcripts folder ended "Done"."""
    transcripts = tmp_path / "transcripts-raw"
    transcripts.mkdir()
    out_dir = tmp_path / "out"

    result = runner.invoke(app, ["analyze", str(transcripts), "-o", str(out_dir)])

    assert result.exit_code == 1, result.output
    assert "Done" not in result.output, result.output
    assert "No transcript files found" in result.output
    events = out_dir / ".bristlenose" / "pipeline-events.jsonl"
    terminus = json.loads(events.read_text(encoding="utf-8").splitlines()[-1])
    assert terminus["event"] == "run_failed", terminus
    assert terminus["cause"]["category"] == "missing_input", terminus


@pytest.mark.parametrize("command", ["run", "transcribe"])
def test_a_folder_of_only_declined_files_names_each_one(
    runner, tmp_path: Path, command: str
) -> None:
    """The run-side twin of R119: the files it declined went unnamed.

    Ingest found nothing to analyse and the run stopped before the files
    bucket was written, so `guide.pdf` and `notes.xlsx` were never said, in
    the terminal or in `summary.ingest`. They are named with the existing
    refusal reason, as when a run goes ahead beside them.
    """
    input_dir = tmp_path / "interviews"
    input_dir.mkdir()
    for name in ("guide.pdf", "notes.xlsx"):
        (input_dir / name).write_text("x", encoding="utf-8")

    args = [command, str(input_dir)] + (["--no-serve"] if command == "run" else [])
    result = runner.invoke(app, args)

    assert result.exit_code == 1, result.output
    # The scan's own log lines named them already; the refusal block is the
    # summary a run that goes ahead prints, and what the Mac reads.
    assert "2 files not analysed" in result.output, result.output
    assert "guide.pdf — Not a format Bristlenose reads." in result.output, result.output
    assert "notes.xlsx — Not a format Bristlenose reads." in result.output, result.output
    # Not "No supported files found." straight after naming two (decision #81).
    assert "No supported files found" not in result.output, result.output
    assert "No analysable interviews found." in result.output, result.output
    assert _terminus(input_dir)["cause"]["message"] == "No analysable interviews found."
    ingest = _terminus(input_dir)["summary"]["ingest"]
    assert ingest is not None
    assert ingest["succeeded"] == 0, ingest
    assert sorted(
        (f["source_file"], f["cause"]["category"], f["cause"]["reason"]) for f in ingest["failed"]
    ) == [
        ("guide.pdf", "unusable_input", "unsupported_format"),
        ("notes.xlsx", "unusable_input", "unsupported_format"),
    ]
