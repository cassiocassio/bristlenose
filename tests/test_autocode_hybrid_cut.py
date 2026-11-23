"""AutoCode landing, Phase 3: the end-of-run hybrid cut and the stopped-run settle.

Every first apply that completes, the house default's and a researcher's, ends with the
hybrid (docs/design-autocode-landing-plan.md D5): the most confident 30% of the run's
proposals, never below 0.70, accepted at the line stored for them, the rank rounded UP to
the 0.05 grid (D41, D46); below 0.30 excluded; the rest pending. The cut is committed with
the job's outcome (``autocode.cut_first_apply``), so no reader sees a completed run before
its cut, and the outcome's save retries are the cut's. A first apply stopped partway
settles the same way and stays resumable (D27, D35); its resumed run finishes at the
stored lines. The LLM is always mocked.
"""

from __future__ import annotations

import asyncio
import shutil
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from sqlalchemy import event

from bristlenose.llm.structured import AutoCodeBatchResult, AutoCodeTagAssignment
from bristlenose.server import autocode
from bristlenose.server import autocode_house_default as hd
from bristlenose.server.app import create_app
from bristlenose.server.autocode import (
    accept_line_for,
    cut_first_apply,
    hybrid_accept_line,
    hybrid_rank_confidence,
    run_autocode_job,
)
from bristlenose.server.codebook import get_template
from bristlenose.server.models import AutoCodeJob, ProposedTag, Quote, QuoteTag
from bristlenose.server.routes import autocode as routes
from tests.conftest import AuthTestClient
from tests.test_autocode_batch_save import (
    _file_project,
    _hold_the_write_lock,
    _n_in_prompt,
    _settings,
)
from tests.test_autocode_engine import _patch_llm
from tests.test_serve_autocode_api import _FIXTURE_DIR, _import_garrett

READY = "bristlenose.server.routes.autocode.require_provider_ready"
SNAPSHOT = "bristlenose.server.routes.signals.materialise_completed_signal_snapshot"

# ── The rule ───────────────────────────────────────────────────────────────────────────────────


def test_the_rank_is_the_top_30_percent_never_below_the_floor() -> None:
    ten = [0.99, 0.95, 0.9, 0.88, 0.85, 0.8, 0.75, 0.7, 0.4, 0.1]
    assert hybrid_rank_confidence(ten) == 0.9  # ceil(30% of 10) = 3: 0.99, 0.95, 0.9
    assert hybrid_rank_confidence([0.9, 0.85, 0.8, 0.8, 0.8, 0.5, 0.5]) == 0.8  # ceil(2.1) = 3
    assert hybrid_rank_confidence([0.95, 0.75, 0.72]) == 0.95  # at least the first


def test_ties_on_the_grid_are_all_accepted() -> None:
    confs = [0.9, 0.9, 0.9, 0.9, 0.9, 0.5, 0.5, 0.5, 0.5, 0.5]
    line = hybrid_accept_line(confs)
    assert line == 0.9
    assert sum(c >= line for c in confs) == 5  # all five tied, though 30% is three


def test_a_rank_off_the_grid_accepts_at_the_line_above_it() -> None:
    """D46: the line accepted at is the stored one; 0.72 rounds up to 0.75, and a run whose
    rank falls between grid values takes a little under 30%."""
    confs = [0.8, 0.72, 0.6, 0.5, 0.4]  # rank 2 of 5: 0.72
    assert hybrid_rank_confidence(confs) == 0.72
    assert hybrid_accept_line(confs) == 0.75
    assert sum(c >= 0.75 for c in confs) == 1


def test_a_poorly_fitting_run_has_only_the_floor() -> None:
    """Phase 0a: three poorly fitting runs had every proposal at 0.10; the top 30% alone
    would have accepted all of them."""
    assert hybrid_accept_line([0.1] * 20) == 0.70
    assert hybrid_accept_line([0.65, 0.6, 0.2]) == 0.70
    assert hybrid_accept_line([]) == 0.70


