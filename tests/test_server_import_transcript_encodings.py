"""The report server reads a transcript the way ``analyze`` does.

``analyze`` reads transcripts through ``decode_text_any_encoding`` (R118): a
Windows-1252 or UTF-16 file is read as itself. The report server's import read
the same files as strict UTF-8 at four places, so the analysis ran, the import
raised, and the report opened empty with only a log line to say why (N199,
25 Oct 2026).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy import select

from bristlenose.server import importer
from bristlenose.server.db import create_session_factory, get_engine, init_db
from bristlenose.server.importer import import_project
from bristlenose.server.models import SessionSpeaker, TranscriptSegment

FIXTURE = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
ACCENTED = "J'ai trouvé ça très difficile."


def _study(tmp_path: Path, encoding: str) -> Path:
    """The smoke fixture with its first transcript re-saved in *encoding*, and
    one line replaced by an accented one (so the bytes are not also UTF-8)."""
    proj = tmp_path / "proj"
    shutil.copytree(
        FIXTURE, proj,
        ignore=shutil.ignore_patterns("bristlenose.db*", "bristlenose.log*"),
    )
    txt = proj / "bristlenose-output" / "transcripts-raw" / "s1.txt"
    lines = txt.read_text(encoding="utf-8").splitlines()
    lines[-1] = f"[01:00] [p1] {ACCENTED}"
    # "utf-16" writes a byte-order mark; the file is what a Windows editor saves.
    txt.write_bytes("\n".join(lines).encode(encoding) + "\n".encode(encoding))
    return proj


@pytest.mark.parametrize("encoding", ["cp1252", "utf-16"])
def test_a_non_utf8_transcript_is_imported_and_read_as_itself(
    tmp_path: Path, encoding: str,
) -> None:
    proj = _study(tmp_path, encoding)
    engine = get_engine("sqlite://")
    init_db(engine)
    db = create_session_factory(engine)()

    import_project(db, proj)  # raised UnicodeDecodeError

    texts = db.scalars(select(TranscriptSegment.text)).all()
    assert any(ACCENTED in t for t in texts), texts
    assert db.scalars(select(SessionSpeaker.speaker_code)).all()
    db.close()


@pytest.mark.parametrize("encoding", ["cp1252", "utf-16"])
def test_the_speaker_turn_starts_read_the_same_file(tmp_path: Path, encoding: str) -> None:
    proj = _study(tmp_path, encoding)
    engine = get_engine("sqlite://")
    init_db(engine)
    db = create_session_factory(engine)()
    import_project(db, proj)
    project = db.scalars(select(importer.Project)).one()

    assert 60.0 in importer.turn_starts(project, "s1", "p1")
    db.close()
