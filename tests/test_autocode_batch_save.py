"""AutoCode saves each batch as it answers (docs/design-autocode-landing-plan.md Phase 1).

Against a real database FILE, as serve runs it: an in-memory database is one
connection shared by every session, so it cannot show a lock, a second writer or
what another session sees mid-run. The LLM is mocked; no call is paid for.

Also here: a catch-up sorts each batch by the lines stored when it saves (review 8),
and when Signals is rebuilt after AutoCode (D21, review 9).
"""

from __future__ import annotations

import asyncio
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import event

from bristlenose.server import autocode, busy
from bristlenose.server.autocode import (
    owed_quotes,
    reapply_to_new_quotes,
    reconcile_orphaned_jobs,
    run_autocode_job,
)
from bristlenose.server.codebook import get_template
from bristlenose.server.db import Base, create_session_factory, get_engine
from bristlenose.server.models import (
    AutoCodeJob,
    AutoCodeSentQuote,
    CodebookGroup,
    Project,
    ProjectCodebookGroup,
    ProposedTag,
    Quote,
    QuoteTag,
    TagDefinition,
)
from tests.test_autocode_engine import _make_batch_result, _mock_settings, _patch_llm


def _file_project(
    tmp_path: Path, n_quotes: int, *, busy_ms: int | None = None, applied: bool = False,
) -> tuple[Any, Any, int, Path]:
    """A study database file with Garrett installed and ``n_quotes`` quotes, and its
    job (``applied`` sets ``completed_at``, as after a first apply). ``busy_ms``
    shortens the write-lock wait so a test can hold the lock past it quickly."""
    db_path = tmp_path / "bristlenose.db"
    engine = get_engine(f"sqlite:///{db_path}")
    if busy_ms is not None:

        @event.listens_for(engine, "connect")
        def _short_wait(dbapi_connection, _record):  # type: ignore[no-untyped-def]
            dbapi_connection.execute(f"PRAGMA busy_timeout={busy_ms}")

    Base.metadata.create_all(engine)
    session_cls = create_session_factory(engine)
    db = session_cls()
    project = Project(name="P", slug="p", input_dir=str(tmp_path), output_dir=str(tmp_path))
    db.add(project)
    db.flush()
    template = get_template("garrett")
    assert template is not None
    for group_tmpl in template.groups:
        group = CodebookGroup(
            name=group_tmpl.name, subtitle=group_tmpl.subtitle,
            colour_set=group_tmpl.colour_set, framework_id="garrett",
        )
        db.add(group)
        db.flush()
        db.add(ProjectCodebookGroup(project_id=project.id, codebook_group_id=group.id))
        for tag_tmpl in group_tmpl.tags:
            db.add(TagDefinition(name=tag_tmpl.name, codebook_group_id=group.id))
    for i in range(n_quotes):
        db.add(Quote(
            project_id=project.id, session_id="s1", participant_id="p1",
            start_timecode=float(i * 10), end_timecode=float(i * 10 + 5),
            text=f"Quote {i}", quote_type="screen_specific",
        ))
    db.add(AutoCodeJob(
        project_id=project.id, framework_id="garrett",
        status="completed" if applied else "pending",
        completed_at=datetime(2026, 11, 1, tzinfo=timezone.utc) if applied else None,
        applied_upper_threshold=0.9 if applied else None,
        applied_lower_threshold=0.3 if applied else None,
    ))
    db.commit()
    project_id = project.id
    db.close()
    return session_cls, engine, project_id, db_path


def _n_in_prompt(user_prompt: str) -> int:
    return len(re.findall(r"^\d+\. \[", user_prompt, re.MULTILINE))


def _counts(session_cls: Any) -> tuple[int, int, int]:
    """(proposals, register rows, the job's proposed_count), read by another session."""
    db = session_cls()
    try:
        job = db.query(AutoCodeJob).one()
        return (
            db.query(ProposedTag).count(),
            db.query(AutoCodeSentQuote).count(),
            job.proposed_count,
        )
    finally:
        db.close()


def _settings() -> Any:
    settings = _mock_settings()
    settings.llm_concurrency = 1  # batches one after another, for a deterministic order
    return settings


# ---------------------------------------------------------------------------
# A first apply
# ---------------------------------------------------------------------------


