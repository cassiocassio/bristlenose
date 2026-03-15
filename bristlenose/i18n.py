"""Lightweight i18n module for Bristlenose CLI and server.

Loads translations from JSON files in bristlenose/locales/<locale>/<namespace>.json.
Shares the same JSON format as the frontend (react-i18next) so translators work
with one file format.

Usage:
    from bristlenose.i18n import t, set_locale

    set_locale("es")
    print(t("cli.stage.transcribe"))  # "Transcribir"
    print(t("cli.version", version="0.13.4"))  # "bristlenose 0.13.4"
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_LOCALE_DIR = Path(__file__).parent / "locales"

SUPPORTED_LOCALES = ("en", "es", "ja", "fr", "de", "ko")

_current_locale = "en"


@lru_cache(maxsize=64)
def _load_namespace(locale: str, namespace: str) -> dict[str, object]:
    """Load a single namespace JSON file. Falls back to English if missing."""
    path = _LOCALE_DIR / locale / f"{namespace}.json"
    if not path.exists():
        if locale != "en":
            return _load_namespace("en", namespace)
        return {}
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


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


def t(key: str, **kwargs: object) -> str:
    """Translate a dotted key. Format: ``"namespace.dotted.key"``.

    Interpolation uses Python ``str.format_map``:
        t("cli.version", version="0.13.4")  →  "bristlenose {version}" → "bristlenose 0.13.4"

    Falls back to the English string, then to the raw key.
    """
    namespace, _, dotted = key.partition(".")
    if not dotted:
        return key  # No namespace separator — return raw key

    parts = dotted.split(".")

    # Try current locale first
    strings = _load_namespace(_current_locale, namespace)
    value = _resolve(strings, parts)

    # Fallback to English
    if value is None and _current_locale != "en":
        strings = _load_namespace("en", namespace)
        value = _resolve(strings, parts)

    if value is None:
        return key  # Last resort — return raw key

    if kwargs:
        try:
            return value.format_map({k: str(v) for k, v in kwargs.items()})
        except (KeyError, IndexError):
            return value
    return value


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
