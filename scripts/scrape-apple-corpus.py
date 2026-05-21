#!/usr/bin/env python3
"""Scrape Apple's DocC-backed developer docs to a local markdown corpus.

Generic by design — no project-specific paths. Originally a HIG-only scraper
(`scrape-hig.py`), parameterised on 2026-05-17 to also scrape the Foundation
Models framework. The renderer body is the asset; the per-corpus knobs
(`CorpusConfig`) are a thin selector.

Intended for clean lift-out to a public companion repo (mirroring the
`what-would-william-of-ockham-say` pattern). One file, multiple corpora.

Usage:
    scripts/scrape-apple-corpus.py                       # default: hig
    scripts/scrape-apple-corpus.py --corpus fm           # Foundation Models
    scripts/scrape-apple-corpus.py --out /some/dir
    scripts/scrape-apple-corpus.py --corpus fm --pages essentials/foundationmodels

Apple's content is copyrighted; default output directories live outside any
repo to make accidental `git add` structurally harder. Do not redistribute.

Contributor tool only — never invoked by the Bristlenose runtime, sidecar,
PyInstaller bundle, or pipeline. Run manually to refresh the agent reference
corpus. Determinism: re-running against unchanged source produces zero-diff
output (per-file content-hash sidecars gate writes). Last manual zero-diff
verification: 16 May 2026 (hig corpus).
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

RATE_LIMIT_SECONDS = 2.0

# Flat slug: lowercase alphanum + hyphens.
FLAT_SLUG_RE = re.compile(r"^[a-z0-9-]+$")
# Nested slug for DocC member symbols, e.g. `systemlanguagemodel/guardrails`.
# Each segment is the flat shape; no leading/trailing slash, no `..`.
NESTED_SLUG_RE = re.compile(r"^[a-z0-9-]+(/[a-z0-9-]+)*$")


# ---------- Per-corpus config ----------


@dataclass
class CorpusConfig:
    name: str
    base: str                        # JSON endpoint root (no trailing slash)
    public_root: str                 # human-readable URL root, for citations
    user_agent: str
    out_subdir: str                  # default output dir name under XDG data
    slug_re: re.Pattern[str]
    pages: dict[str, list[str]]      # category -> [slug, ...]
    identifier_prefix: str | None = None  # for filtering cross-framework refs
    landing_slug: str | None = None  # slug whose JSON lives at <base>.json
                                     # (one level up — DocC framework landing)


HIG_PAGES: dict[str, list[str]] = {
    "foundations": [
        "color",
        "typography",
        "materials",
        "layout",
        "accessibility",
        "writing",
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


# FM v1 manifest — hand-curated from Phase 0b sample (see
# docs/private/handoffs/foundation-models-corpus.md §Phase 0 results).
# Shallow: top-level topicSection identifiers only. Member symbols are
# reached via cross-references inside parent markdown, not as separate files.
FM_PAGES: dict[str, list[str]] = {
    "essentials": [
        "foundationmodels",                                              # landing
        "adding-intelligent-app-features-with-generative-models",
        "generating-content-and-performing-tasks-with-foundation-models",
    ],
    "sessions": [
        "systemlanguagemodel",
        "systemlanguagemodel/guardrails",
        "languagemodelsession",
        "instructions",
        "prompt",
        "transcript",
        "generationoptions",
        "prompting-an-on-device-foundation-model",
        "updating-prompts-for-new-model-versions",
    ],
    "structured-output": [
        "generable",
        "generating-swift-data-structures-with-guided-generation",
        "generate-dynamic-game-content-with-guided-generation-and-tools",
    ],
    "tools": [
        "tool",
        "expanding-generation-with-tool-calling",
    ],
    "safety": [
        "improving-the-safety-of-generative-model-output",
    ],
    "performance": [
        "evaluating-prompts-to-measure-performance-and-improve-model-responses",
        "analyzing-the-runtime-performance-of-your-foundation-models-app",
    ],
}


CONFIGS: dict[str, CorpusConfig] = {
    "hig": CorpusConfig(
        name="hig",
        base="https://developer.apple.com/tutorials/data/design/human-interface-guidelines",
        public_root="https://developer.apple.com/design/human-interface-guidelines",
        user_agent="hig-corpus-scraper/0.1 (+https://github.com/cassiocassio/what-would-gruber-say)",
        out_subdir="hig-corpus",
        slug_re=FLAT_SLUG_RE,
        pages=HIG_PAGES,
    ),
    "fm": CorpusConfig(
        name="fm",
        base="https://developer.apple.com/tutorials/data/documentation/foundationmodels",
        public_root="https://developer.apple.com/documentation/foundationmodels",
        user_agent="foundation-models-corpus-scraper/0.1 "
                   "(+https://github.com/cassiocassio/what-would-apple-fm-say)",
        out_subdir="foundation-models-corpus",
        slug_re=NESTED_SLUG_RE,
        pages=FM_PAGES,
        identifier_prefix="doc://com.apple.foundationmodels/",
        landing_slug="foundationmodels",
    ),
    # mlx-swift: deferred. Phase 0c (2026-05-17) confirmed Swift Package Index
    # serves HTML only, not DocC JSON — Phase 2 of the handoff would fall back
    # to local `xcrun docc convert`. Not wired here; YAGNI until Phase 1
    # reading flags FM as insufficient.
}


# ---------- Fetch ----------


@dataclass
class FetchResult:
    slug: str
    data: dict
    raw_bytes: bytes


def default_out_dir(cfg: CorpusConfig) -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / cfg.out_subdir


def fetch_page(cfg: CorpusConfig, slug: str) -> FetchResult:
    if not cfg.slug_re.match(slug):
        raise ValueError(f"refusing to fetch unsafe slug: {slug!r}")
    # DocC framework landing pages live at the parent endpoint, not as a
    # child of themselves. e.g. .../documentation/foundationmodels.json
    # rather than .../documentation/foundationmodels/foundationmodels.json.
    if cfg.landing_slug and slug == cfg.landing_slug:
        url = f"{cfg.base}.json"
    else:
        url = f"{cfg.base}/{slug}.json"
    req = urllib.request.Request(url, headers={"User-Agent": cfg.user_agent})
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
            if "inlineContent" in n:
                out.append(render_inline(n["inlineContent"], references))
            elif "text" in n:
                out.append(n["text"])
    return "".join(out)


def render_declaration_tokens(tokens: list) -> str:
    """Render a DocC declaration's token stream as flat source text."""
    return "".join(tok.get("text", "") for tok in tokens)


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
        for col in node.get("columns", []):
            lines.extend(render_blocks(col.get("content", []), references, depth + 1))
    elif t == "tabNavigator":
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
    elif t == "termList":
        # DocC definition list: term + definition pairs. Render as a bold
        # term followed by an indented paragraph.
        for item in node.get("items", []):
            term_inline = item.get("term", {}).get("inlineContent", [])
            term_text = render_inline(term_inline, references)
            def_lines = render_blocks(
                item.get("definition", {}).get("content", []), references, depth + 1)
            def_text = " ".join(line for line in def_lines if line).strip()
            lines.append(f"- **{term_text}** — {def_text}" if def_text
                         else f"- **{term_text}**")
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


