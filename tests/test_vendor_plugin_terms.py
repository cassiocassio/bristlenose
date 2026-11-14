"""Each vendor tab says that vendor's own word for a plugin, in every language.

The mapping is data (``bristlenose/locales/vendor-terms.json``; rule and refresh
method in ``docs/i18n-vendor-terms.md``). Two vendors call the same thing different words
per language (Spanish: Claude "Plugins", ChatGPT/Codex "Complementos"), so a
locale file that drifts to one shared word, or a vendor string that loses its
noun, fails here and not on a researcher's screen.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_LOCALES = Path(__file__).resolve().parent.parent / "bristlenose" / "locales"
_TERMS = json.loads((_LOCALES / "vendor-terms.json").read_text(encoding="utf-8"))

# The 21 full locales; zh-Hant-HK is a thin override that inherits zh-Hant.
_LOCALE_CODES = sorted(_TERMS["claude"]["locales"])


def _mcp_agents(locale: str) -> dict[str, str]:
    data = json.loads((_LOCALES / locale / "desktop.json").read_text(encoding="utf-8"))
    return (data["desktop"] if "desktop" in data else data)["mcpAgents"]


def test_the_data_covers_every_full_locale_for_both_vendors() -> None:
    shipped = sorted(
        p.name for p in _LOCALES.iterdir()
        if p.is_dir() and p.name != "zh-Hant-HK" and (p / "desktop.json").exists()
    )
    assert sorted(_TERMS["claude"]["locales"]) == shipped
    assert sorted(_TERMS["chatgpt"]["locales"]) == shipped


@pytest.mark.parametrize("vendor", ["claude", "chatgpt"])
@pytest.mark.parametrize("locale", _LOCALE_CODES)
def test_every_string_of_a_vendor_tab_carries_that_vendors_word(vendor: str, locale: str) -> None:
    stem = _TERMS[vendor]["locales"][locale]["stem"].lower()
    strings = _mcp_agents(locale)
    for key in _TERMS[vendor]["keys"]:
        assert key in strings, f"{locale} has no {key}"
        assert stem in strings[key].lower(), (
            f"{locale} {key} should carry the {vendor} word {stem!r}: {strings[key]!r}"
        )


@pytest.mark.parametrize("locale", _LOCALE_CODES)
def test_where_the_vendors_disagree_a_tab_does_not_borrow_the_other_vendors_word(
    locale: str,
) -> None:
    claude = _TERMS["claude"]["locales"][locale]["stem"].lower()
    chatgpt = _TERMS["chatgpt"]["locales"][locale]["stem"].lower()
    if claude in chatgpt or chatgpt in claude:
        return  # same word, or one stem inside the other: nothing to separate
    strings = _mcp_agents(locale)
    for key in _TERMS["chatgpt"]["keys"]:
        assert claude not in strings[key].lower(), (
            f"{locale} ChatGPT string {key} uses the Claude word {claude!r}: {strings[key]!r}"
        )
    for key in _TERMS["claude"]["keys"]:
        assert chatgpt not in strings[key].lower(), (
            f"{locale} Claude string {key} uses the ChatGPT word {chatgpt!r}: {strings[key]!r}"
        )


@pytest.mark.parametrize("locale", _LOCALE_CODES)
def test_the_claude_reinstall_how_to_quotes_claudes_sidebar_label(locale: str) -> None:
    """claudeReinstallHow tells the user which Claude section to open: that label is
    Claude's word as Claude shows it (Italian "Plugin", Russian "Plugins" in Latin)."""
    label = _TERMS["claude"]["locales"][locale]["label"]
    assert label in _mcp_agents(locale)["claudeReinstallHow"], (
        f"{locale}: claudeReinstallHow should name Claude's section {label!r}"
    )


def test_the_roster_is_not_empty_and_every_row_has_a_word() -> None:
    """An empty roster, stem or label would pass every other test having asserted nothing
    (`"" in text` is always true)."""
    for vendor in ("claude", "chatgpt"):
        assert _TERMS[vendor]["keys"], f"{vendor} has no keys to check"
        for locale, row in _TERMS[vendor]["locales"].items():
            assert row["stem"].strip() and row["stem"] == row["stem"].lower(), (vendor, locale)
            assert row["label"].strip(), (vendor, locale)


def test_every_english_vendor_string_that_says_plugin_is_in_the_roster() -> None:
    """A new claude*/chatgpt* string that says "plugin" in English must be listed (and so
    checked in 21 languages) or named here as covered another way."""
    covered_elsewhere = {"claudeReinstallHow"}  # pinned by the sidebar-label test below
    english = _mcp_agents("en")
    says_plugin = {
        k for k, v in english.items()
        if k.startswith(("claude", "chatgpt")) and "plugin" in v.lower()
    }
    listed = set(_TERMS["claude"]["keys"]) | set(_TERMS["chatgpt"]["keys"]) | covered_elsewhere
    assert says_plugin <= listed, f"not in vendor-terms.json keys: {sorted(says_plugin - listed)}"
