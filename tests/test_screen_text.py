"""Screen text: the index and the screens derived from it (bristlenose/screen_text/).

Synthetic indexes and a fake engine, so this runs anywhere; one test builds a real index from a
tiny generated video through ffmpeg and skips where there is none.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from bristlenose.screen_text import index as sti
from bristlenose.screen_text.engine import FakeEngine, Frame, VisionEngine
from bristlenose.screen_text.screens import (
    SessionInput,
    content_crop,
    derive_screens,
    id_key,
    match,
    url_norm,
    visits_of,
)

# One marker, as test_format_ingest_coverage.py does: CI's Linux cells install ffmpeg, so these run
# there; a cell without it skips them all, for the one reason.
_needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                                   reason="needs ffmpeg")

# ── Keys ─────────────────────────────────────────────────────────────────


def test_the_same_page_in_two_locales_has_one_key() -> None:
    assert id_key("/gb/en/shoppingcart", "") == id_key("/de/de/shoppingcart", "") == "/shoppingcart"
    assert id_key("/gb/en", "") == id_key("/de/de", "") == "/"


def test_different_categories_and_products_keep_different_keys() -> None:
    # The template key (/cat/*) stacked these; the ID at the end of the slug tells them apart.
    assert id_key("/gb/en/cat/jars-tins-15950", "") == "/cat/15950"
    assert id_key("/de/de/cat/aufbewahrungsmoebel-organisation-st001", "") == "/cat/st001"
    assert id_key("/gb/en/p/korken-jar-50213546", "") != id_key("/de/de/p/besta-s69612088", "")


def test_the_same_product_in_two_locales_has_one_key() -> None:
    assert id_key("/gb/en/p/korken-jar-with-lid-50213546", "") == id_key("/de/de/p/korken-glas-50213546", "")


def test_an_address_is_read_and_a_sentence_is_not() -> None:
    u = url_norm("ikea.com/gb/en/shoppingcart/")
    assert u is not None and u["host"] == "ikea.com" and u["path"] == "/gb/en/shoppingcart"
    assert url_norm("Continue to checkout") is None
    assert url_norm("www.example.co.uk/basket?x=1#top") == {"host": "example.co.uk", "path": "/basket", "frag": "top"}


def test_fold_matches_search_folding() -> None:
    assert sti.fold("Größe & Straße – Café") == "grosse & strasse cafe"


# ── Index ────────────────────────────────────────────────────────────────


def _ln(text: str, x: float, y: float, w: float = 0.2, h: float = 0.02, conf: float = 0.9) -> dict:
    return {"text": text, "conf": conf, "box": [x, y, w, h]}


def _frames(times: list[float]) -> list[Frame]:
    return [Frame(width=4, height=2, bgra=b"\0" * 32, t=t) for t in times]


def test_episodes_bridge_one_missing_sample_and_split_on_a_longer_gap() -> None:
    seen = {0: True, 4: False, 8: True, 12: False, 16: False, 20: False, 24: True}
    eng = FakeEngine(lambda t: [_ln("Hello world", 0.1, 0.5)] if seen[int(t)] else [])
    rec = sti.index_frames(iter(_frames([float(t) for t in seen])), eng)
    [ep] = rec["episodes"]
    assert ep["runs"] == [[0.0, 8.0], [24.0, 24.0]]


def test_a_line_that_moves_is_a_new_episode_at_its_new_place() -> None:
    # The page scrolled: positions are per moment, so "where" must follow the line.
    eng = FakeEngine(lambda t: [_ln("Delivery costs", 0.1, 0.6 if t < 8 else 0.3)])
    rec = sti.index_frames(iter(_frames([0.0, 4.0, 8.0, 12.0])), eng)
    boxes = sorted(e["box"][1] for e in rec["episodes"])
    assert boxes == [0.3, 0.6]


def test_lines_on_most_dense_frames_are_sticky() -> None:
    # Sticky lines are chrome and are not stored (tests/test_screens_at_rest.py), except an address,
    # which keys the screen: so the flag is seen on the address, and the name is simply gone.
    def lines(t: float) -> list[dict]:
        page = [_ln(f"line {int(t)} {i}", 0.1, 0.1 + i * 0.02) for i in range(30)]
        return page + [_ln("Martin Storey", 0.9, 0.2), _ln("ikea.com/gb/en/planner", 0.2, 0.03)]
    rec = sti.index_frames(iter(_frames([0.0, 4.0, 8.0])), FakeEngine(lines))
    sticky = {e["text"] for e in rec["episodes"] if e["sticky"]}
    assert sticky == {"ikea.com/gb/en/planner"}
    assert "Martin Storey" not in {e["text"] for e in rec["episodes"]}
    assert len(rec["episodes"]) == 3 * 30 + 1


def test_low_confidence_lines_are_dropped() -> None:
    eng = FakeEngine(lambda t: [_ln("blurry", 0.1, 0.1, conf=0.2), _ln("clear", 0.1, 0.3)])
    rec = sti.index_frames(iter(_frames([0.0])), eng)
    assert [e["text"] for e in rec["episodes"]] == ["clear"]


def test_moments_are_where_the_screen_text_changes() -> None:
    def lines(t: float) -> list[dict]:
        return [_ln("page one", 0.1, 0.3)] if t < 8 else [_ln("page two", 0.1, 0.3)]
    rec = sti.index_frames(iter(_frames([0.0, 4.0, 8.0, 12.0])), FakeEngine(lines))
    assert rec["moments"] == [0.0, 8.0]


def test_the_vision_engine_explains_itself_where_it_cannot_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("platform.system", lambda: "Linux")
    assert VisionEngine().available() == "not_macos"


@_needs_ffmpeg
def test_a_real_recording_is_sampled_and_indexed(tmp_path: Path) -> None:
    video = tmp_path / "share.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc=size=320x180:rate=10:duration=13", "-pix_fmt", "yuv420p", str(video)], check=True)
    times: list[float] = []

    def lines(t: float) -> list[dict]:
        times.append(t)
        return [_ln("Checkout", 0.1, 0.3)]
    out = tmp_path / "s1.json"
    eng = FakeEngine(lines)
    assert sti.build_index(video, eng, out)
    rec = json.loads(out.read_text())
    # ffmpeg's fps filter gives 0, 4, 8 for 13 s (it drops the last part-interval): exactly three,
    # so a decode that stopped early cannot pass.
    assert rec["size"] == [320, 180] and rec["samples"] == len(times) == 3
    assert rec["raw_lines"] == 3
    assert times == sorted(times) and times[0] < 1.0  # real times from showinfo, in order
    assert sti.is_current(out, video, eng)
    calls = len(times)
    assert sti.build_index(video, eng, out) and len(times) == calls  # cached: not read again


@_needs_ffmpeg
def test_a_stopped_pass_writes_nothing(tmp_path: Path) -> None:
    video = tmp_path / "share.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc=size=160x90:rate=5:duration=20", "-pix_fmt", "yuv420p", str(video)], check=True)
    n = 0

    def stop() -> bool:
        nonlocal n
        n += 1
        return n > 2
    out = tmp_path / "s1.json"
    assert not sti.build_index(video, FakeEngine(lambda t: []), out, should_stop=stop)
    assert not out.exists()


@_needs_ffmpeg
def test_a_cut_off_recording_is_an_error_not_a_short_index(tmp_path: Path) -> None:
    video = tmp_path / "share.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc=size=160x90:rate=5:duration=40", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", str(video)], check=True)  # header first, as a cut file keeps it
    data = video.read_bytes()
    video.write_bytes(data[: len(data) // 3])  # the header still says 40 s
    out = tmp_path / "s1.json"
    with pytest.raises(RuntimeError, match="decoded only|ffmpeg exited"):
        sti.build_index(video, FakeEngine(lambda t: []), out)
    assert not out.exists()


@_needs_ffmpeg
def test_a_recording_with_no_picture_says_so(tmp_path: Path) -> None:
    audio = tmp_path / "call.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "sine=duration=3",
                    "-c:a", "aac", str(audio)], check=True)
    with pytest.raises(ValueError, match="no video stream"):
        sti.build_index(audio, FakeEngine(lambda t: []), tmp_path / "s1.json")


@_needs_ffmpeg
def test_a_video_track_that_starts_late_keeps_frames_and_times_in_step(tmp_path: Path) -> None:
    video = tmp_path / "share.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error",
                    "-f", "lavfi", "-i", "sine=duration=14",
                    "-itsoffset", "2.3", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=5:duration=11",
                    "-map", "0:a", "-map", "1:v", "-c:a", "aac", "-pix_fmt", "yuv420p", str(video)], check=True)
    times: list[float] = []
    out = tmp_path / "s1.json"
    assert sti.build_index(video, FakeEngine(lambda t: times.append(t) or []), out)
    assert times == sorted(times) and len(times) == json.loads(out.read_text())["samples"] >= 2
    assert times[0] >= 2.0  # the first frame is where the picture starts, not a duplicate at 0


def test_an_index_missing_its_parts_is_not_read(tmp_path: Path) -> None:
    path = tmp_path / "s1.json"
    path.write_text(json.dumps({"version": sti.INDEX_VERSION, "key": "k", "samples": 1, "moments": []}))
    assert sti.read_index(path) is None


# ── Screens ──────────────────────────────────────────────────────────────


def _episode(text: str, box: list[float], runs: list[list[float]], sticky: bool = False) -> dict:
    return {"text": text, "box": box, "sticky": sticky, "runs": runs}


def _session(prefix: str, pages: list[tuple[str, list[dict], float, float]]) -> dict:
    """An index: an address bar showing each page's path for its span, plus each page's lines."""
    eps = []
    for path, lines, t0, t1 in pages:
        eps.append(_episode(f"ikea.com{prefix}{path}", [0.2, 0.05, 0.4, 0.02], [[t0, t1]]))
        for ln in lines:
            eps.append(_episode(ln["text"], ln["box"], [[t0, t1]]))
    filler = [_episode(f"filler {i}", [0.1, 0.3 + i * 0.05, 0.6, 0.02], [[0, 1000]]) for i in range(10)]
    return {"version": 1, "every": 4.0, "episodes": eps + filler, "moments": []}


def test_two_locales_of_one_page_are_one_screen_and_different_categories_are_not() -> None:
    uk = _session("/gb/en", [("/shoppingcart", [_ln("Shopping Bag", 0.1, 0.2, 0.3, 0.05)], 0, 40),
                             ("/cat/jars-tins-15950", [_ln("Jars & tins", 0.1, 0.2)], 44, 80)])
    de = _session("/de/de", [("/shoppingcart", [_ln("Warenkorb", 0.1, 0.2, 0.3, 0.05)], 0, 40),
                             ("/cat/aufbewahrung-st001", [_ln("Aufbewahrung", 0.1, 0.2)], 44, 80)])
    screens = derive_screens([SessionInput("s1", "p1", uk, []), SessionInput("s2", "p2", de, [])])
    by = {s["name"]: s for s in screens}
    assert {t["code"] for t in by["/shoppingcart"]["tabs"]} == {"p1", "p2"}
    assert {t["code"] for t in by["/cat/15950"]["tabs"]} == {"p1"}
    assert {t["code"] for t in by["/cat/st001"]["tabs"]} == {"p2"}


def test_a_quote_is_placed_by_time_and_pinned_to_the_line_it_reads() -> None:
    uk = _session("/gb/en", [("/shoppingcart", [_ln("Continue to checkout", 0.5, 0.6, 0.3, 0.04),
                                                 _ln("Shopping Bag", 0.1, 0.2, 0.3, 0.05)], 0, 60)])
    quotes = [
        {"dom_id": "q-p1-10", "start": 10, "end": 18, "text": "so I click continue to checkout, I think"},
        {"dom_id": "q-p1-30", "start": 30, "end": 34, "text": "this is quite expensive really"},
        {"dom_id": "q-p1-200", "start": 200, "end": 210, "text": "after the session, nothing on screen"},
    ]
    [screen] = derive_screens([SessionInput("s1", "p1", uk, quotes)])
    [tab] = screen["tabs"]
    assert [p["dom_id"] for p in tab["pins"]] == ["q-p1-10"]
    assert tab["pins"][0]["phrase"] == "continue to checkout"
    assert tab["loose"] == ["q-p1-30"]  # placed on the screen, pinned to nothing
    # Boxes are in the crop's coordinates, so the client can draw them on the cropped still.
    x0, y0, x1, y1 = tab["crop"]
    bx = tab["pins"][0]["box"]
    assert abs(bx[0] - (0.5 - x0) / (x1 - x0)) < 1e-3 and abs(bx[1] - (0.6 - y0) / (y1 - y0)) < 1e-3


def test_furniture_is_never_a_pin_target() -> None:
    nav = _ln("Products Rooms Offers", 0.1, 0.12, 0.5, 0.02)
    pages = [(f"/page-{i}00{i}", [_ln(f"Page {i}", 0.1, 0.2 + i * 0.01), nav], i * 20, i * 20 + 16)
             for i in range(5)]
    idx = _session("/gb/en", pages)
    q = {"dom_id": "q-p1-2", "start": 2, "end": 6, "text": "I look at products rooms offers up there"}
    screens = derive_screens([SessionInput("s1", "p1", idx, [q])])
    assert all(not t["pins"] for s in screens for t in s["tabs"])


def test_match_needs_a_content_word_or_a_rare_long_word() -> None:
    lines = [_ln("Go to the shop", 0.1, 0.1), _ln("Lieferverfügbarkeit", 0.1, 0.3)]
    assert match("I want to go to the shop now", lines, set()) == ("go to the shop", lines[0])
    assert match("it is to the", lines, set()) is None
    assert match("die lieferverfugbarkeit ist", lines, {"lieferverfugbarkeit"})[0] == "lieferverfugbarkeit"


def test_safari_with_no_path_is_keyed_by_tab_title() -> None:
    eps = [_episode("ikea.com", [0.4, 0.05, 0.1, 0.02], [[0, 100]])]
    for i, (title, t0, t1) in enumerate([("Shopping bag - IKEA", 0, 40), ("Delivery - IKEA", 44, 80)]):
        eps.append(_episode(title, [0.05 + i * 0.3, 0.02, 0.25, 0.02], [[t0, t1]]))
    visits = visits_of({"every": 4.0, "episodes": eps})
    assert [v.key for v in visits] == ["title:shopping bag", "title:delivery"]


def test_the_crop_leaves_out_the_browser_and_the_call_tiles() -> None:
    eps = [_episode("ikea.com/gb/en/shoppingcart", [0.2, 0.05, 0.4, 0.02], [[0, 10]])]
    eps += [_episode(f"page line {i}", [0.05, 0.2 + i * 0.05, 0.6, 0.02], [[0, 10]]) for i in range(12)]
    eps += [_episode("Martin Storey", [0.9, 0.3, 0.08, 0.02], [[0, 10]], sticky=True)]
    x0, y0, x1, y1 = content_crop({"every": 4.0, "episodes": eps})
    assert y0 > 0.07 and x1 < 0.9 and x0 < 0.05


def test_the_still_is_a_moment_the_page_is_drawn_not_a_loading_frame() -> None:
    # A line the quote reads is on screen only while the page loads (0–16 s); the page is drawn
    # from 20 s. Measured on a real planner page: the loading frame won on pins and the board
    # showed a pin over a blank screengrab. A drawn page with the quote unpinned is the better
    # still: the quote is still on the screen, under it.
    eps = [_episode("ikea.com/gb/en/planner", [0.2, 0.05, 0.4, 0.02], [[0, 60]]),
           _episode("Personalise your wardrobe", [0.3, 0.4, 0.3, 0.04], [[0, 16]])]
    eps += [_episode(f"planner control {i}", [0.05, 0.2 + i * 0.05, 0.4, 0.02], [[20, 60]]) for i in range(12)]
    q = {"dom_id": "q-p1-5", "start": 5, "end": 9, "text": "I can personalise your wardrobe here"}
    [screen] = derive_screens([SessionInput("s1", "p1", {"every": 4.0, "episodes": eps}, [q])])
    [tab] = screen["tabs"]
    assert tab["t"] >= 20
    assert tab["pins"] == [] and tab["loose"] == ["q-p1-5"]


def test_each_version_links_every_participants_quote_and_the_default_is_the_best_linked() -> None:
    """A screen is one place: p2's still links p1's quote when its words are on it, and the
    version that links the most is shown first."""
    from bristlenose.screen_text.screens import SessionInput, derive_screens

    def ln(text: str, x: float, y: float, w: float = 0.3, h: float = 0.04) -> dict:
        return {"text": text, "box": [x, y, w, h], "sticky": False, "runs": [[0, 60]]}

    def index(extra: list[dict]) -> dict:
        eps = [ln("ikea.com/gb/en/shoppingcart", 0.2, 0.05, 0.4, 0.02), ln("Shopping Bag", 0.1, 0.2)]
        eps += [{"text": f"filler {i}", "box": [0.1, 0.3 + i * 0.05, 0.6, 0.02], "sticky": False,
                 "runs": [[0, 1000]]} for i in range(10)]
        return {"every": 4.0, "episodes": eps + extra, "moments": []}

    p1 = SessionInput("s1", "p1", index([]),
                      [{"dom_id": "q-p1-10", "start": 10, "end": 18, "text": "where is continue to checkout"}])
    p2 = SessionInput("s2", "p2", index([ln("Continue to checkout", 0.5, 0.6)]),
                      [{"dom_id": "q-p2-20", "start": 20, "end": 24, "text": "nice colours"}])
    [screen] = derive_screens([p1, p2])
    tabs = {t["code"]: t for t in screen["tabs"]}
    assert [p["dom_id"] for p in tabs["p2"]["pins"]] == ["q-p1-10"]
    assert tabs["p1"]["pins"] == []
    assert screen["tabs"][screen["default_tab"]]["code"] == "p2"
    assert screen["quotes"] == 2
