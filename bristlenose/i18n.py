"""Lightweight i18n module for Bristlenose CLI and server.

Loads translations from JSON files in bristlenose/locales/<locale>/<namespace>.json.
Shares the same JSON format as the frontend (react-i18next) so translators work
with one file format.

Usage:
    from bristlenose.i18n import t, set_locale

    set_locale("es")
    print(t("server.statusPage.noRunCliShort"))  # "Aquí no hay nada todavía."
    print(t("preflight.closing.no_more_questions", estimate_suffix=""))
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

_LOCALE_DIR = Path(__file__).parent / "locales"

SUPPORTED_LOCALES = ("en", "es", "ca", "ja", "fr", "de", "ko", "cs", "it", "pl", "ru", "uk", "da", "sv", "nb", "tr", "nl", "fi", "pt-BR", "pt-PT", "zh-Hant", "zh-Hant-HK")

# Region/script variants borrow missing keys from a base locale before falling
# back to English. zh-Hant-HK (Hong Kong) → zh-Hant (Taiwan Traditional) → en.
# TW/HK Traditional Chinese are mutually intelligible, so borrowing is correct,
# not lossy — a missing HK string resolving to the Taiwan one beats English.
_FALLBACK_CHAINS: dict[str, tuple[str, ...]] = {
    "zh-Hant-HK": ("zh-Hant",),
}

#: Locales that ship ONLY the namespaces they override, inheriting the rest.
#: An absent namespace file is how a fork inherits — it is the design, never a
#: gap — so anything asserting completeness must exempt these.
#:
#: Deliberately NOT derived from ``_FALLBACK_CHAINS``. The two coincide today
#: and are different properties: a full locale could sensibly acquire a chain
#: (pt-BR → pt-PT), and deriving would then silently exempt it from checks that
#: exist to catch a half-shipped tree. Name the property, don't infer it.
#:
#: This lived in ``tests/test_pipeline_diagnostic_locale_keys.py`` from 3 Jul
#: 2026 (``b6ae8951``) and was promoted here 22 Sep 2026, because ``doctor.py``
#: needs it and a self-test running inside a PyInstaller bundle can import
#: ``bristlenose.i18n`` but not a test module. The test constant now derives
#: from this one, so there is a single copy.
FALLBACK_ONLY_LOCALES: frozenset[str] = frozenset({"zh-Hant-HK"})

_current_locale = "en"


@lru_cache(maxsize=64)
def _load_namespace(locale: str, namespace: str) -> dict[str, object]:
    """Load a single namespace JSON file. Returns {} if missing — the caller
    (`t`) walks the fallback chain, so a thin-override locale that ships only
    some namespaces resolves the rest through its base, not straight to en."""
    path = _LOCALE_DIR / locale / f"{namespace}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _resolution_order(locale: str) -> tuple[str, ...]:
    """Lookup order for a locale: itself, its fallback base(s), then English."""
    order = [locale, *_FALLBACK_CHAINS.get(locale, ())]
    if "en" not in order:
        order.append("en")
    return tuple(order)


def locale_resources(
    locale: str, namespaces: Sequence[str]
) -> dict[str, dict[str, object]]:
    """Every namespace in ``locale``'s resolution order, keyed locale -> namespace.

    Built for the HTML export, which inlines the chrome strings for exactly the
    languages the report can render in rather than all 22.  Returns the whole
    **chain**, never the leaf: ``zh-Hant-HK`` is deliberately a thin override
    fork carrying only genuine HK-idiom differences, so shipping it alone would
    render raw keys — ``codebook.frameworks`` — at whoever the report was sent
    to.  English rides under every locale for the same reason: it costs ~35 KB
    and removes the failure mode where a future key gap prints a key name in an
    artefact nobody can correct after it has been sent.

    Locales that contribute no files are omitted rather than returned empty, so
    the caller can embed the result without pruning.
    """
    out: dict[str, dict[str, object]] = {}
    for loc in _resolution_order(locale if locale in SUPPORTED_LOCALES else "en"):
        bundle = {
            ns: data for ns in namespaces if (data := _load_namespace(loc, ns))
        }
        if bundle:
            out[loc] = bundle
    return out


def _resolve(data: object, parts: list[str]) -> str | None:
    """Walk a nested dict by dotted key parts."""
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
            if current is None:
                return None
        else:
            return None
    if isinstance(current, str):
        return current
    return None


_I18NEXT_VAR = re.compile(r"\{\{(\w+)\}\}")


def _interpolate(value: str, vars: dict[str, str]) -> str:
    """Substitute both placeholder conventions the locale corpus actually uses.

    The files carry **two**, and which one a value uses is a property of who
    wrote it, not of the namespace: ``preflight`` was authored for Python and
    spells a variable ``{size}``; everything the SPA reads is i18next and spells
    it ``{{size}}`` — 249 values against 17, measured 22 Sep 2026.

    Python's ``str.format_map`` reads ``{{`` as an *escaped literal brace*, so a
    double-brace value passed straight to it renders ``{count} quotes`` — the
    variable name, in braces, in the artefact. No Python caller read such a key
    until the Miro board did, so this was latent rather than broken; the board is
    the first, and a gate (``test_miro_board_locale.py``) now keeps it honest.

    i18next form first, then ``format_map`` for the Python form.
    """
    out = _I18NEXT_VAR.sub(lambda m: vars.get(m.group(1), m.group(0)), value)
    try:
        return out.format_map(vars)
    except (KeyError, IndexError, ValueError):
        return out


def t_in(locale: str, key: str, **kwargs: object) -> str:
    """``t`` bound to one locale, without touching the module global.

    ``set_locale`` is process-wide, which is right for the CLI (one run, one
    language) and wrong for the server, where two requests can want two
    languages and the loser gets the winner's. Every server-side caller should
    reach for this; ``t`` is the CLI's convenience and is defined in terms of it.
    """
    namespace, _, dotted = key.partition(".")
    if not dotted:
        return key  # No namespace separator — return raw key

    parts = dotted.split(".")

    # Resolve through the locale's fallback chain: requested → base(s) → en.
    value = None
    for loc in _resolution_order(locale if locale in SUPPORTED_LOCALES else "en"):
        value = _resolve(_load_namespace(loc, namespace), parts)
        if value is not None:
            break

    if value is None:
        return key  # Last resort — return raw key

    if kwargs:
        return _interpolate(value, {k: str(v) for k, v in kwargs.items()})
    return value


def t(key: str, **kwargs: object) -> str:
    """Translate a dotted key in the process-wide locale. ``"namespace.dotted.key"``.

    Falls back to the English string, then to the raw key.
    """
    return t_in(_current_locale, key, **kwargs)


def plural_category(count: int, locale: str) -> str:
    """The CLDR plural category for an integer — the Python half of a pair.

    `I18n.swift`'s `pluralCategory(_:locale:)` is the other half and came first;
    `tests/test_plural_category_parity.py` asserts the two agree across every
    supported locale over a range that includes each rule's exceptions, so this
    cannot drift into a board that counts one way and a menu that counts another.

    `count` is always an ``int``, so CLDR's decimal fraction ``v`` is 0 and the
    decimals-only categories never fire. That is why ``cs`` returns ``other``
    where ``pl`` returns ``many``: Czech's ``many`` is decimals-only and Polish's
    is a live integer category. Do not copy the ``cs`` branch to a new Slavic
    locale — its shape is cs-specific and wrong for the others.
    """
    n = abs(count)
    mod10, mod100 = n % 10, n % 100
    if locale == "cs":
        # Czech: one = 1; few = 2–4; other = 0, 5+ (many is decimals-only).
        if n == 1:
            return "one"
        return "few" if 2 <= n <= 4 else "other"
    if locale == "pl":
        # Polish: one = 1; few = mod10 2–4 except teens; many = the rest
        # (0, 5–21, …). 21 → many, unlike ru/uk where 21 → one.
        if n == 1:
            return "one"
        if 2 <= mod10 <= 4 and not 12 <= mod100 <= 14:
            return "few"
        return "many"
    if locale in ("ru", "uk"):
        # Russian and Ukrainian share an identical integer rule.
        if mod10 == 1 and mod100 != 11:
            return "one"
        if 2 <= mod10 <= 4 and not 12 <= mod100 <= 14:
            return "few"
        return "many"
    if locale == "fr":
        return "one" if n <= 1 else "other"  # French: 0 and 1 are both "one".
    if locale in ("ja", "ko", "zh-Hant", "zh-Hant-HK"):
        return "other"  # Single-form locales.
    return "one" if n == 1 else "other"  # en, es, de, and any unmapped locale.


def plural_in(locale: str, base: str, count: int, **kwargs: object) -> str:
    """Resolve ``<base>_<category>`` for ``count`` in ``locale``, ``count`` bound.

    Degrades to ``<base>_other`` when the selected stem is absent, which covers
    both real cases: a single-form locale carrying only ``_other``, and a locale
    whose category exists in CLDR but not in this key. Without it, pl/ru/uk would
    be the first to render a raw ``…_many`` into a researcher's deliverable.
    """
    merged: dict[str, object] = {**kwargs, "count": count}
    key = f"{base}_{plural_category(count, locale)}"
    rendered = t_in(locale, key, **merged)
    if rendered == key:  # a miss returns the raw key, which carries no count
        return t_in(locale, f"{base}_other", **merged)
    return rendered


def get_locale() -> str:
    """Return the current locale code."""
    return _current_locale


def set_locale(locale: str) -> None:
    """Set the active locale. Clears the file cache."""
    global _current_locale
    if locale not in SUPPORTED_LOCALES:
        locale = "en"
    _current_locale = locale
    _load_namespace.cache_clear()
