"""Screens named by the pipeline's sections, where no address or title keys one (§3.6 rung 3).

A recording of a native app or a desktop shows no address bar, so before 16 Nov 2026 such a study
had almost no screens (the Inception study: 8, all browser detours). The sections name them now,
in a session that is a screen share with text and that addresses and titles mostly do not cover.
"""

from __future__ import annotations

from typing import Any

from bristlenose.screen_text.screens import (
    NamedScreen,
    SessionInput,
    derive_screens,
    named_eligible,
    visits_of,
)

EVERY = 4.0


def _lines(prefix: str, t0: float, t1: float, n: int = 20, y0: float = 0.25) -> list[dict[str, Any]]:
    """``n`` lines of an app's window on screen from t0 to t1 (a sample every 4 s)."""
    return [{"text": f"{prefix} {w} row {i}", "box": [0.1, y0 + i * 0.03, 0.6, 0.02], "sticky": False,
             "runs": [[t0, t1]]} for i, w in enumerate(["alpha", "bravo", "charlie", "delta", "echo",
                                                        "foxtrot", "golf", "hotel", "india", "juliet",
                                                        "kilo", "lima", "mike", "november", "oscar",
                                                        "papa", "quebec", "romeo", "sierra", "tango"][:n])]


def _index(episodes: list[dict[str, Any]], t_end: float) -> dict[str, Any]:
    return {"every": EVERY, "samples": int(t_end / EVERY) + 1, "episodes": episodes, "moments": []}


def _q(dom_id: str, start: float, end: float, text: str) -> dict[str, Any]:
    return {"dom_id": dom_id, "start": start, "end": end, "text": text}


def _app_recording() -> dict[str, Any]:
    """A native app: a codebook window 0–96 s, a quotes window 100–200 s; no address bar."""
    return _index(_lines("codebook", 0, 96) + _lines("quotes", 100, 200), 200)


CODEBOOK = NamedScreen("section:1", "Codebooks & Auto-Tagging", frozenset({"q-p1-40"}))
QUOTES = NamedScreen("section:2", "Quotes View", frozenset({"q-p1-150"}))


def test_an_app_recording_has_a_screen_per_section_named_and_still_where_it_was_said() -> None:
    quotes = [_q("q-p1-40", 40, 48, "the codebook charlie row was confusing"),
              _q("q-p1-150", 150, 158, "the quotes kilo row is what I wanted")]
    rec = _app_recording()
    assert derive_screens([SessionInput("s1", "p1", rec, quotes)]) == [], "no address, no title"
    screens = derive_screens([SessionInput("s1", "p1", rec, quotes)], [CODEBOOK, QUOTES])
    by_key = {sc["key"]: sc for sc in screens}
    assert set(by_key) == {"section:1", "section:2"}
    assert by_key["section:1"]["name"] == "Codebooks & Auto-Tagging"
    [cb] = by_key["section:1"]["tabs"]
    [qv] = by_key["section:2"]["tabs"]
    assert 36 <= cb["t"] <= 52 and 146 <= qv["t"] <= 162, "the still is taken where it was said"
    assert [p["dom_id"] for p in cb["pins"]] == ["q-p1-40"]
    assert [p["dom_id"] for p in qv["pins"]] == ["q-p1-150"]


def test_a_talking_head_gets_no_section_screens() -> None:
    """A call's faces carry a few lines (names, a clock): sections name no screen there."""
    rec = _index(_lines("tile", 0, 200, n=3), 200)
    quotes = [_q("q-p1-40", 40, 48, "the tile alpha row was confusing")]
    assert not named_eligible(rec, visits_of(rec))
    assert derive_screens([SessionInput("s1", "p1", rec, quotes)], [CODEBOOK]) == []


def _address(t0: float, t1: float) -> dict[str, Any]:
    return {"text": "shop.example.com/checkout/cart", "box": [0.2, 0.03, 0.4, 0.02], "sticky": False,
            "runs": [[t0, t1]]}


def test_a_web_study_is_unchanged() -> None:
    """Addresses cover the session: its screens are the pages, exactly as without sections."""
    rec = _index([_address(0, 200), *_lines("page", 0, 200)], 200)
    quotes = [_q("q-p1-40", 40, 48, "the page charlie row was confusing")]
    before = derive_screens([SessionInput("s1", "p1", rec, quotes)])
    after = derive_screens([SessionInput("s1", "p1", rec, quotes)], [CODEBOOK])
    assert after == before and [sc["key"] for sc in after] == ["url:/checkout/cart"]


def test_a_session_addresses_mostly_cover_gets_no_section_screens() -> None:
    """A web session with a stretch no address covers is still a web session: as before."""
    rec = _index([_address(0, 120), *_lines("page", 0, 200)], 200)
    quotes = [_q("q-p1-160", 160, 166, "the page hotel row was confusing")]
    section = NamedScreen("section:1", "Account", frozenset({"q-p1-160"}))
    assert derive_screens([SessionInput("s1", "p1", rec, quotes)], [section]) == derive_screens(
        [SessionInput("s1", "p1", rec, quotes)])


