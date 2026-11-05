"""The CLAUDE.md files stay short, and the links that lead out of them resolve.

Each area keeps rules and a one-line-per-entry index in CLAUDE.md; the full entries live in a
gotchas.md (or reference.md) beside it. Two things rot silently: a CLAUDE.md that regrows an
86 KB gotchas section because nobody was obliged to look, and a relative link or anchor that
stops resolving after a move. Both are checked here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Ceilings carry slack over the sizes measured on 5 Nov 2026 (bytes). Raising one is a
# deliberate edit that says why; new long entries belong in the sibling gotchas.md.
CEILINGS = {
    "CLAUDE.md": 62_000,
    "desktop/CLAUDE.md": 62_000,
    "bristlenose/server/CLAUDE.md": 46_000,
    "bristlenose/stages/CLAUDE.md": 40_000,
    "bristlenose/theme/CLAUDE.md": 35_000,
    "bristlenose/llm/CLAUDE.md": 25_000,
    "frontend/CLAUDE.md": 18_000,
}

# .claude/gotchas.md is not link-checked: older prose in it writes root-relative paths in
# link syntax. Links INTO it are still checked, from the files above.
LINKED = [
    *CEILINGS,
    "desktop/gotchas.md",
    "desktop/reference.md",
    "bristlenose/server/gotchas.md",
    "bristlenose/stages/gotchas.md",
    "bristlenose/theme/gotchas.md",
    "bristlenose/llm/gotchas.md",
    "frontend/gotchas.md",
    ".claude/reference-docs.md",
    ".claude/branch-workflow.md",
    "docs/release-timing.md",
]

_LINK = re.compile(r"\]\(([^)\s]*)\)")
_FENCE = re.compile(r"^(```|~~~)")


def _slug(heading: str) -> str:
    """GitHub's anchor rule: lower-case, drop punctuation, spaces to hyphens."""
    text = re.sub(r"[`*_]", "", heading.strip().lower())
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return re.sub(r"\s", "-", text)


def _anchors(path: Path) -> set[str]:
    out: set[str] = set()
    fenced = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced and line.startswith("#"):
            out.add(_slug(line.lstrip("#")))
    return out


def _links(path: Path):
    fenced = False
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        for target in _LINK.findall(line):
            if target and not target.startswith(("http://", "https://", "mailto:")):
                yield n, target


@pytest.mark.parametrize("rel", sorted(CEILINGS))
def test_claude_md_stays_under_its_ceiling(rel: str) -> None:
    size = (ROOT / rel).stat().st_size
    assert size <= CEILINGS[rel], (
        f"{rel} is {size:,} bytes (ceiling {CEILINGS[rel]:,}). Put the long entry in the "
        "gotchas.md beside it and add its headline to the index; raise the ceiling only "
        "on purpose."
    )


@pytest.mark.parametrize("rel", LINKED)
def test_links_out_of_claude_md_files_resolve(rel: str) -> None:
    path = ROOT / rel
    broken = []
    for n, target in _links(path):
        file_part, _, anchor = target.partition("#")
        dest = path if not file_part else (path.parent / file_part).resolve()
        if not dest.exists():
            broken.append(f"{rel}:{n} -> {target} (no such file)")
        elif anchor and dest.suffix == ".md" and anchor not in _anchors(dest):
            broken.append(f"{rel}:{n} -> {target} (no such heading)")
    assert not broken, "\n".join(broken)
