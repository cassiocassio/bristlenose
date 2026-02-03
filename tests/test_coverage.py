"""Tests for transcript coverage calculation."""

from datetime import datetime, timezone

from bristlenose.coverage import (
    FRAGMENT_THRESHOLD,
    calculate_coverage,
)
from bristlenose.models import (
    ExtractedQuote,
    FullTranscript,
    QuoteType,
    SpeakerRole,
    TranscriptSegment,
)


def _make_segment(
    start: float,
    text: str,
    speaker_code: str = "p1",
    role: SpeakerRole = SpeakerRole.PARTICIPANT,
) -> TranscriptSegment:
    """Helper to create a transcript segment."""
    return TranscriptSegment(
        start_time=start,
        end_time=start + 10,
        text=text,
        speaker_code=speaker_code,
        speaker_role=role,
    )


def _make_transcript(
    session_id: str,
    segments: list[TranscriptSegment],
    participant_id: str = "p1",
) -> FullTranscript:
    """Helper to create a transcript."""
    return FullTranscript(
        session_id=session_id,
        participant_id=participant_id,
        source_file="test.mov",
        session_date=datetime.now(tz=timezone.utc),
        duration_seconds=300.0,
        segments=segments,
    )


def _make_quote(
    session_id: str,
    start: float,
    end: float,
    participant_id: str = "p1",
) -> ExtractedQuote:
    """Helper to create an extracted quote."""
    return ExtractedQuote(
        session_id=session_id,
        participant_id=participant_id,
        start_timecode=start,
        end_timecode=end,
        text="Quote text",
        topic_label="Test topic",
        quote_type=QuoteType.SCREEN_SPECIFIC,
    )


