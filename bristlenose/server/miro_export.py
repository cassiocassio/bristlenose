"""Miro export orchestration: quotes -> layout IR -> (preview | Miro board).

Pulls quotes for a project (optionally scoped to a quote_ids set — which is how
star / tag / section / hidden-exclusion all collapse to a selection), buckets
them into section/theme columns, runs the pure layout engine, and either renders
a creds-free SVG/HTML preview or pushes a real Miro board.

Synchronous by design for the v0 slice (an export is seconds for hundreds of
stickies) — no background-job table yet. See design-miro-bridge.md.
"""

from __future__ import annotations

from html import escape

from sqlalchemy.orm import Session

from bristlenose import miro_client
from bristlenose.miro_board import (
    Board,
    Column,
    QuoteCard,
    Sticky,
    fmt_timecode,
    layout_board,
)
from bristlenose.miro_render_svg import render_html
from bristlenose.server.export_core import extract_quotes_for_export

MAX_QUOTE_CHARS = 300  # keep stickies readable (Miro hard cap is 6000)


def _parse_timecode(s: str) -> float:
    """'m:ss' or 'h:mm:ss' -> seconds."""
    try:
        parts = [int(p) for p in s.split(":")]
    except (ValueError, AttributeError):
        return 0.0
    secs = 0
    for p in parts:
        secs = secs * 60 + p
    return float(secs)


def _clip_url(base: str, q) -> str | None:
    """Best-effort clip URL from a user-supplied folder base + filename convention.

    ASSUMPTION (A5): filename convention mirrors export-clips; verify on Mac.
    """
    if not base:
        return None
    fname = f"{q.session}-{q.participant_code}-{int(_parse_timecode(q.timecode))}.mp4"
    return f"{base.rstrip('/')}/{fname}"


def build_columns(db: Session, project_id: int, quote_ids: list[str] | None,
                  clips_base: str = "") -> list[Column]:
    """Bucket the project's (optionally scoped) quotes into section/theme columns,
    preserving section display-order (extract_quotes_for_export is pre-sorted)."""
    quotes = extract_quotes_for_export(db, project_id, quote_ids=quote_ids, anonymise=False)

    sections: dict[str, Column] = {}
    themes: dict[str, Column] = {}
    for q in quotes:
        card = QuoteCard(
            text=q.text,
            participant_id=q.participant_code,
            session_id=q.session,
            start_timecode=_parse_timecode(q.timecode),
            sentiment=(q.sentiment or None),
            link_url=_clip_url(clips_base, q),
        )
        label = (q.section or "").strip()
        if label:
            sections.setdefault(label, Column(label, "section", [])).quotes.append(card)
            continue
        tlabel = (q.theme or "").strip() or "Other"
        themes.setdefault(tlabel, Column(tlabel, "theme", [])).quotes.append(card)

    return list(sections.values()) + list(themes.values())


def build_board(db: Session, project_id: int, project_name: str,
                quote_ids: list[str] | None, *, colour_by: str = "sentiment",
                clips_base: str = "") -> Board:
    columns = build_columns(db, project_id, quote_ids, clips_base=clips_base)
    n = sum(len(c.quotes) for c in columns)
    title = f"{project_name} — research board ({n} quotes)"
    return layout_board(columns, title, colour_by=colour_by)


def build_preview_html(db: Session, project_id: int, project_name: str,
                       quote_ids: list[str] | None, *, colour_by: str = "sentiment",
                       clips_base: str = "") -> str:
    """Creds-free: render exactly what would be pushed, as standalone HTML."""
    board = build_board(db, project_id, project_name, quote_ids,
                        colour_by=colour_by, clips_base=clips_base)
    return render_html(board)


# ---------------------------------------------------------------------------
# IR -> Miro shapes
# ---------------------------------------------------------------------------


def _sticky_content(s: Sticky) -> str:
    if s.kind == "header":
        label, *rest = s.text.split("\n")
        sub = f"<br>{escape(rest[0])}" if rest else ""
        return f"<strong>{escape(label)}</strong>{sub}"
    body = s.text
    if len(body) > MAX_QUOTE_CHARS:
        body = body[: MAX_QUOTE_CHARS - 1].rstrip() + "…"
    attribution = f"— {s.participant_id.upper()} · {fmt_timecode(s.timecode)}"
    if s.link_url:
        attribution += f' · <a href="{escape(s.link_url, quote=True)}">▶ clip</a>'
    return f"{escape(body)}<br><i>{attribution}</i>"


def _sticky_item(s: Sticky) -> dict:
    return {
        "type": "sticky_note",
        "data": {"content": _sticky_content(s), "shape": "square"},
        "style": {"fillColor": s.colour},
        "position": {"x": s.x + s.width / 2, "y": s.y + s.height / 2},
        "geometry": {"width": s.width},
    }


def push_to_miro(token: str, db: Session, project_id: int, project_name: str,
                 quote_ids: list[str] | None, *, colour_by: str = "sentiment",
                 clips_base: str = "") -> dict:
    """Create a new Miro board from the layout IR. Returns {board_id, board_url, stickies}."""
    board = build_board(db, project_id, project_name, quote_ids,
                        colour_by=colour_by, clips_base=clips_base)

    created = miro_client.create_board(token, board.title)
    board_id = created["id"]

    # frames (position = centre)
    for f in board.frames:
        miro_client.create_frame(token, board_id, f.title,
                                 f.x + f.width / 2, f.y + f.height / 2, f.width, f.height)

    # stickies in bulk batches of 20
    items = [_sticky_item(s) for s in board.stickies]
    for i in range(0, len(items), 20):
        miro_client.bulk_create_items(token, board_id, items[i:i + 20])

    # board title as a real text item
    for t in board.texts:
        miro_client.create_text(token, board_id, escape(t.text),
                                t.x + 300, t.y, 600, int(t.size))

    view = created.get("viewLink") or f"https://miro.com/app/board/{board_id}/"
    n_quotes = sum(1 for s in board.stickies if s.kind == "quote")
    return {"board_id": board_id, "board_url": view, "stickies": n_quotes}
