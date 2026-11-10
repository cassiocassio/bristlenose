"""`bristlenose transcribe` counts the sessions that transcribed, not every session.

The step line read ``Transcribed {len(sessions)}``, so with one of two
recordings failing it said "Transcribed 2 sessions" while the summary it had
just built knew one had failed. The seam is ``_gather_all_segments``, as in
``test_transcribe_only_speaker_codes.py``.
"""

from __future__ import annotations

import asyncio
import io
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from rich.console import Console

from bristlenose.events import Cause, CauseCategoryEnum, StageFailure, StageOutcome
from bristlenose.models import FileType, InputFile, InputSession, TranscriptSegment
from bristlenose.pipeline import Pipeline


def _sessions(input_dir: Path, n: int) -> list[InputSession]:
    out = []
    for i in range(1, n + 1):
        media = input_dir / f"rec{i}.wav"
        media.write_bytes(b"fake " + media.name.encode())  # its own bytes: identical files fold
        out.append(InputSession(
            session_id=f"s{i}", session_number=i,
            participant_id=f"p{i}", participant_number=i,
            session_date=datetime.now(timezone.utc),
            files=[InputFile(
                path=media, file_type=FileType.AUDIO,
                created_at=datetime.now(timezone.utc), size_bytes=4,
                duration_seconds=60.0,
            )],
            audio_path=media,
        ))
    return out


def _interview() -> list[TranscriptSegment]:
    lines = [
        ("Mod", "Thanks for joining. Can you tell me about the last time you shopped?"),
        ("Ann", "I went to the store on Saturday and could not find the checkout at all."),
        ("Mod", "What happened next?"),
        ("Ann", "Someone pointed me to the back of the shop and I gave up."),
    ]
    return [
        TranscriptSegment(
            segment_index=i, start_time=float(i * 10), end_time=float(i * 10 + 9),
            text=text, speaker_label=label,
        )
        for i, (label, text) in enumerate(lines)
    ]


def test_a_failed_session_is_not_counted_as_transcribed(tmp_path: Path) -> None:
    settings = MagicMock()
    settings.project_name = "count"
    settings.write_intermediate = False
    settings.color_scheme = "default"
    settings.whisper_language = None
    pipeline = Pipeline(settings)

    input_dir = tmp_path / "in"
    input_dir.mkdir()
    sessions = _sessions(input_dir, 2)

    async def _fake_gather(_self, _sessions, **_kw):
        # s1 transcribes; s2's Whisper call raised.
        failure = StageFailure(session_id="s2", cause=Cause(
            category=CauseCategoryEnum.WHISPER, message="decoder failed",
            stage="s05_transcribe", session_id="s2",
        ))
        return {"s1": _interview()}, StageOutcome(attempted=2, succeeded=1, failed=[failure])

    async def _passthrough(sess, _tmp, **_kw):
        return sess

    buf = io.StringIO()
    console = Console(file=buf, width=120, force_terminal=False, color_system=None)
    with (
        patch("bristlenose.stages.s01_ingest.ingest", return_value=sessions),
        patch(
            "bristlenose.stages.s02_extract_audio.extract_audio_for_sessions",
            new=_passthrough,
        ),
        patch.object(Pipeline, "_gather_all_segments", new=_fake_gather),
        patch("bristlenose.pipeline.console", console),
    ):
        result = asyncio.run(pipeline.run_transcription_only(input_dir, tmp_path / "out"))

    assert result.summary.transcripts.succeeded == 1
    out = buf.getvalue()
    assert "Transcribed 1 session " in out, out
    assert "Transcribed 2 sessions" not in out, out


def test_an_unreadable_people_file_is_on_the_transcribe_end_line_too(tmp_path: Path) -> None:
    """N82 covers ``transcribe`` as well: it reads people.yaml, warns mid-run and
    carries on without the names, so its end line must not be a plain Done."""
    settings = MagicMock()
    settings.project_name = "count"
    settings.write_intermediate = False
    settings.color_scheme = "default"
    settings.whisper_language = None
    pipeline = Pipeline(settings)

    input_dir = tmp_path / "in"
    input_dir.mkdir()
    sessions = _sessions(input_dir, 1)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "people.yaml").write_text("participants: [\n", encoding="utf-8")

    async def _fake_gather(_self, _sessions, **_kw):
        return {"s1": _interview()}, StageOutcome(attempted=1, succeeded=1, failed=[])

    async def _passthrough(sess, _tmp, **_kw):
        return sess

    buf = io.StringIO()
    console = Console(file=buf, width=120, force_terminal=False, color_system=None)
    with (
        patch("bristlenose.stages.s01_ingest.ingest", return_value=sessions),
        patch(
            "bristlenose.stages.s02_extract_audio.extract_audio_for_sessions",
            new=_passthrough,
        ),
        patch.object(Pipeline, "_gather_all_segments", new=_fake_gather),
        patch("bristlenose.pipeline.console", console),
    ):
        result = asyncio.run(pipeline.run_transcription_only(input_dir, out_dir))

    assert "people.yaml couldn't be read" in buf.getvalue()
    assert result.pipeline_warning == "people.yaml couldn't be read"
