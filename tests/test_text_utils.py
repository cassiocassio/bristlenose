"""Tests for text utility functions."""

from bristlenose.utils.text import (
    apply_smart_quotes,
    clean_transcript_text,
    remove_disfluencies,
    safe_filename,
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


# -- safe_filename tests --


class TestSafeFilename:
    """Adversarial tests for safe_filename — zip entry path safety."""

    def test_normal_name_unchanged(self) -> None:
        assert safe_filename("Sarah") == "Sarah"

    def test_preserves_spaces_and_case(self) -> None:
        assert safe_filename("p1 03m45 Sarah onboarding was confusing") == (
            "p1 03m45 Sarah onboarding was confusing"
        )

    def test_preserves_accents(self) -> None:
        assert safe_filename("José María") == "José María"

    def test_strips_path_separators(self) -> None:
        assert "/" not in safe_filename("path/to/evil")
        assert "\\" not in safe_filename("path\\to\\evil")

    def test_strips_path_traversal(self) -> None:
        result = safe_filename("../../etc/cron.d/evil")
        assert ".." not in result
        assert "/" not in result

    def test_strips_null_bytes(self) -> None:
        assert "\x00" not in safe_filename("hello\x00world")

    def test_strips_windows_illegal_chars(self) -> None:
        result = safe_filename('file: "test" <data> |pipe|')
        assert ":" not in result
        assert '"' not in result
        assert "<" not in result
        assert ">" not in result
        assert "|" not in result

    def test_strips_question_mark_and_asterisk(self) -> None:
        result = safe_filename("what? really* yes")
        assert "?" not in result
        assert "*" not in result

    def test_leading_dots_stripped(self) -> None:
        assert not safe_filename("...hidden").startswith(".")

    def test_trailing_dots_stripped(self) -> None:
        assert not safe_filename("file...").endswith(".")

    def test_leading_trailing_spaces_stripped(self) -> None:
        result = safe_filename("  spaced  ")
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    def test_empty_string_returns_underscore(self) -> None:
        assert safe_filename("") == "_"

    def test_all_unsafe_chars_returns_underscore(self) -> None:
        assert safe_filename('/:*?"<>|') == "_"

    def test_only_dots_returns_underscore(self) -> None:
        assert safe_filename("...") == "_"

    def test_truncation(self) -> None:
        long_name = "a" * 200
        result = safe_filename(long_name)
        assert len(result) <= 120

    def test_custom_max_length(self) -> None:
        result = safe_filename("a" * 50, max_length=30)
        assert len(result) <= 30

    def test_collapses_multiple_spaces(self) -> None:
        # Removing chars may leave double spaces
        result = safe_filename("hello / world")
        assert "  " not in result

    def test_apostrophe_preserved(self) -> None:
        """Quotes often contain apostrophes — these are safe in filenames."""
        assert "'" in safe_filename("i don't trust the results")

    def test_unicode_cjk_preserved(self) -> None:
        assert safe_filename("田中由紀") == "田中由紀"

    def test_emoji_preserved(self) -> None:
        # Emoji are valid filename chars on macOS and modern Windows
        assert safe_filename("test 🎉 file") == "test 🎉 file"

    def test_real_export_filename(self) -> None:
        """Realistic clip filename from the design doc."""
        result = safe_filename("p1 03m45 Sarah onboarding was confusing")
        assert result == "p1 03m45 Sarah onboarding was confusing"
