"""Smart-split quote extraction — recovery from output-cap truncation.

Covers the chunked-quote-extraction feature: when an LLM response is truncated
at the model's output ceiling (gpt-4o → 16384, Local → ~2–4K), s09 splits the
session and re-extracts per chunk (Map-Reduce, all-or-nothing per session).

All tests use a mocked LLM — no network, no keys (CI has neither).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from bristlenose.events import CauseCategoryEnum
from bristlenose.llm.client import TruncatedResponseError
from bristlenose.llm.structured import ExtractedQuoteItem, QuoteExtractionResult
from bristlenose.models import (
    ExtractedQuote,
    PiiCleanTranscript,
    QuoteType,
    SessionTopicMap,
    SpeakerRole,
    TopicBoundary,
    TranscriptSegment,
    TransitionType,
)
from bristlenose.stages.s09_quote_extraction import (
    _choose_split_time,
    _dedupe_overlapping_quotes,
    _split_transcript,
    extract_quotes,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncation_error(provider: str = "openai", model: str = "gpt-4o") -> TruncatedResponseError:
    return TruncatedResponseError(
        f"LLM response truncated at the model output cap "
        f"(provider={provider}, model={model}, max_tokens=16384).",
        provider=provider,
        model=model,
        requested_max_tokens=16384,
        model_cap=16384,
    )


def _dense_transcript(
    session_id: str = "s1",
    pid: str = "p1",
    n_segments: int = 10,
    seg_seconds: float = 10.0,
) -> PiiCleanTranscript:
    """A timecoded participant transcript with n evenly-spaced segments."""
    segments = [
        TranscriptSegment(
            start_time=i * seg_seconds,
            end_time=(i + 1) * seg_seconds,
            text=f"This is participant turn number {i} and I have plenty to say.",
            speaker_label="Speaker A",
            speaker_role=SpeakerRole.PARTICIPANT,
            speaker_code=f"{pid}",
            source="whisper",
            segment_index=i,
        )
        for i in range(n_segments)
    ]
    return PiiCleanTranscript(
        participant_id=pid,
        session_id=session_id,
        source_file=f"{session_id}.mp4",
        session_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
        duration_seconds=n_segments * seg_seconds,
        segments=segments,
    )


def _quote_item(
    text: str,
    verbatim: str,
    start_timecode: str = "00:00:10",
    end_timecode: str = "00:00:20",
    topic: str = "Onboarding",
) -> ExtractedQuoteItem:
    return ExtractedQuoteItem(
        start_timecode=start_timecode,
        end_timecode=end_timecode,
        text=text,
        verbatim_excerpt=verbatim,
        topic_label=topic,
        quote_type="screen_specific",
    )


def _empty_topic_map(session_id: str = "s1", pid: str = "p1") -> SessionTopicMap:
    return SessionTopicMap(participant_id=pid, session_id=session_id, boundaries=[])


def _mock_client(analyze_fn) -> AsyncMock:
    client = AsyncMock()
    client.provider = "openai"
    client.analyze = analyze_fn
    return client


# ---------------------------------------------------------------------------
# Recursion behaviour (end-to-end through extract_quotes, mocked LLM)
# ---------------------------------------------------------------------------


class TestTruncationSplitSuccess:
    @pytest.mark.asyncio
    async def test_truncate_once_then_split_succeeds(self) -> None:
        """First pass truncates; the two chunks succeed; quotes merged."""
        calls = {"n": 0}

        async def mock_analyze(system_prompt, user_prompt, response_model, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _truncation_error()
            # Each chunk returns one distinct quote.
            text = "I really enjoy this flow and would use it often again"
            verbatim = f"chunk-{calls['n']} verbatim words here please"
            return QuoteExtractionResult(quotes=[_quote_item(text, verbatim)])

        transcript = _dense_transcript(n_segments=10)
        client = _mock_client(mock_analyze)

        result, outcome = await extract_quotes(
            [transcript], [_empty_topic_map()], client, concurrency=1
        )

        # One full-pass truncation + two chunk passes = 3 analyze calls.
        assert calls["n"] == 3
        assert outcome.succeeded == 1
        assert outcome.failed == []
        # Two distinct quotes survive (no dedup collision).
        assert len(result) == 2
        verbatims = [q.verbatim_excerpt for q in result]
        assert len(set(verbatims)) == 2


class TestDepthExhaustion:
    @pytest.mark.asyncio
    async def test_depth3_exhaustion_records_one_failure(self) -> None:
        """Every pass truncates → one OUTPUT_TRUNCATED StageFailure, bounded calls."""
        calls = {"n": 0}

        async def mock_analyze(system_prompt, user_prompt, response_model, **kw):
            calls["n"] += 1
            raise _truncation_error()

        transcript = _dense_transcript(n_segments=16)
        client = _mock_client(mock_analyze)

        result, outcome = await extract_quotes(
            [transcript], [_empty_topic_map()], client, concurrency=1
        )

        assert result == []
        # All-or-nothing short-circuits the first failing branch: one pass per
        # depth 0..3 = 4 calls, NOT 2**3 leaf calls.
        assert calls["n"] == 4
        assert len(outcome.failed) == 1
        assert outcome.failed[0].cause.category is CauseCategoryEnum.OUTPUT_TRUNCATED

    @pytest.mark.asyncio
    async def test_two_sessions_exhausting_produce_two_failures_not_eight(self) -> None:
        """Finding 10: one StageFailure per exhausted session, not per chunk."""
        async def mock_analyze(system_prompt, user_prompt, response_model, **kw):
            raise _truncation_error()

        transcripts = [
            _dense_transcript(session_id="s1", pid="p1", n_segments=16),
            _dense_transcript(session_id="s2", pid="p2", n_segments=16),
        ]
        topic_maps = [
            _empty_topic_map("s1", "p1"),
            _empty_topic_map("s2", "p2"),
        ]
        client = _mock_client(mock_analyze)

        result, outcome = await extract_quotes(
            transcripts, topic_maps, client, concurrency=1
        )

        assert result == []
        assert len(outcome.failed) == 2
        assert all(
            f.cause.category is CauseCategoryEnum.OUTPUT_TRUNCATED
            for f in outcome.failed
        )


class TestEmptyChunkPathology:
    @pytest.mark.asyncio
    async def test_empty_chunk_records_failure_not_silent_zero(self) -> None:
        """A split that yields a participant-free chunk fails loudly (Finding 7)."""
        # Only the first segment is the participant; the index-based halves
        # split puts the all-moderator tail in the right chunk → no participant
        # speech there.
        segments = [
            TranscriptSegment(
                start_time=0.0, end_time=10.0,
                text="I really love the dashboard and use it every single day.",
                speaker_role=SpeakerRole.PARTICIPANT, speaker_code="p1",
                source="whisper", segment_index=0,
            ),
            TranscriptSegment(
                start_time=10.0, end_time=20.0,
                text="And what did you think about the settings screen overall?",
                speaker_role=SpeakerRole.RESEARCHER, speaker_code="m1",
                source="whisper", segment_index=1,
            ),
            TranscriptSegment(
                start_time=20.0, end_time=30.0,
                text="Could you say a little more about that experience please?",
                speaker_role=SpeakerRole.RESEARCHER, speaker_code="m1",
                source="whisper", segment_index=2,
            ),
            TranscriptSegment(
                start_time=30.0, end_time=40.0,
                text="Interesting — and how did that compare to what you expected?",
                speaker_role=SpeakerRole.RESEARCHER, speaker_code="m1",
                source="whisper", segment_index=3,
            ),
        ]
        transcript = PiiCleanTranscript(
            participant_id="p1", session_id="s1", source_file="s1.mp4",
            session_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
            duration_seconds=40.0, segments=segments,
        )

        async def mock_analyze(system_prompt, user_prompt, response_model, **kw):
            raise _truncation_error()  # force the split path

        client = _mock_client(mock_analyze)
        result, outcome = await extract_quotes(
            [transcript], [_empty_topic_map()], client, concurrency=1
        )

        # The split raised ValueError("empty chunk"); recorded as a failure,
        # never a silent zero-quote success.
        assert result == []
        assert outcome.succeeded == 0
        assert len(outcome.failed) == 1

    def test_split_transcript_raises_empty_chunk(self) -> None:
        """_split_transcript raises ValueError when a half has no participant."""
        # One participant segment then an all-moderator tail: the index-based
        # halves split lands the tail in a participant-free right chunk.
        segments = [
            TranscriptSegment(
                start_time=0.0, end_time=10.0, text="I love it so much honestly.",
                speaker_role=SpeakerRole.PARTICIPANT, speaker_code="p1",
                source="whisper", segment_index=0,
            ),
            TranscriptSegment(
                start_time=10.0, end_time=20.0, text="What did you make of that?",
                speaker_role=SpeakerRole.RESEARCHER, speaker_code="m1",
                source="whisper", segment_index=1,
            ),
            TranscriptSegment(
                start_time=20.0, end_time=30.0, text="And then what happened next?",
                speaker_role=SpeakerRole.RESEARCHER, speaker_code="m1",
                source="whisper", segment_index=2,
            ),
            TranscriptSegment(
                start_time=30.0, end_time=40.0, text="How did that feel for you?",
                speaker_role=SpeakerRole.RESEARCHER, speaker_code="m1",
                source="whisper", segment_index=3,
            ),
        ]
        transcript = PiiCleanTranscript(
            participant_id="p1", session_id="s1", source_file="s1.mp4",
            session_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
            duration_seconds=40.0, segments=segments,
        )
        with pytest.raises(ValueError, match="empty chunk"):
            _split_transcript(transcript, _empty_topic_map(), 0.1)


# ---------------------------------------------------------------------------
# Dedup + segment-index stability
# ---------------------------------------------------------------------------


class TestVerbatimDedup:
    @pytest.mark.asyncio
    async def test_same_verbatim_different_text_dedupes_to_one(self) -> None:
        """Overlap-band quotes with identical verbatim collapse to one."""
        calls = {"n": 0}
        shared_verbatim = "i had pizza but then switched to fruit"

        async def mock_analyze(system_prompt, user_prompt, response_model, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _truncation_error()
            # Both chunks see the seam quote; same verbatim, different cleanup.
            text = (
                "I had pizza but then switched to fruit"
                if calls["n"] == 2
                else "I had pizza, but then... switched to fruit"
            )
            return QuoteExtractionResult(quotes=[_quote_item(text, shared_verbatim)])

        transcript = _dense_transcript(n_segments=10)
        client = _mock_client(mock_analyze)

        result, outcome = await extract_quotes(
            [transcript], [_empty_topic_map()], client, concurrency=1
        )

        assert outcome.succeeded == 1
        assert len(result) == 1  # deduped on verbatim_excerpt

    def test_single_occurrence_quote_survives_merge(self) -> None:
        """A seam quote seen in only one chunk (no collision) is not dropped."""
        full = _dense_transcript(n_segments=6).segments
        quotes = [
            ExtractedQuote(
                participant_id="p1", start_timecode=10.0, end_timecode=20.0,
                text="alpha words that the participant said", verbatim_excerpt="alpha unique",
                topic_label="t", quote_type=QuoteType.SCREEN_SPECIFIC, segment_index=-1,
            ),
            ExtractedQuote(
                participant_id="p1", start_timecode=40.0, end_timecode=50.0,
                text="beta words that the participant said", verbatim_excerpt="beta unique",
                topic_label="t", quote_type=QuoteType.SCREEN_SPECIFIC, segment_index=-1,
            ),
        ]
        merged = _dedupe_overlapping_quotes(quotes, full)
        assert len(merged) == 2
        assert {q.verbatim_excerpt for q in merged} == {"alpha unique", "beta unique"}

    def test_dedupe_keeps_empty_verbatim_quotes(self) -> None:
        """Quotes with empty verbatim can't be keyed — all are kept."""
        full = _dense_transcript(n_segments=5).segments
        quotes = [
            ExtractedQuote(
                participant_id="p1", start_timecode=10.0, end_timecode=20.0,
                text="first", verbatim_excerpt="", topic_label="t",
                quote_type=QuoteType.SCREEN_SPECIFIC, segment_index=-1,
            ),
            ExtractedQuote(
                participant_id="p1", start_timecode=30.0, end_timecode=40.0,
                text="second", verbatim_excerpt="", topic_label="t",
                quote_type=QuoteType.SCREEN_SPECIFIC, segment_index=-1,
            ),
        ]
        merged = _dedupe_overlapping_quotes(quotes, full)
        assert len(merged) == 2


