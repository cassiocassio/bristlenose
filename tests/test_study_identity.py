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


def test_the_marker_leaves_a_visible_beacon_for_spotlight(tmp_path: Path) -> None:
    """Spotlight indexes a visible text file's contents but not the hidden
    marker; the Mac's Locate searches for this (design §13a)."""
    out = tmp_path / "bristlenose-output"
    study_id = study_marker.read_or_mint(out, minted_by="run")
    beacon = study_marker.beacon_path(out)
    assert beacon.parent == out and not beacon.name.startswith(".")
    assert beacon.read_text(encoding="utf-8") == f"bristlenose-study {study_id}\n"


def test_ingest_knows_the_marker_and_beacon_as_its_own(tmp_path: Path) -> None:
    """With ``--output`` inside the interview folder, or a beacon copied about by
    hand, ingest must pass over them silently rather than call them a format
    it cannot read."""
    from bristlenose.utils.fs import is_bristlenose_artefact

    out = tmp_path / "bristlenose-output"
    study_marker.read_or_mint(out, minted_by="run")
    assert is_bristlenose_artefact(study_marker.beacon_path(out))
    assert is_bristlenose_artefact(study_marker.marker_path(out))


def test_a_beacon_that_cannot_be_written_leaves_the_marker_and_no_litter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The beacon is a search aid: failing to place it must not fail the
    marker, and must not leave a half-written or temporary file behind."""
    out = tmp_path / "bristlenose-output"
    real_replace = study_marker.os.replace

    def refuse_beacon(src: str, dst: object) -> None:
        if str(dst).endswith(study_marker.BEACON_FILENAME):
            raise OSError("read-only")
        real_replace(src, dst)

    monkeypatch.setattr(study_marker.os, "replace", refuse_beacon)
    study_id = study_marker.read_or_mint(out, minted_by="run")
    assert study_id is not None and study_marker.read(out) == study_id
    assert not study_marker.beacon_path(out).exists()
    assert [p.name for p in out.iterdir()] == [".bristlenose"]


def test_a_study_minted_before_the_beacon_gets_one(tmp_path: Path) -> None:
    """Markers minted before 15 Oct 2026 have no beacon, and a copy re-minted
    by the app may carry its original's; the next run or serve puts it right."""
    out = tmp_path / "bristlenose-output"
    study_id = study_marker.read_or_mint(out, minted_by="run")
    beacon = study_marker.beacon_path(out)
    beacon.unlink()
    assert study_marker.read_or_mint(out, minted_by="serve") == study_id
    assert beacon.read_text(encoding="utf-8") == study_marker.beacon_text(study_id)
    beacon.write_text(study_marker.beacon_text(str(uuid.uuid4())), encoding="utf-8")
    study_marker.read_or_mint(out, minted_by="serve")
    assert beacon.read_text(encoding="utf-8") == study_marker.beacon_text(study_id)


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


def test_a_forked_row_holding_a_persons_tag_is_left(tmp_path: Path) -> None:
    """A tag a person applied keeps the fork; the importer's own sentiment tags
    (``source="pipeline"``) do not (``test_a_fork_made_by_a_real_import_is_removed``)."""
    proj = _project(tmp_path)
    engine, factory = _own_db(proj)
    _fork(proj, factory)
    db = factory()
    from bristlenose.server.models import Quote, QuoteTag

    fork_id = max(r.id for r in db.query(Project).all())
    quote = db.query(Quote).first()
    clone = Quote(**{c.name: getattr(quote, c.name) for c in Quote.__table__.columns
                     if c.name != "id"})
    clone.project_id = fork_id
    db.add(clone)
    db.flush()
    tag_def = db.query(QuoteTag).first().tag_definition_id
    db.add(QuoteTag(quote_id=clone.id, tag_definition_id=tag_def, source="human"))
    db.commit()
    import_project(db, proj)
    db.commit()
    assert sorted(r.id for r in db.query(Project).all()) == [1, fork_id]
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


