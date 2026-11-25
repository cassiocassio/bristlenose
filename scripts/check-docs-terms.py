#!/usr/bin/env python3
"""check-docs-terms.py PATH... : flag forbidden spellings of platform and vendor names in prose.

The rules live in docs/platform-terms.json (human table: docs/glossary.md, section
"Platforms, vendors and architectures"). Added 20 Nov 2026 after "ARM" and "Arm" sat on
one install page: a spelling that a script can assert is a missing gate, not a
documentation problem.

Only prose is checked. Skipped: fenced code blocks, inline code, link targets, URLs,
HTML tags and attributes, <script>/<style>/<pre>/<code> content, HTML comments, and any
line carrying the marker `terms:ignore` (for the rare line that must quote an old name).

PATH is a file or a directory (searched for *.md and *.html; `build`, `node_modules`
and dot-directories are skipped).

Exit 0 = clean, 1 = a forbidden spelling found, 2 = usage or a broken rules file.
Stdlib only, so a deploy script can call it with any python3.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "docs" / "platform-terms.json"
SKIP_DIRS = {"build", "node_modules", "__pycache__"}
IGNORE_MARKER = "terms:ignore"

_INLINE_CODE = re.compile(r"`[^`\n]*`")
_LINK_TARGET = re.compile(r"\]\([^)\n]*\)")
_URL = re.compile(r"https?://[^\s)>\"']+")
_TAG = re.compile(r"<[^>\n]*>")
_COMMENT = re.compile(r"<!--.*?-->")
_HTML_BLOCKS = ("script", "style", "pre", "code")


def load_rules() -> list[tuple[str, re.Pattern[str]]]:
    """Return (canonical, compiled forbidden pattern) pairs."""
    try:
        data = json.loads(RULES.read_text(encoding="utf-8"))
        out = []
        for term in data["terms"]:
            for pat in term["forbidden"]:
                out.append((term["canonical"], re.compile(pat)))
        return out
    except (OSError, ValueError, KeyError, re.error) as exc:
        print(f"check-docs-terms: cannot use {RULES}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


def prose_lines(path: Path) -> list[tuple[int, str]]:
    """Return (line number, text with everything that is not prose blanked out)."""
    text = path.read_text(encoding="utf-8")
    is_html = path.suffix.lower() == ".html"
    out: list[tuple[int, str]] = []
    in_fence = False
    in_comment = False
    block: str | None = None  # an open <script>/<style>/<pre>/<code> element
    for n, raw in enumerate(text.split("\n"), 1):
        line = raw
        if IGNORE_MARKER in line:
            continue
        if not is_html:
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
        if in_comment:
            if "-->" in line:
                line = line.split("-->", 1)[1]
                in_comment = False
            else:
                continue
        line = _COMMENT.sub(" ", line)
        if "<!--" in line:
            line = line.split("<!--", 1)[0]
            in_comment = True
        if is_html:
            # Drop whole elements whose content is not prose; they may span lines.
            while True:
                if block is not None:
                    end = re.search(rf"</{block}\s*>", line, re.I)
                    if not end:
                        line = ""
                        break
                    line = line[end.end():]
                    block = None
                start = re.search(rf"<({'|'.join(_HTML_BLOCKS)})\b[^>]*>", line, re.I)
                if not start:
                    break
                block = start.group(1).lower()
                line = line[: start.start()] + " " + line[start.end():]
        line = _INLINE_CODE.sub(" ", line)
        line = _LINK_TARGET.sub("] ", line)
        line = _URL.sub(" ", line)
        line = _TAG.sub(" ", line)
        out.append((n, line))
    return out


def files_under(arg: Path) -> list[Path]:
    if arg.is_file():
        return [arg]
    found: list[Path] = []
    for p in sorted(arg.rglob("*")):
        rel = p.relative_to(arg).parts
        if any(part in SKIP_DIRS or part.startswith(".") for part in rel[:-1]):
            continue
        if p.is_file() and p.suffix.lower() in {".md", ".html"}:
            found.append(p)
    return found


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    rules = load_rules()
    hits = 0
    for arg in argv:
        root = Path(arg)
        if not root.exists():
            print(f"check-docs-terms: no such path: {arg}", file=sys.stderr)
            return 2
        for path in files_under(root):
            for n, line in prose_lines(path):
                for canonical, pattern in rules:
                    for m in pattern.finditer(line):
                        print(f"{path.as_posix()}:{n}: '{m.group(0)}' should be '{canonical}'")
                        hits += 1
    if hits:
        print(
            f"\n{hits} spelling(s) to fix. Rules: docs/glossary.md, section "
            f"'Platforms, vendors and architectures'. A line that must quote the old "
            f"spelling carries `{IGNORE_MARKER}`.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
