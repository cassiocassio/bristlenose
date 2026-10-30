"""Durable completed Signals snapshots."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import inspect, text

from bristlenose.events import KindEnum, RunCompletedEvent, new_run_id
from bristlenose.server.app import (
    _make_run_completed_handler,
    _schedule_missing_signal_snapshot,
    create_app,
)
from bristlenose.server.db import Base, create_session_factory, get_engine, init_db, run_migrations
from bristlenose.server.models import Project, SignalSnapshot
from bristlenose.server.routes import signals as signal_routes
from bristlenose.server.routes.signals import (
    _signal_snapshot_has_complete_narratives,
    materialise_completed_signal_snapshot,
)
from bristlenose.server.signal_snapshots import (
    SIGNAL_SNAPSHOT_PAYLOAD_VERSION,
    latest_completed_snapshot,
    snapshot_payload,
    store_completed_snapshot,
)
from tests.conftest import AuthTestClient


def test_snapshot_payload_survives_a_fresh_database_initialisation() -> None:
    engine = get_engine("sqlite://")
    init_db(engine)
    db = create_session_factory(engine)()
    try:
        project = Project(name="P", slug="p", input_dir="/in", output_dir="/out")
        db.add(project)
        db.flush()
        expected = {"codebooks": [{"signals": [{"signal_name": "Order opacity"}]}]}
        db.add(SignalSnapshot(
            project_id=project.id,
            source="codebook_apply",
            payload=json.dumps(expected),
        ))
        db.commit()

        saved = db.query(SignalSnapshot).one()
        assert saved.source == "codebook_apply"
        assert json.loads(saved.payload) == expected
    finally:
        db.close()


def test_migrations_023_and_024_upgrade_an_existing_database() -> None:
    """``create_all`` masks migration mistakes, so exercise the old-DB path."""
    engine = get_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE signal_snapshots"))
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('022')"))

    run_migrations(engine)

    assert "signal_snapshots" in inspect(engine).get_table_names()
    with engine.connect() as conn:
        # 025 is the AutoCode sent-quote register (ruling 4); this test pins that the
        # chain from 022 runs, not which revision is the head.
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "025"


def test_migration_024_adds_evidence_assertions_to_a_pre_024_cache_table() -> None:
    """024 must work against an actual 023-shaped cache, not ORM metadata."""
    engine = get_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE elaboration_caches"))
        conn.execute(text("""
            CREATE TABLE elaboration_caches (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                signal_key VARCHAR NOT NULL,
                content_hash VARCHAR NOT NULL,
                signal_name VARCHAR NOT NULL,
                pattern VARCHAR NOT NULL,
                elaboration TEXT NOT NULL,
                created_at DATETIME
            )
        """))
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('023')"))

    run_migrations(engine)

    columns = {column["name"]: column for column in inspect(engine).get_columns("elaboration_caches")}
    assert "evidence_assertions" in columns
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO elaboration_caches
              (project_id, signal_key, content_hash, signal_name, pattern, elaboration)
            VALUES (1, 'section|Checkout|Clarity', 'hash', 'Title', 'gap', 'Claim')
        """))
        assert conn.execute(text("SELECT evidence_assertions FROM elaboration_caches")).scalar() == "[]"


def test_latest_snapshot_is_newest_and_preserves_its_complete_payload() -> None:
    engine = get_engine("sqlite://")
    init_db(engine)
    db = create_session_factory(engine)()
    try:
        project = Project(name="P", slug="p", input_dir="/in", output_dir="/out")
        db.add(project)
        db.flush()
        store_completed_snapshot(db, project.id, source="codebook_apply", payload={"version": 1})
        newest = store_completed_snapshot(db, project.id, source="new_interviews", payload={"version": 2})
        db.commit()

        assert latest_completed_snapshot(db, project.id).id == newest.id
    finally:
        db.close()


