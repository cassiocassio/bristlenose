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
from pathlib import Path

from bristlenose.server.app import create_app
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
