"""The Screens lens as a Miro board (bristlenose/screens_board.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bristlenose import screens_board as sb

_CONTRACT = json.loads((Path(__file__).parent / "fixtures" / "screens-layout-contract.json").read_text())


@pytest.mark.parametrize("c", _CONTRACT["edgeFor"])
def test_edge_for_matches_the_lens(c: dict) -> None:
    assert sb.edge_for(c["box"], c["mode"]) == c["edge"]


@pytest.mark.parametrize("c", _CONTRACT["placeColumn"])
def test_place_column_matches_the_lens(c: dict) -> None:
    tops, stacked = sb.place_column([tuple(x) for x in c["cards"]], c["limit"])
    assert tops == pytest.approx(c["tops"]) and stacked == c["stacked"]


@pytest.mark.parametrize("c", _CONTRACT["placeRow"])
def test_place_row_matches_the_lens(c: dict) -> None:
    assert sb.place_row([tuple(x) for x in c["cards"]], c["limit"]) == (c["lefts"], c["tops"], c["height"])


@pytest.mark.parametrize("c", _CONTRACT["rectFromIntent"])
def test_rect_from_intent_matches_the_lens(c: dict) -> None:
    left, top = sb.rect_from_intent(c["intent"], tuple(c["shot"]), c["cardW"], c["height"])
    assert (left, top) == pytest.approx((c["left"], c["top"]))


def _shot(sid: str, code: str, key: str, pins: list[tuple[str, list[float]]], loose: list[str], n: int) -> dict:
    return {"session_id": sid, "code": code, "screen_key": key, "title": key.strip("/").title(),
            "filename": f"{code}-{n:02d}.jpg",
            "pins": [{"dom_id": d, "box": b} for d, b in pins], "loose": loose}


def _overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def test_a_frame_holds_its_still_and_quotes_round_it_never_over_it() -> None:
    shot = _shot("s1", "p1", "/basket", [("q-p1-10", [0.05, 0.4, 0.2, 0.03]), ("q-p1-20", [0.7, 0.6, 0.2, 0.03]),
                                         ("q-p1-30", [0.4, 0.05, 0.2, 0.03])], ["q-p1-40", "q-p1-50"], 1)
    w, h, still, stickies = sb.lay_out_shot(shot, (1600, 900))
    assert still[2] == sb.SHOT_W and still[3] == pytest.approx(sb.SHOT_W * 900 / 1600)
    by = {s.dom_id: s for s in stickies}
    assert set(by) == {"q-p1-10", "q-p1-20", "q-p1-30", "q-p1-40", "q-p1-50"}
    rects = {d: (s.x, s.y, sb.STICKY_W, sb.STICKY_H) for d, s in by.items()}
    for d, r in rects.items():
        assert not _overlaps(r, still), d
        assert r[0] >= 0 and r[1] >= 0 and r[0] + r[2] <= w and r[1] + r[3] <= h, d
    assert rects["q-p1-10"][0] + sb.STICKY_W <= still[0]  # left half of the page: left column
    assert rects["q-p1-20"][0] >= still[0] + still[2]  # right half: right column
    assert rects["q-p1-30"][1] + sb.STICKY_H <= still[1]  # top band
    assert min(rects["q-p1-40"][1], rects["q-p1-50"][1]) >= still[1] + still[3]  # the rest, beneath
    assert not any(_overlaps(a, b) for i, a in enumerate(rects.values()) for b in list(rects.values())[i + 1:])


def test_the_researchers_arrangement_wins_over_the_automatic_one() -> None:
    shot = _shot("s1", "p1", "/basket", [("q-p1-10", [0.05, 0.4, 0.2, 0.03])], ["q-p1-40"], 1)
    arrangement = {"q-p1-10": {"kind": "over", "x": 0.5, "y": 0.5, "z": 4},
                   "q-p1-40": {"kind": "edge", "edge": "R", "along": 0.0, "out": 40, "z": 2}}
    _, _, still, stickies = sb.lay_out_shot(shot, (1600, 900), arrangement)
    by = {s.dom_id: s for s in stickies}
    assert (by["q-p1-10"].x, by["q-p1-10"].y) == pytest.approx((still[0] + 0.5 * still[2], still[1] + 0.5 * still[3]))
    assert by["q-p1-40"].x == pytest.approx(still[0] + still[2] + 40)
    assert [s.dom_id for s in stickies][-1] == "q-p1-10"  # the higher card is drawn last


def test_a_row_per_participant_in_shot_order_and_stills_that_failed_are_left_out() -> None:
    shots = [_shot("s1", "p1", "/home", [], [], 1), _shot("s1", "p1", "/basket", [], [], 2),
             _shot("s2", "p2", "/home", [], [], 1), _shot("s2", "p2", "/basket", [], [], 2)]
    px = {"p1-01.jpg": (1600, 900), "p1-02.jpg": (1600, 900), "p2-01.jpg": (1600, 900)}
    frames = sb.lay_out_board(shots, px)
    assert [f.title for f in frames] == ["P1 · Home", "P1 · Basket", "P2 · Home"]
    assert frames[0].y == frames[1].y < frames[2].y
    assert frames[1].x == frames[0].x + frames[0].width + sb.FRAME_GAP
    assert frames[2].x == 0


def test_only_quotes_the_board_can_write_get_a_sticky() -> None:
    shot = _shot("s1", "p1", "/a", [("q-p1-10", [0.1, 0.4, 0.1, 0.02])], ["q-p1-20"], 1)
    _, _, _, stickies = sb.lay_out_shot(shot, (1600, 900), known={"q-p1-20"})
    assert [s.dom_id for s in stickies] == ["q-p1-20"]
