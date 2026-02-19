"""LLM prompt loader — reads prompt templates from Markdown files.

Each pipeline stage has a Markdown file in this directory containing both
a system prompt and a user prompt template, separated by ``## System``
and ``## User`` headings.  This module reads those files, caches them,
and exposes them via :func:`get_prompt`.

Backward-compatible constants (``SPEAKER_IDENTIFICATION_PROMPT``, etc.)
are still importable — they resolve lazily to the *user* prompt string
from the corresponding Markdown file.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import NamedTuple

_PROMPTS_DIR = Path(__file__).resolve().parent

_SECTION_RE = re.compile(r"^##\s+(system|user)\s*$", re.IGNORECASE | re.MULTILINE)


class PromptPair(NamedTuple):
    """A system prompt and user prompt template pair."""

    system: str
    user: str


@cache
def _load_prompt(name: str) -> PromptPair:
    path = _PROMPTS_DIR / f"{name}.md"
    text = path.read_text(encoding="utf-8")

    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(text))

    for i, match in enumerate(matches):
        section_name = match.group(1).lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[section_name] = text[start:end].strip()

    if "system" not in sections:
        msg = f"Prompt file {path.name} missing '## System' section"
        raise ValueError(msg)
    if "user" not in sections:
        msg = f"Prompt file {path.name} missing '## User' section"
        raise ValueError(msg)

    return PromptPair(system=sections["system"], user=sections["user"])


def get_prompt(name: str) -> PromptPair:
    """Load a prompt pair by stage name.

    Args:
        name: kebab-case stage name (e.g. ``"topic-segmentation"``).

    Returns:
        A :class:`PromptPair` with ``.system`` and ``.user`` attributes.
    """
    return _load_prompt(name)


# ---------------------------------------------------------------------------
# Backward-compatible constants
# ---------------------------------------------------------------------------

_CONSTANT_MAP: dict[str, str] = {
    "SPEAKER_IDENTIFICATION_PROMPT": "speaker-identification",
    "TOPIC_SEGMENTATION_PROMPT": "topic-segmentation",
    "QUOTE_EXTRACTION_PROMPT": "quote-extraction",
    "QUOTE_CLUSTERING_PROMPT": "quote-clustering",
    "THEMATIC_GROUPING_PROMPT": "thematic-grouping",
}


def __getattr__(name: str) -> str:
    """Lazy-load backward-compatible prompt constants."""
    if name in _CONSTANT_MAP:
        return _load_prompt(_CONSTANT_MAP[name]).user
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