@pytest.mark.parametrize(
    ("value", "line"),
    [(0.70, 0.70), (0.72, 0.75), (0.75, 0.75), (0.7000000000000001, 0.70), (0.55, 0.55),
     (0.81, 0.85), (0.97, 1.0), (1.0, 1.0)],
)
def test_the_accept_line_is_rounded_up_to_the_grid(value: float, line: float) -> None:
    assert accept_line_for(value) == line


# ── The cut, at the routes' database ───────────────────────────────────────────────────────────


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


def _cut(db_factory: Any, framework: str = "garrett", *, stopped: bool = False) -> Any:
    """``cut_first_apply`` in its own transaction, as the job's outcome save runs it."""
    db = db_factory()
    try:
        job = db.query(AutoCodeJob).filter_by(framework_id=framework).one()
        out = cut_first_apply(db, job.id, stopped=stopped)
        db.commit()
        return out
    finally:
        db.close()


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


def _lines(db_factory: Any, framework: str = "garrett") -> tuple[float | None, float | None]:
    db = db_factory()
    try:
        job = db.query(AutoCodeJob).filter_by(framework_id=framework).one()
        return job.applied_upper_threshold, job.applied_lower_threshold
    finally:
        db.close()


def _autocode_tags(db: Any) -> int:
    return db.query(QuoteTag).filter_by(source="autocode").count()


def test_a_fitting_run_accepts_its_top_30_percent_ties_included() -> None:
    app, ids = _seeded((0.95, 0.9, 0.9, 0.5))
    out = _cut(app.state.db_factory)
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
    assert _lines(app.state.db_factory) == (0.90, 0.30)


def test_every_accepted_row_is_at_or_above_the_stored_line_and_every_pending_below() -> None:
    """D46. The top 30% of four is two (0.75, 0.72): the rank 0.72 rounds up to 0.75, the line
    stored AND accepted at. The 0.72 and the 0.71 stay pending; a line rounded down to 0.70
    would accept both."""
    app, ids = _seeded((0.75, 0.72, 0.71, 0.2))
    _cut(app.state.db_factory)
    assert [s for s, _ in _states(app, ids)] == ["accepted", "pending", "pending", "denied"]
    upper, lower = _lines(app.state.db_factory)
    assert (upper, lower) == (0.75, 0.30)
    db = app.state.db_factory()
    try:
        rows = db.query(ProposedTag).all()
        assert all(p.confidence >= upper for p in rows if p.status == "accepted")
        assert all(p.confidence < upper for p in rows if p.status == "pending")
    finally:
        db.close()


def test_a_poorly_fitting_run_accepts_nothing_and_excludes_below_030() -> None:
    app, ids = _seeded((0.65, 0.6, 0.25, 0.1))
    out = _cut(app.state.db_factory)
    assert out is not None and (out.accepted, out.excluded) == (0, 2)
    assert _states(app, ids) == [
        ("pending", None), ("pending", None), ("denied", "threshold"), ("denied", "threshold"),
    ]
    assert _lines(app.state.db_factory) == (0.70, 0.30)


def test_a_run_with_no_proposals_accepts_nothing() -> None:
    app, _ = _seeded(())
    out = _cut(app.state.db_factory)
    assert out is not None and (out.accepted, out.excluded) == (0, 0)
    assert _lines(app.state.db_factory) == (0.70, 0.30)


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
    _cut(app.state.db_factory)
    assert _states(app, ids) == [
        ("denied", "researcher"), ("accepted", "threshold"), ("accepted", "unknown"),
        ("denied", "threshold"),
    ]


def test_only_a_proposal_still_pending_when_it_is_written_changes() -> None:
    """A researcher's decision committed after the cut read the proposals (a quote card,
    mid-cut) is not overwritten: the write is conditional on pending (D2)."""
    app, ids = _seeded((0.95, 0.9, 0.5, 0.2))
    db = app.state.db_factory()
    landed: list[bool] = []
    real_query = db.query

    def query_then_decide(*entities: Any, **kw: Any) -> Any:
        q = real_query(*entities, **kw)
        if len(entities) == 1 and entities[0] is QuoteTag.id and not landed:  # first accept's tag check
            landed.append(True)
            other = app.state.db_factory()
            try:
                p = other.get(ProposedTag, ids[3])
                assert p is not None
                p.status, p.decided_by = "accepted", "researcher"
                other.commit()
            finally:
                other.close()
        return q

    try:
        job = db.query(AutoCodeJob).one()
        with patch.object(db, "query", query_then_decide):
            cut_first_apply(db, job.id)
        db.commit()
    finally:
        db.close()
    assert landed
    assert _states(app, ids)[3] == ("accepted", "researcher")