def test_the_swift_writer_shape_reads(tmp_path: Path) -> None:
    """What ``StudyMarker.remint`` writes (sorted keys, minted_by app, a
    copied_from id) is a marker Python reads. ``StudyMarkerTests`` pins the
    other direction."""
    out = tmp_path / "bristlenose-output"
    path = study_marker.marker_path(out)
    path.parent.mkdir(parents=True)
    fresh, original = str(uuid.uuid4()), str(uuid.uuid4())
    path.write_text(json.dumps({
        "copied_from": original, "minted_at": "2026-10-15T10:00:00Z",
        "minted_by": "app", "schema": 1, "study_id": fresh,
    }, indent=2, sort_keys=True))
    assert study_marker.read(out) == fresh


def test_a_mid_run_import_never_deletes_a_fork(tmp_path: Path) -> None:
    """Fork cleanup belongs to the whole-project import, not to the progressive
    imports a run makes while the researcher may be reading (review)."""
    from bristlenose.server.importer import import_readable_sessions

    proj = _project(tmp_path)
    engine, factory = _own_db(proj)
    _fork(proj, factory)
    db = factory()
    fork_id = max(r.id for r in db.query(Project).all())
    import_readable_sessions(db, proj, {"s1"})
    db.commit()
    assert sorted(r.id for r in db.query(Project).all()) == [1, fork_id]
    db.close()
    engine.dispose()


def test_a_recording_re_exported_in_place_is_not_the_old_sessions_media(
    tmp_path: Path,
) -> None:
    """Re-exported under its name, a recording is a new session (§5); the old
    session's transcript still names the file and must not play its new
    bytes, or every quote lands in the wrong edit (Fable review, 15 Oct 2026)."""
    from bristlenose.server.models import Session as SessionModel
    from bristlenose.server.models import SourceFile
    from bristlenose.session_registry import FP_PREFIX, SessionRegistry
    from bristlenose.utils.fingerprint import content_fingerprint

    proj = _project(tmp_path)
    out = proj / "bristlenose-output"
    raw = out / "transcripts-raw" / "s1.txt"
    raw.write_text(raw.read_text(encoding="utf-8").replace(
        "# Source: Session 1.vtt", "# Source: Session 1.mp4"), encoding="utf-8")
    media = proj / "Session 1.mp4"
    media.write_bytes(b"the recording this session was made from")
    reg = SessionRegistry.load(out)
    fp_key = FP_PREFIX + content_fingerprint(media)
    reg.sessions[fp_key] = "s1"
    reg.hints[fp_key] = "Session 1.mp4"
    reg.save()

    def media_rows() -> list[str]:
        engine, factory = _own_db(proj)
        db = factory()
        import_project(db, proj)
        db.commit()
        sess = db.query(SessionModel).filter_by(session_id="s1").one()
        rows = [Path(r.path).name for r in db.query(SourceFile).filter_by(session_id=sess.id)
                if r.file_type in ("video", "audio")]
        has_media = sess.has_media
        db.close()
        engine.dispose()
        return rows if has_media else []

    assert media_rows() == ["Session 1.mp4"]
    media.write_bytes(b"a trimmed re-export saved over it")
    assert media_rows() == [], "the old session plays the re-export's bytes"


def test_a_session_with_video_and_audio_keeps_its_media(tmp_path: Path) -> None:
    """The header names one file and the fingerprint was taken from the other:
    their bytes differ by nature, and that is not a re-export (Fable review,
    15 Oct 2026)."""
    from bristlenose.server.models import Session as SessionModel
    from bristlenose.session_registry import FP_PREFIX, SessionRegistry
    from bristlenose.utils.fingerprint import content_fingerprint

    proj = _project(tmp_path)
    out = proj / "bristlenose-output"
    raw = out / "transcripts-raw" / "s1.txt"
    raw.write_text(raw.read_text(encoding="utf-8").replace(
        "# Source: Session 1.vtt", "# Source: Session 1.m4a"), encoding="utf-8")
    (proj / "Session 1.m4a").write_bytes(b"the audio track")
    video = proj / "Session 1.mp4"
    video.write_bytes(b"the video, fingerprinted as the primary file")
    reg = SessionRegistry.load(out)
    fp_key = FP_PREFIX + content_fingerprint(video)
    reg.sessions[fp_key] = "s1"
    reg.hints[fp_key] = "Session 1.mp4"
    reg.save()

    engine, factory = _own_db(proj)
    db = factory()
    import_project(db, proj)
    db.commit()
    assert db.query(SessionModel).filter_by(session_id="s1").one().has_media
    db.close()
    engine.dispose()