class TestSegmentIndexStability:
    def test_segment_index_reresolved_against_full_transcript(self) -> None:
        """Merged quotes get unique, full-transcript-relative segment ordinals."""
        full = _dense_transcript(n_segments=6).segments  # start_times 0,10,..,50
        # Simulate chunk output carrying stale/duplicate segment indices.
        quotes = [
            ExtractedQuote(
                participant_id="p1", start_timecode=10.0, end_timecode=20.0,
                text="alpha words here that count", verbatim_excerpt="alpha",
                topic_label="t", quote_type=QuoteType.SCREEN_SPECIFIC,
                segment_index=0,
            ),
            ExtractedQuote(
                participant_id="p1", start_timecode=40.0, end_timecode=50.0,
                text="beta words here that count", verbatim_excerpt="beta",
                topic_label="t", quote_type=QuoteType.SCREEN_SPECIFIC,
                segment_index=0,
            ),
        ]
        merged = _dedupe_overlapping_quotes(quotes, full)
        indices = [q.segment_index for q in merged]
        # t=10 → segment_index 1; t=40 → segment_index 4 (against the full list)
        assert indices == [1, 4]
        assert len(set(indices)) == len(indices)


# ---------------------------------------------------------------------------
# Cause message (re-identification boundary + stage labelling)
# ---------------------------------------------------------------------------


