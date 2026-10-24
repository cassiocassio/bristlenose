"""`bristlenose transcribe` runs the Whisper and ffmpeg preflights, gated as run() gates them.

Until 14 Oct 2026 only ``Pipeline.run`` called ``preflight_whisper``, so a first
``transcribe`` fetched the model inside the "Transcribing..." spinner with no
banner, no size and no progress (docs/design-cli-just-works.md, Debate 1). The
ffmpeg preflight had the same gap: on a machine without ffmpeg, ``transcribe`` on
a video got no install offer and failed late, at audio extraction.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.events import StageOutcome
from bristlenose.models import FileType, InputFile, InputSession, TranscriptSegment
from bristlenose.pipeline import Pipeline


def _session(
    input_dir: Path, i: int, *, has_transcript: bool, video: bool = False,
) -> InputSession:
    media = input_dir / (f"rec{i}.mp4" if video else f"rec{i}.wav")
    media.write_bytes(b"fake " + media.name.encode())  # its own bytes: identical files fold (R49)
    return InputSession(
        session_id=f"s{i}", session_number=i,
        participant_id=f"p{i}", participant_number=i,
        session_date=datetime.now(timezone.utc),
        files=[InputFile(
            path=media, file_type=FileType.VIDEO if video else FileType.AUDIO,
            created_at=datetime.now(timezone.utc), size_bytes=4,
            duration_seconds=60.0,
        )],
        audio_path=None if video else media,
        has_existing_transcript=has_transcript,
    )


def _preflight_calls(
    tmp_path: Path,
    has_transcript: list[bool],
    *,
    video: bool = False,
    ffmpeg_calls: list[dict] | None = None,
    ffmpeg_raises: Exception | None = None,
) -> list[dict]:
    settings = MagicMock()
    settings.project_name = "preflight"
    settings.write_intermediate = False
    settings.color_scheme = "default"
    settings.no_fetch = False
    pipeline = Pipeline(settings)

    input_dir = tmp_path / "in"
    input_dir.mkdir()
    sessions = [
        _session(input_dir, i, has_transcript=h, video=video)
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
    ffmpeg_seen = ffmpeg_calls if ffmpeg_calls is not None else []

    def _fake_ffmpeg(**kw) -> None:
        ffmpeg_seen.append(kw)
        if ffmpeg_raises is not None:
            raise ffmpeg_raises

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
        patch("bristlenose.preflight.ffmpeg.preflight_ffmpeg", new=_fake_ffmpeg),
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


def test_ffmpeg_preflight_runs_when_a_video_needs_transcription(tmp_path: Path) -> None:
    ffmpeg: list[dict] = []
    _preflight_calls(tmp_path, [False, True], video=True, ffmpeg_calls=ffmpeg)
    assert len(ffmpeg) == 1
    assert ffmpeg[0]["allow_install"] is True
    assert ffmpeg[0]["status"] is not None


def test_ffmpeg_preflight_skipped_for_audio(tmp_path: Path) -> None:
    ffmpeg: list[dict] = []
    _preflight_calls(tmp_path, [False, False], video=False, ffmpeg_calls=ffmpeg)
    assert ffmpeg == []


def test_ffmpeg_preflight_skipped_when_every_video_has_a_transcript(tmp_path: Path) -> None:
    ffmpeg: list[dict] = []
    _preflight_calls(tmp_path, [True, True], video=True, ffmpeg_calls=ffmpeg)
    assert ffmpeg == []


def test_a_declined_ffmpeg_install_stops_the_run(tmp_path: Path) -> None:
    """The same abort ``run`` raises: the CLI turns it into its fix-it message."""
    from bristlenose.preflight import PreflightAbortedError

    ffmpeg: list[dict] = []
    with pytest.raises(PreflightAbortedError):
        _preflight_calls(
            tmp_path, [False], video=True, ffmpeg_calls=ffmpeg,
            ffmpeg_raises=PreflightAbortedError("ffmpeg is required"),
        )
    assert len(ffmpeg) == 1
