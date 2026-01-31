"""Tests for markdown style template utilities."""

from __future__ import annotations

from bristlenose.models import (
    EmotionalTone,
    ExtractedQuote,
    QuoteIntent,
    QuoteType,
)
from bristlenose.utils.markdown import (
    BOLD,
    CODE_SPAN,
    DESCRIPTION,
    ELLIPSIS_MARKER,
    EM_DASH,
    EN_DASH,
    HEADING_1,
    HEADING_2,
    HEADING_3,
    HORIZONTAL_RULE,
    ITALIC,
    LQUOTE,
    RQUOTE,
    SNIPPET_MAX_LENGTH,
    format_cooked_segment_md,
    format_cooked_segment_txt,
    format_friction_item,
    format_participant_range,
    format_quote_block,
    format_raw_segment_md,
    format_raw_segment_txt,
    format_transcript_header_md,
    format_transcript_header_txt,
)

# ---------------------------------------------------------------------------
# 1. Typographic constants
# ---------------------------------------------------------------------------


def test_unicode_constants() -> None:
    assert LQUOTE == "\u201c"
    assert RQUOTE == "\u201d"
    assert EM_DASH == "\u2014"
    assert EN_DASH == "\u2013"


# ---------------------------------------------------------------------------
# 2. Structural format strings
# ---------------------------------------------------------------------------


def test_heading_format_strings() -> None:
    assert HEADING_1.format(title="My Project") == "# My Project"
    assert HEADING_2.format(title="Themes") == "## Themes"
    assert HEADING_3.format(title="Dashboard") == "### Dashboard"


def test_text_format_strings() -> None:
    assert DESCRIPTION.format(text="A note") == "_A note_"
    assert BOLD.format(text="p1") == "**p1**"
    assert ITALIC.format(text="confusion") == "_confusion_"
    assert CODE_SPAN.format(text="frustrated") == "`frustrated`"


def test_horizontal_rule() -> None:
    assert HORIZONTAL_RULE == "---"


# ---------------------------------------------------------------------------
# 3. format_quote_block
# ---------------------------------------------------------------------------


def _make_quote(**kwargs: object) -> ExtractedQuote:
    """Helper to build an ExtractedQuote with sensible defaults."""
    defaults: dict[str, object] = {
        "participant_id": "p1",
        "start_timecode": 323.0,
        "end_timecode": 340.0,
        "text": "I couldn\u2019t find the button",
        "topic_label": "Dashboard",
        "quote_type": QuoteType.SCREEN_SPECIFIC,
    }
    defaults.update(kwargs)
    return ExtractedQuote(**defaults)  # type: ignore[arg-type]


def test_format_quote_block_basic() -> None:
    quote = _make_quote()
    result = format_quote_block(quote)
    # Should start with >
    assert result.startswith(">")
    # Should contain smart quotes around text
    assert LQUOTE in result
    assert RQUOTE in result
    # Should contain em dash before participant
    assert f"{EM_DASH} p1" in result
    # Should contain timecode
    assert "[05:23]" in result
    # No badge line (defaults are narration + neutral + intensity 1)
    assert result.count("\n") == 0  # single line, no badges


def test_format_quote_block_with_context() -> None:
    quote = _make_quote(
        researcher_context="When asked about the settings page"
    )
    result = format_quote_block(quote)
    lines = result.split("\n")
    # First line is context
    assert lines[0] == "> [When asked about the settings page]"
    # Second line is the quote body
    assert LQUOTE in lines[1]
    assert f"{EM_DASH} p1" in lines[1]


def test_format_quote_block_with_badges() -> None:
    quote = _make_quote(
        intent=QuoteIntent.CONFUSION,
        emotion=EmotionalTone.FRUSTRATED,
        intensity=3,
    )
    result = format_quote_block(quote)
    lines = result.split("\n")
    # Last line should be badges
    badge_line = lines[-1]
    assert "`confusion`" in badge_line
    assert "`frustrated`" in badge_line
    assert "`intensity:strong`" in badge_line


def test_format_quote_block_moderate_intensity() -> None:
    quote = _make_quote(intensity=2)
    result = format_quote_block(quote)
    assert "`intensity:moderate`" in result


def test_format_quote_block_no_badges_for_defaults() -> None:
    quote = _make_quote(
        intent=QuoteIntent.NARRATION,
        emotion=EmotionalTone.NEUTRAL,
        intensity=1,
    )
    result = format_quote_block(quote)
    # No badge line at all
    assert "`" not in result


# ---------------------------------------------------------------------------
# 4. format_friction_item
# ---------------------------------------------------------------------------


