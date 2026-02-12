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
    format_finder_date,
    format_finder_filename,
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


def test_format_quote_block_with_display_name() -> None:
    quote = _make_quote()
    result = format_quote_block(quote, display_name="Sarah")
    assert f"{EM_DASH} Sarah" in result
    assert "p1" not in result


def test_format_quote_block_display_name_none_uses_pid() -> None:
    quote = _make_quote(participant_id="p3")
    result = format_quote_block(quote, display_name=None)
    assert f"{EM_DASH} p3" in result


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


# ---------------------------------------------------------------------------
# 8. format_finder_date
# ---------------------------------------------------------------------------


def test_format_finder_date_today() -> None:
    from datetime import datetime

    now = datetime(2026, 1, 31, 18, 0, 0)
    dt = datetime(2026, 1, 31, 16, 59, 0)
    assert format_finder_date(dt, now=now) == "Today at 16:59"


def test_format_finder_date_today_midnight() -> None:
    from datetime import datetime

    now = datetime(2026, 1, 31, 23, 59, 0)
    dt = datetime(2026, 1, 31, 0, 0, 0)
    assert format_finder_date(dt, now=now) == "Today at 00:00"


def test_format_finder_date_yesterday() -> None:
    from datetime import datetime

    now = datetime(2026, 2, 1, 10, 0, 0)
    dt = datetime(2026, 1, 31, 17, 0, 0)
    assert format_finder_date(dt, now=now) == "Yesterday at 17:00"


def test_format_finder_date_yesterday_midnight() -> None:
    from datetime import datetime

    now = datetime(2026, 2, 1, 10, 0, 0)
    dt = datetime(2026, 1, 31, 0, 0, 0)
    assert format_finder_date(dt, now=now) == "Yesterday at 00:00"


def test_format_finder_date_older_same_year() -> None:
    from datetime import datetime

    now = datetime(2026, 2, 1, 10, 0, 0)
    dt = datetime(2026, 1, 29, 20, 56, 0)
    assert format_finder_date(dt, now=now) == "29 Jan 2026 at 20:56"


def test_format_finder_date_older_different_year() -> None:
    from datetime import datetime

    now = datetime(2026, 2, 1, 10, 0, 0)
    dt = datetime(2025, 12, 25, 8, 30, 0)
    assert format_finder_date(dt, now=now) == "25 Dec 2025 at 08:30"


def test_format_finder_date_no_zero_pad_day() -> None:
    from datetime import datetime

    now = datetime(2026, 2, 15, 10, 0, 0)
    dt = datetime(2026, 2, 9, 8, 30, 0)
    assert format_finder_date(dt, now=now) == "9 Feb 2026 at 08:30"


def test_format_finder_date_two_days_ago_not_yesterday() -> None:
    from datetime import datetime

    now = datetime(2026, 2, 3, 10, 0, 0)
    dt = datetime(2026, 2, 1, 16, 54, 0)
    assert format_finder_date(dt, now=now) == "1 Feb 2026 at 16:54"


# ---------------------------------------------------------------------------
# 9. format_finder_filename
# ---------------------------------------------------------------------------


def test_format_finder_filename_short_unchanged() -> None:
    assert format_finder_filename("report.html") == "report.html"


def test_format_finder_filename_exact_max_len() -> None:
    name = "a" * 20 + ".vtt"  # 24 chars
    assert format_finder_filename(name, max_len=24) == name


def test_format_finder_filename_truncates_long() -> None:
    result = format_finder_filename("Fishkeeping Research S3.vtt", max_len=24)
    assert len(result) <= 24
    assert result.endswith(".vtt")
    assert "\u2026" in result


def test_format_finder_filename_preserves_extension() -> None:
    result = format_finder_filename("very_long_filename_here.mp4", max_len=20)
    assert result.endswith(".mp4")
    assert "\u2026" in result


def test_format_finder_filename_no_extension() -> None:
    result = format_finder_filename("a" * 30, max_len=20)
    assert len(result) <= 20
    assert result.endswith("\u2026")


def test_format_finder_filename_keeps_front_and_back() -> None:
    result = format_finder_filename("Fishkeeping Research S3.vtt", max_len=24)
    # Front portion of stem preserved
    assert result.startswith("Fishkeeping")
    # Back portion of stem + extension preserved
    assert result.endswith("S3.vtt") or result.endswith(".vtt")
