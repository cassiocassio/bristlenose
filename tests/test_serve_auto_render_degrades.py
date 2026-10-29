"""Incomplete analysis output remains safe for the live report (R112)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bristlenose import cli

_FIXTURE = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    dst = tmp_path / "input"
    shutil.copytree(_FIXTURE, dst)
    return dst


def _intermediate(project: Path) -> Path:
    return project / "bristlenose-output" / ".bristlenose" / "intermediate"


def test_serve_starts_during_a_first_analysis_with_partial_intermediate(
    project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Server startup does not read final analysis files a first run has not made yet."""
    for name in ("screen_clusters.json", "theme_groups.json"):
        _intermediate(project).joinpath(name).unlink()

    started: list[tuple[Path, dict[str, object]]] = []
    rendered: list[object] = []

    def _unexpected_render(*args: object, **kwargs: object) -> object:
        rendered.append((args, kwargs))
        return object()

    monkeypatch.setattr(cli, "_run_preflight", lambda *_args: None)
    monkeypatch.setattr(cli, "_print_mcp_connect", lambda _port: None)
    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run_render_only", _unexpected_render)
    monkeypatch.setattr(
        cli, "_start_server", lambda path, **kwargs: started.append((path, kwargs)),
    )

    result = CliRunner().invoke(
        cli.app, ["serve", str(project), "--no-open", "--port", "8199"],
    )

    assert result.exit_code == 0, result.output
    assert started == [(project, {"port": 8199, "open_browser": False, "verbose": False})]
    assert rendered == []


# ---------------------------------------------------------------------------
# The importer: the same files must not empty the report either
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    from bristlenose.server.db import create_session_factory, get_engine, init_db

    engine = get_engine("sqlite://")
    init_db(engine)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.mark.parametrize(
    "name", ["metadata.json", "screen_clusters.json", "theme_groups.json"],
)
def test_a_truncated_file_still_imports_the_sessions(db, project: Path, name: str) -> None:
    """A fresh database (first serve, or the Mac app's after a reset) got no
    project at all: the whole import raised, and the report opened empty."""
    from bristlenose.server.importer import import_project
    from bristlenose.server.models import Session as SessionModel

    (_intermediate(project) / name).write_text('[{"screen_label": "Dash', encoding="utf-8")
    project_row = import_project(db, project)
    assert db.query(SessionModel).filter_by(project_id=project_row.id).count() == 1


@pytest.mark.parametrize("name", ["screen_clusters.json", "theme_groups.json"])
def test_a_truncated_quote_file_keeps_the_quotes_already_imported(
    db, project: Path, name: str,
) -> None:
    """Read as missing, not as empty: an empty answer would sweep every quote,
    and its stars and tags, as removed by the re-run."""
    from bristlenose.server.importer import import_project
    from bristlenose.server.models import Quote

    project_row = import_project(db, project)
    before = db.query(Quote).filter_by(project_id=project_row.id).count()
    assert before > 0
    (_intermediate(project) / name).write_text('[{"screen_label": "Dash', encoding="utf-8")
    import_project(db, project)
    assert db.query(Quote).filter_by(project_id=project_row.id).count() == before


def test_a_truncated_topic_map_still_imports(db, project: Path) -> None:
    from bristlenose.server.importer import import_project
    from bristlenose.server.models import Session as SessionModel

    (_intermediate(project) / "topic_boundaries.json").write_text('[{"sess', encoding="utf-8")
    project_row = import_project(db, project)
    assert db.query(SessionModel).filter_by(project_id=project_row.id).count() == 1


@pytest.mark.parametrize("name", ["screen_clusters.json", "theme_groups.json"])
def test_half_the_quotes_are_never_shown_as_the_whole(db, project: Path, name: str) -> None:
    """With one quote file unreadable, a first import shows no quotes rather than
    the other file's share of them, which would look like the complete report."""
    from bristlenose.server.importer import import_project
    from bristlenose.server.models import Quote

    (_intermediate(project) / name).write_text('[{"screen_label": "Dash', encoding="utf-8")
    project_row = import_project(db, project)
    assert db.query(Quote).filter_by(project_id=project_row.id).count() == 0