def test_a_hidden_quotes_proposal_is_not_ranked_or_touched() -> None:
    """Accept-all's counted-quote rule: a hidden quote's proposal stays pending."""
    from bristlenose.server.grounding import quote_dom_id

    app, ids = _seeded((0.95, 0.9, 0.85, 0.1))
    db = app.state.db_factory()
    try:
        p = db.get(ProposedTag, ids[0])
        assert p is not None
        q = db.get(Quote, p.quote_id)
        assert q is not None
        dom = quote_dom_id(q.participant_id, q.start_timecode, q.ordinal)
    finally:
        db.close()
    assert AuthTestClient(app).put("/api/projects/1/hidden", json={dom: True}).status_code == 200
    _cut(app.state.db_factory)
    # Three counted proposals (0.9, 0.85, 0.1): the top one is 0.9.
    assert [s for s, _ in _states(app, ids)] == ["pending", "accepted", "pending", "denied"]


def test_the_reviews_apply_with_the_lines_unmoved_after_a_cut_changes_nothing() -> None:
    """D26 with D41 and D46: the cut accepts at the line it stores, so the review opened on
    the stored lines finds nothing to move."""
    app, ids = _seeded((0.75, 0.72, 0.71, 0.2))
    _cut(app.state.db_factory)
    before = _states(app, ids)
    assert [s for s, _ in before] == ["accepted", "pending", "pending", "denied"]
    upper, lower = _lines(app.state.db_factory)
    resp = AuthTestClient(app).post(
        "/api/projects/1/autocode/garrett/recut", json={"lower": lower, "upper": upper})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"accepted": 0, "tentative": 0, "excluded": 0}
    assert _states(app, ids) == before


def test_a_recut_across_a_gap_that_changes_nothing_counts_nothing(monkeypatch) -> None:
    """The D31 belt: a threshold acceptance left below the stored line (as the first build of
    Phase 3 did, at 0.72 under 0.80) is in the old lines' tentative zone; lowering the line
    to 0.70 puts it in the accepted zone it is already in. No move, no Signals rebuild."""
    app, ids = _seeded((0.72, 0.5))
    db = app.state.db_factory()
    try:
        p = db.get(ProposedTag, ids[0])
        assert p is not None
        p.status, p.decided_by = "accepted", "threshold"
        db.add(QuoteTag(quote_id=p.quote_id, tag_definition_id=p.tag_definition_id,
                        source="autocode"))
        job = db.query(AutoCodeJob).one()
        job.applied_upper_threshold, job.applied_lower_threshold = 0.80, 0.30
        db.commit()
    finally:
        db.close()
    asked: list[int] = []
    monkeypatch.setattr(routes, "recut_made", lambda _app, pid: asked.append(pid))
    resp = AuthTestClient(app).post(
        "/api/projects/1/autocode/garrett/recut", json={"lower": 0.30, "upper": 0.70})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"accepted": 0, "tentative": 0, "excluded": 0}
    assert asked == []
    assert _states(app, ids) == [("accepted", "threshold"), ("pending", None)]


# ── The real job, the LLM mocked ───────────────────────────────────────────────────────────────


def _answers(*per_call: tuple[float, ...], tag: str) -> AsyncMock:
    """One confidence list per call, in order, one assignment per quote in its batch."""
    calls = list(per_call)

    async def analyze(**kw: Any) -> AutoCodeBatchResult:
        confs = calls.pop(0)
        n = _n_in_prompt(str(kw["user_prompt"]))
        return AutoCodeBatchResult(assignments=[
            AutoCodeTagAssignment(quote_index=i, tag_name=tag, confidence=c, rationale="r")
            for i, c in zip(range(n), confs, strict=False)
        ])

    return AsyncMock(side_effect=analyze)