class TestTruncationCauseMessage:
    def test_output_truncated_cause_message_is_leak_safe(self) -> None:
        """The built Cause carries actionable, leak-safe, hint-free copy."""
        from bristlenose.run_lifecycle import _build_cause

        cause = _build_cause(
            _truncation_error(), stage="quote_extraction", provider="openai"
        )
        assert cause.category is CauseCategoryEnum.OUTPUT_TRUNCATED
        msg = cause.message or ""
        # Not the misleading old hint (clamp caps gpt-4o back to 16384).
        assert "BRISTLENOSE_LLM_MAX_TOKENS" not in msg
        # Constant actionable copy — no provider response body / prompt fragment.
        assert "--llm" in msg and "--model" in msg

    def test_non_s09_truncation_not_mislabelled_quote_extraction(self) -> None:
        """A truncation from another stage isn't labelled 'Quote extraction'."""
        from bristlenose.run_lifecycle import _build_cause

        cause = _build_cause(
            _truncation_error(), stage="topic_segmentation", provider="openai"
        )
        assert cause.category is CauseCategoryEnum.OUTPUT_TRUNCATED
        msg = cause.message or ""
        assert "Quote extraction" not in msg
        assert "topic_segmentation" in msg


# ---------------------------------------------------------------------------
# Boundary picker (pure, no LLM)
# ---------------------------------------------------------------------------


