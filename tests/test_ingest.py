"""Tests for Stage 1 session grouping — platform-aware file matching."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from bristlenose.models import FileType, InputFile
from bristlenose.stages.s01_ingest import (
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

    # -- Teams: real specimens ------------------------------------------------
    #
    # Every Teams case above this line is CONSTRUCTED — invented in Feb 2026
    # alongside the regex, with a space before the timestamp. Both real formats
    # use a hyphen, so the regex matched only its own fixtures and neither real
    # file, for six months, with a green suite throughout.
    #
    # The rule that follows from that: a case below this line must be a
    # filename observed on a real tenant, with the date and tier recorded.

    def test_teams_business_pair_matches(self) -> None:
        """Business tenant, captured 15 Aug 2026 — no UTC marker, hyphen separator.

        Unpaired, this is not a cosmetic bug: the video and its transcript
        become two sessions, so the mp4 is transcribed from scratch and the
        report gains a duplicate participant.
        """
        recording = _normalise_stem(
            "meeting with martin storey-20260815_200732-meeting recording"
        )
        transcript = _normalise_stem("meeting with martin storey")
        assert recording == transcript == "meeting with martin storey"

    def test_teams_personal_pair_matches(self) -> None:
        """Personal OneDrive, captured 15 Aug 2026 — UTC marker, hyphen separator."""
        recording = _normalise_stem(
            "meeting with martin storey-20260719_142007utc-meeting recording"
        )
        transcript = _normalise_stem("meeting with martin storey")
        assert recording == transcript == "meeting with martin storey"

    # -- Bristlenose's own cloud-import naming -------------------------------

    def test_cloud_import_pairs_with_a_hand_fetched_teams_transcript(self) -> None:
        """The workflow this rule exists for, and it was broken until 18 Aug 2026.

        Cloud import *renames on download* — "2026-08-12 1400 — P07 Interview.mp4"
        — so by the time the file is on disk it wears no vendor convention and
        none of the platform rules above can see it. The researcher then fetches
        the Teams transcript by hand, which is worth doing because it carries
        accurate speaker names that Whisper has to guess at.

        Unpaired, that costs exactly what it was meant to save: two sessions,
        the video re-transcribed from scratch with the names thrown away, and a
        phantom media-less session holding the transcript.
        """
        imported = _normalise_stem("2026-08-12 1400 — p07 interview")
        transcript = _normalise_stem("p07 interview-20260812_140000-meeting transcript")
        assert imported == transcript == "p07 interview"

    def test_cloud_import_pairs_with_a_hand_fetched_meet_transcript(self) -> None:
        imported = _normalise_stem("2026-08-12 1400 — p07 interview")
        transcript = _normalise_stem(
            "p07 interview - 2026_08_12 14_00 bst - notes by gemini"
        )
        assert imported == transcript == "p07 interview"

    def test_cloud_import_sibling_halves_stay_apart(self) -> None:
        """The ordinal is deliberately not stripped.

        Two recordings of one call are two files the researcher may want kept
        distinct, and that is already how platform-named siblings behave. Left
        alone rather than folded in, because collapsing them is a different
        decision from pairing a video with its transcript.
        """
        first = _normalise_stem("2026-08-12 1400 — p07 interview")
        second = _normalise_stem("2026-08-12 1400 — p07 interview (2)")
        assert first != second

    def test_cloud_import_untitled_recording_keeps_its_stamp(self) -> None:
        """A meeting with no title is named from the stamp alone.

        There is no title to pair on, so the stamp must survive as the whole
        key — stripping it would leave an empty stem, and every untitled
        recording in the folder would collapse into one session.
        """
        assert _normalise_stem("2026-08-12 1400") == "2026-08-12 1400"

    def test_a_researchers_own_dated_filename_is_not_mistaken_for_ours(self) -> None:
        """The prefix rule needs the separator, not just a leading date.

        Researchers date their own files. "2026-08-12 kickoff notes" has no
        " — " after a four-digit time, so it is left whole; treating any leading
        date as ours would silently re-key files we never touched.
        """
        assert _normalise_stem("2026-08-12 kickoff notes") == "2026-08-12 kickoff notes"
        assert _normalise_stem("2026-08-12 1400 debrief") == "2026-08-12 1400 debrief"

    def test_teams_hyphenated_title_survives(self) -> None:
        """The hyphen separator makes a hyphenated title the interesting case.

        "Q3 Review - Design" is an ordinary meeting name, and the tail strip
        must take only the timestamp block, not the first hyphen it meets.
        """
        recording = _normalise_stem(
            "q3 review - design-20260815_200732-meeting recording"
        )
        transcript = _normalise_stem("q3 review - design")
        assert recording == transcript == "q3 review - design"

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

    # -- Google Meet: real specimens ------------------------------------------
    #
    # Every Google Meet case above this line is CONSTRUCTED, from the paren
    # naming Google used when the regex was written. Google has since moved to
    # a dated-tail form, so those patterns match nothing Google emits today —
    # the same shape of failure as the Teams block above.
    #
    # Cases below this line are names observed on a real tenant, with the date
    # and tier recorded.

    def test_gmeet_business_pair_matches(self) -> None:
        """Business Standard tenant, captured 15 Aug 2026.

        The two files carry DIFFERENT timestamps — the recording is stamped
        with the meeting start, the notes Doc with the moment Gemini finished
        writing. Anything that normalises the timestamp rather than removing it
        still yields two keys, so the pair still would not group.
        """
        recording = _normalise_stem(
            "banyalbufar discussion - 2026/08/15 22:45 bst - recording"
        )
        transcript = _normalise_stem(
            "banyalbufar discussion - 2026/08/15 23:02 - notes by gemini"
        )
        assert recording == transcript == "banyalbufar discussion"

    def test_gmeet_disk_sanitised_name_matches(self) -> None:
        """Drive's API `name` and the downloaded filename differ.

        The API returns "2026/08/15 23:02"; macOS sanitises the file on disk to
        "2026_08_15 23_02". Ingest only ever sees the disk form, but the API
        form reaches the importer, so both must normalise identically.
        """
        on_disk = _normalise_stem(
            "banyalbufar discussion - 2026_08_15 23_02 - notes by gemini"
        )
        from_api = _normalise_stem(
            "banyalbufar discussion - 2026/08/15 23:02 - notes by gemini"
        )
        assert on_disk == from_api == "banyalbufar discussion"

    def test_gmeet_tail_strip_is_anchored_on_digits_not_the_trailing_word(
        self,
    ) -> None:
        """"Recording" / "Notes by Gemini" are localised; the date block is not.

        A tenant running in another language must still group its pair, so the
        pattern may not enumerate the trailing words.
        """
        recording = _normalise_stem(
            "reunió de banyalbufar - 2026/08/15 22:45 cest - gravació"
        )
        transcript = _normalise_stem(
            "reunió de banyalbufar - 2026/08/15 23:02 - notes de gemini"
        )
        assert recording == transcript == "reunió de banyalbufar"

    def test_gmeet_hyphenated_title_survives(self) -> None:
        """The " - " separator makes a hyphenated meeting title the risk case."""
        assert (
            _normalise_stem("q3 review - design - 2026/08/15 22:45 bst - recording")
            == "q3 review - design"
        )

    def test_gmeet_title_ending_in_a_date_is_not_truncated(self) -> None:
        """The trailing kind is mandatory, and this is why.

        Without it, any title whose own text ends in a date and time would be
        silently cut back to its first few words.
        """
        assert (
            _normalise_stem("q3 planning - 2026/08/15 14:00")
            == "q3 planning - 2026/08/15 14:00"
        )

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

    def test_session_id_assigned(self) -> None:
        """Sessions get session_id = s1, s2, ... independently from participant_id."""
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
        assert sessions[0].session_id == "s1"
        assert sessions[0].session_number == 1
        assert sessions[1].session_id == "s2"
        assert sessions[1].session_number == 2

    def test_session_id_distinct_from_participant_id(self) -> None:
        """session_id uses 's' prefix, participant_id uses 'p' prefix."""
        files = [_file("interview_01.mp4", FileType.VIDEO)]
        sessions = group_into_sessions(files)
        assert sessions[0].session_id == "s1"
        assert sessions[0].participant_id == "p1"
        assert sessions[0].session_id != sessions[0].participant_id
