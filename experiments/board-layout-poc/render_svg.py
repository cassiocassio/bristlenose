"""SVG renderer for the board IR — the fast local feedback loop.

Translates a `Board` into a standalone .svg you can open in any browser. This is
the throwaway renderer: it exists so we can iterate spacing/colour/sizing in
milliseconds instead of round-tripping through the Miro API.
"""

from __future__ import annotations

from html import escape

from board_model import Board, Sticky

BOARD_BG = "#F4F4F2"
STROKE = "#E3D9A6"  # faint quote-sticky edge
HEADER_STROKE = "#E8B7C0"
PAD_IN = 16.0  # inner text padding
BODY_FONT = 14.0
BODY_LH = 18.0
META_FONT = 13.0


def _wrap(text: str, max_chars: int) -> list[str]:
    """Naive word-wrap to a character budget per line."""
    lines: list[str] = []
    for raw_line in text.split("\n"):
        if not raw_line:
            lines.append("")
            continue
        words = raw_line.split(" ")
        cur = ""
        for w in words:
            candidate = w if not cur else f"{cur} {w}"
            if len(candidate) <= max_chars:
                cur = candidate
            else:
                if cur:
                    lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def _sticky_svg(s: Sticky) -> str:
    usable_w = s.width - 2 * PAD_IN
    max_chars = max(8, int(usable_w / (BODY_FONT * 0.52)))
    max_lines = max(1, int((s.height - 2 * PAD_IN) / BODY_LH))

    is_header = s.kind == "header"
    stroke = HEADER_STROKE if is_header else STROKE
    rx = 10

    parts = [
        f'<g>',
        f'<rect x="{s.x:.1f}" y="{s.y:.1f}" width="{s.width:.1f}" '
        f'height="{s.height:.1f}" rx="{rx}" ry="{rx}" fill="{s.fill}" '
        f'stroke="{stroke}" stroke-width="1.5" filter="url(#shadow)"/>',
    ]

    lines = _wrap(s.text, max_chars)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max_chars - 1].rstrip() + "…"

    tx = s.x + PAD_IN
    ty = s.y + PAD_IN + BODY_FONT
    for i, line in enumerate(lines):
        # first line of any sticky is the label/meta line — render it bolder
        is_meta = i == 0
        weight = "700" if is_meta else "400"
        size = META_FONT if (is_meta and not is_header) else BODY_FONT
        parts.append(
            f'<text x="{tx:.1f}" y="{ty:.1f}" font-family="Inter, Helvetica, '
            f'Arial, sans-serif" font-size="{size:.0f}" font-weight="{weight}" '
            f'fill="#2B2B2B" xml:space="preserve">{escape(line)}</text>'
        )
        ty += BODY_LH
    parts.append("</g>")
    return "\n".join(parts)


def render_svg(board: Board) -> str:
    body = "\n".join(_sticky_svg(s) for s in board.stickies)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{board.width:.0f}" \
height="{board.height:.0f}" viewBox="0 0 {board.width:.0f} {board.height:.0f}">
  <defs>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-opacity="0.18"/>
    </filter>
  </defs>
  <rect x="0" y="0" width="{board.width:.0f}" height="{board.height:.0f}" \
fill="{BOARD_BG}"/>
  <text x="{64}" y="{40}" font-family="Inter, Helvetica, Arial, sans-serif" \
font-size="22" font-weight="700" fill="#1A1A1A">{escape(board.title)}</text>
{body}
</svg>
"""
