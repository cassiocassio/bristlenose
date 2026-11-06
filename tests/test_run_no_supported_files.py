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
    # Files in a format we never offered are left alone, not refused (6 Nov 2026),
    # so a folder of only those reads as the empty folder it is to Bristlenose.
    assert "No supported files found" in result.output, result.output
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
def test_a_folder_of_only_unoffered_formats_is_left_alone_not_refused(
    runner, tmp_path: Path, command: str
) -> None:
    """The files a folder holds in formats we never offered are not named as refusals.

    `guide.pdf` and `notes.xlsx` were never going to be analysed, so nothing is
    missing: they are counted on `summary.ingest.left_alone` and appear in no
    `failed` row, no "not analysed" line and no "Partial completion". The run still
    stops, with the empty-folder line, because there was nothing to read.
    """
    input_dir = tmp_path / "interviews"
    input_dir.mkdir()
    for name in ("guide.pdf", "notes.xlsx"):
        (input_dir / name).write_text("x", encoding="utf-8")

    args = [command, str(input_dir)] + (["--no-serve"] if command == "run" else [])
    result = runner.invoke(app, args)

    assert result.exit_code == 1, result.output
    assert "not analysed" not in result.output, result.output
    assert "No supported files found" in result.output, result.output
    terminus = _terminus(input_dir)
    assert terminus["cause"]["message"] == "No supported files found in input directory."
    ingest = terminus["summary"]["ingest"]
    assert ingest is not None
    assert ingest["failed"] == [], ingest
    assert ingest["left_alone"] == 2, ingest


def test_strays_beside_a_real_session_are_counted_and_do_not_make_the_run_partial(
    runner, tmp_path: Path
) -> None:
    """The Talismanic case end to end: one readable session plus stray files.

    `transcribe` reads the `.vtt`, finds nothing it refused, and the terminus carries
    the strays as a count. Deleting `left_alone=` from the call that follows a
    successful ingest, or letting a stray into `failed`, fails this (6 Nov 2026).
    """
    input_dir = tmp_path / "interviews"
    input_dir.mkdir()
    (input_dir / "p1.vtt").write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:04.000\n<v Moderator>How did you find it?\n\n"
        "00:00:05.000 --> 00:00:09.000\n<v Participant>I could not find the save button.\n",
        encoding="utf-8",
    )
    for name in ("build.py", "notes.txt", "labels.xlsx"):
        (input_dir / name).write_text("x", encoding="utf-8")

    result = runner.invoke(app, ["transcribe", str(input_dir)])

    assert result.exit_code == 0, result.output
    assert "not analysed" not in result.output, result.output
    terminus = _terminus(input_dir)
    ingest = terminus["summary"]["ingest"]
    assert terminus["event"] == "run_completed", terminus
    assert ingest["failed"] == [], ingest
    assert ingest["left_alone"] == 3, ingest
