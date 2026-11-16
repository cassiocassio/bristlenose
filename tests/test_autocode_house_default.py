"""The house default: a study with screens is coded with the UXR codebook, once.

No real LLM calls: ``start_autocode`` is replaced. What is pinned is the decision (when it
starts, when it stays silent), the install it does first, the one-shot marker, and the job-side
hook that asks (``ScreenTextJob``'s ``on_idle``).
"""

from __future__ import annotations

import asyncio
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from bristlenose.events import KindEnum, RunCompletedEvent, new_run_id
from bristlenose.server import autocode_house_default as hd
from bristlenose.server.app import _make_run_completed_handler, create_app
from bristlenose.server.codebook_install import framework_linked
from bristlenose.server.models import AutoCodeJob, ProposedTag, Quote, QuoteTag, TagDefinition
from bristlenose.server.refusal import RefusalError, RefusalReason
from bristlenose.server.routes.autocode import accept_at_default_cutoff
from bristlenose.server.screen_text_job import ScreenTextJob

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
START = "bristlenose.server.routes.autocode.start_autocode"
READY = "bristlenose.server.routes.autocode.require_provider_ready"


@pytest.fixture()
def app(tmp_path: Path) -> FastAPI:
    application = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    # The marker goes to tmp_path, never into the fixture tree.
    marker = tmp_path / hd.MARKER_NAME
    with patch.object(hd, "marker_path", lambda _app: marker):
        yield application


def _linked(app: FastAPI) -> bool:
    db = app.state.db_factory()
    try:
        return framework_linked(db, 1, "uxr")
    finally:
        db.close()


def _run(app: FastAPI, *, screens: bool = True, ready: bool = True,
         complete: bool = True) -> tuple[bool, AsyncMock]:
    """One decision. ``complete`` makes the stubbed job finish, as the real one calls
    ``after_apply`` when it has completed; the cutoff step itself is stubbed."""

    def finish(*_a: object, after_apply: object = None, **_k: object) -> None:
        if complete and after_apply is not None:
            after_apply()  # type: ignore[operator]

    start = AsyncMock(side_effect=finish)
    refuse = RefusalError(503, RefusalReason.NO_API_KEY, "no key")
    with (
        patch.object(hd, "_has_screens", lambda _a: screens),
        patch(READY, side_effect=None if ready else refuse),
        patch(START, start),
        patch("bristlenose.server.routes.autocode.accept_at_default_cutoff", MagicMock()),
    ):
        return asyncio.run(hd.maybe_apply(app)), start


def test_a_study_with_screens_installs_and_starts_uxr_once(app: FastAPI) -> None:
    hd.arm(app)
    started, start = _run(app)
    assert started is True
    start.assert_awaited_once()
    assert start.await_args.args[1:] == (1, "uxr")
    assert callable(start.await_args.kwargs["after_apply"])
    assert _linked(app)  # AutoCode resolves answers against these rows
    assert hd.already_done(app)


def test_it_never_runs_twice(app: FastAPI) -> None:
    hd.arm(app)
    _run(app)
    hd.arm(app)  # the next completed run arms it again
    started, start = _run(app)
    assert started is False
    start.assert_not_awaited()


def test_the_marker_outlives_the_codebook_being_removed(app: FastAPI) -> None:
    """Remove deletes the job and unlinks the groups; neither may bring the default back."""
    hd.arm(app)
    _run(app)
    db = app.state.db_factory()
    try:
        from bristlenose.server.autocode import delete_jobs
        from bristlenose.server.models import ProjectCodebookGroup

        delete_jobs(db, [j.id for j in db.query(AutoCodeJob).all()])
        db.query(ProjectCodebookGroup).delete()
        db.commit()
    finally:
        db.close()
    hd.arm(app)
    started, start = _run(app)
    assert started is False
    start.assert_not_awaited()


def test_not_armed_means_an_ordinary_open_spends_nothing(app: FastAPI) -> None:
    started, start = _run(app)
    assert started is False
    start.assert_not_awaited()
    assert not _linked(app)


def test_no_screens_spends_nothing_and_installs_nothing(app: FastAPI) -> None:
    hd.arm(app)
    started, start = _run(app, screens=False)
    assert started is False
    start.assert_not_awaited()
    assert not _linked(app)
    assert not hd.already_done(app)
    assert app.state.house_default_due is False  # decided: waits for the next completed run


def test_no_cloud_provider_or_key_installs_nothing(app: FastAPI) -> None:
    hd.arm(app)
    started, start = _run(app, ready=False)
    assert started is False
    start.assert_not_awaited()
    assert not _linked(app)
    assert not hd.already_done(app)


