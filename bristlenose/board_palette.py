"""Canonical colour-token → hex map, shared across board renderers.

Single source of truth for what each board IR colour token renders as. The board
IR (`board_layout.py`) stores colour tokens by name (currently Miro's named-palette
strings, e.g. ``light_pink``); the *concrete hex* a renderer paints them is a
rendering concern, not an IR concern, so it lives here — one map, consumed by every
renderer that needs hex (the creds-free SVG preview today; Mural / Lucidspark
renderers later). The Miro renderer doesn't import this — it passes the named token
straight to Miro as ``fillColor`` (identity), which is why the tokens are Miro names.

**The cross-board baseline is two flat colours:** pink header stickies
(``light_pink``) and yellow quote stickies (``light_yellow``). That is what every
board reproduces by default — see ``docs/design-board-integrations.md``. The
remaining sentiment colours support the optional, non-default ``colour_by="sentiment"``
path; they are not a cross-board guarantee.

Pure stdlib (no bristlenose imports) so it stays fast and renderer-agnostic.
"""

from __future__ import annotations

# The two baseline tokens — the only colours guaranteed on every board.
HEADER_HEX = "#FADADD"  # Miro light_pink — column-header stickies
QUOTE_HEX = "#FFF9B1"  # Miro light_yellow — quote stickies (default)

# Full colour-token -> hex map. Baseline (header/quote) + the optional
# sentiment palette. Renderers that need hex import this; the Miro renderer uses
# the named tokens directly.
TOKEN_HEX = {
    "light_pink": HEADER_HEX,  # header (and, in the sentiment path, "negative")
    "light_yellow": QUOTE_HEX,  # quote default (and sentiment "mixed")
    "light_green": "#CDEBC5",  # sentiment positive
    "green": "#9BD7A0",  # sentiment delight
    "red": "#F4A6A6",  # sentiment frustration
    "light_blue": "#BEE0F2",  # sentiment confusion
    "gray": "#E2E2E2",  # sentiment neutral
}

# Fallback for an unknown token — the yellow quote default.
DEFAULT_HEX = QUOTE_HEX

# FigJam paints the same tokens from its own fixed sticky palette (decided 17 Oct
# 2026): Miro's pale hexes would register there as custom colours. A palette
# colour is matched exactly, so these are FigJam's own values, not near misses.
# The manifest carries this map, so the plugin draws whatever Bristlenose sends
# and a colour change never waits on a plugin release.
FIGJAM_TOKEN_HEX = {
    "light_pink": "#FFA8DB",  # FigJam Pink — header
    "light_yellow": "#FFE299",  # FigJam Yellow — quote default
    "light_green": "#B3EFBD",  # FigJam Green
    "green": "#B3F4EF",  # FigJam Teal — kept apart from light_green
    "red": "#FFB8A8",  # FigJam Red
    "light_blue": "#A8DAFF",  # FigJam Blue
    "gray": "#E6E6E6",  # FigJam Gray
}


def hex_for(token: str) -> str:
    """Resolve a board IR colour token to its canonical hex (yellow fallback)."""
    return TOKEN_HEX.get(token, DEFAULT_HEX)
