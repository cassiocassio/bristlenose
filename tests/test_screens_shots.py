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


def test_the_board_pools_each_screen_in_journey_order_grouped_by_participant() -> None:
    from bristlenose.screen_text.shots import journey

    home = _screen("/home", _tab("s1", "p1", 5, [[0, 20]], loose=["q-p1-3"]),
                   _tab("s2", "p2", 9, [[0, 30]], pins=["q-p2-8", "q-p1-3"]))
    basket = _screen("/basket", _tab("s2", "p2", 300, [[290, 310]], loose=["q-p2-300", "q-p2-295"]),
                     _tab("s1", "p1", 50, [[40, 60]], loose=["q-p1-45"]))
    owner = {"q-p1-3": "s1", "q-p2-8": "s2", "q-p2-300": "s2", "q-p2-295": "s2", "q-p1-45": "s1"}
    out = journey([basket, home], owner, hidden={"q-p2-300"})  # the lens's order is not the journey's
    assert [e["screen_key"] for e in out] == ["/home", "/basket"]
    assert out[0]["groups"] == [("p1", ["q-p1-3"]), ("p2", ["q-p2-8"])]  # a cross-linked quote, once
    assert out[1]["groups"] == [("p1", ["q-p1-45"]), ("p2", ["q-p2-295"])]
    assert out[1]["session_id"] == "s2"  # the version the lens shows first
    assert [e["filename"] for e in out] == ["screen-01.jpg", "screen-02.jpg"]


def test_a_crafted_code_cannot_name_a_file_outside_the_folder() -> None:
    for code in ("../../../escape", "/tmp/pwn", "p1/../x"):
        [shot] = shot_list([_screen("/a", _tab("s1", code, 1, [[0, 2]]))], {})
        assert "/" not in shot["filename"] and not shot["filename"].startswith(".")


def test_two_names_cleaned_into_one_are_numbered_apart() -> None:
    shared = [_screen("/a", _tab("s 1", "p1", 1, [[0, 2]]), _tab("s/1", "p1", 1, [[0, 2]]))]
    names = sorted(s["filename"] for s in shot_list(shared, {}))
    assert len(set(names)) == 2 and all("/" not in n and " " not in n for n in names)


def test_journey_order_weighs_each_participants_journey_equally() -> None:
    from bristlenose.screen_text.shots import journey

    # p1 browsed widely and reached /cart 25th; p2, p3 and p4 went straight there, 2nd of 3.
    wide = [_tab("s1", "p1", i, [[i, i + 1]]) for i in range(30)]
    screens = [_screen(f"/x{i}", t) for i, t in enumerate(wide) if i != 24]
    cart = _screen("/cart", _tab("s1", "p1", 24, [[24, 25]]),
                   *[_tab(f"s{n}", f"p{n}", 10, [[10, 11]]) for n in (2, 3, 4)])
    done = _screen("/done", *[_tab(f"s{n}", f"p{n}", 20, [[20, 21]]) for n in (2, 3, 4)])
    first = _screen("/home", *[_tab(f"s{n}", f"p{n}", 0, [[0, 1]]) for n in (2, 3, 4)])
    order = [e["screen_key"] for e in journey(screens + [cart, done, first], {})]
    assert order.index("/home") < order.index("/cart") < order.index("/done")
