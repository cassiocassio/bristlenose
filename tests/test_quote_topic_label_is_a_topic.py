"""A quote's topic label is never a transition type ("screen_change").

Found on a 0.46.0 walk (16 Nov 2026): a small model copied the "(screen_change)" suffix the prompt
puts after each boundary, the label became a section heading in the report and over MCP.
"""

from __future__ import annotations

import pytest

from bristlenose.models import TopicBoundary, TransitionType
from bristlenose.stages.s09_quote_extraction import _checked_topic_label

_B = [
    TopicBoundary(timecode_seconds=0.0, topic_label="Dashboard view",
                  transition_type=TransitionType.GENERAL_CONTEXT),
    TopicBoundary(timecode_seconds=30.0, topic_label="Settings navigation",
                  transition_type=TransitionType.SCREEN_CHANGE),
]


@pytest.mark.parametrize("label", ["screen_change", "Screen Change", "screen-change", " topic_shift ",
                                   "task_change", "general_context"])
def test_a_transition_type_is_replaced_by_the_boundary_in_force(label: str) -> None:
    assert _checked_topic_label(label, _B, at=45.0) == "Settings navigation"
    assert _checked_topic_label(label, _B, at=10.0) == "Dashboard view"


def test_before_any_boundary_has_started_the_label_is_left_not_moved_forward() -> None:
    late = [TopicBoundary(timecode_seconds=20.0, topic_label="Checkout",
                          transition_type=TransitionType.SCREEN_CHANGE)]
    assert _checked_topic_label("screen_change", late, at=5.0) == "screen_change"


def test_a_real_label_is_left_alone() -> None:
    assert _checked_topic_label("Error with price display", _B, at=45.0) == "Error with price display"


def test_no_boundary_means_nothing_better_to_say() -> None:
    assert _checked_topic_label("screen_change", [], at=5.0) == "screen_change"


def test_a_boundary_that_is_itself_a_transition_word_is_not_a_topic_to_snap_to() -> None:
    bad = [
        TopicBoundary(timecode_seconds=0.0, topic_label="Dashboard view",
                      transition_type=TransitionType.GENERAL_CONTEXT),
        TopicBoundary(timecode_seconds=30.0, topic_label="screen_change",
                      transition_type=TransitionType.SCREEN_CHANGE),
    ]
    assert _checked_topic_label("screen_change", bad, at=45.0) == "Dashboard view"


# --- BR-23: a quote that begins a sentence is not left in lower case after a lead-in is cut ---

from bristlenose.stages.s09_quote_extraction import _restore_sentence_start  # noqa: E402

_SRC = "Oh, the search was great actually. It was fast."


@pytest.mark.parametrize(("text", "excerpt", "want"), [
    # filler trimmed from a sentence start: capitalise
    ("the search was great actually.", _SRC, "The search was great actually."),
    # a whole earlier sentence cut: the quote starts a sentence
    ("it was fast.", _SRC, "It was fast."),
    # begins mid-sentence in the original: leave
    ("the search was great", "I think the search was great", "the search was great"),
    # the model kept the ellipsis marking the cut: leave
    ("...the search was great", _SRC, "...the search was great"),
    # already capitalised
    ("The search was great.", _SRC, "The search was great."),
    # nothing to check against
    ("the search was great", "", "the search was great"),
    # lead-in with no comma is not shown to be a filler: leave
    ("search was great", "So search was great", "search was great"),
    # whole-word match only ("the" inside "another" is not the quote's start)
    ("the end", "Oh, another thing the end", "the end"),
])
def test_a_trimmed_lead_in_does_not_leave_a_lower_case_start(
    text: str, excerpt: str, want: str,
) -> None:
    assert _restore_sentence_start(text, excerpt) == want


# --- the call site: model output as a fixture through the real extraction pass ---

import asyncio  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from unittest.mock import AsyncMock  # noqa: E402

