"""Curation deltas: ``PATCH`` on the five curation paths writes only what it names.

The ``PUT`` routes replace the whole map, so the server erases whatever the
client didn't hold: AutoCode tags re-applied after new sessions (R1), the
curation of quotes a speaker recode hides from ``/quotes`` (R2), and a deleted
tag the client still carried came back under Uncategorised (R3). The SPA now
sends each gesture as a ``PATCH`` that names only the quotes it changed and only
what changed. These tests pin that, and the ``PUT`` contract stays in
``test_serve_data_api.py``.
"""

from __future__ import annotations

import asyncio
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.models import (
    AutoCodeJob,
    CodebookGroup,
    Quote,
    QuoteTag,
    TagDefinition,
)
from bristlenose.server.models import Session as SessionModel
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_P = "/api/projects/1"


@pytest.fixture()
def client() -> TestClient:
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return AuthTestClient(app)


def _smoke_copy(tmp_path: Path) -> TestClient:
    proj = tmp_path / "proj"
    shutil.copytree(_FIXTURE_DIR, proj)
    return AuthTestClient(create_app(project_dir=proj, dev=True, db_url="sqlite://"))


# The smoke fixture's sentiment tags are quote tags too; the tag tests read past them.
_SENTIMENT = {"confusion", "frustration", "delight"}


def _tags(client: TestClient) -> dict[str, list[str]]:
    """``GET /tags`` without the fixture's sentiment tags."""
    out: dict[str, list[str]] = {}
    for k, v in client.get(f"{_P}/tags").json().items():
        kept = [t for t in v if t not in _SENTIMENT]
        if kept:
            out[k] = kept
    return out


def _quote(client: TestClient, participant: str, start: float) -> Quote:
    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        q = (
            db.query(Quote)
            .filter_by(project_id=1, participant_id=participant)
            .filter(Quote.start_timecode >= start, Quote.start_timecode < start + 1)
            .one()
        )
        db.expunge(q)
        return q
    finally:
        db.close()


# ---------------------------------------------------------------------------
# A PATCH touches only the keys it names
# ---------------------------------------------------------------------------


class TestPatchTouchesOnlyNamedKeys:
    def test_starred(self, client: TestClient) -> None:
        client.put(f"{_P}/starred", json={"q-p1-10": True, "q-p1-26": True})
        r = client.patch(f"{_P}/starred", json={"q-p1-46": True})
        assert r.status_code == 200, r.text
        assert client.get(f"{_P}/starred").json() == {
            "q-p1-10": True, "q-p1-26": True, "q-p1-46": True,
        }
        client.patch(f"{_P}/starred", json={"q-p1-10": False})
        assert client.get(f"{_P}/starred").json() == {"q-p1-26": True, "q-p1-46": True}

    def test_hidden(self, client: TestClient) -> None:
        client.put(f"{_P}/hidden", json={"q-p1-10": True, "q-p1-26": True})
        r = client.patch(f"{_P}/hidden", json={"q-p1-46": True})
        assert r.status_code == 200, r.text
        assert client.get(f"{_P}/hidden").json() == {
            "q-p1-10": True, "q-p1-26": True, "q-p1-46": True,
        }
        client.patch(f"{_P}/hidden", json={"q-p1-26": False})
        assert client.get(f"{_P}/hidden").json() == {"q-p1-10": True, "q-p1-46": True}

    def test_edits(self, client: TestClient) -> None:
        client.put(f"{_P}/edits", json={"q-p1-10": "ten", "section-cluster-1:title": "Head"})
        r = client.patch(f"{_P}/edits", json={"q-p1-26": "twenty-six"})
        assert r.status_code == 200, r.text
        assert client.get(f"{_P}/edits").json() == {
            "q-p1-10": "ten", "q-p1-26": "twenty-six", "section-cluster-1:title": "Head",
        }

    def test_tags(self, client: TestClient) -> None:
        client.put(f"{_P}/tags", json={"q-p1-10": ["a"], "q-p1-26": ["b"]})
        r = client.patch(f"{_P}/tags", json={"q-p1-46": {"add": ["c"]}})
        assert r.status_code == 200, r.text
        assert _tags(client) == {
            "q-p1-10": ["a"], "q-p1-26": ["b"], "q-p1-46": ["c"],
        }

    def test_deleted_badges(self, client: TestClient) -> None:
        client.put(f"{_P}/deleted-badges", json={"q-p1-10": ["confusion"]})
        r = client.patch(f"{_P}/deleted-badges", json={"q-p1-26": {"add": ["frustration"]}})
        assert r.status_code == 200, r.text
        assert client.get(f"{_P}/deleted-badges").json() == {
            "q-p1-10": ["confusion"], "q-p1-26": ["frustration"],
        }


