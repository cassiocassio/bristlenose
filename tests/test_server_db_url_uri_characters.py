"""A study's database is the study's own file, whatever its folder is called.

``db_url_for_project`` used to interpolate the path into ``sqlite:///{path}``.
SQLAlchemy parses that as a URL: it ends the database at the first ``?`` and
percent-decodes the rest, so a study under ``Who? Inc/`` kept its database in a
stray file named ``Who`` beside the folder (and two studies under that folder
shared the one file, the second showing the first's report), and a folder named
``Interview%20recordings`` made the report server unable to open its database.
``curation_counts`` and the Mac's readers already escaped the path; the writer
was the one place that did not (N197, 25 Oct 2026).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

from bristlenose import curation_counts
from bristlenose.server.db import (
    create_session_factory,
    db_url_for_project,
    get_engine,
    init_db,
)
from bristlenose.server.importer import import_project

FIXTURE = Path(__file__).parent / "fixtures" / "smoke-test" / "input"

# Windows forbids "?" in a file name, so that folder cannot exist there.
FOLDERS = ["Round #2", "100%25 done", "Interview%20recordings", "x%3F y", "plain study"] + (
    [] if sys.platform == "win32" else ["Study?v2", "Who? Inc"]
)


def _own_file(study: Path) -> Path:
    return study / "bristlenose-output" / ".bristlenose" / "bristlenose.db"


@pytest.mark.parametrize("folder", FOLDERS)
def test_the_engine_opens_the_studys_own_database(tmp_path: Path, folder: str) -> None:
    study = tmp_path / folder
    study.mkdir()
    before = sorted(p.name for p in tmp_path.iterdir())

    engine = get_engine(db_url_for_project(study))
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS probe (n INTEGER)"))
        conn.execute(text("INSERT INTO probe VALUES (1)"))
    engine.dispose()

    own = _own_file(study)
    assert own.exists(), "the database belongs inside the study's own output folder"
    assert os.path.samefile(engine.url.database, own)
    assert sorted(p.name for p in tmp_path.iterdir()) == before, "a stray file beside the study"


@pytest.mark.parametrize("folder", FOLDERS)
def test_the_readers_agree_with_the_writer_on_the_file(tmp_path: Path, folder: str) -> None:
    """``curation_counts`` (which --clean trusts before it discards anything)
    must be looking at the file the server writes."""
    study = tmp_path / folder
    study.mkdir()
    engine = get_engine(db_url_for_project(study))
    init_db(engine)
    engine.dispose()

    out = study / "bristlenose-output"
    assert os.path.samefile(engine.url.database, curation_counts.db_path(out))
    counts = curation_counts.read(out)
    assert counts is not None and counts.total == 0


# The folder that holds two studies. A "?" is the case that made them share one
# file, and that sharing can only happen where a "?" can be a name: it is POSIX-only
# by nature. On Windows the "%3F" spelling stands in, which proves only that two
# studies under an encoded parent keep their own files (the decode half; the sharing
# half is not reproducible there). Chosen over a skipif to keep the skip ratchet.
SHARED_PARENTS = ["Who%3F Inc" if sys.platform == "win32" else "Who? Inc"]


@pytest.mark.parametrize("parent", SHARED_PARENTS)
def test_two_studies_under_one_folder_do_not_share_a_database(
    tmp_path: Path, parent: str
) -> None:
    """Under a ``?`` the second study's report read the first study's rows."""
    studies = []
    for name in ("Study A", "Study B"):
        proj = tmp_path / parent / name
        shutil.copytree(
            FIXTURE, proj,
            ignore=shutil.ignore_patterns("bristlenose.db*", "bristlenose.log*"),
        )
        studies.append(proj)

    engines = []
    for proj in studies:
        engine = get_engine(db_url_for_project(proj))
        init_db(engine)
        db = create_session_factory(engine)()
        import_project(db, proj)
        db.commit()
        db.close()
        engines.append(engine)

    files = {os.path.realpath(e.url.database) for e in engines}
    assert len(files) == 2, "the two studies share one database file"
    for engine, proj in zip(engines, studies, strict=True):
        assert os.path.samefile(engine.url.database, _own_file(proj))
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM projects")).scalar() == 1
        engine.dispose()
    assert sorted(p.name for p in (tmp_path / parent).iterdir()) == ["Study A", "Study B"]
    assert [p.name for p in tmp_path.iterdir()] == [parent]


def test_the_default_database_path_is_escaped_too(tmp_path: Path, monkeypatch) -> None:
    from bristlenose.server import db as server_db

    monkeypatch.setattr(server_db, "_CONFIG_DIR", tmp_path / "Who? Inc" / "cfg%20dir")
    engine = get_engine(server_db._default_db_url())
    init_db(engine)
    engine.dispose()
    here = tmp_path / "Who? Inc" / "cfg%20dir" / "bristlenose.db"
    assert os.path.samefile(engine.url.database, here)


def test_the_dev_info_names_the_database_as_it_is_on_disk(tmp_path: Path) -> None:
    """The About tab's developer section printed the escaped URL tail."""
    from bristlenose.server.app import create_app
    from bristlenose.server.db import sqlite_url
    from tests.conftest import AuthTestClient

    db = tmp_path / "Who? Inc" / "bristlenose.db"
    db.parent.mkdir()
    app = create_app(project_dir=FIXTURE, dev=True, db_url=sqlite_url(db))
    info = AuthTestClient(app).get("/api/dev/info").json()
    assert info["db_path"] == str(db)
