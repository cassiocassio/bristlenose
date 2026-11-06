"""The cross-harness entry docs keep working when nobody has opened them for a week.

CLAUDE.md is Claude Code's entry point and AGENTS.md is everyone else's (Codex and others).
They share one rulebook, so they must name each other, every file they send an agent to must
exist, and CODEX.md must stay a pointer: a second rulebook there is how Codex came to prescribe
a worktree per feature (1 Nov 2026) while the other two said trunk by default.

test_claude_md_shape.py follows Markdown links; these files cite paths in backticks, which it
does not read.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ENTRY = ["AGENTS.md", "CODEX.md"]

# `path/to/file.ext` in backticks, root-relative, with an extension we ship docs or scripts in.
_BACKTICK_PATH = re.compile(r"`((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:md|sh|py|json|toml|yml))`")


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


ROOT_DOCS = {"AGENTS.md", "CLAUDE.md", "CODEX.md", "TODO.md", "README.md"}


def test_every_path_the_entry_docs_cite_exists() -> None:
    missing = []
    for rel in ENTRY:
        for path in sorted(set(_BACKTICK_PATH.findall(_text(rel)))):
            # A bare name like SKILL.md is prose about a family of files; only a path with a
            # directory, or a named root document, can be checked.
            checkable = "/" in path or path in ROOT_DOCS
            if checkable and not (ROOT / path).exists():
                missing.append(f"{rel}: {path}")
    assert not missing, "cited but absent:\n" + "\n".join(missing)


def test_the_two_entry_points_name_each_other() -> None:
    assert "AGENTS.md" in _text("CLAUDE.md"), "CLAUDE.md must point other harnesses at AGENTS.md"
    assert "CLAUDE.md" in _text("AGENTS.md"), "AGENTS.md must point at CLAUDE.md for the shared rules"


def test_codex_md_is_a_pointer_not_a_second_rulebook() -> None:
    text = _text("CODEX.md")
    assert "AGENTS.md" in text and "CLAUDE.md" in text
    assert len(text.splitlines()) <= 40, "CODEX.md grew; a rule that lives only here is one Claude never sees"
    # The rule it once contradicted: trunk is the default, a worktree is the exception.
    assert not re.search(r"(?i)\buse feature branches in dedicated worktrees\b", text)


def test_every_lifecycle_skill_agents_md_names_exists_and_is_indexed() -> None:
    skills = sorted(set(re.findall(r"\.claude/skills/([a-z-]+)/SKILL\.md", _text("AGENTS.md"))))
    assert skills, "AGENTS.md no longer names a lifecycle skill; the table moved?"
    index = _text(".claude/skills/WORKFLOW.md")
    for name in skills:
        assert (ROOT / ".claude/skills" / name / "SKILL.md").is_file(), name
        assert name in index, f"{name} is in AGENTS.md but not in .claude/skills/WORKFLOW.md"


def test_the_shared_handoff_section_agents_md_relies_on_exists() -> None:
    assert "## Session-end housekeeping" in _text("CLAUDE.md")
    assert "### Shared Claude / Codex handoffs" in _text("CLAUDE.md")