# ---------------------------------------------------------------------------
# Tags: add / remove by name, provenance and pins as the PUT keeps them
# ---------------------------------------------------------------------------


class TestPatchTags:
    def test_add_keeps_the_quotes_other_tags(self, client: TestClient) -> None:
        client.put(f"{_P}/tags", json={"q-p1-10": ["a", "b"]})
        client.patch(f"{_P}/tags", json={"q-p1-10": {"add": ["c"]}})
        assert _tags(client) == {"q-p1-10": ["a", "b", "c"]}

    def test_remove_takes_only_that_tag(self, client: TestClient) -> None:
        client.put(f"{_P}/tags", json={"q-p1-10": ["a", "b"], "q-p1-26": ["a"]})
        client.patch(f"{_P}/tags", json={"q-p1-10": {"remove": ["a"]}})
        assert _tags(client) == {"q-p1-10": ["b"], "q-p1-26": ["a"]}

    def test_remove_is_case_insensitive_and_unknown_is_a_no_op(
        self, client: TestClient,
    ) -> None:
        client.put(f"{_P}/tags", json={"q-p1-10": ["Alpha"]})
        r = client.patch(f"{_P}/tags", json={"q-p1-10": {"remove": ["alpha", "never-made"]}})
        assert r.status_code == 200
        assert _tags(client) == {}
        db = client.app.state.db_factory()  # type: ignore[attr-defined]
        try:
            assert db.query(TagDefinition).filter_by(name="never-made").count() == 0
        finally:
            db.close()

    def test_remove_finds_the_quotes_tag_when_two_definitions_share_its_name(
        self, client: TestClient,
    ) -> None:
        client.patch(f"{_P}/tags", json={"q-p1-10": {"add": ["Shared"]}})
        db = client.app.state.db_factory()  # type: ignore[attr-defined]
        try:
            first = db.query(TagDefinition).filter_by(name="Shared").one()
            db.add(TagDefinition(name="shared", codebook_group_id=first.codebook_group_id))
            db.commit()
        finally:
            db.close()
        client.patch(f"{_P}/tags", json={"q-p1-10": {"remove": ["Shared"]}})
        assert _tags(client) == {}

    def test_new_name_is_created_in_uncategorised_as_human_and_pins(
        self, client: TestClient,
    ) -> None:
        client.patch(f"{_P}/tags", json={"q-p1-10": {"add": ["brand new"]}})
        db = client.app.state.db_factory()  # type: ignore[attr-defined]
        try:
            td = db.query(TagDefinition).filter_by(name="brand new").one()
            assert db.get(CodebookGroup, td.codebook_group_id).name == "Uncategorised"
            qt = db.query(QuoteTag).filter_by(tag_definition_id=td.id).one()
            assert qt.source == "human"
        finally:
            db.close()
        assert _quote(client, "p1", 10).durable_id is not None

    def test_adding_a_name_already_on_the_quote_keeps_its_provenance(
        self, client: TestClient,
    ) -> None:
        client.put(f"{_P}/tags", json={"q-p1-10": ["machine"]})
        db = client.app.state.db_factory()  # type: ignore[attr-defined]
        try:
            for qt in db.query(QuoteTag).all():
                qt.source = "autocode"
            q = db.query(Quote).filter_by(participant_id="p1", start_timecode=10.0).first()
            if q is not None:
                q.durable_id = None
                q.frozen_form = None
            db.commit()
        finally:
            db.close()
        client.patch(f"{_P}/tags", json={"q-p1-10": {"add": ["Machine"]}})
        db = client.app.state.db_factory()  # type: ignore[attr-defined]
        try:
            assert [qt.source for qt in db.query(QuoteTag).all()] == ["autocode"]
        finally:
            db.close()
        assert _quote(client, "p1", 10).durable_id is None

    def test_a_sentiment_named_tag_does_not_pin(self, client: TestClient) -> None:
        db = client.app.state.db_factory()  # type: ignore[attr-defined]
        try:
            names = [
                td.name
                for td in db.query(TagDefinition)
                .join(CodebookGroup, TagDefinition.codebook_group_id == CodebookGroup.id)
                .filter(CodebookGroup.framework_id == "sentiment")
                .all()
            ]
        finally:
            db.close()
        if not names:
            pytest.skip("smoke fixture has no sentiment framework tags")
        client.patch(f"{_P}/tags", json={"q-p1-46": {"add": [names[0]]}})
        assert _quote(client, "p1", 46).durable_id is None


