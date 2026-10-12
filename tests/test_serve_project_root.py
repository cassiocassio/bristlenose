"""One project row and one database, wherever and whenever the serve started.

A serve started before ``bristlenose-output/`` exists used to root its database
at ``<project>/.bristlenose/`` and create project row 1 with
``output_dir == input_dir``; the run's import then matched no row and created
row 2, and the SPA — hardcoded to project 1 — showed an empty report with every
signal green (measured 12 Oct 2026; ``bristlenose/server/CLAUDE.md``). A first
analysis in the Mac app takes exactly this path, because the app starts the
serve on the next SwiftUI pass after it spawns the run.

None of these tests passes ``db_url``: the bug lives in where the serve puts its
database when nobody tells it, and every one of the 161 ``create_app`` calls in
the suite before these passed one, which is why the class was green throughout.
"""

from __future__ import annotations

import functools
import shutil
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from bristlenose.server import event_watcher
from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient

FIXTURE = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_VITE_INDEX_HTML = (
    '<!doctype html><html><head></head><body>'
    '<div id="bn-app-root"></div></body></html>'
)


@pytest.fixture()
def fast_watcher(monkeypatch: pytest.MonkeyPatch):
    fast = functools.partial(event_watcher.run_event_watcher, poll_interval=0.05)
    monkeypatch.setattr(event_watcher, "run_event_watcher", fast)


def _project(tmp_path: Path) -> Path:
    """A copy of the smoke fixture, minus its local (gitignored) database and log,
    which record the maintainer's checkout path and would fork on their own."""
    proj = tmp_path / "proj"
    shutil.copytree(
        FIXTURE, proj,
        ignore=shutil.ignore_patterns("bristlenose.db*", "bristlenose.log*"),
    )
    return proj


def _app(project_dir: Path, tmp_path: Path):
    static = tmp_path / "static"
    static.mkdir(exist_ok=True)
    (static / "index.html").write_text(_VITE_INDEX_HTML, encoding="utf-8")
    (static / "assets").mkdir(exist_ok=True)
    with patch("bristlenose.server.app._STATIC_DIR", static):
        return create_app(project_dir=project_dir, dev=False)  # no db_url, deliberately


def _rows(db: Path) -> list[tuple[int, str, str]]:
    con = sqlite3.connect(db)
    try:
        return con.execute("SELECT id, input_dir, output_dir FROM projects ORDER BY id").fetchall()
    finally:
        con.close()


def _wait(pred, timeout: float = 5.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.05)
    return False


def _run_writes_its_output(held: Path, out: Path) -> None:
    """What a run does to an output folder the serve already holds: the files
    arrive, and the events log (with its terminus) is the last thing written."""
    events = Path(".bristlenose") / "pipeline-events.jsonl"
    shutil.copytree(held, out, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("pipeline-events.jsonl"))
    shutil.copy2(held / events, out / events)


def test_serve_started_before_the_first_run(tmp_path: Path, fast_watcher) -> None:
    proj = _project(tmp_path)
    out = proj / "bristlenose-output"
    held = tmp_path / "held-output"
    shutil.move(str(out), str(held))  # the project has never been analysed

    app = _app(proj, tmp_path)
    with AuthTestClient(app) as client:
        db = out / ".bristlenose" / "bristlenose.db"
        assert db.exists(), "the database belongs under the output folder, created eagerly"
        assert not (proj / ".bristlenose").exists(), "litter at the project root"

        _run_writes_its_output(held, out)
        assert _wait(lambda: client.get("/api/projects/1/sessions").json().get("sessions")), (
            "the report the SPA reads (project 1) stayed empty after the run"
        )

    rows = _rows(db)
    assert len(rows) == 1, f"the import forked a second project row: {rows}"
    assert Path(rows[0][2]).resolve() == out.resolve()


