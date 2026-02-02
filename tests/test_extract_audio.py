"""Tests for Stage 2 audio extraction — platform transcript skip."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from bristlenose.models import FileType, InputFile, InputSession
from bristlenose.stages.extract_audio import extract_audio_for_sessions


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
        "bristlenose.stages.extract_audio._extract_one",
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
        "bristlenose.stages.extract_audio._extract_one",
        new_callable=AsyncMock,
    ) as mock_extract:
        await extract_audio_for_sessions([session], tmp_path)
    mock_extract.assert_called_once()
