#!/usr/bin/env python3
"""Scrape Apple's Human Interface Guidelines to a local markdown corpus.

Generic by design — no project-specific paths. Intended for clean lift-out to
a public `what-would-gruber-say` companion repo (mirroring the
`what-would-william-of-ockham-say` pattern).

The HIG is built with DocC; the developer.apple.com web client fetches
structured JSON from a public endpoint. This script consumes that JSON,
converts it to markdown with stable section anchors, and writes one file per
HIG page.

Usage:
    scripts/scrape-hig.py                   # scrape v1 page list to default out
    scripts/scrape-hig.py --out /some/dir   # override output directory
    scripts/scrape-hig.py --pages slug1,slug2/category   # override page list

Apple's HIG content is copyrighted; the default output directory lives outside
any repo to make accidental `git add` structurally harder. Do not redistribute.

This script is a contributor tool. It is NOT invoked by the Bristlenose
runtime, the desktop sidecar, the PyInstaller bundle, or any pipeline stage.
Run manually on a development machine to refresh the agent reference corpus.
Determinism: re-running against an unchanged HIG produces zero-diff output
(per-file content-hash sidecars gate writes). Last manual zero-diff
verification: 16 May 2026 against the v1 page list.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BASE = "https://developer.apple.com/tutorials/data/design/human-interface-guidelines"
USER_AGENT = "hig-corpus-scraper/0.1 (+https://github.com/cassiocassio/what-would-gruber-say)"
RATE_LIMIT_SECONDS = 2.0
SLUG_RE = re.compile(r"^[a-z0-9-]+$")

# v1 page manifest: category subdir -> list of slugs.
# Slug = trailing segment of /design/human-interface-guidelines/<slug>.
# All confirmed flat (no nesting) by the 2026-05-16 API-shape spike.
V1_PAGES: dict[str, list[str]] = {
    "foundations": [
        "color",
        "typography",
        "materials",        # Liquid Glass lives inside this page
        "layout",
        "accessibility",
        "writing",          # Apple files this under Foundations
    ],
    "components": [
        "sidebars",
        "context-menus",
    ],
    "patterns": [
        "feedback",
        "modality",
    ],
    "platforms": [
        "designing-for-macos",
    ],
}


# ---------- Fetch ----------


@dataclass
class FetchResult:
    slug: str
    data: dict
    raw_bytes: bytes


def default_out_dir() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "hig-corpus"


def fetch_page(slug: str) -> FetchResult:
    if not SLUG_RE.match(slug):
        raise ValueError(f"refusing to fetch unsafe slug: {slug!r}")
    url = f"{BASE}/{slug}.json"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    return FetchResult(slug=slug, data=json.loads(raw), raw_bytes=raw)


# ---------- DocC → markdown converter ----------


_WARNED_TYPES: set[str] = set()


def warn_unknown(t: str, where: str) -> None:
    key = f"{t}@{where}"
    if key in _WARNED_TYPES:
        return
    _WARNED_TYPES.add(key)
    print(f"  warn: unhandled node type {t!r} (first seen in {where})", file=sys.stderr)


def slug_anchor(text: str) -> str:
    """Stable slugified heading anchor: lowercase, alphanumerics, hyphens."""
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def resolve_ref(identifier: str, references: dict) -> tuple[str, str | None]:
    """Return (display_title, url) for a reference identifier."""
    ref = references.get(identifier, {})
    title = ref.get("title") or identifier
    url = ref.get("url")
    if url and url.startswith("/"):
        url = f"https://developer.apple.com{url}"
    return title, url


def render_inline(nodes: list, references: dict) -> str:
    out: list[str] = []
    for n in nodes:
        t = n.get("type")
        if t == "text":
            out.append(n.get("text", ""))
        elif t == "emphasis":
            out.append(f"*{render_inline(n.get('inlineContent', []), references)}*")
        elif t == "strong":
            out.append(f"**{render_inline(n.get('inlineContent', []), references)}**")
        elif t == "codeVoice":
            out.append(f"`{n.get('code', '')}`")
        elif t == "small":
            out.append(render_inline(n.get("inlineContent", []), references))
        elif t == "reference":
            ident = n.get("identifier", "")
            title, url = resolve_ref(ident, references)
            if url:
                out.append(f"[{title}]({url})")
            else:
                out.append(title)
        elif t == "image":
            ident = n.get("identifier", "")
            ref = references.get(ident, {})
            out.append(f"![{ref.get('alt') or ident}]({ident})")
        elif t == "link":
            out.append(f"[{n.get('title', n.get('destination', ''))}]({n.get('destination', '')})")
        else:
            warn_unknown(t or "?", "inline")
            # pass-through: try inlineContent or text
            if "inlineContent" in n:
                out.append(render_inline(n["inlineContent"], references))
            elif "text" in n:
                out.append(n["text"])
    return "".join(out)


def render_block(node: dict, references: dict, depth: int = 0) -> list[str]:
    """Render a single block node; return list of markdown lines."""
    t = node.get("type")
    lines: list[str] = []
    if t == "paragraph":
        lines.append(render_inline(node.get("inlineContent", []), references))
        lines.append("")
    elif t == "heading":
        level = node.get("level", 2)
        text = node.get("text", "")
        anchor = slug_anchor(text)
        # Markdown heading; anchor follows directly so [HIG: page.md#anchor] resolves
        lines.append(f"{'#' * level} {text} {{#{anchor}}}")
        lines.append("")
    elif t == "aside":
        style = node.get("style", "note")
        label = node.get("name") or style.title()
        body_lines = render_blocks(node.get("content", []), references, depth + 1)
        lines.append(f"> **{label}:** ")
        for bl in body_lines:
            lines.append(f"> {bl}" if bl else ">")
        lines.append("")
    elif t in ("unorderedList", "orderedList"):
        marker_fn = (lambda i: "- ") if t == "unorderedList" else (lambda i: f"{i + 1}. ")
        for i, item in enumerate(node.get("items", [])):
            item_lines = render_blocks(item.get("content", []), references, depth + 1)
            if not item_lines:
                continue
            first = item_lines[0]
            lines.append(f"{marker_fn(i)}{first}")
            for cont in item_lines[1:]:
                lines.append(f"  {cont}" if cont else "")
        lines.append("")
    elif t == "codeListing":
        syntax = node.get("syntax", "")
        code = "\n".join(node.get("code", []))
        lines.append(f"```{syntax}")
        lines.append(code)
        lines.append("```")
        lines.append("")
    elif t == "table":
        header_kind = node.get("header", "none")
        rows = node.get("rows", [])
        if not rows:
            return lines
        # Each row is a list of cells; each cell is a list of block nodes.
        def cell_to_text(cell: list) -> str:
            txt = " ".join(render_inline(b.get("inlineContent", []), references)
                           for b in cell if b.get("type") == "paragraph")
            return txt.replace("|", "\\|").replace("\n", " ")
        if header_kind == "row" and rows:
            header_cells = [cell_to_text(c) for c in rows[0]]
            body_rows = rows[1:]
            lines.append("| " + " | ".join(header_cells) + " |")
            lines.append("| " + " | ".join("---" for _ in header_cells) + " |")
        else:
            body_rows = rows
        for r in body_rows:
            lines.append("| " + " | ".join(cell_to_text(c) for c in r) + " |")
        lines.append("")
    elif t == "row":
        # Multi-column layout — flatten columns left-to-right.
        for col in node.get("columns", []):
            lines.extend(render_blocks(col.get("content", []), references, depth + 1))
    elif t == "tabNavigator":
        # Apple uses tabNavigators for platform/size variants on a single page
        # (e.g. iOS / iPadOS / macOS tabs). Flattening loses the disambiguator,
        # so prefix every tab's content with a labelled marker and an anchor so
        # citations can pin to the right tab.
        for tab in node.get("tabs", []):
            title = tab.get("title", "")
            if title:
                anchor = slug_anchor(f"tab-{title}")
                lines.append(f"**[{title}]** {{#{anchor}}}")
                lines.append("")
            lines.extend(render_blocks(tab.get("content", []), references, depth + 1))
    elif t == "image":
        ident = node.get("identifier", "")
        ref = references.get(ident, {})
        alt = ref.get("alt") or ident
        lines.append(f"![{alt}]({ident})")
        lines.append("")
    elif t == "video":
        ident = node.get("identifier", "")
        ref = references.get(ident, {})
        title = ref.get("alt") or ident
        lines.append(f"_[video: {title}]_")
        lines.append("")
    elif t == "links":
        for ident in node.get("identifiers", []):
            title, url = resolve_ref(ident, references)
            if url:
                lines.append(f"- [{title}]({url})")
            else:
                lines.append(f"- {title}")
        lines.append("")
    else:
        warn_unknown(t or "?", "block")
        # Pass-through: try to walk known sub-fields
        if "content" in node and isinstance(node["content"], list):
            lines.extend(render_blocks(node["content"], references, depth + 1))
        elif "inlineContent" in node:
            lines.append(render_inline(node["inlineContent"], references))
            lines.append("")
    return lines


def render_blocks(nodes: list, references: dict, depth: int = 0) -> list[str]:
    out: list[str] = []
    for n in nodes:
        out.extend(render_block(n, references, depth))
    return out


def doc_to_markdown(data: dict, slug: str) -> str:
    references = data.get("references", {})
    meta = data.get("metadata", {})
    title = meta.get("title", slug)
    custom = meta.get("customMetadata", {})
    platforms = custom.get("supported-platforms", "")
    alert_date = custom.get("alert-date", "")
    alert_text = custom.get("alert-text", "")

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"_Source: {BASE.replace('/tutorials/data', '')}/{slug}_  ")
    if platforms:
        lines.append(f"_Platforms: {platforms}_  ")
    if alert_date or alert_text:
        lines.append(f"_Last Apple update ({alert_date}): {alert_text}_  ")
    lines.append("")

    # Abstract / intro lives in metadata, sometimes as `abstract` at root
    abstract = data.get("abstract", [])
    if abstract:
        lines.append(render_inline(abstract, references))
        lines.append("")

    for section in data.get("primaryContentSections", []):
        if section.get("kind") == "content":
            lines.extend(render_blocks(section.get("content", []), references))

    return "\n".join(lines).rstrip() + "\n"


# ---------- Output ----------


def safe_write(corpus_root: Path, rel_path: Path, content: str) -> tuple[bool, Path]:
    """Write content to corpus_root/rel_path with a path-traversal guard.

    Returns (content_changed, final_path).
    """
    target = (corpus_root / rel_path).resolve()
    if not str(target).startswith(str(corpus_root.resolve()) + os.sep):
        raise ValueError(f"refusing to write outside corpus root: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)

    new_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    marker = target.with_suffix(target.suffix + ".sha256")

    if target.exists() and marker.exists():
        old_hash = marker.read_text().strip()
        if old_hash == new_hash:
            return False, target

    target.write_text(content, encoding="utf-8")
    marker.write_text(new_hash + "\n", encoding="utf-8")
    return True, target


def write_index(corpus_root: Path, manifest: dict[str, list[str]], titles: dict[str, str]) -> None:
    lines = ["# HIG corpus index", ""]
    lines.append(f"Scraped from {BASE.replace('/tutorials/data', '')}")
    lines.append("")
    for category, slugs in manifest.items():
        lines.append(f"## {category}/")
        lines.append("")
        for slug in slugs:
            title = titles.get(slug, slug)
            lines.append(f"- [{title}]({category}/{slug}.md)")
        lines.append("")
    safe_write(corpus_root, Path("_index.md"), "\n".join(lines))


def write_readme(corpus_root: Path) -> None:
    content = f"""# HIG corpus

