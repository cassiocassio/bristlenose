"""Quote timecode range guard — the `gpt-5.6-terra` minutes-as-hours defect.

Measured 5 Sep 2026 (`experiments/quote-stability/FINDINGS.md` § 3): the model
writes an `MM:SS` transcript value into an `HH:MM:SS` slot by appending `:00`,
making the parsed value exactly 60x the truth for 63% of quotes (239 of 380
across four passes). Claude and Gemini: zero, on the same transcripts.

The SOURCE was fixed on 11 Sep 2026 — the prompt now renders zero-padded
`HH:MM:SS`, so there is no mismatch left for a model to resolve. `TestPromptRendering`
pins that; the guard tests below pin the defence in depth that stays behind it.

These tests drive the real stage with a mocked LLM — no network, no keys.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from bristlenose.llm.structured import ExtractedQuoteItem, QuoteExtractionResult
from bristlenose.models import (
    PiiCleanTranscript,
    SessionTopicMap,
    SpeakerRole,
    TopicBoundary,
    TranscriptSegment,
    TransitionType,
)
from bristlenose.stages.s09_quote_extraction import extract_quotes
from bristlenose.utils.timecodes import parse_timecode

# Long enough to clear the default min_quote_words=5 filter.
_TEXT = "I really enjoy this flow and would happily use it again tomorrow"


def _transcript(
    duration_seconds: float = 23 * 60,
    n_segments: int = 20,
    timecoded: bool = True,
) -> PiiCleanTranscript:
    """A participant transcript spanning `duration_seconds`."""
    step = duration_seconds / n_segments
    segments = [
        TranscriptSegment(
            start_time=(i * step) if timecoded else 0.0,
            end_time=((i + 1) * step) if timecoded else 0.0,
            text=f"Participant turn {i}, with plenty of words in it to quote.",
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
        session_id="s9",
        source_file="s9.mp4",
        session_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
        duration_seconds=duration_seconds if timecoded else 0.0,
        segments=segments,
    )


def _item(start: str, end: str, verbatim: str = "") -> ExtractedQuoteItem:
    return ExtractedQuoteItem(
        start_timecode=start,
        end_timecode=end,
        text=_TEXT,
        verbatim_excerpt=verbatim or f"{start}-{end} verbatim words here",
        topic_label="Onboarding",
        quote_type="screen_specific",
    )


def _client(items: list[ExtractedQuoteItem]) -> AsyncMock:
    async def analyze(system_prompt, user_prompt, response_model, **kw):
        return QuoteExtractionResult(quotes=items)

    client = AsyncMock()
    client.provider = "openai"
    client.analyze = analyze
    return client


async def _run(transcript: PiiCleanTranscript, items: list[ExtractedQuoteItem]):
    quotes, outcome = await extract_quotes(
        [transcript],
        [SessionTopicMap(participant_id="p1", session_id="s9", boundaries=[])],
        _client(items),
        concurrency=1,
    )
    assert outcome.failed == []
    return quotes


class TestMinutesAsHours:
    @pytest.mark.asyncio
    async def test_measured_wire_strings_are_recovered(self) -> None:
        """The three raw pairs captured from the live s9 call, 5 Sep 2026.

        s9 is 23 minutes. Every one of these parses to a time past the end of
        the recording, and every one is the truth times sixty.
        """
        quotes = await _run(
            _transcript(),
            [
                _item("00:53:00", "02:07:00"),
                _item("02:10:00", "03:00:00"),
                _item("05:34:00", "07:00:00"),
            ],
        )

        pairs = [(q.start_timecode, q.end_timecode) for q in quotes]
        assert pairs == [
            (53.0, 127.0),      # 00:53 -> 02:07
            (130.0, 180.0),     # 02:10 -> 03:00
            (334.0, 420.0),     # 05:34 -> 07:00
        ]

    @pytest.mark.asyncio
    async def test_correct_quotes_in_the_same_response_are_untouched(self) -> None:
        """37% of quotes in an affected response are already right.

        This is why a blanket divide-by-60 is the wrong fix — the guard has to
        be per-quote, and it must leave the good ones alone.
        """
        quotes = await _run(
            _transcript(),
            [
                _item("00:53:00", "02:07:00"),  # 60x
                _item("00:05:30", "00:06:10"),  # correct HH:MM:SS, in range
            ],
        )

        assert [(q.start_timecode, q.end_timecode) for q in quotes] == [
            (53.0, 127.0),
            (330.0, 370.0),
        ]

    @pytest.mark.asyncio
    async def test_a_genuine_exact_minute_quote_in_range_is_not_divided(self) -> None:
        """The exact-minute signature alone must not trigger a repair.

        A real boundary lands on an exact minute about 1 time in 60. Being in
        range is what settles it.
        """
        quotes = await _run(_transcript(), [_item("00:05:00", "00:06:00")])
        assert (quotes[0].start_timecode, quotes[0].end_timecode) == (300.0, 360.0)


class TestOutOfRangeWithoutTheSignature:
    @pytest.mark.asyncio
    async def test_is_clamped_not_divided(self) -> None:
        """An out-of-range value with seconds on it is a different fault.

        Dividing it would invent a position. It is bounded into the session
        instead, so the deep link and the clip-export boundary stay valid.
        """
        quotes = await _run(_transcript(), [_item("00:41:17", "00:42:03")])

        ceiling = 23 * 60.0
        assert (quotes[0].start_timecode, quotes[0].end_timecode) == (ceiling, ceiling)

    @pytest.mark.asyncio
    async def test_repair_never_inverts_the_pair(self) -> None:
        """A scaled start against a clamped end must not produce a negative span."""
        quotes = await _run(_transcript(), [_item("20:00:00", "00:41:17")])

        q = quotes[0]
        assert q.end_timecode >= q.start_timecode


class TestGuardStandsDown:
    @pytest.mark.asyncio
    async def test_non_timecoded_transcript_is_left_alone(self) -> None:
        """Every segment at 0.0 means there is no clock to measure against."""
        quotes = await _run(
            _transcript(timecoded=False), [_item("00:53:00", "02:07:00")]
        )
        assert (quotes[0].start_timecode, quotes[0].end_timecode) == (3180.0, 7620.0)

    @pytest.mark.asyncio
    async def test_unparseable_timecode_is_logged_not_silently_zeroed(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            quotes = await _run(_transcript(), [_item("later on", "much later")])

        assert quotes[0].start_timecode == 0.0
        assert "quote_timecode_unparseable" in caplog.text


class TestRepairIsAnnounced:
    @pytest.mark.asyncio
    async def test_each_repair_and_the_per_session_total_are_warnings(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A repair buys the researcher their run; the log says it needed buying."""
        with caplog.at_level(logging.WARNING):
            await _run(
                _transcript(),
                [_item("00:53:00", "02:07:00"), _item("02:10:00", "03:00:00")],
            )

        assert caplog.text.count("quote_timecode_repair") == 4  # 2 quotes x 2 ends
        assert "signature=minutes-as-hours" in caplog.text
        assert (
            "quote_timecodes_repaired | session=s9 | quotes=2 | scaled=4 | "
            "clamped=0 | unparseable=0"
        ) in caplog.text


