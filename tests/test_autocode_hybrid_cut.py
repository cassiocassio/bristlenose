"""AutoCode landing, Phase 3: the end-of-run hybrid cut and the stopped-run settle.

Every first apply that completes, the house default's and a researcher's, ends with the
hybrid (docs/design-autocode-landing-plan.md D5): the most confident 30% of the run's
proposals accepted, never below 0.70, ties at the cut in; below 0.30 excluded; the rest
pending. The lines are stored, the accept line rounded UP to the 0.05 grid (D41). A first
apply stopped partway settles the same way and stays resumable (D27, D35); its resumed
run finishes at the stored lines. No LLM calls: the job runner is replaced where a test
goes through ``start_autocode``.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bristlenose.server import autocode_house_default as hd
from bristlenose.server.app import create_app
from bristlenose.server.autocode import accept_line_for, hybrid_cut
from bristlenose.server.models import (
    AutoCodeJob,
    CodebookGroup,
    ProposedTag,
    Quote,
    QuoteTag,
    TagDefinition,
)
from bristlenose.server.routes import autocode as routes
from bristlenose.server.routes.autocode import settle_first_apply_cut
from tests.conftest import AuthTestClient
from tests.test_serve_autocode_api import _FIXTURE_DIR, _import_garrett

READY = "bristlenose.server.routes.autocode.require_provider_ready"
SNAPSHOT = "bristlenose.server.routes.signals.materialise_completed_signal_snapshot"

# ── The rule ───────────────────────────────────────────────────────────────────────────────────


def test_the_cut_is_the_top_30_percent_never_below_the_floor() -> None:
    ten = [0.99, 0.95, 0.9, 0.88, 0.85, 0.8, 0.75, 0.7, 0.4, 0.1]
    assert hybrid_cut(ten) == 0.9  # ceil(30% of 10) = 3: 0.99, 0.95, 0.9
    assert hybrid_cut([0.9, 0.85, 0.8, 0.8, 0.8, 0.5, 0.5]) == 0.8  # ceil(2.1) = 3
    # Fewer than four proposals: still the first one (ceil, at least one).
    assert hybrid_cut([0.95, 0.75, 0.72]) == 0.95


def test_ties_at_the_cut_are_all_at_or_above_it() -> None:
    confs = [0.9, 0.9, 0.9, 0.9, 0.9, 0.5, 0.5, 0.5, 0.5, 0.5]
    cut = hybrid_cut(confs)
    assert cut == 0.9
    assert sum(c >= cut for c in confs) == 5  # all five tied, though 30% is three


def test_a_poorly_fitting_run_has_only_the_floor() -> None:
    """Phase 0a: three poorly fitting runs had every proposal at 0.10; the top 30% alone
    would have accepted all of them."""
    assert hybrid_cut([0.1] * 20) == 0.70
    assert hybrid_cut([0.65, 0.6, 0.2]) == 0.70
    assert hybrid_cut([]) == 0.70


@pytest.mark.parametrize(
    ("cut", "line"),
    [(0.70, 0.70), (0.72, 0.75), (0.75, 0.75), (0.7000000000000001, 0.70), (0.55, 0.55),
     (0.81, 0.85), (0.97, 1.0), (1.0, 1.0)],
)
def test_the_accept_line_is_the_cut_rounded_up_to_the_grid(cut: float, line: float) -> None:
    assert accept_line_for(cut) == line
    assert accept_line_for(cut) >= cut - 1e-9


# ── The step, at the routes' database ──────────────────────────────────────────────────────────


def _seeded(confidences: tuple[float, ...], *, status: str = "completed",
            framework: str = "garrett") -> tuple[FastAPI, list[int]]:
    """The smoke study (four quotes) with Garrett installed, a job of ``status`` and one
    pending proposal per quote at ``confidences``. Returns (app, proposal ids in order)."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    tag_ids = _import_garrett(app)
    db = app.state.db_factory()
    try:
        quotes = db.query(Quote).filter_by(project_id=1).order_by(Quote.id).all()
        job = AutoCodeJob(
            project_id=1, framework_id=framework, status=status,
            completed_at=datetime.now(timezone.utc) if status == "completed" else None,
        )
        db.add(job)
        db.flush()
        ids = []
        for quote, tag_id, conf in zip(quotes, tag_ids, confidences, strict=False):
            p = ProposedTag(job_id=job.id, quote_id=quote.id, tag_definition_id=tag_id,
                            confidence=conf, rationale="r")
            db.add(p)
            db.flush()
            ids.append(p.id)
        db.commit()
    finally:
        db.close()
    return app, ids


