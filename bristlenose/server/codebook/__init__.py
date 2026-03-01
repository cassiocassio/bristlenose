"""Codebook template loader — reads YAML files from this directory.

Each codebook framework (Garrett, Norman, UXR, etc.) is a separate YAML
file with metadata, groups, and tags.  Tags may include discrimination
prompt fields (definition, apply_when, not_this) used by the AutoCode
engine.  Files are auto-discovered: drop a new ``.yaml`` file here and
it appears in the codebook picker.

Public API::

    from bristlenose.server.codebook import (
        get_template,
        load_all_templates,
        CodebookTemplate,
        TemplateGroup,
        TemplateTag,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import yaml

_TEMPLATES_DIR = Path(__file__).resolve().parent

_VALID_COLOUR_SETS = frozenset({"ux", "emo", "task", "trust", "opp"})


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TemplateTag:
    name: str
    definition: str = ""
    apply_when: str = ""
    not_this: str = ""


@dataclass(frozen=True)
class TemplateGroup:
    name: str
    subtitle: str
    colour_set: str  # "ux", "emo", "task", "trust", "opp"
    tags: list[TemplateTag] = field(default_factory=list)


@dataclass(frozen=True)
class CodebookTemplate:
    id: str
    title: str
    author: str
    description: str
    author_bio: str
    author_links: list[tuple[str, str]]  # [(label, url), ...]
    preamble: str = ""
    groups: list[TemplateGroup] = field(default_factory=list)
    enabled: bool = True
    sort_order: int = 50  # lower = earlier in browse list


# ---------------------------------------------------------------------------
# YAML → dataclass parsing
# ---------------------------------------------------------------------------


def _str(value: Any) -> str:
    """Convert a YAML value to a stripped string.

    YAML ``>`` (folded) scalars include a trailing newline.  Strip it so
    callers always get clean text.
    """
    if value is None:
        return ""
    return str(value).strip()


def _require(raw: dict[str, Any], key: str, filename: str) -> Any:
    """Return raw[key] or raise ValueError with a clear message."""
    if key not in raw:
        msg = f"{filename}: missing required key '{key}'"
        raise ValueError(msg)
    return raw[key]


def _parse_tag(raw: dict[str, Any], filename: str) -> TemplateTag:
    name = _require(raw, "name", filename)
    return TemplateTag(
        name=_str(name),
        definition=_str(raw.get("definition")),
        apply_when=_str(raw.get("apply_when")),
        not_this=_str(raw.get("not_this")),
    )


def _parse_group(raw: dict[str, Any], filename: str) -> TemplateGroup:
    name = _str(_require(raw, "name", filename))
    subtitle = _str(_require(raw, "subtitle", filename))
    colour_set = _str(_require(raw, "colour_set", filename))
    if colour_set not in _VALID_COLOUR_SETS:
        msg = (
            f"{filename}: group '{name}' has invalid colour_set"
            f" '{colour_set}' (expected one of {sorted(_VALID_COLOUR_SETS)})"
        )
        raise ValueError(msg)
    raw_tags = raw.get("tags", []) or []
    tags = [_parse_tag(t, filename) for t in raw_tags]
    return TemplateGroup(name=name, subtitle=subtitle, colour_set=colour_set, tags=tags)


def _parse_template(raw: dict[str, Any], filename: str) -> CodebookTemplate:
    """Validate and convert a raw YAML dict to a CodebookTemplate."""
    template_id = _str(_require(raw, "id", filename))
    title = _str(_require(raw, "title", filename))
    author = _str(raw.get("author"))
    description = _str(_require(raw, "description", filename))
    author_bio = _str(raw.get("author_bio"))
    preamble = _str(raw.get("preamble"))
    enabled = bool(raw.get("enabled", True))
    sort_order = int(raw.get("sort_order", 50))

    raw_links = raw.get("author_links", []) or []
    author_links: list[tuple[str, str]] = []
    for link in raw_links:
        label = _str(link.get("label"))
        url = _str(link.get("url"))
        author_links.append((label, url))

    raw_groups = _require(raw, "groups", filename)
    groups = [_parse_group(g, filename) for g in raw_groups]

    return CodebookTemplate(
        id=template_id,
        title=title,
        author=author,
        description=description,
        author_bio=author_bio,
        author_links=author_links,
        preamble=preamble,
        groups=groups,
        enabled=enabled,
        sort_order=sort_order,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@cache
def _load_template(template_id: str) -> CodebookTemplate:
    path = _TEMPLATES_DIR / f"{template_id}.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _parse_template(raw, path.name)


def get_template(template_id: str) -> CodebookTemplate | None:
    """Return a template by ID, or None if not found."""
    path = _TEMPLATES_DIR / f"{template_id}.yaml"
    if not path.exists():
        return None
    return _load_template(template_id)


def load_all_templates() -> list[CodebookTemplate]:
    """Load all codebook templates from YAML files.

    Auto-discovers ``*.yaml`` files in the templates directory.  Templates
    are sorted by ``sort_order`` (lower first, default 50), then
    alphabetically by ``id`` as a tiebreaker.
    """
    templates: list[CodebookTemplate] = []
    for path in sorted(_TEMPLATES_DIR.glob("*.yaml")):
        templates.append(_load_template(path.stem))
    templates.sort(key=lambda t: (t.sort_order, t.id))
    return templates


# Backward-compatible constant — routes/codebook.py used this directly.
CODEBOOK_TEMPLATES = load_all_templates()
