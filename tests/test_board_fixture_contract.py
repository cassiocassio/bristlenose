"""Python side of the FigJam board contract.

`tests/fixtures/figjam-board-v1.json` is a board document written by
`board_manifest`, from the fixed input below. The FigJam plugin's tests
(`figjam-plugin/src/plan.test.ts`) read the same file, so if Bristlenose and the
plugin drift — either side — one of the two suites fails with the case named.
Same pattern as `shared-format-contract.json`.

`figjam-board-v1-additive.json` is the same board with keys a version-1 plugin
has never seen, at every level, and a higher `version`. The plugin must draw it
exactly as it draws the plain file: that is what lets Bristlenose add optional
keys without waiting on a plugin review.

The fixtures are generated, never hand-edited. When the document changes on
purpose, regenerate and read the diff:

    BRISTLENOSE_REGENERATE_BOARD_FIXTURE=1 .venv/bin/python -m pytest tests/test_board_fixture_contract.py
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from bristlenose.board_layout import BoardStrings, Column, QuoteCard
from bristlenose.board_manifest import build_manifest, to_json
from bristlenose.board_palette import FIGJAM_TOKEN_HEX

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
PLAIN = _FIXTURES / "figjam-board-v1.json"
ADDITIVE = _FIXTURES / "figjam-board-v1-additive.json"


def _card(text: str, pid: str, session: str, start: float, link: str | None = None) -> QuoteCard:
    return QuoteCard(text=text, participant_id=pid, session_id=session,
                     start_timecode=start, link_url=link)


def _board() -> dict[str, Any]:
    """Every case the plugin has to get right, in one small board."""
    columns = [
        Column("Checkout", "section", [
            _card("I couldn't find the pay button.", "p1", "s1", 42.0,
                  "https://clips.example/study/s1-p1-42.mp4"),
            _card('She said "no" — then C:\\Users\\jane </script> and left', "p2", "s2", 3725.5),
            _card("Line\u2028separator, and an emoji 👩🏽‍💻🎉 mid-quote", "p3", "s10", 9.0),
        ]),
        Column("Delivery & returns", "section", [
            _card("كانت الصفحة مربكة جدًا ولم أجد زر الدفع", "p4", "s3", 192.0),
            _card("駅の券売機で往復を選んだつもりが片道になっていて𠮷", "p5", "s4", 3723.0),
        ]),
        Column("Trust", "theme", [
            _card("Is this site even safe?", "p1", "s1", 600.0),
        ]),
    ]
    return build_manifest(
        columns, "Fixture study — research board (6 quotes)",
        strings=BoardStrings(), clip_label="clip", palette=FIGJAM_TOKEN_HEX,
        locale="en", generator="Bristlenose (fixture)", requested=7,
    )


def _additive(plain: dict[str, Any]) -> dict[str, Any]:
    doc = copy.deepcopy(plain)
    doc["version"] = plain["version"] + 1  # a newer writer …
    doc["min_reader_version"] = plain["min_reader_version"]  # … still drawable by v1
    doc["future_top"] = {"anything": [1, 2, 3]}
    doc["frames"][0]["future_frame"] = True
    doc["frames"][0]["columns"][0]["future_column"] = "x"
    doc["frames"][0]["columns"][0]["quotes"][0]["future_quote"] = None
    return doc


def _expected(doc: dict[str, Any]) -> str:
    return to_json(doc) + "\n"


def _regenerate() -> None:
    plain = _board()
    PLAIN.write_text(_expected(plain), encoding="utf-8")
    ADDITIVE.write_text(_expected(_additive(plain)), encoding="utf-8")


if os.environ.get("BRISTLENOSE_REGENERATE_BOARD_FIXTURE") == "1":
    _regenerate()


def test_the_fixture_is_what_bristlenose_writes():
    assert PLAIN.read_text(encoding="utf-8") == _expected(_board()), (
        "board_manifest no longer writes tests/fixtures/figjam-board-v1.json. If the "
        "change is deliberate, regenerate (see this file's docstring), read the diff, "
        "and check the plugin still reads it — a renamed or retyped key needs a "
        "version bump."
    )


def test_the_additive_fixture_is_the_plain_one_plus_unknown_keys():
    plain = json.loads(PLAIN.read_text(encoding="utf-8"))
    assert json.loads(ADDITIVE.read_text(encoding="utf-8")) == _additive(plain)


def test_the_fixture_exercises_what_it_claims_to():
    """Guard against a regeneration that quietly loses a case."""
    doc = json.loads(PLAIN.read_text(encoding="utf-8"))
    quotes = [q for f in doc["frames"] for c in f["columns"] for q in c["quotes"]]
    texts = "".join(q["text"] for q in quotes)
    assert [f["kind"] for f in doc["frames"]] == ["section", "theme"]
    assert any(q["clip_url"] for q in quotes) and any(q["clip_url"] is None for q in quotes)
    for needle in ("</script>", "\\", '"', "\u2028", "👩🏽‍💻", "𠮷", "كانت"):
        assert needle in texts, needle
    assert doc["totals"] == {"frames": 2, "columns": 3, "quotes": 6}
    assert doc["requested"] == 7
    # Ordered by session number, then time: s2 before s10.
    assert [q["attribution"] for q in doc["frames"][0]["columns"][0]["quotes"]] == [
        "— P1 · 00:42", "— P2 · 1:02:05", "— P3 · 00:09"]
