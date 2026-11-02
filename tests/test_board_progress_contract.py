"""The board build's status is read by three clients: pin its fields across all of them.

`BoardProgress.snapshot()` is served as `BoardBuild` (`routes/miro.py`), decoded by the Mac sheet as
`MiroBoardBuild` (Swift) and by the web panel as `MiroBoardBuild` (TypeScript). A field renamed on
one side would decode as missing on another — silently, as a bar that never fills — so the names
are asserted equal from the source of each.
"""

from __future__ import annotations

import re
from pathlib import Path

from bristlenose.board_progress import BoardProgress
from bristlenose.server.routes.miro import BoardBuild

_ROOT = Path(__file__).resolve().parent.parent


def _swift_fields() -> set[str]:
    text = (_ROOT / "desktop/Bristlenose/Bristlenose/MiroBoardBuild.swift").read_text(encoding="utf-8")
    body = text.split("struct MiroBoardBuild", 1)[1].split("}", 1)[0]
    return set(re.findall(r"^\s*let (\w+):", body, re.M))


def _ts_fields() -> set[str]:
    text = (_ROOT / "frontend/src/utils/types.ts").read_text(encoding="utf-8")
    body = text.split("export interface MiroBoardBuild {", 1)[1].split("}", 1)[0]
    return set(re.findall(r"^\s*(\w+):", body, re.M))


def test_the_snapshot_the_route_and_both_clients_name_the_same_fields() -> None:
    served = set(BoardProgress("quotes").snapshot())
    assert served == set(BoardBuild.model_fields)
    assert _swift_fields() == served
    assert _ts_fields() == served
