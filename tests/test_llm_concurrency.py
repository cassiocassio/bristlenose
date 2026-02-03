"""Tests for LLM concurrency: semaphore-bounded asyncio.gather in stages 5b, 8, 9, 10+11."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from bristlenose.models import (
    PiiCleanTranscript,
    SessionTopicMap,
    SpeakerRole,
    TranscriptSegment,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_transcript(pid: str) -> PiiCleanTranscript:
    """Build a minimal PiiCleanTranscript for testing."""
    return PiiCleanTranscript(
        participant_id=pid,
        session_id=f"s-{pid}",
        source_file=f"{pid}.mp4",
        session_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
        duration_seconds=120.0,
        segments=[
            TranscriptSegment(
                start_time=0.0,
                end_time=60.0,
                text="This product is amazing, I use it every day.",
                speaker_label="Speaker A",
                speaker_role=SpeakerRole.PARTICIPANT,
                source="whisper",
            ),
            TranscriptSegment(
                start_time=60.0,
                end_time=120.0,
                text="But the settings page is confusing.",
                speaker_label="Speaker A",
                speaker_role=SpeakerRole.PARTICIPANT,
                source="whisper",
            ),
        ],
    )


def _make_segments(pid: str) -> list[TranscriptSegment]:
    """Build minimal segments for speaker identification testing."""
    return [
        TranscriptSegment(
            start_time=0.0,
            end_time=30.0,
            text="So tell me about your experience with the app.",
            speaker_label="Speaker A",
            speaker_role=SpeakerRole.RESEARCHER,
            source="whisper",
        ),
        TranscriptSegment(
            start_time=31.0,
            end_time=60.0,
            text="I really love the dashboard but hate the search.",
            speaker_label="Speaker B",
            speaker_role=SpeakerRole.PARTICIPANT,
            source="whisper",
        ),
    ]


# ---------------------------------------------------------------------------
# Stage 8: topic segmentation concurrency
# ---------------------------------------------------------------------------

class TestTopicSegmentationConcurrency:
    """Verify segment_topics runs concurrently with concurrency > 1."""

    @pytest.mark.asyncio
    async def test_sequential_when_concurrency_1(self) -> None:
        """With concurrency=1, calls execute sequentially."""
        from bristlenose.stages.topic_segmentation import segment_topics

        call_times: list[tuple[str, float, float]] = []

        async def mock_analyze(system_prompt, user_prompt, response_model, **kw):
            pid = "unknown"
            for t in transcripts:
                if t.participant_id in user_prompt:
                    pid = t.participant_id
                    break
            start = time.monotonic()
            await asyncio.sleep(0.05)
            end = time.monotonic()
            call_times.append((pid, start, end))
            # Return an empty result
            from bristlenose.llm.structured import TopicSegmentationResult
            return TopicSegmentationResult(boundaries=[])

        transcripts = [_make_transcript(f"p{i}") for i in range(1, 5)]
        mock_client = AsyncMock()
        mock_client.analyze = mock_analyze

        result = await segment_topics(transcripts, mock_client, concurrency=1)

        assert len(result) == 4
        # With concurrency=1, each call should start after the previous ends
        for i in range(1, len(call_times)):
            assert call_times[i][1] >= call_times[i - 1][2] - 0.01

    @pytest.mark.asyncio
    async def test_concurrent_when_concurrency_3(self) -> None:
        """With concurrency=3, up to 3 calls run in parallel."""
        from bristlenose.stages.topic_segmentation import segment_topics

        active_count = 0
        max_active = 0

        async def mock_analyze(system_prompt, user_prompt, response_model, **kw):
            nonlocal active_count, max_active
            active_count += 1
            max_active = max(max_active, active_count)
            await asyncio.sleep(0.05)
            active_count -= 1
            from bristlenose.llm.structured import TopicSegmentationResult
            return TopicSegmentationResult(boundaries=[])

        transcripts = [_make_transcript(f"p{i}") for i in range(1, 7)]
        mock_client = AsyncMock()
        mock_client.analyze = mock_analyze

        result = await segment_topics(transcripts, mock_client, concurrency=3)

        assert len(result) == 6
        assert max_active <= 3, f"Max concurrent calls was {max_active}, expected <= 3"
        assert max_active >= 2, f"Expected at least 2 concurrent calls, got {max_active}"

    @pytest.mark.asyncio
    async def test_error_isolation(self) -> None:
        """A failing participant doesn't break the others."""
        from bristlenose.stages.topic_segmentation import segment_topics

        call_count = 0

        async def mock_analyze(system_prompt, user_prompt, response_model, **kw):
            nonlocal call_count
            call_count += 1
            if "p2" in user_prompt:
                raise RuntimeError("LLM call failed for p2")
            from bristlenose.llm.structured import TopicSegmentationResult
            return TopicSegmentationResult(boundaries=[])

        transcripts = [_make_transcript(f"p{i}") for i in range(1, 4)]
        mock_client = AsyncMock()
        mock_client.analyze = mock_analyze

        result = await segment_topics(transcripts, mock_client, concurrency=3)

        assert len(result) == 3
        assert call_count == 3
        # p2 should have empty boundaries
        assert result[1].participant_id == "p2"
        assert result[1].boundaries == []
        # p1 and p3 should have succeeded (empty but valid)
        assert result[0].participant_id == "p1"
        assert result[2].participant_id == "p3"

    @pytest.mark.asyncio
    async def test_result_order_preserved(self) -> None:
        """Results come back in input order regardless of completion order."""
        from bristlenose.stages.topic_segmentation import segment_topics

        async def mock_analyze(system_prompt, user_prompt, response_model, **kw):
            # p3 finishes fastest, p1 slowest
            for pid, delay in [("p1", 0.08), ("p2", 0.04), ("p3", 0.01)]:
                if pid in user_prompt:
                    await asyncio.sleep(delay)
                    break
            from bristlenose.llm.structured import TopicSegmentationResult
            return TopicSegmentationResult(boundaries=[])

        transcripts = [_make_transcript(f"p{i}") for i in range(1, 4)]
        mock_client = AsyncMock()
        mock_client.analyze = mock_analyze

        result = await segment_topics(transcripts, mock_client, concurrency=3)

        assert [r.participant_id for r in result] == ["p1", "p2", "p3"]


