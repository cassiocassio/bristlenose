"""Frontmatter parsing for shipped LLM prompts.

Every ``bristlenose/llm/prompts/*.md`` file must have a YAML frontmatter
block declaring ``id`` and ``version``. The id must match the filename
stem so cohort lookup is unambiguous, and the SHA must be deterministic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bristlenose.llm.prompts import (
    _PROMPTS_DIR,
    PromptTemplate,
    get_prompt_template,
)


def _all_prompt_stems() -> list[str]:
    return sorted(p.stem for p in _PROMPTS_DIR.glob("*.md"))


@pytest.mark.parametrize("stem", _all_prompt_stems())
def test_prompt_has_frontmatter(stem: str) -> None:
    tmpl = get_prompt_template(stem)
    assert isinstance(tmpl, PromptTemplate)
    assert tmpl.id == stem, f"id {tmpl.id!r} should match filename stem {stem!r}"
    assert tmpl.version, f"version is empty for {stem}"
    assert tmpl.system, f"system prompt empty for {stem}"
    assert tmpl.user, f"user prompt empty for {stem}"
    assert isinstance(tmpl.path, Path)
    assert tmpl.path.exists()


@pytest.mark.parametrize("stem", _all_prompt_stems())
def test_prompt_sha_stable_across_calls(stem: str) -> None:
    a = get_prompt_template(stem)
    b = get_prompt_template(stem)
    assert a.sha == b.sha
    assert len(a.sha) == 64  # sha256 hex


def test_legacy_get_prompt_still_works() -> None:
    from bristlenose.llm.prompts import get_prompt

    pair = get_prompt("quote-extraction")
    assert pair.system
    assert pair.user


def test_legacy_constants_still_resolve() -> None:
    from bristlenose.llm import prompts

    assert isinstance(prompts.QUOTE_EXTRACTION_PROMPT, str)
    assert prompts.QUOTE_EXTRACTION_PROMPT
