"""Tests for the pipeline-to-SQLite importer."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from bristlenose.server.db import create_session_factory, get_engine, init_db
from bristlenose.server.importer import import_project
from bristlenose.server.models import (
    ClusterQuote,
    Person,
    Quote,
    ScreenCluster,
    SessionSpeaker,
    SourceFile,
    ThemeGroup,
    ThemeQuote,
    TranscriptSegment,
)
from bristlenose.server.models import (
    Session as SessionModel,
)

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.fixture()
def db():
    """In-memory database session with all tables created."""
    engine = get_engine("sqlite://")
    init_db(engine)
    factory = create_session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


class TestImportProject:
    """Test importing the smoke-test fixture."""

    def test_creates_project(self, db: Session) -> None:
        project = import_project(db, _FIXTURE_DIR)
        assert project.name == "Smoke Test"
        assert project.slug == "smoke-test"
        assert project.imported_at is not None

    def test_creates_session(self, db: Session) -> None:
        import_project(db, _FIXTURE_DIR)
        sessions = db.query(SessionModel).all()
        assert len(sessions) == 1
        s = sessions[0]
        assert s.session_id == "s1"
        assert s.session_number == 1
        assert s.session_date is not None
        assert s.duration_seconds == 78.0  # 00:01:18

    def test_creates_source_file(self, db: Session) -> None:
        import_project(db, _FIXTURE_DIR)
        files = db.query(SourceFile).all()
        assert len(files) == 1
        sf = files[0]
        assert sf.file_type == "subtitle_vtt"
        assert "Session 1.vtt" in sf.path

    def test_creates_transcript_segments(self, db: Session) -> None:
        import_project(db, _FIXTURE_DIR)
        segments = db.query(TranscriptSegment).all()
        # The transcript has 7 segments: m1, p1, m1, p1, m1, p1, m1 (wait — let's count)
        # [00:02] [m1], [00:10] [p1], [00:19] [m1], [00:26] [p1],
        # [00:39] [m1], [00:46] [p1], [00:56] [m1], [01:06] [p1]
        assert len(segments) == 8
        assert segments[0].speaker_code == "m1"
        assert segments[1].speaker_code == "p1"

    def test_creates_speakers(self, db: Session) -> None:
        import_project(db, _FIXTURE_DIR)
        speakers = db.query(SessionSpeaker).all()
        assert len(speakers) == 2
        codes = {sp.speaker_code for sp in speakers}
        assert codes == {"m1", "p1"}

        # Check roles
        roles = {sp.speaker_code: sp.speaker_role for sp in speakers}
        assert roles["m1"] == "researcher"
        assert roles["p1"] == "participant"

    def test_creates_persons(self, db: Session) -> None:
        import_project(db, _FIXTURE_DIR)
        persons = db.query(Person).all()
        assert len(persons) == 2  # one per speaker

    def test_creates_screen_clusters(self, db: Session) -> None:
        import_project(db, _FIXTURE_DIR)
        clusters = db.query(ScreenCluster).all()
        assert len(clusters) == 2
        labels = {c.screen_label for c in clusters}
        assert labels == {"Dashboard", "Search"}

        # Check created_by
        for c in clusters:
            assert c.created_by == "pipeline"
            assert c.last_imported_at is not None

    def test_creates_theme_groups(self, db: Session) -> None:
        import_project(db, _FIXTURE_DIR)
        themes = db.query(ThemeGroup).all()
        assert len(themes) == 1
        assert themes[0].theme_label == "Onboarding gaps"
        assert themes[0].created_by == "pipeline"

    def test_creates_quotes(self, db: Session) -> None:
        import_project(db, _FIXTURE_DIR)
        quotes = db.query(Quote).all()
        # 2 quotes in Dashboard cluster + 1 in Search cluster + 1 in Onboarding theme = 4
        assert len(quotes) == 4

        # Verify quote content
        texts = {q.text[:30] for q in quotes}
        assert any("dashboard" in t.lower() for t in texts)
        assert any("search" in t.lower() for t in texts)
        assert any("onboarding" in t.lower() for t in texts)

    def test_creates_cluster_quote_joins(self, db: Session) -> None:
        import_project(db, _FIXTURE_DIR)
        cqs = db.query(ClusterQuote).all()
        # 2 quotes in Dashboard + 1 in Search = 3
        assert len(cqs) == 3
        for cq in cqs:
            assert cq.assigned_by == "pipeline"

    def test_creates_theme_quote_joins(self, db: Session) -> None:
        import_project(db, _FIXTURE_DIR)
        tqs = db.query(ThemeQuote).all()
        assert len(tqs) == 1
        assert tqs[0].assigned_by == "pipeline"

    def test_quote_sentiments(self, db: Session) -> None:
        import_project(db, _FIXTURE_DIR)
        quotes = db.query(Quote).all()
        # "I found the dashboard" → confusion
        dashboard_q = [q for q in quotes if "dashboard" in q.text.lower()][0]
        assert dashboard_q.sentiment == "confusion"
        # "The search was great" → delight
        search_q = [q for q in quotes if "search" in q.text.lower()][0]
        assert search_q.sentiment == "delight"

    def test_cluster_display_order(self, db: Session) -> None:
        import_project(db, _FIXTURE_DIR)
        clusters = db.query(ScreenCluster).order_by(ScreenCluster.display_order).all()
        assert clusters[0].screen_label == "Dashboard"  # display_order=1
        assert clusters[1].screen_label == "Search"  # display_order=2


class TestImportIdempotent:
    """Verify re-importing doesn't duplicate data."""

    def test_second_import_skips(self, db: Session) -> None:
        """Second import should be a no-op (imported_at already set)."""
        project1 = import_project(db, _FIXTURE_DIR)
        project2 = import_project(db, _FIXTURE_DIR)
        assert project1.id == project2.id

        # Should still be 1 session, 4 quotes, etc.
        assert db.query(SessionModel).count() == 1
        assert db.query(Quote).count() == 4

    def test_forced_reimport_after_clear(self, db: Session) -> None:
        """If we clear imported_at, re-import should update data."""
        project = import_project(db, _FIXTURE_DIR)

        # Clear imported_at to force re-import
        project.imported_at = None
        db.commit()

        project = import_project(db, _FIXTURE_DIR)
        assert project.imported_at is not None
        # Data should still be consistent (upsert, no duplicates)
        assert db.query(SessionModel).count() == 1
        assert db.query(Quote).count() == 4
        assert db.query(ScreenCluster).count() == 2
        assert db.query(ThemeGroup).count() == 1


class TestImportMissing:
    """Test import handles missing files gracefully."""

    def test_import_nonexistent_dir(self, db: Session, tmp_path: Path) -> None:
        """Import from an empty dir should create a minimal project."""
        empty = tmp_path / "empty"
        empty.mkdir()
        project = import_project(db, empty)
        assert project.name == "Untitled"
        assert project.imported_at is not None
        assert db.query(SessionModel).count() == 0
        assert db.query(Quote).count() == 0

    def test_import_only_metadata(self, db: Session, tmp_path: Path) -> None:
        """Import with only metadata.json should create named project."""
        out = tmp_path / "bristlenose-output"
        out.mkdir()
        intermediate = out / ".bristlenose" / "intermediate"
        intermediate.mkdir(parents=True)
        (intermediate / "metadata.json").write_text('{"project_name": "My Project"}')

        project = import_project(db, tmp_path)
        assert project.name == "My Project"
        assert project.slug == "my-project"
