#!/usr/bin/env python3
"""Embed the mockup SVGs into the catalogue markdown as data URIs.

Why: sandboxed/preview renderers (iA Writer opened on a single file, the Claude
desktop markdown preview, etc.) won't load sibling image *files* off disk —
relative `![](png/…)` paths show as broken images. Inlining each SVG as a
`data:image/svg+xml;base64,…` URI makes the doc fully self-contained, so it renders
anywhere without filesystem access. SVG (vector) embeds at ~300 KB total vs ~5 MB
for the same set as base64 PNG, and stays crisp at any zoom.

Idempotent: matches `![STEM](…)` whether the target is a `mockups/…` path or an
existing data URI, and re-embeds from source. Re-run after changing any mockup. The
`svg/` + `png/` files remain on disk as the editable source / for any context that
*can* load files (e.g. swapping back to relative refs for GitHub).

Default embeds SVG (~300 KB total, crisp, vector). If a preview tool sanitises SVG
data URIs and shows blanks, fall back to raster:

  python3 embed-images.py            # SVG data URIs (default)
  python3 embed-images.py --png      # PNG data URIs (~3–5 MB, universally rendered)
  python3 embed-images.py --png 900  # PNG at a custom width
"""

from __future__ import annotations

import base64
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent                      # docs/mockups/detail-panes
SVG_DIR = HERE / "svg"
PNG_DIR = HERE / "png"
DOC = HERE.parent.parent / "design-detail-panes-catalogue.md"   # docs/…catalogue.md

# ![STEM](  mockups/…  OR  data:image/{svg+xml,png};base64,…  )
IMG_RE = re.compile(
    r"!\[([A-Za-z0-9_-]+)\]\((?:mockups/detail-panes/[^)]+"
    r"|data:image/(?:svg\+xml|png);base64,[^)]+)\)"
)


def svg_uri(stem: str) -> str | None:
    src = SVG_DIR / f"{stem}.svg"
    if not src.exists():
        return None
    b64 = base64.b64encode(src.read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def png_uri(stem: str, width: int) -> str | None:
    src = PNG_DIR / f"{stem}.png"
    if not src.exists():
        return None
    with tempfile.NamedTemporaryFile(suffix=".png") as tf:
        subprocess.run(["sips", "--resampleWidth", str(width), str(src), "--out", tf.name],
                       check=True, capture_output=True)
        b64 = base64.b64encode(Path(tf.name).read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def main() -> None:
    png_mode = "--png" in sys.argv
    width = 1100
    if png_mode:
        rest = [a for a in sys.argv[2:] if a.isdigit()]
        if rest:
            width = int(rest[0])

    text = DOC.read_text(encoding="utf-8")
    embedded = 0
    missing: list[str] = []

    def repl(m: re.Match[str]) -> str:
        nonlocal embedded
        stem = m.group(1)
        uri = png_uri(stem, width) if png_mode else svg_uri(stem)
        if uri is None:
            missing.append(stem)
            return m.group(0)
        embedded += 1
        return f"![{stem}]({uri})"

    text = IMG_RE.sub(repl, text)
    DOC.write_text(text, encoding="utf-8")
    kind = f"PNG@{width}w" if png_mode else "SVG"
    print(f"embedded {embedded} {kind} images into {DOC.name} ({DOC.stat().st_size // 1024} KB)")
    if missing:
        print(f"  WARNING: no source for: {', '.join(missing)}")


if __name__ == "__main__":
    main()