class TestCalculateCoverage:
    """Tests for calculate_coverage function."""

    def test_empty_transcripts(self) -> None:
        """Empty transcripts should return zero percentages."""
        result = calculate_coverage([], [])
        assert result.pct_in_report == 0
        assert result.pct_moderator == 0
        assert result.pct_omitted == 0
        assert result.omitted_by_session == {}

    def test_all_in_quotes(self) -> None:
        """When all participant speech becomes quotes, pct_omitted is 0."""
        segments = [
            _make_segment(0, "This is a test sentence with enough words"),
            _make_segment(20, "Another sentence that is also long enough"),
        ]
        transcripts = [_make_transcript("s1", segments)]
        quotes = [
            _make_quote("s1", 0, 15),
            _make_quote("s1", 20, 35),
        ]

        result = calculate_coverage(transcripts, quotes)

        assert result.pct_in_report == 100
        assert result.pct_omitted == 0
        assert result.pct_moderator == 0

    def test_moderator_percentage(self) -> None:
        """Moderator speech should be counted in pct_moderator."""
        segments = [
            _make_segment(0, "Participant says something here", "p1", SpeakerRole.PARTICIPANT),
            _make_segment(20, "Moderator asks a question here", "m1", SpeakerRole.RESEARCHER),
        ]
        transcripts = [_make_transcript("s1", segments)]
        # Only the participant speech is quoted
        quotes = [_make_quote("s1", 0, 15)]

        result = calculate_coverage(transcripts, quotes)

        # 4 words participant, 5 words moderator = 9 total
        # 4/9 ≈ 44% in report, 5/9 ≈ 56% moderator
        assert result.pct_moderator > 0
        assert result.pct_in_report > 0
        assert result.pct_omitted == 0

    def test_observer_counted_as_moderator(self) -> None:
        """Observer speech should be counted with moderator."""
        segments = [
            _make_segment(0, "Participant speech here", "p1", SpeakerRole.PARTICIPANT),
            _make_segment(20, "Observer comment here", "o1", SpeakerRole.OBSERVER),
        ]
        transcripts = [_make_transcript("s1", segments)]
        quotes = [_make_quote("s1", 0, 15)]

        result = calculate_coverage(transcripts, quotes)

        assert result.pct_moderator > 0

    def test_omitted_segments_tracked(self) -> None:
        """Omitted participant segments should appear in omitted_by_session."""
        segments = [
            _make_segment(0, "This segment becomes a quote in the report"),
            _make_segment(30, "This segment is omitted and should appear"),
        ]
        transcripts = [_make_transcript("s1", segments)]
        # Only first segment is covered
        quotes = [_make_quote("s1", 0, 15)]

        result = calculate_coverage(transcripts, quotes)

        assert "s1" in result.omitted_by_session
        omitted = result.omitted_by_session["s1"]
        assert len(omitted.full_segments) == 1
        assert "This segment is omitted" in omitted.full_segments[0].text

    def test_fragment_threshold(self) -> None:
        """Segments with ≤FRAGMENT_THRESHOLD words go to fragment_counts."""
        segments = [
            _make_segment(0, "This is a long sentence that becomes a quote"),
            _make_segment(30, "Okay"),  # 1 word - fragment
            _make_segment(40, "Yes please"),  # 2 words - fragment
            _make_segment(50, "I agree now"),  # 3 words - fragment
            _make_segment(60, "This is four words"),  # 4 words - full segment
        ]
        transcripts = [_make_transcript("s1", segments)]
        quotes = [_make_quote("s1", 0, 15)]

        result = calculate_coverage(transcripts, quotes)

        omitted = result.omitted_by_session["s1"]
        # 4-word segment should be in full_segments
        assert len(omitted.full_segments) == 1
        assert "four words" in omitted.full_segments[0].text

        # 1, 2, 3-word segments should be in fragment_counts
        assert len(omitted.fragment_counts) == 3
        fragment_texts = [text for text, _ in omitted.fragment_counts]
        assert "Okay" in fragment_texts
        assert "Yes please" in fragment_texts
        assert "I agree now" in fragment_texts

    def test_fragment_repeat_counting(self) -> None:
        """Repeated fragments should be counted."""
        segments = [
            _make_segment(0, "Main content that becomes a quote"),
            _make_segment(30, "Okay"),
            _make_segment(40, "Okay"),
            _make_segment(50, "Okay"),
            _make_segment(60, "Yeah"),
        ]
        transcripts = [_make_transcript("s1", segments)]
        quotes = [_make_quote("s1", 0, 15)]

        result = calculate_coverage(transcripts, quotes)

        omitted = result.omitted_by_session["s1"]
        # Should have Okay (3) and Yeah (1)
        fragment_dict = dict(omitted.fragment_counts)
        assert fragment_dict["Okay"] == 3
        assert fragment_dict["Yeah"] == 1

    def test_multiple_sessions(self) -> None:
        """Coverage should work across multiple sessions."""
        segments1 = [_make_segment(0, "Session one participant speech")]
        segments2 = [_make_segment(0, "Session two participant speech")]
        transcripts = [
            _make_transcript("s1", segments1),
            _make_transcript("s2", segments2, participant_id="p2"),
        ]
        quotes = [
            _make_quote("s1", 0, 15),
            # No quote for s2
        ]

        result = calculate_coverage(transcripts, quotes)

        assert "s2" in result.omitted_by_session
        assert "s1" not in result.omitted_by_session  # s1 fully quoted

    def test_timecode_overlap_detection(self) -> None:
        """Segment is 'in quotes' if start_time falls within any quote range."""
        segments = [
            _make_segment(10, "This should be covered"),  # start=10
            _make_segment(30, "This should not be covered"),  # start=30
        ]
        transcripts = [_make_transcript("s1", segments)]
        # Quote covers 5-20, so segment at 10 is covered
        quotes = [_make_quote("s1", 5, 20)]

        result = calculate_coverage(transcripts, quotes)

        # Only the second segment should be omitted
        assert "s1" in result.omitted_by_session
        omitted = result.omitted_by_session["s1"]
        assert len(omitted.full_segments) == 1
        assert "not be covered" in omitted.full_segments[0].text

    def test_zero_omitted_message(self) -> None:
        """When pct_omitted is 0, omitted_by_session should be empty."""
        segments = [_make_segment(0, "All content becomes a quote")]
        transcripts = [_make_transcript("s1", segments)]
        quotes = [_make_quote("s1", 0, 15)]

        result = calculate_coverage(transcripts, quotes)

        assert result.pct_omitted == 0
        assert result.omitted_by_session == {}

    def test_think_aloud_no_moderator(self) -> None:
        """Think-aloud sessions with no moderator show 0% moderator."""
        segments = [
            _make_segment(0, "Participant talking to themselves about the task"),
            _make_segment(20, "More participant narration here"),
        ]
        transcripts = [_make_transcript("s1", segments)]
        quotes = [_make_quote("s1", 0, 15)]

        result = calculate_coverage(transcripts, quotes)

        assert result.pct_moderator == 0

    def test_omitted_segment_has_timecode(self) -> None:
        """OmittedSegment should have formatted timecode."""
        segments = [
            _make_segment(0, "Quoted content here"),
            _make_segment(125, "Omitted at two minutes five seconds"),
        ]
        transcripts = [_make_transcript("s1", segments)]
        quotes = [_make_quote("s1", 0, 15)]

        result = calculate_coverage(transcripts, quotes)

        omitted = result.omitted_by_session["s1"]
        assert len(omitted.full_segments) == 1
        assert omitted.full_segments[0].timecode == "02:05"
        assert omitted.full_segments[0].timecode_seconds == 125

    def test_omitted_segment_has_speaker_code(self) -> None:
        """OmittedSegment should preserve speaker code."""
        segments = [
            _make_segment(0, "Quoted content here with enough words", "p3"),
            _make_segment(30, "Omitted content here with enough words too", "p3"),
        ]
        transcripts = [_make_transcript("s1", segments, participant_id="p3")]
        quotes = [_make_quote("s1", 0, 15, participant_id="p3")]

        result = calculate_coverage(transcripts, quotes)

        omitted = result.omitted_by_session["s1"]
        assert omitted.full_segments[0].speaker_code == "p3"


class TestFragmentThreshold:
    """Tests for the fragment threshold constant."""

    def test_threshold_is_three(self) -> None:
        """Fragment threshold should be 3 words."""
        assert FRAGMENT_THRESHOLD == 3
