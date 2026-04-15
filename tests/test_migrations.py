"""Tests for Alembic migration infrastructure.

Covers: fresh DB creation, pre-Alembic upgrade + data preservation,
idempotent init_db, and script location resolution.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from bristlenose.server.db import Base, create_session_factory, get_engine, init_db, run_migrations
from bristlenose.server.models import Person, Project


@pytest.fixture()
def engine():
    """In-memory SQLite engine with full init_db."""
    eng = get_engine("sqlite://")
    init_db(eng)
    return eng


# ---------------------------------------------------------------------------
# Fresh database
# ---------------------------------------------------------------------------


class TestFreshDatabase:
    """Brand-new DB gets all tables + alembic_version stamped at head."""

    def test_alembic_version_exists(self, engine):
        insp = inspect(engine)
        assert "alembic_version" in insp.get_table_names()

    def test_stamped_at_head(self, engine):
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        assert row is not None
        # Head is currently 001 (baseline). Update when new migrations land.
        assert row[0] == "001"

    def test_all_user_tables_exist(self, engine):
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        assert "persons" in tables
        assert "quotes" in tables
        assert "projects" in tables

    def test_idempotent(self, engine):
        """Calling init_db twice must not error."""
        init_db(engine)
        insp = inspect(engine)
        assert "alembic_version" in insp.get_table_names()


# ---------------------------------------------------------------------------
# Pre-Alembic upgrade
# ---------------------------------------------------------------------------


class TestPreAlembicUpgrade:
    """Existing DB without alembic_version gets detected and stamped."""

    @pytest.fixture()
    def pre_alembic_engine(self):
        """Create tables via create_all only (no run_migrations)."""
        eng = get_engine("sqlite://")
        from bristlenose.server import models  # noqa: F401

        Base.metadata.create_all(bind=eng)
        return eng

    def test_detected_and_stamped(self, pre_alembic_engine):
        insp = inspect(pre_alembic_engine)
        assert "alembic_version" not in insp.get_table_names()

        run_migrations(pre_alembic_engine)

        insp = inspect(pre_alembic_engine)
        assert "alembic_version" in insp.get_table_names()
        with pre_alembic_engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        assert row is not None
        assert row[0] == "001"

    def test_data_preserved(self, pre_alembic_engine):
        """Existing rows survive the migration stamp."""
        factory = create_session_factory(pre_alembic_engine)
        db: Session = factory()
        try:
            project = Project(id=1, name="Test", slug="test", input_dir="/tmp", output_dir="/tmp")
            db.add(project)
            person = Person(full_name="Alice", short_name="Alice")
            db.add(person)
            db.commit()
            person_id = person.id
        finally:
            db.close()

        run_migrations(pre_alembic_engine)

        db = factory()
        try:
            assert db.query(Project).count() == 1
            assert db.query(Person).filter_by(id=person_id).one().full_name == "Alice"
        finally:
            db.close()

    def test_upgrade_then_init_db_idempotent(self, pre_alembic_engine):
        """After stamping, a full init_db should be a no-op."""
        run_migrations(pre_alembic_engine)
        init_db(pre_alembic_engine)
        with pre_alembic_engine.connect() as conn:
            rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Script location
# ---------------------------------------------------------------------------


class TestScriptLocation:
    """Verify the alembic package resolves correctly."""

    def test_env_py_exists(self):
        from pathlib import Path

        alembic_dir = Path(__file__).parent.parent / "bristlenose" / "server" / "alembic"
        assert (alembic_dir / "env.py").is_file()

    def test_versions_dir_exists(self):
        from pathlib import Path

        versions_dir = (
            Path(__file__).parent.parent / "bristlenose" / "server" / "alembic" / "versions"
        )
        assert versions_dir.is_dir()
        assert (versions_dir / "001_baseline.py").is_file()
