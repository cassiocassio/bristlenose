"""Japanese and Chinese quotes are measured by reading length, not by spaces (N167, owner 1 Nov 2026).

The five-word minimum counted the pieces between spaces, so an unspaced quote was one or a few
"words" (in the Japanese trial the shortest kept quote was 109 characters; an English quote of five
words is about 25). The house rule (``reading_length``, 0.4 of a word per no-space character, so about
12 characters is five words) now decides, in the quote filter and in the Discussion moderator-turn
check. Spaced languages are unchanged.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from bristlenose.discussion.moderator import MIN_WORDS, is_askable_length, moderator_turns
from bristlenose.llm.structured import ExtractedQuoteItem, QuoteExtractionResult
from bristlenose.models import (
    FullTranscript,
    PiiCleanTranscript,
    SessionTopicMap,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.stages.s09_quote_extraction import extract_quotes


def _participant_transcript() -> PiiCleanTranscript:
    seg = TranscriptSegment(
        start_time=0.0, end_time=60.0, text="x", speaker_label="p1",
        speaker_role=SpeakerRole.PARTICIPANT, speaker_code="p1", source="whisper",
        segment_index=0,
    )
    return PiiCleanTranscript(
        participant_id="p1", session_id="s1", source_file="s1.mp4",
        session_date=datetime(2026, 1, 10, tzinfo=timezone.utc), duration_seconds=60.0,
        segments=[seg],
    )


async def _kept(text: str) -> int:
    async def analyze(system_prompt, user_prompt, response_model, **kw):
        return QuoteExtractionResult(quotes=[ExtractedQuoteItem(
            start_timecode="00:00:10", end_timecode="00:00:20", text=text,
            verbatim_excerpt=text[:20], topic_label="T", quote_type="screen_specific",
        )])

    client = AsyncMock()
    client.provider = "openai"
    client.analyze = analyze
    quotes, _ = await extract_quotes(
        [_participant_transcript()],
        [SessionTopicMap(participant_id="p1", session_id="s1", boundaries=[])],
        client, concurrency=1,
    )
    return len(quotes)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "kept"),
    [
        ("私は臨床心理学を習いたくてここにしました", 1),  # 20 characters, no spaces: 8 words' worth
        ("你们好吗今天怎么样呢", 0),  # 10 characters: 4 words' worth, under the minimum
        ("はい", 0),
        ("I think the price is high", 1),  # five spaced words, as before
        ("the price is high", 0),  # four, as before
    ],
)
async def test_the_quote_minimum_reads_length_not_spaces(text: str, kept: int) -> None:
    assert await _kept(text) == kept


def test_a_short_japanese_moderator_turn_is_not_a_question_and_a_real_one_is() -> None:
    assert MIN_WORDS == 3
    assert not is_askable_length("はい")  # 0.8
    assert not is_askable_length("そうですね")  # 2.0
    assert is_askable_length("どうして選びましたか")  # 10 characters = 4.0
    assert is_askable_length("What made you choose it")  # spaced: unchanged
    assert not is_askable_length("yeah great")  # two words, as before


def _moderator_transcript(turn: str) -> FullTranscript:
    segs = [
        TranscriptSegment(
            start_time=0.0, end_time=5.0, text=turn, speaker_label="m1",
            speaker_role=SpeakerRole.RESEARCHER, speaker_code="m1", source="whisper",
            segment_index=0,
        ),
        TranscriptSegment(
            start_time=5.0, end_time=30.0, text="answer words here", speaker_label="p1",
            speaker_role=SpeakerRole.PARTICIPANT, speaker_code="p1", source="whisper",
            segment_index=1,
        ),
    ]
    return FullTranscript(
        session_id="s1", participant_id="p1", source_file="s1.mp4",
        session_date=datetime(2026, 1, 10, tzinfo=timezone.utc), duration_seconds=30.0,
        segments=segs,
    )


def test_a_japanese_moderator_is_found_by_reading_length() -> None:
    assert moderator_turns(_moderator_transcript("どうして選びましたか")).reason != "no_moderator"
    assert moderator_turns(_moderator_transcript("はい")).reason == "no_moderator"
