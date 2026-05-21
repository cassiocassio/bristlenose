"""Locale-key presence test for the pipeline diagnostic popover.

The desktop popover renders pill labels, headers, and actions via
`i18n.t("desktop.pipeline.diagnostic.*")` — if any locale is missing one
of the required keys the popover silently renders the raw dotted key.
This is a smoke test: every locale must carry every key.

CLDR plural keys are checked separately because the locale rules differ
(en/es/fr/de carry `_one` + `_other`; ko/ja carry `_other` only).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_LOCALES_DIR = Path(__file__).resolve().parents[1] / "bristlenose" / "locales"

_ALL_LOCALES = ("en", "es", "fr", "de", "ko", "ja")
_PLURAL_LOCALES = ("en", "es", "fr", "de")
_SINGLE_FORM_LOCALES = ("ko", "ja")

_REQUIRED_PILL_CATEGORIES = (
    "auth",
    "missing_binary",
    "quota",
    "network",
    "unknown",
)
_REQUIRED_HEADERS = ("completed_partial", "failed")
_REQUIRED_ACTIONS = ("copy",)
# `email` and `copied` keys were removed (Finding 31) — Email button was
# dropped during the Swift design pass and Copy is silent (no flip), so the
# keys had zero call sites.


def _load_desktop(locale: str) -> dict:
    path = _LOCALES_DIR / locale / "desktop.json"
    with path.open() as f:
        return json.load(f)


@pytest.mark.parametrize("locale", _ALL_LOCALES)
def test_pill_categories_present(locale: str) -> None:
    pill = _load_desktop(locale)["pipeline"]["diagnostic"]["pill"]
    for category in _REQUIRED_PILL_CATEGORIES:
        assert category in pill, (
            f"locale={locale} missing pill.{category}"
        )
        assert pill[category], f"locale={locale} pill.{category} is empty"


@pytest.mark.parametrize("locale", _ALL_LOCALES)
def test_headers_present(locale: str) -> None:
    header = _load_desktop(locale)["pipeline"]["diagnostic"]["header"]
    for key in _REQUIRED_HEADERS:
        assert key in header, f"locale={locale} missing header.{key}"


@pytest.mark.parametrize("locale", _ALL_LOCALES)
def test_actions_present(locale: str) -> None:
    action = _load_desktop(locale)["pipeline"]["diagnostic"]["action"]
    for key in _REQUIRED_ACTIONS:
        assert key in action, f"locale={locale} missing action.{key}"


@pytest.mark.parametrize("locale", _PLURAL_LOCALES)
def test_plural_locales_have_one_and_other(locale: str) -> None:
    diagnostic = _load_desktop(locale)["pipeline"]["diagnostic"]
    assert "overflow_one" in diagnostic, (
        f"locale={locale} missing overflow_one"
    )
    assert "overflow_other" in diagnostic, (
        f"locale={locale} missing overflow_other"
    )


@pytest.mark.parametrize("locale", _SINGLE_FORM_LOCALES)
def test_single_form_locales_have_only_other(locale: str) -> None:
    diagnostic = _load_desktop(locale)["pipeline"]["diagnostic"]
    assert "overflow_other" in diagnostic, (
        f"locale={locale} missing overflow_other"
    )
    # Negative assertion — single-form CLDR locales (ko/ja) must NOT carry
    # overflow_one. Catches accidental copy-paste from a plural locale.
    assert "overflow_one" not in diagnostic, (
        f"locale={locale} unexpectedly carries overflow_one"
    )