Local mirror of Apple's Human Interface Guidelines for offline agent reference.

- **Source:** {BASE.replace('/tutorials/data', '')}
- **Scraper:** `scripts/scrape-hig.py` (in the public companion repo or your
  source project)
- **Refresh cadence:** quarterly, plus after WWDC announcements.

Apple's content is copyrighted; this mirror is for personal/agent reference
only. Do not redistribute. The corpus lives outside any git repo by default.

## Layout

- `_index.md` — the page list with titles.
- `<category>/<slug>.md` — one markdown file per scraped HIG page.
- `<category>/<slug>.md.sha256` — content-hash sidecar. The scraper only
  rewrites `<slug>.md` when its hash changes, so re-running against an
  unchanged HIG is a no-op. The sidecars are an implementation detail of
  the determinism gate — humans can ignore them; agents shouldn't read them.

## Citation contract (for agents)

The agent prompts cite by `[HIG: <category>/<slug>.md#<anchor>] "verbatim
phrase of 8+ words"`. The phrase is the load-bearing anti-bluff: it must
grep against the file. Anchors are navigational hints; Apple reuses heading
text across platform subsections, so the same slug can appear multiple
times in one page — the phrase disambiguates.
"""
    safe_write(corpus_root, Path("README.md"), content)


# ---------- Main ----------


def parse_manifest_arg(raw: str | None) -> dict[str, list[str]]:
    if not raw:
        return V1_PAGES
    out: dict[str, list[str]] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "/" in entry:
            cat, slug = entry.split("/", 1)
        else:
            cat, slug = "uncategorised", entry
        out.setdefault(cat, []).append(slug)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else "")
    ap.add_argument("--out", type=Path, default=default_out_dir(),
                    help="output directory (default: $XDG_DATA_HOME/hig-corpus or ~/.local/share/hig-corpus)")
    ap.add_argument("--pages", type=str, default=None,
                    help="comma-separated overrides; format: category/slug or slug")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    manifest = parse_manifest_arg(args.pages)
    corpus_root = args.out.resolve()
    corpus_root.mkdir(parents=True, exist_ok=True)

    titles: dict[str, str] = {}
    changed_count = 0
    total_count = 0
    first = True
    for category, slugs in manifest.items():
        for slug in slugs:
            total_count += 1
            if not SLUG_RE.match(slug):
                print(f"  skip unsafe slug: {slug!r}", file=sys.stderr)
                continue
            if not first:
                time.sleep(RATE_LIMIT_SECONDS)
            first = False
            try:
                if not args.quiet:
                    print(f"fetch {category}/{slug}")
                result = fetch_page(slug)
            except urllib.error.HTTPError as e:
                print(f"  ERROR {slug}: HTTP {e.code}", file=sys.stderr)
                continue
            except Exception as e:
                print(f"  ERROR {slug}: {e}", file=sys.stderr)
                continue
            md = doc_to_markdown(result.data, slug)
            rel = Path(category) / f"{slug}.md"
            changed, _ = safe_write(corpus_root, rel, md)
            if changed:
                changed_count += 1
            titles[slug] = result.data.get("metadata", {}).get("title", slug)

    write_index(corpus_root, manifest, titles)
    write_readme(corpus_root)

    print(f"\ndone: {changed_count}/{total_count} pages changed; corpus at {corpus_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