def test_each_batch_is_saved_with_its_register_entries_as_it_answers(tmp_path) -> None:
    session_cls, engine, project_id, _ = _file_project(tmp_path, 50)
    seen: list[tuple[int, int, int]] = []

    async def analyze(system_prompt, user_prompt, response_model, **kw):  # type: ignore[no-untyped-def]
        seen.append(_counts(session_cls))
        return _make_batch_result(_n_in_prompt(user_prompt), "user need", 0.8)

    progress_before = busy.progress()
    with _patch_llm(AsyncMock(side_effect=analyze)):
        asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))

    # While the second batch was out, the first was already there, whole.
    assert seen == [(0, 0, 0), (25, 25, 25)]
    assert _counts(session_cls) == (50, 50, 50)
    # The host's progress figure moved by every quote answered.
    assert busy.progress() - progress_before == 50
    engine.dispose()


def test_a_batchs_proposals_and_register_entries_land_together(tmp_path) -> None:
    """A save whose register half fails keeps neither half; the batch is held and
    lands with the end of the run, both halves together."""
    session_cls, engine, project_id, _ = _file_project(tmp_path, 50)
    seen: list[tuple[int, int, int]] = []
    real_record_sent = autocode.record_sent
    calls = {"n": 0}

    def flaky_record_sent(db, job_id, quote_ids):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("the register write failed")
        return real_record_sent(db, job_id, quote_ids)

    async def analyze(system_prompt, user_prompt, response_model, **kw):  # type: ignore[no-untyped-def]
        seen.append(_counts(session_cls))
        return _make_batch_result(_n_in_prompt(user_prompt), "user need", 0.8)

    with _patch_llm(AsyncMock(side_effect=analyze)), patch.object(
        autocode, "record_sent", flaky_record_sent,
    ):
        asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))

    assert seen[1] == (0, 0, 0)  # the first batch's proposals did not land without it
    assert _counts(session_cls) == (50, 50, 50)
    engine.dispose()


def _hold_the_write_lock(db_path: Path, release: threading.Event, held: threading.Event) -> None:
    conn = sqlite3.connect(db_path, timeout=5)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE projects SET name = 'held' WHERE id = 1")
        held.set()
        release.wait(10)
        conn.commit()
    finally:
        conn.close()


def test_a_writer_holding_the_lock_does_not_lose_a_batch(tmp_path, monkeypatch) -> None:
    """Another connection holds the write lock through every try of the first batch's
    save: the batch is kept and saved with the end of the run, never dropped."""
    session_cls, engine, project_id, db_path = _file_project(tmp_path, 50, busy_ms=30)
    monkeypatch.setattr(autocode, "SAVE_BACKOFF_S", (0.01,))
    release, held = threading.Event(), threading.Event()
    seen: list[tuple[int, int, int]] = []
    holder: list[threading.Thread] = []

    async def analyze(system_prompt, user_prompt, response_model, **kw):  # type: ignore[no-untyped-def]
        if not holder:
            t = threading.Thread(target=_hold_the_write_lock, args=(db_path, release, held))
            t.start()
            holder.append(t)
            assert held.wait(5)
        else:
            seen.append(_counts(session_cls))
            release.set()
            holder[0].join(5)
        return _make_batch_result(_n_in_prompt(user_prompt), "user need", 0.8)

    with _patch_llm(AsyncMock(side_effect=analyze)):
        asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))

    assert seen == [(0, 0, 0)]  # the first batch could not be saved while the lock was held
    assert _counts(session_cls) == (50, 50, 50)
    db = session_cls()
    try:
        job = db.query(AutoCodeJob).one()
        assert (job.status, job.processed_quotes, job.failure_kind) == ("completed", 50, "")
        assert job.completed_at is not None
    finally:
        db.close()
    engine.dispose()


def test_a_writer_that_lets_go_in_time_is_waited_for(tmp_path, monkeypatch) -> None:
    """A lock held for a moment is a retry, not a deferral: the batch is saved as it
    answered, before the next one goes."""
    session_cls, engine, project_id, db_path = _file_project(tmp_path, 50, busy_ms=30)
    monkeypatch.setattr(autocode, "SAVE_BACKOFF_S", (0.1, 0.2, 0.4))
    release, held = threading.Event(), threading.Event()
    seen: list[tuple[int, int, int]] = []

    async def analyze(system_prompt, user_prompt, response_model, **kw):  # type: ignore[no-untyped-def]
        if not seen and not held.is_set():
            threading.Thread(
                target=_hold_the_write_lock, args=(db_path, release, held), daemon=True,
            ).start()
            assert held.wait(5)
            threading.Timer(0.08, release.set).start()
        else:
            seen.append(_counts(session_cls))
        return _make_batch_result(_n_in_prompt(user_prompt), "user need", 0.8)

    with _patch_llm(AsyncMock(side_effect=analyze)):
        asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))

    assert seen == [(25, 25, 25)]
    assert _counts(session_cls) == (50, 50, 50)
    engine.dispose()


