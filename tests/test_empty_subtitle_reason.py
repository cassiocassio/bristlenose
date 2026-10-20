"""An empty or unreadable subtitle file is said to be that, not "nothing was said" (R117).

A subtitle that parsed to no segments reached the pipeline as a session with no
words, and the silent-recording rule stated it as `NO_SPEECH`, "No speech found —
nothing was said in this recording". For a 0-byte file, a header-only VTT or a
text file wearing a .srt extension that is false: the file held nothing, or was
not a subtitle file. These now take the existing `EMPTY` and `UNREADABLE`
reasons. A file with cues and no words still reads as nothing said.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bristlenose.events import CauseCategoryEnum, UnusableReason
from bristlenose.models import FileType, InputFile, InputSession

_T0 = datetime(2026, 10, 20, tzinfo=timezone.utc)


def _gather(path: Path, kind: FileType):
    from bristlenose.config import BristlenoseSettings
    from bristlenose.pipeline import Pipeline

    f = InputFile(path=path, file_type=kind, created_at=_T0, size_bytes=path.stat().st_size)
    session = InputSession(
        session_id="s1", session_number=1, participant_id="p1", participant_number=1,
        files=[f], has_existing_transcript=True, session_date=_T0,
    )
    pipeline = Pipeline(BristlenoseSettings(skip_transcription=True))
    return asyncio.run(pipeline._gather_all_segments([session]))


@pytest.mark.parametrize("name, data, reason", [
    ("empty.srt", b"", UnusableReason.EMPTY),
    ("header-only.vtt", b"WEBVTT\n\n", UnusableReason.EMPTY),
    ("notes.srt", b"Interview notes, not subtitles.\nSee the recording.\n", UnusableReason.UNREADABLE),
])
def test_a_subtitle_with_nothing_in_it_is_refused_by_the_right_name(
    tmp_path: Path, name: str, data: bytes, reason: UnusableReason,
) -> None:
    path = tmp_path / name
    path.write_bytes(data)
    kind = FileType.SUBTITLE_VTT if name.endswith(".vtt") else FileType.SUBTITLE_SRT
    segments, outcome = _gather(path, kind)
    assert segments == {}
    (failure,) = outcome.failed
    assert failure.cause.category == CauseCategoryEnum.UNUSABLE_INPUT
    assert failure.cause.reason == reason
    assert failure.source_file == name
    assert failure.session_id == "s1"


def test_cues_with_no_words_are_still_nothing_said(tmp_path: Path) -> None:
    """Timed cues whose text is empty: the file was read, and nothing was said."""
    path = tmp_path / "quiet.srt"
    path.write_bytes(b"1\n00:00:01,000 --> 00:00:02,000\n \n\n")
    segments, outcome = _gather(path, FileType.SUBTITLE_SRT)
    assert segments == {}
    assert outcome.failed == []
