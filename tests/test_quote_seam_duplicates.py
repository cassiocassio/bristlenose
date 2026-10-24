"""N42: a quote in the overlap band of a split session is extracted by both chunks.

When a long session is split (an output-cap truncation or the 570 s pass
deadline), the two chunks share a ~10% band so a quote that straddles the cut
survives. Both chunks then extract the quote in that band, and
``_dedupe_overlapping_quotes`` collapses the pair only when their
``verbatim_excerpt`` agrees to the byte. The excerpt is the model's own choice of
substring, so two prompts need not choose alike. Reproduced here with an LLM
stand-in that, like the two real passes, quotes the same turn from the start of
one chunk and from the end of the other.

Measured with a real local model on 24 Oct 2026: see
``docs/private/reliability/re-prove-1-scenarios.md`` (N42).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from bristlenose.llm.client import TruncatedResponseError
from bristlenose.llm.structured import ExtractedQuoteItem, QuoteExtractionResult
from bristlenose.models import (
    PiiCleanTranscript,
    SessionTopicMap,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.stages.s09_quote_extraction import extract_quotes

_SEAM_TURN = 9
_WHOLE_TURN = f"This is participant turn number {_SEAM_TURN} and I have plenty to say."
# What the model keeps when the turn is the first thing it reads in a chunk: the
# lead-in clause is context it was not shown.
_TRIMMED_TURN = f"turn number {_SEAM_TURN} and I have plenty to say."


def _transcript(n_segments: int = 20, seg_seconds: float = 10.0) -> PiiCleanTranscript:
    segments = [
        TranscriptSegment(
            start_time=i * seg_seconds,
            end_time=(i + 1) * seg_seconds,
            text=f"This is participant turn number {i} and I have plenty to say.",
            speaker_label="Speaker A",
            speaker_role=SpeakerRole.PARTICIPANT,
            speaker_code="p1",
            source="whisper",
            segment_index=i,
        )
        for i in range(n_segments)
    ]
    return PiiCleanTranscript(
        participant_id="p1",
        session_id="s1",
        source_file="s1.mp4",
        session_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
        duration_seconds=n_segments * seg_seconds,
        segments=segments,
    )


def _client() -> tuple[AsyncMock, dict[str, int]]:
    calls = {"n": 0}

    async def analyze(system_prompt, user_prompt, response_model, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TruncatedResponseError(
                "truncated", provider="openai", model="gpt-4o",
                requested_max_tokens=16384, model_cap=16384,
            )
        # The seam turn sits in both chunks. The chunk that opens at turn 0 sees
        # it at its end; the other sees it at its start.
        sees_it = re.search(rf"turn number {_SEAM_TURN} ", user_prompt) is not None
        assert sees_it, "the seam turn must be in both chunks' overlap band"
        opens_session = re.search(r"turn number 0 ", user_prompt) is not None
        verbatim = _WHOLE_TURN if opens_session else _TRIMMED_TURN
        return QuoteExtractionResult(quotes=[ExtractedQuoteItem(
            start_timecode="00:01:30", end_timecode="00:01:40",
            text=_WHOLE_TURN, verbatim_excerpt=verbatim,
            topic_label="Onboarding", quote_type="screen_specific",
        )])

    client = AsyncMock()
    client.provider = "openai"
    client.analyze = analyze
    return client, calls


@pytest.mark.asyncio
async def test_both_chunks_see_the_seam_turn_and_extract_it() -> None:
    """Sanity: the stand-in does what the scenario says (two passes, one turn)."""
    client, calls = _client()
    topic_map = SessionTopicMap(participant_id="p1", session_id="s1", boundaries=[])
    await extract_quotes([_transcript()], [topic_map], client, concurrency=1)
    assert calls["n"] == 3  # the truncated full pass, then one pass per chunk


@pytest.mark.xfail(
    strict=True,
    reason="N42: the seam dedupe is byte-exact on verbatim_excerpt, so one turn quoted "
    "with different edges by the two chunks is kept twice",
)
@pytest.mark.asyncio
async def test_a_turn_quoted_by_both_chunks_is_one_quote() -> None:
    client, _ = _client()
    topic_map = SessionTopicMap(participant_id="p1", session_id="s1", boundaries=[])
    quotes, outcome = await extract_quotes([_transcript()], [topic_map], client, concurrency=1)
    assert outcome.succeeded == 1
    assert [q.start_timecode for q in quotes] == [90.0], (
        f"expected one quote at 90 s, got {[(q.start_timecode, q.verbatim_excerpt) for q in quotes]}"
    )
