"""The Screens lens as a Miro board (bristlenose/screens_board.py)."""

from __future__ import annotations

import pytest

from bristlenose import screens_board as sb
from bristlenose.board_layout import RECT_ASPECT


def _overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def test_quotes_stack_beneath_the_still_a_new_row_for_each_participant() -> None:
    groups = [("p1", [f"q-p1-{i}" for i in range(5)]), ("p2", ["q-p2-1"])]
    w, h, still, stickies = sb.lay_out_screen(groups, (1600, 900))
    assert still[2] == sb.SHOT_W and still[3] == pytest.approx(sb.SHOT_W * 900 / 1600)
    by = {s.dom_id: s for s in stickies}
    assert [s.dom_id for s in stickies] == [f"q-p1-{i}" for i in range(5)] + ["q-p2-1"]
    rects = [(s.x, s.y, sb.STICKY_W, sb.STICKY_H) for s in stickies]
    for r in rects:
        assert r[1] >= still[1] + still[3]  # beneath the still, never over it
        assert r[0] >= 0 and r[0] + r[2] <= w + 0.01 and r[1] + r[3] <= h
    assert not any(_overlaps(a, b) for i, a in enumerate(rects) for b in rects[i + 1:])
    assert by["q-p1-4"].y > by["q-p1-3"].y and by["q-p1-4"].x == by["q-p1-0"].x  # four to a row
    assert by["q-p2-1"].y > by["q-p1-4"].y and by["q-p2-1"].x == by["q-p1-0"].x  # p2 starts a row


def test_the_stickies_are_the_house_rectangle_and_four_span_the_still() -> None:
    assert sb.STICKY_H == pytest.approx(sb.STICKY_W * RECT_ASPECT)
    assert sb.PER_ROW * sb.STICKY_W + (sb.PER_ROW - 1) * sb.GAP == pytest.approx(sb.SHOT_W)


def test_frames_run_left_to_right_and_a_still_that_failed_is_left_out() -> None:
    screens = [{"title": t, "filename": f, "groups": []}
               for t, f in [("Home", "screen-01.jpg"), ("Basket", "screen-02.jpg"), ("Checkout", "screen-03.jpg")]]
    frames = sb.lay_out_board(screens, {"screen-01.jpg": (1600, 900), "screen-03.jpg": (1600, 900)})
    assert [f.title for f in frames] == ["Home", "Checkout"]
    assert frames[0].y == frames[1].y == 0
    assert frames[1].x == frames[0].x + frames[0].width + sb.FRAME_GAP


def test_only_quotes_the_board_can_write_get_a_sticky() -> None:
    _, _, _, stickies = sb.lay_out_screen([("p1", ["q-p1-10", "q-p1-20"])], (1600, 900), known={"q-p1-20"})
    assert [s.dom_id for s in stickies] == ["q-p1-20"]


def test_jpeg_size_reads_the_frame_header() -> None:
    sof = b"\xff\xc0\x00\x11\x08" + (180).to_bytes(2, "big") + (320).to_bytes(2, "big") + b"\x03" + b"\x00" * 9
    assert sb.jpeg_size(b"\xff\xd8" + b"\xff\xe0\x00\x04ab" + sof) == (320, 180)
    assert sb.jpeg_size(b"not a jpeg") is None
