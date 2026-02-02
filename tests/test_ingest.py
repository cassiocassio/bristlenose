"""Tests for Stage 1 session grouping — platform-aware file matching."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from bristlenose.models import FileType, InputFile
from bristlenose.stages.ingest import (
    _is_zoom_local_dir,
    _normalise_stem,
    group_into_sessions,
)

_T0 = datetime(2026, 1, 15, 14, 0, 0, tzinfo=timezone.utc)


def _file(name: str, file_type: FileType, parent: Path | None = None) -> InputFile:
    """Helper: build an InputFile with a fake path."""
    base = parent or Path("/input")
    return InputFile(
        path=base / name,
        file_type=file_type,
        created_at=_T0,
        size_bytes=1000,
    )


# ---------------------------------------------------------------------------
# _normalise_stem unit tests
# ---------------------------------------------------------------------------


class TestNormaliseStem:
    def test_plain_stem_unchanged(self) -> None:
        assert _normalise_stem("interview_01") == "interview_01"

    def test_legacy_suffix_transcript(self) -> None:
        assert _normalise_stem("interview_01_transcript") == "interview_01"

    def test_legacy_suffix_subtitles(self) -> None:
        assert _normalise_stem("interview_01_subtitles") == "interview_01"

    def test_legacy_suffix_captions(self) -> None:
        assert _normalise_stem("interview_01_captions") == "interview_01"

    # -- Teams ---------------------------------------------------------------

    def test_teams_meeting_recording(self) -> None:
        stem = "user research 20260130_093012-meeting recording"
        assert _normalise_stem(stem) == "user research"

    def test_teams_meeting_recording_case_insensitive(self) -> None:
        stem = "user research 20260130_093012-Meeting Recording"
        assert _normalise_stem(stem.lower()) == "user research"

    def test_teams_meeting_transcript(self) -> None:
        stem = "user research 20260130_093012-meeting transcript"
        assert _normalise_stem(stem) == "user research"

    def test_teams_plain_transcript_stem(self) -> None:
        """Downloaded transcript is just 'User Research.vtt' → stem unchanged."""
        assert _normalise_stem("user research") == "user research"

    def test_teams_pair_matches(self) -> None:
        """Recording and transcript normalise to the same key."""
        recording = _normalise_stem(
            "user research 20260130_093012-meeting recording"
        )
        transcript = _normalise_stem("user research")
        assert recording == transcript

    # -- Zoom cloud ----------------------------------------------------------

    def test_zoom_cloud_video(self) -> None:
        stem = "user research_987654321_jan_15_2026"
        assert _normalise_stem(stem) == "user research"

    def test_zoom_cloud_audio_transcript(self) -> None:
        stem = "audio transcript_user research_987654321_jan_15_2026"
        assert _normalise_stem(stem) == "user research"

    def test_zoom_cloud_pair_matches(self) -> None:
        video = _normalise_stem("user research_987654321_jan_15_2026")
        transcript = _normalise_stem(
            "audio transcript_user research_987654321_jan_15_2026"
        )
        assert video == transcript

    def test_zoom_cloud_ten_digit_id(self) -> None:
        stem = "standup_9876543210_feb_01_2026"
        assert _normalise_stem(stem) == "standup"

    # -- Google Meet (Phase 2 prep) ------------------------------------------

    def test_gmeet_recording(self) -> None:
        stem = "weekly sync (2026-01-28 at 14 30 gmt-5)"
        assert _normalise_stem(stem) == "weekly sync"

    def test_gmeet_transcript(self) -> None:
        stem = "weekly sync (2026-1-28 at 14:30 est) - transcript"
        assert _normalise_stem(stem) == "weekly sync"

    def test_gmeet_pair_matches(self) -> None:
        recording = _normalise_stem("weekly sync (2026-01-28 at 14 30 gmt-5)")
        transcript = _normalise_stem(
            "weekly sync (2026-1-28 at 14:30 est) - transcript"
        )
        assert recording == transcript

    # -- No false positives --------------------------------------------------

    def test_normal_stem_not_mangled(self) -> None:
        assert _normalise_stem("my_recording_2026") == "my_recording_2026"

    def test_short_number_not_zoom_id(self) -> None:
        """A trailing _12345 should NOT be stripped (too short for Zoom ID)."""
        assert _normalise_stem("recording_12345") == "recording_12345"


# ---------------------------------------------------------------------------
# _is_zoom_local_dir
# ---------------------------------------------------------------------------


class TestIsZoomLocalDir:
    def test_matches_zoom_folder(self) -> None:
        assert _is_zoom_local_dir("2026-01-15 14.30.22 Interview 987654321")

    def test_matches_long_topic(self) -> None:
        assert _is_zoom_local_dir(
            "2026-01-15 14.30.22 User Research Session 5 987654321"
        )

    def test_rejects_plain_directory(self) -> None:
        assert not _is_zoom_local_dir("interviews")

    def test_rejects_teams_style(self) -> None:
        assert not _is_zoom_local_dir("User Research 20260130_093012")

    def test_rejects_no_meeting_id(self) -> None:
        assert not _is_zoom_local_dir("2026-01-15 14.30.22 Interview")

    def test_rejects_short_id(self) -> None:
        assert not _is_zoom_local_dir("2026-01-15 14.30.22 Interview 12345")


# ---------------------------------------------------------------------------
# group_into_sessions integration tests
# ---------------------------------------------------------------------------


class TestGroupIntoSessions:
    def test_plain_stem_match(self) -> None:
        """Original behaviour: same-stem files grouped."""
        files = [
            _file("interview_01.mp4", FileType.VIDEO),
            _file("interview_01.srt", FileType.SUBTITLE_SRT),
        ]
        sessions = group_into_sessions(files)
        assert len(sessions) == 1
        assert len(sessions[0].files) == 2
        assert sessions[0].has_existing_transcript is True

    def test_legacy_suffix_match(self) -> None:
        """Original behaviour: _transcript suffix stripped."""
        files = [
            _file("interview_01.mp4", FileType.VIDEO),
            _file("interview_01_transcript.srt", FileType.SUBTITLE_SRT),
        ]
        sessions = group_into_sessions(files)
        assert len(sessions) == 1

    def test_different_stems_separate(self) -> None:
        """Different stems → different sessions."""
        files = [
            _file("interview_01.mp4", FileType.VIDEO),
            _file("interview_02.vtt", FileType.SUBTITLE_VTT),
        ]
        sessions = group_into_sessions(files)
        assert len(sessions) == 2

    def test_teams_video_plus_vtt(self) -> None:
        """Teams recording + downloaded VTT → same session."""
        files = [
            _file(
                "User Research 20260130_093012-Meeting Recording.mp4",
                FileType.VIDEO,
            ),
            _file("User Research.vtt", FileType.SUBTITLE_VTT),
        ]
        sessions = group_into_sessions(files)
        assert len(sessions) == 1
        assert len(sessions[0].files) == 2
        assert sessions[0].has_existing_transcript is True

    def test_teams_video_plus_docx(self) -> None:
        """Teams recording + downloaded DOCX transcript → same session."""
        files = [
            _file(
                "User Research 20260130_093012-Meeting Recording.mp4",
                FileType.VIDEO,
            ),
            _file("User Research.docx", FileType.DOCX),
        ]
        sessions = group_into_sessions(files)
        assert len(sessions) == 1
        assert sessions[0].has_existing_transcript is True

    def test_zoom_cloud_video_plus_transcript(self) -> None:
        """Zoom cloud download files → same session."""
        files = [
            _file(
                "User Research_987654321_Jan_15_2026.mp4",
                FileType.VIDEO,
            ),
            _file(
                "Audio Transcript_User Research_987654321_Jan_15_2026.vtt",
                FileType.SUBTITLE_VTT,
            ),
        ]
        sessions = group_into_sessions(files)
        assert len(sessions) == 1
        assert sessions[0].has_existing_transcript is True

    def test_zoom_local_folder(self) -> None:
        """Zoom local recording folder → all files grouped regardless of stem."""
        zoom_dir = Path("/input/2026-01-15 14.30.22 Interview 987654321")
        files = [
            _file("zoom_0.mp4", FileType.VIDEO, parent=zoom_dir),
            _file("audio_only.m4a", FileType.AUDIO, parent=zoom_dir),
            _file("closed_caption.vtt", FileType.SUBTITLE_VTT, parent=zoom_dir),
        ]
        sessions = group_into_sessions(files)
        assert len(sessions) == 1
        assert len(sessions[0].files) == 3
        assert sessions[0].has_existing_transcript is True

    def test_zoom_local_folder_no_video(self) -> None:
        """Zoom folder with only a transcript → single session."""
        zoom_dir = Path("/input/2026-01-15 14.30.22 Interview 987654321")
        files = [
            _file("closed_caption.vtt", FileType.SUBTITLE_VTT, parent=zoom_dir),
        ]
        sessions = group_into_sessions(files)
        assert len(sessions) == 1
        assert sessions[0].has_existing_transcript is True

    def test_video_only_no_transcript(self) -> None:
        """Video file alone → has_existing_transcript=False."""
        files = [_file("interview.mp4", FileType.VIDEO)]
        sessions = group_into_sessions(files)
        assert len(sessions) == 1
        assert sessions[0].has_existing_transcript is False

    def test_mixed_zoom_and_plain(self) -> None:
        """Zoom folder files + plain files → separate sessions."""
        zoom_dir = Path("/input/2026-01-15 14.30.22 Interview 987654321")
        files = [
            _file("zoom_0.mp4", FileType.VIDEO, parent=zoom_dir),
            _file("closed_caption.vtt", FileType.SUBTITLE_VTT, parent=zoom_dir),
            _file("interview_02.mp4", FileType.VIDEO),
        ]
        sessions = group_into_sessions(files)
        assert len(sessions) == 2

    def test_participant_numbering_by_date(self) -> None:
        """Sessions are numbered p1, p2, ... by earliest file date."""
        early = datetime(2026, 1, 10, 10, 0, 0, tzinfo=timezone.utc)
        late = datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc)
        files = [
            InputFile(
                path=Path("/input/second.mp4"),
                file_type=FileType.VIDEO,
                created_at=late,
                size_bytes=1000,
            ),
            InputFile(
                path=Path("/input/first.mp4"),
                file_type=FileType.VIDEO,
                created_at=early,
                size_bytes=1000,
            ),
        ]
        sessions = group_into_sessions(files)
        assert sessions[0].participant_id == "p1"
        assert sessions[0].files[0].path.name == "first.mp4"
        assert sessions[1].participant_id == "p2"
