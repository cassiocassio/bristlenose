"""One damaged file must not stop the report opening (R112).

`serve` re-renders the sealed static report before it starts (`_auto_render`).
That render reads `people.yaml` and the intermediate JSON, and until 20 Oct
2026 a typo in the one or a truncated copy of the other raised out of `serve`
before the server bound: the Mac app said "exited before ready". The SPA reads
the database, which the importer fills tolerantly, so the static render is
skipped with a warning and the server starts.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pytest

from bristlenose.cli import _auto_render

_FIXTURE = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    dst = tmp_path / "input"
    shutil.copytree(_FIXTURE, dst)
    return dst


def _intermediate(project: Path) -> Path:
    return project / "bristlenose-output" / ".bristlenose" / "intermediate"


class _Warnings(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _render_capturing(project: Path) -> list[logging.LogRecord]:
    # The render reconfigures logging, so caplog cannot see it; listen on the
    # package logger directly.
    handler = _Warnings()
    log = logging.getLogger("bristlenose")
    log.addHandler(handler)
    try:
        _auto_render(project)
    finally:
        log.removeHandler(handler)
    return handler.records


def test_a_people_yaml_typo_is_skipped_not_fatal(project: Path) -> None:
    (project / "bristlenose-output" / "people.yaml").write_text(
        'participants:\n  p1:\n    editable: {full_name: "Ann\n', encoding="utf-8",
    )
    records = _render_capturing(project)
    assert any("static report" in r.getMessage() for r in records)


@pytest.mark.parametrize("name", ["screen_clusters.json", "extracted_quotes.json"])
def test_a_truncated_intermediate_file_is_skipped_not_fatal(project: Path, name: str) -> None:
    path = _intermediate(project) / name
    path.write_text('[{"screen_label": "Dash', encoding="utf-8")
    records = _render_capturing(project)
    assert any("static report" in r.getMessage() for r in records)


def test_an_intact_project_still_renders(project: Path) -> None:
    records = _render_capturing(project)
    assert not any("static report" in r.getMessage() for r in records)


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
