"""Tests for moderator identification and per-segment speaker codes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from bristlenose.models import (
    FileType,
    FullTranscript,
    InputFile,
    InputSession,
    PeopleFile,
    PersonComputed,
    PersonEditable,
    PersonEntry,
    PiiCleanTranscript,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.stages.identify_speakers import assign_speaker_codes

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seg(
    start: float,
    end: float,
    text: str,
    label: str = "Speaker A",
    role: SpeakerRole = SpeakerRole.PARTICIPANT,
) -> TranscriptSegment:
    return TranscriptSegment(
        start_time=start,
        end_time=end,
        text=text,
        speaker_label=label,
        speaker_role=role,
        source="whisper",
    )


def _make_two_speaker_segments() -> list[TranscriptSegment]:
    """Researcher (Speaker A) and participant (Speaker B)."""
    return [
        _seg(0.0, 10.0, "Can you tell me about your experience?",
             "Speaker A", SpeakerRole.RESEARCHER),
        _seg(11.0, 30.0, "Yeah I've been using this for years.",
             "Speaker B", SpeakerRole.PARTICIPANT),
        _seg(31.0, 40.0, "And what do you think of the new feature?",
             "Speaker A", SpeakerRole.RESEARCHER),
        _seg(41.0, 60.0, "It's really confusing actually.",
             "Speaker B", SpeakerRole.PARTICIPANT),
    ]


# ---------------------------------------------------------------------------
# assign_speaker_codes()
# ---------------------------------------------------------------------------


class TestAssignSpeakerCodes:
    def test_two_speakers_researcher_and_participant(self) -> None:
        segments = _make_two_speaker_segments()
        label_map, _ = assign_speaker_codes(1, segments)

        assert label_map["Speaker A"] == "m1"
        assert label_map["Speaker B"] == "p1"
        assert segments[0].speaker_code == "m1"
        assert segments[1].speaker_code == "p1"
        assert segments[2].speaker_code == "m1"
        assert segments[3].speaker_code == "p1"

    def test_two_researchers(self) -> None:
        segments = [
            _seg(0.0, 10.0, "I'm the lead researcher.",
                 "Speaker A", SpeakerRole.RESEARCHER),
            _seg(11.0, 20.0, "And I'm the second moderator.",
                 "Speaker B", SpeakerRole.RESEARCHER),
            _seg(21.0, 40.0, "Nice to meet you both.",
                 "Speaker C", SpeakerRole.PARTICIPANT),
        ]
        label_map, _ = assign_speaker_codes(1, segments)

        assert label_map["Speaker A"] == "m1"
        assert label_map["Speaker B"] == "m2"
        assert label_map["Speaker C"] == "p1"

    def test_observer_gets_o_prefix(self) -> None:
        segments = [
            _seg(0.0, 10.0, "Let's begin.", "Speaker A", SpeakerRole.RESEARCHER),
            _seg(11.0, 30.0, "Sure.", "Speaker B", SpeakerRole.PARTICIPANT),
            _seg(31.0, 33.0, "Mm-hmm.", "Speaker C", SpeakerRole.OBSERVER),
        ]
        label_map, _ = assign_speaker_codes(2, segments)

        assert label_map["Speaker A"] == "m1"
        assert label_map["Speaker B"] == "p2"
        assert label_map["Speaker C"] == "o1"

    def test_single_speaker_gets_participant_id(self) -> None:
        segments = [
            _seg(0.0, 30.0, "I was talking to myself.",
                 "Speaker A", SpeakerRole.PARTICIPANT),
        ]
        label_map, _ = assign_speaker_codes(3, segments)

        assert label_map["Speaker A"] == "p3"
        assert segments[0].speaker_code == "p3"

    def test_unknown_role_falls_back_to_participant_id(self) -> None:
        segments = [
            _seg(0.0, 15.0, "Hello.", "Speaker A", SpeakerRole.UNKNOWN),
        ]
        label_map, _ = assign_speaker_codes(1, segments)

        assert label_map["Speaker A"] == "p1"

    def test_none_speaker_label_treated_as_unknown(self) -> None:
        segments = [
            TranscriptSegment(
                start_time=0.0, end_time=10.0, text="No label.",
                speaker_label=None, speaker_role=SpeakerRole.PARTICIPANT,
                source="whisper",
            ),
        ]
        label_map, _ = assign_speaker_codes(1, segments)

        assert label_map["Unknown"] == "p1"
        assert segments[0].speaker_code == "p1"


# ---------------------------------------------------------------------------
# Transcript writing round-trip
# ---------------------------------------------------------------------------


class TestTranscriptRoundTrip:
    def _make_transcript_with_moderator(self) -> FullTranscript:
        segs = _make_two_speaker_segments()
        assign_speaker_codes(1, segs)
        return FullTranscript(
            participant_id="p1",
            session_id="s1",
            source_file="interview_01.mp4",
            session_date=datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc),
            duration_seconds=60.0,
            segments=segs,
        )

    def test_raw_txt_contains_moderator_codes(self, tmp_path: Path) -> None:
        from bristlenose.stages.merge_transcript import write_raw_transcripts

        transcript = self._make_transcript_with_moderator()
        write_raw_transcripts([transcript], tmp_path)
        content = (tmp_path / "s1.txt").read_text()

        assert "[00:00] [m1]" in content
        assert "[00:11] [p1]" in content
        assert "[00:31] [m1]" in content
        assert "[00:41] [p1]" in content

    def test_raw_md_contains_moderator_codes(self, tmp_path: Path) -> None:
        from bristlenose.stages.merge_transcript import write_raw_transcripts_md

        transcript = self._make_transcript_with_moderator()
        write_raw_transcripts_md([transcript], tmp_path)
        content = (tmp_path / "s1.md").read_text()

        assert "**[00:00] m1**" in content
        assert "**[00:11] p1**" in content

    def test_cooked_txt_contains_moderator_codes(self, tmp_path: Path) -> None:
        from bristlenose.stages.pii_removal import write_cooked_transcripts

        segs = _make_two_speaker_segments()
        assign_speaker_codes(1, segs)
        transcript = PiiCleanTranscript(
            participant_id="p1",
            session_id="s1",
            source_file="interview_01.mp4",
            session_date=datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc),
            duration_seconds=60.0,
            segments=segs,
        )
        write_cooked_transcripts([transcript], tmp_path)
        content = (tmp_path / "s1.txt").read_text()

        assert "[00:00] [m1]" in content
        assert "[00:11] [p1]" in content

    def test_cooked_md_contains_moderator_codes(self, tmp_path: Path) -> None:
        from bristlenose.stages.pii_removal import write_cooked_transcripts_md

        segs = _make_two_speaker_segments()
        assign_speaker_codes(1, segs)
        transcript = PiiCleanTranscript(
            participant_id="p1",
            session_id="s1",
            source_file="interview_01.mp4",
            session_date=datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc),
            duration_seconds=60.0,
            segments=segs,
        )
        write_cooked_transcripts_md([transcript], tmp_path)
        content = (tmp_path / "s1.md").read_text()

        assert "**[00:00] m1**" in content
        assert "**[00:11] p1**" in content

    def test_load_recovers_moderator_role(self, tmp_path: Path) -> None:
        """Write with [m1]/[p1] codes, load back, verify roles and codes."""
        from bristlenose.pipeline import load_transcripts_from_dir
        from bristlenose.stages.pii_removal import write_cooked_transcripts

        segs = _make_two_speaker_segments()
        assign_speaker_codes(1, segs)
        transcript = PiiCleanTranscript(
            participant_id="p1",
            session_id="s1",
            source_file="interview_01.mp4",
            session_date=datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc),
            duration_seconds=60.0,
            segments=segs,
        )
        write_cooked_transcripts([transcript], tmp_path)
        loaded = load_transcripts_from_dir(tmp_path)

        assert len(loaded) == 1
        segs_loaded = loaded[0].segments
        assert len(segs_loaded) == 4

        # Moderator segments
        assert segs_loaded[0].speaker_role == SpeakerRole.RESEARCHER
        assert segs_loaded[0].speaker_code == "m1"
        assert segs_loaded[2].speaker_role == SpeakerRole.RESEARCHER
        assert segs_loaded[2].speaker_code == "m1"

        # Participant segments
        assert segs_loaded[1].speaker_code == "p1"
        assert segs_loaded[3].speaker_code == "p1"


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    def test_old_format_all_p1_loads_as_unknown(self, tmp_path: Path) -> None:
        """Old .txt files with [p1] for all segments load with UNKNOWN role."""
        from bristlenose.pipeline import load_transcripts_from_dir

        content = (
            "# Transcript: p1\n"
            "# Source: interview.mp4\n"
            "# Date: 2026-01-10\n"
            "# Duration: 00:01:00\n"
            "\n"
            "[00:00] [p1] Hi, thanks for joining.\n"
            "\n"
            "[00:10] [p1] Sure, happy to be here.\n"
        )
        (tmp_path / "s1_cooked.txt").write_text(content, encoding="utf-8")
        loaded = load_transcripts_from_dir(tmp_path)

        assert len(loaded) == 1
        for seg in loaded[0].segments:
            assert seg.speaker_role == SpeakerRole.UNKNOWN
            assert seg.speaker_code == "p1"

    def test_no_speaker_code_defaults_empty(self) -> None:
        """TranscriptSegment without speaker_code has empty string default."""
        seg = TranscriptSegment(
            start_time=0.0, end_time=10.0, text="Hello.",
        )
        assert seg.speaker_code == ""


# ---------------------------------------------------------------------------
# People file: moderator stats
# ---------------------------------------------------------------------------


class TestModeratorPeopleStats:
    def test_moderator_entry_in_stats(self) -> None:
        from bristlenose.people import compute_participant_stats

        segs = _make_two_speaker_segments()
        assign_speaker_codes(1, segs)

        _dt = datetime(2026, 1, 20, tzinfo=timezone.utc)
        _file = InputFile(
            path=Path("/fake/interview.mp4"),
            file_type=FileType.VIDEO,
            created_at=_dt,
            size_bytes=1000,
            duration_seconds=60.0,
        )
        session = InputSession(
            session_id="s1", session_number=1,
            participant_id="p1", participant_number=1,
            session_date=_dt, files=[_file],
        )
        transcript = FullTranscript(
            participant_id="p1",
            session_id="s1",
            source_file="interview.mp4",
            session_date=_dt,
            duration_seconds=60.0,
            segments=segs,
        )

        stats = compute_participant_stats([session], [transcript])

        # Participant entry
        assert "p1" in stats
        assert stats["p1"].words_spoken > 0

        # Moderator entry
        assert "m1" in stats
        assert stats["m1"].words_spoken > 0
        assert stats["m1"].source_file == "interview.mp4"

    def test_no_moderator_entry_for_single_speaker(self) -> None:
        from bristlenose.people import compute_participant_stats

        segs = [_seg(0.0, 30.0, "Just me talking.", "Speaker A", SpeakerRole.PARTICIPANT)]
        assign_speaker_codes(1, segs)

        _dt = datetime(2026, 1, 20, tzinfo=timezone.utc)
        _file = InputFile(
            path=Path("/fake/interview.mp4"),
            file_type=FileType.VIDEO,
            created_at=_dt,
            size_bytes=1000,
            duration_seconds=30.0,
        )
        session = InputSession(
            session_id="s1", session_number=1,
            participant_id="p1", participant_number=1,
            session_date=_dt, files=[_file],
        )
        transcript = FullTranscript(
            participant_id="p1",
            session_id="s1",
            source_file="interview.mp4",
            session_date=datetime(2026, 1, 20, tzinfo=timezone.utc),
            duration_seconds=30.0,
            segments=segs,
        )

        stats = compute_participant_stats([session], [transcript])

        assert "p1" in stats
        assert "m1" not in stats


# ---------------------------------------------------------------------------
# Transcript page HTML rendering
# ---------------------------------------------------------------------------


class TestTranscriptPageRendering:
    _MODERATOR_TRANSCRIPT = (
        "# Transcript: s1\n"
        "# Source: interview_01.mp4\n"
        "# Date: 2026-01-20\n"
        "# Duration: 00:01:00\n"
        "\n"
        "[00:00] [m1] Can you tell me about your experience?\n"
        "\n"
        "[00:11] [p1] Yeah I've been using this for years.\n"
        "\n"
        "[00:31] [m1] And what about the new feature?\n"
        "\n"
        "[00:41] [p1] It's really confusing actually.\n"
    )

    def _setup_and_render(self, tmp_path: Path, people: PeopleFile | None = None) -> str:
        from bristlenose.stages.render_html import render_transcript_pages

        raw_dir = tmp_path / "transcripts-raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "s1.txt").write_text(self._MODERATOR_TRANSCRIPT, encoding="utf-8")

        render_transcript_pages(
            sessions=[], project_name="Test", output_dir=tmp_path, people=people,
        )
        return (tmp_path / "sessions" / "transcript_s1.html").read_text(encoding="utf-8")

    def test_moderator_segments_have_css_class(self, tmp_path: Path) -> None:
        html = self._setup_and_render(tmp_path)
        assert "segment-moderator" in html

    def test_participant_segments_no_moderator_class(self, tmp_path: Path) -> None:
        html = self._setup_and_render(tmp_path)
        # Participant segments should not have segment-moderator class
        lines = [line for line in html.split("\n") if "been using this" in line]
        assert lines  # sanity check
        for line in lines:
            assert "segment-moderator" not in line

    def test_per_segment_speaker_name_resolution(self, tmp_path: Path) -> None:
        people = PeopleFile(
            last_updated=datetime.now(tz=timezone.utc),
            participants={
                "p1": PersonEntry(
                    computed=PersonComputed(
                        participant_id="p1",
                        session_id="s1",
                        session_date=datetime(2026, 1, 20, tzinfo=timezone.utc),
                        duration_seconds=60.0, words_spoken=20,
                        pct_words=100.0, pct_time_speaking=50.0,
                        source_file="interview_01.mp4",
                    ),
                    editable=PersonEditable(short_name="Sarah"),
                ),
                "m1": PersonEntry(
                    computed=PersonComputed(
                        participant_id="m1",
                        session_id="s1",
                        session_date=datetime(2026, 1, 20, tzinfo=timezone.utc),
                        duration_seconds=60.0, words_spoken=15,
                        pct_words=0.0, pct_time_speaking=30.0,
                        source_file="interview_01.mp4",
                    ),
                    editable=PersonEditable(short_name="Dr Smith"),
                ),
            },
        )
        html = self._setup_and_render(tmp_path, people=people)

        # Segment labels show speaker codes, not resolved names
        assert 'data-participant="m1">m1:</span>' in html
        assert 'data-participant="p1">p1:</span>' in html

    def test_moderator_data_participant_attribute(self, tmp_path: Path) -> None:
        html = self._setup_and_render(tmp_path)
        assert 'data-participant="m1"' in html
        assert 'data-participant="p1"' in html

    def test_old_format_renders_without_moderator_class(self, tmp_path: Path) -> None:
        """Old transcripts (all [p1]) render without segment-moderator."""
        from bristlenose.stages.render_html import render_transcript_pages

        old_transcript = (
            "# Transcript: s1\n"
            "# Source: interview.mp4\n"
            "# Date: 2026-01-20\n"
            "# Duration: 00:01:00\n"
            "\n"
            "[00:00] [p1] Hello.\n"
            "\n"
            "[00:10] [p1] Goodbye.\n"
        )
        raw_dir = tmp_path / "transcripts-raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "s1.txt").write_text(old_transcript, encoding="utf-8")

        render_transcript_pages(
            sessions=[], project_name="Test", output_dir=tmp_path,
        )
        html = (tmp_path / "sessions" / "transcript_s1.html").read_text(encoding="utf-8")

        assert "segment-moderator" not in html


# ---------------------------------------------------------------------------
# CSS output
# ---------------------------------------------------------------------------


class TestModeratorCSS:
    def test_moderator_css_rules_present(self) -> None:
        css_path = Path(__file__).parent.parent / "bristlenose" / "theme" / "templates" / "transcript.css"
        css = css_path.read_text(encoding="utf-8")

        assert ".segment-moderator" in css
        assert "--bn-colour-muted" in css


# ---------------------------------------------------------------------------
# Multi-participant sessions
# ---------------------------------------------------------------------------


def _make_multi_participant_segments(
    num_participants: int = 2,
    with_researcher: bool = True,
    num_observers: int = 0,
) -> list[TranscriptSegment]:
    """Build a realistic segment list with multiple speakers.

    Returns segments in a natural conversation order: researcher asks,
    participants respond, observers chime in occasionally.
    """
    segments: list[TranscriptSegment] = []
    t = 0.0

    if with_researcher:
        segments.append(_seg(
            t, t + 8, "Welcome everyone, let's start with introductions.",
            "Researcher", SpeakerRole.RESEARCHER,
        ))
        t += 10

    for i in range(num_participants):
        label = f"Participant {chr(65 + i)}"  # A, B, C, ...
        segments.append(_seg(
            t, t + 15, f"Hi, I'm participant {chr(65 + i)}, nice to meet you.",
            label, SpeakerRole.PARTICIPANT,
        ))
        t += 17

    for i in range(num_observers):
        label = f"Observer {chr(88 + i)}"  # X, Y, Z
        segments.append(_seg(
            t, t + 3, "Taking notes.",
            label, SpeakerRole.OBSERVER,
        ))
        t += 5

    if with_researcher:
        segments.append(_seg(
            t, t + 10, "Can you describe your workflow?",
            "Researcher", SpeakerRole.RESEARCHER,
        ))
        t += 12

    # More participant responses
    for i in range(num_participants):
        label = f"Participant {chr(65 + i)}"
        segments.append(_seg(
            t, t + 20, "Well, I usually start by checking the dashboard.",
            label, SpeakerRole.PARTICIPANT,
        ))
        t += 22

    return segments


class TestMultiParticipantCodes:
    """Test assign_speaker_codes with 2+ participants in one session."""

    def test_two_participants_one_researcher(self) -> None:
        """1 moderator + 2 participants → m1, p1, p2."""
        segments = _make_multi_participant_segments(
            num_participants=2, with_researcher=True,
        )
        label_map, next_pnum = assign_speaker_codes(1, segments)

        assert label_map["Researcher"] == "m1"
        assert label_map["Participant A"] == "p1"
        assert label_map["Participant B"] == "p2"
        assert next_pnum == 3

        # Verify all segments got stamped
        for seg in segments:
            assert seg.speaker_code in ("m1", "p1", "p2")

    def test_three_participants_no_researcher(self) -> None:
        """3 participants, no moderator → p1, p2, p3."""
        segments = _make_multi_participant_segments(
            num_participants=3, with_researcher=False,
        )
        label_map, next_pnum = assign_speaker_codes(1, segments)

        assert label_map["Participant A"] == "p1"
        assert label_map["Participant B"] == "p2"
        assert label_map["Participant C"] == "p3"
        assert next_pnum == 4
        # No moderator codes
        assert all(not v.startswith("m") for v in label_map.values())

    def test_researcher_two_observers_two_participants(self) -> None:
        """1 mod + 2 observers + 2 participants → m1, o1, o2, p1, p2."""
        segments = _make_multi_participant_segments(
            num_participants=2, with_researcher=True, num_observers=2,
        )
        label_map, next_pnum = assign_speaker_codes(1, segments)

        assert label_map["Researcher"] == "m1"
        assert label_map["Observer X"] == "o1"
        assert label_map["Observer Y"] == "o2"
        assert label_map["Participant A"] == "p1"
        assert label_map["Participant B"] == "p2"
        assert next_pnum == 3

    def test_single_participant_unchanged(self) -> None:
        """Backward compat: 1 mod + 1 participant → m1, p1 (same as before)."""
        segments = _make_two_speaker_segments()
        label_map, next_pnum = assign_speaker_codes(1, segments)

        assert label_map["Speaker A"] == "m1"
        assert label_map["Speaker B"] == "p1"
        assert next_pnum == 2


class TestGlobalNumberingAcrossSessions:
    """Participant numbers should be globally unique across sessions."""

    def test_two_sessions_global_numbering(self) -> None:
        """s1 has 2 participants (p1, p2), s2 starts at p3."""
        # Session 1: 1 mod + 2 participants
        s1_segs = _make_multi_participant_segments(
            num_participants=2, with_researcher=True,
        )
        s1_map, next_pnum = assign_speaker_codes(1, s1_segs)

        assert s1_map["Participant A"] == "p1"
        assert s1_map["Participant B"] == "p2"
        assert next_pnum == 3

        # Session 2: 1 mod + 1 participant — starts numbering at 3
        s2_segs = _make_two_speaker_segments()
        s2_map, next_pnum = assign_speaker_codes(next_pnum, s2_segs)

        assert s2_map["Speaker B"] == "p3"
        assert next_pnum == 4

    def test_three_sessions_no_collision(self) -> None:
        """Three sessions, each with different participant counts."""
        next_pnum = 1

        # s1: 3 participants
        s1_segs = _make_multi_participant_segments(num_participants=3, with_researcher=False)
        s1_map, next_pnum = assign_speaker_codes(next_pnum, s1_segs)
        assert set(s1_map.values()) == {"p1", "p2", "p3"}

        # s2: 1 participant
        s2_segs = [_seg(0.0, 30.0, "Solo session.", "Solo", SpeakerRole.PARTICIPANT)]
        s2_map, next_pnum = assign_speaker_codes(next_pnum, s2_segs)
        assert s2_map["Solo"] == "p4"

        # s3: 2 participants + observer
        s3_segs = _make_multi_participant_segments(
            num_participants=2, with_researcher=True, num_observers=1,
        )
        s3_map, next_pnum = assign_speaker_codes(next_pnum, s3_segs)
        assert s3_map["Participant A"] == "p5"
        assert s3_map["Participant B"] == "p6"
        assert s3_map["Observer X"] == "o1"  # observer numbering is per-session
        assert next_pnum == 7


class TestMultiParticipantRoundTrip:
    """Write transcript with multiple participants, load it back."""

    def test_write_parse_roundtrip_multi_participant(self, tmp_path: Path) -> None:
        from bristlenose.pipeline import load_transcripts_from_dir
        from bristlenose.stages.pii_removal import write_cooked_transcripts

        segs = _make_multi_participant_segments(
            num_participants=2, with_researcher=True,
        )
        assign_speaker_codes(1, segs)

        transcript = PiiCleanTranscript(
            participant_id="p1",
            session_id="s1",
            source_file="group_interview.mp4",
            session_date=datetime(2026, 2, 1, 14, 0, 0, tzinfo=timezone.utc),
            duration_seconds=120.0,
            segments=segs,
        )
        write_cooked_transcripts([transcript], tmp_path)

        # Verify file was written
        assert (tmp_path / "s1.txt").exists()

        # Load back
        loaded = load_transcripts_from_dir(tmp_path)
        assert len(loaded) == 1

        lt = loaded[0]
        assert lt.session_id == "s1"
        assert lt.participant_id == "p1"  # first p-code found

        # Check speaker codes survived round-trip
        codes_found = {seg.speaker_code for seg in lt.segments}
        assert "m1" in codes_found
        assert "p1" in codes_found
        assert "p2" in codes_found

        # Check roles survived round-trip
        for seg in lt.segments:
            if seg.speaker_code == "m1":
                assert seg.speaker_role == SpeakerRole.RESEARCHER
            elif seg.speaker_code.startswith("p"):
                # p-codes don't recover a role from the code alone — they're UNKNOWN
                assert seg.speaker_role == SpeakerRole.UNKNOWN

    def test_write_parse_roundtrip_with_observer(self, tmp_path: Path) -> None:
        from bristlenose.pipeline import load_transcripts_from_dir
        from bristlenose.stages.pii_removal import write_cooked_transcripts

        segs = _make_multi_participant_segments(
            num_participants=1, with_researcher=True, num_observers=1,
        )
        assign_speaker_codes(1, segs)

        transcript = PiiCleanTranscript(
            participant_id="p1",
            session_id="s2",
            source_file="observed_session.mp4",
            session_date=datetime(2026, 2, 1, 14, 0, 0, tzinfo=timezone.utc),
            duration_seconds=60.0,
            segments=segs,
        )
        write_cooked_transcripts([transcript], tmp_path)

        loaded = load_transcripts_from_dir(tmp_path)
        assert len(loaded) == 1

        codes_found = {seg.speaker_code for seg in loaded[0].segments}
        assert "m1" in codes_found
        assert "p1" in codes_found
        assert "o1" in codes_found

        for seg in loaded[0].segments:
            if seg.speaker_code == "o1":
                assert seg.speaker_role == SpeakerRole.OBSERVER


class TestMultiParticipantStats:
    """People stats for sessions with multiple participants."""

    def test_two_participants_separate_stats(self) -> None:
        """p1 and p2 in same session get independent people entries."""
        from bristlenose.people import compute_participant_stats

        segs = _make_multi_participant_segments(
            num_participants=2, with_researcher=True,
        )
        assign_speaker_codes(1, segs)

        _dt = datetime(2026, 2, 1, tzinfo=timezone.utc)
        _file = InputFile(
            path=Path("/fake/group_interview.mp4"),
            file_type=FileType.VIDEO,
            created_at=_dt,
            size_bytes=5000,
            duration_seconds=120.0,
        )
        session = InputSession(
            session_id="s1", session_number=1,
            participant_id="p1", participant_number=1,
            session_date=_dt, files=[_file],
        )
        transcript = FullTranscript(
            participant_id="p1",
            session_id="s1",
            source_file="group_interview.mp4",
            session_date=_dt,
            duration_seconds=120.0,
            segments=segs,
        )

        stats = compute_participant_stats([session], [transcript])

        # Both participants should have separate entries
        assert "p1" in stats
        assert "p2" in stats
        assert stats["p1"].words_spoken > 0
        assert stats["p2"].words_spoken > 0

        # Moderator should also have its own entry
        assert "m1" in stats
        assert stats["m1"].words_spoken > 0

        # pct_words should be relative to total participant words (not mod)
        assert stats["p1"].pct_words > 0
        assert stats["p2"].pct_words > 0
        total_pct = stats["p1"].pct_words + stats["p2"].pct_words
        assert abs(total_pct - 100.0) < 0.2  # should sum to ~100%

    def test_global_numbering_stats_across_sessions(self) -> None:
        """Stats for p1, p2 (s1) and p3 (s2) are all separate entries."""
        from bristlenose.people import compute_participant_stats

        # Session 1: 2 participants
        s1_segs = _make_multi_participant_segments(
            num_participants=2, with_researcher=True,
        )
        s1_map, next_pnum = assign_speaker_codes(1, s1_segs)

        _dt = datetime(2026, 2, 1, tzinfo=timezone.utc)
        _file1 = InputFile(
            path=Path("/fake/group.mp4"), file_type=FileType.VIDEO,
            created_at=_dt, size_bytes=5000, duration_seconds=120.0,
        )
        session1 = InputSession(
            session_id="s1", session_number=1,
            participant_id="p1", participant_number=1,
            session_date=_dt, files=[_file1],
        )
        transcript1 = FullTranscript(
            participant_id="p1", session_id="s1",
            source_file="group.mp4", session_date=_dt,
            duration_seconds=120.0, segments=s1_segs,
        )

        # Session 2: 1 participant (starts at p3)
        s2_segs = _make_two_speaker_segments()
        s2_map, next_pnum = assign_speaker_codes(next_pnum, s2_segs)

        _dt2 = datetime(2026, 2, 2, tzinfo=timezone.utc)
        _file2 = InputFile(
            path=Path("/fake/solo.mp4"), file_type=FileType.VIDEO,
            created_at=_dt2, size_bytes=3000, duration_seconds=60.0,
        )
        session2 = InputSession(
            session_id="s2", session_number=2,
            participant_id="p3", participant_number=3,
            session_date=_dt2, files=[_file2],
        )
        transcript2 = FullTranscript(
            participant_id="p3", session_id="s2",
            source_file="solo.mp4", session_date=_dt2,
            duration_seconds=60.0, segments=s2_segs,
        )

        stats = compute_participant_stats(
            [session1, session2], [transcript1, transcript2]
        )

        # All participants should have distinct entries
        assert "p1" in stats
        assert "p2" in stats
        assert "p3" in stats
        # Both moderators (independent per-session)
        assert "m1" in stats
        # All have words
        for code in ("p1", "p2", "p3"):
            assert stats[code].words_spoken > 0
