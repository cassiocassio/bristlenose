"""AutoCode landing, Phase 2: the re-cuttable review, at the routes.

``POST …/autocode/{fw}/recut`` is the review dialog's Apply: it moves only threshold
decisions and pending proposals (D2), only those whose zone changes between the stored
lines and the new ones (D26), and removes only a tag AutoCode made (review 1). The
per-row accept and deny change a decided proposal only when the review dialog sends
its explicit override; every other call is still refused with 409 (D34).
docs/design-autocode-landing-plan.md § Phase 2.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.grounding import quote_dom_id
from bristlenose.server.models import AutoCodeJob, ProposedTag, Quote, QuoteTag
from tests.conftest import AuthTestClient
from tests.test_serve_autocode_api import _FIXTURE_DIR, _import_garrett

BASE = "/api/projects/1"
RECUT = f"{BASE}/autocode/garrett/recut"

#: One proposal per quote, in quote order.
CONFIDENCES = (0.5, 0.6, 0.7, 0.8)


@pytest.fixture()
def run() -> tuple[TestClient, list[int]]:
    """Garrett installed, a completed job, one pending proposal per quote at 0.5, 0.6,
    0.7 and 0.8, no lines stored. Returns (client, proposal ids in that order)."""
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
        for quote, tag_id, confidence in zip(quotes, tag_ids, CONFIDENCES, strict=False):
            p = ProposedTag(job_id=job.id, quote_id=quote.id, tag_definition_id=tag_id,
                            confidence=confidence, rationale="r")
            db.add(p)
            db.flush()
            ids.append(p.id)
        db.commit()
    finally:
        db.close()
    return AuthTestClient(app), ids


def _set(client: TestClient, pid: int, status: str, decided_by: str | None,
         tag_source: str | None = None) -> None:
    """Put a proposal in a state directly, with its quote's tag (by ``tag_source``) or none."""
    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        p = db.get(ProposedTag, pid)
        assert p is not None
        p.status = status
        p.decided_by = decided_by
        p.reviewed_at = None if status == "pending" else datetime.now(timezone.utc)
        db.query(QuoteTag).filter_by(
            quote_id=p.quote_id, tag_definition_id=p.tag_definition_id).delete()
        if tag_source is not None:
            db.add(QuoteTag(quote_id=p.quote_id, tag_definition_id=p.tag_definition_id,
                            source=tag_source))
        db.commit()
    finally:
        db.close()


def _store_lines(client: TestClient, lower: float | None, upper: float | None) -> None:
    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        job = db.query(AutoCodeJob).filter_by(framework_id="garrett").one()
        job.applied_lower_threshold = lower
        job.applied_upper_threshold = upper
        db.commit()
    finally:
        db.close()


def _state(client: TestClient, pid: int) -> tuple[str, str | None, str | None]:
    """(status, decided_by, the source of the quote's tag or None)."""
    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        p = db.get(ProposedTag, pid)
        assert p is not None
        qt = db.query(QuoteTag).filter_by(
            quote_id=p.quote_id, tag_definition_id=p.tag_definition_id).first()
        return p.status, p.decided_by, (qt.source if qt else None)
    finally:
        db.close()


def _states(client: TestClient, ids: list[int]) -> list[tuple[str, str | None, str | None]]:
    return [_state(client, i) for i in ids]