def test_format_friction_item() -> None:
    result = format_friction_item("05:23", "confusion", "Why is that not working?")
    assert result.startswith("- [05:23]")
    assert "_confusion_" in result
    assert EM_DASH in result
    assert f"{LQUOTE}Why is that not working?{RQUOTE}" in result


def test_format_friction_item_truncation() -> None:
    long_snippet = "a" * 100
    result = format_friction_item("05:23", "confusion", long_snippet)
    # Should be truncated
    assert ELLIPSIS_MARKER in result
    # The quoted text should be SNIPPET_MAX_LENGTH + len(ELLIPSIS_MARKER) + quotes
    assert ("a" * SNIPPET_MAX_LENGTH + ELLIPSIS_MARKER) in result


def test_format_friction_item_no_truncation_at_limit() -> None:
    snippet = "a" * SNIPPET_MAX_LENGTH
    result = format_friction_item("05:23", "confusion", snippet)
    assert ELLIPSIS_MARKER not in result


# ---------------------------------------------------------------------------
# 5. format_participant_range
# ---------------------------------------------------------------------------


def test_format_participant_range_empty() -> None:
    assert format_participant_range([]) == "none"


def test_format_participant_range_single() -> None:
    assert format_participant_range(["p1"]) == "p1"


def test_format_participant_range_multiple() -> None:
    result = format_participant_range(["p1", "p2", "p8"])
    assert result == f"p1{EN_DASH}p8"


# ---------------------------------------------------------------------------
# 6. Transcript header formatters
# ---------------------------------------------------------------------------


def test_format_transcript_header_txt() -> None:
    result = format_transcript_header_txt(
        participant_id="p1",
        source_file="interview_01.mp4",
        session_date="2026-01-10",
        duration="00:45:00",
    )
    assert "# Transcript: p1" in result
    assert "# Source: interview_01.mp4" in result
    assert "# Date: 2026-01-10" in result
    assert "# Duration: 00:45:00" in result


def test_format_transcript_header_txt_cooked() -> None:
    result = format_transcript_header_txt(
        participant_id="p1",
        source_file="interview_01.mp4",
        session_date="2026-01-10",
        duration="00:45:00",
        label="Transcript (cooked)",
        extra_headers={"PII entities redacted": "5"},
    )
    assert "# Transcript (cooked): p1" in result
    assert "# PII entities redacted: 5" in result


def test_format_transcript_header_md() -> None:
    result = format_transcript_header_md(
        participant_id="p1",
        source_file="interview_01.mp4",
        session_date="2026-01-10",
        duration="00:45:00",
    )
    assert result.startswith("# Transcript: p1")
    assert "**Source:** interview_01.mp4" in result
    assert "**Date:** 2026-01-10" in result
    assert "**Duration:** 00:45:00" in result
    assert result.endswith("---")


def test_format_transcript_header_md_extra_headers() -> None:
    result = format_transcript_header_md(
        participant_id="p1",
        source_file="interview_01.mp4",
        session_date="2026-01-10",
        duration="00:45:00",
        label="Transcript (cooked)",
        extra_headers={"PII entities redacted": "5"},
    )
    assert "# Transcript (cooked): p1" in result
    assert "**PII entities redacted:** 5" in result


# ---------------------------------------------------------------------------
# 7. Segment formatters
# ---------------------------------------------------------------------------


def test_format_raw_segment_txt_with_speaker() -> None:
    result = format_raw_segment_txt("00:16", "p1", "Speaker B", "Hello")
    assert result == "[00:16] [p1] (Speaker B) Hello"


def test_format_raw_segment_txt_no_speaker() -> None:
    result = format_raw_segment_txt("00:16", "p1", None, "Hello")
    assert result == "[00:16] [p1] Hello"


def test_format_raw_segment_md_with_speaker() -> None:
    result = format_raw_segment_md("00:16", "p1", "Speaker B", "Hello")
    assert result == "**[00:16] p1** (Speaker B) Hello"


def test_format_raw_segment_md_no_speaker() -> None:
    result = format_raw_segment_md("00:16", "p1", None, "Hello")
    assert result == "**[00:16] p1** Hello"


def test_format_cooked_segment_txt() -> None:
    result = format_cooked_segment_txt("00:16", "p1", "[NAME] said hi")
    assert result == "[00:16] [p1] [NAME] said hi"


def test_format_cooked_segment_md() -> None:
    result = format_cooked_segment_md("00:16", "p1", "[NAME] said hi")
    assert result == "**[00:16] p1** [NAME] said hi"
