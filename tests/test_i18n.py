"""Tests for bristlenose.i18n module."""

from __future__ import annotations

import json

import pytest

from bristlenose.i18n import _LOCALE_DIR, SUPPORTED_LOCALES, get_locale, set_locale, t


@pytest.fixture(autouse=True)
def _reset_locale():
    """Reset locale to English before and after each test."""
    set_locale("en")
    yield
    set_locale("en")


class TestSetLocale:
    def test_set_valid_locale(self):
        set_locale("es")
        assert get_locale() == "es"

    def test_set_invalid_locale_falls_back_to_english(self):
        set_locale("zz")
        assert get_locale() == "en"

    def test_set_english(self):
        set_locale("en")
        assert get_locale() == "en"


class TestTranslation:
    # These exercise `t()` itself — simple key, nesting, a miss, interpolation —
    # and used `cli.*` as their corpus until that namespace was deleted on
    # 22 Sep 2026 (CLI chrome is English by decision, so its translations could
    # never be read). Repointed at `server.statusPage.*`, which is live and is
    # read by `status_page.py`. The assertions are unchanged in substance.
    def test_simple_key(self):
        result = t("server.statusPage.cliExitedWithCode", code="1")
        assert result == "CLI exited with code 1"

    def test_nested_key(self):
        result = t("server.statusPage.noRunCliShort")
        assert result == "Nothing to see here, yet."

    def test_missing_key_returns_raw_key(self):
        result = t("server.nonexistent.key")
        assert result == "server.nonexistent.key"

    def test_missing_namespace_returns_raw_key(self):
        result = t("nonexistent.key")
        assert result == "nonexistent.key"

    def test_no_namespace_separator_returns_raw_key(self):
        result = t("plainkey")
        assert result == "plainkey"

    def test_interpolation(self):
        result = t("preflight.whisper.banner_intro", size="1.5 GB")
        assert result == "Bristlenose needs the Whisper transcription model (1.5 GB)."

    def test_interpolation_missing_placeholder_returns_string(self):
        # If kwargs has extra keys, format_map just ignores them
        result = t("server.statusPage.cliExitedWithCode", code="2", extra="unused")
        assert result == "CLI exited with code 2"


class TestEnumTranslations:
    def test_sentiment_labels(self):
        assert t("enums.sentiment.frustration") == "Frustration"
        assert t("enums.sentiment.delight") == "Delight"

    def test_speaker_roles(self):
        assert t("enums.speakerRole.researcher") == "Researcher"
        assert t("enums.speakerRole.participant") == "Participant"


class TestLocaleFiles:
    """Validate that all English locale JSON files are well-formed."""

    def test_all_english_files_are_valid_json(self):
        en_dir = _LOCALE_DIR / "en"
        assert en_dir.exists(), f"English locale directory not found: {en_dir}"
        json_files = list(en_dir.glob("*.json"))
        assert len(json_files) > 0, "No English locale files found"
        for path in json_files:
            data = json.loads(path.read_text(encoding="utf-8"))
            assert isinstance(data, dict), f"{path.name} root must be a dict"

    def test_supported_locales_tuple(self):
        assert "en" in SUPPORTED_LOCALES
        assert len(SUPPORTED_LOCALES) >= 2
