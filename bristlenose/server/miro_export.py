"""Miro export orchestration: quotes -> layout IR -> (preview | Miro board).

Pulls quotes for a project (optionally scoped to a quote_ids set — which is how
star / tag / section / hidden-exclusion all collapse to a selection), buckets
them into section/theme columns, runs the pure layout engine, and either renders
a creds-free SVG/HTML preview or pushes a real Miro board.

Synchronous by design for the v0 slice (an export is seconds for hundreds of
stickies) — no background-job table yet. See design-miro-bridge.md.

**This module owns the board's language.** A Miro board is a deliverable, so it
follows the caller's UI locale, which the SPA and the Mac sheet each send; the
layout engine below it is handed words and the renderer under it is handed a
locale. `locale` defaults to `"en"` throughout so a caller that sends nothing
gets exactly what the board produced before — the gap this closes is that until
22 Sep 2026 *every* caller was that caller, and a board built by a researcher
working in Spanish, from Spanish interviews, still said "Sections" and
"3 quotes". Whether a researcher can override it per board, as they can for the
HTML export (`docs/design-export-locale.md`), is an open product question and
deliberately not answered here.
"""

from __future__ import annotations

import logging
from html import escape
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from bristlenose import __version__, miro_client
from bristlenose.board_layout import (
    STICKY_SHAPE,
    Board,
    BoardStrings,
    Column,
    QuoteCard,
    Sticky,
    attribution,
    fit_miro_sticky,
    layout_board,
)
from bristlenose.board_manifest import FIGJAM_STICKY_SHAPE, build_manifest
from bristlenose.board_palette import FIGJAM_TOKEN_HEX
from bristlenose.i18n import plural_in, t_in
from bristlenose.miro_render_svg import render_html
from bristlenose.server.export_core import ExportableQuote, extract_quotes_for_export
from bristlenose.utils.safe_url import is_safe_url
from bristlenose.utils.timecodes import parse_timecode

logger = logging.getLogger(__name__)



def board_strings(locale: str) -> BoardStrings:
    """The board's vocabulary in `locale`.

    Section and theme are the report's own nouns, so these are the shipped keys
    the lenses already use rather than a second set that could disagree with the
    report the board was built from.
    """
    return BoardStrings(
        sections=t_in(locale, "common.quotes.sections"),
        themes=t_in(locale, "common.quotes.themes"),
        quote_count=lambda n: plural_in(locale, "common.miro.boardQuoteCount", n),
    )


def _parse_timecode(s: str) -> float:
    """'m:ss' or 'h:mm:ss' -> seconds, via the canonical parser.

    This is the EXPORT edge: ``q.timecode`` is Bristlenose's own
    ``format_timecode`` output (``export_core.py``), not a string from a Miro
    board. The hand-rolled version returned 0.0 for *any* failure and accepted
    any number of colon-separated parts. A refusal — reachable only at the
    declared >99 h limit — still yields 0.0 so the sticky is kept, but it is
    logged, and ``_clip_url`` declines to build a link to a clip that cannot
    exist at that position.
    """
    try:
        return parse_timecode(s)
    except (ValueError, AttributeError, TypeError):
        logger.warning("board_export_timecode_unparseable | raw=%r", s)
        return 0.0


def clips_base_ok(base: str) -> bool:
    """Whether a clip folder may become a link on a shared board: http(s) only,
    and no credentials in it (``https://user:token@host/`` would publish them)."""
    if not is_safe_url(base):
        return False
    parsed = urlparse(base)
    return parsed.scheme in ("http", "https") and not (parsed.username or parsed.password)


def _clip_url(base: str, q: ExportableQuote) -> str | None:
    """Best-effort clip URL from a user-supplied folder base + filename convention.

    Only http(s) bases are accepted — `html.escape` does NOT neutralise a
    `javascript:`/`data:` scheme, and this URL egresses into a shareable Miro
    board's `<a href>`. ASSUMPTION (A5): filename convention mirrors export-clips.
    """
    if not base:
        # No clip folder is the default, not a refusal — it was logged as
        # one, once per quote, on every board built without clip links.
        return None
    if not clips_base_ok(base):
        # Don't echo the user-supplied value into the log (log-injection guard).
        logger.warning("Ignoring clips_base for Miro links: not an http(s) URL")
        return None
    start = _parse_timecode(q.timecode)
    if start == 0.0 and q.timecode.strip() not in ("00:00", "0:00", "00:00:00"):
        # The parser refused the timecode and fell back to 0.0 — a link to
        # `…-0.mp4` would be a well-formed URL to a clip that does not exist.
        return None
    fname = f"{q.session}-{q.participant_code}-{int(start)}.mp4"
    return f"{base.rstrip('/')}/{fname}"


