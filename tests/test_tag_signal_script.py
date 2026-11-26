"""scripts/tag-signal.py: counts shipped-tag AutoCode decisions, touches nothing.

Design: docs/design-tag-telemetry-debug.md.
"""

from __future__ import annotations

import importlib.util
import shutil
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from bristlenose.server.models import (
    AutoCodeJob,
    Base,
    CodebookGroup,
    ProposedTag,
    TagDefinition,
)

_PATH = Path(__file__).resolve().parent.parent / "scripts" / "tag-signal.py"
_spec = importlib.util.spec_from_file_location("bn_tag_signal", _PATH)
assert _spec is not None and _spec.loader is not None
tag_signal = importlib.util.module_from_spec(_spec)
sys.modules["bn_tag_signal"] = tag_signal
_spec.loader.exec_module(tag_signal)


def _make_study(
    root: Path,
    rows: list[tuple[str | None, str, str, str | None]],
    *,
    revision: str | None = "029",
) -> Path:
    """Build a study folder whose database holds one proposal per row.

    Each row is (framework_id or None, tag name, status, decided_by). The app's
    engine hook (``bristlenose/server/db.py``) puts every connection in WAL
    mode, as the app's own databases are. ``revision=None`` leaves out the
    ``alembic_version`` table.
    """
    db_dir = root / ".bristlenose"
    db_dir.mkdir(parents=True)
    engine = create_engine(f"sqlite:///{db_dir / 'bristlenose.db'}")

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record):  # noqa: ANN001
        # Only the four tables the script reads are filled; the project and
        # quote rows they point at don't matter to it.
        dbapi_conn.execute("PRAGMA foreign_keys=OFF")

    Base.metadata.create_all(engine)
    with Session(engine) as s:
        job = AutoCodeJob(
            project_id=1,
            framework_id="garrett",
            status="completed",
            prompt_version="0.1.1",
            llm_provider="anthropic",
            llm_model="claude-test",
        )
        s.add(job)
        s.flush()
        groups: dict[str | None, CodebookGroup] = {}
        for i, (framework_id, name, status, decided_by) in enumerate(rows):
            if framework_id not in groups:
                groups[framework_id] = CodebookGroup(
                    name=f"group {framework_id}", framework_id=framework_id
                )
                s.add(groups[framework_id])
                s.flush()
            tag = TagDefinition(codebook_group_id=groups[framework_id].id, name=name)
            s.add(tag)
            s.flush()
            s.add(
                ProposedTag(
                    job_id=job.id,
                    quote_id=i + 1,
                    tag_definition_id=tag.id,
                    status=status,
                    decided_by=decided_by,
                )
            )
        s.commit()
    if revision is not None:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
            )
            conn.exec_driver_sql(f"INSERT INTO alembic_version VALUES ('{revision}')")
    engine.dispose()
    return root


def _leave_empty_wal(db: Path, *, shm: bool) -> None:
    """Leave the closed *db* with a zero-length ``-wal``, and a ``-shm`` if *shm*.

    That is what a plain ``mode=ro`` visit leaves with Homebrew's SQLite 3.53.3
    on the Mac (measured 26 Nov 2026), but Debian's 3.46.1 and Fedora's 3.47.2
    create no file for that visit, so the state is built here rather than by a
    visit: a writer's TRUNCATE checkpoint empties its WAL beside a real
    ``-shm``, whose bytes are kept. Closing the writer deletes both files with
    most builds (Apple's SQLite keeps them), so afterwards the empty ``-wal``
    is always written back, and the ``-shm`` is written back or removed.
    """
    wal, shm_path = db.with_name(db.name + "-wal"), db.with_name(db.name + "-shm")
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
        assert wal.stat().st_size == 0
        shm_bytes = shm_path.read_bytes()
    finally:
        conn.close()
    wal.write_bytes(b"")
    if shm:
        shm_path.write_bytes(shm_bytes)
    else:
        shm_path.unlink(missing_ok=True)
    assert wal.stat().st_size == 0
    assert shm_path.exists() is shm


