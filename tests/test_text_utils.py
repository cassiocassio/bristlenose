"""Tests for text utility functions."""

from bristlenose.utils.text import (
    apply_smart_quotes,
    clean_transcript_text,
    remove_disfluencies,
    wrap_in_smart_quotes,
)


def test_apply_smart_quotes() -> None:
    result = apply_smart_quotes('"Hello world"')
    assert result == "\u201cHello world\u201d"


def test_apply_smart_quotes_apostrophe() -> None:
    result = apply_smart_quotes("I don't know")
    assert "\u2019" in result  # right single quote as apostrophe


def test_wrap_in_smart_quotes() -> None:
    result = wrap_in_smart_quotes("Hello world")
    assert result == "\u201cHello world\u201d"


def test_wrap_strips_existing_quotes() -> None:
    result = wrap_in_smart_quotes('"Hello world"')
    assert result == "\u201cHello world\u201d"

    result2 = wrap_in_smart_quotes("\u201cHello world\u201d")
    assert result2 == "\u201cHello world\u201d"


def test_remove_disfluencies_um() -> None:
    result = remove_disfluencies("I was um trying to find it")
    assert "um" not in result.lower()
    assert "..." in result
    assert "trying to find it" in result


def test_remove_disfluencies_you_know() -> None:
    result = remove_disfluencies("So you know it was really hard")
    assert "you know" not in result.lower()
    assert "..." in result


def test_remove_disfluencies_like_filler() -> None:
    result = remove_disfluencies("I was, like, trying to click it")
    assert "..." in result
    assert "trying to click it" in result


def test_remove_disfluencies_preserves_like_comparison() -> None:
    # "like" as comparison should not be removed
    result = remove_disfluencies("It looked like a dashboard")
    assert "like" in result


def test_clean_transcript_text() -> None:
    result = clean_transcript_text("  Hello   world  ")
    assert result == "Hello world"


def test_clean_transcript_text_double_periods() -> None:
    result = clean_transcript_text("Hello.. world")
    assert result == "Hello. world"
