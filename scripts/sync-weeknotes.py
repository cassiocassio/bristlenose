#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["feedparser>=6.0", "html2text>=2024.2.26"]
# ///
"""Mirror blog.bristlenose.app posts to website/weeknotes/ as markdown.

Idempotent: only writes files that don't yet exist. Run weekly via launchd
or ad hoc. Substack RSS is the source of truth; this is an archive so the
writing survives independently of Substack.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import feedparser
import html2text

FEED_URL = "https://blog.bristlenose.app/feed"
OUT_DIR = Path(__file__).resolve().parent.parent / "website" / "weeknotes"


def slugify(title: str) -> str:
    s = re.sub(r"[^\w\s-]", "", title.lower()).strip()
    s = re.sub(r"[-\s]+", "-", s)
    return s[:60] or "untitled"


def to_markdown(html: str) -> str:
    h = html2text.HTML2Text()
    h.body_width = 0
    h.inline_links = True
    h.ignore_images = False
    return h.handle(html).strip()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    feed = feedparser.parse(FEED_URL)
    if feed.bozo and not feed.entries:
        print(f"error: could not parse {FEED_URL}: {feed.bozo_exception}", file=sys.stderr)
        return 1

    written = 0
    skipped = 0
    for entry in feed.entries:
        pub = entry.get("published_parsed") or entry.get("updated_parsed")
        if not pub:
            continue
        date = f"{pub.tm_year:04d}-{pub.tm_mon:02d}-{pub.tm_mday:02d}"
        path = OUT_DIR / f"{date}-{slugify(entry.title)}.md"
        if path.exists():
            skipped += 1
            continue
        html = entry.get("content", [{}])[0].get("value") or entry.get("summary", "")
        body = to_markdown(html)
        front = (
            "---\n"
            f'title: "{entry.title.replace(chr(34), chr(39))}"\n'
            f"date: {date}\n"
            f"source: {entry.link}\n"
            f"guid: {entry.get('id', entry.link)}\n"
            "---\n\n"
        )
        path.write_text(front + body + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(OUT_DIR.parent.parent)}")
        written += 1

    print(f"done: {written} new, {skipped} already present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
