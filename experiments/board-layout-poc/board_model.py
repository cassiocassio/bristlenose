"""Target-agnostic board IR for the research-board POC.

This is the thing that survives: the layout engine produces a `Board` of
`Sticky` rectangles in absolute board coordinates, and *renderers* translate it
to a concrete surface (SVG today; Miro REST / a FigJam plugin manifest later).
No Miro, no network, no Figma — just geometry + colour + text.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Sticky:
    """One rectangle on the board, positioned by its top-left corner."""

    kind: str  # "header" | "quote"
    x: float
    y: float
    width: float
    height: float
    fill: str  # hex colour, e.g. "#FFF9B1"
    text: str  # body text (already composed)
    # carried for later renderers / sorting provenance, unused by SVG:
    session_id: str = ""
    timecode: float = 0.0
    participant_id: str = ""


@dataclass
class Board:
    """A laid-out board: a flat list of stickies plus overall canvas size."""

    title: str
    stickies: list[Sticky] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
