"""The sample board file published with the FigJam plugin.

Figma's reviewers, and anyone trying the plugin from its Community page, need a
board file without running Bristlenose, so ``figjam-plugin/publishing/
sample-board.json`` is linked from the listing. It is written by
``board_manifest`` like any real download, so it cannot fall out of step with
the format; this test fails if it does. The study and its quotes are invented.

Regenerate after a deliberate format change:

    BRISTLENOSE_REGENERATE_BOARD_FIXTURE=1 .venv/bin/python -m pytest tests/test_figjam_sample_board.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from bristlenose.board_layout import BoardStrings, Column, QuoteCard
from bristlenose.board_manifest import build_manifest, to_json
from bristlenose.board_palette import FIGJAM_TOKEN_HEX

SAMPLE = Path(__file__).resolve().parents[1] / "figjam-plugin" / "publishing" / "sample-board.json"


def _q(text: str, pid: str, start: float) -> QuoteCard:
    return QuoteCard(text=text, participant_id=pid, session_id=f"s{pid[1:]}", start_timecode=start)


# Over SPLIT_AT, so the sample shows a quote breaking into a grouped set.
_LONG = (
    "Saturday morning is the only time I get, so I open the app on the bus and look for "
    "the book my daughter wants for school. It says available, so I walk over, and when I "
    "get there the shelf is empty and the person at the desk tells me it's in the returns "
    "trolley, still to be checked in. She found it in the end. But the app said available, "
    "and I'd planned my whole morning around that one word, and now I don't really believe "
    "it when it says it any more."
)


def _sample() -> dict[str, Any]:
    columns = [
        Column("Finding a book", "section", [
            _q("I typed the title exactly and it still showed me cookbooks first.", "p1", 74.0),
            _q("The map of the shelves is the best bit. I didn't know it had that.", "p3", 412.0),
            _q("I search on my phone, but I'd never reserve on it — too fiddly.", "p4", 233.0),
        ]),
        Column("Reserving and collecting", "section", [
            _q("Ten days to collect is generous. Three would make me forget.", "p2", 958.0),
            _q("I wanted a message when it was ready, not an email I'd never open.", "p5", 1220.5),
            _q("The collection shelf is by the door, so I can be in and out.", "p1", 1504.0),
        ]),
        Column("Trust in availability", "theme", [
            _q(_LONG, "p2", 612.0),
            _q("If it says available I want it to mean on the shelf, now.", "p4", 801.0),
        ]),
        Column("Fitting it into the week", "theme", [
            _q("Late opening on Thursdays is the only reason I still come in.", "p3", 1730.0),
            _q("I renew everything on Sunday night, all at once.", "p5", 344.0),
        ]),
    ]
    return build_manifest(
        columns, "Neighbourhood library app (sample) — research board (10 quotes)",
        strings=BoardStrings(), clip_label="clip", palette=FIGJAM_TOKEN_HEX,
        locale="en", generator="Bristlenose (sample board)",
    )


def _expected() -> str:
    return to_json(_sample()) + "\n"


if os.environ.get("BRISTLENOSE_REGENERATE_BOARD_FIXTURE") == "1":
    SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    SAMPLE.write_text(_expected(), encoding="utf-8")


def test_the_sample_is_what_bristlenose_writes() -> None:
    assert SAMPLE.read_text(encoding="utf-8") == _expected(), (
        "board_manifest no longer writes figjam-plugin/publishing/sample-board.json. "
        "Regenerate it (see this file's docstring) and read the diff."
    )


def test_the_sample_shows_a_split_quote() -> None:
    doc = json.loads(SAMPLE.read_text(encoding="utf-8"))
    parts = [len(q["parts"]) for f in doc["frames"] for c in f["columns"] for q in c["quotes"]]
    assert max(parts) > 1
