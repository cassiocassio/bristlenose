"""The five-kind glyph table exists three times; this pins the web mirror.

``bristlenose/ui_kinds.py`` is the source.  ``MessageKind.swift`` is the desktop
mirror, pinned by ``tests/fixtures/pipeline-summary-contract.json``.  This pins
``frontend/src/utils/messageKind.ts``, which had no gate at all.

Asserted from Python rather than Vitest deliberately: the web test would have to
read a ``.py`` file, and ``npm run build`` runs ``tsc -b`` over test files with
no ``@types/node`` in scope -- so ``readFileSync`` type-checks under Vitest and
then fails the build.  ``tests/test_export_css_selectors.py`` already reads
``frontend/src`` from pytest; this follows it.

The point is not tidiness.  ``docs/design-pipeline-diagnostic-popover.md``
forbids minting new glyphs, and a fourth surface quietly rendering a sixth one
is exactly the drift nothing else would catch.
"""

from __future__ import annotations

import re
from pathlib import Path

from bristlenose.ui_kinds import CLI_GLYPH, MessageKind

_TS = (
    Path(__file__).resolve().parent.parent
    / "frontend" / "src" / "utils" / "messageKind.ts"
)


def _parse_ts_table() -> dict[str, str]:
    text = _TS.read_text(encoding="utf-8")
    start = text.index("KIND_GLYPH")
    body = text[start : text.index("};", start)]
    return dict(re.findall(r"(\w+):\s*\"([^\"]+)\"", body))


def test_web_mirror_has_the_same_kinds() -> None:
    ts = _parse_ts_table()
    assert set(ts) == {k.value for k in MessageKind}


def test_web_mirror_has_the_same_glyphs() -> None:
    ts = _parse_ts_table()
    for kind, glyph in CLI_GLYPH.items():
        assert ts[kind.value] == glyph, (
            f"{kind.value}: TypeScript renders {ts[kind.value]!r}, "
            f"ui_kinds.py says {glyph!r}"
        )


def test_web_mirror_declares_the_union_type() -> None:
    """The exported union must list exactly the five, so a typo is a type error."""
    text = _TS.read_text(encoding="utf-8")
    union = re.search(r"export type MessageKind =([^;]+);", text)
    assert union, "messageKind.ts must export a MessageKind union type"
    assert set(re.findall(r"\"(\w+)\"", union.group(1))) == {
        k.value for k in MessageKind
    }
