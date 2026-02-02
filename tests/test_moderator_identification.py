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
        label_map = assign_speaker_codes("p1", segments)

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
        label_map = assign_speaker_codes("p1", segments)

        assert label_map["Speaker A"] == "m1"
        assert label_map["Speaker B"] == "m2"
        assert label_map["Speaker C"] == "p1"

    def test_observer_gets_o_prefix(self) -> None:
        segments = [
            _seg(0.0, 10.0, "Let's begin.", "Speaker A", SpeakerRole.RESEARCHER),
            _seg(11.0, 30.0, "Sure.", "Speaker B", SpeakerRole.PARTICIPANT),
            _seg(31.0, 33.0, "Mm-hmm.", "Speaker C", SpeakerRole.OBSERVER),
        ]
        label_map = assign_speaker_codes("p2", segments)

        assert label_map["Speaker A"] == "m1"
        assert label_map["Speaker B"] == "p2"
        assert label_map["Speaker C"] == "o1"

    def test_single_speaker_gets_participant_id(self) -> None:
        segments = [
            _seg(0.0, 30.0, "I was talking to myself.",
                 "Speaker A", SpeakerRole.PARTICIPANT),
        ]
        label_map = assign_speaker_codes("p3", segments)

        assert label_map["Speaker A"] == "p3"
        assert segments[0].speaker_code == "p3"

    def test_unknown_role_falls_back_to_participant_id(self) -> None:
        segments = [
            _seg(0.0, 15.0, "Hello.", "Speaker A", SpeakerRole.UNKNOWN),
        ]
        label_map = assign_speaker_codes("p1", segments)

        assert label_map["Speaker A"] == "p1"

    def test_none_speaker_label_treated_as_unknown(self) -> None:
        segments = [
            TranscriptSegment(
                start_time=0.0, end_time=10.0, text="No label.",
                speaker_label=None, speaker_role=SpeakerRole.PARTICIPANT,
                source="whisper",
            ),
        ]
        label_map = assign_speaker_codes("p1", segments)

        assert label_map["Unknown"] == "p1"
        assert segments[0].speaker_code == "p1"


# ---------------------------------------------------------------------------
# Transcript writing round-trip
# ---------------------------------------------------------------------------


