"""The links that lead out of the CLAUDE.md files resolve.

Each area keeps rules and a one-line-per-entry index in CLAUDE.md; the full entries live in a
gotchas.md (or reference.md) beside it. A relative link or anchor rots silently after a move,
so it is checked here. There is no size ceiling: the owner dropped the byte limits on 6 Nov 2026
(a bikeshed; keep entries in the gotchas.md beside the file by habit, not by gate).

Known limits (usual-suspects review, 6 Nov 2026): only links in Markdown link syntax are followed,
not the paths written in backticks, which is the dominant citation style in these files; several
of the checked files hold no links today and pass trivially, guarding the day they gain one.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parent.parent

# .claude/gotchas.md is not link-checked: older prose in it writes root-relative paths in
# link syntax. Links INTO it are still checked, from the files above.
LINKED = [
    "CLAUDE.md",
    "desktop/CLAUDE.md",
    "bristlenose/server/CLAUDE.md",
    "bristlenose/stages/CLAUDE.md",
    "bristlenose/theme/CLAUDE.md",
    "bristlenose/llm/CLAUDE.md",
    "frontend/CLAUDE.md",
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

# A target, with an optional "title": [a](b.md "title") is a link too.
_LINK = re.compile(r'\]\(([^)\s]*)(?:\s+"[^"]*")?\)')
_FENCE = re.compile(r"^(```|~~~)")


def _slug(heading: str) -> str:
    """GitHub's anchor rule: lower-case, drop punctuation (underscores stay), spaces to hyphens."""
    text = re.sub(r"\s+#+\s*$", "", heading.strip())  # a closing run of #s is not part of it
    text = re.sub(r"[`*]", "", text.lower())
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # a heading link keeps its text only
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return re.sub(r"\s", "-", text)


def _anchors(path: Path) -> set[str]:
    """Every anchor GitHub gives the file's headings, repeats numbered -1, -2 as it does."""
    out: set[str] = set()
    seen: dict[str, int] = {}
    fenced = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced and (m := re.match(r"#{1,6}[ \t]+(.*)", line)):  # "#tag" is no heading
            slug = _slug(m.group(1))
            n = seen.get(slug, 0)
            seen[slug] = n + 1
            out.add(slug if n == 0 else f"{slug}-{n}")
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


def _exists_with_exact_case(path: Path) -> bool:
    """macOS is case-insensitive and GitHub and Linux CI are not: every part of a link's path
    must match the name on disk, not only the last."""
    if not path.exists():
        return False
    try:
        parts = path.relative_to(ROOT).parts
    except ValueError:
        return path.name in {p.name for p in path.parent.iterdir()}
    here = ROOT
    for part in parts:
        if part not in {p.name for p in here.iterdir()}:
            return False
        here = here / part
    return True


@pytest.mark.parametrize("rel", LINKED)
def test_links_out_of_claude_md_files_resolve(rel: str) -> None:
    path = ROOT / rel
    broken = []
    for n, target in _links(path):
        file_part, _, anchor = unquote(target).partition("#")
        dest = path if not file_part else (path.parent / file_part).resolve()
        if not _exists_with_exact_case(dest):
            broken.append(f"{rel}:{n} -> {target} (no such file, or the case differs)")
        elif anchor and dest.suffix == ".md" and anchor not in _anchors(dest):
            broken.append(f"{rel}:{n} -> {target} (no such heading)")
    assert not broken, "\n".join(broken)


def test_the_link_checker_sees_the_forms_that_rot() -> None:
    # Its own proof of reach: a plain link, a titled link, a repeated heading and an underscore.
    assert _LINK.findall('[a](b.md#x) [c](d.md "a title") [e](f.md#g_h)') == [
        "b.md#x", "d.md", "f.md#g_h"]
    assert _slug("Foo_bar `code` **bold**") == "foo_bar-code-bold"
    assert _slug("A [link](x.md) here") == "a-link-here"
    assert _slug("Foo ##") == "foo"
    assert _exists_with_exact_case(ROOT / "CLAUDE.md")
    assert not _exists_with_exact_case(ROOT / "DOCS" / "release-timing.md")
    assert not _exists_with_exact_case(ROOT / "claude.md")


def test_anchors_number_repeated_headings_and_ignore_fences_and_hashtags(tmp_path: Path) -> None:
    doc = tmp_path / "d.md"
    doc.write_text("# Foo\n\n```\n# not a heading\n```\n\n## Foo\n\n#hashtag\n\n## Foo\n", encoding="utf-8")
    assert _anchors(doc) == {"foo", "foo-1", "foo-2"}