def _states(app: FastAPI, ids: list[int]) -> list[tuple[str, str | None]]:
    db = app.state.db_factory()
    try:
        out = []
        for pid in ids:
            p = db.get(ProposedTag, pid)
            assert p is not None
            out.append((p.status, p.decided_by))
        return out
    finally:
        db.close()


def _lines(app: FastAPI, framework: str = "garrett") -> tuple[float | None, float | None]:
    db = app.state.db_factory()
    try:
        job = db.query(AutoCodeJob).filter_by(framework_id=framework).one()
        return job.applied_upper_threshold, job.applied_lower_threshold
    finally:
        db.close()


def _autocode_tags(db: Any) -> int:
    return db.query(QuoteTag).filter_by(source="autocode").count()


def test_a_fitting_run_accepts_its_top_30_percent_ties_included() -> None:
    app, ids = _seeded((0.95, 0.9, 0.9, 0.5))
    out = settle_first_apply_cut(app.state.db_factory, 1, "garrett")
    assert out is not None and (out.accept_at, out.accepted, out.excluded) == (0.9, 3, 0)
    assert _states(app, ids) == [
        ("accepted", "threshold"), ("accepted", "threshold"), ("accepted", "threshold"),
        ("pending", None),
    ]
    db = app.state.db_factory()
    try:
        assert _autocode_tags(db) == 3
    finally:
        db.close()
    assert _lines(app) == (0.90, 0.30)


def test_the_cut_never_goes_below_070_and_the_stored_line_is_rounded_up() -> None:
    """Top 30% of four is two (0.75, 0.72): the cut is 0.72, stored as 0.75, and no
    pending proposal is left at or above the stored line (D41)."""
    app, ids = _seeded((0.75, 0.72, 0.6, 0.2))
    settle_first_apply_cut(app.state.db_factory, 1, "garrett")
    assert [s for s, _ in _states(app, ids)] == ["accepted", "accepted", "pending", "denied"]
    upper, lower = _lines(app)
    assert (upper, lower) == (0.75, 0.30)
    db = app.state.db_factory()
    try:
        pending = [p.confidence for p in db.query(ProposedTag).filter_by(status="pending")]
        assert pending and all(c < upper for c in pending)
    finally:
        db.close()


def test_a_poorly_fitting_run_accepts_nothing_and_excludes_below_030() -> None:
    app, ids = _seeded((0.65, 0.6, 0.25, 0.1))
    out = settle_first_apply_cut(app.state.db_factory, 1, "garrett")
    assert out is not None and (out.accepted, out.excluded) == (0, 2)
    assert _states(app, ids) == [
        ("pending", None), ("pending", None), ("denied", "threshold"), ("denied", "threshold"),
    ]
    assert _lines(app) == (0.70, 0.30)


def test_a_run_with_no_proposals_accepts_nothing() -> None:
    app, _ = _seeded(())
    out = settle_first_apply_cut(app.state.db_factory, 1, "garrett")
    assert out is not None and (out.accepted, out.excluded) == (0, 0)
    assert _lines(app) == (0.70, 0.30)


def test_researcher_and_unknown_decisions_are_never_touched() -> None:
    """D2: a person's decision, or one from before decisions were recorded, stays. The cut
    is still ranked over them (0.95, 0.9 are the top two), so 0.9 is accepted."""
    app, ids = _seeded((0.95, 0.9, 0.2, 0.1))
    db = app.state.db_factory()
    try:
        for pid, status, by in ((ids[0], "denied", "researcher"), (ids[2], "accepted", "unknown")):
            p = db.get(ProposedTag, pid)
            assert p is not None
            p.status, p.decided_by = status, by
        db.commit()
    finally:
        db.close()
    settle_first_apply_cut(app.state.db_factory, 1, "garrett")
    assert _states(app, ids) == [
        ("denied", "researcher"), ("accepted", "threshold"), ("accepted", "unknown"),
        ("denied", "threshold"),
    ]


def test_only_a_proposal_still_pending_when_it_is_written_changes() -> None:
    """A researcher's decision committed after the step read the proposals (a quote card,
    mid-step) is not overwritten: the write is conditional on pending (D2)."""
    app, ids = _seeded((0.95, 0.9, 0.5, 0.2))
    original = routes._ensure_autocode_tag
    landed: list[bool] = []

    def decide_meanwhile(db: Any, proposal: ProposedTag) -> None:
        if not landed:
            landed.append(True)
            other = app.state.db_factory()
            try:
                p = other.get(ProposedTag, ids[3])
                assert p is not None
                p.status, p.decided_by = "accepted", "researcher"
                other.commit()
            finally:
                other.close()
        original(db, proposal)

    with patch.object(routes, "_ensure_autocode_tag", decide_meanwhile):
        settle_first_apply_cut(app.state.db_factory, 1, "garrett")
    assert landed
    assert _states(app, ids)[3] == ("accepted", "researcher")


