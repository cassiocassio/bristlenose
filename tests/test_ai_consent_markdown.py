"""The AI disclosure's Agent Access text carries Markdown emphasis (``*are*`` in English).

The Mac app parses that one string as Markdown (``AIConsentView.footnote``), so an unmatched
asterisk in a translation would show as a literal "*". A language may move the emphasis to
its own word or drop it (Japanese, Korean, Chinese), but never leave half a pair. Nothing
else checked this: ``scripts/check-locales.py`` does not compare Markdown markers.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

LOCALES = Path(__file__).resolve().parents[1] / "bristlenose" / "locales"
LOCALE_FILES = sorted(LOCALES.glob("*/desktop.json"))


def _agent_access(path: Path) -> str | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("aiConsent", {}).get("agentAccess")


def test_english_carries_the_emphasis() -> None:
    text = _agent_access(LOCALES / "en" / "desktop.json")
    assert text is not None
    assert "*are*" in text


@pytest.mark.parametrize("path", LOCALE_FILES, ids=lambda p: p.parent.name)
def test_agent_access_emphasis_is_balanced(path: Path) -> None:
    text = _agent_access(path)
    if text is None:  # a thin override fork (zh-Hant-HK) carries only real overrides
        return
    assert "**" not in text, "bold is not used here; one pair of single asterisks at most"
    assert text.count("*") in (0, 2), f"{path.parent.name}: {text.count('*')} asterisks"
