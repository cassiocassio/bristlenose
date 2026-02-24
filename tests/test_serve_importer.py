"""Tests for the pipeline-to-SQLite importer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from bristlenose.server.db import create_session_factory, get_engine, init_db
from bristlenose.server.importer import _find_transcripts_dir, import_project
from bristlenose.server.models import (
    ClusterQuote,
    DeletedBadge,
    Person,
    Quote,
    QuoteEdit,
    QuoteState,
    QuoteTag,
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

    def test_second_import_no_duplicates(self, db: Session) -> None:
        """Second import should re-import without duplicating data."""
        project1 = import_project(db, _FIXTURE_DIR)
        project2 = import_project(db, _FIXTURE_DIR)
        assert project1.id == project2.id

        # Should still be 1 session, 4 quotes, etc.
        assert db.query(SessionModel).count() == 1
        assert db.query(Quote).count() == 4
        assert db.query(ScreenCluster).count() == 2
        assert db.query(ThemeGroup).count() == 1

    def test_reimport_updates_imported_at(self, db: Session) -> None:
        """Re-import should update imported_at timestamp."""
        project = import_project(db, _FIXTURE_DIR)
        first_imported = project.imported_at

        project = import_project(db, _FIXTURE_DIR)
        assert project.imported_at is not None
        assert project.imported_at >= first_imported
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


# ---------------------------------------------------------------------------
# Helpers for re-import tests
# ---------------------------------------------------------------------------


def _write_pipeline_output(
    tmp_path: Path,
    clusters: list[dict],
    themes: list[dict],
    project_name: str = "Reimport Test",
) -> Path:
    """Write intermediate JSON files for a synthetic project.

    Returns the project input directory (parent of bristlenose-output).
    """
    out = tmp_path / "bristlenose-output"
    out.mkdir(exist_ok=True)
    intermediate = out / ".bristlenose" / "intermediate"
    intermediate.mkdir(parents=True, exist_ok=True)
    (intermediate / "metadata.json").write_text(
        json.dumps({"project_name": project_name})
    )
    (intermediate / "screen_clusters.json").write_text(json.dumps(clusters))
    (intermediate / "theme_groups.json").write_text(json.dumps(themes))
    return tmp_path


def _make_quote(
    session_id: str,
    participant_id: str,
    start: float,
    text: str,
    sentiment: str = "neutral",
) -> dict:
    """Build a quote dict matching the intermediate JSON format."""
    return {
        "session_id": session_id,
        "participant_id": participant_id,
        "start_timecode": start,
        "end_timecode": start + 10.0,
        "text": text,
        "verbatim_excerpt": text[:40],
        "topic_label": "Test",
        "quote_type": "screen_specific",
        "researcher_context": None,
        "sentiment": sentiment,
        "intensity": 1,
    }


# ---------------------------------------------------------------------------
# Re-import with session changes
# ---------------------------------------------------------------------------


class TestReimportRemovedSession:
    """When a session is removed between pipeline runs, its data should vanish."""

    def test_removed_session_quotes_deleted(self, db: Session, tmp_path: Path) -> None:
        """Quotes from a removed session disappear on re-import."""
        # Run 1: two sessions (s1, s2)
        clusters_v1 = [
            {
                "screen_label": "Login",
                "description": "Login screen",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Login was easy"),
                    _make_quote("s2", "p1", 15.0, "Login was confusing"),
                ],
            },
        ]
        themes_v1 = [
            {
                "theme_label": "First impressions",
                "description": "First time using the app",
                "quotes": [
                    _make_quote("s2", "p1", 30.0, "It looked modern"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters_v1, themes_v1)
        import_project(db, tmp_path)

        assert db.query(Quote).count() == 3
        assert db.query(SessionModel).count() == 2

        # Run 2: removed s2 (bad interview)
        clusters_v2 = [
            {
                "screen_label": "Login",
                "description": "Login screen",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Login was easy"),
                ],
            },
        ]
        themes_v2: list[dict] = []
        _write_pipeline_output(tmp_path, clusters_v2, themes_v2)
        import_project(db, tmp_path)

        # s2 quotes should be gone
        assert db.query(Quote).count() == 1
        remaining = db.query(Quote).first()
        assert remaining is not None
        assert remaining.session_id == "s1"

        # s2 session should be gone
        assert db.query(SessionModel).count() == 1
        assert db.query(SessionModel).first().session_id == "s1"

        # Stale theme should be gone
        assert db.query(ThemeGroup).count() == 0

    def test_removed_session_cleans_join_rows(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """ClusterQuote and ThemeQuote joins for removed quotes are cleaned."""
        clusters_v1 = [
            {
                "screen_label": "Dashboard",
                "description": "",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 5.0, "Dashboard quote s1"),
                    _make_quote("s2", "p1", 5.0, "Dashboard quote s2"),
                ],
            },
        ]
        themes_v1 = [
            {
                "theme_label": "Theme A",
                "description": "",
                "quotes": [
                    _make_quote("s2", "p1", 20.0, "Theme quote s2"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters_v1, themes_v1)
        import_project(db, tmp_path)

        assert db.query(ClusterQuote).count() == 2
        assert db.query(ThemeQuote).count() == 1

        # Remove s2
        clusters_v2 = [
            {
                "screen_label": "Dashboard",
                "description": "",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 5.0, "Dashboard quote s1"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters_v2, [])
        import_project(db, tmp_path)

        assert db.query(ClusterQuote).count() == 1
        assert db.query(ThemeQuote).count() == 0


class TestReimportPreservesResearcherState:
    """Researcher state on surviving quotes must be preserved."""

    def test_starred_survives_reimport(self, db: Session, tmp_path: Path) -> None:
        """A starred quote keeps its star after re-import."""
        clusters = [
            {
                "screen_label": "Login",
                "description": "",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Login was easy"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters, [])
        import_project(db, tmp_path)

        # Researcher stars the quote
        quote = db.query(Quote).first()
        state = QuoteState(quote_id=quote.id, is_starred=True)
        db.add(state)
        db.commit()

        # Re-import with same data
        import_project(db, tmp_path)

        # Star should survive
        states = db.query(QuoteState).all()
        assert len(states) == 1
        assert states[0].is_starred is True

    def test_hidden_survives_reimport(self, db: Session, tmp_path: Path) -> None:
        """A hidden quote keeps its hidden state after re-import."""
        clusters = [
            {
                "screen_label": "Login",
                "description": "",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Login was easy"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters, [])
        import_project(db, tmp_path)

        # Researcher hides the quote
        quote = db.query(Quote).first()
        state = QuoteState(quote_id=quote.id, is_hidden=True)
        db.add(state)
        db.commit()

        # Re-import
        import_project(db, tmp_path)

        states = db.query(QuoteState).all()
        assert len(states) == 1
        assert states[0].is_hidden is True

    def test_tags_survive_reimport(self, db: Session, tmp_path: Path) -> None:
        """User-applied tags on surviving quotes are preserved."""
        from bristlenose.server.models import CodebookGroup, TagDefinition

        clusters = [
            {
                "screen_label": "Login",
                "description": "",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Login was easy"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters, [])
        import_project(db, tmp_path)

        # Create a tag and apply it
        group = CodebookGroup(name="UX", colour_set="ux")
        db.add(group)
        db.flush()
        tag_def = TagDefinition(codebook_group_id=group.id, name="Usability")
        db.add(tag_def)
        db.flush()
        quote = db.query(Quote).first()
        qt = QuoteTag(quote_id=quote.id, tag_definition_id=tag_def.id)
        db.add(qt)
        db.commit()

        # Re-import
        import_project(db, tmp_path)

        tags = db.query(QuoteTag).all()
        assert len(tags) == 1
        assert tags[0].tag_definition_id == tag_def.id

    def test_edits_survive_reimport(self, db: Session, tmp_path: Path) -> None:
        """Researcher text edits on surviving quotes are preserved."""
        clusters = [
            {
                "screen_label": "Login",
                "description": "",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Login was easy"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters, [])
        import_project(db, tmp_path)

        # Edit a quote
        quote = db.query(Quote).first()
        edit = QuoteEdit(quote_id=quote.id, edited_text="Login was very easy")
        db.add(edit)
        db.commit()

        # Re-import
        import_project(db, tmp_path)

        edits = db.query(QuoteEdit).all()
        assert len(edits) == 1
        assert edits[0].edited_text == "Login was very easy"

    def test_deleted_badges_survive_reimport(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """Deleted badge markers on surviving quotes are preserved."""
        clusters = [
            {
                "screen_label": "Login",
                "description": "",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Login was easy"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters, [])
        import_project(db, tmp_path)

        # Delete a badge
        quote = db.query(Quote).first()
        badge = DeletedBadge(quote_id=quote.id, sentiment="confusion")
        db.add(badge)
        db.commit()

        # Re-import
        import_project(db, tmp_path)

        badges = db.query(DeletedBadge).all()
        assert len(badges) == 1
        assert badges[0].sentiment == "confusion"


class TestReimportCleansRemovedSessionState:
    """Researcher state on quotes from removed sessions gets cleaned up."""

    def test_state_cleaned_for_removed_quotes(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """Stars/hidden/tags/edits/badges on removed quotes are deleted."""
        from bristlenose.server.models import CodebookGroup, TagDefinition

        clusters_v1 = [
            {
                "screen_label": "Login",
                "description": "",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Keep this"),
                    _make_quote("s2", "p1", 10.0, "Remove this"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters_v1, [])
        import_project(db, tmp_path)

        # Apply researcher state to both quotes
        q_keep = db.query(Quote).filter_by(session_id="s1").first()
        q_remove = db.query(Quote).filter_by(session_id="s2").first()

        # Star both
        db.add(QuoteState(quote_id=q_keep.id, is_starred=True))
        db.add(QuoteState(quote_id=q_remove.id, is_starred=True))

        # Tag both
        group = CodebookGroup(name="UX", colour_set="ux")
        db.add(group)
        db.flush()
        tag_def = TagDefinition(codebook_group_id=group.id, name="Usability")
        db.add(tag_def)
        db.flush()
        db.add(QuoteTag(quote_id=q_keep.id, tag_definition_id=tag_def.id))
        db.add(QuoteTag(quote_id=q_remove.id, tag_definition_id=tag_def.id))

        # Edit both
        db.add(QuoteEdit(quote_id=q_keep.id, edited_text="Keep edited"))
        db.add(QuoteEdit(quote_id=q_remove.id, edited_text="Remove edited"))

        # Badge both
        db.add(DeletedBadge(quote_id=q_keep.id, sentiment="frustration"))
        db.add(DeletedBadge(quote_id=q_remove.id, sentiment="frustration"))
        db.commit()

        # Re-import without s2
        clusters_v2 = [
            {
                "screen_label": "Login",
                "description": "",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Keep this"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters_v2, [])
        import_project(db, tmp_path)

        # s1 state preserved
        assert db.query(QuoteState).count() == 1
        assert db.query(QuoteState).first().quote_id == q_keep.id
        assert db.query(QuoteTag).count() == 1
        assert db.query(QuoteEdit).count() == 1
        assert db.query(QuoteEdit).first().edited_text == "Keep edited"
        assert db.query(DeletedBadge).count() == 1

        # s2 everything gone
        assert db.query(Quote).filter_by(session_id="s2").count() == 0


class TestReimportAddedSession:
    """When a new session is added between pipeline runs."""

    def test_new_session_quotes_appear(self, db: Session, tmp_path: Path) -> None:
        """Quotes from a newly added session appear on re-import."""
        # Run 1: just s1
        clusters_v1 = [
            {
                "screen_label": "Login",
                "description": "",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Login was easy"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters_v1, [])
        import_project(db, tmp_path)

        assert db.query(Quote).count() == 1
        assert db.query(SessionModel).count() == 1

        # Run 2: added s2 with new quotes
        clusters_v2 = [
            {
                "screen_label": "Login",
                "description": "Updated description",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Login was easy"),
                    _make_quote("s2", "p1", 12.0, "Login needs work"),
                ],
            },
        ]
        themes_v2 = [
            {
                "theme_label": "New theme",
                "description": "Emerged from new data",
                "quotes": [
                    _make_quote("s2", "p1", 25.0, "New insight"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters_v2, themes_v2)
        import_project(db, tmp_path)

        assert db.query(Quote).count() == 3
        assert db.query(SessionModel).count() == 2
        assert db.query(ThemeGroup).count() == 1
        assert db.query(ThemeGroup).first().theme_label == "New theme"

    def test_existing_researcher_state_preserved_on_add(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """Adding a session doesn't lose state on existing quotes."""
        clusters_v1 = [
            {
                "screen_label": "Login",
                "description": "",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Login was easy"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters_v1, [])
        import_project(db, tmp_path)

        # Star the existing quote
        quote = db.query(Quote).first()
        db.add(QuoteState(quote_id=quote.id, is_starred=True))
        db.commit()

        # Add s2
        clusters_v2 = [
            {
                "screen_label": "Login",
                "description": "",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Login was easy"),
                    _make_quote("s2", "p1", 12.0, "Login needs work"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters_v2, [])
        import_project(db, tmp_path)

        # Original quote's star preserved
        assert db.query(QuoteState).count() == 1
        assert db.query(QuoteState).first().is_starred is True
        assert db.query(Quote).count() == 2


class TestReimportStaleClusters:
    """Clusters/themes that no longer appear in pipeline output are removed."""

    def test_removed_cluster_cleaned(self, db: Session, tmp_path: Path) -> None:
        """A cluster that vanishes from the JSON is deleted on re-import."""
        clusters_v1 = [
            {
                "screen_label": "Dashboard",
                "description": "",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Dashboard quote"),
                ],
            },
            {
                "screen_label": "Settings",
                "description": "",
                "display_order": 2,
                "quotes": [
                    _make_quote("s1", "p1", 30.0, "Settings quote"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters_v1, [])
        import_project(db, tmp_path)

        assert db.query(ScreenCluster).count() == 2

        # Merge happened: Settings cluster removed, quote moved to Dashboard
        clusters_v2 = [
            {
                "screen_label": "Dashboard",
                "description": "Updated",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Dashboard quote"),
                    _make_quote("s1", "p1", 30.0, "Settings quote"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters_v2, [])
        import_project(db, tmp_path)

        assert db.query(ScreenCluster).count() == 1
        assert db.query(ScreenCluster).first().screen_label == "Dashboard"
        assert db.query(Quote).count() == 2  # both quotes survive
        assert db.query(ClusterQuote).count() == 2  # both in Dashboard now

    def test_removed_theme_cleaned(self, db: Session, tmp_path: Path) -> None:
        """A theme that vanishes from the JSON is deleted on re-import."""
        themes_v1 = [
            {
                "theme_label": "Theme A",
                "description": "",
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Theme A quote"),
                ],
            },
            {
                "theme_label": "Theme B",
                "description": "",
                "quotes": [
                    _make_quote("s1", "p1", 20.0, "Theme B quote"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, [], themes_v1)
        import_project(db, tmp_path)

        assert db.query(ThemeGroup).count() == 2

        # Re-run merged themes: only Theme A remains
        themes_v2 = [
            {
                "theme_label": "Theme A",
                "description": "Updated",
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Theme A quote"),
                    _make_quote("s1", "p1", 20.0, "Theme B quote"),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, [], themes_v2)
        import_project(db, tmp_path)

        assert db.query(ThemeGroup).count() == 1
        assert db.query(ThemeGroup).first().theme_label == "Theme A"
        assert db.query(Quote).count() == 2  # both quotes survive


# ---------------------------------------------------------------------------
# Transcript discovery fallback
# ---------------------------------------------------------------------------


def _write_transcript(output_dir: Path, sid: str, content: str) -> None:
    """Write a transcript file into the output directory."""
    raw = output_dir / "transcripts-raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / f"{sid}.txt").write_text(content)


def _write_people_yaml(output_dir: Path, participants: dict) -> None:
    """Write a people.yaml file into the output directory."""
    import yaml

    data = {
        "generated_by": "bristlenose",
        "last_updated": "2026-02-23T10:00:00Z",
        "participants": participants,
    }
    (output_dir / "people.yaml").write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True)
    )


class TestImportPeopleYaml:
    """People.yaml names should populate Person rows on import."""

    def _make_project(self, tmp_path: Path) -> Path:
        """Create a minimal project with transcripts and people.yaml."""
        out = tmp_path / "bristlenose-output"
        out.mkdir()
        intermediate = out / ".bristlenose" / "intermediate"
        intermediate.mkdir(parents=True)
        (intermediate / "metadata.json").write_text('{"project_name": "Name Test"}')
        (intermediate / "screen_clusters.json").write_text("[]")
        (intermediate / "theme_groups.json").write_text("[]")

        _write_transcript(
            out,
            "s1",
            (
                "# Transcript: s1\n"
                "# Date: 2026-02-20\n"
                "# Duration: 00:01:00\n"
                "\n"
                "[00:02] [m1] Welcome.\n"
                "[00:10] [p1] Thanks for having me.\n"
            ),
        )
        return tmp_path

    def test_names_populated_from_people_yaml(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """Person rows get full_name, short_name, role from people.yaml."""
        project_dir = self._make_project(tmp_path)
        out = tmp_path / "bristlenose-output"

        _write_people_yaml(out, {
            "p1": {
                "computed": {
                    "participant_id": "p1",
                    "session_id": "s1",
                    "duration_seconds": 60.0,
                    "words_spoken": 100,
                    "pct_words": 50.0,
                    "pct_time_speaking": 50.0,
                    "source_file": "test.vtt",
                },
                "editable": {
                    "full_name": "Sarah Jones",
                    "short_name": "Sarah",
                    "role": "Product Manager",
                    "persona": "early adopter",
                    "notes": "Very engaged",
                },
            },
            "m1": {
                "computed": {
                    "participant_id": "m1",
                    "session_id": "s1",
                    "duration_seconds": 60.0,
                    "words_spoken": 50,
                    "pct_words": 25.0,
                    "pct_time_speaking": 25.0,
                    "source_file": "test.vtt",
                },
                "editable": {
                    "full_name": "Jane Researcher",
                    "short_name": "Jane",
                    "role": "UX Researcher",
                    "persona": "",
                    "notes": "",
                },
            },
        })

        import_project(db, project_dir)

        speakers = db.query(SessionSpeaker).all()
        assert len(speakers) == 2

        # Check p1
        p1_sp = [sp for sp in speakers if sp.speaker_code == "p1"][0]
        p1 = db.get(Person, p1_sp.person_id)
        assert p1.full_name == "Sarah Jones"
        assert p1.short_name == "Sarah"
        assert p1.role_title == "Product Manager"
        assert p1.persona == "early adopter"
        assert p1.notes == "Very engaged"

        # Check m1
        m1_sp = [sp for sp in speakers if sp.speaker_code == "m1"][0]
        m1 = db.get(Person, m1_sp.person_id)
        assert m1.full_name == "Jane Researcher"
        assert m1.short_name == "Jane"
        assert m1.role_title == "UX Researcher"

    def test_missing_people_yaml_creates_empty_names(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """Without people.yaml, Person rows have empty names (existing behaviour)."""
        project_dir = self._make_project(tmp_path)
        import_project(db, project_dir)

        persons = db.query(Person).all()
        for p in persons:
            assert p.full_name == ""
            assert p.short_name == ""

    def test_partial_people_yaml(self, db: Session, tmp_path: Path) -> None:
        """people.yaml with only some speakers populates what it can."""
        project_dir = self._make_project(tmp_path)
        out = tmp_path / "bristlenose-output"

        # Only p1 has names, m1 is missing from people.yaml
        _write_people_yaml(out, {
            "p1": {
                "computed": {
                    "participant_id": "p1",
                    "session_id": "s1",
                    "duration_seconds": 60.0,
                    "words_spoken": 100,
                    "pct_words": 50.0,
                    "pct_time_speaking": 50.0,
                    "source_file": "test.vtt",
                },
                "editable": {
                    "full_name": "Fred Thompson",
                    "short_name": "Fred",
                    "role": "",
                    "persona": "",
                    "notes": "",
                },
            },
        })

        import_project(db, project_dir)

        speakers = db.query(SessionSpeaker).all()

        p1_sp = [sp for sp in speakers if sp.speaker_code == "p1"][0]
        p1 = db.get(Person, p1_sp.person_id)
        assert p1.full_name == "Fred Thompson"
        assert p1.short_name == "Fred"

        m1_sp = [sp for sp in speakers if sp.speaker_code == "m1"][0]
        m1 = db.get(Person, m1_sp.person_id)
        assert m1.full_name == ""
        assert m1.short_name == ""


    def test_reimport_fills_empty_names_from_yaml(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """Re-import fills empty Person names from people.yaml added after first run."""
        # First import: no people.yaml → empty names
        project_dir = self._make_project(tmp_path)
        import_project(db, project_dir)

        speakers = db.query(SessionSpeaker).all()
        p1_sp = [sp for sp in speakers if sp.speaker_code == "p1"][0]
        p1 = db.get(Person, p1_sp.person_id)
        assert p1.full_name == ""

        # Now add people.yaml
        out = tmp_path / "bristlenose-output"
        _write_people_yaml(out, {
            "p1": {
                "computed": {
                    "participant_id": "p1",
                    "session_id": "s1",
                    "duration_seconds": 60.0,
                    "words_spoken": 100,
                    "pct_words": 50.0,
                    "pct_time_speaking": 50.0,
                    "source_file": "test.vtt",
                },
                "editable": {
                    "full_name": "Sarah Jones",
                    "short_name": "Sarah",
                    "role": "Designer",
                    "persona": "",
                    "notes": "",
                },
            },
        })

        # Re-import: should fill empty names from people.yaml
        import_project(db, project_dir)

        # Refresh from DB
        db.expire_all()
        p1 = db.get(Person, p1_sp.person_id)
        assert p1.full_name == "Sarah Jones"
        assert p1.short_name == "Sarah"
        assert p1.role_title == "Designer"

    def test_reimport_does_not_overwrite_ui_edits(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """Re-import doesn't overwrite names the researcher edited via UI."""
        project_dir = self._make_project(tmp_path)
        out = tmp_path / "bristlenose-output"

        _write_people_yaml(out, {
            "p1": {
                "computed": {
                    "participant_id": "p1",
                    "session_id": "s1",
                    "duration_seconds": 60.0,
                    "words_spoken": 100,
                    "pct_words": 50.0,
                    "pct_time_speaking": 50.0,
                    "source_file": "test.vtt",
                },
                "editable": {
                    "full_name": "Frederick Thompson",
                    "short_name": "Frederick",
                    "role": "",
                    "persona": "",
                    "notes": "",
                },
            },
        })

        import_project(db, project_dir)

        # Researcher edits the name via UI (simulated by direct DB update)
        speakers = db.query(SessionSpeaker).all()
        p1_sp = [sp for sp in speakers if sp.speaker_code == "p1"][0]
        p1 = db.get(Person, p1_sp.person_id)
        p1.full_name = "Fred Thompson"
        p1.short_name = "Fred"
        db.commit()

        # Re-import: YAML still says "Frederick", but DB says "Fred"
        import_project(db, project_dir)

        db.expire_all()
        p1 = db.get(Person, p1_sp.person_id)
        # Researcher's edit wins — non-empty fields are never overwritten
        assert p1.full_name == "Fred Thompson"
        assert p1.short_name == "Fred"


class TestFindTranscriptsDir:
    """_find_transcripts_dir tries multiple candidate locations."""

    def test_prefers_cooked_over_raw(self, tmp_path: Path) -> None:
        """transcripts-cooked wins if both exist in output_dir."""
        output = tmp_path / "output"
        output.mkdir()
        cooked = output / "transcripts-cooked"
        cooked.mkdir()
        (cooked / "s1.txt").write_text("# Transcript: s1\n")
        raw = output / "transcripts-raw"
        raw.mkdir()
        (raw / "s1.txt").write_text("# Transcript: s1\n")

        result = _find_transcripts_dir(tmp_path, output)
        assert result == cooked

    def test_finds_raw_in_output(self, tmp_path: Path) -> None:
        """Standard pipeline layout: transcripts-raw in output dir."""
        output = tmp_path / "output"
        output.mkdir()
        raw = output / "transcripts-raw"
        raw.mkdir()
        (raw / "s1.txt").write_text("# Transcript: s1\n")

        result = _find_transcripts_dir(tmp_path, output)
        assert result == raw

    def test_falls_back_to_project_transcripts(self, tmp_path: Path) -> None:
        """Non-standard layout: transcripts/ in project dir (Plato case)."""
        output = tmp_path / "output"
        output.mkdir()
        transcripts = tmp_path / "transcripts"
        transcripts.mkdir()
        (transcripts / "s1.txt").write_text("# Transcript: s1\n")

        result = _find_transcripts_dir(tmp_path, output)
        assert result == transcripts

    def test_falls_back_to_project_transcripts_raw(self, tmp_path: Path) -> None:
        """Input-dir layout: transcripts-raw/ in project dir."""
        output = tmp_path / "output"
        output.mkdir()
        raw = tmp_path / "transcripts-raw"
        raw.mkdir()
        (raw / "s1.txt").write_text("# Transcript: s1\n")

        result = _find_transcripts_dir(tmp_path, output)
        assert result == raw

    def test_returns_default_when_none_found(self, tmp_path: Path) -> None:
        """Returns output_dir/transcripts-raw when no candidates match."""
        output = tmp_path / "output"
        output.mkdir()

        result = _find_transcripts_dir(tmp_path, output)
        assert result == output / "transcripts-raw"

    def test_ignores_empty_directories(self, tmp_path: Path) -> None:
        """A candidate dir must contain .txt files to match."""
        output = tmp_path / "output"
        output.mkdir()
        raw = output / "transcripts-raw"
        raw.mkdir()  # exists but empty

        transcripts = tmp_path / "transcripts"
        transcripts.mkdir()
        (transcripts / "s1.txt").write_text("# Transcript: s1\n")

        result = _find_transcripts_dir(tmp_path, output)
        assert result == transcripts
