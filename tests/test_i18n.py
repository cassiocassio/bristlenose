"""Tests for bristlenose.i18n module."""

from __future__ import annotations

import json

import pytest

from bristlenose.i18n import (
    _LOCALE_DIR,
    ENGLISH_ONLY_NAMESPACES,
    SUPPORTED_LOCALES,
    get_locale,
    set_locale,
    t,
    t_in,
)


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

    # Norwegian is a macrolanguage: `no` encompasses Bokmal (`nb`) and Nynorsk
    # (`nn`), and we ship only Bokmal. The desktop already resolves both to `nb`
    # because Apple's matcher does CLDR language matching (measured, see
    # docs/design-locale-negotiation.md section 1). Python had no such step, so
    # `bristlenose --lang no` silently ran in English.
    def test_norwegian_macrolanguage_resolves_to_bokmal(self):
        set_locale("no")
        assert get_locale() == "nb"

    def test_nynorsk_resolves_to_bokmal(self):
        set_locale("nn")
        assert get_locale() == "nb"

    def test_alias_is_one_way(self):
        # nb must never be rewritten to anything else.
        set_locale("nb")
        assert get_locale() == "nb"


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
        assert result == "This folder hasn’t been analysed yet"

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


class TestEnglishOnlyNamespaces:
    """``preflight`` is terminal chrome, and its text also becomes exception
    messages that land in ``Cause.message`` and in the stdout the Mac app
    classifies by English pattern. English whatever ``--lang`` says
    (docs/design-i18n.md, "Which surfaces are targets")."""

    def test_preflight_is_english_under_another_cli_language(self):
        set_locale("de")
        assert t("preflight.whisper.ready") == "Whisper model ready"

    def test_a_copy_that_comes_back_is_not_read(self, tmp_path, monkeypatch):
        """With the copies deleted, every locale falls back to English anyway,
        so only a copy on disk shows whether the resolver forces English."""
        import bristlenose.i18n as i18n_module

        for code, value in (("en", "Whisper model ready"), ("de", "Whisper-Modell bereit")):
            (tmp_path / code).mkdir()
            (tmp_path / code / "preflight.json").write_text(
                json.dumps({"whisper": {"ready": value}}), encoding="utf-8"
            )
        monkeypatch.setattr(i18n_module, "_LOCALE_DIR", tmp_path)
        i18n_module._load_namespace.cache_clear()
        try:
            assert t_in("de", "preflight.whisper.ready") == "Whisper model ready"
        finally:
            i18n_module._load_namespace.cache_clear()

    @pytest.mark.parametrize("locale", sorted(SUPPORTED_LOCALES))
    def test_t_in_answers_english_for_every_locale(self, locale: str):
        assert t_in(locale, "preflight.whisper.ready") == "Whisper model ready"

    def test_other_namespaces_still_translate(self):
        assert t_in("de", "enums.speakerRole.participant") != "Participant"

    def test_check_locales_names_the_same_namespaces(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "check_locales", _LOCALE_DIR.parents[1] / "scripts" / "check-locales.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.ENGLISH_ONLY_NAMESPACES == ENGLISH_ONLY_NAMESPACES

    def test_no_locale_ships_a_copy(self):
        """A copy would be read by no one and reviewed by no one."""
        copies = sorted(
            str(path.relative_to(_LOCALE_DIR))
            for ns in ENGLISH_ONLY_NAMESPACES
            for path in _LOCALE_DIR.glob(f"*/{ns}.json")
            if path.parent.name != "en"
        )
        assert copies == []


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


class TestLoadNamespaceGuard:
    """``_load_namespace`` takes both arguments from callers, so it reads only
    a supported locale and a plain namespace name, whatever the caller did."""

    @pytest.fixture
    def tree_with_a_file_outside(self, tmp_path, monkeypatch):
        """A locale tree plus a readable file just outside it, so an escape
        would load something rather than read as merely missing."""
        import bristlenose.i18n as i18n_module

        locales = tmp_path / "locales"
        (locales / "en").mkdir(parents=True)
        (locales / "en" / "common.json").write_text(
            json.dumps({"hello": "inside"}), encoding="utf-8"
        )
        (tmp_path / "outside").mkdir()
        (tmp_path / "outside" / "common.json").write_text(
            json.dumps({"hello": "outside"}), encoding="utf-8"
        )
        monkeypatch.setattr(i18n_module, "_LOCALE_DIR", locales)
        i18n_module._load_namespace.cache_clear()
        yield tmp_path
        i18n_module._load_namespace.cache_clear()

    def test_a_real_pair_loads(self, tree_with_a_file_outside):
        from bristlenose.i18n import _load_namespace

        assert _load_namespace("en", "common") == {"hello": "inside"}

    @pytest.mark.parametrize(
        ("locale", "namespace"),
        [
            ("../outside", "common"),
            ("en", "../../outside/common"),
        ],
    )
    def test_a_path_shaped_argument_reads_as_missing(
        self, tree_with_a_file_outside, locale, namespace
    ):
        from bristlenose.i18n import _load_namespace

        assert _load_namespace(locale, namespace) == {}

    def test_an_absolute_locale_reads_as_missing(self, tree_with_a_file_outside):
        from bristlenose.i18n import _load_namespace

        assert _load_namespace(str(tree_with_a_file_outside / "outside"), "common") == {}

    def test_an_absolute_namespace_reads_as_missing(self, tree_with_a_file_outside):
        from bristlenose.i18n import _load_namespace

        assert _load_namespace("en", str(tree_with_a_file_outside / "outside" / "common")) == {}

    def test_the_real_corpus_passes_the_guard(self):
        """Every locale directory and namespace file shipped is one the guard
        admits, so it excludes nothing real."""
        from bristlenose.i18n import _NAMESPACE_NAME

        for locale_dir in (p for p in _LOCALE_DIR.iterdir() if p.is_dir()):
            assert locale_dir.name in SUPPORTED_LOCALES, locale_dir.name
            for path in locale_dir.glob("*.json"):
                assert _NAMESPACE_NAME.fullmatch(path.stem), path
