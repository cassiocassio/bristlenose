"""CLI honesty fixes from the 16 Nov 2026 bug campaign, cluster C (BR-24, 25, 26, 33).

* BR-26: `status` / `serve` on a folder that does not exist say so, instead of
  suggesting `bristlenose run` on it (status) or raising a traceback (serve).
* BR-33: `bristlenose help` lists every command `bristlenose --help` lists.
* BR-24: a failed run says "no supported files" once, not also as raw log lines.
* BR-25: a transcript-only folder is not told audio was extracted or transcribed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from bristlenose.cli import app
from bristlenose.logging import release_log_file, setup_logging


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", lambda s: None)
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None)
    return CliRunner()


# ── BR-26 ────────────────────────────────────────────────────────────


def test_status_on_a_missing_folder_does_not_suggest_running_it(
    runner, tmp_path: Path
) -> None:
    result = runner.invoke(app, ["status", str(tmp_path / "typo")])
    out = " ".join(result.output.split())
    assert result.exit_code == 1, out
    assert "doesn't exist" in out, out
    assert "bristlenose run" not in out, out


def test_status_on_a_real_folder_with_nothing_still_suggests_running_it(
    runner, tmp_path: Path
) -> None:
    """Control: the guidance is right for a folder that exists."""
    result = runner.invoke(app, ["status", str(tmp_path)])
    out = " ".join(result.output.split())
    assert result.exit_code == 1, out
    assert "No pipeline data found" in out and "bristlenose run" in out, out


def test_status_on_a_file_says_it_is_not_a_folder(runner, tmp_path: Path) -> None:
    f = tmp_path / "notes.txt"
    f.write_text("x", encoding="utf-8")
    result = runner.invoke(app, ["status", str(f)])
    assert result.exit_code == 1, result.output
    assert "is not a folder" in " ".join(result.output.split()), result.output


def test_serve_on_a_missing_folder_is_a_plain_refusal_not_a_traceback(
    runner, tmp_path: Path
) -> None:
    result = runner.invoke(app, ["serve", str(tmp_path / "typo"), "--no-open"])
    assert result.exit_code == 1, result.output
    assert "Traceback" not in result.output, result.output
    assert "doesn't exist" in " ".join(result.output.split()), result.output


# ── BR-33 ────────────────────────────────────────────────────────────


def _visible_commands() -> set[str]:
    group: Any = typer.main.get_command(app)
    return {n for n, c in group.commands.items() if not c.hidden}


def test_help_overview_lists_every_visible_command(runner) -> None:
    out = runner.invoke(app, ["help"]).output
    table = out.split("Commands\n", 1)[1].split("\n\n", 1)[0]
    listed = {line.split()[0] for line in table.splitlines() if line.strip()}
    assert _visible_commands() <= listed, sorted(_visible_commands() - listed)


def test_help_commands_describes_every_visible_command(runner) -> None:
    """`help commands` is a hand-written table: a command it lacks is silently absent."""
    out = runner.invoke(app, ["help", "commands"]).output
    missing = {c for c in _visible_commands() - {"help"} if f"bristlenose {c}" not in out}
    assert not missing, sorted(missing)


def test_help_topic_for_each_visible_command_is_a_known_topic(runner) -> None:
    """`help <command>` must not answer "Unknown topic" for a listed command."""
    for name in sorted(_visible_commands() - {"help"}):
        out = runner.invoke(app, ["help", name]).output
        assert "Unknown topic" not in out, name


# ── BR-24 ────────────────────────────────────────────────────────────


def test_a_file_only_record_reaches_the_log_but_not_the_terminal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    try:
        setup_logging(output_dir=tmp_path, verbose=False)
        log = logging.getLogger("bristlenose.stages.s01_ingest")
        log.warning("shown on the terminal")
        log.warning("only in the file", extra={"file_only": True})
        logging.getLogger("bristlenose").error("run_abandoned run_id=x category=missing_input")
        for h in logging.getLogger().handlers:
            h.flush()
        err = capsys.readouterr().err
        assert "shown on the terminal" in err  # control: warnings still reach the terminal
        assert "only in the file" not in err, err
        assert "run_abandoned" not in err, err
        text = (tmp_path / ".bristlenose" / "bristlenose.log").read_text(encoding="utf-8")
        assert "only in the file" in text and "run_abandoned" in text
    finally:
        release_log_file()


def test_an_empty_folder_failure_names_no_absolute_path_on_the_terminal(
    runner, tmp_path: Path
) -> None:
    input_dir = tmp_path / "interviews"
    input_dir.mkdir()
    result = runner.invoke(app, ["transcribe", str(input_dir)])
    assert result.exit_code == 1, result.output
    assert "No supported files found" in result.output
    assert str(tmp_path) not in result.output, result.output
    assert "WARNING |" not in result.output and "ERROR |" not in result.output, result.output
    release_log_file()


# ── BR-25 ────────────────────────────────────────────────────────────


def test_a_transcript_only_folder_does_not_claim_audio_was_extracted(
    runner, tmp_path: Path
) -> None:
    input_dir = tmp_path / "interviews"
    input_dir.mkdir()
    (input_dir / "p1.vtt").write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:05.000\nSpeaker: Hello there how are you today\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["transcribe", str(input_dir)])
    out = " ".join(result.output.split())
    release_log_file()
    assert "Read 1 session" in out, out
    assert "Extracted audio" not in out, out
    assert "Transcribed" not in out, out


def _session(*, recording: bool, transcript: bool):
    from datetime import datetime, timezone

    from bristlenose.models import FileType, InputFile, InputSession

    files = [
        InputFile(
            path=Path("rec.mp4"), file_type=FileType.VIDEO,
            created_at=datetime.now(timezone.utc), size_bytes=1,
        )
    ] if recording else []
    return InputSession(
        session_id="s1", session_number=1, participant_id="p1", participant_number=1,
        session_date=datetime.now(timezone.utc), files=files,
        has_existing_transcript=transcript,
    )


def test_a_video_beside_its_own_transcript_is_not_transcribed() -> None:
    """Teams and Zoom exports: video plus .vtt. Whisper and ffmpeg never run."""
    from bristlenose.pipeline import _any_recording, _transcribed_verb

    with_transcript = [_session(recording=True, transcript=True)]
    assert not _any_recording(with_transcript)
    assert _transcribed_verb(with_transcript) == "Read"
    # control: a bare recording is transcribed
    bare = [_session(recording=True, transcript=False)]
    assert _any_recording(bare) and _transcribed_verb(bare) == "Transcribed"