# ---------------------------------------------------------------------------
# Edits, stars, badges
# ---------------------------------------------------------------------------


class TestPatchEditsStarsBadges:
    def test_null_clears_a_quote_edit_and_a_heading_edit(self, client: TestClient) -> None:
        client.put(f"{_P}/edits", json={
            "q-p1-10": "ten", "q-p1-26": "keep", "theme-group-1:desc": "D",
        })
        r = client.patch(f"{_P}/edits", json={"q-p1-10": None, "theme-group-1:desc": None})
        assert r.status_code == 200, r.text
        assert client.get(f"{_P}/edits").json() == {"q-p1-26": "keep"}

    def test_an_edit_replaces_the_previous_one_and_freezes_its_words(
        self, client: TestClient,
    ) -> None:
        client.patch(f"{_P}/edits", json={"q-p1-10": "first"})
        client.patch(f"{_P}/edits", json={"q-p1-10": "second"})
        assert client.get(f"{_P}/edits").json() == {"q-p1-10": "second"}
        assert _quote(client, "p1", 10).frozen_form == "first"  # first touch wins

    def test_star_pins_hide_does_not(self, client: TestClient) -> None:
        client.patch(f"{_P}/hidden", json={"q-p1-26": True})
        assert _quote(client, "p1", 26).durable_id is None
        client.patch(f"{_P}/starred", json={"q-p1-10": True})
        assert _quote(client, "p1", 10).durable_id is not None

    def test_badges_add_and_remove(self, client: TestClient) -> None:
        client.patch(f"{_P}/deleted-badges", json={"q-p1-10": {"add": ["confusion", "x"]}})
        client.patch(f"{_P}/deleted-badges", json={"q-p1-10": {"add": ["confusion"]}})
        client.patch(f"{_P}/deleted-badges", json={"q-p1-10": {"remove": ["x"]}})
        assert client.get(f"{_P}/deleted-badges").json() == {"q-p1-10": ["confusion"]}

    def test_an_unknown_quote_is_skipped(self, client: TestClient) -> None:
        for path, body in (
            ("starred", {"q-p9-999": True}),
            ("hidden", {"q-p9-999": True}),
            ("edits", {"q-p9-999": "x"}),
            ("tags", {"q-p9-999": {"add": ["x"]}}),
            ("deleted-badges", {"q-p9-999": {"add": ["x"]}}),
        ):
            before = client.get(f"{_P}/{path}").json()
            r = client.patch(f"{_P}/{path}", json=body)
            assert r.status_code == 200, (path, r.text)
            assert client.get(f"{_P}/{path}").json() == before, path


