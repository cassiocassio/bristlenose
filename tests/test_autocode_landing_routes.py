"""AutoCode landing, Phase 1, at the routes (docs/design-autocode-landing-plan.md).

How each decision was made (``decided_by``), a tag removed on a card as the
researcher's exclusion (review 1), the export's accepted tags only (D28), the
proposals cursor and the counts by confidence, the jobs list the Mac reads (review
10), and the busy route's progress (review 11). The engine half (per-batch saving,
catch-up lines read at save time, the Signals rebuild) is in
``tests/test_autocode_batch_save.py``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.models import AutoCodeJob, ProposedTag, Quote
from tests.conftest import AuthTestClient
from tests.test_serve_autocode_api import _FIXTURE_DIR, _import_garrett, _proposal_count

BASE = "/api/projects/1"


@pytest.fixture()
def seeded() -> tuple[TestClient, list[int], list[int]]:
    """Garrett installed, a completed job, one pending proposal per quote at 0.5, 0.6,
    0.7, 0.8. Returns (client, proposal ids in that order, tag ids)."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    tag_ids = _import_garrett(app)
    db = app.state.db_factory()
    try:
        quotes = db.query(Quote).filter_by(project_id=1).order_by(Quote.id).all()
        job = AutoCodeJob(
            project_id=1, framework_id="garrett", status="completed",
            total_quotes=len(quotes), processed_quotes=len(quotes),
            proposed_count=len(quotes), completed_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.flush()
        ids = []
        for i, quote in enumerate(quotes):
            p = ProposedTag(
                job_id=job.id, quote_id=quote.id, tag_definition_id=tag_ids[i],
                confidence=0.5 + i * 0.1, rationale=f"r{i}",
            )
            db.add(p)
            db.flush()
            ids.append(p.id)
        db.commit()
    finally:
        db.close()
    return AuthTestClient(app), ids, tag_ids


def _proposal(client: TestClient, pid: int) -> ProposedTag:
    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        p = db.get(ProposedTag, pid)
        assert p is not None
        db.expunge(p)
        return p
    finally:
        db.close()


def _dom_id(client: TestClient, pid: int) -> str:
    from bristlenose.server.grounding import quote_dom_id

    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        p = db.get(ProposedTag, pid)
        assert p is not None
        q = db.get(Quote, p.quote_id)
        assert q is not None
        return quote_dom_id(q.participant_id, q.start_timecode, q.ordinal)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# How each decision was made
# ---------------------------------------------------------------------------


class TestDecidedBy:
    def test_a_proposal_accepted_or_excluded_by_hand_is_the_researchers(self, seeded) -> None:
        client, ids, _ = seeded
        assert client.post(f"{BASE}/autocode/proposals/{ids[0]}/accept").status_code == 200
        assert client.post(f"{BASE}/autocode/proposals/{ids[1]}/deny").status_code == 200
        assert (_proposal(client, ids[0]).status, _proposal(client, ids[0]).decided_by) == (
            "accepted", "researcher")
        assert (_proposal(client, ids[1]).status, _proposal(client, ids[1]).decided_by) == (
            "denied", "researcher")
        assert _proposal(client, ids[2]).decided_by is None  # still pending

    def test_the_review_dialogs_lines_are_threshold_decisions(self, seeded) -> None:
        client, ids, _ = seeded
        client.post(f"{BASE}/autocode/garrett/accept-all", json={"min_confidence": 0.7})
        client.post(f"{BASE}/autocode/garrett/deny-all",
                    json={"min_confidence": 0.0, "max_confidence": 0.6})
        got = [(_proposal(client, i).status, _proposal(client, i).decided_by) for i in ids]
        assert got == [
            ("denied", "threshold"), ("pending", None),
            ("accepted", "threshold"), ("accepted", "threshold"),
        ]

    def test_the_house_defaults_cut_is_a_threshold_decision(self, seeded) -> None:
        from bristlenose.server.routes.autocode import accept_at_default_cutoff

        client, ids, _ = seeded
        accept_at_default_cutoff(client.app.state.db_factory, 1, "garrett", 0.7)  # type: ignore[attr-defined]
        assert [_proposal(client, i).decided_by for i in ids] == [
            None, None, "threshold", "threshold"]

    def test_the_proposals_route_says_how_each_was_decided(self, seeded) -> None:
        client, ids, _ = seeded
        client.post(f"{BASE}/autocode/proposals/{ids[3]}/accept")
        rows = client.get(f"{BASE}/autocode/garrett/proposals?min_confidence=0").json()
        by_id = {r["id"]: r["decided_by"] for r in rows["proposals"]}
        assert by_id == {ids[0]: None, ids[1]: None, ids[2]: None, ids[3]: "researcher"}


# ---------------------------------------------------------------------------
# A tag removed on a quote card (review 1)
# ---------------------------------------------------------------------------


def _accept(client: TestClient, pid: int) -> None:
    assert client.post(f"{BASE}/autocode/proposals/{pid}/accept").status_code == 200


class TestRemovedOnACard:
    def test_patch_removing_an_accepted_autocode_tag_excludes_it_by_the_researcher(
        self, seeded,
    ) -> None:
        client, ids, tag_ids = seeded
        client.post(f"{BASE}/autocode/garrett/accept-all", json={"min_confidence": 0.5})
        dom = _dom_id(client, ids[2])
        resp = client.patch(f"{BASE}/tags", json={dom: {"remove_ids": [tag_ids[2]]}})
        assert resp.status_code == 200
        removed = _proposal(client, ids[2])
        assert (removed.status, removed.decided_by) == ("denied", "researcher")
        assert removed.reviewed_at is not None
        # The others' tags were not removed: their decisions are untouched.
        for other in (ids[0], ids[1], ids[3]):
            assert (_proposal(client, other).status, _proposal(client, other).decided_by) == (
                "accepted", "threshold")

    def test_patch_removing_by_name_is_the_same_exclusion(self, seeded) -> None:
        client, ids, tag_ids = seeded
        _accept(client, ids[0])
        db = client.app.state.db_factory()  # type: ignore[attr-defined]
        try:
            from bristlenose.server.models import TagDefinition

            td = db.get(TagDefinition, tag_ids[0])
            assert td is not None
            name = td.name
        finally:
            db.close()
        client.patch(f"{BASE}/tags", json={_dom_id(client, ids[0]): {"remove": [name]}})
        assert _proposal(client, ids[0]).decided_by == "researcher"
        assert _proposal(client, ids[0]).status == "denied"

    @pytest.mark.filterwarnings("error::sqlalchemy.exc.SAWarning")
    def test_removed_and_put_back_in_one_request_is_not_an_exclusion(self, seeded) -> None:
        client, ids, tag_ids = seeded
        _accept(client, ids[1])
        dom = _dom_id(client, ids[1])
        client.patch(f"{BASE}/tags", json={
            dom: {"remove_ids": [tag_ids[1]], "add_ids": [tag_ids[1]]},
        })
        assert _proposal(client, ids[1]).status == "accepted"

    def test_put_dropping_an_accepted_autocode_tag_excludes_it(self, seeded) -> None:
        client, ids, _ = seeded
        _accept(client, ids[0])
        _accept(client, ids[3])
        whole = client.get(f"{BASE}/tags").json()
        whole[_dom_id(client, ids[0])] = []  # named, with its tag taken off
        assert client.put(f"{BASE}/tags", json=whole).status_code == 200
        assert (_proposal(client, ids[0]).status, _proposal(client, ids[0]).decided_by) == (
            "denied", "researcher")
        # Round-tripped, so kept: still the researcher's acceptance.
        assert (_proposal(client, ids[3]).status, _proposal(client, ids[3]).decided_by) == (
            "accepted", "researcher")

    def test_put_leaves_a_quote_it_could_not_place_alone(self, seeded) -> None:
        """A whole-map PUT whose id for a quote no longer resolves (a re-run moved it)
        loses that quote's tags to the replace, not to a researcher's judgement."""
        client, ids, _ = seeded
        _accept(client, ids[0])
        _accept(client, ids[3])
        whole = client.get(f"{BASE}/tags").json()
        whole["q-p9-999"] = whole.pop(_dom_id(client, ids[0]))  # an id nobody has
        assert client.put(f"{BASE}/tags", json=whole).status_code == 200
        assert (_proposal(client, ids[0]).status, _proposal(client, ids[0]).decided_by) == (
            "accepted", "researcher")

    def test_a_pending_proposal_is_not_touched_by_a_removal(self, seeded) -> None:
        """A tag the researcher added by hand that a pending proposal happens to name
        is theirs; removing it leaves the proposal tentative."""
        client, ids, tag_ids = seeded
        dom = _dom_id(client, ids[1])
        client.patch(f"{BASE}/tags", json={dom: {"add_ids": [tag_ids[1]]}})
        client.patch(f"{BASE}/tags", json={dom: {"remove_ids": [tag_ids[1]]}})
        assert (_proposal(client, ids[1]).status, _proposal(client, ids[1]).decided_by) == (
            "pending", None)


# ---------------------------------------------------------------------------
# The export carries accepted tags only (D28)
# ---------------------------------------------------------------------------


def _export(client: TestClient) -> dict:
    html = client.get(f"{BASE}/export").text
    marker = "window.BRISTLENOSE_EXPORT="
    start = html.index(marker) + len(marker)
    return json.loads(html[start:html.index(";\n</script>", start)])


def test_the_export_carries_no_tentative_tags(seeded) -> None:
    client, ids, _ = seeded
    _accept(client, ids[3])
    live = client.get(f"{BASE}/quotes").json()
    assert _proposal_count(live) == 3  # the page shows the tentative ones

    endpoints = _export(client)["endpoints"]
    assert _proposal_count(endpoints["/quotes"]) == 0
    # Nor through Signals: no card weighs a tentative tag, and none is counted.
    live_signals = client.get(f"{BASE}/signals/codebooks").json()["codebooks"]
    assert any(c["source_breakdown"]["pending"] for c in live_signals)
    assert endpoints["/signals/codebooks"]["codebooks"]
    for codebook in endpoints["/signals/codebooks"]["codebooks"]:
        assert codebook["source_breakdown"]["pending"] == 0
    tags = [t for g in endpoints["/codebook"]["groups"] for t in g["tags"]]
    assert all(t["tentative_count"] == 0 for t in tags)
    # The accepted one is a tag like any other.
    assert sum(t["count"] for t in tags) >= 1


# ---------------------------------------------------------------------------
# Reading what is new: the proposals cursor and the counts by confidence
# ---------------------------------------------------------------------------


def test_the_proposals_cursor_lists_only_what_was_saved_after_it(seeded) -> None:
    client, ids, _ = seeded
    url = f"{BASE}/autocode/garrett/proposals?min_confidence=0"
    assert {r["id"] for r in client.get(url).json()["proposals"]} == set(ids)
    newer = client.get(f"{url}&since_id={ids[1]}").json()
    assert {r["id"] for r in newer["proposals"]} == {ids[2], ids[3]}
    assert newer["total"] == 2
    assert client.get(f"{url}&since_id={ids[3]}").json()["proposals"] == []


def test_the_status_read_counts_proposals_by_confidence_when_asked(seeded) -> None:
    client, ids, _ = seeded
    url = f"{BASE}/autocode/garrett/status"
    assert client.get(url).json()["confidence_counts"] is None  # the chip's poll: cheap
    _accept(client, ids[3])  # 0.8
    client.post(f"{BASE}/autocode/proposals/{ids[0]}/deny")  # 0.5
    bins = client.get(f"{url}?counts=true").json()["confidence_counts"]
    assert len(bins) == 20
    assert [round(b["lower"], 2) for b in bins[:2]] == [0.0, 0.05]
    nonzero = {
        round(b["lower"], 2): (b["accepted"], b["tentative"], b["excluded"])
        for b in bins if b["accepted"] or b["tentative"] or b["excluded"]
    }
    # 0.6 and 0.7 come out of float arithmetic (0.5 + i * 0.1) and still land on their
    # own band, not the one below.
    assert nonzero == {0.5: (0, 0, 1), 0.6: (0, 1, 0), 0.7: (0, 1, 0), 0.8: (1, 0, 0)}


def test_the_counts_leave_out_a_hidden_quote(seeded) -> None:
    client, ids, _ = seeded
    client.patch(f"{BASE}/hidden", json={_dom_id(client, ids[1]): True})
    bins = client.get(f"{BASE}/autocode/garrett/status?counts=true").json()["confidence_counts"]
    assert sum(b["tentative"] for b in bins) == 3


def test_a_confidence_of_one_is_in_the_top_band(seeded) -> None:
    client, ids, _ = seeded
    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        p = db.get(ProposedTag, ids[0])
        assert p is not None
        p.confidence = 1.0
        db.commit()
    finally:
        db.close()
    bins = client.get(f"{BASE}/autocode/garrett/status?counts=true").json()["confidence_counts"]
    assert bins[19]["tentative"] == 1


# ---------------------------------------------------------------------------
# The jobs list the Mac reads (review 10)
# ---------------------------------------------------------------------------


def _jobs_client(rows: list[dict]) -> TestClient:
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    db = app.state.db_factory()
    try:
        for row in rows:
            db.add(AutoCodeJob(project_id=1, **row))
        db.commit()
    finally:
        db.close()
    return AuthTestClient(app)


_DONE = datetime(2026, 11, 1, tzinfo=timezone.utc)


def _the_jobs() -> list[dict]:
    return [
        {"framework_id": "garrett", "status": "running", "total_quotes": 4,
         "processed_quotes": 2, "started_at": datetime(2026, 11, 2)},
        {"framework_id": "norman", "status": "cancelled", "started_at": datetime(2026, 11, 3)},
        {"framework_id": "uxr", "status": "failed", "failure_kind": "out_of_credit",
         "started_at": datetime(2026, 11, 4)},
        {"framework_id": "plato", "status": "completed", "failure_kind": "rate_limited",
         "completed_at": _DONE, "started_at": datetime(2026, 11, 5)},
        # Never listed: a clean apply, and an applied codebook's failed catch-up.
        {"framework_id": "nielsen", "status": "completed", "completed_at": _DONE,
         "started_at": datetime(2026, 11, 6)},
        {"framework_id": "yablonski", "status": "failed", "failure_kind": "invalid_key",
         "completed_at": _DONE, "started_at": datetime(2026, 11, 7)},
    ]


def test_the_jobs_list_is_unchanged_without_asking_for_ended_runs() -> None:
    client = _jobs_client(_the_jobs())
    body = client.get(f"{BASE}/autocode/jobs").json()
    assert body == {"jobs": [{
        "framework_id": "garrett", "title": body["jobs"][0]["title"], "status": "running",
        "completed_at": None, "processed_quotes": 2, "total_quotes": 4,
    }]}


def test_the_jobs_list_includes_ended_first_applies_when_asked() -> None:
    client = _jobs_client(_the_jobs())
    jobs = client.get(f"{BASE}/autocode/jobs?include_ended=true").json()["jobs"]
    got = {j["framework_id"]: (j["status"], j["failure_kind"]) for j in jobs}
    assert got == {
        "garrett": ("running", ""),
        "norman": ("cancelled", ""),  # Stopped
        "uxr": ("failed", "out_of_credit"),  # Out of credit
        "plato": ("completed", "rate_limited"),  # Partial run
    }


# ---------------------------------------------------------------------------
# The busy route's progress (review 11)
# ---------------------------------------------------------------------------


def test_background_work_reports_a_progress_count_that_moves() -> None:
    from bristlenose.server import busy

    app = create_app(dev=True, db_url="sqlite://")
    client = AuthTestClient(app)
    before = client.get("/api/background-work").json()
    assert isinstance(before["progress"], int)
    busy.note_progress(25)
    after = client.get("/api/background-work").json()
    assert after["progress"] == before["progress"] + 25
    assert set(after) == {"busy", "kinds", "progress"}



def test_the_review_dialogs_lines_ask_for_a_signals_rebuild(seeded, monkeypatch) -> None:
    """A re-cut changes the accepted tags Signals counts (review 9); a bulk action
    without the dialog's lines asks nothing."""
    from bristlenose.server.routes import autocode as autocode_routes

    client, _, _ = seeded
    asked: list[int] = []
    monkeypatch.setattr(autocode_routes, "recut_made", lambda app, pid: asked.append(pid))
    client.post(f"{BASE}/autocode/garrett/accept-all")
    client.post(f"{BASE}/autocode/garrett/deny-all")
    assert asked == []
    client.post(f"{BASE}/autocode/garrett/accept-all", json={"min_confidence": 0.7})
    client.post(f"{BASE}/autocode/garrett/deny-all",
                json={"min_confidence": 0.0, "max_confidence": 0.5})
    assert asked == [1, 1]
