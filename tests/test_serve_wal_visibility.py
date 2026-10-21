"""Curation the serve has committed is visible to a reader that ignores the WAL.

The Mac app counts a study's curation before Re-analyse with a sandboxed
``?immutable=1`` read, which sees only the main database file. The serve runs
in WAL mode on long-lived connections and only the importer checkpointed, so a
star or tag made in this session stayed in ``-wal`` for as long as the serve
ran: the count read zero and Re-analyse skipped its "you'll lose N edits" sheet
and discarded them (reproduced 19 Oct 2026). Every connection now checkpoints
after each commit.

File-backed database on purpose: the in-memory one has no WAL.
"""

from __future__ import annotations

import shutil
import sqlite3
import struct
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import select, text

from bristlenose.server.app import create_app
from bristlenose.server.models import Quote
from tests.conftest import AuthTestClient

_SMOKE = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


def _immutable_count(db_path: Path, sql: str) -> int:
    conn = sqlite3.connect(f"file:{db_path}?immutable=1", uri=True)
    try:
        return int(conn.execute(sql).fetchone()[0])
    finally:
        conn.close()


def test_a_star_and_a_tag_are_visible_while_the_serve_is_still_up(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(_SMOKE, project)
    db_path = tmp_path / "serve.db"
    client = AuthTestClient(create_app(project_dir=project, db_url=f"sqlite:///{db_path}"))

    assert client.put("/api/projects/1/starred", json={"q-p1-10": True}).status_code == 200
    assert client.put("/api/projects/1/tags", json={"q-p1-10": ["pricing"]}).status_code == 200

    # The serve is still running and holds its connections open, as it does
    # while the researcher picks Re-analyse.
    assert _immutable_count(
        db_path, "SELECT COUNT(*) FROM quote_states WHERE is_starred = 1"
    ) == 1
    assert _immutable_count(db_path, "SELECT COUNT(*) FROM quote_tags") == 1


# ---------------------------------------------------------------------------
# Decision #115 (21 Oct 2026): the checkpoint cannot pass a reader's snapshot.
#
# A checkpoint copies WAL frames into the main file only up to the oldest open
# reader's snapshot. A star committed while any statement is in flight on
# another connection stays in ``-wal`` after its own commit's checkpoint, and
# ``wal_autocheckpoint=1`` does not come back for it when the reader finishes:
# nothing checkpoints until the NEXT commit. The researcher's last star before
# Re-analyse has no next commit. So the Mac app cannot trust the main file
# alone; it reads the WAL index header in ``-shm`` and treats
# ``mxFrame != nBackfill`` (committed frames not yet copied) as "couldn't
# count" (``CurationCountsReader.walVouch``).
#
# These tests measure that against the serve's own engine and routes, and pin
# the header fields the Swift side reads at the offsets it reads them.
# ---------------------------------------------------------------------------

_STARS = (
    "SELECT COUNT(*) FROM quote_states s JOIN quotes q ON q.id = s.quote_id "
    "WHERE s.is_starred = 1 AND q.project_id = 1"
)  # CurationCountsReader's starred query, verbatim


def _wal_index(db_path: Path) -> tuple[int, int]:
    """``(mxFrame, nBackfill)`` from ``-shm``, at the offsets the Mac reads.

    sqlite.org/walformat.html: the header's ``mxFrame`` is the u32 at 16,
    ``nBackfill`` the first field of the checkpoint info at 96; native order.
    """
    raw = Path(f"{db_path}-shm").read_bytes()[:100]
    assert struct.unpack_from("=I", raw, 0)[0] == 3007000  # iVersion
    assert raw[0:48] == raw[48:96]  # the two header copies agree
    return struct.unpack_from("=I", raw, 16)[0], struct.unpack_from("=I", raw, 96)[0]


def _served(tmp_path: Path) -> tuple[AuthTestClient, Path, FastAPI]:
    project = tmp_path / "project"
    shutil.copytree(_SMOKE, project)
    db_path = tmp_path / "serve.db"
    app = create_app(project_dir=project, db_url=f"sqlite:///{db_path}")
    return AuthTestClient(app), db_path, app


def test_a_star_under_an_open_reader_stays_in_the_wal_until_the_next_commit(
    tmp_path: Path,
) -> None:
    client, db_path, _app = _served(tmp_path)

    # Idle and fully checkpointed: the main file is current, the index says so,
    # and the WAL file is NOT empty — SQLite reuses it rather than truncating,
    # which is why "a non-empty -wal" cannot be the Mac's signal.
    mx, nb = _wal_index(db_path)
    assert mx == nb
    assert Path(f"{db_path}-wal").stat().st_size > 0

    reader = sqlite3.connect(str(db_path), isolation_level=None)
    reader.execute("BEGIN")
    reader.execute("SELECT COUNT(*) FROM quotes").fetchone()
    try:
        assert client.put("/api/projects/1/starred", json={"q-p1-10": True}).status_code == 200
        assert _immutable_count(db_path, _STARS) == 0  # the Mac would count nothing
        mx, nb = _wal_index(db_path)
        assert mx > nb  # ...and the index says the main file is behind
    finally:
        reader.execute("COMMIT")
        reader.close()

    # The reader is gone, and nothing checkpointed for it.
    assert _immutable_count(db_path, _STARS) == 0
    mx, nb = _wal_index(db_path)
    assert mx > nb

    # The next commit, by anyone, heals it.
    assert client.put("/api/projects/1/tags", json={"q-p1-10": ["pricing"]}).status_code == 200
    assert _immutable_count(db_path, _STARS) == 1
    mx, nb = _wal_index(db_path)
    assert mx == nb


def test_the_serve_holds_no_snapshot_between_requests_but_an_in_flight_statement_is_one(
    tmp_path: Path,
) -> None:
    """Where a reader comes from in practice.

    A serve session left open after ORM reads holds nothing: pysqlite begins no
    transaction for a SELECT and ORM results are fully buffered. A statement
    still stepping does hold one, and that is every concurrent request, the
    elaboration stream and the importer for the moment they read.
    """
    client, db_path, app = _served(tmp_path)

    held = app.state.db_factory()
    try:
        held.execute(select(Quote)).scalars().all()
        held.execute(select(Quote)).first()
        assert client.put("/api/projects/1/starred", json={"q-p1-10": True}).status_code == 200
        assert _immutable_count(db_path, _STARS) == 1
    finally:
        held.close()

    in_flight = app.state.db_factory()
    try:
        rows = in_flight.execute(text("SELECT id FROM quotes"))
        rows.fetchone()  # one row stepped, the statement still open
        assert client.put("/api/projects/1/starred", json={"q-p1-11": True}).status_code == 200
        assert _immutable_count(db_path, _STARS) == 1  # the second star is in -wal only
        mx, nb = _wal_index(db_path)
        assert mx > nb
        rows.close()
    finally:
        in_flight.close()


def test_a_partial_checkpoint_leaves_the_wal_older_than_the_main_file(tmp_path: Path) -> None:
    """Why the Mac does not compare modification times.

    Two overlapping readers: the star's commit checkpoints up to the newer
    reader's snapshot, writing the main file AFTER the star was appended to the
    WAL. The main file is newer, and the star is still only in the WAL.
    """
    client, db_path, _app = _served(tmp_path)

    first = sqlite3.connect(str(db_path), isolation_level=None)
    first.execute("BEGIN")
    first.execute("SELECT 1 FROM quotes").fetchone()
    assert client.put("/api/projects/1/tags", json={"q-p1-11": ["pricing"]}).status_code == 200
    second = sqlite3.connect(str(db_path), isolation_level=None)
    second.execute("BEGIN")
    second.execute("SELECT 1 FROM quotes").fetchone()
    first.execute("COMMIT")
    first.close()
    try:
        assert client.put("/api/projects/1/starred", json={"q-p1-10": True}).status_code == 200
        wal = Path(f"{db_path}-wal").stat().st_mtime_ns
        main = db_path.stat().st_mtime_ns
        assert wal <= main  # by mtime the main file looks current
        assert _immutable_count(db_path, _STARS) == 0  # it is not
        mx, nb = _wal_index(db_path)
        assert mx > nb  # the index is not fooled
    finally:
        second.execute("COMMIT")
        second.close()
