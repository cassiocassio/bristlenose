"""Stage 8's timecode range guard — the minutes-as-hours defect in topic boundaries.

s08 shares s09's exposure: the same `full_text()` goes into the prompt and the
answer comes back through the same `parse_timecode`. Measured 11 Sep 2026
(`experiments/quote-stability/FINDINGS.md` § 3b): the cached FOSSDA boundaries
carry the signature on 38 of 133 (28.6%), written by `claude-sonnet-4`, and
`gemini-3.8-flash` reproduces it on an unpadded prompt and loses it on a padded
one. The source is fixed; this guard is the defence in depth behind it.

The one place s08 must NOT copy s09 is the non-signature out-of-range case —
see `test_out_of_range_without_the_signature_is_dropped_not_clamped`.

Mocked LLM throughout — no network, no keys.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from bristlenose.llm.structured import TopicBoundaryItem, TopicSegmentationResult
from bristlenose.models import PiiCleanTranscript, SpeakerRole, TranscriptSegment
from bristlenose.stages.s08_topic_segmentation import segment_topics


def _transcript(
    duration_seconds: float = 23 * 60, n_segments: int = 20, timecoded: bool = True
) -> PiiCleanTranscript:
    step = duration_seconds / n_segments
    return PiiCleanTranscript(
        participant_id="p1",
        session_id="s6",
        source_file="s6.mp4",
        session_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
        duration_seconds=duration_seconds if timecoded else 0.0,
        segments=[
            TranscriptSegment(
                start_time=(i * step) if timecoded else 0.0,
                end_time=((i + 1) * step) if timecoded else 0.0,
                text=f"Participant turn {i} with words in it.",
                speaker_label="Speaker A",
                speaker_role=SpeakerRole.PARTICIPANT,
                speaker_code="p1",
                source="whisper",
                segment_index=i,
            )
            for i in range(n_segments)
        ],
    )


def _item(timecode: str, label: str = "Open source background") -> TopicBoundaryItem:
    return TopicBoundaryItem(
        timecode=timecode,
        topic_label=label,
        transition_type="topic_shift",
        confidence=0.9,
    )


async def _run(transcript: PiiCleanTranscript, items: list[TopicBoundaryItem]):
    async def analyze(system_prompt, user_prompt, response_model, **kw):
        return TopicSegmentationResult(boundaries=items)

    client = AsyncMock()
    client.provider = "anthropic"
    client.analyze = analyze

    maps, outcome = await segment_topics([transcript], client, concurrency=1)
    assert outcome.failed == []
    return maps[0].boundaries


class TestMinutesAsHours:
    @pytest.mark.asyncio
    async def test_affected_boundaries_are_recovered(self) -> None:
        """s6 is 23 minutes and 7 of its 8 cached boundaries were 60x too large."""
        bounds = await _run(
            _transcript(),
            [_item("00:53:00"), _item("02:10:00"), _item("05:34:00")],
        )

        assert [b.timecode_seconds for b in bounds] == [53.0, 130.0, 334.0]

    @pytest.mark.asyncio
    async def test_correct_boundaries_in_the_same_response_are_untouched(self) -> None:
        """The cache is mixed within a session — 7 of 8 affected, not 8 of 8."""
        bounds = await _run(_transcript(), [_item("00:53:00"), _item("00:09:12")])

        assert sorted(b.timecode_seconds for b in bounds) == [53.0, 552.0]

    @pytest.mark.asyncio
    async def test_a_genuine_exact_minute_boundary_in_range_is_not_divided(self) -> None:
        """Several clean arms carried one such boundary — the ~1-in-60 base rate."""
        bounds = await _run(_transcript(), [_item("00:05:00")])

        assert [b.timecode_seconds for b in bounds] == [300.0]


class TestOutOfRangeWithoutTheSignature:
    @pytest.mark.asyncio
    async def test_out_of_range_without_the_signature_is_dropped_not_clamped(self) -> None:
        """THE s08/s09 divergence, and the reason this file exists separately.

        s09 clamps, because a quote timecode is *shown* and a bounded deep link
        beats one past the end of the media. Clamping a BOUNDARY would invent a
        topic transition at the session end and then push it back inside
        `_boundaries_in_range` — converting a boundary the downstream filter
        would have caught into one it cannot. Dropping is the only safe move.
        """
        bounds = await _run(_transcript(), [_item("00:41:17"), _item("00:09:12")])

        kept = [b.timecode_seconds for b in bounds]
        assert kept == [552.0], "the out-of-range boundary should be gone entirely"
        assert 23 * 60.0 not in kept, "clamped to the session end — that is s09's rule, not s08's"

    @pytest.mark.asyncio
    async def test_the_drop_is_announced(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            await _run(_transcript(), [_item("00:41:17")])

        assert "boundary_timecode_out_of_range" in caplog.text
        assert "action=dropped" in caplog.text


class TestGuardStandsDown:
    @pytest.mark.asyncio
    async def test_non_timecoded_transcript_is_left_alone(self) -> None:
        bounds = await _run(_transcript(timecoded=False), [_item("00:53:00")])

        assert [b.timecode_seconds for b in bounds] == [3180.0]

    @pytest.mark.asyncio
    async def test_unparseable_timecode_is_logged_and_skipped(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            bounds = await _run(_transcript(), [_item("later on"), _item("00:09:12")])

        assert [b.timecode_seconds for b in bounds] == [552.0]
        assert "boundary_timecode_unparseable" in caplog.text


class TestRepairIsAnnounced:
    @pytest.mark.asyncio
    async def test_each_repair_and_the_per_session_total_are_warnings(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            await _run(_transcript(), [_item("00:53:00"), _item("02:10:00"), _item("00:41:17")])

        assert caplog.text.count("boundary_timecode_repair") == 2
        assert "signature=minutes-as-hours" in caplog.text
        assert (
            "boundary_timecodes_repaired | session=s6 | boundaries=3 | scaled=2 | "
            "dropped=1 | unparseable=0"
        ) in caplog.text

    @pytest.mark.asyncio
    async def test_log_keys_are_stage_distinct(self, caplog: pytest.LogCaptureFixture) -> None:
        """s08 and s09 share an implementation; their log keys must stay separable."""
        with caplog.at_level(logging.WARNING):
            await _run(_transcript(), [_item("00:53:00")])

        assert "boundary_timecode_repair" in caplog.text
        assert "quote_timecode_repair" not in caplog.text
