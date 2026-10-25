"""The first run after an install or upgrade honours --skip-transcription (N152).

``_maybe_auto_doctor`` ran the full ``run`` preflight, FFmpeg and Whisper
included, without the ``skip_transcription`` the every-run preflight passes. On a
transcripts-only workflow (Teams ``.docx``/``.vtt``) with no FFmpeg it stopped the
run, and since the sentinel is written only on a pass, every later run stopped the
same way until the researcher ran ``bristlenose doctor``.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import typer

from bristlenose import cli
from bristlenose.config import load_settings
from bristlenose.doctor import CheckResult, CheckStatus


def _ok(label: str) -> CheckResult:
    return CheckResult(status=CheckStatus.OK, label=label, detail="stub")


@pytest.fixture()
def no_ffmpeg(monkeypatch: pytest.MonkeyPatch):
    """Every check passes except FFmpeg; the sentinel write is recorded."""
    fail = CheckResult(
        status=CheckStatus.FAIL, label="FFmpeg", detail="not found (stub)", fix_key="ffmpeg_missing"
    )
    written: list[bool] = []
    with (
        patch("bristlenose.doctor.check_ffmpeg", return_value=fail),
        patch("bristlenose.doctor.check_backend", return_value=_ok("Transcription")),
        patch("bristlenose.doctor.check_whisper_model", return_value=_ok("Whisper model")),
        patch("bristlenose.doctor.check_api_key", return_value=_ok("API key")),
        patch("bristlenose.doctor.check_network", return_value=_ok("Network")),
        patch("bristlenose.doctor.check_pii", return_value=_ok("PII")),
        patch("bristlenose.doctor.check_disk_space", return_value=_ok("Disk")),
        patch("bristlenose.doctor.check_serve_deps", return_value=_ok("Serve")),
    ):
        monkeypatch.setattr(cli, "_should_auto_doctor", lambda: True)
        monkeypatch.setattr(cli, "_write_doctor_sentinel", lambda: written.append(True))
        yield written


def test_a_transcripts_only_first_run_does_not_need_ffmpeg(no_ffmpeg: list[bool]) -> None:
    settings = load_settings(skip_transcription=True)
    assert cli._maybe_auto_doctor(settings, "run") is True
    assert no_ffmpeg == [True], "a pass writes the sentinel, so the next run is not doctored"


def test_a_first_run_that_transcribes_still_needs_ffmpeg(no_ffmpeg: list[bool]) -> None:
    settings = load_settings(skip_transcription=False)
    with pytest.raises(typer.Exit) as stopped:
        cli._maybe_auto_doctor(settings, "run")
    assert stopped.value.exit_code == 1
    assert no_ffmpeg == []
