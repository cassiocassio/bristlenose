"""AutoCode landing, Phase 1, at the routes (docs/design-autocode-landing-plan.md).

How each decision was made (``decided_by``), a tag removed on a card as the
researcher's exclusion (review 1) and its Undo (D30), tentative tags shown only
for applied jobs, the export's included (D32, D28 reversed), the
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


@pytest.fixture(autouse=True)
def _export_bundle_stub(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """The export route needs the single-file export build, which is gitignored and
    which CI's pytest cells never build; without a stub every export read here is a
    500 (red on every cell of the 0.48.0 strict run). Same stub as the export tests."""
    from bristlenose.server.routes import export as export_mod

    bundle = tmp_path_factory.mktemp("export-bundle")
    (bundle / "app.js").write_text("// stub", encoding="utf-8")
    (bundle / "app.css").write_text("/* stub */", encoding="utf-8")
    monkeypatch.setattr(export_mod, "_EXPORT_STATIC_DIR", bundle)


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
        from bristlenose.server.autocode import cut_first_apply

        client, ids, _ = seeded
        db = client.app.state.db_factory()  # type: ignore[attr-defined]
        try:
            cut_first_apply(db, db.query(AutoCodeJob).one().id)
            db.commit()
        finally:
            db.close()
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

    def test_undo_of_a_removal_puts_the_proposal_back(self, seeded) -> None:
        """Undo of "remove tag" is a second request that adds the tag back with its
        source (``restoreTag``, decision #14), after the removal marked the proposal
        excluded: the exclusion goes with it, accepted by the researcher (D30)."""
        from bristlenose.server.models import QuoteTag

        client, ids, tag_ids = seeded
        client.post(f"{BASE}/autocode/garrett/accept-all", json={"min_confidence": 0.7})
        dom = _dom_id(client, ids[2])
        client.patch(f"{BASE}/tags", json={dom: {"remove_ids": [tag_ids[2]]}})
        assert _proposal(client, ids[2]).status == "denied"
        resp = client.patch(f"{BASE}/tags", json={
            dom: {"add_ids": [tag_ids[2]], "source": "autocode"},
        })
        assert resp.status_code == 200
        back = _proposal(client, ids[2])
        assert (back.status, back.decided_by) == ("accepted", "researcher")
        db = client.app.state.db_factory()  # type: ignore[attr-defined]
        try:
            qt = db.query(QuoteTag).filter_by(
                quote_id=back.quote_id, tag_definition_id=tag_ids[2]).one()
            assert qt.source == "autocode"
        finally:
            db.close()
        # The other accepted proposal was not touched.
        assert (_proposal(client, ids[3]).status, _proposal(client, ids[3]).decided_by) == (
            "accepted", "threshold")

    def test_a_tag_put_back_by_hand_undoes_an_exclusion_too(self, seeded) -> None:
        """Any source: the excluded proposal of the dialog's exclude line, its tag typed
        back on the card by the researcher, is theirs and accepted."""
        client, ids, tag_ids = seeded
        client.post(f"{BASE}/autocode/garrett/deny-all",
                    json={"min_confidence": 0.0, "max_confidence": 0.6})
        assert (_proposal(client, ids[0]).status, _proposal(client, ids[0]).decided_by) == (
            "denied", "threshold")
        client.patch(f"{BASE}/tags", json={_dom_id(client, ids[0]): {"add_ids": [tag_ids[0]]}})
        assert (_proposal(client, ids[0]).status, _proposal(client, ids[0]).decided_by) == (
            "accepted", "researcher")

    def test_put_adding_back_an_excluded_tag_undoes_the_exclusion(self, seeded) -> None:
        client, ids, _ = seeded
        _accept(client, ids[0])
        whole = client.get(f"{BASE}/tags").json()
        dom = _dom_id(client, ids[0])
        names = whole[dom]
        whole[dom] = []
        client.put(f"{BASE}/tags", json=whole)
        assert _proposal(client, ids[0]).status == "denied"
        whole[dom] = names
        client.put(f"{BASE}/tags", json=whole)
        assert (_proposal(client, ids[0]).status, _proposal(client, ids[0]).decided_by) == (
            "accepted", "researcher")

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
# Tentative tags: applied jobs only (D32), and the export carries them (D28 reversed)
# ---------------------------------------------------------------------------


def _export(client: TestClient) -> dict:
    html = client.get(f"{BASE}/export").text
    marker = "window.BRISTLENOSE_EXPORT="
    start = html.index(marker) + len(marker)
    return json.loads(html[start:html.index(";\n</script>", start)])


def _tentative(quotes: dict, codebook: dict, signals: dict) -> tuple[int, int, int]:
    """(proposals on the quote cards, the Codebook lens's tentative counts, Signals'
    pending), each summed over the study."""
    tags = [t for g in codebook["groups"] for t in g["tags"]]
    return (
        _proposal_count(quotes),
        sum(t["tentative_count"] for t in tags),
        sum(c["source_breakdown"]["pending"] for c in signals["codebooks"]),
    )


def _live(client: TestClient) -> tuple[int, int, int]:
    return _tentative(
        client.get(f"{BASE}/quotes").json(),
        client.get(f"{BASE}/codebook").json(),
        client.get(f"{BASE}/signals/codebooks").json(),
    )


def _embedded(client: TestClient) -> tuple[int, int, int]:
    endpoints = _export(client)["endpoints"]
    return _tentative(
        endpoints["/quotes"], endpoints["/codebook"], endpoints["/signals/codebooks"],
    )


def _unfinish(client: TestClient, status: str) -> None:
    """Make the seeded job a first apply that never finished."""
    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        job = db.query(AutoCodeJob).one()
        job.status = status
        job.completed_at = None
        db.commit()
    finally:
        db.close()


def test_a_finished_runs_tentative_tags_show_and_the_export_carries_them(seeded) -> None:
    """The export carries tentative tags as shipped (dashed tags, the pale bar
    segments, their weighted part in Signals): D28 is reversed."""
    client, ids, _ = seeded
    _accept(client, ids[3])
    assert _live(client) == (3, 3, 3)
    assert _embedded(client) == (3, 3, 3)


@pytest.mark.parametrize("status", ["running", "pending", "failed", "cancelled"])
def test_a_first_apply_not_finished_shows_no_tentative_tags_anywhere(seeded, status) -> None:
    """Until Phase 4's playback, a run still coding, stopped or failed shows none of
    its proposals, on the page or in the export (D32): its batches are saved as they
    answer, but before Phase 1 they did not exist until it finished."""
    client, _, _ = seeded
    _unfinish(client, status)
    assert _live(client) == (0, 0, 0)
    assert _embedded(client) == (0, 0, 0)


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


def test_the_ended_list_carries_what_the_mac_row_needs() -> None:
    """``started_at`` is the identity the Mac remembers a seen line by; a running catch-up's
    own counts are its "AutoCode · N of M" (D40). Only the wide answer carries them."""
    rows = [*_the_jobs(), {
        "framework_id": "nielsen2", "status": "running", "completed_at": _DONE,
        "total_quotes": 40, "processed_quotes": 40, "catch_up_total": 12,
        "catch_up_processed": 5, "started_at": datetime(2026, 11, 8),
    }]
    client = _jobs_client(rows)
    jobs = {j["framework_id"]: j
            for j in client.get(f"{BASE}/autocode/jobs?include_ended=true").json()["jobs"]}
    assert jobs["norman"]["started_at"].startswith("2026-11-03")
    assert (jobs["nielsen2"]["catch_up_total"], jobs["nielsen2"]["catch_up_processed"]) == (12, 5)
    narrow = client.get(f"{BASE}/autocode/jobs").json()["jobs"]
    assert all("started_at" not in j and "catch_up_total" not in j for j in narrow)


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



def test_the_review_dialogs_lines_ask_for_a_signals_rebuild_only_when_they_move_one(
    seeded, monkeypatch,
) -> None:
    """A re-cut that accepted or denied something changes what Signals counts (review
    9); one that moved nothing asks nothing (D31), and neither does a bulk action
    without the dialog's lines."""
    from bristlenose.server.routes import autocode as autocode_routes

    client, _, _ = seeded
    asked: list[int] = []
    monkeypatch.setattr(autocode_routes, "recut_made", lambda app, pid: asked.append(pid))
    # Nothing at or above 0.9, nothing below 0.5: no proposal moves.
    assert client.post(f"{BASE}/autocode/garrett/accept-all",
                       json={"min_confidence": 0.9}).json() == {"accepted": 0}
    assert client.post(f"{BASE}/autocode/garrett/deny-all",
                       json={"min_confidence": 0.0, "max_confidence": 0.5}).json() == {
        "denied": 0}
    assert asked == []
    client.post(f"{BASE}/autocode/garrett/accept-all", json={"min_confidence": 0.7})
    client.post(f"{BASE}/autocode/garrett/deny-all",
                json={"min_confidence": 0.0, "max_confidence": 0.6})
    assert asked == [1, 1]
    assert client.post(f"{BASE}/autocode/garrett/accept-all").json() == {"accepted": 1}
    client.post(f"{BASE}/autocode/garrett/deny-all")
    assert asked == [1, 1]


def test_the_exports_signals_report_is_the_stored_one(seeded) -> None:
    """The stored report, tentative tags weighted in, goes into the file as the lens
    reads it: nothing is taken out (D28 reversed)."""
    import asyncio

    from bristlenose.server.routes.signals import _build_codebook_analysis
    from bristlenose.server.signal_snapshots import store_completed_snapshot

    client, ids, _ = seeded
    _accept(client, ids[0])
    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        report = asyncio.run(_build_codebook_analysis(1, db=db, elaborate=False))
        store_completed_snapshot(db, 1, source="test", payload=report.model_dump(mode="json"))
        db.commit()
    finally:
        db.close()
    live = client.get(f"{BASE}/signals/snapshot").json()["snapshot"]
    assert any(c["source_breakdown"]["pending"] for c in live["codebooks"])
    assert _export(client)["endpoints"]["/signals/snapshot"]["snapshot"] == live
