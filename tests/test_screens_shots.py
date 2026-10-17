"""The shot list: one still per participant per screen, in time order (screen_text/shots.py)."""

from __future__ import annotations

from typing import Any

from bristlenose.screen_text.shots import code_order, shot_list, title_of


def _tab(sid: str, code: str, t: float, visits: list[list[float]], pins: list[str] = (),
         loose: list[str] = ()) -> dict[str, Any]:
    return {"session_id": sid, "code": code, "t": t, "crop": [0, 0.1, 1, 1], "heading": "",
            "visits": visits, "pins": [{"dom_id": d, "box": [0, 0, 0.1, 0.1], "phrase": "", "line": ""}
                                       for d in pins], "loose": list(loose)}


def _screen(key: str, *tabs: dict[str, Any]) -> dict[str, Any]:
    return {"key": key, "name": key, "tabs": list(tabs), "default_tab": 0, "quotes": 0}


def test_participants_in_code_order_and_each_in_visit_order() -> None:
    screens = [  # the lens's order: most-said-about first, not time
        _screen("/basket", _tab("s10", "p10", 50, [[40, 60]]), _tab("s2", "p2", 300, [[290, 310]])),
        _screen("/home", _tab("s2", "p2", 5, [[0, 20], [400, 420]]), _tab("s10", "p10", 9, [[0, 30]])),
    ]
    shots = shot_list(screens, {})
    assert [(s["code"], s["screen_key"], s["filename"]) for s in shots] == [
        ("p2", "/home", "p2-01.jpg"), ("p2", "/basket", "p2-02.jpg"),
        ("p10", "/home", "p10-01.jpg"), ("p10", "/basket", "p10-02.jpg"),
    ]


def test_a_still_carries_only_its_own_participants_visible_quotes() -> None:
    tab = _tab("s1", "p1", 5, [[0, 10]], pins=["q-p1-3", "q-p2-7", "q-p1-4"], loose=["q-p1-8", "q-p1-9"])
    owner = {"q-p1-3": "s1", "q-p1-4": "s1", "q-p1-8": "s1", "q-p1-9": "s1", "q-p2-7": "s2"}
    [shot] = shot_list([_screen("/a", tab)], owner, hidden={"q-p1-4", "q-p1-9"})
    assert [p["dom_id"] for p in shot["pins"]] == ["q-p1-3"]  # p2's cross-link is on p2's still
    assert shot["loose"] == ["q-p1-8"]


def test_numbers_widen_past_99_and_a_shared_code_keeps_files_apart() -> None:
    many = [_screen(f"/{i}", _tab("s1", "p1", i, [[i, i + 1]])) for i in range(120)]
    names = [s["filename"] for s in shot_list(many, {})]
    assert names[0] == "p1-001.jpg" and names[-1] == "p1-120.jpg"
    shared = [_screen("/a", _tab("s1", "p1", 1, [[0, 2]]), _tab("s9", "p1", 1, [[0, 2]]))]
    assert sorted(s["filename"] for s in shot_list(shared, {})) == ["p1-s1-01.jpg", "p1-s9-01.jpg"]


def test_code_order_is_natural() -> None:
    assert sorted(["p10", "p2", "p1", "m1"], key=code_order) == ["m1", "p1", "p2", "p10"]


def test_a_still_is_titled_as_the_lens_titles_it() -> None:
    assert title_of({"name": "/cat/15950"}, {"heading": "Jars & tins"}) == "Jars & tins"
    assert title_of({"name": "/cat/15950"}, {"heading": ""}) == "/cat/15950"
    assert title_of({"name": "shopping bag"}, {"heading": "Ignored"}) == "Shopping bag"
