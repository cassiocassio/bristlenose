"""One recording that outlasts ffmpeg's time limit costs that session, not the run (N144).

``extract_audio_from_video`` let ``subprocess.TimeoutExpired`` escape. It reached
``asyncio.gather`` in stage 2 as an unknown failure, so one long video on a slow
drive stopped the whole run, threw away the other sessions' finished extractions,
and did the same on every retry. The ffprobe timeout is a different case and stays
fail-loud (``test_has_audio_stream_raises_on_timeout``): a probe that cannot answer
says nothing about the file, an extraction that ran too long does.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import bristlenose.utils.audio as audio
from bristlenose.events import UnusableReason
from bristlenose.models import FileType, InputFile, InputSession
from bristlenose.stages import s02_extract_audio as s02


def _session(n: int, path: Path) -> InputSession:
    when = datetime(2026, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
    return InputSession(
        session_id=f"s{n}",
        session_number=n,
        participant_id=f"p{n}",
        participant_number=n,
        files=[InputFile(path=path, file_type=FileType.VIDEO, created_at=when, size_bytes=10)],
        session_date=when,
    )


@pytest.fixture()
def two_videos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[InputSession]:
    videos = []
    for n in (1, 2):
        path = tmp_path / f"interview{n}.mp4"
        path.write_bytes(b"x" * 10)
        videos.append(path)
    monkeypatch.setattr(s02, "has_audio_stream", lambda _p: True)
    monkeypatch.setattr(audio, "ensure_materialised", lambda _p: None)

    def fake_run(cmd, *_a, **kwargs):  # noqa: ANN001
        if "interview2" in " ".join(map(str, cmd)):
            Path(cmd[-1]).write_bytes(b"half a wav")  # what a killed ffmpeg leaves behind
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))
        Path(cmd[-1]).write_bytes(b"RIFF")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(audio.subprocess, "run", fake_run)
    return [_session(1, videos[0]), _session(2, videos[1])]


@pytest.mark.asyncio
async def test_a_timed_out_extraction_fails_that_session_and_the_run_continues(
    two_videos: list[InputSession], tmp_path: Path,
) -> None:
    out = await s02.extract_audio_for_sessions(two_videos, tmp_path / "tmp")
    good, slow = out
    assert good.audio_path is not None and good.audio_path.exists()
    assert slow.audio_path is None
    assert [f.error for f in slow.files] == [UnusableReason.UNREADABLE.value]
    assert [f.error for f in good.files] == [None]


@pytest.mark.asyncio
async def test_a_timed_out_extraction_leaves_no_half_written_audio(
    two_videos: list[InputSession], tmp_path: Path,
) -> None:
    await s02.extract_audio_for_sessions(two_videos, tmp_path / "tmp")
    assert not (tmp_path / "tmp" / "s2_extracted.wav").exists()


def test_the_timeout_is_a_named_error_not_a_raw_subprocess_one(
    two_videos: list[InputSession], tmp_path: Path,
) -> None:
    with pytest.raises(audio.MediaExtractionTimedOutError) as caught:
        audio.extract_audio_from_video(two_videos[1].files[0].path, tmp_path / "s2_extracted.wav")
    assert isinstance(caught.value, audio.AudioToolError)
    assert "interview2.mp4" in str(caught.value)
