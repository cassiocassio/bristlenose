"""SVG/HTML preview renderer for the Miro board IR.

Lets a researcher see exactly what would be pushed to Miro *without* any Miro
account or token — the creds-free preview path. Pure stdlib. Ported from
experiments/board-layout-poc/render_svg.py and adapted to colour tokens.
"""

from __future__ import annotations

from html import escape

from bristlenose.board_palette import hex_for
from bristlenose.miro_board import Board, Frame, Sticky, TextItem, fmt_timecode

BOARD_BG = "#F4F4F2"
PAD_IN = 16.0
BODY_FONT = 14.0
BODY_LH = 18.0
BODY_INK = "#2B2B2B"
HEADER_STROKE = "#E8B7C0"
QUOTE_STROKE = "#E3D9A6"

FRAME_CHROME = {
    "section": {"fill": "#ECEFF5", "stroke": "#C3CEE2", "tab": "#D7DEEC", "ink": "#33415C"},
    "theme": {"fill": "#F2ECF6", "stroke": "#D8C9E6", "tab": "#E4D7EF", "ink": "#553F72"},
}


def _hex(token: str) -> str:
    return hex_for(token)


def _text(x: float, y: float, line: str, *, size: float, weight: str, ink: str,
          italic: bool = False, anchor: str = "start") -> str:
    style = ' font-style="italic"' if italic else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-family="Inter, Helvetica, '
        f'Arial, sans-serif" font-size="{size:.0f}" font-weight="{weight}" fill="{ink}"{style} '
        f'xml:space="preserve">{escape(line)}</text>'
    )


def _wrap(text: str, max_chars: int) -> list[str]:
    lines: list[str] = []
    for raw in text.split("\n"):
        if not raw:
            lines.append("")
            continue
        cur = ""
        for w in raw.split(" "):
            cand = w if not cur else f"{cur} {w}"
            if len(cand) <= max_chars:
                cur = cand
            else:
                if cur:
                    lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def _frame_svg(f: Frame) -> str:
    c = FRAME_CHROME.get(f.kind, FRAME_CHROME["section"])
    tab_w = len(f.title) * 8.6 + 26
    return "\n".join([
        "<g>",
        f'<rect x="{f.x:.1f}" y="{f.y:.1f}" width="{f.width:.1f}" height="{f.height:.1f}" '
        f'rx="14" ry="14" fill="{c["fill"]}" stroke="{c["stroke"]}" stroke-width="1.5"/>',
        f'<rect x="{f.x:.1f}" y="{f.y - 30:.1f}" width="{tab_w:.1f}" height="24" rx="7" ry="7" '
        f'fill="{c["tab"]}" stroke="{c["stroke"]}" stroke-width="1"/>',
        _text(f.x + 13, f.y - 13, f.title, size=13.0, weight="700", ink=c["ink"]),
        "</g>",
    ])


def _sticky_svg(s: Sticky) -> str:
    fill = _hex(s.colour)
    if s.kind == "header":
        lines = s.text.split("\n")
        cx = s.x + s.width / 2
        parts = [
            "<g>",
            f'<rect x="{s.x:.1f}" y="{s.y:.1f}" width="{s.width:.1f}" height="{s.height:.1f}" '
            f'rx="10" ry="10" fill="{fill}" stroke="{HEADER_STROKE}" stroke-width="1.5" '
            f'filter="url(#shadow)"/>',
            _text(cx, s.y + 32, lines[0], size=16, weight="700", ink=BODY_INK, anchor="middle"),
        ]
        if len(lines) > 1:
            parts.append(_text(cx, s.y + 52, lines[1], size=12, weight="400", ink="#8a6b72",
                               anchor="middle"))
        parts.append("</g>")
        return "\n".join(parts)

    usable_w = s.width - 2 * PAD_IN
    max_chars = max(8, int(usable_w / (BODY_FONT * 0.52)))
    max_lines = max(1, int((s.height - 2 * PAD_IN) / BODY_LH))
    tx = s.x + PAD_IN
    parts = [
        "<g>",
        f'<rect x="{s.x:.1f}" y="{s.y:.1f}" width="{s.width:.1f}" height="{s.height:.1f}" '
        f'rx="10" ry="10" fill="{fill}" stroke="{QUOTE_STROKE}" stroke-width="1.5" '
        f'filter="url(#shadow)"/>',
    ]
    body_lines = _wrap(s.text, max_chars)
    budget = max(1, max_lines - 1)
    if len(body_lines) > budget:
        body_lines = body_lines[:budget]
        body_lines[-1] = body_lines[-1][: max_chars - 1].rstrip() + "…"
    ty = s.y + PAD_IN + BODY_FONT
    for line in body_lines:
        parts.append(_text(tx, ty, line, size=BODY_FONT, weight="400", ink=BODY_INK))
        ty += BODY_LH
    link = " 🔗" if s.link_url else ""
    meta = f"— {s.participant_id.upper()} · {fmt_timecode(s.timecode)}{link}"
    parts.append(_text(tx, s.y + s.height - PAD_IN + 2, meta,
                       size=BODY_FONT, weight="400", ink=BODY_INK, italic=True))
    parts.append("</g>")
    return "\n".join(parts)


def _textitem_svg(t: TextItem) -> str:
    return _text(t.x, t.y, t.text, size=t.size, weight=t.weight, ink="#1A1A1A")


def render_svg(board: Board) -> str:
    frames = "\n".join(_frame_svg(f) for f in board.frames)
    texts = "\n".join(_textitem_svg(t) for t in board.texts)
    stickies = "\n".join(_sticky_svg(s) for s in board.stickies)
    w, h = int(board.width), int(board.height)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-opacity="0.18"/>
    </filter>
  </defs>
  <rect x="0" y="0" width="{w}" height="{h}" fill="{BOARD_BG}"/>
{frames}
{texts}
{stickies}
</svg>
"""


def render_html(board: Board) -> str:
    """Phone/desktop-friendly standalone HTML wrapping the SVG."""
    svg = render_svg(board).split("?>", 1)[-1].strip()
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=6, user-scalable=yes">
<title>{escape(board.title)}</title>
<style>html,body{{margin:0;background:{BOARD_BG};font-family:Inter,-apple-system,sans-serif;}}
.hint{{position:fixed;top:0;left:0;right:0;padding:7px 12px;font-size:12px;color:#666;
background:rgba(255,255,255,.92);border-bottom:1px solid #e4e4e7;z-index:2;}}
.scroll{{padding-top:34px;overflow:auto;-webkit-overflow-scrolling:touch;}}
svg{{display:block;width:100%;height:auto;}}</style></head>
<body><div class="hint">Miro board preview — this is what would be pushed</div>
<div class="scroll">
{svg}
</div></body></html>
"""