# ---------- Symbol-page section renderers ----------
#
# Foundation Models DocC pages add four kinds the HIG renderer didn't see
# (per Phase 0 results 2026-05-17):
#   - primaryContentSections[].kind == "declarations"  → Swift signature blocks
#   - primaryContentSections[].kind == "parameters"    → parameter tables
#   - primaryContentSections[].kind == "properties"    → property tables
#   - top-level relationshipsSections                  → conforms-to / inherits
#   - primaryContentSections[].kind == "mentions"      → cross-refs to other
#                                                         pages that link here
#   - top-level seeAlsoSections                        → cross-refs


def render_declarations_section(section: dict, references: dict) -> list[str]:
    lines: list[str] = ["## Declaration", ""]
    for decl in section.get("declarations", []):
        tokens = decl.get("tokens", [])
        code = render_declaration_tokens(tokens)
        languages = decl.get("languages", ["swift"])
        syntax = "swift" if "swift" in languages else (languages[0] if languages else "")
        lines.append(f"```{syntax}")
        lines.append(code)
        lines.append("```")
        lines.append("")
    return lines


def render_param_property_section(section: dict, references: dict,
                                  heading: str, items_key: str,
                                  name_key: str) -> list[str]:
    items = section.get(items_key, [])
    if not items:
        return []
    lines: list[str] = [f"## {heading}", ""]
    for item in items:
        name = item.get(name_key, "")
        content = item.get("content", [])
        body = render_blocks(content, references)
        body_text = " ".join(line for line in body if line).strip()
        lines.append(f"- **`{name}`** — {body_text}" if body_text else f"- **`{name}`**")
    lines.append("")
    return lines


