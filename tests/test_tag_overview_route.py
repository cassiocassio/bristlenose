"""The tag sidebar overview's route and migration 029 (landing plan Phase 6: D12, D17, D22).

What the overview draws (reviewable codebooks only: never Sentiment, never a codebook with
nothing to show; Review inactive while a first apply codes), what it remembers per study
(open, split, opened-by-itself-once), and that it never reaches an export.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.models import AutoCodeJob, ProposedTag, Quote
from tests.conftest import AuthTestClient
from tests.test_serve_autocode_api import _FIXTURE_DIR, _import_garrett

BASE = "/api/projects/1"
URL = f"{BASE}/tag-overview"


def _add_job(app: object, fw: str, status: str, done: bool, confs: list[float],
             tag_ids: list[int], statuses: list[str] | None = None) -> None:
    db = app.state.db_factory()  # type: ignore[attr-defined]
    try:
        quotes = db.query(Quote).filter_by(project_id=1).order_by(Quote.id).all()
        job = AutoCodeJob(
            project_id=1, framework_id=fw, status=status,
            total_quotes=len(quotes), processed_quotes=len(confs), proposed_count=len(confs),
            completed_at=datetime.now(timezone.utc) if done else None,
            applied_lower_threshold=0.3 if done else None,
            applied_upper_threshold=0.7 if done else None,
        )
        db.add(job)
        db.flush()
        for i, conf in enumerate(confs):
            db.add(ProposedTag(
                job_id=job.id, quote_id=quotes[i].id, tag_definition_id=tag_ids[i],
                confidence=conf, rationale="r",
                status=(statuses[i] if statuses else "pending"),
            ))
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def app_and_tags() -> tuple[object, list[int]]:
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return app, _import_garrett(app)


@pytest.fixture()
def client(app_and_tags: tuple[object, list[int]]) -> TestClient:
    return AuthTestClient(app_and_tags[0])


class TestRemembered:
    def test_a_study_with_no_row_is_closed_merged_and_never_opened(self, client) -> None:
        got = client.get(URL).json()
        assert (got["open"], got["split"], got["auto_opened"]) == (False, False, False)
        assert got["codebooks"] == []

    def test_a_patch_writes_only_the_fields_it_names(self, client) -> None:
        assert client.patch(URL, json={"open": True, "auto_opened": True}).status_code == 200
        assert client.patch(URL, json={"split": True}).status_code == 200
        got = client.get(URL).json()
        assert (got["open"], got["split"], got["auto_opened"]) == (True, True, True)
        assert client.patch(URL, json={"open": False}).status_code == 200
        got = client.get(URL).json()
        assert (got["open"], got["split"], got["auto_opened"]) == (False, True, True)

    def test_a_patch_refuses_a_field_it_does_not_know(self, client) -> None:
        assert client.patch(URL, json={"opened": True}).status_code == 422

    def test_another_project_is_not_found(self, client) -> None:
        assert client.get("/api/projects/99/tag-overview").status_code == 404
        assert client.patch("/api/projects/99/tag-overview", json={"open": True}).status_code == 404


class TestCodebooks:
    def test_a_finished_run_is_listed_with_its_lines_and_bands(self, app_and_tags) -> None:
        app, tags = app_and_tags
        _add_job(app, "garrett", "completed", True, [0.1, 0.5, 0.8, 0.95], tags,
                 ["denied", "pending", "accepted", "accepted"])
        got = AuthTestClient(app).get(URL).json()["codebooks"]
        assert [c["framework_id"] for c in got] == ["garrett"]
        book = got[0]
        assert (book["coding"], book["lower"], book["upper"]) == (False, 0.3, 0.7)
        assert len(book["bins"]) == 20
        assert book["bins"][2]["excluded"] == 1
        assert book["bins"][10]["tentative"] == 1
        assert book["bins"][16]["accepted"] == 1
        assert book["bins"][19]["accepted"] == 1

    def test_sentiment_is_never_reviewable(self, app_and_tags) -> None:
        app, tags = app_and_tags
        _add_job(app, "sentiment", "completed", True, [0.5, 0.9], tags)
        assert AuthTestClient(app).get(URL).json()["codebooks"] == []

    def test_a_run_still_coding_is_listed_and_says_so(self, app_and_tags) -> None:
        app, tags = app_and_tags
        _add_job(app, "garrett", "running", False, [], tags)
        got = AuthTestClient(app).get(URL).json()["codebooks"]
        assert [(c["framework_id"], c["coding"], c["lower"]) for c in got] == [
            ("garrett", True, None)
        ]

    def test_a_catch_up_on_an_applied_codebook_is_not_coding(self, app_and_tags) -> None:
        # D20: Review stays live while a catch-up runs. An applied job keeps completed_at.
        app, tags = app_and_tags
        _add_job(app, "garrett", "running", True, [0.5], tags)
        got = AuthTestClient(app).get(URL).json()["codebooks"]
        assert got[0]["coding"] is False

    def test_a_run_that_ended_with_nothing_is_not_listed(self, app_and_tags) -> None:
        app, tags = app_and_tags
        _add_job(app, "garrett", "failed", False, [], tags)
        assert AuthTestClient(app).get(URL).json()["codebooks"] == []


class TestOneCountedSet:
    def test_the_quotes_that_count_are_worked_out_once_per_read(self, app_and_tags, monkeypatch) -> None:
        import bristlenose.server.routes.tag_overview as overview

        app, tags = app_and_tags
        _add_job(app, "garrett", "completed", True, [0.5, 0.8], tags)
        _add_job(app, "uxr", "completed", True, [0.6], tags)
        calls: list[int] = []
        real = overview._counted_quote_ids

        def counting(db: object, project_id: int) -> set[int]:
            calls.append(project_id)
            return real(db, project_id)  # type: ignore[arg-type]

        monkeypatch.setattr(overview, "_counted_quote_ids", counting)
        import bristlenose.server.routes.autocode as autocode_routes

        monkeypatch.setattr(autocode_routes, "_counted_quote_ids", counting)
        got = AuthTestClient(app).get(URL).json()["codebooks"]
        assert len(got) == 2
        assert calls == [1]


class TestExport:
    def test_the_overview_is_server_only(self) -> None:
        from bristlenose.server.routes.export import (
            EMBED_PATH_TEMPLATES,
            SERVER_ONLY_PATH_TEMPLATES,
        )

        path = "/projects/{project_id}/tag-overview"
        assert path in SERVER_ONLY_PATH_TEMPLATES
        assert path not in EMBED_PATH_TEMPLATES


class TestRaceSafePatch:
    def test_two_first_writes_at_once_both_land(self, tmp_path: Path) -> None:
        import threading

        app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url=f"sqlite:///{tmp_path / 'r.db'}")
        client = AuthTestClient(app)
        barrier = threading.Barrier(2)
        codes: list[int] = []

        def write(body: dict[str, bool]) -> None:
            barrier.wait()
            codes.append(client.patch(URL, json=body).status_code)

        threads = [threading.Thread(target=write, args=(b,))
                   for b in ({"open": True}, {"split": True})]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert codes == [200, 200]
        got = client.get(URL).json()
        assert (got["open"], got["split"]) == (True, True)
        db = app.state.db_factory()
        try:
            from bristlenose.server.models import TagOverviewState

            assert db.query(TagOverviewState).count() == 1
        finally:
            db.close()

    def test_a_first_write_onto_a_row_made_meanwhile_lands(self, client) -> None:
        # The insert yields to a row another write made, then updates it.
        db = client.app.state.db_factory()  # type: ignore[attr-defined]
        try:
            from bristlenose.server.models import TagOverviewState

            db.add(TagOverviewState(project_id=1, split=True))
            db.commit()
        finally:
            db.close()
        assert client.patch(URL, json={"open": True}).status_code == 200
        got = client.get(URL).json()
        assert (got["open"], got["split"]) == (True, True)


class TestLiveLine:
    def test_a_first_apply_reports_its_live_accept_line(self, app_and_tags) -> None:
        app, tags = app_and_tags
        _add_job(app, "garrett", "running", False, [0.9], tags)
        db = app.state.db_factory()  # type: ignore[attr-defined]
        try:
            job = db.query(AutoCodeJob).one()
            job.live_accept_line = 0.8
            db.commit()
        finally:
            db.close()
        got = AuthTestClient(app).get(URL).json()["codebooks"][0]
        assert (got["coding"], got["live_accept_line"], got["upper"]) == (True, 0.8, None)


class TestMigration029:
    def _db_at_028(self, tmp_path: Path) -> sa.Engine:
        from bristlenose.server.db import create_session_factory, init_db
        from bristlenose.server.models import Project

        engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
        init_db(engine)
        db = create_session_factory(engine)()
        db.add(Project(id=1, name="Old", input_dir=str(tmp_path), output_dir=str(tmp_path)))
        db.commit()
        db.close()
        with engine.connect() as conn:
            conn.execute(sa.text("DROP TABLE tag_overview_states"))
            conn.execute(sa.text("UPDATE alembic_version SET version_num = '028'"))
            conn.commit()
        return engine

    def test_an_old_study_gets_the_table_and_reads_closed(self, tmp_path: Path) -> None:
        from bristlenose.server.db import run_migrations
        from tests.test_migrations import MIGRATION_HEAD

        engine = self._db_at_028(tmp_path)
        run_migrations(engine)
        with engine.connect() as conn:
            version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
            rows = conn.execute(sa.text("SELECT COUNT(*) FROM tag_overview_states")).scalar()
            conn.execute(sa.text("INSERT INTO tag_overview_states (project_id) VALUES (1)"))
            row = conn.execute(
                sa.text("SELECT open, split, auto_opened FROM tag_overview_states")
            ).one()
        assert version == MIGRATION_HEAD == "029"
        assert rows == 0
        assert tuple(row) == (0, 0, 0)

    @pytest.mark.parametrize(
        ("fw", "status", "proposals", "seeded"),
        [
            ("garrett", "completed", True, True),   # a finished run: opened once already
            ("garrett", "cancelled", True, True),   # a stopped run that settled
            ("garrett", "running", True, False),    # still coding: it opens after
            ("garrett", "failed", False, False),    # nothing to show
            ("sentiment", "completed", True, False),  # never reviewable
        ],
    )
    @pytest.mark.parametrize("table_made_by_create_all", [False, True])
    def test_an_upgrade_seeds_studies_with_a_finished_run(
        self, tmp_path: Path, fw: str, status: str, proposals: bool, seeded: bool,
        table_made_by_create_all: bool,
    ) -> None:
        from bristlenose.server.db import run_migrations

        app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url=f"sqlite:///{tmp_path / 'u.db'}")
        tags = _import_garrett(app)
        _add_job(app, fw, status, status == "completed", [0.5] if proposals else [], tags)
        engine = sa.create_engine(f"sqlite:///{tmp_path / 'u.db'}")
        with engine.connect() as conn:
            if table_made_by_create_all:
                # init_db runs create_all before the migrations: the table is there, empty.
                conn.execute(sa.text("DELETE FROM tag_overview_states"))
            else:
                conn.execute(sa.text("DROP TABLE tag_overview_states"))
            conn.execute(sa.text("UPDATE alembic_version SET version_num = '028'"))
            conn.commit()
        run_migrations(engine)
        with engine.connect() as conn:
            rows = conn.execute(
                sa.text("SELECT project_id, open, split, auto_opened FROM tag_overview_states")
            ).all()
        assert [tuple(r) for r in rows] == ([(1, 0, 0, 1)] if seeded else [])

    def test_a_fresh_database_upgrades_cleanly(self, tmp_path: Path) -> None:
        from bristlenose.server.db import init_db, run_migrations

        engine = sa.create_engine(f"sqlite:///{tmp_path / 'new.db'}")
        init_db(engine)
        run_migrations(engine)
        with engine.connect() as conn:
            assert "tag_overview_states" in sa.inspect(conn).get_table_names()
