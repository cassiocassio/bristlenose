"""``--lang FR`` and ``fr_FR.UTF-8`` mean French (N154, owner ruling 1 Nov 2026).

``canonical_locale`` used to compare the raw string with the shipped codes, so any spelling
that was not exact (case, a region, an environment-style ``.UTF-8``) silently ran in English.
The spelling is forgiven; the language is not guessed.
"""

from __future__ import annotations

import pytest

from bristlenose.i18n import SUPPORTED_LOCALES, canonical_locale, get_locale, set_locale


@pytest.mark.parametrize(
    ("typed", "means"),
    [
        ("FR", "fr"),
        ("Fr", "fr"),
        ("fr-FR", "fr"),
        ("fr_FR", "fr"),
        ("fr_FR.UTF-8", "fr"),
        ("de_DE@euro", "de"),
        ("fr.UTF-8", "fr"),  # no region: only the encoding strip finds it
        ("de@euro", "de"),
        ("ja-JP", "ja"),
        ("en-GB", "en"),
        ("PT-br", "pt-BR"),
        ("pt_PT", "pt-PT"),
        ("zh-hant", "zh-Hant"),
        ("ZH-HANT-HK", "zh-Hant-HK"),
        ("zh-Hant-TW", "zh-Hant"),
        # What macOS puts in LANG for Traditional Chinese: unambiguous, so named (not guessed).
        ("zh-TW", "zh-Hant"),
        ("zh_TW.UTF-8", "zh-Hant"),
        ("zh-HK", "zh-Hant-HK"),
        ("ZH_hk", "zh-Hant-HK"),
        ("nb-NO", "nb"),
        ("no", "nb"),
        ("no-NO", "nb"),
        ("nn", "nb"),
        ("  es  ", "es"),
    ],
)
def test_a_spelling_that_names_a_shipped_language_means_it(typed: str, means: str) -> None:
    assert canonical_locale(typed) == means


@pytest.mark.parametrize("typed", SUPPORTED_LOCALES)
def test_every_shipped_code_still_means_itself(typed: str) -> None:
    assert canonical_locale(typed) == typed


@pytest.mark.parametrize(
    "typed",
    ["pt", "zh", "zh-CN", "zz", "xx-YY", "", "-", "C", "POSIX", "zz\nINJECT", "../../etc"],
)
def test_what_is_ambiguous_or_unknown_stays_english_and_is_never_echoed(typed: str) -> None:
    # `pt` and `zh` are ambiguous between shipped locales: guessing one would be a choice
    # nobody made. The result is always one of our own codes, never the typed string.
    assert canonical_locale(typed) == "en"


def test_set_locale_takes_the_forgiven_spelling() -> None:
    set_locale("FR_fr.UTF-8")
    try:
        assert get_locale() == "fr"
    finally:
        set_locale("en")