def test_a_crash_between_batches_keeps_the_saved_batches_and_the_sweep_keeps_the_counts(
    tmp_path,
) -> None:
    """The serve dies while the second batch is out: the first is saved, the boot
    sweep fails the job with its counts as they were, and a retry sends only the rest."""
    session_cls, engine, project_id, _ = _file_project(tmp_path, 50)

    async def main() -> None:
        second = asyncio.Event()
        calls = {"n": 0}

        async def analyze(system_prompt, user_prompt, response_model, **kw):  # type: ignore[no-untyped-def]
            calls["n"] += 1
            if calls["n"] == 2:
                second.set()
                await asyncio.Event().wait()  # never answers
            return _make_batch_result(_n_in_prompt(user_prompt), "user need", 0.8)

        with _patch_llm(AsyncMock(side_effect=analyze)):
            task = asyncio.ensure_future(
                run_autocode_job(session_cls, project_id, "garrett", _settings())
            )
            await second.wait()
            task.cancel()  # the process goes; no handler of the job's runs
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(main())

    db = session_cls()
    try:
        assert db.query(AutoCodeJob).one().status == "running"  # as a crash leaves it
        assert reconcile_orphaned_jobs(db) == 1
        job = db.query(AutoCodeJob).one()
        assert job.status == "failed"
        assert (job.processed_quotes, job.proposed_count) == (25, 25)
        assert job.completed_at is None
        assert db.query(ProposedTag).count() == 25
        assert len(owed_quotes(db, job)) == 25
    finally:
        db.close()
    engine.dispose()


# ---------------------------------------------------------------------------
# A catch-up
# ---------------------------------------------------------------------------


def test_a_catch_up_saves_each_batch_by_the_lines_stored_when_it_saves(tmp_path) -> None:
    """A re-cut made while a catch-up codes applies to the batches it saves after
    the re-cut (review 8): the lines are read as each batch is saved."""
    session_cls, engine, project_id, _ = _file_project(tmp_path, 50, applied=True)
    seen: list[tuple[int, int]] = []

    def mixed(n: int) -> Any:
        result = _make_batch_result(n, "user need", 0.8)
        for a in result.assignments[1::2]:
            a.confidence = 0.2  # below the exclude line
        return result

    async def analyze(system_prompt, user_prompt, response_model, **kw):  # type: ignore[no-untyped-def]
        db = session_cls()
        try:
            seen.append((db.query(ProposedTag).count(), db.query(AutoCodeSentQuote).count()))
            if len(seen) == 2:
                # The researcher re-cuts in the review while the second batch is out.
                db.query(AutoCodeJob).update({AutoCodeJob.applied_upper_threshold: 0.75})
                db.commit()
        finally:
            db.close()
        return mixed(_n_in_prompt(user_prompt))

    with _patch_llm(AsyncMock(side_effect=analyze)):
        accepted = asyncio.run(
            reapply_to_new_quotes(session_cls, project_id, "garrett", _settings())
        )

    assert seen == [(0, 0), (25, 25)]
    db = session_cls()
    try:
        rows = db.query(ProposedTag).order_by(ProposedTag.quote_id).all()
        first, second = rows[:25], rows[25:]
        # Saved before the re-cut, by 0.90: 0.8 stays tentative.
        assert {(p.status, p.decided_by) for p in first if p.confidence == 0.8} == {
            ("pending", None)}
        # Saved after it, by 0.75: 0.8 is accepted, a threshold decision.
        assert {(p.status, p.decided_by) for p in second if p.confidence == 0.8} == {
            ("accepted", "threshold")}
        assert {(p.status, p.decided_by) for p in rows if p.confidence == 0.2} == {
            ("denied", "threshold")}
        assert accepted == db.query(QuoteTag).count() == 13
        job = db.query(AutoCodeJob).one()
        assert (job.total_quotes, job.processed_quotes, job.proposed_count) == (50, 50, 50)
    finally:
        db.close()
    engine.dispose()


# ---------------------------------------------------------------------------
# When Signals is rebuilt (D21, review 9)
# ---------------------------------------------------------------------------


def _fake_app(session_cls: Any) -> Any:
    return SimpleNamespace(state=SimpleNamespace(db_factory=session_cls, project_dir=None))


