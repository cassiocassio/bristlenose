"""The is-this-bristlenosey skill's domain files must quote the tree, not paraphrase it.

A domain file tells an agent what Bristlenose already does. On 14 Oct 2026 one of its rules carried
a clause written in rather than found, cited to a doc that said the opposite, and it steered two of
three test runs to the wrong answer (`.claude/skills/is-this-bristlenosey/domains/progress.md`,
status note). So every rule now quotes its source as `«verbatim» — path`, and this test checks
each quote still appears in the file it cites. A rule with no source must say **Inference**.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOMAINS = ROOT / ".claude" / "skills" / "is-this-bristlenosey" / "domains"

_QUOTE = re.compile(r"«(.+?)»\s*—\s*([\w./-]+\.\w+)(?=\s|$)")
_RULE = re.compile(r"^(\d+)\. \*\*")
_PATH = re.compile(r"`([\w./-]+/[\w.-]+\.(?:py|swift|ts|tsx|md|css|sh|json|html|spec\.ts))`")
_COMMENT = re.compile(r"^\s*(?:///|//|#|>|\*)\s?", re.M)


def _norm(text: str) -> str:
    """Ignore what quoting cannot preserve: emphasis, backticks, comment markers, line wraps."""
    text = _COMMENT.sub("", text)
    text = text.replace("*", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip().lower()


def _domain_files() -> list[Path]:
    return sorted(DOMAINS.glob("*.md"))


def _quotes() -> list[tuple[Path, str, str]]:
    out = []
    for f in _domain_files():
        for m in _QUOTE.finditer(f.read_text(encoding="utf-8")):
            out.append((f, m.group(1), m.group(2)))
    return out


def test_the_domain_files_are_found_and_quote_something() -> None:
    assert _domain_files(), f"no domain files under {DOMAINS}"
    assert len(_quotes()) >= 15  # a parser that reads nothing would pass everything below


def test_every_quote_appears_in_the_file_it_cites() -> None:
    bad = []
    for f, quote, rel in _quotes():
        src = ROOT / rel
        if not src.is_file():
            bad.append(f"{f.name}: cites {rel}, which does not exist")
        elif _norm(quote) not in _norm(src.read_text(encoding="utf-8")):
            bad.append(f"{f.name}: «{quote}» is not in {rel}")
    assert not bad, "\n".join(bad)


def test_every_rule_quotes_a_source_or_says_it_is_an_inference() -> None:
    bad = []
    for f in _domain_files():
        lines = f.read_text(encoding="utf-8").splitlines()
        starts = [i for i, ln in enumerate(lines) if _RULE.match(ln)]
        for n, i in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else len(lines)
            block = []
            for ln in lines[i:end]:
                if ln.startswith("#"):
                    break
                block.append(ln)
            body = "\n".join(block)
            if "«" not in body and "**Inference:**" not in body:
                bad.append(f"{f.name}: rule {_RULE.match(lines[i]).group(1)} cites nothing")
    assert not bad, "\n".join(bad)


def test_every_cited_path_exists() -> None:
    missing = []
    for f in [*_domain_files(), DOMAINS.parent / "SKILL.md"]:
        for rel in set(_PATH.findall(f.read_text(encoding="utf-8"))):
            bases = (ROOT, ROOT / "docs", ROOT / "bristlenose", DOMAINS.parent)
            if not any((base / rel).exists() for base in bases):
                missing.append(f"{f.name}: {rel}")
    assert not missing, "\n".join(sorted(missing))
