"""The board as a portable, versioned document: what the FigJam plugin reads.

FigJam has no server write path, so Bristlenose cannot push a board there the
way it pushes one to Miro. It writes this document instead, the researcher opens
it in the Bristlenose FigJam plugin, and the plugin builds the board inside the
editor (`docs/design-board-integrations.md`, F1).

**Structure, not geometry.** A FigJam sticky is never shorter than 240 px and
grows with its text — 12 of 30 quotes in the 17 Oct 2026 spike outgrew it — so
the layout engine's fixed heights would overlap. The document carries frames →
columns → quotes in board order, and the plugin stacks each column by the height
it measures. Order and colour come from `board_layout`, so a FigJam board and a
Miro board of the same selection agree on both.

**Everything the board says is in the document.** A published plugin lags
Bristlenose releases, and it cannot translate. So the words (localised by the
caller), the attribution line, and the palette all travel here; the plugin only
draws. A colour or wording change then ships with Bristlenose, not with a plugin
review.

**No participant names, by construction.** The input is `Column`/`QuoteCard`,
which has no name field; `build_columns` dropped it upstream. The serialised
bytes are tested for a planted name and a name-bearing filename anyway, since
this is what leaves the machine.

Pure stdlib, like `board_layout`.
"""

from __future__ import annotations

import json
from typing import Any

from bristlenose.board_layout import (
    DEFAULT_QUOTE_TOKEN,
    HEADER_TOKEN,
    STICKY_SHAPE,
    BoardStrings,
    Column,
    attribution,
    quote_colour,
    quote_sort_key,
    quoted,
)

FORMAT = "bristlenose-board"
# Bump on any change a version-1 reader would misread. Adding an optional key a
# reader can ignore is not one; renaming or retyping a key is.
VERSION = 1


def build_manifest(
    columns: list[Column],
    title: str,
    *,
    strings: BoardStrings,
    clip_label: str,
    palette: dict[str, str],
    locale: str,
    generator: str,
    colour_by: str = "none",
) -> dict[str, Any]:
    """The document as a dict. `palette` maps every colour token used to hex.

    `colour_by` defaults to flat (pink headers, yellow quotes), the cross-board
    baseline. Only the tokens the board uses go into `palette`, so a reader never
    sees a colour it has no card for.
    """
    used: set[str] = {HEADER_TOKEN}
    frames: list[dict[str, Any]] = []
    for kind, frame_title in (("section", strings.sections), ("theme", strings.themes)):
        cols = [c for c in columns if c.kind == kind]
        if not cols:
            continue
        out_cols = []
        for col in cols:
            quotes = []
            for q in sorted(col.quotes, key=quote_sort_key):
                token = quote_colour(q, colour_by)
                used.add(token)
                quotes.append({
                    "text": quoted(q.text),
                    "attribution": attribution(q.participant_id, q.start_timecode),
                    "colour": token,
                    "clip_url": q.link_url,
                })
            out_cols.append({
                "label": col.label,
                "count": strings.quote_count(len(col.quotes)),
                "colour": HEADER_TOKEN,
                "quotes": quotes,
            })
        frames.append({"kind": kind, "title": frame_title, "columns": out_cols})

    return {
        "format": FORMAT,
        "version": VERSION,
        "generator": generator,
        "locale": locale,
        "title": title,
        # The house shape on every board (`board_layout.STICKY_SHAPE`); the
        # plugin draws "rectangle" as FigJam's wide sticky.
        "sticky_shape": STICKY_SHAPE,
        "strings": {"clip": f"▶ {clip_label}"},
        "palette": {t: palette.get(t, palette.get(DEFAULT_QUOTE_TOKEN, "")) for t in sorted(used)},
        "frames": frames,
    }


def to_json(manifest: dict[str, Any]) -> str:
    """Serialise once, ASCII-only: a quote can hold any character, and every one
    of them must stay inside its string value.

    This is a file the plugin reads with ``JSON.parse``, not a ``<script>``
    embed, so ``<`` is left as it is. Anything that inlines it into HTML must
    escape it first, and the plugin must never put its text through
    ``innerHTML``."""
    return json.dumps(manifest, ensure_ascii=True, indent=1)