class TestPatchLimits:
    def test_too_many_quotes_is_refused(self, client: TestClient) -> None:
        body = {f"q-p1-{i}": True for i in range(10_001)}
        assert client.patch(f"{_P}/starred", json=body).status_code == 422

    def test_too_long_a_tag_name_is_refused(self, client: TestClient) -> None:
        r = client.patch(f"{_P}/tags", json={"q-p1-10": {"add": ["x" * 201]}})
        assert r.status_code == 422

    def test_too_many_ops_on_one_quote_is_refused(self, client: TestClient) -> None:
        r = client.patch(f"{_P}/tags", json={"q-p1-10": {"add": [f"t{i}" for i in range(101)]}})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# The bugs, end to end
# ---------------------------------------------------------------------------


def test_r1_tags_autocode_reapplied_survive_the_next_tag_gesture(tmp_path: Path) -> None:
    """R1: the re-apply lands after the SPA last loaded; a tag gesture must not erase it."""
    from tests.test_autocode_engine import _make_batch_result, _mock_settings, _patch_llm

    client = _smoke_copy(tmp_path)
    factory = client.app.state.db_factory  # type: ignore[attr-defined]
    r = client.post(f"{_P}/codebook/import-template", json={"template_id": "garrett"})
    assert r.status_code == 200, r.text
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = factory()
    try:
        db.add(AutoCodeJob(project_id=1, framework_id="garrett", status="completed",
                           completed_at=now, applied_upper_threshold=0.7))
        db.add(SessionModel(project_id=1, session_id="s2", session_number=2,
                            first_imported_at=now + timedelta(days=1)))
        for i in range(2):
            db.add(Quote(project_id=1, session_id="s2", participant_id="p2",
                         start_timecode=float(100 + 10 * i), end_timecode=float(105 + 10 * i),
                         text=f"new session quote {i}", quote_type="screen_specific",
                         topic_label="Dashboard"))
        db.commit()
    finally:
        db.close()

    from bristlenose.server.autocode import reapply_active_frameworks

    with _patch_llm(AsyncMock(return_value=_make_batch_result(2, "user need", 0.9))):
        asyncio.run(reapply_active_frameworks(factory, 1, _mock_settings()))
    reapplied = {k: v for k, v in client.get(f"{_P}/tags").json().items()
                 if k.startswith("q-p2-")}
    assert reapplied, "re-apply wrote nothing — set-up wrong"

    # The gesture the SPA now sends: only the quote and the tag it added.
    r = client.patch(f"{_P}/tags", json={"q-p1-10": {"add": ["my tag"]}})
    assert r.status_code == 200, r.text
    after = client.get(f"{_P}/tags").json()
    assert {k: after.get(k) for k in reapplied} == reapplied
    assert "my tag" in after["q-p1-10"]


