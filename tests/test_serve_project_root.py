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
import os
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


def _client(app) -> AuthTestClient:
    """A client that polls through the reattach: a request landing while
    ``init_db`` is recreating a replaced database's schema gets a 500 (no such
    table yet, or the write lock), which is "not yet", not a verdict."""
    return AuthTestClient(app, raise_server_exceptions=False)


def _sessions(client) -> list:
    resp = client.get("/api/projects/1/sessions")
    if resp.status_code != 200:
        return []
    return resp.json().get("sessions") or []


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


def test_the_database_path_names_the_future_output_folder(tmp_path: Path) -> None:
    """``db_url_for_project`` on its own, before anything else has made the folder.

    Inside ``create_app`` the log setup runs first and creates
    ``bristlenose-output/.bristlenose/``, so the old two-line rule there would
    have found the folder and been right by accident — mutating ``db.py`` back
    left every serve-level test green (measured 12 Oct 2026). This pins the
    function, so the fix does not depend on the order of two calls in another
    file."""
    from bristlenose.server.db import db_url_for_project

    proj = _project(tmp_path)
    shutil.rmtree(proj / "bristlenose-output")  # never analysed

    url = db_url_for_project(proj)
    assert Path(url.removeprefix("sqlite:///")) == (
        proj / "bristlenose-output" / ".bristlenose" / "bristlenose.db"
    )
    assert not (proj / ".bristlenose").exists(), "litter at the project root"


def test_a_forked_import_is_logged_and_published_under_its_own_row(
    tmp_path: Path, fast_watcher,
) -> None:
    """When an import lands in a row other than 1, say so, and do not tell the
    SPA (which reads row 1) that row 1 holds the run.

    Every path that forks today is fixed, so this test makes the fork by hand:
    the database already holds an unrelated row 1, and the project becomes row 2.
    Before 12 Oct 2026 the handler published ``last_run[1]`` whatever row was
    written, which is why the incident read as healthy.

    Since 15 Oct 2026 a study's OWN database cannot fork — it holds one study,
    found by its marker (``test_a_study_database_adopts_its_one_row``) — so the
    fork is made in a database outside the study folder, the shape a future
    instance database would have, where projects are still matched by path."""
    import logging

    from bristlenose.events import KindEnum, RunCompletedEvent, append_event, events_path
    from bristlenose.server.db import create_session_factory, get_engine, init_db
    from bristlenose.server.models import Project

    proj = _project(tmp_path)
    out = proj / "bristlenose-output"
    db_file = tmp_path / "instance" / "bristlenose.db"
    db_file.parent.mkdir()
    engine = get_engine(f"sqlite:///{db_file}")
    init_db(engine)
    seed = create_session_factory(engine)()
    elsewhere = tmp_path / "another-study"
    seed.add(Project(name="Another study", slug="another-study",
                     input_dir=str(elsewhere), output_dir=str(elsewhere / "bristlenose-output")))
    seed.commit()
    seed.close()
    engine.dispose()

    run_id = "01FORKTEST0000000000000001"
    # Not caplog: ``create_app`` calls ``setup_logging``, which reconfigures the
    # root logger and drops caplog's handler. A handler on the module's own
    # logger survives that.
    seen: list[str] = []

    class _Keep(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            seen.append(record.getMessage())

    keep = _Keep(level=logging.ERROR)
    app_logger = logging.getLogger("bristlenose.server.app")
    app_logger.addHandler(keep)
    try:
        static = tmp_path / "static"
        static.mkdir(exist_ok=True)
        (static / "index.html").write_text(_VITE_INDEX_HTML, encoding="utf-8")
        with patch("bristlenose.server.app._STATIC_DIR", static):
            app = create_app(project_dir=proj, dev=False, db_url=f"sqlite:///{db_file}")
        with AuthTestClient(app):
            append_event(events_path(out), RunCompletedEvent(
                ts="2026-10-12T23:00:00Z", run_id=run_id, kind=KindEnum.RUN,
                started_at="2026-10-12T22:59:00Z", ended_at="2026-10-12T23:00:00Z"))
            assert _wait(lambda: (app.state.last_run.get(2) or {}).get("run_id") == run_id), (
                f"the run was not published under the row it was imported into: "
                f"{app.state.last_run}"
            )
            assert (app.state.last_run.get(1) or {}).get("run_id") != run_id, (
                "row 1 was told it holds a run that went into row 2"
            )
    finally:
        app_logger.removeHandler(keep)

    assert any("forked" in m and run_id in m for m in seen), "a forked import was not logged"


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


def _open_paths_under(folder: Path) -> list[str]:
    """Files this process holds open under ``folder`` (macOS and Linux). On
    Windows the move in the test below is the check: it refuses a held file."""
    import fcntl
    import sys

    base = str(folder.resolve())
    found: list[str] = []
    fds = os.listdir("/proc/self/fd") if sys.platform.startswith("linux") else os.listdir("/dev/fd")
    for name in fds:
        fd = int(name)
        try:
            if sys.platform == "darwin":
                raw = fcntl.fcntl(fd, fcntl.F_GETPATH, b"\0" * 1024)  # type: ignore[attr-defined]
                path = raw.split(b"\0", 1)[0].decode()
            else:
                path = os.readlink(f"/proc/self/fd/{fd}")
        except OSError:
            continue
        if path.startswith(base):
            found.append(path)
    return found


def test_a_stopped_server_holds_nothing_open_in_the_study(tmp_path: Path) -> None:
    """A project closed in the app can be moved: the server lets go of its
    database and its log when it stops. Windows refuses to move a folder holding
    an open file, which is how CI found it (16 Oct 2026)."""
    proj = _project(tmp_path)
    with AuthTestClient(_app(proj, tmp_path)) as client:
        assert client.get("/api/projects/1/sessions").json().get("sessions")
    if os.name != "nt":
        assert _open_paths_under(proj) == [], "the stopped server still holds files open"
    moved = tmp_path / "moved" / proj.name
    moved.parent.mkdir()
    shutil.move(str(proj), str(moved))
    with AuthTestClient(_app(moved, tmp_path)) as client:
        assert client.get("/api/projects/1/sessions").json().get("sessions")
