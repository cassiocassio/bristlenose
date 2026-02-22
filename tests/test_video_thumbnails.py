"""Tests for video thumbnail extraction: heuristic and FFmpeg wrapper."""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from bristlenose.models import (
    FileType,
    FullTranscript,
    InputFile,
    InputSession,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.utils.video import (
    choose_thumbnail_time,
    extract_thumbnail,
    extract_thumbnails,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seg(
    start: float,
    end: float,
    role: SpeakerRole = SpeakerRole.PARTICIPANT,
    text: str = "hello",
) -> TranscriptSegment:
    return TranscriptSegment(
        start_time=start,
        end_time=end,
        text=text,
        speaker_label="Speaker A",
        speaker_role=role,
    )


def _transcript(
    segments: list[TranscriptSegment],
    session_id: str = "s1",
    duration: float = 600.0,
) -> FullTranscript:
    return FullTranscript(
        session_id=session_id,
        participant_id="p1",
        source_file="test.mp4",
        session_date=datetime(2026, 1, 1),
        duration_seconds=duration,
        segments=segments,
    )


def _video_session(
    session_id: str = "s1",
    video_path: Path | None = None,
) -> InputSession:
    path = video_path or Path("/fake/video.mp4")
    return InputSession(
        session_id=session_id,
        session_number=1,
        participant_id="p1",
        participant_number=1,
        files=[
            InputFile(
                path=path,
                file_type=FileType.VIDEO,
                created_at=datetime(2026, 1, 1),
                size_bytes=1000,
                duration_seconds=600.0,
            ),
        ],
        has_existing_transcript=False,
        session_date=datetime(2026, 1, 1),
    )


def _audio_session(session_id: str = "s2") -> InputSession:
    return InputSession(
        session_id=session_id,
        session_number=2,
        participant_id="p2",
        participant_number=2,
        files=[
            InputFile(
                path=Path("/fake/audio.mp3"),
                file_type=FileType.AUDIO,
                created_at=datetime(2026, 1, 1),
                size_bytes=500,
                duration_seconds=600.0,
            ),
        ],
        has_existing_transcript=False,
        session_date=datetime(2026, 1, 1),
    )


# ---------------------------------------------------------------------------
# choose_thumbnail_time — pure heuristic tests (no mocks)
# ---------------------------------------------------------------------------


class TestChooseThumbnailTime:
    def test_first_participant_segment(self) -> None:
        """Uses end_time of first PARTICIPANT segment."""
        t = _transcript([
            _seg(0, 30, SpeakerRole.RESEARCHER),
            _seg(30, 65, SpeakerRole.PARTICIPANT),
            _seg(65, 90, SpeakerRole.PARTICIPANT),
        ])
        assert choose_thumbnail_time(t) == 65.0

    def test_skips_researcher_segments(self) -> None:
        """Ignores RESEARCHER segments, finds first PARTICIPANT."""
        t = _transcript([
            _seg(0, 10, SpeakerRole.RESEARCHER),
            _seg(10, 20, SpeakerRole.RESEARCHER),
            _seg(20, 45, SpeakerRole.PARTICIPANT),
        ])
        assert choose_thumbnail_time(t) == 45.0

    def test_skips_observer_segments(self) -> None:
        """Ignores OBSERVER segments."""
        t = _transcript([
            _seg(0, 15, SpeakerRole.OBSERVER),
            _seg(15, 40, SpeakerRole.PARTICIPANT),
        ])
        assert choose_thumbnail_time(t) == 40.0

    def test_respects_window(self) -> None:
        """Ignores PARTICIPANT segments after the 3-minute window."""
        t = _transcript([
            _seg(0, 60, SpeakerRole.RESEARCHER),
            _seg(60, 120, SpeakerRole.RESEARCHER),
            _seg(200, 250, SpeakerRole.PARTICIPANT),  # After 180s window
        ])
        assert choose_thumbnail_time(t) == 60.0  # fallback

    def test_custom_window(self) -> None:
        """Respects custom window_seconds parameter."""
        t = _transcript([
            _seg(50, 70, SpeakerRole.PARTICIPANT),
        ])
        assert choose_thumbnail_time(t, window_seconds=40.0) == 60.0  # fallback

    def test_fallback_no_participant(self) -> None:
        """Returns 60s when no PARTICIPANT in window."""
        t = _transcript([
            _seg(0, 30, SpeakerRole.RESEARCHER),
            _seg(30, 60, SpeakerRole.RESEARCHER),
        ])
        assert choose_thumbnail_time(t) == 60.0

    def test_fallback_short_video(self) -> None:
        """Returns 0.0 when video is shorter than fallback time."""
        t = _transcript(
            [_seg(0, 10, SpeakerRole.RESEARCHER)],
            duration=30.0,
        )
        assert choose_thumbnail_time(t) == 0.0

    def test_uses_end_time_not_start_time(self) -> None:
        """Uses end_time (boundary) for better still frame."""
        t = _transcript([
            _seg(10.5, 25.3, SpeakerRole.PARTICIPANT),
        ])
        assert choose_thumbnail_time(t) == 25.3

    def test_empty_transcript(self) -> None:
        """Empty transcript falls back to 60s."""
        t = _transcript([], duration=600.0)
        assert choose_thumbnail_time(t) == 60.0

    def test_participant_at_very_start(self) -> None:
        """Participant speaking from the very start."""
        t = _transcript([
            _seg(0, 5, SpeakerRole.PARTICIPANT),
        ])
        assert choose_thumbnail_time(t) == 5.0


# ---------------------------------------------------------------------------
# extract_thumbnail — FFmpeg wrapper (mock subprocess)
# ---------------------------------------------------------------------------


class TestExtractThumbnail:
    def test_success(self, tmp_path: Path) -> None:
        """FFmpeg succeeds — returns output path."""
        output = tmp_path / "thumb.jpg"

        def _fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            # Create a non-empty file to simulate FFmpeg output.
            Path(cmd[-1]).write_bytes(b"\xff\xd8fake-jpeg")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with patch("bristlenose.utils.video.subprocess.run", side_effect=_fake_run):
            result = extract_thumbnail(Path("/fake/video.mp4"), output, 30.0)

        assert result == output
        assert output.exists()

    def test_ffmpeg_failure(self, tmp_path: Path) -> None:
        """FFmpeg fails — returns None."""
        output = tmp_path / "thumb.jpg"
        mock_result = subprocess.CompletedProcess([], 1, "", "Error: something broke")

        with patch("bristlenose.utils.video.subprocess.run", return_value=mock_result):
            result = extract_thumbnail(Path("/fake/video.mp4"), output, 30.0)

        assert result is None

    def test_timeout(self, tmp_path: Path) -> None:
        """FFmpeg times out — returns None."""
        output = tmp_path / "thumb.jpg"

        with patch(
            "bristlenose.utils.video.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=30),
        ):
            result = extract_thumbnail(Path("/fake/video.mp4"), output, 30.0)

        assert result is None

    def test_ffmpeg_not_found(self, tmp_path: Path) -> None:
        """FFmpeg not in PATH — returns None."""
        output = tmp_path / "thumb.jpg"

        with patch(
            "bristlenose.utils.video.subprocess.run",
            side_effect=FileNotFoundError("ffmpeg not found"),
        ):
            result = extract_thumbnail(Path("/fake/video.mp4"), output, 30.0)

        assert result is None

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """Creates output directory if it doesn't exist."""
        output = tmp_path / "thumbs" / "nested" / "thumb.jpg"

        def _fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            Path(cmd[-1]).write_bytes(b"\xff\xd8fake-jpeg")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with patch("bristlenose.utils.video.subprocess.run", side_effect=_fake_run):
            result = extract_thumbnail(Path("/fake/video.mp4"), output, 10.0)

        assert result == output
        assert output.parent.exists()

    def test_empty_output_returns_none(self, tmp_path: Path) -> None:
        """FFmpeg succeeds but produces empty file — returns None."""
        output = tmp_path / "thumb.jpg"
        mock_result = subprocess.CompletedProcess([], 0, "", "")

        with patch("bristlenose.utils.video.subprocess.run", return_value=mock_result):
            result = extract_thumbnail(Path("/fake/video.mp4"), output, 30.0)

        assert result is None


# ---------------------------------------------------------------------------
# extract_thumbnails — orchestrator
# ---------------------------------------------------------------------------


class TestExtractThumbnails:
    def test_skips_audio_only_sessions(self, tmp_path: Path) -> None:
        """Audio-only sessions produce no thumbnail."""
        sessions = [_audio_session()]
        transcripts = [_transcript([_seg(0, 30)], session_id="s2")]

        result = extract_thumbnails(sessions, transcripts, tmp_path)

        assert result == {}

    def test_uses_cache(self, tmp_path: Path) -> None:
        """Pre-existing thumbnail is reused without re-extraction."""
        # Create a cached thumbnail.
        thumb = tmp_path / "s1.jpg"
        thumb.write_bytes(b"\xff\xd8cached")

        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake-video")
        sessions = [_video_session(video_path=video_path)]
        transcripts = [_transcript([_seg(0, 30)])]

        with patch("bristlenose.utils.video.extract_thumbnail") as mock_extract:
            result = extract_thumbnails(sessions, transcripts, tmp_path)

        # Should not call extract_thumbnail — used cache instead.
        mock_extract.assert_not_called()
        assert "s1" in result
        assert result["s1"] == thumb

    def test_no_transcript_uses_fallback(self, tmp_path: Path) -> None:
        """Session without transcript falls back to 60s timestamp."""
        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake-video")
        sessions = [_video_session(video_path=video_path)]
        transcripts: list[FullTranscript] = []  # No transcripts

        with patch("bristlenose.utils.video.extract_thumbnail", return_value=None) as mock:
            extract_thumbnails(sessions, transcripts, tmp_path)

        # Check the timestamp argument (3rd positional arg).
        mock.assert_called_once()
        call_args = mock.call_args
        assert call_args[0][2] == 60.0  # fallback timestamp

    def test_extracts_for_video_sessions(self, tmp_path: Path) -> None:
        """Calls extract_thumbnail for video sessions with transcripts."""
        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake-video")
        sessions = [_video_session(video_path=video_path)]
        transcripts = [_transcript([
            _seg(0, 20, SpeakerRole.RESEARCHER),
            _seg(20, 50, SpeakerRole.PARTICIPANT),
        ])]

        thumb_path = tmp_path / "s1.jpg"

        with patch(
            "bristlenose.utils.video.extract_thumbnail",
            return_value=thumb_path,
        ) as mock:
            result = extract_thumbnails(sessions, transcripts, tmp_path)

        mock.assert_called_once()
        # Heuristic should pick end_time of first participant segment = 50.0
        call_args = mock.call_args
        assert call_args[0][2] == 50.0
        assert result == {"s1": thumb_path}

    def test_skips_missing_video_file(self, tmp_path: Path) -> None:
        """Skips session when video file doesn't exist on disk."""
        sessions = [_video_session(video_path=Path("/nonexistent/video.mp4"))]
        transcripts = [_transcript([_seg(0, 30)])]

        with patch("bristlenose.utils.video.extract_thumbnail") as mock:
            result = extract_thumbnails(sessions, transcripts, tmp_path)

        mock.assert_not_called()
        assert result == {}