def test_a_researcher_who_already_has_uxr_is_left_alone(app: FastAPI) -> None:
    from bristlenose.server.codebook import get_template
    from bristlenose.server.codebook_install import link_framework

    db = app.state.db_factory()
    try:
        tmpl = get_template("uxr")
        assert tmpl is not None
        link_framework(db, 1, tmpl)
        db.commit()
    finally:
        db.close()
    hd.arm(app)
    started, start = _run(app)
    assert started is False
    start.assert_not_awaited()
    assert not hd.already_done(app)  # we did nothing, so there is nothing to record


def _job_row(app: FastAPI, status: str, applied: bool) -> None:
    db = app.state.db_factory()
    try:
        db.add(AutoCodeJob(project_id=1, framework_id="uxr", status=status,
                           completed_at=datetime.now(timezone.utc) if applied else None))
        db.commit()
    finally:
        db.close()


def test_a_job_the_restart_killed_is_retried_on_the_next_completed_run(app: FastAPI) -> None:
    """14 Nov 2026: a rebuild restarted the serve 28 s into the job, startup reconciled it to
    failed with nothing coded, and the one-shot marker kept it from ever running again."""
    hd.arm(app)
    _run(app, complete=False)
    assert not hd.already_done(app)
    _job_row(app, "failed", applied=False)  # what startup's reconcile leaves
    hd.arm(app)
    started, start = _run(app)
    assert started is True
    start.assert_awaited_once()
    assert hd.already_done(app)


@pytest.mark.parametrize(("status", "applied"), [("running", False), ("completed", True),
                                                 ("failed", True)])
def test_a_job_in_flight_or_applied_is_never_retried(app: FastAPI, status: str,
                                                     applied: bool) -> None:
    hd.arm(app)
    _run(app, complete=False)
    _job_row(app, status, applied)
    hd.arm(app)
    started, start = _run(app)
    assert started is False
    start.assert_not_awaited()


def test_an_old_bare_timestamp_marker_reads_as_started_not_done(app: FastAPI) -> None:
    hd.marker_path(app).write_text('{"uxr": "2026-11-14T17:50:25+00:00"}', encoding="utf-8")
    assert not hd.already_done(app)
    assert hd._read_marker(app).get("started")


def test_a_run_in_progress_keeps_it_armed(app: FastAPI) -> None:
    hd.arm(app)
    with patch.object(app.state.screen_text, "run_in_progress", lambda: True):
        started, start = _run(app)
    assert started is False
    start.assert_not_awaited()
    assert app.state.house_default_due is True


def test_a_failed_start_is_logged_not_raised_and_stays_retryable(app: FastAPI) -> None:
    hd.arm(app)
    with (
        patch.object(hd, "_has_screens", lambda _a: True),
        patch(READY),
        patch(START, AsyncMock(side_effect=RuntimeError("boom"))),
    ):
        assert asyncio.run(hd.maybe_apply(app)) is False
    # Installed and started, but not finished: not "done", so the next completed run retries.
    assert not hd.already_done(app)
    assert hd._read_marker(app).get("started")
    assert _linked(app)


def test_the_default_cutoff_accepts_at_and_above_and_stores_it(app: FastAPI) -> None:
    db = app.state.db_factory()
    try:
        quotes = db.query(Quote).filter_by(project_id=1).order_by(Quote.id).all()
        tag = TagDefinition(name="t", codebook_group_id=1)
        db.add(tag)
        db.flush()
        job = AutoCodeJob(project_id=1, framework_id="uxr", status="completed",
                          completed_at=datetime.now(timezone.utc))
        db.add(job)
        db.flush()
        for q, conf in zip(quotes, (0.9, 0.7, 0.5, 0.2), strict=False):
            db.add(ProposedTag(job_id=job.id, quote_id=q.id, tag_definition_id=tag.id,
                               confidence=conf, status="pending", rationale=""))
        db.commit()
        n = len(quotes)
    finally:
        db.close()
    assert n == 4
    assert accept_at_default_cutoff(app.state.db_factory, 1, "uxr", 0.70) == 2
    db = app.state.db_factory()
    try:
        status = {p.confidence: p.status for p in db.query(ProposedTag).all()}
        assert status == {0.9: "accepted", 0.7: "accepted", 0.5: "pending", 0.2: "pending"}
        assert db.query(QuoteTag).filter_by(source="autocode").count() == 2
        stored = db.query(AutoCodeJob).one()
        assert stored.applied_upper_threshold == 0.70
        # Later re-applies must not deny below the dialog's default: nothing was chosen.
        assert stored.applied_lower_threshold == 0.0
    finally:
        db.close()


# ── The job side: when the screen-text thread asks ─────────────────────────────────────────────


class _Engine:
    def available(self) -> None:
        return None