# ---------------------------------------------------------------------------
# Stage 9: quote extraction concurrency
# ---------------------------------------------------------------------------

class TestQuoteExtractionConcurrency:
    """Verify extract_quotes runs concurrently with concurrency > 1."""

    @pytest.mark.asyncio
    async def test_concurrent_extraction(self) -> None:
        """With concurrency=3, up to 3 calls run in parallel."""
        from bristlenose.stages.quote_extraction import extract_quotes

        active_count = 0
        max_active = 0

        async def mock_analyze(system_prompt, user_prompt, response_model, **kw):
            nonlocal active_count, max_active
            active_count += 1
            max_active = max(max_active, active_count)
            await asyncio.sleep(0.05)
            active_count -= 1
            from bristlenose.llm.structured import QuoteExtractionResult
            return QuoteExtractionResult(quotes=[])

        transcripts = [_make_transcript(f"p{i}") for i in range(1, 7)]
        topic_maps = [
            SessionTopicMap(participant_id=f"p{i}", session_id=f"s{i}", boundaries=[])
            for i in range(1, 7)
        ]
        mock_client = AsyncMock()
        mock_client.analyze = mock_analyze

        result = await extract_quotes(
            transcripts, topic_maps, mock_client, concurrency=3,
        )

        assert isinstance(result, list)
        assert max_active <= 3
        assert max_active >= 2

    @pytest.mark.asyncio
    async def test_extraction_error_isolation(self) -> None:
        """A failing participant produces no quotes but doesn't break others."""
        from bristlenose.stages.quote_extraction import extract_quotes

        async def mock_analyze(system_prompt, user_prompt, response_model, **kw):
            if "p2" in user_prompt:
                raise RuntimeError("LLM failed for p2")
            from bristlenose.llm.structured import QuoteExtractionResult
            return QuoteExtractionResult(quotes=[])

        transcripts = [_make_transcript(f"p{i}") for i in range(1, 4)]
        topic_maps = [
            SessionTopicMap(participant_id=f"p{i}", session_id=f"s{i}", boundaries=[])
            for i in range(1, 4)
        ]
        mock_client = AsyncMock()
        mock_client.analyze = mock_analyze

        result = await extract_quotes(
            transcripts, topic_maps, mock_client, concurrency=3,
        )

        # All calls attempted, no crash
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Timing: concurrency=3 faster than concurrency=1
# ---------------------------------------------------------------------------

class TestConcurrencySpeedup:
    """Measure wall-time improvement from concurrency."""

    @pytest.mark.asyncio
    async def test_topic_segmentation_speedup(self) -> None:
        """concurrency=3 should be measurably faster than concurrency=1 for 6 participants."""
        from bristlenose.stages.topic_segmentation import segment_topics

        async def mock_analyze(system_prompt, user_prompt, response_model, **kw):
            await asyncio.sleep(0.05)  # 50ms simulated latency
            from bristlenose.llm.structured import TopicSegmentationResult
            return TopicSegmentationResult(boundaries=[])

        transcripts = [_make_transcript(f"p{i}") for i in range(1, 7)]

        # Sequential
        mock_client = AsyncMock()
        mock_client.analyze = mock_analyze
        t0 = time.monotonic()
        await segment_topics(transcripts, mock_client, concurrency=1)
        sequential_time = time.monotonic() - t0

        # Concurrent
        mock_client2 = AsyncMock()
        mock_client2.analyze = mock_analyze
        t0 = time.monotonic()
        await segment_topics(transcripts, mock_client2, concurrency=3)
        concurrent_time = time.monotonic() - t0

        # 6 calls × 50ms sequential ≈ 300ms
        # 6 calls × 50ms at concurrency=3 ≈ 100ms (2 batches)
        # Expect concurrent to be at least 1.5x faster (conservative)
        speedup = sequential_time / concurrent_time
        assert speedup >= 1.5, (
            f"Expected >= 1.5x speedup, got {speedup:.2f}x "
            f"(sequential={sequential_time:.3f}s, concurrent={concurrent_time:.3f}s)"
        )
