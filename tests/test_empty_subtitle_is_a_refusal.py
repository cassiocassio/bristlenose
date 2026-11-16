"""A 0-byte subtitle file is stated as an empty file, not as "MalformedFileError".

The parser raises on a file with nothing in it, so the zero-segment reason
(`empty_subtitle_reason`) never applied. Found on a 0.46.0 walk (16 Nov 2026).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from bristlenose.events import CauseCategoryEnum
from bristlenose.models import FileType, InputFile, InputSession
from bristlenose.refusals import UnusableReason

_T0 = datetime(2026, 9, 22)


def _gather(path: Path):
    from bristlenose.config import BristlenoseSettings
    from bristlenose.pipeline import Pipeline

    f = InputFile(path=path, file_type=FileType.SUBTITLE_VTT, created_at=_T0,
                  size_bytes=path.stat().st_size)
    session = InputSession(
        session_id="s2", session_number=2, participant_id="p2", participant_number=2,
        files=[f], has_existing_transcript=True, session_date=_T0,
    )
    pipeline = Pipeline(BristlenoseSettings(skip_transcription=True))
    return asyncio.run(pipeline._gather_all_segments([session]))


def test_a_zero_byte_vtt_is_empty(tmp_path: Path) -> None:
    path = tmp_path / "02 empty.vtt"
    path.write_bytes(b"")
    segments, outcome = _gather(path)
    assert segments == {}
    (failure,) = outcome.failed
    assert failure.cause.category == CauseCategoryEnum.UNUSABLE_INPUT
    assert failure.cause.reason == UnusableReason.EMPTY
    assert failure.source_file == "02 empty.vtt"
    assert "MalformedFileError" not in (failure.cause.message or "")


def test_control_a_vtt_with_cues_still_parses(tmp_path: Path) -> None:
    path = tmp_path / "ok.vtt"
    path.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello there\n", encoding="utf-8")
    segments, outcome = _gather(path)
    assert outcome.failed == []
    assert segments["s2"]
