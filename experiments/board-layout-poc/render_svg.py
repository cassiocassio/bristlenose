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
META_FONT = 12.0
META_INK = "#8a8a90"  # muted grey for supporting attribution
BODY_INK = "#2B2B2B"


def _fmt_timecode(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"


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


def _text_svg(
    x: float, y: float, line: str, *, size: float, weight: str, ink: str, italic: bool = False
) -> str:
    style = ' font-style="italic"' if italic else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Inter, Helvetica, Arial, '
        f'sans-serif" font-size="{size:.0f}" font-weight="{weight}" fill="{ink}"{style} '
        f'xml:space="preserve">{escape(line)}</text>'
    )


def _sticky_svg(s: Sticky) -> str:
    usable_w = s.width - 2 * PAD_IN
    max_chars = max(8, int(usable_w / (BODY_FONT * 0.52)))
    max_lines = max(1, int((s.height - 2 * PAD_IN) / BODY_LH))

    is_header = s.kind == "header"
    stroke = HEADER_STROKE if is_header else STROKE
    rx = 10

    parts = [
        '<g>',
        f'<rect x="{s.x:.1f}" y="{s.y:.1f}" width="{s.width:.1f}" '
        f'height="{s.height:.1f}" rx="{rx}" ry="{rx}" fill="{s.fill}" '
        f'stroke="{stroke}" stroke-width="1.5" filter="url(#shadow)"/>',
    ]
    tx = s.x + PAD_IN

    if is_header:
        # Header: label prominent (first line bold), supporting line muted.
        lines = _wrap(s.text, max_chars)
        ty = s.y + PAD_IN + BODY_FONT
        for i, line in enumerate(lines[:max_lines]):
            if i == 0:
                parts.append(_text_svg(tx, ty, line, size=BODY_FONT, weight="700", ink=BODY_INK))
            else:
                parts.append(_text_svg(tx, ty, line, size=META_FONT, weight="400", ink=META_INK))
            ty += BODY_LH
    else:
        # Quote: body leads (normal weight); attribution trails as muted metadata.
        # Reserve the bottom line for the "— P1 · 0:10" supporting line so the
        # meaning is read first and the who/when never overlaps it.
        body_lines = _wrap(s.text, max_chars)
        body_budget = max(1, max_lines - 1)
        if len(body_lines) > body_budget:
            body_lines = body_lines[:body_budget]
            body_lines[-1] = body_lines[-1][: max_chars - 1].rstrip() + "…"

        ty = s.y + PAD_IN + BODY_FONT
        for line in body_lines:
            parts.append(_text_svg(tx, ty, line, size=BODY_FONT, weight="400", ink=BODY_INK))
            ty += BODY_LH

        # Attribution: italic, SAME size/colour as the quote — this mirrors what a
        # real Miro sticky can render (auto-fit font, no per-span size or colour;
        # <i> is the only de-emphasis lever the sticky API affords).
        meta = f"— {s.participant_id.upper()} · {_fmt_timecode(s.timecode)}"
        meta_y = s.y + s.height - PAD_IN + 2
        parts.append(
            _text_svg(tx, meta_y, meta, size=BODY_FONT, weight="400", ink=BODY_INK, italic=True)
        )

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