def render_mentions_section(section: dict, references: dict) -> list[str]:
    idents = section.get("mentions", [])
    if not idents:
        return []
    lines: list[str] = ["## Mentioned in", ""]
    for ident in idents:
        ref_title, url = resolve_ref(ident, references)
        lines.append(f"- [{ref_title}]({url})" if url else f"- {ref_title}")
    lines.append("")
    return lines


def render_relationships_section(section: dict, references: dict) -> list[str]:
    title = section.get("title", "Relationships")
    idents = section.get("identifiers", [])
    if not idents:
        return []
    lines: list[str] = [f"## {title}", ""]
    for ident in idents:
        ref_title, url = resolve_ref(ident, references)
        lines.append(f"- [{ref_title}]({url})" if url else f"- {ref_title}")
    lines.append("")
    return lines


def render_see_also_section(section: dict, references: dict) -> list[str]:
    title = section.get("title", "See Also")
    idents = section.get("identifiers", [])
    if not idents:
        return []
    lines: list[str] = [f"## {title}", ""]
    for ident in idents:
        ref_title, url = resolve_ref(ident, references)
        lines.append(f"- [{ref_title}]({url})" if url else f"- {ref_title}")
    lines.append("")
    return lines


def doc_to_markdown(cfg: CorpusConfig, data: dict, slug: str) -> str:
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
    source_url = (cfg.public_root if cfg.landing_slug and slug == cfg.landing_slug
                  else f"{cfg.public_root}/{slug}")
    lines.append(f"_Source: {source_url}_  ")
    if platforms:
        lines.append(f"_Platforms: {platforms}_  ")
    if alert_date or alert_text:
        lines.append(f"_Last Apple update ({alert_date}): {alert_text}_  ")
    lines.append("")

    abstract = data.get("abstract", [])
    if abstract:
        lines.append(render_inline(abstract, references))
        lines.append("")

    for section in data.get("primaryContentSections", []):
        kind = section.get("kind")
        if kind == "content":
            lines.extend(render_blocks(section.get("content", []), references))
        elif kind == "declarations":
            lines.extend(render_declarations_section(section, references))
        elif kind == "parameters":
            lines.extend(render_param_property_section(
                section, references, "Parameters", "parameters", "name"))
        elif kind == "properties":
            lines.extend(render_param_property_section(
                section, references, "Properties", "items", "name"))
        elif kind == "mentions":
            lines.extend(render_mentions_section(section, references))
        else:
            warn_unknown(kind or "?", f"primaryContentSections (slug={slug})")

    # Symbol-page extras live at the top level, not in primaryContentSections.
    for rel_section in data.get("relationshipsSections", []) or []:
        lines.extend(render_relationships_section(rel_section, references))

    for see_section in data.get("seeAlsoSections", []) or []:
        lines.extend(render_see_also_section(see_section, references))

    return "\n".join(lines).rstrip() + "\n"


# ---------- Output ----------


def safe_write(corpus_root: Path, rel_path: Path, content: str) -> tuple[bool, Path]:
    """Write content to corpus_root/rel_path with a path-traversal guard."""
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


def write_index(cfg: CorpusConfig, corpus_root: Path,
                manifest: dict[str, list[str]], titles: dict[str, str]) -> None:
    lines = [f"# {cfg.out_subdir} index", ""]
    lines.append(f"Scraped from {cfg.public_root}")
    lines.append("")
    for category, slugs in manifest.items():
        lines.append(f"## {category}/")
        lines.append("")
        for slug in slugs:
            title = titles.get(slug, slug)
            lines.append(f"- [{title}]({category}/{slug}.md)")
        lines.append("")
    safe_write(corpus_root, Path("_index.md"), "\n".join(lines))


