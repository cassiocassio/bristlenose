"""The Screens lens's arrangements: a researcher edit, per project in SQLite, one version per write.

Until 15 Oct 2026 they lived in the browser's localStorage, which in the Mac app is an in-memory
store per serve session, so quitting the app lost every custom board."""

from __future__ import annotations

from pathlib import Path

import pytest

from bristlenose.server.app import create_app
from bristlenose.server.models import ScreenArrangement
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
URL = "/api/projects/1/screens"


def _edge(edge: str = "R", along: float = 0.4, z: float = 31) -> dict:
    return {"kind": "edge", "edge": edge, "along": along, "out": 32.0, "z": z}


def _put(client, key: str, sid: str, cards):
    return client.put(f"{URL}/arrangement", json={"screen_key": key, "session_id": sid, "cards": cards})


def _versions(client) -> dict[tuple[str, str], dict]:
    body = client.get(f"{URL}/arrangements").json()
    return {(v["screen_key"], v["session_id"]): v["cards"] for v in body["versions"]}


@pytest.fixture()
def db_file(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'serve.db'}"


@pytest.fixture()
def client(db_file: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("BRISTLENOSE_SCREEN_TEXT", raising=False)
    return AuthTestClient(create_app(project_dir=_FIXTURE_DIR, dev=True, db_url=db_file))


def test_none_until_a_board_is_rearranged(client) -> None:
    assert client.get(f"{URL}/arrangements").json() == {"versions": []}


def test_a_write_replaces_its_own_version_and_touches_no_other(client) -> None:
    assert _put(client, "url:/cart", "s1", {"q-p1-10": _edge(), "q-p1-26": _edge("L", 0.2)}).status_code == 200
    assert _put(client, "url:/cart", "s2", {"q-p1-46": _edge("T", 0.5)}).status_code == 200
    assert _put(client, "url:/pay", "s1", {"q-p1-66": {"kind": "over", "x": 0.3, "y": 0.6, "z": 40}}).status_code == 200
    # The whole of one version is replaced: a card dropped from the body is gone from it.
    assert _put(client, "url:/cart", "s1", {"q-p1-10": _edge(along=0.7)}).status_code == 200
    v = _versions(client)
    assert v[("url:/cart", "s1")] == {"q-p1-10": _edge(along=0.7)}
    assert v[("url:/cart", "s2")] == {"q-p1-46": _edge("T", 0.5)}
    assert set(v) == {("url:/cart", "s1"), ("url:/cart", "s2"), ("url:/pay", "s1")}


def test_tidy_deletes_the_version_and_only_that_version(client) -> None:
    _put(client, "url:/cart", "s1", {"q-p1-10": _edge()})
    _put(client, "url:/cart", "s2", {"q-p1-46": _edge()})
    assert _put(client, "url:/cart", "s1", None).status_code == 200
    assert set(_versions(client)) == {("url:/cart", "s2")}
    assert _put(client, "url:/cart", "s1", None).status_code == 200  # already automatic: no error


def test_it_survives_a_new_serve_on_the_same_project(db_file: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The point of the table: quitting the app, or any serve restart, keeps the board."""
    monkeypatch.delenv("BRISTLENOSE_SCREEN_TEXT", raising=False)
    first = AuthTestClient(create_app(project_dir=_FIXTURE_DIR, dev=True, db_url=db_file))
    _put(first, "url:/cart", "s1", {"q-p1-10": _edge()})
    second = AuthTestClient(create_app(project_dir=_FIXTURE_DIR, dev=True, db_url=db_file))
    assert _versions(second) == {("url:/cart", "s1"): {"q-p1-10": _edge()}}


def test_turning_reading_off_deletes_them(db_file: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A screen key is a page's path read from a participant's screen (§4.8)."""
    monkeypatch.delenv("BRISTLENOSE_SCREEN_TEXT", raising=False)
    first = AuthTestClient(create_app(project_dir=_FIXTURE_DIR, dev=True, db_url=db_file))
    _put(first, "url:/cart", "s1", {"q-p1-10": _edge()})
    monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "0")
    off = AuthTestClient(create_app(project_dir=_FIXTURE_DIR, dev=True, db_url=db_file))
    assert _versions(off) == {}


@pytest.mark.parametrize("cards", [
    {"q-p1-10": {**_edge(), "edge": "X"}},
    {"q-p1-10": {"kind": "over", "x": None, "y": 0.1, "z": 31}},  # what JSON.stringify makes of NaN
    {"q-p1-10": {"kind": "sideways", "x": 0.1, "y": 0.1, "z": 31}},
    {"": _edge()},
    {f"q-{i}": _edge() for i in range(2001)},
    {"q-p1-10": _edge(along=1000)},  # a thousand screengrabs along: corrupt
    {"q-p1-10": {**_edge(), "out": 1e6}},
    {"q-p1-10": _edge(z=-1)},
    {"q-p1-10": _edge(z=1e308)},  # would put every later card underneath it
])
def test_refuses_a_body_no_board_could_write(client, cards) -> None:
    r = _put(client, "url:/cart", "s1", cards)
    assert r.status_code == 422
    assert _versions(client) == {}


@pytest.mark.parametrize("body", [
    {"screen_key": "", "session_id": "s1", "cards": None},
    {"screen_key": "url:/cart", "session_id": "", "cards": None},
    {"screen_key": "url:/cart", "session_id": "s1"},
])
def test_refuses_a_version_it_cannot_name(client, body) -> None:
    assert client.put(f"{URL}/arrangement", json=body).status_code == 422


def test_an_unknown_project_is_404(client) -> None:
    assert client.get("/api/projects/99/screens/arrangements").status_code == 404
    assert client.put("/api/projects/99/screens/arrangement",
                      json={"screen_key": "k", "session_id": "s1", "cards": None}).status_code == 404


def test_a_row_that_does_not_parse_is_skipped_not_served(client) -> None:
    _put(client, "url:/cart", "s2", {"q-p1-46": _edge()})
    db = client.app.state.db_factory()
    try:
        db.add(ScreenArrangement(project_id=1, screen_key="url:/cart", session_id="s1", cards="{not json"))
        db.add(ScreenArrangement(project_id=1, screen_key="url:/pay", session_id="s1",
                                 cards='{"q": {"kind": "edge", "edge": "Q"}}'))
        db.commit()
    finally:
        db.close()
    assert set(_versions(client)) == {("url:/cart", "s2")}


@pytest.mark.parametrize("env", ["0", None])
def test_nothing_is_written_or_served_while_the_lens_is_off(db_file: str, env, monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit off deleted them; nothing may write one back (a browser's copy would, on open).
    Unset without --dev, the lens is off too."""
    if env is None:
        monkeypatch.delenv("BRISTLENOSE_SCREEN_TEXT", raising=False)
    else:
        monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", env)
    off = AuthTestClient(create_app(project_dir=_FIXTURE_DIR, dev=False, db_url=db_file))
    assert _put(off, "url:/cart", "s1", {"q-p1-10": _edge()}).status_code == 404
    assert off.get(f"{URL}/arrangements").json() == {"versions": []}
    db = off.app.state.db_factory()
    try:
        assert db.query(ScreenArrangement).count() == 0
    finally:
        db.close()


def test_two_windows_creating_one_version_at_once_both_succeed(client, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both find no row; the second insert meets the unique constraint and becomes an update."""
    db = client.app.state.db_factory()
    try:
        db.add(ScreenArrangement(project_id=1, screen_key="url:/cart", session_id="s1", cards="{}"))
        db.commit()
    finally:
        db.close()
    from sqlalchemy.orm import Query

    real = Query.one_or_none
    calls = {"n": 0}

    def stale_first(self):  # the other window's insert landed after this one looked
        calls["n"] += 1
        return None if calls["n"] == 1 else real(self)
    monkeypatch.setattr(Query, "one_or_none", stale_first)
    assert _put(client, "url:/cart", "s1", {"q-p1-10": _edge()}).status_code == 200
    monkeypatch.setattr(Query, "one_or_none", real)
    assert _versions(client) == {("url:/cart", "s1"): {"q-p1-10": _edge()}}


def test_only_this_projects_rows_are_served(client) -> None:
    from bristlenose.server.models import Project

    db = client.app.state.db_factory()
    try:
        db.add(Project(id=2, name="Other", slug="other", input_dir="/x", output_dir="/x/out"))
        db.add(ScreenArrangement(project_id=2, screen_key="url:/elsewhere", session_id="s1",
                                 cards='{"q-p1-10": {"kind": "over", "x": 0.1, "y": 0.1, "z": 31}}'))
        db.commit()
    finally:
        db.close()
    assert _versions(client) == {}


def test_a_reimport_drops_placements_for_quotes_that_no_longer_exist(db_file: str,
                                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    """A re-analysis that moves a quote's start makes it a new id: the old id's placement goes,
    the board is otherwise left as it was, and a version left with none returns to automatic."""
    monkeypatch.delenv("BRISTLENOSE_SCREEN_TEXT", raising=False)
    first = AuthTestClient(create_app(project_dir=_FIXTURE_DIR, dev=True, db_url=db_file))
    _put(first, "url:/cart", "s1", {"q-p1-10": _edge(), "q-p1-999": _edge("L", 0.2)})
    _put(first, "url:/pay", "s1", {"q-p9-1": _edge()})
    _put(first, "url:/ok", "s1", {"q-p1-46": _edge("T", 0.5)})
    second = AuthTestClient(create_app(project_dir=_FIXTURE_DIR, dev=True, db_url=db_file))  # imports again
    assert _versions(second) == {
        ("url:/cart", "s1"): {"q-p1-10": _edge()},
        ("url:/ok", "s1"): {"q-p1-46": _edge("T", 0.5)},
    }

