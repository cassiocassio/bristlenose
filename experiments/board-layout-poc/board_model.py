"""Target-agnostic board IR for the research-board POC.

This is the thing that survives: the layout engine produces a `Board` of frames
(named containers → Miro frames), stickies (quotes → Miro sticky notes parented
into a frame), and free text items (titles/legend → Miro text items, which —
unlike stickies — afford real font size + colour). Renderers translate it to a
concrete surface (SVG today; Miro REST later). No Miro, no network, no Figma —
just geometry + colour + text.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Frame:
    """A named container column → a Miro frame (`data.title` = the label)."""

    title: str
    x: float
    y: float
    width: float
    height: float
    fill: str  # faint background tint
    kind: str = "section"  # "section" | "theme"


@dataclass
class Sticky:
    """A Miro sticky note, positioned by its top-left corner.

    kind="header" → pale-pink column-title sticky; kind="quote" → yellow quote.
    """

    x: float
    y: float
    width: float
    height: float
    fill: str  # hex colour, e.g. "#FFF9B1"
    text: str  # quote body / column label (already composed)
    kind: str = "quote"  # "header" | "quote"
    # carried for the renderer / later Miro mapping:
    session_id: str = ""
    timecode: float = 0.0
    participant_id: str = ""


@dataclass
class TextItem:
    """Free text → a Miro text item (real fontSize + colour, no sticky needed)."""

    text: str
    x: float
    y: float
    size: float
    color: str
    weight: str = "700"


@dataclass
class Board:
    """A laid-out board: frames + stickies + text items, plus canvas size."""

    title: str
    frames: list[Frame] = field(default_factory=list)
    stickies: list[Sticky] = field(default_factory=list)
    texts: list[TextItem] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