def _tag_of(framework: str) -> str:
    template = get_template(framework)
    assert template is not None
    return template.groups[0].tags[0].name


def _snapshot_spy() -> tuple[Any, list[tuple[str, int]]]:
    """A Signals build that records its source and the AutoCode tags it would read."""
    seen: list[tuple[str, int]] = []

    async def build(db: Any, project_id: int, *, source: str, **_k: Any) -> None:
        seen.append((source, _autocode_tags(db)))

    return build, seen


@pytest.fixture()
def study(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """A copy of the smoke study (four quotes), so a run's records never land in the
    fixture; batches of two, one at a time; the house default's marker in tmp_path."""
    project = tmp_path / "input"
    shutil.copytree(_FIXTURE_DIR, project)
    application = create_app(project_dir=project, dev=True, db_url="sqlite://")
    monkeypatch.setattr(autocode, "BATCH_SIZE", 2)
    monkeypatch.setattr(routes, "load_settings", _settings)
    marker = tmp_path / hd.MARKER_NAME
    with patch.object(hd, "marker_path", lambda _app: marker):
        yield application


def _start(app: FastAPI, framework: str, analyze: AsyncMock, build: Any) -> None:
    async def go() -> None:
        with patch(READY), patch(SNAPSHOT, build), _patch_llm(analyze):
            await routes.start_autocode(app, 1, framework)
            await routes._AUTOCODE_LIVE[(1, framework)]

    asyncio.run(go())


def _house_default(app: FastAPI, analyze: AsyncMock, build: Any) -> None:
    async def go() -> None:
        with (
            patch.object(hd, "_has_screens", lambda _a: True),
            patch(READY),
            patch(SNAPSHOT, build),
            _patch_llm(analyze),
        ):
            hd.arm(app)
            assert await hd.maybe_apply(app) is True
            await routes._AUTOCODE_LIVE[(1, "uxr")]

    asyncio.run(go())


def _stop_during_first_call(app: FastAPI, framework: str, analyze: AsyncMock) -> AsyncMock:
    """The researcher's Stop lands while the first batch codes; the second is never sent."""
    inner = analyze.side_effect

    async def stopping(**kw: Any) -> AutoCodeBatchResult:
        if analyze.await_count == 1:
            db = app.state.db_factory()
            try:
                db.query(AutoCodeJob).filter_by(framework_id=framework).update(
                    {"status": "cancelled"})
                db.commit()
                # The status read says the stopped run is still ending (the page waits).
                assert routes._job_to_out(
                    db.query(AutoCodeJob).filter_by(framework_id=framework).one()).ending
            finally:
                db.close()
        return await inner(**kw)

    analyze.side_effect = stopping
    return analyze


def test_a_researchers_first_apply_is_cut_before_the_signals_snapshot(study: FastAPI) -> None:
    """Until Phase 3 a first apply the researcher started left every proposal pending
    (D5 changes it); the snapshot that follows reads the cut."""
    _import_garrett(study)
    build, seen = _snapshot_spy()
    _start(study, "garrett", _answers((0.95, 0.9), (0.6, 0.1), tag="user need"), build)
    assert seen == [("codebook_apply", 2)]
    assert _lines(study.state.db_factory) == (0.90, 0.30)


def test_a_failed_first_apply_is_not_settled(study: FastAPI) -> None:
    """As shipped: a failure is not a stop (D27, D35 name a stop); its retry cuts the
    whole run when it completes."""
    _import_garrett(study)
    build, seen = _snapshot_spy()
    _start(study, "garrett", AsyncMock(side_effect=RuntimeError("boom")), build)
    db = study.state.db_factory()
    try:
        assert db.query(AutoCodeJob).one().status == "failed"
    finally:
        db.close()
    assert seen == []
    assert _lines(study.state.db_factory) == (None, None)


def test_a_stopped_first_apply_settles_stays_resumable_and_resumes_at_its_lines(
    study: FastAPI,
) -> None:
    """D27, D35, through the real house default. Stopped with two quotes coded (0.9, 0.5):
    the top 30% of two is 0.9, accepted, and the lines (0.90, 0.30) stored, but the job has
    no ``completed_at`` and the marker is not written, so the next completed run retries it.
    The retry codes the other two (0.85, 0.8) and ends at the STORED lines: 0.85 stays
    pending, where a cut ranked again over all four (top two: 0.9, 0.85) would accept it."""
    tag = _tag_of("uxr")
    build, seen = _snapshot_spy()
    analyze = _stop_during_first_call(study, "uxr", _answers((0.9, 0.5), tag=tag))
    _house_default(study, analyze, build)

    db = study.state.db_factory()
    try:
        job = db.query(AutoCodeJob).filter_by(framework_id="uxr").one()
        assert (job.status, job.completed_at) == ("cancelled", None)
        assert (job.applied_upper_threshold, job.applied_lower_threshold) == (0.90, 0.30)
        assert sorted((p.confidence, p.status) for p in db.query(ProposedTag)) == [
            (0.5, "pending"), (0.9, "accepted")]
        assert _autocode_tags(db) == 1
    finally:
        db.close()
    assert not autocode.first_apply_ending(1, "uxr")
    assert not hd.already_done(study)
    assert hd._read_marker(study).get("started")
    assert seen == [("codebook_stopped", 1)]  # D31: a stop that left accepted tags

    _house_default(study, _answers((0.85, 0.8), tag=tag), build)

    db = study.state.db_factory()
    try:
        job = db.query(AutoCodeJob).filter_by(framework_id="uxr").one()
        assert job.completed_at is not None
        assert (job.applied_upper_threshold, job.applied_lower_threshold) == (0.90, 0.30)
        assert sorted((p.confidence, p.status) for p in db.query(ProposedTag)) == [
            (0.5, "pending"), (0.8, "pending"), (0.85, "pending"), (0.9, "accepted")]
    finally:
        db.close()
    assert hd.already_done(study)
    assert seen[-1] == ("codebook_apply", 1)


def test_a_stop_before_anything_was_coded_stores_no_lines(study: FastAPI) -> None:
    """Lines fixed from nothing would cut the resumed run at the floor, not its 30%."""
    _import_garrett(study)
    db = study.state.db_factory()
    try:
        db.add(AutoCodeJob(project_id=1, framework_id="garrett", status="pending"))
        db.commit()
    finally:
        db.close()
    _cut(study.state.db_factory, stopped=True)
    assert _lines(study.state.db_factory) == (None, None)


def test_the_house_defaults_marker_follows_the_cut(study: FastAPI) -> None:
    build, seen = _snapshot_spy()
    _house_default(study, _answers((0.95, 0.9), (0.6, 0.1), tag=_tag_of("uxr")), build)
    assert hd.already_done(study)
    assert _lines(study.state.db_factory, "uxr") == (0.90, 0.30)
    assert seen == [("codebook_apply", 2)]


def test_the_status_read_carries_the_lines_and_says_when_the_run_has_ended(
    study: FastAPI,
) -> None:
    build, _ = _snapshot_spy()
    _house_default(study, _answers((0.75, 0.72), (0.71, 0.2), tag=_tag_of("uxr")), build)
    body = AuthTestClient(study).get("/api/projects/1/autocode/uxr/status").json()
    assert (body["applied_upper_threshold"], body["applied_lower_threshold"]) == (0.75, 0.30)
    assert body["ending"] is False


# ── Atomic with the outcome, and retried with it (a study database file) ───────────────────────


def _job_row(db_path: Path) -> tuple[str, float | None, int]:
    """(status, stored accept line, accepted proposals), read by a plain connection."""
    conn = sqlite3.connect(db_path, timeout=5)
    try:
        status, upper, job_id = conn.execute(
            "SELECT status, applied_upper_threshold, id FROM autocode_jobs").fetchone()
        accepted = conn.execute(
            "SELECT count(*) FROM proposed_tags WHERE job_id = ? AND status = 'accepted'",
            (job_id,)).fetchone()[0]
        return status, upper, accepted
    finally:
        conn.close()


def test_no_reader_ever_sees_a_completed_first_apply_without_its_cut(tmp_path) -> None:
    """Every commit of the run is followed by a read from outside it: none finds the job
    completed with no lines or nothing accepted (the chip refreshes on "completed")."""
    session_cls, engine, project_id, db_path = _file_project(tmp_path, 10)
    seen: list[tuple[str, float | None, int]] = []
    event.listen(session_cls, "after_commit", lambda _s: seen.append(_job_row(db_path)))
    with _patch_llm(_answers((0.95,) * 3 + (0.5,) * 7, tag="user need")):
        asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))
    completed = [row for row in seen if row[0] == "completed"]
    assert completed, seen
    assert all(upper == 0.95 and accepted == 3 for _, upper, accepted in completed), completed
    engine.dispose()


