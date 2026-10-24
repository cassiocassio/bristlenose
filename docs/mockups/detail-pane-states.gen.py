#!/usr/bin/env python3
"""Refresh the generated blocks in docs/mockups/detail-pane-states.html.

The page is hand-written; four blocks inside it are generated from the tree so
they cannot drift from what ships:

  sf          SF Symbols as CSS mask images, rendered from AppKit by
              experiments/icon-system/render_sf.swift (the same renderer the
              icon-system mockups use). Each class carries the symbol's own
              width and height per point (--sw / --sh), so symbols keep their
              true relative sizes at any --pt.
  lucide      An SVG <symbol> sprite built from the installed lucide-react
              package's own icon nodes (frontend/node_modules/lucide-react).
  status-css  bristlenose/theme/templates/status-page.css, verbatim.
  appicon     The app icon (Assets.xcassets, 256 px) for the BootView "before".

Markers in the HTML:  /* ⟦gen:NAME⟧ */ … /* ⟦/gen:NAME⟧ */   (CSS)
                      <!-- ⟦gen:NAME⟧ --> … <!-- ⟦/gen:NAME⟧ -->  (HTML)

Usage (macOS, from the repo root):
    python3 docs/mockups/detail-pane-states.gen.py
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs/mockups/detail-pane-states.html"
RENDERER = ROOT / "experiments/icon-system/render_sf.swift"
LUCIDE = ROOT / "frontend/node_modules/lucide-react/dist/esm/icons"
STATUS_CSS = ROOT / "bristlenose/theme/templates/status-page.css"
APP_ICON = ROOT / "desktop/Bristlenose/Bristlenose/Assets.xcassets/AppIcon.appiconset/icon_128x128@2x.png"

RENDER_PT = 64

SF_SYMBOLS = [
    # pane concepts (proposed)
    "tray.and.arrow.down", "square.stack", "clock", "questionmark.folder", "key",
    "doc.on.doc", "stop.circle", "externaldrive.badge.xmark", "network.slash",
    "exclamationmark.triangle",
    # (N03's icloud.and.arrow.down / icloud / cloud-download removed 22 Oct 2026: the
    # in-iCloud pane and glyph were deleted; docs/design-cloud-files.md)
    # pane icons shipped today that the proposal replaces
    "square.and.arrow.down", "externaldrive.trianglebadge.exclamationmark", "waveform",
    # sidebar row furniture
    "doc.text", "exclamationmark.triangle.fill", "xmark.circle.fill", "externaldrive",
    "network",
]

LUCIDE_ICONS = [
    "inbox", "layers", "clock", "folder-search", "key-round", "files", "circle-stop",
    "hard-drive", "wifi-off", "triangle-alert",
]


def css_class(name: str) -> str:
    return "sf-" + name.replace(".", "-")


def render_sf() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        out = subprocess.run(
            ["swift", str(RENDERER), tmp, str(RENDER_PT), "regular", *SF_SYMBOLS],
            capture_output=True, text=True, check=True, timeout=600,
        ).stdout
        if "MISSING" in out:
            sys.exit(f"renderer could not find: {out.split('MISSING:')[1].strip()}")
        sizes: dict[str, tuple[float, float]] = {}
        for line in out.splitlines():
            m = re.match(r"(\S+) regular \d+pt ([\d.]+)x([\d.]+)$", line.strip())
            if m:
                sizes[m.group(1)] = (float(m.group(2)), float(m.group(3)))
        lines = [f"  /* rendered {len(SF_SYMBOLS)} symbols at {RENDER_PT}pt regular, 2x, "
                 "black on transparent; used as masks so the tint stays a token */"]
        for name in SF_SYMBOLS:
            if name not in sizes:
                sys.exit(f"no size reported for {name}")
            w, h = sizes[name]
            png = Path(tmp) / f"{name}@regular-{RENDER_PT}.png"
            b64 = base64.b64encode(png.read_bytes()).decode()
            url = f"url(data:image/png;base64,{b64})"
            lines.append(
                f"  .{css_class(name)}{{-webkit-mask-image:{url};mask-image:{url};"
                f"--sw:{w / RENDER_PT:.4f};--sh:{h / RENDER_PT:.4f};}}"
            )
        return "\n".join(lines) + "\n"


def render_lucide() -> str:
    version = json.loads((LUCIDE.parents[2] / "package.json").read_text())["version"]
    js = (
        "const names=" + json.dumps(LUCIDE_ICONS) + ";const base=" + json.dumps(LUCIDE.as_uri())
        + ";Promise.all(names.map(n=>import(base+'/'+n+'.mjs').then(m=>[n,m.__iconData.node])))"
        ".then(r=>console.log(JSON.stringify(r)));"
    )
    nodes = json.loads(subprocess.run(
        ["node", "--input-type=module", "-e", js],
        capture_output=True, text=True, check=True, timeout=60,
    ).stdout)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" style="display:none" '
           f'data-source="lucide-react {version}">']
    for name, node in nodes:
        parts = []
        for tag, attrs in node:
            a = " ".join(f'{k}="{v}"' for k, v in attrs.items() if k != "key")
            parts.append(f"<{tag} {a}/>")
        out.append(f'  <symbol id="lu-{name}" viewBox="0 0 24 24">{"".join(parts)}</symbol>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def render_status_css() -> str:
    rel = STATUS_CSS.relative_to(ROOT)
    return f"  /* ════ {rel} — verbatim ════ */\n" + STATUS_CSS.read_text() + "\n"


def render_appicon() -> str:
    b64 = base64.b64encode(APP_ICON.read_bytes()).decode()
    return f"  .appicon{{background-image:url(data:image/png;base64,{b64});}}\n"


def replace_block(text: str, name: str, body: str, html: bool) -> str:
    if html:
        start, end = f"<!-- ⟦gen:{name}⟧ -->", f"<!-- ⟦/gen:{name}⟧ -->"
    else:
        start, end = f"/* ⟦gen:{name}⟧ */", f"/* ⟦/gen:{name}⟧ */"
    i, j = text.find(start), text.find(end)
    if i < 0 or j < 0 or j < i:
        sys.exit(f"marker for block '{name}' not found in {PAGE.name}")
    return text[: i + len(start)] + "\n" + body + text[j:]


def main() -> None:
    text = PAGE.read_text()
    text = replace_block(text, "status-css", render_status_css(), html=False)
    text = replace_block(text, "appicon", render_appicon(), html=False)
    text = replace_block(text, "sf", render_sf(), html=False)
    text = replace_block(text, "lucide", render_lucide(), html=True)
    PAGE.write_text(text)
    print(f"wrote {PAGE.relative_to(ROOT)} ({len(text) // 1024} KB)")


if __name__ == "__main__":
    main()
