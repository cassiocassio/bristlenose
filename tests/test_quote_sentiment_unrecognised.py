"""A sentiment outside the enum is said once per extraction, not dropped silently.

Stage 9 keeps such a quote with ``sentiment=None``, and Signals counts no quote
without one, so a model that capitalises every label used to empty Signals
with nothing in the log.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from bristlenose.llm.client import _validate_repairing
from bristlenose.models import (
    PiiCleanTranscript,
    SessionTopicMap,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.stages.s09_quote_extraction import extract_quotes


def _transcript(sid: str, n: int = 8) -> PiiCleanTranscript:
    segs = [
        TranscriptSegment(
            start_time=float(i), end_time=float(i + 1),
            text=f"This is quote number {i} and it says something useful",
            speaker_label="Speaker A", speaker_role=SpeakerRole.PARTICIPANT,
            speaker_code="p1", source="whisper", segment_index=i,
        )
        for i in range(n)
    ]
    return PiiCleanTranscript(
        participant_id="p1", session_id=sid, source_file=f"{sid}.mp4",
        session_date=datetime(2026, 10, 23, tzinfo=timezone.utc),
        duration_seconds=float(n), segments=segs,
    )


def _client(sentiment: str) -> AsyncMock:
    reply = {"quotes": [{
        "start_timecode": f"00:00:{i:02d}", "end_timecode": f"00:00:{i + 1:02d}",
        "text": f"This is quote number {i} and it says something useful",
        "verbatim_excerpt": f"quote number {i}", "topic_label": "Checkout",
        "quote_type": "screen_specific", "sentiment": sentiment, "intensity": 2,
    } for i in range(4)]}

    async def analyze(system_prompt, user_prompt, response_model, **kw):
        return _validate_repairing(reply, response_model, provider="anthropic", model="m")

    client = AsyncMock()
    client.provider = "anthropic"
    client.analyze = analyze
    return client


def _extract(sentiment: str, caplog: pytest.LogCaptureFixture):
    transcripts = [_transcript("s1"), _transcript("s2")]
    topics = [SessionTopicMap(participant_id="p1", session_id=t.session_id, boundaries=[])
              for t in transcripts]
    with caplog.at_level(logging.WARNING, logger="bristlenose.stages.s09_quote_extraction"):
        quotes, _ = asyncio.run(
            extract_quotes(transcripts, topics, _client(sentiment), min_quote_words=1),
        )
    lines = [r.getMessage() for r in caplog.records if "sentiment" in r.getMessage()]
    return quotes, lines


def test_unrecognised_sentiments_are_counted_in_one_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    quotes, lines = _extract("Frustration", caplog)
    assert len(quotes) == 8
    assert all(q.sentiment is None for q in quotes)  # behaviour unchanged
    assert len(lines) == 1, lines  # one line for the run, not one per quote
    assert "quotes=8" in lines[0]
    assert "'Frustration'" in lines[0]


def test_an_enum_sentiment_says_nothing(caplog: pytest.LogCaptureFixture) -> None:
    quotes, lines = _extract("frustration", caplog)
    assert all(q.sentiment is not None for q in quotes)
    assert lines == []