def test_concurrent_passes_rebuild_signals_once_when_the_last_ends(tmp_path) -> None:
    session_cls, engine, _, _ = _file_project(tmp_path, 1)
    app = _fake_app(session_cls)
    build = AsyncMock()

    async def main() -> list[int]:
        go_a, go_b, go_c = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def a_pass(go: asyncio.Event, source: str | None) -> None:
            await go.wait()
            await autocode.coding_ended(app, 1, snapshot_source=source)

        calls: list[int] = []
        tasks = []
        for go, source in ((go_a, "codebook_apply"), (go_b, "codebook_apply"), (go_c, None)):
            task = asyncio.ensure_future(a_pass(go, source))
            autocode.coding_started(1, task)
            tasks.append(task)
        for go in (go_a, go_b, go_c):  # two applies end, then a catch-up
            go.set()
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            calls.append(build.await_count)
        await asyncio.gather(*tasks)
        return calls

    with patch("bristlenose.server.routes.signals.materialise_completed_signal_snapshot", build):
        calls = asyncio.run(main())

    assert calls == [0, 0, 1]
    assert build.await_args.kwargs["source"] == "codebook_apply"
    engine.dispose()


def test_a_pass_that_ends_alone_rebuilds_at_once_and_one_that_changed_nothing_does_not(
    tmp_path,
) -> None:
    session_cls, engine, _, _ = _file_project(tmp_path, 1)
    app = _fake_app(session_cls)
    build = AsyncMock()

    async def one(source: str | None) -> None:
        async def body() -> None:
            await autocode.coding_ended(app, 1, snapshot_source=source)

        task = asyncio.ensure_future(body())
        autocode.coding_started(1, task)
        await task

    with patch("bristlenose.server.routes.signals.materialise_completed_signal_snapshot", build):
        asyncio.run(one(None))
        assert build.await_count == 0
        asyncio.run(one("new_interviews"))
        assert build.await_count == 1
    engine.dispose()


def test_a_burst_of_recuts_rebuilds_once_and_waits_for_a_pass_still_coding(
    tmp_path, monkeypatch,
) -> None:
    session_cls, engine, _, _ = _file_project(tmp_path, 1)
    app = _fake_app(session_cls)
    build = AsyncMock()
    monkeypatch.setattr(autocode, "RECUT_SNAPSHOT_DEBOUNCE_S", 0.05)

    async def main() -> tuple[int, int, int]:
        for _ in range(3):
            autocode.recut_made(app, 1)
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.2)
        after_burst = build.await_count

        go = asyncio.Event()

        async def a_pass() -> None:
            await go.wait()
            await autocode.coding_ended(app, 1, snapshot_source=None)

        task = asyncio.ensure_future(a_pass())
        autocode.coding_started(1, task)
        autocode.recut_made(app, 1)
        await asyncio.sleep(0.2)
        while_coding = build.await_count
        go.set()
        await task
        return after_burst, while_coding, build.await_count

    with patch("bristlenose.server.routes.signals.materialise_completed_signal_snapshot", build):
        assert asyncio.run(main()) == (1, 1, 2)
    assert build.await_args.kwargs["source"] == "codebook_recut"
    engine.dispose()


@pytest.mark.parametrize(
    ("status", "accepted", "expected"),
    [
        ("completed", False, "codebook_apply"),
        ("cancelled", True, "codebook_stopped"),
        ("cancelled", False, None),
        ("failed", True, None),
    ],
)
def test_how_a_first_apply_ended_says_whether_signals_is_rebuilt(
    tmp_path, status: str, accepted: bool, expected: str | None,
) -> None:
    from bristlenose.server.routes.autocode import _settle_first_apply

    session_cls, engine, project_id, _ = _file_project(tmp_path, 1)
    db = session_cls()
    try:
        job = db.query(AutoCodeJob).one()
        job.status = status
        quote = db.query(Quote).one()
        tag = db.query(TagDefinition).first()
        assert tag is not None
        db.add(ProposedTag(
            job_id=job.id, quote_id=quote.id, tag_definition_id=tag.id, confidence=0.9,
            status="accepted" if accepted else "pending",
        ))
        db.commit()
    finally:
        db.close()
    after: list[bool] = []
    assert _settle_first_apply(
        session_cls, project_id, "garrett", lambda: after.append(True),
    ) == expected
    assert after == ([True] if status == "completed" else [])
    engine.dispose()