def test_a_quote_said_on_a_page_stays_on_the_page_and_its_section_takes_only_the_rest() -> None:
    """A section with one quote over an address and one off it: the first stays on the page."""
    rec = _index([_address(0, 16), *_lines("app", 0, 200)], 200)
    section = NamedScreen("section:1", "Settings", frozenset({"q-p1-8", "q-p1-80"}))
    quotes = [_q("q-p1-8", 8, 12, "the app bravo row on the cart"),
              _q("q-p1-80", 80, 86, "the app hotel row in settings")]
    screens = {sc["key"]: sc for sc in derive_screens([SessionInput("s1", "p1", rec, quotes)], [section])}
    assert set(screens) == {"url:/checkout/cart", "section:1"}

    def said(sc: dict[str, Any]) -> set[str]:
        return {p["dom_id"] for t in sc["tabs"] for p in t["pins"]} | {d for t in sc["tabs"] for d in t["loose"]}
    assert said(screens["url:/checkout/cart"]) == {"q-p1-8"}
    assert said(screens["section:1"]) == {"q-p1-80"}


def test_two_sections_said_close_together_never_share_a_still() -> None:
    """Their windows stop at each other's quote, so each still is in its own section's time."""
    rec = _index(_lines("app", 0, 200), 200)
    a = NamedScreen("section:1", "Import", frozenset({"q-p1-a"}))
    b = NamedScreen("section:2", "Progress", frozenset({"q-p1-b"}))

    def tabs(qa: tuple[float, float], qb: tuple[float, float]) -> tuple[dict[str, Any], dict[str, Any]]:
        quotes = [_q("q-p1-a", *qa, "the app delta row importing"), _q("q-p1-b", *qb, "the app golf row progress")]
        screens = {sc["key"]: sc for sc in derive_screens([SessionInput("s1", "p1", rec, quotes)], [a, b])}
        return screens["section:1"]["tabs"][0], screens["section:2"]["tabs"][0]

    # The first section's window would run on to 108, past where the second's quote starts.
    ta, tb = tabs((100, 104), (106, 112))
    assert max(v[1] for v in ta["visits"]) <= 106 and ta["t"] != tb["t"]
    # The second's window would reach back to 100, before the first's quote ends.
    ta, tb = tabs((96, 103), (104, 110))
    assert min(v[0] for v in tb["visits"]) >= 103 and ta["t"] != tb["t"]


def test_a_section_quote_is_placed_on_its_own_section_even_inside_another_sections_time() -> None:
    """Placed by membership: by time alone, a short quote said inside a longer one's span would go
    to whichever screen came first."""
    rec = _index(_lines("app", 0, 200), 200)
    long_ = NamedScreen("section:1", "Import", frozenset({"q-p1-100"}))
    short = NamedScreen("section:2", "Progress", frozenset({"q-p1-104"}))
    quotes = [_q("q-p1-100", 100, 112, "the app delta row importing"),
              _q("q-p1-104", 104, 108, "the app golf row progress")]
    screens = {sc["key"]: sc for sc in derive_screens([SessionInput("s1", "p1", rec, quotes)], [long_, short])}
    [tab] = screens["section:2"]["tabs"]
    assert "q-p1-104" in {p["dom_id"] for p in tab["pins"]} | set(tab["loose"])
    [other] = screens["section:1"]["tabs"]
    assert "q-p1-104" not in set(other["loose"]) | {p["dom_id"] for p in other["pins"]}


def test_one_section_across_two_sessions_is_one_screen_with_a_tab_each() -> None:
    section = NamedScreen("section:2", "Quotes View", frozenset({"q-p1-150", "q-p2-120"}))
    s1 = SessionInput("s1", "p1", _app_recording(), [_q("q-p1-150", 150, 158, "the quotes kilo row")])
    s2 = SessionInput("s2", "p2", _app_recording(), [_q("q-p2-120", 120, 126, "the quotes mike row")])
    [screen] = derive_screens([s1, s2], [section])
    assert screen["key"] == "section:2" and [t["code"] for t in screen["tabs"]] == ["p1", "p2"]
    assert screen["quotes"] == 2


def test_many_sections_over_one_window_keep_their_screens() -> None:
    """A window the participant stays in is content, not chrome: sections do not count as pages
    when telling furniture (five or more sections once erased every screen; review, 16 Nov)."""
    rec = _index(_lines("doc", 0, 400), 400)
    sections = [NamedScreen(f"section:{i}", f"Part {i}", frozenset({f"q-p1-{i}"})) for i in range(6)]
    quotes = [_q(f"q-p1-{i}", 20 + 60 * i, 26 + 60 * i, f"the doc {w} row") for i, w in
              enumerate(["alpha", "bravo", "charlie", "delta", "echo", "foxtrot"])]
    screens = derive_screens([SessionInput("s1", "p1", rec, quotes)], sections)
    assert len(screens) == 6 and all(sc["tabs"][0]["pins"] for sc in screens)


def test_a_quote_said_far_from_any_text_makes_no_visit() -> None:
    """Text on screen 0–400 s, a quote at 560 s (the camera alone): no still from 160 s away."""
    rec = _index(_lines("app", 0, 400), 600)
    section = NamedScreen("section:1", "Later", frozenset({"q-p1-560"}))
    quotes = [_q("q-p1-560", 560, 566, "the app alpha row")]
    assert derive_screens([SessionInput("s1", "p1", rec, quotes)], [section]) == []


def test_the_gate_lies_where_it_was_measured() -> None:
    """15 lines a sample is a screen share, 14 is not; addresses on under a quarter of the samples
    leave it to the sections, a quarter does not."""
    def eligible(lines: int, covered_samples: int) -> bool:
        eps = _lines("app", 0, 396, n=lines)
        if covered_samples:
            eps.append(_address(0, (covered_samples - 1) * EVERY))
        rec = _index(eps, 396)  # 100 samples
        return named_eligible(rec, visits_of(rec))
    assert eligible(15, 0) and not eligible(14, 0)
    assert eligible(20, 24) and not eligible(20, 25)
