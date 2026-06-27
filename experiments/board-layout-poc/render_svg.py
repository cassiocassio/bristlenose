"""SVG renderer for the board IR — the fast local feedback loop.

Translates a `Board` (frames + stickies + text items) into a standalone SVG you
can open in any browser. Throwaway renderer: it exists so we can iterate
spacing/colour/sizing in milliseconds instead of round-tripping the Miro API.
"""

from __future__ import annotations

from html import escape

from board_model import Board, Frame, Sticky, TextItem

BOARD_BG = "#F4F4F2"
PAD_IN = 16.0  # sticky inner text padding
BODY_FONT = 14.0
BODY_LH = 18.0
BODY_INK = "#2B2B2B"
QUOTE_STROKE = "#E3D9A6"

# frame chrome by kind
FRAME_CHROME = {
    "section": {"stroke": "#C3CEE2", "tab": "#D7DEEC", "ink": "#33415C"},
    "theme": {"stroke": "#D8C9E6", "tab": "#E4D7EF", "ink": "#553F72"},
}


def _fmt_timecode(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"


def _text_svg(x: float, y: float, line: str, *, size: float, weight: str, ink: str,
              italic: bool = False) -> str:
    style = ' font-style="italic"' if italic else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Inter, Helvetica, Arial, '
        f'sans-serif" font-size="{size:.0f}" font-weight="{weight}" fill="{ink}"{style} '
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
        f'rx="14" ry="14" fill="{f.fill}" stroke="{c["stroke"]}" stroke-width="1.5"/>',
        # name tab above the frame's top-left (Miro draws the frame title here)
        f'<rect x="{f.x:.1f}" y="{f.y - 30:.1f}" width="{tab_w:.1f}" height="24" rx="7" ry="7" '
        f'fill="{c["tab"]}" stroke="{c["stroke"]}" stroke-width="1"/>',
        _text_svg(f.x + 13, f.y - 13, f.title, size=13.0, weight="700", ink=c["ink"]),
        "</g>",
    ])


HEADER_STROKE = "#E8B7C0"


def _header_sticky_svg(s: Sticky) -> str:
    """Pale-pink column-title sticky: bold label + muted count, centred."""
    lines = s.text.split("\n")
    label = lines[0]
    sub = lines[1] if len(lines) > 1 else ""
    cx = s.x + s.width / 2
    parts = [
        "<g>",
        f'<rect x="{s.x:.1f}" y="{s.y:.1f}" width="{s.width:.1f}" height="{s.height:.1f}" '
        f'rx="10" ry="10" fill="{s.fill}" stroke="{HEADER_STROKE}" stroke-width="1.5" '
        f'filter="url(#shadow)"/>',
        f'<text x="{cx:.1f}" y="{s.y + 32:.1f}" text-anchor="middle" font-family="Inter, '
        f'Helvetica, Arial, sans-serif" font-size="16" font-weight="700" fill="{BODY_INK}">'
        f'{escape(label)}</text>',
    ]
    if sub:
        parts.append(
            f'<text x="{cx:.1f}" y="{s.y + 52:.1f}" text-anchor="middle" font-family="Inter, '
            f'Helvetica, Arial, sans-serif" font-size="12" font-weight="400" fill="#8a6b72">'
            f'{escape(sub)}</text>'
        )
    parts.append("</g>")
    return "\n".join(parts)


def _sticky_svg(s: Sticky) -> str:
    if s.kind == "header":
        return _header_sticky_svg(s)

    usable_w = s.width - 2 * PAD_IN
    max_chars = max(8, int(usable_w / (BODY_FONT * 0.52)))
    max_lines = max(1, int((s.height - 2 * PAD_IN) / BODY_LH))
    tx = s.x + PAD_IN

    parts = [
        "<g>",
        f'<rect x="{s.x:.1f}" y="{s.y:.1f}" width="{s.width:.1f}" height="{s.height:.1f}" '
        f'rx="10" ry="10" fill="{s.fill}" stroke="{QUOTE_STROKE}" stroke-width="1.5" '
        f'filter="url(#shadow)"/>',
    ]

    # quote body leads; reserve the bottom line for the italic attribution
    body_lines = _wrap(s.text, max_chars)
    budget = max(1, max_lines - 1)
    if len(body_lines) > budget:
        body_lines = body_lines[:budget]
        body_lines[-1] = body_lines[-1][: max_chars - 1].rstrip() + "…"

    ty = s.y + PAD_IN + BODY_FONT
    for line in body_lines:
        parts.append(_text_svg(tx, ty, line, size=BODY_FONT, weight="400", ink=BODY_INK))
        ty += BODY_LH

    # attribution: italic, same size/colour — the only de-emphasis a Miro sticky affords
    meta = f"— {s.participant_id.upper()} · {_fmt_timecode(s.timecode)}"
    parts.append(_text_svg(tx, s.y + s.height - PAD_IN + 2, meta,
                           size=BODY_FONT, weight="400", ink=BODY_INK, italic=True))
    parts.append("</g>")
    return "\n".join(parts)


def _textitem_svg(t: TextItem) -> str:
    return _text_svg(t.x, t.y, t.text, size=t.size, weight=t.weight, ink=t.color)


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
    """Wrap the SVG in a phone-friendly HTML page: fits to screen width on first
    view, pinch-to-zoom enabled, horizontal scroll for the full board."""
    svg = render_svg(board).split("?>", 1)[-1].strip()  # drop XML prolog
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=6, user-scalable=yes">
<title>{escape(board.title)}</title>
<style>
  html,body{{margin:0;background:{BOARD_BG};
    font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;}}
  .hint{{position:fixed;top:0;left:0;right:0;padding:7px 12px;font-size:12px;color:#666;
    background:rgba(255,255,255,.92);border-bottom:1px solid #e4e4e7;z-index:2;}}
  .scroll{{padding-top:34px;overflow:auto;-webkit-overflow-scrolling:touch;}}
  svg{{display:block;width:100%;height:auto;}}
</style>
</head>
<body>
  <div class="hint">Research board — first draft · pinch to zoom, drag to pan</div>
  <div class="scroll">
{svg}
  </div>
</body>
</html>
"""
