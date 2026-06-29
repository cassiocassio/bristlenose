"""Locale-key presence test for the pipeline diagnostic popover.

The desktop popover renders pill labels, headers, and actions via
`i18n.t("desktop.pipeline.diagnostic.*")` — if any locale is missing one
of the required keys the popover silently renders the raw dotted key.
This is a smoke test: every locale must carry every key.

CLDR plural keys are checked separately because the locale rules differ
(en/es/fr/de carry `_one` + `_other`; ko/ja carry `_other` only; Czech is the
first four-form locale — `_one`/`_few`/`_many`/`_other`).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_LOCALES_DIR = Path(__file__).resolve().parents[1] / "bristlenose" / "locales"

# zh-Hant is a full locale (single-form, like ja/ko). zh-Hant-HK is a thin
# override that ships only HK term deltas and resolves the rest via the
# fallback chain — so it is NOT listed here (these tests read each locale's
# desktop.json directly, with no fallback).
_ALL_LOCALES = ("en", "es", "fr", "de", "ko", "ja", "cs", "zh-Hant")
_PLURAL_LOCALES = ("en", "es", "fr", "de", "cs")
_SINGLE_FORM_LOCALES = ("ko", "ja", "zh-Hant")

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


@pytest.mark.parametrize("locale", _ALL_LOCALES)
def test_four_form_locales_carry_all_forms(locale: str) -> None:
    # Czech is the first four-form locale. A locale that carries `overflow_few`
    # (the 2–4 form) MUST also carry `_one`, `_many`, and `_other` — a partial
    # four-form set (e.g. `_few` without `_many`) would silently render the
    # wrong grammar at runtime. Derived from the presence of `_few`, so a
    # future four-form locale is covered without a hardcoded list. (Guards the
    # gap behind the Swift CLDR-selector fix: the desktop selector now requests
    # `overflow_few` for Czech counts 2–4, so the form must exist.)
    diagnostic = _load_desktop(locale)["pipeline"]["diagnostic"]
    if "overflow_few" in diagnostic:
        for form in ("overflow_one", "overflow_few", "overflow_many", "overflow_other"):
            assert form in diagnostic, (
                f"locale={locale} carries overflow_few but is missing {form} "
                "(four-form CLDR locales need all of one/few/many/other)"
            )


# ── chrome.* count strings — sidebar row interview/unanalysed/missing deltas ─
# ProjectRow.swift renders these via `deltaText` → `pluralCategory`, the same
# CLDR-selector class as the diagnostic overflow. These were converted from the
# legacy camelCase `One`/`Other` binary pair (which mis-rendered Czech counts
# 2–4) to snake_case `_one`/`_few`/`_many`/`_other` forms (Finding 14). Same
# per-locale form rules as overflow: en/es/fr/de carry one+other, ko/ja carry
# only other, cs carries all four.
_CHROME_COUNT_PREFIXES = ("interviewCount", "unanalysedSubtitle", "missingSubtitle")


def _chrome_count(locale: str) -> dict:
    return _load_desktop(locale)["chrome"]


@pytest.mark.parametrize("locale", _PLURAL_LOCALES)
@pytest.mark.parametrize("prefix", _CHROME_COUNT_PREFIXES)
def test_chrome_count_plural_locales_have_one_and_other(prefix: str, locale: str) -> None:
    chrome = _chrome_count(locale)
    assert chrome.get(f"{prefix}_one"), f"locale={locale} missing chrome.{prefix}_one"
    assert chrome.get(f"{prefix}_other"), f"locale={locale} missing chrome.{prefix}_other"
    # The legacy camelCase keys must be gone — a stray `interviewCountOne` would
    # mean a half-finished conversion that the Swift selector never reads.
    assert f"{prefix}One" not in chrome, f"locale={locale} still carries legacy chrome.{prefix}One"
    assert f"{prefix}Other" not in chrome, f"locale={locale} still carries legacy chrome.{prefix}Other"


@pytest.mark.parametrize("locale", _SINGLE_FORM_LOCALES)
@pytest.mark.parametrize("prefix", _CHROME_COUNT_PREFIXES)
def test_chrome_count_single_form_locales_have_only_other(prefix: str, locale: str) -> None:
    chrome = _chrome_count(locale)
    assert chrome.get(f"{prefix}_other"), f"locale={locale} missing chrome.{prefix}_other"
    assert f"{prefix}_one" not in chrome, (
        f"locale={locale} unexpectedly carries chrome.{prefix}_one "
        "(ko/ja are single-form — other only)"
    )


@pytest.mark.parametrize("locale", _ALL_LOCALES)
@pytest.mark.parametrize("prefix", _CHROME_COUNT_PREFIXES)
def test_chrome_count_four_form_locales_carry_all_forms(prefix: str, locale: str) -> None:
    # Presence of `_few` (the 2–4 form) implies a four-form locale (cs) that
    # MUST carry all of one/few/many/other — derived from `_few` so a future
    # four-form locale is covered without a hardcoded list.
    chrome = _chrome_count(locale)
    if f"{prefix}_few" in chrome:
        for form in ("_one", "_few", "_many", "_other"):
            assert chrome.get(f"{prefix}{form}"), (
                f"locale={locale} carries chrome.{prefix}_few but is missing "
                f"chrome.{prefix}{form} (four-form locales need one/few/many/other)"
            )


# ── pipeline.status.* — the activity-pill / popover live status strings ──────
# (PipelineActivityItem.swift; added in the cz-branch desktop i18n wave). Same
# silent-failure class as the diagnostic block: a missing key renders the raw
# dotted string in the running-analysis popover.
_REQUIRED_STATUS_KEYS = (
    "stopping", "starting", "analysing", "working", "stage", "stageShort",
    "queued", "waitingSubprocess", "resuming", "startingUp", "elapsed",
    "waitingInQueue", "stop",
)
_REQUIRED_STATUS_HEADLINE = ("running", "stopping", "queued", "failed")
_REQUIRED_STATUS_HELP = ("running", "queued", "failed")
_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _flatten_status(status: dict) -> dict:
    """Flatten one level of nesting (headline.*, help.*) into dotted keys."""
    out: dict[str, str] = {}
    for k, v in status.items():
        if isinstance(v, dict):
            for k2, v2 in v.items():
                out[f"{k}.{k2}"] = v2
        else:
            out[k] = v
    return out


@pytest.mark.parametrize("locale", _ALL_LOCALES)
def test_pipeline_status_keys_present(locale: str) -> None:
    status = _load_desktop(locale)["pipeline"]["status"]
    for key in _REQUIRED_STATUS_KEYS:
        assert status.get(key), f"locale={locale} missing/empty status.{key}"
    for key in _REQUIRED_STATUS_HEADLINE:
        assert status.get("headline", {}).get(key), (
            f"locale={locale} missing/empty status.headline.{key}"
        )
    for key in _REQUIRED_STATUS_HELP:
        assert status.get("help", {}).get(key), (
            f"locale={locale} missing/empty status.help.{key}"
        )


@pytest.mark.parametrize("locale", [loc for loc in _ALL_LOCALES if loc != "en"])
def test_pipeline_status_placeholders_match_english(locale: str) -> None:
    # A dropped/typo'd {{placeholder}} during translation ships a literal
    # `{{index}}` or a blank to users — the i18n.t substitution silently no-ops.
    en = _flatten_status(_load_desktop("en")["pipeline"]["status"])
    loc = _flatten_status(_load_desktop(locale)["pipeline"]["status"])
    for key, en_val in en.items():
        en_ph = set(_PLACEHOLDER_RE.findall(en_val))
        loc_ph = set(_PLACEHOLDER_RE.findall(loc.get(key, "")))
        assert en_ph == loc_ph, (
            f"locale={locale} status.{key} placeholder mismatch: "
            f"en={en_ph} {locale}={loc_ph}"
        )


@pytest.mark.parametrize("locale", _ALL_LOCALES)
def test_status_and_chrome_pipeline_agree(locale: str) -> None:
    # `pipeline.status.*` (activity popover) and `chrome.pipeline.*` (sidebar
    # row) deliberately use separate key-sets, but MUST render the same word
    # for the states they share — else the two surfaces fork (they did once:
    # de "Wird gestoppt…" vs "Wird angehalten…"). This pins the contract.
    d = _load_desktop(locale)
    status = d["pipeline"]["status"]
    chrome = d["chrome"]["pipeline"]
    for key in ("stopping", "analysing"):
        assert status[key] == chrome[key], (
            f"locale={locale} status.{key}={status[key]!r} != "
            f"chrome.pipeline.{key}={chrome[key]!r}"
        )