def _recut(client: TestClient, lower: float, upper: float) -> dict:
    resp = client.post(RECUT, json={"lower": lower, "upper": upper})
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture()
def signals(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Every Signals re-cut rebuild the routes ask for, by project id."""
    from bristlenose.server.routes import autocode as autocode_routes

    asked: list[int] = []
    monkeypatch.setattr(autocode_routes, "recut_made", lambda app, pid: asked.append(pid))
    return asked


# ---------------------------------------------------------------------------
# D26: only a zone change moves a proposal
# ---------------------------------------------------------------------------


def test_apply_with_the_lines_unmoved_changes_nothing(run, signals) -> None:
    """Earlier passes left the run unlike a clean cut at the stored lines (a tag accepted
    live below the accept line, a pending one above it, an exclusion above the exclude
    line). Apply at the same lines leaves every one of them as it is."""
    client, ids = run
    _store_lines(client, 0.30, 0.70)
    _set(client, ids[0], "accepted", "threshold", "autocode")  # 0.5, accepted live
    _set(client, ids[3], "denied", "threshold")  # 0.8, excluded by an earlier pass
    # ids[1] (0.6) and ids[2] (0.7) stay pending; a clean cut would accept 0.7.
    before = _states(client, ids)

    assert _recut(client, 0.30, 0.70) == {"accepted": 0, "tentative": 0, "excluded": 0}
    assert _states(client, ids) == before
    assert signals == []


def test_a_recut_moves_only_what_changes_zone(run) -> None:
    """Stored 0.30 / 0.70, re-cut to 0.55 / 0.75: 0.5 leaves tentative for excluded and
    0.7 leaves accepted for tentative; 0.6 (tentative both times) and 0.8 (accepted
    both times) keep whatever they were, a live acceptance and a pending one alike."""
    client, ids = run
    _store_lines(client, 0.30, 0.70)
    _set(client, ids[1], "accepted", "threshold", "autocode")  # 0.6, accepted live
    _set(client, ids[2], "accepted", "threshold", "autocode")  # 0.7

    assert _recut(client, 0.55, 0.75) == {"accepted": 0, "tentative": 1, "excluded": 1}
    assert _states(client, ids) == [
        ("denied", "threshold", None),
        ("accepted", "threshold", "autocode"),
        ("pending", None, None),
        ("pending", None, None),
    ]


def test_researcher_and_unknown_decisions_never_move(run) -> None:
    client, ids = run
    _store_lines(client, 0.30, 0.70)
    _set(client, ids[0], "accepted", "researcher", "autocode")  # 0.5
    _set(client, ids[3], "denied", "unknown")  # 0.8

    _recut(client, 0.95, 1.0)  # everything excluded
    assert _state(client, ids[0]) == ("accepted", "researcher", "autocode")
    assert _state(client, ids[3]) == ("denied", "unknown", None)
    _recut(client, 0.0, 0.05)  # everything accepted
    assert _state(client, ids[0]) == ("accepted", "researcher", "autocode")
    assert _state(client, ids[3]) == ("denied", "unknown", None)
    # The movable ones did move, both times.
    assert [_state(client, i)[0] for i in ids[1:3]] == ["accepted", "accepted"]


def test_a_never_cut_run_gets_a_plain_cut(run) -> None:
    """No lines stored: nothing has been cut, so the first Apply sorts every pending
    proposal by the new lines, as the dialog's Apply always did."""
    client, ids = run
    _recut(client, 0.30, 0.70)
    assert [s[0] for s in _states(client, ids)] == ["pending", "pending", "accepted", "accepted"]


# ---------------------------------------------------------------------------
# Tags: AutoCode's are made and removed, a hand-added one never is (review 1)
# ---------------------------------------------------------------------------


def test_tentative_to_accepted_makes_an_autocode_tag_and_back_removes_only_it(run) -> None:
    client, ids = run
    _store_lines(client, 0.30, 0.70)
    _recut(client, 0.30, 0.60)
    assert _state(client, ids[1]) == ("accepted", "threshold", "autocode")
    _recut(client, 0.30, 0.70)
    assert _state(client, ids[1]) == ("pending", None, None)
    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        p = db.get(ProposedTag, ids[1])
        assert p is not None and p.reviewed_at is None
    finally:
        db.close()


@pytest.mark.parametrize("lower, upper", [(0.30, 0.75), (0.75, 0.80)])
def test_a_recut_never_removes_a_tag_added_by_hand(run, lower, upper) -> None:
    """0.7 accepted at the stored lines, its quote's tag added by the researcher; a
    re-cut that makes it tentative, or excludes it, leaves that tag where it is."""
    client, ids = run
    _store_lines(client, 0.30, 0.70)
    _set(client, ids[2], "accepted", "threshold", "human")
    _recut(client, lower, upper)
    status, _, source = _state(client, ids[2])
    assert status in ("pending", "denied")
    assert source == "human"


def test_an_accepted_proposal_whose_quote_has_the_tag_by_hand_adds_no_second(run) -> None:
    client, ids = run
    _set(client, ids[3], "pending", None, "human")
    _recut(client, 0.30, 0.70)
    assert _state(client, ids[3]) == ("accepted", "threshold", "human")


def test_a_recut_leaves_a_hidden_quotes_proposal_alone(run) -> None:
    client, ids = run
    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        p = db.get(ProposedTag, ids[3])
        assert p is not None
        q = db.get(Quote, p.quote_id)
        assert q is not None
        dom_id = quote_dom_id(q.participant_id, q.start_timecode, q.ordinal)
    finally:
        db.close()
    client.patch(f"{BASE}/hidden", json={dom_id: True})
    _recut(client, 0.30, 0.70)
    assert _state(client, ids[3]) == ("pending", None, None)
    assert _state(client, ids[2])[0] == "accepted"


# ---------------------------------------------------------------------------
# The lines, and Signals
# ---------------------------------------------------------------------------


def test_the_lines_are_stored_snapped(run) -> None:
    client, ids = run
    _recut(client, 0.30000000000000004, 0.7000000000000001)
    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        job = db.query(AutoCodeJob).filter_by(framework_id="garrett").one()
        assert (job.applied_lower_threshold, job.applied_upper_threshold) == (0.3, 0.7)
    finally:
        db.close()


@pytest.mark.parametrize("body", [
    {"lower": 0.33, "upper": 0.7},  # off the grid
    {"lower": 0.8, "upper": 0.7},  # exclude line above the accept line
    {"lower": 0.3},  # a line missing
    {"lower": -0.05, "upper": 0.7},
])
def test_lines_off_the_grid_or_crossed_are_refused(run, body) -> None:
    client, ids = run
    before = _states(client, ids)
    assert client.post(RECUT, json=body).status_code == 422
    assert _states(client, ids) == before


def test_a_recut_that_moves_something_asks_for_a_signals_rebuild(run, signals) -> None:
    client, _ = run
    _store_lines(client, 0.30, 0.70)
    _recut(client, 0.30, 0.70)
    assert signals == []
    _recut(client, 0.30, 0.60)
    assert signals == [1]


def test_a_recut_of_an_unknown_codebook_is_404(run) -> None:
    client, _ = run
    resp = client.post(f"{BASE}/autocode/norman/recut", json={"lower": 0.3, "upper": 0.7})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Per-row decisions: the dialog's explicit override on a decided row (D34)
# ---------------------------------------------------------------------------


def _row(client: TestClient, pid: int, verb: str, override: bool = True) -> None:
    resp = client.post(f"{BASE}/autocode/proposals/{pid}/{verb}",
                       json={"override": True} if override else {})
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("status, decided_by", [
    ("accepted", "threshold"), ("accepted", "researcher"),
    ("denied", "threshold"), ("denied", "unknown"),
])
@pytest.mark.parametrize("verb", ["accept", "deny"])
@pytest.mark.parametrize("body", [None, {}, {"override": False}])
def test_an_ordinary_call_on_a_decided_proposal_is_still_refused(
    run, status, decided_by, verb, body,
) -> None:
    """D34: only the explicit override changes a decided proposal. A quote card's call,
    or the dialog's on a row it still thinks pending, gets the 409 "reviewed
    elsewhere" both clients handle, naming which way it went, and nothing changes."""
    client, ids = run
    _set(client, ids[2], status, decided_by, "autocode" if status == "accepted" else None)
    before = _state(client, ids[2])
    url = f"{BASE}/autocode/proposals/{ids[2]}/{verb}"
    resp = client.post(url) if body is None else client.post(url, json=body)
    assert resp.status_code == 409
    assert resp.json()["reason"] == f"proposal_{status}"
    assert _state(client, ids[2]) == before


def test_an_ordinary_deny_of_a_pending_proposal_leaves_tags_as_shipped(run) -> None:
    """The override's tag removal is for a decided row only: an ordinary deny of a
    pending proposal touches no tag, as it never did, whoever made the one its quote
    carries."""
    client, ids = run
    for pid, source in ((ids[1], "human"), (ids[2], "autocode")):
        _set(client, pid, "pending", None, source)
        _row(client, pid, "deny", override=False)
        assert _state(client, pid) == ("denied", "researcher", source)


def test_an_override_on_a_pending_proposal_is_an_ordinary_decision(run) -> None:
    client, ids = run
    _row(client, ids[1], "accept")
    assert _state(client, ids[1]) == ("accepted", "researcher", "autocode")


def test_excluding_an_accepted_proposal_takes_autocodes_tag_off(run) -> None:
    client, ids = run
    _set(client, ids[2], "accepted", "threshold", "autocode")
    _row(client, ids[2], "deny")
    assert _state(client, ids[2]) == ("denied", "researcher", None)


def test_excluding_an_accepted_proposal_keeps_a_tag_added_by_hand(run) -> None:
    client, ids = run
    _set(client, ids[2], "accepted", "threshold", "human")
    _row(client, ids[2], "deny")
    assert _state(client, ids[2]) == ("denied", "researcher", "human")


def test_accepting_an_excluded_proposal_makes_autocodes_tag(run) -> None:
    client, ids = run
    _set(client, ids[0], "denied", "threshold")
    _row(client, ids[0], "accept")
    assert _state(client, ids[0]) == ("accepted", "researcher", "autocode")


def test_accepting_a_threshold_acceptance_pins_it(run) -> None:
    """The same decision made by hand is the researcher's: no re-cut moves it after."""
    client, ids = run
    _store_lines(client, 0.30, 0.70)
    _set(client, ids[3], "accepted", "threshold", "autocode")
    _row(client, ids[3], "accept")
    assert _state(client, ids[3]) == ("accepted", "researcher", "autocode")
    _recut(client, 0.30, 0.95)
    assert _state(client, ids[3]) == ("accepted", "researcher", "autocode")


def test_an_overridden_exclusion_is_pinned_against_a_recut(run) -> None:
    """A threshold exclusion taken back by hand stays accepted when a re-cut would
    exclude it again (D2)."""
    client, ids = run
    _store_lines(client, 0.30, 0.70)
    _set(client, ids[0], "denied", "threshold")  # 0.5, excluded
    _row(client, ids[0], "accept")
    _recut(client, 0.60, 0.70)
    assert _state(client, ids[0]) == ("accepted", "researcher", "autocode")
