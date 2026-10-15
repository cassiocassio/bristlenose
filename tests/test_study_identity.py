"""A study is what its folder carries: the marker, and one row in its database.

``docs/design-project-identity.md`` §3–4 and §10. The end-to-end proof that a
moved or copied study keeps its curation is in ``test_lifecycle_end_to_end.py``
and the scenario table; these pin the rules underneath.
"""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from pathlib import Path

import pytest

from bristlenose import study_marker
from bristlenose.server.db import create_session_factory, get_engine, init_db
from bristlenose.server.importer import import_project
from bristlenose.server.models import Project, QuoteState
from tests.test_serve_project_root import _project

# ── The marker ──────────────────────────────────────────────────────────────


def test_the_first_toucher_mints_and_every_later_read_agrees(tmp_path: Path) -> None:
    out = tmp_path / "bristlenose-output"
    first = study_marker.read_or_mint(out, minted_by="serve")
    assert first is not None and str(uuid.UUID(first)) == first
    assert study_marker.read_or_mint(out, minted_by="run") == first
    data = json.loads(study_marker.marker_path(out).read_text())
    assert data["minted_by"] == "serve" and data["schema"] == 1


def test_a_marker_this_release_cannot_read_is_never_minted_over(tmp_path: Path) -> None:
    """Minting over it would give the study a second identity."""
    out = tmp_path / "bristlenose-output"
    path = study_marker.marker_path(out)
    path.parent.mkdir(parents=True)
    path.write_text('{"schema": 99, "study_id": "x"}')
    assert study_marker.read_or_mint(out, minted_by="serve") is None
    assert json.loads(path.read_text())["schema"] == 99


def test_a_marker_refuses_an_id_that_is_not_a_uuid(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        study_marker.write(tmp_path, "not-a-uuid", minted_by="run")


# ── One study per database ──────────────────────────────────────────────────


def _own_db(proj: Path):
    db_file = proj / "bristlenose-output" / ".bristlenose" / "bristlenose.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)
    engine = get_engine(f"sqlite:///{db_file}")
    init_db(engine)
    return engine, create_session_factory(engine)


def _rows(factory) -> list[Project]:
    db = factory()
    try:
        return db.query(Project).order_by(Project.id).all()
    finally:
        db.close()


def test_a_study_database_adopts_its_one_row_whatever_its_paths(tmp_path: Path) -> None:
    """A moved folder brings its database, whose row still names the old
    place. The row is the study; its paths are healed, not compared."""
    proj = _project(tmp_path)
    engine, factory = _own_db(proj)
    db = factory()
    db.add(Project(name="Smoke Test", slug="smoke-test", input_dir="/Volumes/Old/proj",
                   output_dir="/Volumes/Old/proj/bristlenose-output"))
    db.commit()
    import_project(db, proj)
    db.commit()
    db.close()

    rows = _rows(factory)
    assert len(rows) == 1, f"the import forked a second row: {[(r.id, r.input_dir) for r in rows]}"
    assert Path(rows[0].input_dir).resolve() == proj.resolve()
    assert rows[0].study_id == study_marker.read(proj / "bristlenose-output")
    engine.dispose()


def test_the_marker_wins_over_the_row(tmp_path: Path) -> None:
    """A copy the app re-minted carries a new id in its marker while its
    database still holds the original's: the database follows the marker."""
    proj = _project(tmp_path)
    engine, factory = _own_db(proj)
    db = factory()
    db.add(Project(name="Smoke Test", slug="smoke-test", input_dir=str(proj),
                   output_dir=str(proj / "bristlenose-output"), study_id=str(uuid.uuid4())))
    db.commit()
    reminted = str(uuid.uuid4())
    study_marker.write(proj / "bristlenose-output", reminted, minted_by="app")
    import_project(db, proj)
    db.commit()
    db.close()
    assert [r.study_id for r in _rows(factory)] == [reminted]
    engine.dispose()


def _fork(proj: Path, factory) -> None:
    """The shape a move used to leave: row 1 from before, row 2 from after."""
    db = factory()
    import_project(db, proj)
    db.commit()
    db.add(Project(name="Smoke Test", slug="smoke-test", input_dir=str(proj / "elsewhere"),
                   output_dir=str(proj / "elsewhere" / "bristlenose-output")))
    db.commit()
    db.close()


def test_a_forked_row_with_no_curation_is_removed(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    engine, factory = _own_db(proj)
    _fork(proj, factory)
    db = factory()
    from bristlenose.server.models import Session as SessionModel

    # Give the fork sessions of its own, as a real forked import would.
    fork_id = max(r.id for r in db.query(Project).all())
    db.add(SessionModel(project_id=fork_id, session_id="s1", session_number=1))
    db.commit()
    import_project(db, proj)
    db.commit()
    assert [r.id for r in db.query(Project).all()] == [1]
    assert db.query(SessionModel).filter_by(project_id=fork_id).count() == 0
    db.close()
    engine.dispose()


def test_a_forked_row_holding_curation_is_left_and_said(tmp_path: Path) -> None:
    """Somebody's work is on it: never deleted by an import, said at ERROR."""
    proj = _project(tmp_path)
    engine, factory = _own_db(proj)
    _fork(proj, factory)
    db = factory()
    fork_id = max(r.id for r in db.query(Project).all())
    from bristlenose.server.models import Quote

    quote = db.query(Quote).first()
    assert quote is not None
    clone = Quote(**{c.name: getattr(quote, c.name) for c in Quote.__table__.columns
                     if c.name != "id"})
    clone.project_id = fork_id
    db.add(clone)
    db.flush()
    db.add(QuoteState(quote_id=clone.id, is_starred=True))
    db.commit()

    seen: list[str] = []

    class _Keep(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            seen.append(record.getMessage())

    keep = _Keep(level=logging.ERROR)
    logging.getLogger("bristlenose.server.importer").addHandler(keep)
    try:
        import_project(db, proj)
        db.commit()
    finally:
        logging.getLogger("bristlenose.server.importer").removeHandler(keep)
    assert sorted(r.id for r in db.query(Project).all()) == [1, fork_id]
    assert any("curation" in m for m in seen), seen
    db.close()
    engine.dispose()


def test_a_database_outside_the_study_folder_still_matches_by_path(tmp_path: Path) -> None:
    """Two studies in one database (a future instance database) stay two."""
    a, b = _project(tmp_path / "a"), _project(tmp_path / "b")
    engine = get_engine(f"sqlite:///{tmp_path / 'instance.db'}")
    init_db(engine)
    factory = create_session_factory(engine)
    db = factory()
    import_project(db, a)
    import_project(db, b)
    db.commit()
    db.close()
    assert len(_rows(factory)) == 2
    engine.dispose()


def test_a_copy_carries_the_same_study_until_the_app_re_mints(tmp_path: Path) -> None:
    """Python cannot know whether the original is still live, so a copy keeps
    the id it was copied with; the app re-mints on arrival (phase 4)."""
    proj = _project(tmp_path)
    engine, factory = _own_db(proj)
    db = factory()
    import_project(db, proj)
    db.commit()
    db.close()
    engine.dispose()
    original = study_marker.read(proj / "bristlenose-output")
    copy = tmp_path / "copy" / proj.name
    shutil.copytree(proj, copy)
    assert study_marker.read(copy / "bristlenose-output") == original