def test_a_hidden_quotes_proposal_is_not_ranked_or_touched() -> None:
    """Accept-all's counted-quote rule: a hidden quote's proposal stays pending."""
    app, ids = _seeded((0.95, 0.9, 0.85, 0.1))
    client = AuthTestClient(app)
    db = app.state.db_factory()
    try:
        from bristlenose.server.grounding import quote_dom_id

        p = db.get(ProposedTag, ids[0])
        assert p is not None
        q = db.get(Quote, p.quote_id)
        assert q is not None
        dom = quote_dom_id(q.participant_id, q.start_timecode, q.ordinal)
    finally:
        db.close()
    assert client.put("/api/projects/1/hidden", json={dom: True}).status_code == 200
    settle_first_apply_cut(app.state.db_factory, 1, "garrett")
    # Three counted proposals (0.9, 0.85, 0.1): the top one is 0.9.
    assert [s for s, _ in _states(app, ids)] == ["pending", "accepted", "pending", "denied"]


def test_the_reviews_apply_with_the_lines_unmoved_after_a_cut_changes_nothing() -> None:
    """D26 and D41 together: the stored accept line is the cut rounded up, so the review
    opened on the stored lines finds nothing to move."""
    app, ids = _seeded((0.75, 0.72, 0.6, 0.2))
    settle_first_apply_cut(app.state.db_factory, 1, "garrett")
    before = _states(app, ids)
    upper, lower = _lines(app)
    resp = AuthTestClient(app).post(
        "/api/projects/1/autocode/garrett/recut", json={"lower": lower, "upper": upper})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"accepted": 0, "tentative": 0, "excluded": 0}
    assert _states(app, ids) == before


# ── Through start_autocode: the order, the stop, the resume ────────────────────────────────────


def _fake_job(outcome: str, confidences: tuple[float, ...]) -> Any:
    """A job runner that proposes, pending, on the next quotes without a proposal, then
    ends as ``outcome`` (``completed_at`` set only for a completed one, as the real one)."""

    async def run(db_factory: Any, project_id: int, framework_id: str, *_a: Any,
                  **_k: Any) -> None:
        db = db_factory()
        try:
            job = db.query(AutoCodeJob).filter_by(
                project_id=project_id, framework_id=framework_id).one()
            done = {p.quote_id for p in db.query(ProposedTag).filter_by(job_id=job.id)}
            quotes = [q for q in db.query(Quote).filter_by(project_id=project_id)
                      .order_by(Quote.id) if q.id not in done]
            # The codebook's own tag: one the import put on a quote already would add no
            # AutoCode tag when accepted.
            tag = (db.query(TagDefinition).join(
                CodebookGroup, CodebookGroup.id == TagDefinition.codebook_group_id)
                .filter(CodebookGroup.framework_id == framework_id)
                .order_by(TagDefinition.id).first())
            assert tag is not None
            for quote, conf in zip(quotes, confidences, strict=False):
                db.add(ProposedTag(job_id=job.id, quote_id=quote.id, tag_definition_id=tag.id,
                                   confidence=conf, rationale="r"))
            job.status = outcome
            if outcome == "completed":
                job.completed_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

    return run


def _snapshot_spy() -> tuple[Any, list[tuple[str, int]]]:
    """A Signals build that records its source and the AutoCode tags it would read."""
    seen: list[tuple[str, int]] = []

    async def build(db: Any, project_id: int, *, source: str, **_k: Any) -> None:
        seen.append((source, _autocode_tags(db)))

    return build, seen


def _start(app: FastAPI, framework: str, job: Any, build: Any) -> None:
    async def go() -> None:
        with patch(READY), patch.object(routes, "run_autocode_job", job), patch(SNAPSHOT, build):
            await routes.start_autocode(app, 1, framework)
            await routes._AUTOCODE_LIVE[(1, framework)]

    asyncio.run(go())