def test_serve_while_the_output_is_stashed_then_restored(tmp_path: Path, fast_watcher) -> None:
    """``run --clean`` moves the report aside; the Mac app (re)starts the serve in
    that window on every Re-analyse; the run fails and ``restore`` puts the old
    report back. The serve must end up reading it — one row, under the output
    folder — not a second row beside an empty first."""
    from bristlenose.utils import output_backup

    proj = _project(tmp_path)
    out = proj / "bristlenose-output"
    backup = output_backup.stash(out)
    assert backup is not None and not out.exists()

    app = _app(proj, tmp_path)
    with AuthTestClient(app) as client:
        db = out / ".bristlenose" / "bristlenose.db"
        assert db.exists(), "the database belongs under the output folder, created eagerly"
        assert not (proj / ".bristlenose").exists(), "litter at the project root"

        # The run dies; its handler puts the previous report back (the serve's
        # own eagerly-created tree is set aside as the failed run's).
        assert output_backup.restore(backup, out).report_is_back
        assert _wait(lambda: client.get("/api/projects/1/sessions").json().get("sessions")), (
            "the report the SPA reads (project 1) stayed empty after the restore"
        )

    rows = _rows(db)
    assert len(rows) == 1, f"the restore's import forked a second project row: {rows}"
    assert Path(rows[0][2]).resolve() == out.resolve()
    assert not (proj / ".bristlenose").exists()


def test_serve_on_the_output_folder_then_the_project(tmp_path: Path) -> None:
    """``serve <p>/bristlenose-output`` and ``serve <p>`` are the same project."""
    proj = _project(tmp_path)
    out = proj / "bristlenose-output"

    with AuthTestClient(_app(out, tmp_path)):
        pass
    with AuthTestClient(_app(proj, tmp_path)) as client:
        assert client.get("/api/projects/1/sessions").json().get("sessions")

    rows = _rows(out / ".bristlenose" / "bristlenose.db")
    assert len(rows) == 1, f"two entry points forked two rows: {rows}"
    assert Path(rows[0][1]).resolve() == proj.resolve()


def test_media_is_rooted_at_the_interview_folder_from_either_entry(tmp_path: Path) -> None:
    """``/media/`` serves recordings from the interview folder; a serve handed
    the output folder used to root it there, and every recording 404'd."""
    proj = _project(tmp_path)
    (proj / "clip.mp4").write_bytes(b"\x00")
    with AuthTestClient(_app(proj / "bristlenose-output", tmp_path)) as client:
        assert client.get("/media/clip.mp4").status_code == 200
    with AuthTestClient(_app(proj, tmp_path)) as client:
        assert client.get("/media/clip.mp4").status_code == 200


def test_a_legacy_row_from_the_output_folder_entry_is_this_project(tmp_path: Path) -> None:
    """Before 12 Oct 2026 ``serve <p>/bristlenose-output`` stored the output folder
    as the row's input folder too. Keying rows on the interview folder must not
    fork such a row on upgrade: it is matched, and its input folder healed."""
    from bristlenose.server.db import create_session_factory, get_engine, init_db
    from bristlenose.server.importer import import_project
    from bristlenose.server.models import Project

    proj = _project(tmp_path)
    out = proj / "bristlenose-output"
    engine = get_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    init_db(engine)
    db = create_session_factory(engine)()
    db.add(Project(name="Smoke Test", slug="smoke-test",
                   input_dir=str(out.resolve()), output_dir=str(out.resolve())))
    db.commit()

    project = import_project(db, proj)
    assert db.query(Project).count() == 1, "the legacy row forked on upgrade"
    assert Path(project.input_dir).resolve() == proj.resolve()
    db.close()


def test_import_before_and_after_the_first_run_is_one_row(tmp_path: Path) -> None:
    from bristlenose.server.db import create_session_factory, get_engine, init_db
    from bristlenose.server.importer import import_project
    from bristlenose.server.models import Project

    proj = _project(tmp_path)
    out = proj / "bristlenose-output"
    held = tmp_path / "held-output"
    shutil.move(str(out), str(held))

    engine = get_engine(f"sqlite:///{tmp_path / 'one.db'}")
    init_db(engine)
    factory = create_session_factory(engine)

    db = factory()
    first = import_project(db, proj)
    assert Path(first.output_dir).resolve() == out.resolve(), (
        "a never-run project's row must carry the FUTURE output folder"
    )
    db.close()

    shutil.move(str(held), str(out))
    db = factory()
    second = import_project(db, proj)
    assert second.id == first.id
    assert db.query(Project).count() == 1
    db.close()