def _boundary(t: float, conf: float, label: str = "topic") -> TopicBoundary:
    return TopicBoundary(
        timecode_seconds=t,
        topic_label=label,
        transition_type=TransitionType.TOPIC_SHIFT,
        confidence=conf,
    )


class TestBoundaryPicker:
    def test_confidence_tiebreaker(self) -> None:
        """Among eligible boundaries, the highest confidence wins."""
        tm = SessionTopicMap(
            participant_id="p1", session_id="s1",
            boundaries=[_boundary(40.0, 0.5), _boundary(60.0, 0.9)],
        )
        segments = _dense_transcript(n_segments=10).segments  # span 0..100
        split_time, reason = _choose_split_time(tm, segments, 0.0, 100.0, 100.0)
        assert reason == "topic"
        assert split_time == 60.0

    def test_longest_region_tiebreaker(self) -> None:
        """Equal confidence → the boundary bordering the longest run wins."""
        # 30 borders a 10s region on its right; 40 borders a 60s region.
        tm = SessionTopicMap(
            participant_id="p1", session_id="s1",
            boundaries=[_boundary(30.0, 0.8), _boundary(40.0, 0.8)],
        )
        segments = _dense_transcript(n_segments=10).segments  # span 0..100
        split_time, reason = _choose_split_time(tm, segments, 0.0, 100.0, 100.0)
        assert reason == "topic"
        assert split_time == 40.0

    def test_no_eligible_boundary_falls_back_to_halves(self) -> None:
        """No boundary in the middle 60% → mechanical halves."""
        # Both boundaries sit in the trivially-small outer 20% bands.
        tm = SessionTopicMap(
            participant_id="p1", session_id="s1",
            boundaries=[_boundary(5.0, 0.9), _boundary(95.0, 0.9)],
        )
        segments = _dense_transcript(n_segments=10).segments  # span 0..100
        split_time, reason = _choose_split_time(tm, segments, 0.0, 100.0, 100.0)
        assert reason == "halves"
        # Segment-count midpoint of 10 segments → segments[5].start_time = 50.
        assert split_time == 50.0


# ---------------------------------------------------------------------------
# Integration: large synthetic transcript recovers without abandoning
# ---------------------------------------------------------------------------


class TestLargeTranscriptIntegration:
    @pytest.mark.asyncio
    async def test_400_segment_session_recovers_after_truncation(self) -> None:
        """A dense ~400-segment session truncates once then completes."""
        calls = {"n": 0}

        async def mock_analyze(system_prompt, user_prompt, response_model, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _truncation_error()
            text = "I found this part genuinely useful and clear to follow"
            verbatim = f"unique-verbatim-{calls['n']} from chunk text body"
            return QuoteExtractionResult(quotes=[_quote_item(text, verbatim)])

        transcript = _dense_transcript(n_segments=400, seg_seconds=3.0)
        client = _mock_client(mock_analyze)

        result, outcome = await extract_quotes(
            [transcript], [_empty_topic_map()], client, concurrency=1
        )

        assert outcome.succeeded == 1
        assert outcome.failed == []
        assert len(result) >= 1
