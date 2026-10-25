"""A zero-byte audio file is named as empty at stage 2, as a zero-byte video is (N171).

An audio file was used as-is and never probed, so an empty ``.m4a`` reached Whisper,
failed there, was reported as "transcription failed" and was retried on every run.
The same file as a video was named as empty and set aside.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from bristlenose.events import UnusableReason
from bristlenose.models import FileType, InputFile, InputSession
from bristlenose.stages.s02_extract_audio import extract_audio_for_sessions


def _session(n: int, path: Path, size: int) -> InputSession:
    when = datetime(2026, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
    return InputSession(
        session_id=f"s{n}",
        session_number=n,
        participant_id=f"p{n}",
        participant_number=n,
        files=[InputFile(path=path, file_type=FileType.AUDIO, created_at=when, size_bytes=size)],
        session_date=when,
    )


@pytest.mark.asyncio
async def test_an_empty_audio_file_is_set_aside_as_empty_and_the_other_session_goes_on(
    tmp_path: Path,
) -> None:
    empty = tmp_path / "interview1.m4a"
    empty.write_bytes(b"")
    whole = tmp_path / "interview2.m4a"
    whole.write_bytes(b"not really audio, but not empty")
    sessions = [_session(1, empty, 0), _session(2, whole, whole.stat().st_size)]

    out = await extract_audio_for_sessions(sessions, tmp_path / "tmp")

    assert out[0].audio_path is None
    assert [f.error for f in out[0].files] == [UnusableReason.EMPTY.value]
    assert out[1].audio_path == whole
    assert [f.error for f in out[1].files] == [None]


@pytest.mark.asyncio
async def test_a_missing_audio_file_is_not_called_empty(tmp_path: Path) -> None:
    """stat failing says nothing about the file's size; the claim needs the fact."""
    gone = tmp_path / "gone.m4a"
    out = await extract_audio_for_sessions([_session(1, gone, 5)], tmp_path / "tmp")
    assert [f.error for f in out[0].files] == [None]
    assert out[0].audio_path == gone
