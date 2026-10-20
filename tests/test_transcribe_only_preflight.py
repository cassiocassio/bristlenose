"""`bristlenose transcribe` runs the Whisper preflight, gated as run() gates it.

Until 14 Oct 2026 only ``Pipeline.run`` called ``preflight_whisper``, so a first
``transcribe`` fetched the model inside the "Transcribing..." spinner with no
banner, no size and no progress (docs/design-cli-just-works.md, Debate 1).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from bristlenose.events import StageOutcome
from bristlenose.models import FileType, InputFile, InputSession, TranscriptSegment
from bristlenose.pipeline import Pipeline


def _session(input_dir: Path, i: int, *, has_transcript: bool) -> InputSession:
    media = input_dir / f"rec{i}.wav"
    media.write_bytes(b"fake " + media.name.encode())  # its own bytes: identical files fold (R49)
    return InputSession(
        session_id=f"s{i}", session_number=i,
        participant_id=f"p{i}", participant_number=i,
        session_date=datetime.now(timezone.utc),
        files=[InputFile(
            path=media, file_type=FileType.AUDIO,
            created_at=datetime.now(timezone.utc), size_bytes=4,
            duration_seconds=60.0,
        )],
        audio_path=media,
        has_existing_transcript=has_transcript,
    )


def _preflight_calls(tmp_path: Path, has_transcript: list[bool]) -> list[dict]:
    settings = MagicMock()
    settings.project_name = "preflight"
    settings.write_intermediate = False
    settings.color_scheme = "default"
    settings.no_fetch = False
    pipeline = Pipeline(settings)

    input_dir = tmp_path / "in"
    input_dir.mkdir()
    sessions = [
        _session(input_dir, i, has_transcript=h)
        for i, h in enumerate(has_transcript, start=1)
    ]

    async def _fake_gather(_self, _sessions, **_kw):
        seg = TranscriptSegment(
            segment_index=0, start_time=0.0, end_time=5.0,
            text="Hello there.", speaker_label="A",
        )
        return (
            {s.session_id: [seg] for s in _sessions},
            StageOutcome(attempted=len(_sessions), succeeded=len(_sessions)),
        )

    async def _passthrough(sess, _tmp, **_kw):
        return sess

    calls: list[dict] = []
    with (
        patch("bristlenose.stages.s01_ingest.ingest", return_value=sessions),
        patch(
            "bristlenose.stages.s02_extract_audio.extract_audio_for_sessions",
            new=_passthrough,
        ),
        patch.object(Pipeline, "_gather_all_segments", new=_fake_gather),
        patch(
            "bristlenose.preflight.whisper.preflight_whisper",
            new=lambda **kw: calls.append(kw),
        ),
    ):
        asyncio.run(pipeline.run_transcription_only(input_dir, tmp_path / "out"))
    return calls


def test_preflight_runs_when_a_session_needs_transcription(tmp_path: Path) -> None:
    calls = _preflight_calls(tmp_path, [True, False])
    assert len(calls) == 1
    assert calls[0]["allow_fetch"] is True
    assert calls[0]["status"] is not None


def test_preflight_skipped_when_every_session_has_a_transcript(tmp_path: Path) -> None:
    assert _preflight_calls(tmp_path, [True, True]) == []
