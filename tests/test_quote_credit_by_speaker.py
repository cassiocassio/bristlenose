"""A quote in a session with two participants goes to whoever spoke it (N166, owner 1 Nov 2026).

Every quote was credited to the session's first participant code, so the second showed none and
Signals counted the pair as one voice. Rule, as the owner refined it: a quote is credited to the
participant segment it overlaps; when it spans two speakers the later one is credited, because in
an exchange the first turn is usually the question and the second the answer; a quote that starts
in a moderator's question is credited to the participant who answers it. A session with one
participant is unchanged.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from bristlenose.llm.structured import ExtractedQuoteItem, QuoteExtractionResult
from bristlenose.models import (
    PiiCleanTranscript,
    SessionTopicMap,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.stages.s09_quote_extraction import extract_quotes

_TEXT = "I really did not expect the price to be that high at all"


def _seg(i: int, start: float, end: float, code: str) -> TranscriptSegment:
    role = SpeakerRole.PARTICIPANT if code.startswith("p") else SpeakerRole.RESEARCHER
    return TranscriptSegment(
        start_time=start, end_time=end, text=f"words spoken by {code} number {i} here",
        speaker_label=code, speaker_role=role, speaker_code=code, source="whisper",
        segment_index=i,
    )


def _transcript(layout: list[tuple[float, float, str]]) -> PiiCleanTranscript:
    return PiiCleanTranscript(
        participant_id="p1", session_id="s1", source_file="s1.mp4",
        session_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
        duration_seconds=layout[-1][1],
        segments=[_seg(i, a, b, c) for i, (a, b, c) in enumerate(layout)],
    )


def _client(start: str, end: str) -> AsyncMock:
    async def analyze(system_prompt, user_prompt, response_model, **kw):
        return QuoteExtractionResult(quotes=[ExtractedQuoteItem(
            start_timecode=start, end_timecode=end, text=_TEXT,
            verbatim_excerpt="did not expect the price", topic_label="Price",
            quote_type="screen_specific",
        )])

    client = AsyncMock()
    client.provider = "openai"
    client.analyze = analyze
    return client


async def _credit(layout, start: str, end: str) -> str:
    quotes, _ = await extract_quotes(
        [_transcript(layout)],
        [SessionTopicMap(participant_id="p1", session_id="s1", boundaries=[])],
        _client(start, end), concurrency=1,
    )
    assert len(quotes) == 1
    return quotes[0].participant_id


# A pair interviewed together: the moderator asks, p1 answers, the moderator asks, p2 answers.
_PAIR = [
    (0.0, 10.0, "m1"), (10.0, 30.0, "p1"), (30.0, 40.0, "m1"), (40.0, 60.0, "p2"),
]


@pytest.mark.asyncio
async def test_a_quote_inside_the_second_participants_turn_is_theirs() -> None:
    assert await _credit(_PAIR, "00:00:45", "00:00:55") == "p2"


@pytest.mark.asyncio
async def test_a_quote_inside_the_first_participants_turn_is_theirs() -> None:
    assert await _credit(_PAIR, "00:00:15", "00:00:25") == "p1"


@pytest.mark.asyncio
async def test_a_quote_that_starts_in_the_question_goes_to_whoever_answers() -> None:
    # starts at 0:33, in the moderator's question to the pair, and runs into p2's answer
    assert await _credit(_PAIR, "00:00:33", "00:00:50") == "p2"


@pytest.mark.asyncio
async def test_a_quote_spanning_two_participants_is_credited_to_the_second() -> None:
    layout = [(0.0, 20.0, "p1"), (20.0, 40.0, "p2"), (40.0, 50.0, "m1")]
    assert await _credit(layout, "00:00:15", "00:00:30") == "p2"


@pytest.mark.asyncio
async def test_a_quote_that_only_touches_the_next_turn_stays_with_the_speaker() -> None:
    layout = [(0.0, 20.0, "p1"), (20.0, 40.0, "p2")]
    assert await _credit(layout, "00:00:10", "00:00:20") == "p1"  # ends as p2 begins


@pytest.mark.asyncio
async def test_one_participant_is_unchanged_whatever_the_timecodes_say() -> None:
    layout = [(0.0, 10.0, "m1"), (10.0, 60.0, "p1")]
    assert await _credit(layout, "00:00:02", "00:00:08") == "p1"  # even in the question


@pytest.mark.asyncio
async def test_a_quote_over_no_participant_turn_keeps_the_primary_code() -> None:
    layout = [(0.0, 10.0, "p1"), (10.0, 20.0, "p2"), (20.0, 90.0, "m1")]
    assert await _credit(layout, "00:00:50", "00:00:60") == "p1"


@pytest.mark.asyncio
async def test_a_chunk_holding_only_the_second_participant_still_credits_them() -> None:
    """A long pair session is split into chunks (truncation, or the pass deadline), and a
    chunk is a copy of the transcript holding a subset of its turns with the session's
    primary code. A chunk that holds only p2's turns must still credit p2 — the one-code
    shortcut used to hand the whole chunk back to p1, which is the N166 bug again on exactly
    the sessions long enough to split."""
    from bristlenose.llm.client import TruncatedResponseError

    # Six turns; the index-halves split (10% overlap) gives a right chunk of m1, m1, p2, p2.
    layout = [
        (0.0, 10.0, "p1"), (10.0, 20.0, "p1"), (20.0, 30.0, "m1"),
        (30.0, 40.0, "m1"), (40.0, 50.0, "p2"), (50.0, 60.0, "p2"),
    ]
    calls = {"n": 0}

    async def analyze(system_prompt, user_prompt, response_model, **kw):
        calls["n"] += 1
        if calls["n"] == 1:  # the whole session: cut off at the output cap, so split
            raise TruncatedResponseError(
                "cut", provider="openai", model="m", requested_max_tokens=1, model_cap=1,
            )
        if "spoken by p2" not in user_prompt:
            return QuoteExtractionResult(quotes=[])
        return QuoteExtractionResult(quotes=[ExtractedQuoteItem(
            start_timecode="00:00:45", end_timecode="00:00:55", text=_TEXT,
            verbatim_excerpt="did not expect the price", topic_label="Price",
            quote_type="screen_specific",
        )])

    client = AsyncMock()
    client.provider = "openai"
    client.analyze = analyze
    quotes, _ = await extract_quotes(
        [_transcript(layout)],
        [SessionTopicMap(participant_id="p1", session_id="s1", boundaries=[])],
        client, concurrency=1,
    )
    assert calls["n"] == 3  # the whole session, then each half
    assert [q.participant_id for q in quotes] == ["p2"]


@pytest.mark.asyncio
async def test_a_transcript_with_no_timecodes_keeps_the_primary_code() -> None:
    # Every segment starts at 0.0 (a transcript with no times): who spoke when is unknowable.
    layout = [(0.0, 50.0, "p1"), (0.0, 50.0, "p2")]
    t = _transcript(layout)
    quotes, _ = await extract_quotes(
        [t], [SessionTopicMap(participant_id="p1", session_id="s1", boundaries=[])],
        _client("00:00:10", "00:00:20"), concurrency=1,
    )
    assert [q.participant_id for q in quotes] == ["p1"]
