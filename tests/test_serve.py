"""Tests for the bristlenose serve command and FastAPI server."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bristlenose import __version__
from bristlenose.server.app import create_app
from bristlenose.server.db import Base, get_engine, init_db


@pytest.fixture()
def client() -> TestClient:
    """Create a test client with an in-memory SQLite database."""
    app = create_app(dev=True, db_url="sqlite://")
    return TestClient(app)


@pytest.fixture()
def engine():
    """Create an in-memory SQLAlchemy engine for database tests."""
    return get_engine("sqlite://")


class TestHealthEndpoint:
    def test_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_returns_version(self, client: TestClient) -> None:
        data = client.get("/api/health").json()
        assert data["version"] == __version__

    def test_returns_status(self, client: TestClient) -> None:
        data = client.get("/api/health").json()
        assert data["status"] == "ok"


class TestDatabase:
    def test_init_db_creates_tables(self, engine) -> None:  # type: ignore[no-untyped-def]
        init_db(engine)
        table_names = Base.metadata.tables.keys()
        assert "projects" in table_names

    def test_init_db_is_idempotent(self, engine) -> None:  # type: ignore[no-untyped-def]
        init_db(engine)
        init_db(engine)  # should not raise


class TestAppFactory:
    def test_create_app_returns_fastapi(self) -> None:
        from fastapi import FastAPI

        app = create_app(dev=True, db_url="sqlite://")
        assert isinstance(app, FastAPI)

    def test_create_app_without_project_dir(self) -> None:
        """App should work without a project directory (no report to serve)."""
        app = create_app(dev=True, db_url="sqlite://")
        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.status_code == 200


class TestServeCommand:
    def test_serve_in_commands_set(self) -> None:
        from bristlenose.cli import _COMMANDS

        assert "serve" in _COMMANDS

    def test_serve_help_works(self) -> None:
        """The serve --help should run without errors."""
        from typer.testing import CliRunner

        from bristlenose.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "serve" in result.output.lower()