def test_a_copy_first_touched_mid_run_still_gets_its_own_id(tmp_path: Path) -> None:
    """The first import of a CLI copy may be a run's progressive one, which
    heals the row's stored paths. The re-mint must happen there too, or the
    only evidence of the copy is gone before the whole import looks (Fable
    review, 15 Oct 2026)."""
    from bristlenose.server.importer import import_readable_sessions

    proj = _project(tmp_path / "a")
    engine, factory = _own_db(proj)
    db = factory()
    import_project(db, proj)
    db.commit()
    db.close()
    engine.dispose()
    original = study_marker.read(proj / "bristlenose-output")

    copy = tmp_path / "b" / proj.name
    shutil.copytree(proj, copy)
    engine, factory = _own_db(copy)
    db = factory()
    import_readable_sessions(db, copy, {"s1"})
    db.commit()
    import_project(db, copy)
    db.commit()
    db.close()
    engine.dispose()
    reminted = study_marker.read(copy / "bristlenose-output")
    assert reminted is not None and reminted != original, "the copy kept the original's id"
    assert study_marker.read(proj / "bristlenose-output") == original


def test_a_copy_opened_from_the_cli_gets_its_own_id(tmp_path: Path) -> None:
    """With no app to re-mint it, the serve does (design §9): the database's
    row still names the original's folder, which is still there carrying the
    same id, so this folder is a copy. A move (original gone) keeps the id."""
    proj = _project(tmp_path / "a")
    engine, factory = _own_db(proj)
    db = factory()
    import_project(db, proj)
    db.commit()
    db.close()
    engine.dispose()
    original = study_marker.read(proj / "bristlenose-output")

    copy = tmp_path / "b" / proj.name
    shutil.copytree(proj, copy)
    engine, factory = _own_db(copy)
    db = factory()
    import_project(db, copy)
    db.commit()
    db.close()
    engine.dispose()
    reminted = study_marker.read(copy / "bristlenose-output")
    assert reminted is not None and reminted != original, "the copy kept the original's id"
    assert study_marker.read(proj / "bristlenose-output") == original

    moved = tmp_path / "c" / proj.name
    moved.parent.mkdir()
    shutil.move(str(proj), str(moved))
    engine, factory = _own_db(moved)
    db = factory()
    import_project(db, moved)
    db.commit()
    db.close()
    engine.dispose()
    assert study_marker.read(moved / "bristlenose-output") == original, "a move was re-minted"


def test_a_fork_made_by_a_real_import_is_removed(tmp_path: Path, monkeypatch) -> None:
    """The fork an older release left was a full import: sessions, speakers and
    the importer's own sentiment tags (``source="pipeline"``). None of that is a
    person's work, so it must not keep the fork alive. The bare-row forks above
    could not show this; found by the second review, 15 Oct 2026."""
    import bristlenose.server.importer as imp

    proj = _project(tmp_path)
    engine, factory = _own_db(proj)
    db = factory()
    import_project(db, proj)
    db.commit()
    # An older release: matched by path, and a moved folder's path is new.
    moved = tmp_path / "moved" / proj.name
    moved.parent.mkdir()
    shutil.move(str(proj), str(moved))
    engine.dispose()
    engine, factory = _own_db(moved)
    db = factory()
    monkeypatch.setattr(imp, "_is_the_studys_own_database", lambda *_a: False)
    import_project(db, moved)
    db.commit()
    assert len(db.query(Project).all()) == 2, "the old release's fork was not made"
    monkeypatch.undo()
    import_project(db, moved)
    db.commit()
    assert [r.id for r in db.query(Project).all()] == [1], "a real fork outlived the import"
    db.close()
    engine.dispose()