def build_columns(db: Session, project_id: int, quote_ids: list[str] | None,
                  clips_base: str = "", locale: str = "en") -> list[Column]:
    """Bucket the project's (optionally scoped) quotes into section/theme columns,
    preserving section display-order (extract_quotes_for_export is pre-sorted)."""
    quotes = extract_quotes_for_export(db, project_id, quote_ids=quote_ids, anonymise=False)
    if clips_base and not clips_base_ok(clips_base):
        # Said once for the board, not once per quote; the value itself is
        # not echoed (log-injection guard).
        logger.warning("Ignoring clips_base for board links: not an http(s) URL")
        clips_base = ""

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
        tlabel = (q.theme or "").strip() or t_in(locale, "common.tags.other")
        themes.setdefault(tlabel, Column(tlabel, "theme", [])).quotes.append(card)

    return list(sections.values()) + list(themes.values())


def board_title(locale: str, project_name: str, columns: list[Column]) -> str:
    n = sum(len(c.quotes) for c in columns)
    # The count goes through CLDR selection even in English, where the old
    # hand-rolled `({n} quotes)` titled a one-quote board "1 quotes".
    return t_in(
        locale, "common.miro.boardTitle",
        project=project_name,
        quotes=plural_in(locale, "common.miro.boardQuoteCount", n),
    )


def build_board(db: Session, project_id: int, project_name: str,
                quote_ids: list[str] | None, *, colour_by: str = "sentiment",
                clips_base: str = "", locale: str = "en", split: bool = True) -> Board:
    columns = build_columns(db, project_id, quote_ids, clips_base=clips_base, locale=locale)
    title = board_title(locale, project_name, columns)
    return layout_board(columns, title, colour_by=colour_by, strings=board_strings(locale),
                        split=split)


def build_figjam_manifest(db: Session, project_id: int, project_name: str,
                          quote_ids: list[str] | None, *, clips_base: str = "",
                          locale: str = "en", split: bool = True,
                          sticky_shape: str = FIGJAM_STICKY_SHAPE) -> dict[str, Any]:
    """The FigJam board document (`board_manifest`): the same selection, order,
    words and title as a Miro board, carried as structure for the plugin.

    Flat colour only — the cross-board baseline. It lives beside the Miro
    orchestration because it shares every step up to the renderer; the module
    becomes `board_export` when the renderer seam is extracted (design doc,
    *Map to our code*).
    """
    columns = build_columns(db, project_id, quote_ids, clips_base=clips_base, locale=locale)
    return build_manifest(
        columns, board_title(locale, project_name, columns),
        strings=board_strings(locale),
        clip_label=t_in(locale, "common.miro.clipLink"),
        palette=FIGJAM_TOKEN_HEX,
        locale=locale,
        generator=f"Bristlenose {__version__}",
        requested=len(dict.fromkeys(quote_ids)) if quote_ids else None,
        split=split,
        sticky_shape=sticky_shape,
    )


def build_preview_html(db: Session, project_id: int, project_name: str,
                       quote_ids: list[str] | None, *, colour_by: str = "sentiment",
                       clips_base: str = "", locale: str = "en", split: bool = True) -> str:
    """Creds-free: render exactly what would be pushed, as standalone HTML."""
    board = build_board(db, project_id, project_name, quote_ids,
                        colour_by=colour_by, clips_base=clips_base, locale=locale, split=split)
    return render_html(board, locale=locale)


# ---------------------------------------------------------------------------
# IR -> Miro shapes
# ---------------------------------------------------------------------------