def test_r2_curation_of_recoded_out_quotes_survives_gestures_and_comes_back(
    tmp_path: Path,
) -> None:
    """R2: a quote the recode hides from /quotes keeps its curation through gestures elsewhere."""
    from tests.test_serve_moderator_identities import _client
    from tests.test_serve_participant_recode import _martin, _with_quotes

    client = _client(_with_quotes(tmp_path))
    client.patch(f"{_P}/starred", json={"q-p1-10": True})
    client.patch(f"{_P}/hidden", json={"q-p1-10": True})
    client.patch(f"{_P}/tags", json={"q-p1-10": {"add": ["keep me"]}})
    client.patch(f"{_P}/edits", json={"q-p1-10": "edited words"})
    client.patch(f"{_P}/deleted-badges", json={"q-p1-10": {"add": ["confusion"]}})

    r = client.put(f"{_P}/sessions/s1/speakers/p1",
                   json={"kind": "moderator", "person": _martin(client)})
    assert r.status_code == 200, r.text

    # Gestures on the other session's quote, as the SPA sends them.
    for path, body in (
        ("starred", {"q-p2-10": True}),
        ("hidden", {"q-p2-10": True}),
        ("tags", {"q-p2-10": {"add": ["other"]}}),
        ("edits", {"q-p2-10": "p2 edit"}),
        ("deleted-badges", {"q-p2-10": {"add": ["delight"]}}),
    ):
        assert client.patch(f"{_P}/{path}", json=body).status_code == 200, path
    assert client.get(f"{_P}/starred").json().get("q-p2-10") is True  # the gestures landed

    r = client.put(f"{_P}/sessions/s1/speakers/p1",
                   json={"kind": "participant", "confirmed": True})
    assert r.status_code == 200, r.text
    assert client.get(f"{_P}/starred").json().get("q-p1-10") is True
    assert client.get(f"{_P}/hidden").json().get("q-p1-10") is True
    assert "keep me" in client.get(f"{_P}/tags").json().get("q-p1-10", [])
    assert client.get(f"{_P}/edits").json().get("q-p1-10") == "edited words"
    assert client.get(f"{_P}/deleted-badges").json().get("q-p1-10") == ["confusion"]


def test_r3_an_uninstalled_codebooks_tag_does_not_come_back(tmp_path: Path) -> None:
    """R3: a gesture after an uninstall never re-creates the removed tag."""
    client = _smoke_copy(tmp_path)
    r = client.post(f"{_P}/codebook/import-template", json={"template_id": "garrett"})
    assert r.status_code == 200, r.text
    client.patch(f"{_P}/tags", json={"q-p1-26": {"add": ["user need"]}})
    r = client.delete(f"{_P}/codebook/remove-framework/garrett")
    assert r.status_code == 200, r.text

    # Tagging the same quote and another one, as the SPA now sends it.
    client.patch(f"{_P}/tags", json={"q-p1-26": {"add": ["my tag"]}})
    client.patch(f"{_P}/tags", json={"q-p1-10": {"add": ["my tag"]}})
    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        assert db.query(TagDefinition).filter(TagDefinition.name.ilike("user need")).count() == 0
    finally:
        db.close()
    assert _tags(client) == {"q-p1-26": ["my tag"], "q-p1-10": ["my tag"]}


@pytest.mark.asyncio
async def test_a_star_and_a_hide_at_once_on_a_fresh_quote_both_land(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two paths are written concurrently. Each found no QuoteState for a quote
    never starred or hidden and made one; the second commit hit the unique
    index, answered 500, and the client rolled back a gesture that was fine.
    Forced here: the star is held for a moment after its look-up while the hide
    is sent."""
    import threading

    import httpx

    import bristlenose.server.routes.data as data

    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url=f"sqlite:///{tmp_path}/s.db")
    held = threading.Event()
    calls = {"n": 0}
    real_now = data._now

    def now_holding_the_first_caller() -> datetime:
        calls["n"] += 1
        if calls["n"] == 1:
            held.wait(5)
        return real_now()

    monkeypatch.setattr(data, "_now", now_holding_the_first_caller)
    headers = {"Authorization": f"Bearer {app.state.auth_token}"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8150") as c:
        star = asyncio.create_task(
            c.patch(f"{_P}/starred", json={"q-p1-10": True}, headers=headers)
        )
        await asyncio.sleep(0.2)
        hide_task = asyncio.create_task(
            c.patch(f"{_P}/hidden", json={"q-p1-10": True}, headers=headers)
        )
        await asyncio.sleep(0.3)  # the hide has committed, or waits on the star's write
        held.set()
        star_answer = await star
        hide = await hide_task
        assert hide.status_code == 200, hide.text
        assert star_answer.status_code == 200, star_answer.text
        assert (await c.get(f"{_P}/starred", headers=headers)).json() == {"q-p1-10": True}
        assert (await c.get(f"{_P}/hidden", headers=headers)).json() == {"q-p1-10": True}
