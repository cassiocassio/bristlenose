"""A researcher's own paragraph breaks in a quote: the rules, in one place.

The quote card draws a long quote as paragraphs. By default they are placed
automatically, in the browser, from the words (``frontend/src/utils/breakParagraphs.ts``),
and nothing is stored. A researcher who starts or joins a paragraph by hand
(Shift-Return, Backspace at a paragraph's start, while editing the quote) makes
the quote's paragraphs their own, and those are stored here (``QuoteBreak``).

A break is a position, "after word i", counted in the quote's resolved wording:
the researcher's edit if there is one, else the pipeline's text. Words are what
``str.split()`` gives. The browser splits on ``/\\s+/``, which differs from it on a
few rare characters (U+FEFF; U+0085 and U+001C–U+001F): a quote carrying one can
have its breaks refused or shown one word off (review 21 Nov, finding 11). The row
carries a hash of the wording it was made against; when the wording changes
(a re-analysis rewords the quote, an edit lands without new breaks) the row is
not shown, and the quote falls back to automatic paragraphs without a message
(docs/design-quote-anchor.md §3.4).
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping

from sqlalchemy.orm import Session

from bristlenose.server.models import Quote, QuoteBreak

logger = logging.getLogger(__name__)

#: The one level used today: a thought (a paragraph). Level 1 (a phrase) is
#: reserved for the line-level breaks still in the lab.
LEVEL_THOUGHT = 2


def verify_of(text: str) -> str:
    """The hash of a wording's words: spacing never counts as a change."""
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()[:16]


def valid(breaks: list[int], text: str) -> bool:
    """Strictly increasing word positions, each with a word on both sides."""
    last = len(text.split()) - 2
    return all(0 <= b <= last for b in breaks) and all(a < b for a, b in zip(breaks, breaks[1:], strict=False))


def encode(breaks: list[int]) -> str:
    return json.dumps([[b, LEVEL_THOUGHT] for b in breaks])


def decode(raw: str) -> list[int] | None:
    """The thought-level positions, or None for a row that cannot be read."""
    try:
        data = json.loads(raw)
        return [int(i) for i, level in data if level == LEVEL_THOUGHT]
    except (ValueError, TypeError):
        return None


def resolved(
    db: Session, quotes: Mapping[int, Quote], edit_map: Mapping[int, str],
) -> dict[int, list[int]]:
    """The researcher's breaks for each quote that has them and whose wording still matches."""
    if not quotes:
        return {}
    out: dict[int, list[int]] = {}
    # Kept off the screen on purpose, but never off the record: a researcher
    # whose paragraphs vanished can be told why (review 21 Nov, finding 15).
    dropped: dict[str, list[int]] = {}
    for row in db.query(QuoteBreak).filter(QuoteBreak.quote_id.in_(list(quotes))).all():
        quote = quotes.get(row.quote_id)
        if quote is None:
            continue
        wording = edit_map.get(row.quote_id) or quote.text
        if row.verify != verify_of(wording):
            dropped.setdefault("wording_changed", []).append(row.quote_id)
            continue
        breaks = decode(row.breaks)
        if breaks is None:
            dropped.setdefault("unreadable", []).append(row.quote_id)
        elif not valid(breaks, wording):
            dropped.setdefault("invalid", []).append(row.quote_id)
        else:
            out[row.quote_id] = breaks
    if dropped:
        # Ids only, never the words: this goes to the project log.
        logger.info(
            "quote_breaks_not_shown | %s",
            " ".join(f"{why}={len(ids)} (quote ids {ids[:10]})" for why, ids in sorted(dropped.items())),
        )
    return out