def _hold_during_outcome(monkeypatch, db_path: Path, tries_held: int | None) -> None:
    """Another connection holds the write lock while the run saves its outcome (and its
    cut): through ``tries_held`` tries of that save, or every try when None."""
    monkeypatch.setattr(autocode, "SAVE_BACKOFF_S", (0.01,))
    monkeypatch.setattr(autocode, "SAVE_BUSY_TIMEOUT_MS", 30)
    real_save, real_try = autocode._save_batch, autocode._try_save
    state = {"outcome": False, "tries": 0}
    release, held = threading.Event(), threading.Event()
    holder: list[threading.Thread] = []

    def start_holding() -> None:
        t = threading.Thread(target=_hold_the_write_lock, args=(db_path, release, held))
        t.start()
        holder.append(t)
        assert held.wait(5)

    def stop_holding() -> None:
        release.set()
        holder[0].join(5)

    async def save_spy(db_factory, write, what):  # type: ignore[no-untyped-def]
        if not what.endswith("its outcome"):
            return await real_save(db_factory, write, what)
        state["outcome"] = True
        start_holding()
        try:
            return await real_save(db_factory, write, what)
        finally:
            if not release.is_set():
                stop_holding()

    def try_spy(db_factory, write):  # type: ignore[no-untyped-def]
        result = real_try(db_factory, write)
        if state["outcome"]:
            state["tries"] += 1
            if tries_held is not None and state["tries"] >= tries_held and not release.is_set():
                stop_holding()
        return result

    monkeypatch.setattr(autocode, "_save_batch", save_spy)
    monkeypatch.setattr(autocode, "_try_save", try_spy)


