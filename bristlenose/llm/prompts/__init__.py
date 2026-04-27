"""LLM prompt loader — reads prompt templates from Markdown files.

Each pipeline stage has a Markdown file in this directory containing both
a system prompt and a user prompt template, separated by ``## System``
and ``## User`` headings. A small YAML frontmatter block at the top
(``id``, ``version``) identifies the prompt for telemetry/cohort lookup.

This module reads those files, caches them, and exposes them via
:func:`get_prompt` (legacy shim returning system+user) and
:func:`get_prompt_template` (full template with id, version, sha, path).

Backward-compatible constants (``SPEAKER_IDENTIFICATION_PROMPT``, etc.)
are still importable — they resolve lazily to the *user* prompt string
from the corresponding Markdown file.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import NamedTuple

_PROMPTS_DIR = Path(__file__).resolve().parent

_SECTION_RE = re.compile(r"^##\s+(system|user)\s*$", re.IGNORECASE | re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_FRONTMATTER_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")


class PromptPair(NamedTuple):
    """A system prompt and user prompt template pair."""

    system: str
    user: str


@dataclass(frozen=True)
class PromptTemplate:
    """Full prompt template with identity for telemetry and cohort lookup."""

    id: str
    version: str
    sha: str
    system: str
    user: str
    path: Path


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Strip a YAML-ish frontmatter block from ``text`` and return (fields, body).

    Only ``key: value`` lines are parsed (no nested structures, no lists).
    If no frontmatter is present, returns an empty dict and the original text.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    fields: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        m = _FRONTMATTER_LINE_RE.match(line)
        if m:
            fields[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fields, text[match.end() :]


@cache
def _load_template(name: str) -> PromptTemplate:
    path = _PROMPTS_DIR / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

    fields, body = _parse_frontmatter(text)

    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(body))
    for i, match in enumerate(matches):
        section_name = match.group(1).lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[section_name] = body[start:end].strip()

    if "system" not in sections:
        msg = f"Prompt file {path.name} missing '## System' section"
        raise ValueError(msg)
    if "user" not in sections:
        msg = f"Prompt file {path.name} missing '## User' section"
        raise ValueError(msg)

    prompt_id = fields.get("id") or path.stem
    version = fields.get("version") or "0.0.0"

    return PromptTemplate(
        id=prompt_id,
        version=version,
        sha=sha,
        system=sections["system"],
        user=sections["user"],
        path=path,
    )


def get_prompt_template(name: str) -> PromptTemplate:
    """Load a full prompt template by stage name.

    Args:
        name: kebab-case stage name (e.g. ``"topic-segmentation"``).

    Returns:
        A :class:`PromptTemplate` with id, version, sha, system, user, path.
    """
    return _load_template(name)


def get_prompt(name: str) -> PromptPair:
    """Load a prompt pair by stage name (legacy shim).

    Args:
        name: kebab-case stage name (e.g. ``"topic-segmentation"``).

    Returns:
        A :class:`PromptPair` with ``.system`` and ``.user`` attributes.
    """
    tmpl = _load_template(name)
    return PromptPair(system=tmpl.system, user=tmpl.user)


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
        return _load_template(_CONSTANT_MAP[name]).user
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
