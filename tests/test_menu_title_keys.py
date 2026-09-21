"""The macOS menu-bar titles go through `LocalizedStringKey`, which eats markdown.

`CommandMenu` takes a `LocalizedStringKey`, not a `String`. Building one from a
runtime string works — the bundle ships no `Localizable.strings` and declares
`knownRegions = (en, Base)`, so the lookup always misses and the key's own
content renders — which is what lets the menu bar follow the app's JSON locale
at all (`MenuCommands.swift`, `CustomMenus.body`).

The idiom carries one hazard, and it is silent: **`LocalizedStringKey` interprets
markdown and `%` format specifiers.** A translation containing `*`, `_`, a
backtick or a bracket pair would render with the characters eaten and the text
styled; one containing `%` would be read as a format specifier against an empty
argument list. Today every value is a single plain noun, so the hazard is
theoretical — which is exactly when it is worth pinning, because the next
translator to touch one of these four keys has no way to know.

Also pins the four keys as *read*: these are string literals in Swift, so a
rename in the JSON is invisible to `tsc`, to mypy and to `check-locales.py`
(the key would still exist, just unread — failure class 5). Same shape as the
`TAB_ROUTES` lookup-key trap in CLAUDE.md § Gotchas.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_LOCALES = _ROOT / "bristlenose" / "locales"
_MENU_COMMANDS = _ROOT / "desktop/Bristlenose/Bristlenose/MenuCommands.swift"

# The four menu-bar titles, as dotted keys. Diagnostics is deliberately absent:
# App-Store-hidden chrome, English by docs/design-i18n.md § "Which surfaces are
# targets".
MENU_TITLE_KEYS = (
    "common.nav.project",
    "desktop.toolbar.codes",
    "common.nav.quotes",
    "desktop.menu.video.title",
)

# Markdown syntax LocalizedStringKey honours, plus the format-specifier lead-in.
FORBIDDEN = set("*_`[]()~%")


def _resolve(locale: str, dotted: str) -> str | None:
    namespace, *parts = dotted.split(".")
    path = _LOCALES / locale / f"{namespace}.json"
    if not path.is_file():
        return None
    node: object = json.loads(path.read_text(encoding="utf-8"))
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) else None


def _full_locales() -> list[str]:
    # zh-Hant-HK is a thin override fork that inherits zh-Hant — absence there
    # is correct, not a gap (CLAUDE.md § i18n).
    return sorted(
        d.name
        for d in _LOCALES.iterdir()
        if d.is_dir() and (d / "common.json").is_file() and d.name != "zh-Hant-HK"
    )


@pytest.mark.parametrize("key", MENU_TITLE_KEYS)
def test_menu_title_key_is_read_by_swift(key: str) -> None:
    """A renamed key is invisible to every other gate — the literal is the contract."""
    source = _MENU_COMMANDS.read_text(encoding="utf-8")
    assert f'i18n.t("{key}")' in source, (
        f'{key} is no longer read by MenuCommands.swift. If the menu title moved to '
        f"another key, update MENU_TITLE_KEYS here in the same commit — otherwise the "
        f"old key lives on untested and the new one renders unguarded."
    )


@pytest.mark.parametrize("locale", _full_locales())
def test_menu_titles_survive_localizedstringkey(locale: str) -> None:
    for key in MENU_TITLE_KEYS:
        value = _resolve(locale, key)
        assert value, f"{locale}: {key} missing — the menu bar would render the raw key"
        bad = sorted(FORBIDDEN & set(value))
        assert not bad, (
            f"{locale}: {key} = {value!r} contains {bad}, which SwiftUI's "
            f"LocalizedStringKey would interpret as markdown or a format specifier "
            f"rather than render. Menu titles are plain nouns — reword, or stop "
            f"routing this title through LocalizedStringKey."
        )
