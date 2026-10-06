#!/usr/bin/env python3
"""Mechanical typesetting scan for the Bristlenose docs and hand-written pages.

Lives in the main bristlenose repo; scans the bristlenose-website checkout
(found via $BRISTLENOSE_WEBSITE, the working directory, or the sibling folder).

A metal detector, not a judge: every hit needs reading in context. Code
(fences, backticks, <code>, <pre>, <kbd>, <script>, <style>) is blanked out
before scanning, line numbers preserved, so nothing typeable is ever flagged.

    scan.py                       docs-src/*.md and content/*.html
    scan.py cli.md index.html     just these (looked up in docs-src/ and content/)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

def _site_root() -> Path:
    """The website checkout: $BRISTLENOSE_WEBSITE, else the working directory if
    it is one, else ../bristlenose-website beside the main repo this skill lives in."""
    import os
    for cand in (os.environ.get("BRISTLENOSE_WEBSITE"), Path.cwd(),
                 Path(__file__).resolve().parents[4] / "bristlenose-website"):
        if cand and (Path(cand) / "docs-src").is_dir() and (Path(cand) / "content").is_dir():
            return Path(cand).resolve()
    sys.exit("scan.py: can't find the bristlenose-website checkout; set BRISTLENOSE_WEBSITE")


ROOT = _site_root()
DOCS, CONTENT = ROOT / "docs-src", ROOT / "content"


def _blank(m: re.Match) -> str:
    """Replace a match with spaces, keeping its newlines so line numbers hold."""
    return re.sub(r"[^\n]", " ", m.group(0))


def prose_md(text: str) -> str:
    text = re.sub(r"^(```|~~~).*?^\1", _blank, text, flags=re.S | re.M)
    text = re.sub(r"`[^`\n]+`", _blank, text)
    text = re.sub(r"\]\([^)]*\)", _blank, text)          # link targets
    text = re.sub(r"<[^>\n]+>", _blank, text)            # inline HTML tags
    return text


def prose_html(text: str) -> str:
    text = re.sub(r"<(script|style|pre|code|kbd|textarea)\b.*?</\1>", _blank, text, flags=re.S | re.I)
    text = re.sub(r"<!--.*?-->", _blank, text, flags=re.S)
    text = re.sub(r"<[^>]+>", _blank, text, flags=re.S)  # tags and their attributes
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    return text


UNIT = r"(?:GB|MB|KB|TB|ms|px|fps|kHz|Hz|dB|min|minutes?|hours?|seconds?|days?|weeks?)"

# (tier, label, pattern, advice, applies_to)  applies_to: "md", "html" or "both"
CHECKS = [
    ("Wrong", "straight double quote", r'"', "use “ ”", "html"),
    ("Wrong", "straight apostrophe/quote", r"(?<=\w)'(?=\w)|(?<=\s)'(?=\w)|(?<=\w)'(?=[\s.,;:!?])", "use ’ (or ‘ ’)", "html"),
    ("Wrong", "hyphen as range", r"(?<![\w.-])\d+-\d+(?![\w-])", "use an en dash: 4–6 (skip dates and versions)", "both"),
    ("Wrong", "three dots", r"\.\.\.", "use …", "html"),
    ("Wrong", "x as times", r"(?<![\w])\d+(?:\.\d+)?x\b|\b\d+ x \d+\b", "use ×", "both"),
    ("Wrong", "hyphen or -- as a dash", r"\w (?:-|--) \w", "use the house sentence dash", "both"),
    ("Wrong", "ASCII arrow", r"->|(?<=\w) > (?=\w)", "use → for menu paths", "both"),
    ("Wrong", "number glued to unit", rf"\b\d+(?:\.\d+)?{UNIT}\b", "space it: 15 GB (non-breaking)", "both"),
    ("Space", "breakable number + unit", rf"\b\d+(?:\.\d+)? {UNIT}\b", "non-breaking space between number and unit", "both"),
    ("Space", "double space", r"(?<=[.!?]) {2,}(?=\S)", "one space after a full stop", "both"),
    ("Inconsistent", "spelled-out shortcut", r"\b(?:Cmd|Command|Ctrl|Control|Opt|Option|Shift)[-+](?:[A-Za-z0-9](?![A-Za-z])|Return|Enter|Tab|Space|Delete|Esc|Escape|Up|Down|Left|Right)", "use glyphs: ⌘ ⌥ ⇧ ⌃", "both"),
    ("Inconsistent", "repeated word", r"\b(\w{2,})(?: |\n[ \t]*)\1\b", "probably a typo", "both"),
]


def scan(path: Path) -> list[tuple[str, int, str, str, str]]:
    raw = path.read_text(encoding="utf-8")
    kind = "md" if path.suffix == ".md" else "html"
    text = prose_md(raw) if kind == "md" else prose_html(raw)
    lines, out = raw.splitlines(), []
    for tier, label, pat, advice, applies in CHECKS:
        if applies not in (kind, "both"):
            continue
        for m in re.finditer(pat, text, flags=re.I if label == "repeated word" else 0):
            n = text.count("\n", 0, m.start()) + 1
            out.append((tier, n, label, advice, lines[n - 1].strip()[:110]))
    return sorted(out, key=lambda r: (["Wrong", "Inconsistent", "Space"].index(r[0]), r[1]))


def targets(args: list[str]) -> list[Path]:
    if not args:
        return sorted(DOCS.glob("*.md")) + sorted(CONTENT.glob("*.html"))
    found = []
    for a in args:
        p = Path(a)
        cands = [p, DOCS / a, CONTENT / a]
        hit = next((c for c in cands if c.is_file()), None)
        if not hit:
            sys.exit(f"scan.py: no such page: {a}")
        found.append(hit)
    return found


def main() -> None:
    total = 0
    for path in targets(sys.argv[1:]):
        hits = scan(path)
        if not hits:
            continue
        print(f"\n{path.relative_to(ROOT)}")
        for tier, n, label, advice, line in hits:
            print(f"  {n:>4}  {tier:<12} {label}: {advice}\n        {line}")
        total += len(hits)
    print(f"\n{total} hits. Read each in context before changing it.")


if __name__ == "__main__":
    main()