class TestTranscriptRoundTrip:
    def _make_transcript_with_moderator(self) -> FullTranscript:
        segs = _make_two_speaker_segments()
        assign_speaker_codes("p1", segs)
        return FullTranscript(
            participant_id="p1",
            source_file="interview_01.mp4",
            session_date=datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc),
            duration_seconds=60.0,
            segments=segs,
        )

    def test_raw_txt_contains_moderator_codes(self, tmp_path: Path) -> None:
        from bristlenose.stages.merge_transcript import write_raw_transcripts

        transcript = self._make_transcript_with_moderator()
        write_raw_transcripts([transcript], tmp_path)
        content = (tmp_path / "p1_raw.txt").read_text()

        assert "[00:00] [m1]" in content
        assert "[00:11] [p1]" in content
        assert "[00:31] [m1]" in content
        assert "[00:41] [p1]" in content

    def test_raw_md_contains_moderator_codes(self, tmp_path: Path) -> None:
        from bristlenose.stages.merge_transcript import write_raw_transcripts_md

        transcript = self._make_transcript_with_moderator()
        write_raw_transcripts_md([transcript], tmp_path)
        content = (tmp_path / "p1_raw.md").read_text()

        assert "**[00:00] m1**" in content
        assert "**[00:11] p1**" in content

    def test_cooked_txt_contains_moderator_codes(self, tmp_path: Path) -> None:
        from bristlenose.stages.pii_removal import write_cooked_transcripts

        segs = _make_two_speaker_segments()
        assign_speaker_codes("p1", segs)
        transcript = PiiCleanTranscript(
            participant_id="p1",
            source_file="interview_01.mp4",
            session_date=datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc),
            duration_seconds=60.0,
            segments=segs,
        )
        write_cooked_transcripts([transcript], tmp_path)
        content = (tmp_path / "p1_cooked.txt").read_text()

        assert "[00:00] [m1]" in content
        assert "[00:11] [p1]" in content

    def test_cooked_md_contains_moderator_codes(self, tmp_path: Path) -> None:
        from bristlenose.stages.pii_removal import write_cooked_transcripts_md

        segs = _make_two_speaker_segments()
        assign_speaker_codes("p1", segs)
        transcript = PiiCleanTranscript(
            participant_id="p1",
            source_file="interview_01.mp4",
            session_date=datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc),
            duration_seconds=60.0,
            segments=segs,
        )
        write_cooked_transcripts_md([transcript], tmp_path)
        content = (tmp_path / "p1_cooked.md").read_text()

        assert "**[00:00] m1**" in content
        assert "**[00:11] p1**" in content

    def test_load_recovers_moderator_role(self, tmp_path: Path) -> None:
        """Write with [m1]/[p1] codes, load back, verify roles and codes."""
        from bristlenose.pipeline import load_transcripts_from_dir
        from bristlenose.stages.pii_removal import write_cooked_transcripts

        segs = _make_two_speaker_segments()
        assign_speaker_codes("p1", segs)
        transcript = PiiCleanTranscript(
            participant_id="p1",
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
        (tmp_path / "p1_cooked.txt").write_text(content, encoding="utf-8")
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
        assign_speaker_codes("p1", segs)

        _dt = datetime(2026, 1, 20, tzinfo=timezone.utc)
        _file = InputFile(
            path=Path("/fake/interview.mp4"),
            file_type=FileType.VIDEO,
            created_at=_dt,
            size_bytes=1000,
            duration_seconds=60.0,
        )
        session = InputSession(
            participant_id="p1", participant_number=1,
            session_date=_dt, files=[_file],
        )
        transcript = FullTranscript(
            participant_id="p1",
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
        assign_speaker_codes("p1", segs)

        _dt = datetime(2026, 1, 20, tzinfo=timezone.utc)
        _file = InputFile(
            path=Path("/fake/interview.mp4"),
            file_type=FileType.VIDEO,
            created_at=_dt,
            size_bytes=1000,
            duration_seconds=30.0,
        )
        session = InputSession(
            participant_id="p1", participant_number=1,
            session_date=_dt, files=[_file],
        )
        transcript = FullTranscript(
            participant_id="p1",
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
        "# Transcript: p1\n"
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

        raw_dir = tmp_path / "raw_transcripts"
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "p1_raw.txt").write_text(self._MODERATOR_TRANSCRIPT, encoding="utf-8")

        render_transcript_pages(
            sessions=[], project_name="Test", output_dir=tmp_path, people=people,
        )
        return (tmp_path / "transcript_p1.html").read_text(encoding="utf-8")

    def test_moderator_segments_have_css_class(self, tmp_path: Path) -> None:
        html = self._setup_and_render(tmp_path)
        assert "segment-moderator" in html

    def test_participant_segments_no_moderator_class(self, tmp_path: Path) -> None:
        html = self._setup_and_render(tmp_path)
        # Participant segments should not have segment-moderator class
        lines = [l for l in html.split("\n") if "been using this" in l]
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

        assert 'data-participant="m1">Dr Smith:</span>' in html
        assert 'data-participant="p1">Sarah:</span>' in html

    def test_moderator_data_participant_attribute(self, tmp_path: Path) -> None:
        html = self._setup_and_render(tmp_path)
        assert 'data-participant="m1"' in html
        assert 'data-participant="p1"' in html

    def test_old_format_renders_without_moderator_class(self, tmp_path: Path) -> None:
        """Old transcripts (all [p1]) render without segment-moderator."""
        from bristlenose.stages.render_html import render_transcript_pages

        old_transcript = (
            "# Transcript: p1\n"
            "# Source: interview.mp4\n"
            "# Date: 2026-01-20\n"
            "# Duration: 00:01:00\n"
            "\n"
            "[00:00] [p1] Hello.\n"
            "\n"
            "[00:10] [p1] Goodbye.\n"
        )
        raw_dir = tmp_path / "raw_transcripts"
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "p1_raw.txt").write_text(old_transcript, encoding="utf-8")

        render_transcript_pages(
            sessions=[], project_name="Test", output_dir=tmp_path,
        )
        html = (tmp_path / "transcript_p1.html").read_text(encoding="utf-8")

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
