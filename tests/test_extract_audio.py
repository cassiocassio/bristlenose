"""Tests for Stage 2 audio extraction — platform transcript skip + fail-loud."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bristlenose.models import FileType, InputFile, InputSession
from bristlenose.stages.s02_extract_audio import extract_audio_for_sessions
from bristlenose.utils.audio import AudioToolError, has_audio_stream


def _ffprobe_result(returncode: int, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    """Stand-in for the CompletedProcess returned by subprocess.run."""
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def _session(
    *,
    has_transcript: bool = False,
    has_video: bool = True,
) -> InputSession:
    """Build a minimal InputSession for testing."""
    files: list[InputFile] = []
    if has_video:
        files.append(
            InputFile(
                path=Path("/input/recording.mp4"),
                file_type=FileType.VIDEO,
                created_at=datetime(2026, 1, 15, 14, 0, 0, tzinfo=timezone.utc),
                size_bytes=100_000_000,
            )
        )
    if has_transcript:
        files.append(
            InputFile(
                path=Path("/input/recording.vtt"),
                file_type=FileType.SUBTITLE_VTT,
                created_at=datetime(2026, 1, 15, 14, 0, 0, tzinfo=timezone.utc),
                size_bytes=5000,
            )
        )
    return InputSession(
        session_id="s1",
        session_number=1,
        participant_id="p1",
        participant_number=1,
        files=files,
        has_existing_transcript=has_transcript,
        session_date=datetime(2026, 1, 15, 14, 0, 0, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_skips_extraction_when_transcript_exists(tmp_path: Path) -> None:
    """Audio extraction is skipped when session has a platform transcript."""
    session = _session(has_transcript=True, has_video=True)
    with patch(
        "bristlenose.stages.s02_extract_audio._extract_one",
        new_callable=AsyncMock,
    ) as mock_extract:
        result = await extract_audio_for_sessions([session], tmp_path)
    mock_extract.assert_not_called()
    assert result[0].audio_path is None


@pytest.mark.asyncio
async def test_extracts_audio_when_no_transcript(tmp_path: Path) -> None:
    """Audio extraction runs normally when no platform transcript."""
    session = _session(has_transcript=False, has_video=True)
    with patch(
        "bristlenose.stages.s02_extract_audio._extract_one",
        new_callable=AsyncMock,
    ) as mock_extract:
        await extract_audio_for_sessions([session], tmp_path)
    mock_extract.assert_called_once()


# ── has_audio_stream: tool error vs genuine no-audio ────────────────────────


def test_has_audio_stream_true_when_audio_present() -> None:
    """ffprobe exit 0 with an audio codec_type line → True."""
    with patch(
        "bristlenose.utils.audio.subprocess.run",
        return_value=_ffprobe_result(0, stdout="audio\n"),
    ):
        assert has_audio_stream(Path("/input/recording.mp4")) is True


def test_has_audio_stream_false_when_genuinely_silent() -> None:
    """ffprobe exit 0 with empty stdout → False (valid silent recording)."""
    with patch(
        "bristlenose.utils.audio.subprocess.run",
        return_value=_ffprobe_result(0, stdout=""),
    ):
        assert has_audio_stream(Path("/input/screen-capture.mp4")) is False


def test_has_audio_stream_raises_on_tool_error() -> None:
    """A non-zero ffprobe exit is a broken toolchain, NOT 'no audio stream'.

    This is the libblas-on-amd64 repro: ffprobe couldn't load a shared library,
    exited non-zero, and the old code read empty stdout as "no audio" and
    silently skipped transcription. It must fail loud instead.
    """
    stderr = (
        "ffprobe: error while loading shared libraries: libblas.so.3: "
        "cannot open shared object file: No such file or directory"
    )
    with patch(
        "bristlenose.utils.audio.subprocess.run",
        return_value=_ffprobe_result(127, stdout="", stderr=stderr),
    ):
        with pytest.raises(AudioToolError) as excinfo:
            has_audio_stream(Path("/input/recording.mp4"))
    # The failure reason must survive for diagnosis.
    assert "libblas.so.3" in str(excinfo.value)


def test_has_audio_stream_raises_when_binary_missing() -> None:
    """A missing ffprobe binary must fail loud, not degrade to 'no audio'."""
    with patch(
        "bristlenose.utils.audio.subprocess.run",
        side_effect=FileNotFoundError(2, "No such file or directory", "ffprobe"),
    ):
        with pytest.raises(AudioToolError):
            has_audio_stream(Path("/input/recording.mp4"))


def test_has_audio_stream_raises_on_timeout() -> None:
    """An ffprobe timeout must fail loud, not degrade to 'no audio'."""
    with patch(
        "bristlenose.utils.audio.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="ffprobe", timeout=30),
    ):
        with pytest.raises(AudioToolError):
            has_audio_stream(Path("/input/recording.mp4"))


# ── Stage 2: a tool error aborts the run (no fake success) ──────────────────


@pytest.mark.asyncio
async def test_tool_error_propagates_and_aborts(tmp_path: Path) -> None:
    """A broken toolchain must abort the run, not silently skip the video.

    Regression guard for the empty-but-'successful' report class: when
    has_audio_stream raises AudioToolError, extract_audio_for_sessions must
    propagate it (→ run_lifecycle records a RunFailedEvent) rather than
    swallowing it and leaving the session with no audio_path.
    """
    session = _session(has_transcript=False, has_video=True)
    with patch(
        "bristlenose.stages.s02_extract_audio.has_audio_stream",
        MagicMock(side_effect=AudioToolError("ffprobe broke: libblas.so.3 missing")),
    ):
        with pytest.raises(AudioToolError):
            await extract_audio_for_sessions([session], tmp_path)


@pytest.mark.asyncio
async def test_genuine_no_audio_stream_skips_without_aborting(tmp_path: Path) -> None:
    """A video that genuinely has no audio is skipped, and the run continues."""
    session = _session(has_transcript=False, has_video=True)
    with patch(
        "bristlenose.stages.s02_extract_audio.has_audio_stream",
        MagicMock(return_value=False),
    ):
        result = await extract_audio_for_sessions([session], tmp_path)
    assert result[0].audio_path is None
