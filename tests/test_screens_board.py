"""The Screens lens as a Miro board (bristlenose/screens_board.py)."""

from __future__ import annotations

import pytest

from bristlenose import screens_board as sb
from bristlenose.board_layout import MIRO_PAPER, SET_STAGGER, X_HEIGHT, quote_parts


def _overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _parts(doms: list[str], chars: int = 200) -> dict:
    return {d: quote_parts("word " * (chars // 5), "— P1 · 0:10") for d in doms}


def test_quotes_lie_beneath_the_screengrabs_a_new_row_for_each_participant() -> None:
    doms = [f"q-p1-{i}" for i in range(9)] + ["q-p2-1"]
    groups = [("p1", doms[:9]), ("p2", ["q-p2-1"])]
    w, h, stills, stickies = sb.lay_out_screen(groups, [("a.jpg", "P1 · A", (1600, 900))], _parts(doms))
    [still] = stills
    assert (still.width, still.height) == (sb.SHOT_W, pytest.approx(sb.SHOT_W * 900 / 1600))
    by = {s.dom_id: s for s in stickies}
    rects = [(s.x, s.y, s.width, s.height) for s in stickies]
    for r in rects:
        assert r[1] >= still.y + still.height  # beneath the screengrab, never over it
        assert r[0] >= 0 and r[0] + r[2] <= w + 0.01 and r[1] + r[3] <= h
    assert not any(_overlaps(a, b) for i, a in enumerate(rects) for b in rects[i + 1:])
    rows = sorted({round(s.y) for d, s in by.items() if d.startswith("q-p1")})
    assert len(rows) > 1  # p1's nine quotes wrap at the screengrab's width
    assert max(s.x + s.width for s in stickies) <= sb.FRAME_PAD + sb.SHOT_W + 0.01
    assert by["q-p2-1"].y > max(s.y for d, s in by.items() if d.startswith("q-p1"))
    assert by["q-p2-1"].x == sb.FRAME_PAD  # p2 starts a row


def test_a_split_quote_is_a_grouped_set_stepping_right_and_overlapping_by_one_amount() -> None:
    long_ = " ".join(f"Sentence {i} is about the jars and the shelf." for i in range(12))
    parts = {"q-p1-5": quote_parts(long_, "— P1 · 0:05")}
    _, _, _, stickies = sb.lay_out_screen([("p1", ["q-p1-5"])], [("a.jpg", "A", (1600, 900))], parts)
    assert len(stickies) >= 2 and len({s.set_id for s in stickies}) == 1 and stickies[0].set_id
    a, b = stickies[0], stickies[1]
    # The next part's paper covers one x-height of the paper above, which is the stagger too:
    # the notch at each left edge is a square (Miro's paper is the top 199/228 of the box).
    assert b.x - a.x == SET_STAGGER == X_HEIGHT
    assert (a.y + a.height * MIRO_PAPER) - b.y == pytest.approx(X_HEIGHT)
    assert [s.attributed for s in stickies][-1] and not stickies[0].attributed


def test_every_participants_screengrab_cascades_behind_the_front_one() -> None:
    versions = [("front.jpg", "P2 · A", (1600, 900)), ("b.jpg", "P1 · A", (1600, 1200)),
                ("c.jpg", "P3 · A", (1600, 900))]
    w, h, stills, stickies = sb.lay_out_screen([("p1", ["q-p1-1"])], versions, _parts(["q-p1-1"]))
    assert [s.filename for s in stills] == ["c.jpg", "b.jpg", "front.jpg"]  # created back first
    front, behind = stills[-1], stills[:-1]
    assert (front.x, front.y) == (sb.FRAME_PAD, sb.FRAME_PAD)
    for k, s in enumerate(reversed(behind), 1):
        assert (s.x, s.y) == (sb.FRAME_PAD + k * sb.CASCADE, sb.FRAME_PAD + k * sb.CASCADE)
    assert w >= sb.SHOT_W + 2 * sb.CASCADE + 2 * sb.FRAME_PAD
    assert stickies[0].y >= max(s.y + s.height for s in stills)  # under the deepest screengrab
    assert [s.title for s in stills] == ["P3 · A", "P1 · A", "P2 · A"]


def test_frames_run_left_to_right_and_a_screen_with_no_still_is_left_out() -> None:
    def screen(t: str, n: int, codes: list[str]) -> dict:
        return {"title": t, "groups": [],
                "versions": [{"filename": f"screen-{n:02d}-{c}.jpg", "code": c} for c in codes]}
    screens = [screen("Home", 1, ["p1"]), screen("Basket", 2, ["p1"]), screen("Checkout", 3, ["p2", "p1"])]
    px = {"screen-01-p1.jpg": (1600, 900), "screen-03-p1.jpg": (1600, 900)}  # p2's checkout failed
    frames = sb.lay_out_board(screens, px, {})
    assert [f.title for f in frames] == ["Home", "Checkout"]
    assert [s.title for s in frames[1].stills] == ["P1 · Checkout"]
    assert frames[0].y == frames[1].y == 0
    assert frames[1].x == frames[0].x + frames[0].width + sb.FRAME_GAP


def test_only_quotes_the_board_can_write_get_a_sticky() -> None:
    _, _, _, stickies = sb.lay_out_screen([("p1", ["q-p1-10", "q-p1-20"])], [("a.jpg", "A", (1600, 900))],
                                          _parts(["q-p1-20"]))
    assert [s.dom_id for s in stickies] == ["q-p1-20"]


def test_jpeg_size_reads_the_frame_header() -> None:
    sof = b"\xff\xc0\x00\x11\x08" + (180).to_bytes(2, "big") + (320).to_bytes(2, "big") + b"\x03" + b"\x00" * 9
    assert sb.jpeg_size(b"\xff\xd8" + b"\xff\xe0\x00\x04ab" + sof) == (320, 180)
    assert sb.jpeg_size(b"not a jpeg") is None