def _sticky_content(s: Sticky, locale: str = "en") -> str:
    if s.kind == "header":
        label, *rest = s.text.split("\n")
        sub = f"<br>{escape(rest[0])}" if rest else ""
        return f"<strong>{escape(label)}</strong>{sub}"
    if not s.attributed:  # a part of a split quote before its last: the words alone
        return fit_miro_sticky(s.text, "")
    line = attribution(s.participant_id, s.timecode)
    if s.link_url:
        clip = escape(t_in(locale, "common.miro.clipLink"))
        line += f' · <a href="{escape(s.link_url, quote=True)}">▶ {clip}</a>'
    return fit_miro_sticky(s.text, f"<br><i>{line}</i>")


def _sticky_item(s: Sticky, locale: str = "en") -> dict[str, Any]:
    return {
        "type": "sticky_note",
        "data": {"content": _sticky_content(s, locale), "shape": STICKY_SHAPE},
        "style": {"fillColor": s.colour},
        "position": {"x": s.x + s.width / 2, "y": s.y + s.height / 2},
        "geometry": {"width": s.width},
    }


def group_sets(token: str, board_id: str, set_ids: list[int | None],
               made: list[dict[str, Any]]) -> int:
    """Group the parts of each split quote, so a set moves and sorts as one quote.

    ``set_ids`` is each item's set (None for a quote on one sticky), in the order the items were
    sent; ``made`` is what Miro created, in that order. A count that does not match is not guessed
    at: the board keeps its stickies, ungrouped, and the log says so. Returns the sets grouped."""
    if len(made) != len(set_ids):
        logger.warning("Miro made %d of %d items; split quotes left ungrouped", len(made), len(set_ids))
        return 0
    sets: dict[int, list[str]] = {}
    for sid, item in zip(set_ids, made, strict=True):
        if sid is not None and item.get("id"):
            sets.setdefault(sid, []).append(str(item["id"]))
    for ids in sets.values():
        miro_client.create_group(token, board_id, ids)
    return len(sets)


def push_to_miro(token: str, db: Session, project_id: int, project_name: str,
                 quote_ids: list[str] | None, *, colour_by: str = "sentiment",
                 clips_base: str = "", locale: str = "en", split: bool = True) -> dict[str, Any]:
    """Create a new Miro board from the layout IR. Returns {board_id, board_url, stickies}."""
    board = build_board(db, project_id, project_name, quote_ids,
                        colour_by=colour_by, clips_base=clips_base, locale=locale, split=split)
    # A quote has one attributed sticky however many parts it was split into.
    n_quotes = sum(1 for s in board.stickies if s.kind == "quote" and s.attributed)
    if n_quotes == 0:
        raise miro_client.MiroError(
            "No quotes match the current selection — nothing to export.",
            reason="no_quotes_selected",
        )

    created = miro_client.create_board(token, board.title)
    board_id = created.get("id")
    if not board_id:
        raise miro_client.MiroError("Miro did not return a board id", reason="no_board_id")
    view = created.get("viewLink") or f"https://miro.com/app/board/{board_id}/"
    logger.info("Miro board %s created (%s) — populating %d stickies", board_id, view, n_quotes)

    # Board exists from here — if a later call fails, surface the URL so the
    # researcher can find (or delete) the partially-built board.
    try:
        for f in board.frames:  # frames (position = centre)
            miro_client.create_frame(token, board_id, f.title,
                                     f.x + f.width / 2, f.y + f.height / 2, f.width, f.height)
        items = [_sticky_item(s, locale) for s in board.stickies]  # stickies, 20/bulk
        # The `stickies` count returned below is the *intended* count — Miro's
        # bulk endpoint can partially succeed, and we don't yet reconcile the
        # created-count against its response (deferred until a real multi-batch
        # push shows whether that count is clean enough to trust).
        made: list[dict[str, Any]] = []
        for i in range(0, len(items), 20):
            made += miro_client.bulk_create_items(token, board_id, items[i:i + 20])
        group_sets(token, board_id, [s.set_id for s in board.stickies], made)
        for t in board.texts:  # board title as a real text item
            miro_client.create_text(token, board_id, escape(t.text),
                                    t.x + 300, t.y, 600, int(t.size))
    except miro_client.MiroError as exc:
        logger.warning("Miro board %s partially populated: %s", board_id, exc)
        raise miro_client.MiroError(
            f"Board created but incomplete — open it: {view} ({exc})",
            reason="board_incomplete",
            vars={"url": view},
        ) from exc

    return {"board_id": board_id, "board_url": view, "stickies": n_quotes}
