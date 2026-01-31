"""Tests for Bristlenose data models and helpers."""

from bristlenose.models import (
    ExtractedQuote,
    QuoteType,
    format_timecode,
    parse_timecode,
)


def test_format_timecode() -> None:
    assert format_timecode(0) == "00:00"
    assert format_timecode(61) == "01:01"
    assert format_timecode(3661) == "01:01:01"
    assert format_timecode(3599.9) == "59:59"


def test_parse_timecode_hhmmss() -> None:
    assert parse_timecode("00:01:23") == 83.0
    assert parse_timecode("1:02:03") == 3723.0


def test_parse_timecode_mmss() -> None:
    assert parse_timecode("01:23") == 83.0
    assert parse_timecode("0:05") == 5.0


def test_parse_timecode_with_millis() -> None:
    result = parse_timecode("00:01:23.456")
    assert abs(result - 83.456) < 0.001


def test_format_timecode_boundary_one_hour() -> None:
    """59:59 → MM:SS, 01:00:00 → HH:MM:SS."""
    assert format_timecode(3599) == "59:59"
    assert format_timecode(3600) == "01:00:00"


def test_format_timecode_long_session() -> None:
    """Sessions >= 1 hour use HH:MM:SS."""
    assert format_timecode(7943) == "02:12:23"
    assert format_timecode(86400) == "24:00:00"
    assert format_timecode(90061) == "25:01:01"


def test_format_timecode_sub_minute() -> None:
    """Sessions under a minute still show MM:SS with zero minutes."""
    assert format_timecode(0) == "00:00"
    assert format_timecode(5) == "00:05"
    assert format_timecode(59) == "00:59"


def test_parse_timecode_round_trip_short() -> None:
    """format → parse round-trip for MM:SS."""
    for secs in [0, 30, 107, 599, 3599]:
        assert int(parse_timecode(format_timecode(secs))) == secs


def test_parse_timecode_round_trip_long() -> None:
    """format → parse round-trip for HH:MM:SS."""
    for secs in [3600, 7943, 86400, 90061]:
        assert int(parse_timecode(format_timecode(secs))) == secs


def test_quote_formatted() -> None:
    quote = ExtractedQuote(
        participant_id="p3",
        start_timecode=323.0,
        end_timecode=340.0,
        text="I just couldn\u2019t find the button anywhere.",
        topic_label="Dashboard",
        quote_type=QuoteType.SCREEN_SPECIFIC,
    )
    result = quote.formatted()
    assert "[05:23]" in result
    assert "\u201c" in result  # left smart quote
    assert "\u201d" in result  # right smart quote
    assert "p3" in result


def test_quote_formatted_with_context() -> None:
    quote = ExtractedQuote(
        participant_id="p1",
        start_timecode=100.0,
        end_timecode=120.0,
        text="I didn\u2019t even know that [page] existed.",
        topic_label="Settings",
        quote_type=QuoteType.SCREEN_SPECIFIC,
        researcher_context="When asked about the settings page",
    )
    result = quote.formatted()
    assert "[When asked about the settings page]" in result
    assert "\u201cI didn\u2019t even know" in result
