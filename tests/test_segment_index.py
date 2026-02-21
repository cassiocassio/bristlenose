"""Tests for segment_index — ordinal assignment and quote resolution."""

from __future__ import annotations

from bristlenose.models import (
    ExtractedQuote,
    InputSession,
    QuoteType,
    ScreenCluster,
    Sentiment,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.stages.merge_transcript import merge_transcripts
from bristlenose.stages.quote_extraction import _resolve_segment_index

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seg(start: float, end: float, text: str = "hello", idx: int = -1) -> TranscriptSegment:
    return TranscriptSegment(
        start_time=start,
        end_time=end,
        text=text,
        speaker_role=SpeakerRole.PARTICIPANT,
        speaker_code="p1",
        segment_index=idx,
    )


# ---------------------------------------------------------------------------
# _resolve_segment_index
# ---------------------------------------------------------------------------


class TestResolveSegmentIndex:

    def test_empty_segments(self) -> None:
        assert _resolve_segment_index(10.0, []) == -1

    def test_non_timecoded_all_zero(self) -> None:
        """Non-timecoded transcripts (all start_time == 0.0) return -1."""
        segments = [_seg(0.0, 0.0, idx=0), _seg(0.0, 0.0, idx=1)]
        assert _resolve_segment_index(0.0, segments) == -1

    def test_exact_match_first_segment(self) -> None:
        segments = [_seg(10.0, 20.0, idx=0), _seg(25.0, 35.0, idx=1)]
        assert _resolve_segment_index(10.0, segments) == 0

    def test_exact_match_second_segment(self) -> None:
        segments = [_seg(10.0, 20.0, idx=0), _seg(25.0, 35.0, idx=1)]
        assert _resolve_segment_index(25.0, segments) == 1

    def test_within_segment_range(self) -> None:
        segments = [_seg(10.0, 20.0, idx=0), _seg(25.0, 35.0, idx=1)]
        assert _resolve_segment_index(15.0, segments) == 0

    def test_between_segments_within_tolerance(self) -> None:
        """Quote starts in the gap between segments but within 5s tolerance."""
        segments = [_seg(10.0, 20.0, idx=0), _seg(30.0, 40.0, idx=1)]
        # 22.0 is 2s after seg[0].end_time (20.0), within 5s tolerance
        assert _resolve_segment_index(22.0, segments) == 0

    def test_between_segments_beyond_tolerance(self) -> None:
        """Quote starts too far after a segment's end_time."""
        segments = [_seg(10.0, 20.0, idx=0), _seg(50.0, 60.0, idx=1)]
        # 30.0 is 10s after seg[0].end_time (20.0), beyond 5s tolerance
        assert _resolve_segment_index(30.0, segments) == -1

    def test_before_first_segment(self) -> None:
        segments = [_seg(10.0, 20.0, idx=0)]
        assert _resolve_segment_index(5.0, segments) == -1

    def test_single_segment(self) -> None:
        segments = [_seg(10.0, 20.0, idx=0)]
        assert _resolve_segment_index(15.0, segments) == 0

    def test_last_segment(self) -> None:
        segments = [
            _seg(10.0, 20.0, idx=0),
            _seg(25.0, 35.0, idx=1),
            _seg(40.0, 50.0, idx=2),
        ]
        assert _resolve_segment_index(45.0, segments) == 2

    def test_uses_segment_index_not_list_position(self) -> None:
        """The function returns seg.segment_index, not the list position."""
        segments = [_seg(10.0, 20.0, idx=5), _seg(25.0, 35.0, idx=6)]
        assert _resolve_segment_index(15.0, segments) == 5
        assert _resolve_segment_index(30.0, segments) == 6


# ---------------------------------------------------------------------------
# merge_transcripts assigns segment_index
# ---------------------------------------------------------------------------


class TestMergeAssignsIndex:

    def test_segments_get_sequential_index(self) -> None:
        """After merge, segments have sequential segment_index starting from 0."""
        from datetime import datetime

        sessions = [
            InputSession(
                session_id="s1",
                session_number=1,
                participant_id="p1",
                participant_number=1,
                session_date=datetime(2026, 1, 1),
                files=[],
            ),
        ]
        segs = {
            "s1": [
                _seg(0.0, 5.0, "hello"),
                _seg(10.0, 15.0, "world"),
                _seg(20.0, 25.0, "foo"),
            ],
        }
        result = merge_transcripts(sessions, segs)
        assert len(result) == 1
        transcript = result[0]
        for i, seg in enumerate(transcript.segments):
            assert seg.segment_index == i, f"segment {i} has index {seg.segment_index}"

    def test_merged_same_speaker_reindexed(self) -> None:
        """Adjacent same-speaker segments are merged; indices are reassigned."""
        from datetime import datetime

        sessions = [
            InputSession(
                session_id="s1",
                session_number=1,
                participant_id="p1",
                participant_number=1,
                session_date=datetime(2026, 1, 1),
                files=[],
            ),
        ]
        # Two segments close enough to be merged (same speaker, gap < 2s)
        segs = {
            "s1": [
                TranscriptSegment(
                    start_time=0.0, end_time=5.0, text="hello",
                    speaker_code="p1", speaker_role=SpeakerRole.PARTICIPANT,
                ),
                TranscriptSegment(
                    start_time=5.5, end_time=10.0, text="world",
                    speaker_code="p1", speaker_role=SpeakerRole.PARTICIPANT,
                ),
                TranscriptSegment(
                    start_time=20.0, end_time=25.0, text="separate",
                    speaker_code="m1", speaker_role=SpeakerRole.RESEARCHER,
                ),
            ],
        }
        result = merge_transcripts(sessions, segs)
        transcript = result[0]
        # First two may merge into one; third is separate
        for i, seg in enumerate(transcript.segments):
            assert seg.segment_index == i


# ---------------------------------------------------------------------------
# ExtractedQuote backward compat
# ---------------------------------------------------------------------------


class TestBackwardCompat:

    def test_quote_defaults_to_negative_one(self) -> None:
        q = ExtractedQuote(
            participant_id="p1",
            start_timecode=10.0,
            end_timecode=15.0,
            text="hello",
            topic_label="Test",
            quote_type=QuoteType.SCREEN_SPECIFIC,
        )
        assert q.segment_index == -1

    def test_segment_defaults_to_negative_one(self) -> None:
        s = TranscriptSegment(start_time=0.0, end_time=5.0, text="hello")
        assert s.segment_index == -1

    def test_quote_json_roundtrip_with_field(self) -> None:
        q = ExtractedQuote(
            participant_id="p1",
            start_timecode=10.0,
            end_timecode=15.0,
            text="hello",
            topic_label="Test",
            quote_type=QuoteType.SCREEN_SPECIFIC,
            segment_index=42,
        )
        data = q.model_dump()
        assert data["segment_index"] == 42
        q2 = ExtractedQuote.model_validate(data)
        assert q2.segment_index == 42

    def test_quote_json_roundtrip_without_field(self) -> None:
        """Old JSON without segment_index deserializes with default -1."""
        data = {
            "participant_id": "p1",
            "start_timecode": 10.0,
            "end_timecode": 15.0,
            "text": "hello",
            "topic_label": "Test",
            "quote_type": "screen_specific",
        }
        q = ExtractedQuote.model_validate(data)
        assert q.segment_index == -1


# ---------------------------------------------------------------------------
# Signal threading
# ---------------------------------------------------------------------------


class TestSignalThreading:

    def test_detect_signals_carries_segment_index(self) -> None:
        """segment_index flows through detect_signals into SignalQuote."""
        from bristlenose.analysis.matrix import build_section_matrix, build_theme_matrix
        from bristlenose.analysis.signals import detect_signals

        quotes = [
            ExtractedQuote(
                session_id="s1",
                participant_id=f"p{i}",
                start_timecode=float(i * 10),
                end_timecode=float(i * 10 + 5),
                text=f"Quote {i}",
                topic_label="Checkout",
                quote_type=QuoteType.SCREEN_SPECIFIC,
                sentiment=Sentiment.FRUSTRATION,
                intensity=2,
                segment_index=i * 3,
            )
            for i in range(1, 4)
        ]
        clusters = [
            ScreenCluster(
                screen_label="Checkout", description="", display_order=1, quotes=quotes,
            ),
        ]
        sm = build_section_matrix(clusters)
        tm = build_theme_matrix([])
        result = detect_signals(sm, tm, clusters, [], total_participants=5)
        assert len(result.signals) > 0
        sig = result.signals[0]
        for sq in sig.quotes:
            assert sq.segment_index >= 0, "segment_index should be carried through"