def _job(on_idle: object) -> ScreenTextJob:
    return ScreenTextJob(lambda: None, lambda: Path("."), engine=_Engine(), on_idle=on_idle)  # type: ignore[arg-type]


def test_idle_is_asked_after_a_pass_that_ran_to_the_end() -> None:
    calls: list[bool] = []
    job = _job(lambda: calls.append(job.running))
    job._lock.acquire()
    job.running = True
    with patch.object(job, "_pass", lambda: True):
        job._run()
    assert calls == [False]  # asked after the job let go, never while holding its lock


def test_idle_is_not_asked_when_a_run_stopped_the_pass() -> None:
    calls: list[int] = []
    job = _job(lambda: calls.append(1))
    job._lock.acquire()
    job.running = True
    with patch.object(job, "_pass", lambda: False):
        job._run()
    assert calls == []


def test_a_callback_that_raises_cannot_break_the_job_or_its_lock() -> None:
    def boom() -> None:
        raise RuntimeError("loop closed")

    job = _job(boom)
    job._lock.acquire()
    job.running = True
    with patch.object(job, "_pass", lambda: True):
        job._run()
    assert job.running is False
    assert job._lock.acquire(blocking=False)  # released exactly once, so it can be taken


# ── The wiring: each link of the chain, so deleting one cannot leave the suite green ───────────


def _in_a_thread(fn: object) -> None:
    t = threading.Thread(target=fn)  # type: ignore[arg-type]
    t.start()
    t.join(5)
    assert not t.is_alive()


def test_a_completed_run_arms_the_default(tmp_path: Path) -> None:
    project = tmp_path / "input"
    shutil.copytree(_FIXTURE_DIR, project)
    application = create_app(project_dir=project, dev=True, db_url="sqlite://")
    handler = _make_run_completed_handler(application, application.state.db_factory, project)
    ts = "2026-11-14T12:00:00+00:00"
    with patch.object(ScreenTextJob, "start", lambda self: True):
        asyncio.run(handler(RunCompletedEvent(
            ts=ts, run_id=new_run_id(), kind=KindEnum.RUN, started_at=ts, ended_at=ts)))
    assert application.state.house_default_due is True


def test_screen_reading_ending_reaches_maybe_apply_on_the_loop(app: FastAPI) -> None:
    """The thread-to-loop hop: ``on_idle`` is the job's own callback, ``event_loop`` the lifespan's."""
    from fastapi.testclient import TestClient

    asked = threading.Event()

    async def fake(_app: object) -> bool:
        asked.set()
        return False

    hd.arm(app)
    with patch.object(hd, "maybe_apply", fake), TestClient(app):
        assert app.state.event_loop is not None
        _in_a_thread(app.state.screen_text._on_idle)
        assert asked.wait(5)


def test_an_unarmed_idle_does_not_even_hop_to_the_loop(app: FastAPI) -> None:
    from fastapi.testclient import TestClient

    asked = threading.Event()

    async def fake(_app: object) -> bool:
        asked.set()
        return False

    with patch.object(hd, "maybe_apply", fake), TestClient(app):
        _in_a_thread(app.state.screen_text._on_idle)
        assert not asked.wait(0.3)


def _start_for_real(app: FastAPI, outcome: str) -> list[str]:
    """Run the real ``start_autocode`` with the LLM job stubbed to end as ``outcome``."""
    from unittest.mock import MagicMock

    from bristlenose.server.routes import autocode as routes

    order: list[str] = []

    async def fake_job(db_factory: object, project_id: int, framework_id: str, *a: object, **k: object) -> int:
        db = db_factory()  # type: ignore[operator]
        try:
            db.query(AutoCodeJob).filter_by(project_id=project_id).update({"status": outcome})
            db.commit()
        finally:
            db.close()
        return 0

    async def fake_snapshot(*a: object, **k: object) -> None:
        order.append("snapshot")

    async def go() -> None:
        after = MagicMock(side_effect=lambda: order.append("after_apply"))
        with (
            patch(READY),
            patch.object(routes, "run_autocode_job", fake_job),
            patch("bristlenose.server.routes.signals.materialise_completed_signal_snapshot",
                  fake_snapshot),
        ):
            await routes.start_autocode(app, 1, "uxr", after_apply=after)
            await routes._AUTOCODE_LIVE[(1, "uxr")]

    asyncio.run(go())
    return order


def test_the_cutoff_is_applied_once_the_job_completed_and_before_the_snapshot(app: FastAPI) -> None:
    assert _start_for_real(app, "completed") == ["after_apply", "snapshot"]


def test_a_job_that_did_not_complete_applies_nothing(app: FastAPI) -> None:
    assert _start_for_real(app, "failed") == []