def write_readme(cfg: CorpusConfig, corpus_root: Path) -> None:
    content = f"""# {cfg.out_subdir}

Local mirror of Apple's developer docs ({cfg.name} corpus) for offline agent
reference.

- **Source:** {cfg.public_root}
- **Scraper:** `scripts/scrape-apple-corpus.py --corpus {cfg.name}`
- **Refresh cadence:** quarterly, plus after WWDC announcements.

Apple's content is copyrighted; this mirror is for personal/agent reference
only. Do not redistribute. The corpus lives outside any git repo by default.

## Layout

- `_index.md` — the page list with titles.
- `<category>/<slug>.md` — one markdown file per scraped page.
- `<category>/<slug>.md.sha256` — content-hash sidecar. The scraper only
  rewrites `<slug>.md` when its hash changes, so re-running against an
  unchanged source is a no-op. The sidecars are an implementation detail of
  the determinism gate — humans can ignore them; agents shouldn't read them.

## Citation contract (for agents)

Cite by `[{cfg.name.upper()}: <category>/<slug>.md#<anchor>] "verbatim phrase
of 8+ words"`. The phrase is the load-bearing anti-bluff: it must grep
against the file. Anchors are navigational hints only.
"""
    safe_write(corpus_root, Path("README.md"), content)


# ---------- Main ----------


def parse_manifest_arg(cfg: CorpusConfig, raw: str | None) -> dict[str, list[str]]:
    if not raw:
        return cfg.pages
    out: dict[str, list[str]] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        # Format: "category/slug" or "category/nested/member". Bare entries
        # land under "uncategorised". For FM nested members
        # (e.g. systemlanguagemodel/guardrails), pass as
        # "sessions/systemlanguagemodel/guardrails" — first segment is the
        # category, the rest is the slug.
        if "/" in entry:
            cat, slug = entry.split("/", 1)
        else:
            cat, slug = "uncategorised", entry
        out.setdefault(cat, []).append(slug)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else "")
    ap.add_argument("--corpus", choices=sorted(CONFIGS.keys()), default="hig",
                    help="which corpus to scrape (default: hig)")
    ap.add_argument("--out", type=Path, default=None,
                    help="output directory (default: $XDG_DATA_HOME/<corpus>-corpus)")
    ap.add_argument("--pages", type=str, default=None,
                    help="comma-separated overrides; format: category/slug")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    cfg = CONFIGS[args.corpus]
    manifest = parse_manifest_arg(cfg, args.pages)
    corpus_root = (args.out or default_out_dir(cfg)).resolve()
    corpus_root.mkdir(parents=True, exist_ok=True)

    titles: dict[str, str] = {}
    changed_count = 0
    total_count = 0
    first = True
    for category, slugs in manifest.items():
        for slug in slugs:
            total_count += 1
            if not cfg.slug_re.match(slug):
                print(f"  skip unsafe slug: {slug!r}", file=sys.stderr)
                continue
            if not first:
                time.sleep(RATE_LIMIT_SECONDS)
            first = False
            try:
                if not args.quiet:
                    print(f"fetch {category}/{slug}")
                result = fetch_page(cfg, slug)
            except urllib.error.HTTPError as e:
                print(f"  ERROR {slug}: HTTP {e.code}", file=sys.stderr)
                continue
            except Exception as e:
                print(f"  ERROR {slug}: {e}", file=sys.stderr)
                continue
            md = doc_to_markdown(cfg, result.data, slug)
            rel = Path(category) / f"{slug}.md"
            changed, _ = safe_write(corpus_root, rel, md)
            if changed:
                changed_count += 1
            titles[slug] = result.data.get("metadata", {}).get("title", slug)

    write_index(cfg, corpus_root, manifest, titles)
    write_readme(cfg, corpus_root)

    print(f"\ndone: {changed_count}/{total_count} pages changed; corpus at {corpus_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