def test_a_lock_held_for_the_first_try_of_the_outcome_is_waited_out(tmp_path, monkeypatch) -> None:
    """The outcome and its cut are retried as a batch's save is (worker thread, the short lock
    wait, ``SAVE_ATTEMPTS``): a writer that lets go after the first try costs nothing."""
    session_cls, engine, project_id, db_path = _file_project(tmp_path, 10, busy_ms=30)
    _hold_during_outcome(monkeypatch, db_path, tries_held=1)
    with _patch_llm(_answers((0.95,) * 3 + (0.5,) * 7, tag="user need")):
        asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))
    assert _job_row(db_path) == ("completed", 0.95, 3)
    engine.dispose()


def test_a_lock_held_through_every_try_fails_the_run_and_the_retry_cuts_it(
    tmp_path, monkeypatch,
) -> None:
    """Held through every try, the outcome is not saved: the run reads failed, never applied,
    with no cut and no lines, its proposals kept. Nothing claims a cut that did not land, and
    the cut is owed to the retry: Apply runs the job again, nothing is left to send, and it
    completes with its cut."""
    session_cls, engine, project_id, db_path = _file_project(tmp_path, 10, busy_ms=30)
    _hold_during_outcome(monkeypatch, db_path, tries_held=None)
    with _patch_llm(_answers((0.95,) * 3 + (0.5,) * 7, tag="user need")):
        asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))
    assert _job_row(db_path) == ("failed", None, 0)
    db = session_cls()
    try:
        job = db.query(AutoCodeJob).one()
        assert job.completed_at is None
        assert db.query(ProposedTag).filter_by(status="pending").count() == 10
        job.status = "pending"  # what Apply's start does to a never-applied failed job
        db.commit()
    finally:
        db.close()
    monkeypatch.undo()
    analyze = AsyncMock()
    with _patch_llm(analyze):
        asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))
    analyze.assert_not_awaited()
    assert _job_row(db_path) == ("completed", 0.95, 3)
    engine.dispose()