def test_reader_skips_a_corrupt_newer_snapshot_and_keeps_the_last_good_one(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A recoverable bad row must not blank the offline Signals report."""
    engine = get_engine("sqlite://")
    init_db(engine)
    db = create_session_factory(engine)()
    try:
        project = Project(name="P", slug="p", input_dir="/in", output_dir="/out")
        db.add(project)
        db.flush()
        good = store_completed_snapshot(
            db, project.id, source="codebook_apply", payload={"version": 1},
        )
        bad = SignalSnapshot(
            project_id=project.id,
            source="new_interviews",
            payload="not json",
        )
        db.add(bad)
        db.commit()

        with caplog.at_level("WARNING"):
            assert latest_completed_snapshot(db, project.id).id == good.id
        # The skip is logged by id so a maintainer can see it; never the payload.
        assert f"snapshot {bad.id} for project {project.id}" in caplog.text
        assert "not json" not in caplog.text
    finally:
        db.close()


def test_reader_endpoint_returns_the_saved_payload_without_calculating() -> None:
    app = create_app(dev=True, db_url="sqlite://")
    db = app.state.db_factory()
    try:
        project = Project(name="P", slug="p", input_dir="/in", output_dir="/out")
        db.add(project)
        db.flush()
        store_completed_snapshot(
            db,
            project.id,
            source="codebook_apply",
            payload={"codebooks": [{"signals": [{"signal_name": "Order opacity"}]}]},
        )
        db.commit()
        project_id = project.id
    finally:
        db.close()

    response = AuthTestClient(app).get(f"/api/projects/{project_id}/signals/snapshot")

    assert response.status_code == 200
    assert response.json()["source"] == "codebook_apply"
    assert response.json()["snapshot"]["codebooks"][0]["signals"][0]["signal_name"] == "Order opacity"


def test_lifecycle_materialisation_writes_a_complete_empty_card_set() -> None:
    """The lifecycle writer, not a reader, owns snapshot creation."""
    engine = get_engine("sqlite://")
    init_db(engine)
    db = create_session_factory(engine)()
    try:
        project = Project(name="P", slug="p", input_dir="/in", output_dir="/out")
        db.add(project)
        db.commit()

        asyncio.run(materialise_completed_signal_snapshot(
            db, project.id, source="codebook_apply",
        ))

        saved = latest_completed_snapshot(db, project.id)
        assert saved is not None
        assert saved.source == "codebook_apply"
        assert json.loads(saved.payload)["codebooks"] == []
    finally:
        db.close()


def test_metrics_only_custom_cards_do_not_block_a_completed_framework_snapshot() -> None:
    assert _signal_snapshot_has_complete_narratives({
        "codebooks": [
            {"codebook_id": "framework", "signals": [
                {"signal_name": "Stock clarity arrives late", "elaboration": "Claim."},
            ]},
            {"codebook_id": "custom", "signals": [
                {"signal_name": None, "elaboration": None},
            ]},
        ],
    })


def test_materialisation_keeps_last_good_snapshot_when_narrative_is_partial(monkeypatch) -> None:
    """A provider/cache partial result is not a completed offline report."""
    engine = get_engine("sqlite://")
    init_db(engine)
    db = create_session_factory(engine)()
    try:
        project = Project(name="P", slug="p", input_dir="/in", output_dir="/out")
        db.add(project)
        db.flush()
        original = store_completed_snapshot(
            db, project.id, source="codebook_apply", payload={"version": "last-good"},
        )
        db.commit()

        async def fake_build(*_args, **_kwargs):
            return SimpleNamespace(model_dump=lambda **_kw: {
                "codebooks": [{"signals": [{"signal_name": None, "elaboration": None}]}],
            })

        monkeypatch.setattr(signal_routes, "_build_codebook_analysis", fake_build)
        asyncio.run(materialise_completed_signal_snapshot(
            db, project.id, source="new_interviews",
        ))

        assert latest_completed_snapshot(db, project.id).id == original.id
        assert db.query(SignalSnapshot).count() == 1
    finally:
        db.close()


def test_run_completed_with_cloud_disabled_preserves_the_existing_snapshot(
    tmp_path, monkeypatch,
) -> None:
    """Post-study manual work must not erase the last cloud-authored report."""
    project_dir = tmp_path / "project"
    (project_dir / "bristlenose-output").mkdir(parents=True)
    app = create_app(project_dir=project_dir, dev=True, db_url="sqlite://")
    db = app.state.db_factory()
    try:
        project = Project(name="P", slug="p", input_dir="/in", output_dir="/out")
        db.add(project)
        db.flush()
        original = store_completed_snapshot(
            db, project.id, source="codebook_apply", payload={"version": 1},
        )
        db.commit()
        project_id = project.id
        original_id = original.id
    finally:
        db.close()

    app.state.settings = SimpleNamespace(llm_provider="local")
    monkeypatch.setattr("bristlenose.server.importer.import_project", lambda _db, _path: None)
    handler = _make_run_completed_handler(app, app.state.db_factory, project_dir)
    event = RunCompletedEvent(
        ts="2026-10-27T00:00:00Z",
        run_id=new_run_id(),
        kind=KindEnum.RUN,
        started_at="2026-10-27T00:00:00Z",
        ended_at="2026-10-27T00:01:00Z",
    )

    asyncio.run(handler(event))

    db = app.state.db_factory()
    try:
        assert latest_completed_snapshot(db, project_id).id == original_id
        assert db.query(SignalSnapshot).count() == 1
    finally:
        db.close()


def test_startup_quietly_materialises_a_missing_snapshot_when_cloud_is_available(
    tmp_path, monkeypatch,
) -> None:
    """A legacy study should not need a researcher-facing refresh action."""
    app = create_app(dev=True, db_url="sqlite://")
    db = app.state.db_factory()
    try:
        project = Project(name="P", slug="p", input_dir="/in", output_dir="/out")
        db.add(project)
        db.commit()
        project_id = project.id
    finally:
        db.close()

    app.state.settings = SimpleNamespace(llm_provider="openai")
    monkeypatch.setattr("bristlenose.server.elaboration._has_api_key", lambda _settings: True)
    called: list[tuple[int, str, object]] = []

    async def fake_materialise(db, received_project_id, *, source, project_dir):
        called.append((received_project_id, source, project_dir))

    monkeypatch.setattr(signal_routes, "materialise_completed_signal_snapshot", fake_materialise)

    async def scenario() -> None:
        task = _schedule_missing_signal_snapshot(app, app.state.db_factory, tmp_path)
        await task

    asyncio.run(scenario())

    assert called == [(project_id, "startup_missing_snapshot", tmp_path)]


def test_startup_does_not_rewrite_an_existing_snapshot(monkeypatch, tmp_path) -> None:
    app = create_app(dev=True, db_url="sqlite://")
    db = app.state.db_factory()
    try:
        project = Project(name="P", slug="p", input_dir="/in", output_dir="/out")
        db.add(project)
        db.flush()
        store_completed_snapshot(db, project.id, source="codebook_apply", payload={"version": 1})
        db.commit()
    finally:
        db.close()

    app.state.settings = SimpleNamespace(llm_provider="openai")
    monkeypatch.setattr("bristlenose.server.elaboration._has_api_key", lambda _settings: True)

    async def must_not_run(*_args, **_kwargs):
        raise AssertionError("an existing frozen snapshot must be left alone")

    monkeypatch.setattr(signal_routes, "materialise_completed_signal_snapshot", must_not_run)

    async def scenario() -> None:
        task = _schedule_missing_signal_snapshot(app, app.state.db_factory, tmp_path)
        await task

    asyncio.run(scenario())


def test_startup_quietly_upgrades_an_older_snapshot_when_cloud_is_available(
    tmp_path, monkeypatch,
) -> None:
    """A narrative-contract release is a one-time lifecycle repair, not UI."""
    app = create_app(dev=True, db_url="sqlite://")
    db = app.state.db_factory()
    try:
        project = Project(name="P", slug="p", input_dir="/in", output_dir="/out")
        db.add(project)
        db.flush()
        db.add(SignalSnapshot(
            project_id=project.id,
            source="codebook_apply",
            payload_version=SIGNAL_SNAPSHOT_PAYLOAD_VERSION - 1,
            payload=json.dumps({"version": "older-contract"}),
        ))
        db.commit()
        project_id = project.id
    finally:
        db.close()

    app.state.settings = SimpleNamespace(llm_provider="openai")
    monkeypatch.setattr("bristlenose.server.elaboration._has_api_key", lambda _settings: True)
    called: list[tuple[int, str, object]] = []

    async def fake_materialise(db, received_project_id, *, source, project_dir):
        called.append((received_project_id, source, project_dir))

    monkeypatch.setattr(signal_routes, "materialise_completed_signal_snapshot", fake_materialise)

    async def scenario() -> None:
        task = _schedule_missing_signal_snapshot(app, app.state.db_factory, tmp_path)
        await task

    asyncio.run(scenario())

    assert called == [(project_id, "startup_snapshot_upgrade", tmp_path)]


def test_startup_missing_snapshot_pending_settles_without_a_cloud_provider(tmp_path) -> None:
    """An offline study must not make its open Signals lens retry forever."""
    app = create_app(dev=True, db_url="sqlite://")
    db = app.state.db_factory()
    try:
        db.add(Project(name="P", slug="p", input_dir="/in", output_dir="/out"))
        db.commit()
    finally:
        db.close()

    app.state.settings = SimpleNamespace(llm_provider="local")

    async def scenario() -> None:
        task = _schedule_missing_signal_snapshot(app, app.state.db_factory, tmp_path)
        assert app.state.initial_signal_snapshot_pending is True
        await task

    asyncio.run(scenario())
    assert app.state.initial_signal_snapshot_pending is False


def test_overlapping_lifecycle_writes_preserve_arrival_order(monkeypatch) -> None:
    """A slow earlier synthesis cannot overwrite a later lifecycle event."""
    engine = get_engine("sqlite://")
    init_db(engine)
    session_factory = create_session_factory(engine)
    db = session_factory()
    try:
        project = Project(name="P", slug="p", input_dir="/in", output_dir="/out")
        db.add(project)
        db.commit()
        project_id = project.id
    finally:
        db.close()

    async def scenario() -> None:
        first_started = asyncio.Event()
        let_first_finish = asyncio.Event()
        builds: list[int] = []

        async def fake_build(*_args, **_kwargs):
            builds.append(len(builds) + 1)
            if len(builds) == 1:
                first_started.set()
                await let_first_finish.wait()
            return SimpleNamespace(model_dump=lambda **_kw: {
                "build": builds[-1], "codebooks": [],
            })

        monkeypatch.setattr(signal_routes, "_build_codebook_analysis", fake_build)
        first_db = session_factory()
        second_db = session_factory()
        try:
            first = asyncio.create_task(materialise_completed_signal_snapshot(
                first_db, project_id, source="codebook_apply",
            ))
            await first_started.wait()
            second = asyncio.create_task(materialise_completed_signal_snapshot(
                second_db, project_id, source="new_interviews",
            ))
            await asyncio.sleep(0)
            assert builds == [1]  # second lifecycle waits behind the first
            let_first_finish.set()
            await asyncio.gather(first, second)
        finally:
            first_db.close()
            second_db.close()

    asyncio.run(scenario())
    db = session_factory()
    try:
        latest = latest_completed_snapshot(db, project_id)
        assert latest.source == "new_interviews"
        assert snapshot_payload(latest) == {"build": 2, "codebooks": []}
    finally:
        db.close()