class TestKnownBlindSpot:
    @pytest.mark.asyncio
    async def test_an_early_60x_quote_in_a_long_session_is_not_caught(self) -> None:
        """Pinned as a LIMIT, not an aspiration.

        `format_timecode` is per-segment, so a session over an hour renders its
        first hour as MM:SS and the rest as H:MM:SS. `00:53` in a two-hour
        session becomes `00:53:00` = 53 minutes, which is comfortably in range,
        so a range check cannot see it. Catching this needs the quote's text
        checked against the segment at its timecode.

        If this test ever fails because the value came back as 53.0, the guard
        grew a capability and this test should be deleted, not repaired.
        """
        quotes = await _run(
            _transcript(duration_seconds=2 * 3600), [_item("00:53:00", "02:07:00")]
        )
        assert quotes[0].start_timecode == 3180.0  # still 60x wrong


class TestPromptRendering:
    """The prompt the model reads must speak the format the schema asks for.

    This is the source fix. If it regresses, the guard above starts firing again
    and 63% of ChatGPT quote timecodes go wrong — so these assertions are the
    thing standing between a tidy-up of the timecode helpers and the defect
    coming back.
    """

    def test_every_line_is_zero_padded_hh_mm_ss(self) -> None:
        t = _transcript(duration_seconds=23 * 60)
        lines = [ln for ln in t.full_text().splitlines() if ln.strip()]

        assert lines, "transcript rendered empty"
        for line in lines:
            tc = line.split("]")[0].lstrip("[")
            assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", tc), f"not padded: {line[:40]!r}"

    def test_one_format_across_the_hour_boundary(self) -> None:
        """The old rendering switched form mid-transcript at 1 h. This one does not."""
        t = _transcript(duration_seconds=2 * 3600, n_segments=40)
        widths = {len(ln.split("]")[0].lstrip("[")) for ln in t.full_text().splitlines() if ln.strip()}

        assert widths == {8}, f"mixed timecode widths in one prompt: {widths}"

    def test_rendering_round_trips_through_parse_timecode(self) -> None:
        """What we render is what we parse back — the two halves of the contract."""
        t = _transcript(duration_seconds=2 * 3600, n_segments=40)
        rendered = [
            parse_timecode(ln.split("]")[0].lstrip("["))
            for ln in t.full_text().splitlines()
            if ln.strip()
        ]

        assert rendered == [pytest.approx(s.start_time) for s in t.segments]

    @pytest.mark.asyncio
    async def test_topic_boundaries_match_the_transcript_in_the_same_prompt(self) -> None:
        """A mixed-format prompt is the ambiguity we just removed.

        The boundary list and the transcript sit in ONE prompt. If they disagree
        on format, the model has a mismatch to resolve all over again.
        """
        captured: dict[str, str] = {}

        async def analyze(system_prompt, user_prompt, response_model, **kw):
            captured["user"] = user_prompt
            return QuoteExtractionResult(quotes=[])

        client = AsyncMock()
        client.provider = "anthropic"
        client.analyze = analyze

        await extract_quotes(
            [_transcript()],
            [
                SessionTopicMap(
                    participant_id="p1",
                    session_id="s9",
                    boundaries=[
                        TopicBoundary(
                            timecode="00:05:30",
                            timecode_seconds=330.0,
                            topic_label="Onboarding",
                            transition_type=TransitionType.TOPIC_SHIFT,
                        )
                    ],
                )
            ],
            client,
            concurrency=1,
        )

        # Every bracketed timecode in the prompt — transcript AND boundary list.
        found = set(re.findall(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]", captured["user"]))
        assert found, "no timecodes in the prompt"
        assert all(re.fullmatch(r"\d{2}:\d{2}:\d{2}", tc) for tc in found), sorted(found)