from bristlenose.llm.structured import ExtractedQuoteItem, QuoteExtractionResult  # noqa: E402
from bristlenose.models import (  # noqa: E402
    PiiCleanTranscript,
    SessionTopicMap,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.stages.s09_quote_extraction import _extract_one_pass  # noqa: E402

_FULL = "Oh, the search was great actually. It was fast and the results were really relevant."


def _one_pass(label: str, text: str) -> tuple[str, str]:
    transcript = PiiCleanTranscript(
        participant_id="p1", session_id="s1", source_file="s1.mp4",
        session_date=datetime(2026, 1, 1, tzinfo=timezone.utc), duration_seconds=60,
        segments=[TranscriptSegment(
            start_time=10, end_time=40, text=_FULL, speaker_label="p1",
            speaker_role=SpeakerRole.PARTICIPANT, speaker_code="p1", source="whisper",
            segment_index=0)],
    )
    topics = SessionTopicMap(participant_id="p1", session_id="s1", boundaries=[
        TopicBoundary(timecode_seconds=0, topic_label="Search results",
                      transition_type=TransitionType.SCREEN_CHANGE)])

    async def analyze(**kw: object) -> QuoteExtractionResult:
        return QuoteExtractionResult(quotes=[ExtractedQuoteItem(
            start_timecode="00:10", end_timecode="00:40", text=text,
            verbatim_excerpt=_FULL, topic_label=label, quote_type="screen_specific")])

    client = AsyncMock()
    client.analyze = analyze
    quote = asyncio.run(_extract_one_pass(transcript, topics, client, 3))[0]
    return quote.topic_label, quote.text


def test_the_extraction_pass_repairs_a_transition_label_and_a_lower_case_start() -> None:
    label, text = _one_pass("screen_change", "the search was great actually. It was fast and the "
                            "results were really relevant.")
    assert label == "Search results"
    assert text.startswith("The search was great")


def test_the_extraction_pass_leaves_a_clean_quote_alone() -> None:
    label, text = _one_pass("Search results", "The search was great actually. It was fast.")
    assert (label, text) == ("Search results", "The search was great actually. It was fast.")


@pytest.mark.parametrize(("text", "excerpt", "want"), [
    # a brand with an inner capital is not a lower-case slip
    ("iPhone was fine.", "Yeah, iPhone was fine.", "iPhone was fine."),
    ("eBay was fine.", "Yeah, eBay was fine.", "eBay was fine."),
    # the quote starts mid-sentence, though its first word also opens an earlier clause
    ("the search was great", "Honestly, the weather was bad and the search was great",
     "the search was great"),
    # the same words do open a sentence further on: that is the one the quote started at
    ("the search was great", "Honestly, the weather was bad. The search was great",
     "The search was great"),
    # a clause, not a lead-in
    ("the search was great", "Well, I think, the search was great", "the search was great"),
])
def test_capitalising_never_misspells_or_guesses_a_clause_start(
    text: str, excerpt: str, want: str,
) -> None:
    assert _restore_sentence_start(text, excerpt) == want


def test_a_label_no_boundary_can_repair_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    caplog.set_level(logging.WARNING)
    # the pass has a topic map with no boundaries: nothing to snap to, so it must say so
    transcript = PiiCleanTranscript(
        participant_id="p1", session_id="s1", source_file="s1.mp4",
        session_date=datetime(2026, 1, 1, tzinfo=timezone.utc), duration_seconds=60,
        segments=[TranscriptSegment(
            start_time=10, end_time=40, text=_FULL, speaker_label="p1",
            speaker_role=SpeakerRole.PARTICIPANT, speaker_code="p1", source="whisper",
            segment_index=0)],
    )

    async def analyze(**kw: object) -> QuoteExtractionResult:
        return QuoteExtractionResult(quotes=[ExtractedQuoteItem(
            start_timecode="00:10", end_timecode="00:40", text="The search was great actually.",
            verbatim_excerpt=_FULL, topic_label="topic_shift", quote_type="screen_specific")])

    client = AsyncMock()
    client.analyze = analyze
    asyncio.run(_extract_one_pass(transcript, None, client, 3))
    assert "quote_topic_label_is_transition_type" in caplog.text


@pytest.mark.parametrize(("label", "want"), [
    ("Settings navigation (screen_change)", "Settings navigation"),
    ("[00:10] Settings navigation (screen_change)", "Settings navigation"),
    ("(screen_change)", "Dashboard view"),
    ("Pricing (and plans)", "Pricing (and plans)"),
])
def test_a_copied_prompt_line_keeps_its_topic(label: str, want: str) -> None:
    assert _checked_topic_label(label, _B, at=10.0) == want


@pytest.mark.parametrize(("text", "excerpt", "want"), [
    # "it" also appears in "it's": the quote's own opening words say where it starts
    ("it was slow", "Oh, it's fine, but it was slow", "it was slow"),
    # a subordinate clause is not a filler
    ("the search was great", "When I clicked, the search was great", "the search was great"),
    # a trailing ellipsis is a pause, not a full stop
    ("the search", "I was, um... the search", "the search"),
    # str.upper() would write the wrong letter in Turkish and Dutch
    ("iyi \u00e7al\u0131\u015ft\u0131", "Evet, iyi \u00e7al\u0131\u015ft\u0131", "iyi \u00e7al\u0131\u015ft\u0131"),
    ("ijs is koud", "Ja, ijs is koud", "ijs is koud"),
])
def test_review_cases_stay_as_the_model_wrote_them(text: str, excerpt: str, want: str) -> None:
    assert _restore_sentence_start(text, excerpt) == want


def test_the_boundary_list_shows_the_topic_never_its_transition_type() -> None:
    """BR-04 (owner ruling A): `- [00:10] Settings navigation`, no parenthesised type."""
    seen: dict[str, str] = {}
    transcript = PiiCleanTranscript(
        participant_id="p1", session_id="s1", source_file="s1.mp4",
        session_date=datetime(2026, 1, 1, tzinfo=timezone.utc), duration_seconds=60,
        segments=[TranscriptSegment(
            start_time=10, end_time=40, text=_FULL, speaker_label="p1",
            speaker_role=SpeakerRole.PARTICIPANT, speaker_code="p1", source="whisper",
            segment_index=0)],
    )
    topics = SessionTopicMap(participant_id="p1", session_id="s1", boundaries=[
        TopicBoundary(timecode_seconds=10, topic_label="Settings navigation",
                      transition_type=TransitionType.SCREEN_CHANGE)])

    async def analyze(**kw: str) -> QuoteExtractionResult:
        seen["prompt"] = kw["user_prompt"]
        return QuoteExtractionResult(quotes=[])

    client = AsyncMock()
    client.analyze = analyze
    asyncio.run(_extract_one_pass(transcript, topics, client, 3))
    assert "Settings navigation" in seen["prompt"], "control: the boundary is listed"
    assert "screen_change" not in seen["prompt"]
    assert "Settings navigation (" not in seen["prompt"]