def _snapshot(folder: Path, *, shm_content: bool = True) -> dict[str, tuple]:
    """Listing, size, mtime and bytes of every file under *folder*.

    ``shm_content=False`` compares the ``-shm`` file by presence and size only:
    it is SQLite's shared-memory index, and every reader of an OPEN database
    (the app's own included) writes its read marks there, which also moves its
    mtime when the reading process exits. The script documents that exception.
    """
    def entry(p: Path) -> tuple:
        st = p.stat()
        if p.name.endswith("-shm") and not shm_content:
            return (st.st_size,)
        return (st.st_size, st.st_mtime_ns, p.read_bytes())

    return {
        str(p.relative_to(folder)): entry(p)
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def _lines(counts) -> dict[tuple[str, str, str, str], int]:  # noqa: ANN001
    """Reduce output lines to (framework, tag, status, decided_by) -> count."""
    out: dict[tuple[str, str, str, str], int] = {}
    for line, n in counts.items():
        key = (line[0], line[1], line[6], line[7])
        out[key] = out.get(key, 0) + n
    return out


def test_only_shipped_tags_count_under_the_templates_spelling(tmp_path: Path) -> None:
    study = _make_study(
        tmp_path / "study",
        [
            ("garrett", "user need", "accepted", "researcher"),
            # Stored under an old name: counts under the current one.
            ("garrett", "Business Objective ", "denied", "researcher"),
            # A framework tag the researcher renamed: their words, skipped.
            ("garrett", "Acme checkout pain", "denied", "researcher"),
            # A custom group: skipped.
            (None, "user need", "accepted", "researcher"),
            # A framework that is not bundled: skipped.
            ("no-such-codebook", "user need", "accepted", "researcher"),
        ],
    )
    counts, _studies, tallies, read = tag_signal.count([study])

    assert read == 1
    assert _lines(counts) == {
        ("garrett", "user need", "accepted", "researcher"): 1,
        ("garrett", "product objective", "denied", "researcher"): 1,
    }
    assert tallies[("garrett", "read")] == 3
    assert tallies[("garrett", "counted")] == 2
    assert tallies[("garrett", "skipped")] == 1
    assert tallies[(tag_signal.CUSTOM, "skipped")] == 1
    assert tallies[(tag_signal.UNKNOWN, "skipped")] == 1
    printed = {line[1] for line in counts}
    assert "Acme checkout pain" not in printed


def test_decided_by_values_are_reported_as_stored(tmp_path: Path) -> None:
    study = _make_study(
        tmp_path / "study",
        [
            ("garrett", "user need", "accepted", "threshold"),
            ("garrett", "user need", "denied", "unknown"),
            ("garrett", "user need", "pending", None),
        ],
    )
    counts, *_ = tag_signal.count([study])
    assert _lines(counts) == {
        ("garrett", "user need", "accepted", "threshold"): 1,
        ("garrett", "user need", "denied", "unknown"): 1,
        ("garrett", "user need", "pending", "none"): 1,
    }


def test_a_redecided_proposal_counts_once_in_its_final_state(tmp_path: Path) -> None:
    study = _make_study(tmp_path / "study", [("garrett", "user need", "pending", None)])
    db = study / ".bristlenose" / "bristlenose.db"
    conn = sqlite3.connect(db)
    for status in ("denied", "accepted", "denied"):
        conn.execute(
            "UPDATE proposed_tags SET status = ?, decided_by = 'researcher'", (status,)
        )
        conn.commit()
    conn.close()

    counts, *_ = tag_signal.count([study])
    assert _lines(counts) == {("garrett", "user need", "denied", "researcher"): 1}


def test_an_old_database_is_skipped_and_the_next_study_still_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old = _make_study(
        tmp_path / "old", [("garrett", "user need", "accepted", "researcher")], revision="026"
    )
    new = _make_study(tmp_path / "new", [("garrett", "user need", "denied", "researcher")])

    counts, studies_per_line, _tallies, read = tag_signal.count([old, new])

    assert read == 1
    assert _lines(counts) == {("garrett", "user need", "denied", "researcher"): 1}
    assert set(studies_per_line.values()) == {1}
    assert "open it in Bristlenose once" in capsys.readouterr().err


def test_a_folder_without_a_database_is_skipped_not_created(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    counts, _s, _t, read = tag_signal.count([empty])
    assert read == 0
    assert not counts
    assert list(empty.iterdir()) == []


def test_a_cleanly_closed_study_folder_is_left_untouched(tmp_path: Path) -> None:
    study = _make_study(tmp_path / "study", [("garrett", "user need", "accepted", "researcher")])
    assert not (study / ".bristlenose" / "bristlenose.db-wal").exists()
    before = _snapshot(study)

    counts, *_ = tag_signal.count([study])

    assert counts
    assert _snapshot(study) == before


def test_a_study_the_app_has_open_is_read_and_left_untouched(tmp_path: Path) -> None:
    study = _make_study(tmp_path / "study", [("garrett", "user need", "pending", None)])
    db = study / ".bristlenose" / "bristlenose.db"
    # Stand in for the running app: WAL frames that have not been checkpointed.
    app = sqlite3.connect(db)
    app.execute("PRAGMA wal_autocheckpoint=0")
    app.execute("UPDATE proposed_tags SET status = 'accepted', decided_by = 'researcher'")
    app.commit()
    try:
        assert (study / ".bristlenose" / "bristlenose.db-wal").stat().st_size > 0
        before = _snapshot(study, shm_content=False)

        counts, *_ = tag_signal.count([study])

        # The committed change lives only in the WAL, and it is seen.
        assert _lines(counts) == {("garrett", "user need", "accepted", "researcher"): 1}
        assert _snapshot(study, shm_content=False) == before
    finally:
        app.close()


def test_folder_names_with_uri_characters_open_the_right_database(tmp_path: Path) -> None:
    # Built under a plain name (SQLAlchemy's URL parser would read the '?' as a
    # query), then renamed to the awkward one.
    built = _make_study(tmp_path / "plain", [("garrett", "user need", "accepted", "researcher")])
    # Windows refuses '?' in a file name; '#' and '%' still need encoding there.
    name = "Q3 study #2 100%" if sys.platform == "win32" else "Q3 study? #2 100%"
    study = built.rename(tmp_path / name)
    counts, _s, _t, read = tag_signal.count([study])
    assert read == 1
    assert counts


def test_csv_output_carries_an_as_of_date(tmp_path: Path) -> None:
    study = _make_study(tmp_path / "study", [("garrett", "user need", "accepted", "researcher")])
    out = tmp_path / "signal.csv"
    assert tag_signal.main([str(study), "--csv", str(out)]) == 0
    header, row = out.read_text(encoding="utf-8").splitlines()
    assert header.startswith("as_of,framework,tag,")
    assert row.startswith(f"{date.today().isoformat()},")
    assert ",garrett,user need,0.1.1,anthropic,claude-test,completed,accepted,researcher,1,1" in row


def test_an_empty_wal_left_by_another_reader_is_left_untouched(tmp_path: Path) -> None:
    study = _make_study(tmp_path / "study", [("garrett", "user need", "accepted", "researcher")])
    db = study / ".bristlenose" / "bristlenose.db"
    # The state a plain mode=ro visit leaves on the Mac: an empty -wal and a -shm.
    _leave_empty_wal(db, shm=True)
    before = _snapshot(study)

    counts, *_ = tag_signal.count([study])

    assert counts
    assert _snapshot(study) == before


def test_wal_frames_without_a_shm_are_skipped_and_nothing_is_created(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    study = _make_study(tmp_path / "study", [("garrett", "user need", "pending", None)])
    db = study / ".bristlenose" / "bristlenose.db"
    app = sqlite3.connect(db)
    app.execute("PRAGMA wal_autocheckpoint=0")
    app.execute("UPDATE proposed_tags SET status = 'accepted'")
    app.commit()
    try:
        # A copied folder: the database and its WAL, no -shm.
        copy = tmp_path / "copy" / ".bristlenose"
        copy.mkdir(parents=True)
        shutil.copy2(db, copy / "bristlenose.db")
        shutil.copy2(db.with_name("bristlenose.db-wal"), copy / "bristlenose.db-wal")
    finally:
        app.close()
    before = _snapshot(copy.parent)

    counts, _s, _t, read = tag_signal.count([copy.parent])

    assert read == 0
    assert not counts
    assert "no -shm" in capsys.readouterr().err
    assert _snapshot(copy.parent) == before


def test_a_hot_journal_is_skipped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    study = _make_study(tmp_path / "study", [("garrett", "user need", "accepted", "researcher")])
    (study / ".bristlenose" / "bristlenose.db-journal").write_bytes(b"\0" * 512)

    counts, _s, _t, read = tag_signal.count([study])

    assert read == 0
    assert "-journal" in capsys.readouterr().err


def test_a_database_without_alembic_version_is_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    study = _make_study(
        tmp_path / "study", [("garrett", "user need", "accepted", "researcher")], revision=None
    )
    counts, _s, _t, read = tag_signal.count([study])
    assert read == 0
    assert "open it in Bristlenose once" in capsys.readouterr().err


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod(0) cannot make a file unreadable on Windows"
)
def test_an_unreadable_study_is_skipped_and_the_run_carries_on(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = _make_study(tmp_path / "bad", [("garrett", "user need", "accepted", "researcher")])
    good = _make_study(tmp_path / "good", [("garrett", "user need", "denied", "researcher")])
    bad_db = bad / ".bristlenose" / "bristlenose.db"
    bad_db.chmod(0)
    try:
        counts, _s, _t, read = tag_signal.count([bad, good])
    finally:
        bad_db.chmod(0o644)
    assert read == 1
    assert _lines(counts) == {("garrett", "user need", "denied", "researcher"): 1}
    assert "could not read" in capsys.readouterr().err


def test_studies_column_counts_studies_and_a_study_named_twice_counts_once(
    tmp_path: Path,
) -> None:
    rows = [("garrett", "user need", "accepted", "researcher")] * 2
    a = _make_study(tmp_path / "a", rows)
    b = _make_study(tmp_path / "b", rows)

    counts, studies_per_line, _t, read = tag_signal.count([a, b, a, a / "."])

    assert read == 2
    assert list(counts.values()) == [4]
    assert list(studies_per_line.values()) == [2]


def test_an_empty_wal_without_a_shm_is_still_read_and_nothing_is_created(
    tmp_path: Path,
) -> None:
    study = _make_study(tmp_path / "study", [("garrett", "user need", "accepted", "researcher")])
    db = study / ".bristlenose" / "bristlenose.db"
    _leave_empty_wal(db, shm=False)
    before = _snapshot(study)

    counts, _s, _t, read = tag_signal.count([study])

    # An empty WAL holds nothing to read, so immutable=1 is safe and creates
    # no -shm; treating it as "has frames" would skip a readable study.
    assert read == 1
    assert counts
    assert _snapshot(study) == before
