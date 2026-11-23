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


class TestExport:
    def test_the_overview_is_server_only(self) -> None:
        from bristlenose.server.routes.export import (
            EMBED_PATH_TEMPLATES,
            SERVER_ONLY_PATH_TEMPLATES,
        )

        path = "/projects/{project_id}/tag-overview"
        assert path in SERVER_ONLY_PATH_TEMPLATES
        assert path not in EMBED_PATH_TEMPLATES


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

    def test_a_fresh_database_upgrades_cleanly(self, tmp_path: Path) -> None:
        from bristlenose.server.db import init_db, run_migrations

        engine = sa.create_engine(f"sqlite:///{tmp_path / 'new.db'}")
        init_db(engine)
        run_migrations(engine)
        with engine.connect() as conn:
            assert "tag_overview_states" in sa.inspect(conn).get_table_names()
