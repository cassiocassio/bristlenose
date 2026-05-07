"""Canonical message-kind taxonomy across CLI, toasts, and the Mac popover.

Five kinds — anything more is over-cataloguing.

Glyph and colour tables are the single source of truth. CLI helpers in
``bristlenose/pipeline.py`` consume :data:`CLI_GLYPH` / :data:`CLI_COLOUR`
directly; the Swift desktop mirror (``MessageKind.swift``) duplicates the
enum values and the glyph table by hand and is pinned to this module via
the cross-language fixture at ``tests/fixtures/pipeline-summary-contract.json``.

Adding a sixth kind: don't, until the existing five demonstrably can't
carry the case. Cached → SUCCESS with a metadata suffix; pending/running
→ status, not a kind; fatal → ERROR (telemetry can subdivide).
"""

from __future__ import annotations

from enum import Enum


class MessageKind(str, Enum):
    """Five-kind message taxonomy. Source of truth for CLI/toast/popover rendering."""

    SUCCESS = "success"  # ✓  step done as expected
    INFO = "info"        # ℹ  neutral note, no action needed
    WARNING = "warning"  # ⚠  recoverable / partial / soft-degrade
    ERROR = "error"      # ✗  did not complete; user/dev action needed
    SKIPPED = "skipped"  # —  not applicable in this run


# Unicode glyph used at the start of CLI lines and (mirrored) in the Mac
# popover rows. Kept Unicode rather than SF Symbols so CLI and popover
# render identically when the user copy-pastes a popover diagnostic.
CLI_GLYPH: dict[MessageKind, str] = {
    MessageKind.SUCCESS: "✓",
    MessageKind.INFO: "ℹ",
    MessageKind.WARNING: "⚠",
    MessageKind.ERROR: "✗",
    MessageKind.SKIPPED: "—",
}


# Rich/Click colour names. Cyan reads cleanly on both light and dark
# terminals; "dim" for SKIPPED demotes the row without colouring it.
CLI_COLOUR: dict[MessageKind, str] = {
    MessageKind.SUCCESS: "green",
    MessageKind.INFO: "cyan",
    MessageKind.WARNING: "yellow",
    MessageKind.ERROR: "red",
    MessageKind.SKIPPED: "dim",
}


def cli_prefix(kind: MessageKind) -> str:
    """Return the leading ``[colour]glyph[/colour]`` Rich markup for a CLI line."""
    return f"[{CLI_COLOUR[kind]}]{CLI_GLYPH[kind]}[/{CLI_COLOUR[kind]}]"