def test_a_researchers_first_apply_is_cut_before_the_signals_snapshot() -> None:
    """Until Phase 3 a first apply the researcher started left every proposal pending
    (D5 changes it); the snapshot that follows reads the cut."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    _import_garrett(app)
    build, seen = _snapshot_spy()
    _start(app, "garrett", _fake_job("completed", (0.95, 0.9, 0.6, 0.1)), build)
    assert seen == [("codebook_apply", 2)]
    assert _lines(app) == (0.90, 0.30)


def test_a_failed_first_apply_is_not_settled() -> None:
    """As shipped: a failure is not a stop (D27, D35 name a stop); its retry cuts the
    whole run when it completes."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    _import_garrett(app)
    build, seen = _snapshot_spy()
    _start(app, "garrett", _fake_job("failed", (0.95, 0.9)), build)
    assert seen == []
    assert _lines(app) == (None, None)


@pytest.fixture()
def house(tmp_path: Path) -> FastAPI:
    application = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    marker = tmp_path / hd.MARKER_NAME
    with patch.object(hd, "marker_path", lambda _app: marker):
        yield application


def _house_default(app: FastAPI, job: Any, build: Any) -> None:
    async def go() -> None:
        with (
            patch.object(hd, "_has_screens", lambda _a: True),
            patch(READY),
            patch.object(routes, "run_autocode_job", job),
            patch(SNAPSHOT, build),
        ):
            hd.arm(app)
            assert await hd.maybe_apply(app) is True
            await routes._AUTOCODE_LIVE[(1, "uxr")]

    asyncio.run(go())


def test_a_stopped_first_apply_settles_stays_resumable_and_resumes_at_its_lines(
    house: FastAPI,
) -> None:
    """D27, D35. Stopped with two quotes coded (0.9, 0.5): the top 30% of two is 0.9, so
    0.9 is accepted and the lines (0.90, 0.30) stored, but the job has no ``completed_at``
    and the house default's marker is not written, so the next completed run retries it.
    The retry codes the other two (0.85, 0.8) and ends at the STORED lines: 0.85 stays
    pending, where a cut recomputed over all four (top two: 0.9, 0.85) would accept it."""
    build, seen = _snapshot_spy()
    _house_default(house, _fake_job("cancelled", (0.9, 0.5)), build)

    db = house.state.db_factory()
    try:
        job = db.query(AutoCodeJob).filter_by(framework_id="uxr").one()
        assert (job.status, job.completed_at) == ("cancelled", None)
        assert (job.applied_upper_threshold, job.applied_lower_threshold) == (0.90, 0.30)
        assert sorted((p.confidence, p.status) for p in db.query(ProposedTag)) == [
            (0.5, "pending"), (0.9, "accepted")]
        assert _autocode_tags(db) == 1
    finally:
        db.close()
    assert not hd.already_done(house)
    assert hd._read_marker(house).get("started")
    assert seen == [("codebook_stopped", 1)]  # D31: a stop that left accepted tags

    _house_default(house, _fake_job("completed", (0.85, 0.8)), build)

    db = house.state.db_factory()
    try:
        job = db.query(AutoCodeJob).filter_by(framework_id="uxr").one()
        assert job.completed_at is not None
        assert (job.applied_upper_threshold, job.applied_lower_threshold) == (0.90, 0.30)
        assert sorted((p.confidence, p.status) for p in db.query(ProposedTag)) == [
            (0.5, "pending"), (0.8, "pending"), (0.85, "pending"), (0.9, "accepted")]
    finally:
        db.close()
    assert hd.already_done(house)
    assert seen[-1] == ("codebook_apply", 1)


def test_a_stop_before_anything_was_coded_stores_no_lines() -> None:
    """Lines fixed from nothing would cut the resumed run at the floor, not its 30%."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    _import_garrett(app)
    build, seen = _snapshot_spy()
    _start(app, "garrett", _fake_job("cancelled", ()), build)
    assert _lines(app) == (None, None)
    assert seen == []


def test_the_house_defaults_end_step_is_the_cut_and_then_its_marker(house: FastAPI) -> None:
    build, seen = _snapshot_spy()
    _house_default(house, _fake_job("completed", (0.95, 0.9, 0.6, 0.1)), build)
    assert hd.already_done(house)
    assert _lines(house, "uxr") == (0.90, 0.30)
    assert seen == [("codebook_apply", 2)]


def test_the_review_route_reads_the_stored_lines(house: FastAPI) -> None:
    """The status the review dialog draws its lines from carries the cut's lines."""
    build, _ = _snapshot_spy()
    _house_default(house, _fake_job("completed", (0.75, 0.72, 0.6, 0.2)), build)
    body = TestClient(house, base_url="http://127.0.0.1", headers={
        "Authorization": f"Bearer {house.state.auth_token}"}).get(
        "/api/projects/1/autocode/uxr/status").json()
    assert (body["applied_upper_threshold"], body["applied_lower_threshold"]) == (0.75, 0.30)
