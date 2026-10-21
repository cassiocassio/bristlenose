"""Tests for the pipeline-to-SQLite importer."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from bristlenose.server.db import create_session_factory, get_engine, init_db
from bristlenose.server.importer import (
    _find_transcripts_dir,
    _words_read_as,
    import_project,
)
from bristlenose.server.models import (
    ClusterQuote,
    CodebookGroup,
    DeletedBadge,
    Person,
    Project,
    ProjectCodebookGroup,
    Quote,
    QuoteEdit,
    QuoteState,
    QuoteTag,
    ScreenCluster,
    SessionSpeaker,
    SourceFile,
    TagDefinition,
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

    def test_checkpoints_wal_so_immutable_readers_see_sessions(
        self, tmp_path: Path
    ) -> None:
        """After import, sessions must be visible to an out-of-process reader
        that opens the DB with ``?immutable=1`` — the sandboxed desktop
        sidecar's session-count read, which ignores the WAL. Without the
        post-import PASSIVE checkpoint the rows stay WAL-resident and an
        immutable read sees zero (the desktop sidebar count bug). Uses a
        file-backed WAL DB; the in-memory ``db`` fixture has no WAL."""
        db_path = tmp_path / "bristlenose.db"
        engine = get_engine(f"sqlite:///{db_path}")
        init_db(engine)
        session = create_session_factory(engine)()
        try:
            import_project(session, _FIXTURE_DIR)
        finally:
            session.close()

        # Fresh immutable connection: reads only the main DB file, ignoring the
        # WAL. Seeing the session proves the checkpoint flushed WAL -> main.
        conn = sqlite3.connect(f"file:{db_path}?immutable=1", uri=True)
        try:
            count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        finally:
            conn.close()
        assert count == 1

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
        # One per identity: the participant. Nothing names the moderator, so
        # its slot points at nobody (route C) rather than at an empty person.
        assert len(persons) == 1

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


class TestImportPathCanonicalisation:
    """Project identity must survive different spellings of the same path.

    Regression for the incremental-add bug where ``run trial-runs/foo``
    (relative) and ``run /abs/trial-runs/foo`` (absolute) resolved to the same
    directory but forked two Project rows — orphaning the researcher's curation
    (starred/hidden/renames) on the first row so the re-analysis showed none of
    it.  The importer now matches on the resolved path.
    """

    @pytest.fixture(autouse=True)
    def _cwd_beside_the_project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # A relative spelling only exists on the same drive: on Windows CI the
        # checkout is D: and the temp dir C:, and relpath across them raises.
        monkeypatch.chdir(tmp_path.parent)

    @staticmethod
    def _clusters() -> list[dict]:
        return [
            {
                "screen_label": "Login",
                "description": "",
                "display_order": 1,
                "quotes": [_make_quote("s1", "p1", 10.0, "Login was easy")],
            },
        ]

    def test_relative_and_absolute_spelling_match_same_project(
        self, db: Session, tmp_path: Path,
    ) -> None:
        proj = _write_pipeline_output(tmp_path, self._clusters(), [])
        rel = Path(os.path.relpath(proj, Path.cwd()))
        assert str(rel) != str(proj)  # genuinely different spellings

        p_abs = import_project(db, proj)
        p_rel = import_project(db, rel)

        assert p_abs.id == p_rel.id
        assert db.query(Project).count() == 1

    def test_stored_input_dir_is_canonical_absolute(
        self, db: Session, tmp_path: Path,
    ) -> None:
        proj = _write_pipeline_output(tmp_path, self._clusters(), [])
        rel = Path(os.path.relpath(proj, Path.cwd()))
        project = import_project(db, rel)
        assert Path(project.input_dir).is_absolute()
        assert Path(project.input_dir) == proj.resolve()

    def test_curation_survives_reimport_via_different_spelling(
        self, db: Session, tmp_path: Path,
    ) -> None:
        proj = _write_pipeline_output(tmp_path, self._clusters(), [])
        p1 = import_project(db, proj)
        quote = db.query(Quote).filter_by(project_id=p1.id).first()
        assert quote is not None
        db.add(QuoteState(quote_id=quote.id, is_starred=True))
        db.commit()

        # Re-import via a non-canonical spelling of the same directory.
        rel = Path(os.path.relpath(proj, Path.cwd()))
        p2 = import_project(db, rel)

        assert p2.id == p1.id
        assert db.query(Project).count() == 1
        state = db.query(QuoteState).filter_by(quote_id=quote.id).first()
        assert state is not None and state.is_starred is True

    def test_case_variant_spelling_matches_on_case_insensitive_fs(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """On a case-insensitive volume (macOS/Windows) a case-variant spelling
        is the *same* directory and must not fork a second project.

        Skips on case-sensitive filesystems (Linux CI), where the variant is a
        genuinely different path and staying distinct is the correct behaviour.
        """
        proj = _write_pipeline_output(tmp_path, self._clusters(), [])
        variant = proj.with_name(proj.name.swapcase())
        if variant.name == proj.name or not (
            variant.exists() and os.path.samefile(proj, variant)
        ):
            pytest.skip("case-sensitive filesystem (or name has no case to swap)")

        p1 = import_project(db, proj)
        p2 = import_project(db, variant)
        assert p1.id == p2.id
        assert db.query(Project).count() == 1

    def test_legacy_noncanonical_row_is_matched_and_healed(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """A pre-existing row stored with a relative path is matched + healed."""
        proj = _write_pipeline_output(tmp_path, self._clusters(), [])
        out = proj / "bristlenose-output"
        legacy = Project(
            name="Legacy",
            slug="legacy",
            input_dir=os.path.relpath(proj, Path.cwd()),
            output_dir=os.path.relpath(out, Path.cwd()),
        )
        db.add(legacy)
        db.flush()
        legacy_id = legacy.id

        project = import_project(db, proj)  # absolute spelling
        assert project.id == legacy_id  # matched, not forked
        assert db.query(Project).count() == 1
        assert Path(project.input_dir) == proj.resolve()  # healed to canonical


class TestImportNameHealing:
    """A row created (at serve-startup import) before the pipeline wrote
    metadata.json freezes at the "Untitled" default; a later re-import, once
    metadata.json carries a real project_name, must heal it."""

    def test_untitled_row_heals_name_and_slug_on_reimport(
        self, db: Session, tmp_path: Path,
    ) -> None:
        # First import mimics the create-before-metadata case: name defaults.
        _write_pipeline_output(tmp_path, [], [], project_name="Untitled")
        first = import_project(db, tmp_path)
        assert first.name == "Untitled"

        # Pipeline has since written a real name into metadata.json.
        _write_pipeline_output(tmp_path, [], [], project_name="New Project ZZZ")
        healed = import_project(db, tmp_path)

        assert healed.id == first.id  # matched, not forked
        assert db.query(Project).count() == 1
        assert healed.name == "New Project ZZZ"
        assert healed.slug == "new-project-zzz"

    def test_reimport_does_not_clobber_an_intentional_name(
        self, db: Session, tmp_path: Path,
    ) -> None:
        # A real name set at create time must survive a differing metadata name
        # (the heal is scoped to the "Untitled" sentinel).
        _write_pipeline_output(tmp_path, [], [], project_name="Real Name")
        first = import_project(db, tmp_path)
        assert first.name == "Real Name"

        _write_pipeline_output(tmp_path, [], [], project_name="Different")
        again = import_project(db, tmp_path)

        assert again.id == first.id
        assert again.name == "Real Name"


class TestImportMissing:
    """Test import handles missing files gracefully."""

    def test_import_nonexistent_dir(self, db: Session, tmp_path: Path) -> None:
        """Import from an empty dir should create a minimal project — whose row
        carries the FUTURE output folder, not the interview folder, so the first
        run's import matches it instead of forking a second row."""
        empty = tmp_path / "empty"
        empty.mkdir()
        project = import_project(db, empty)
        assert project.name == "Untitled"
        assert project.imported_at is not None
        assert db.query(SessionModel).count() == 0
        assert db.query(Quote).count() == 0
        assert Path(project.input_dir).resolve() == empty.resolve()
        assert Path(project.output_dir).resolve() == (empty / "bristlenose-output").resolve()

    def test_import_only_metadata(self, db: Session, tmp_path: Path) -> None:
        """Import with only metadata.json should create named project."""
        out = tmp_path / "bristlenose-output"
        out.mkdir()
        intermediate = out / ".bristlenose" / "intermediate"
        intermediate.mkdir(parents=True)
        (intermediate / "metadata.json").write_text('{"project_name": "My Project"}', encoding="utf-8")

        project = import_project(db, tmp_path)
        assert project.name == "My Project"
        assert project.slug == "my-project"


class TestImportIncompleteOutput:
    """An output folder missing files it used to have is not a re-run that
    removed everything. Clearing the intermediate folder, a partial sync or a
    copied project must not delete the researcher's quotes and state."""

    @pytest.fixture()
    def project_dir(self, tmp_path: Path) -> Path:
        import shutil

        dest = tmp_path / "input"
        shutil.copytree(_FIXTURE_DIR, dest)
        return dest

    @staticmethod
    def _seed_state(db: Session, project_dir: Path) -> None:
        import_project(db, project_dir)
        quotes = db.query(Quote).order_by(Quote.id).all()
        assert len(quotes) >= 3
        db.add(QuoteState(quote_id=quotes[0].id, is_hidden=True))
        db.add(QuoteState(quote_id=quotes[1].id, is_starred=True))
        db.add(QuoteEdit(quote_id=quotes[2].id, edited_text="researcher fix"))
        db.commit()

    @staticmethod
    def _intermediate(project_dir: Path) -> Path:
        return project_dir / "bristlenose-output" / ".bristlenose" / "intermediate"

    def test_absent_cluster_and_theme_files_keep_quotes(
        self, db: Session, project_dir: Path,
    ) -> None:
        self._seed_state(db, project_dir)
        quotes_before = db.query(Quote).count()
        (self._intermediate(project_dir) / "screen_clusters.json").unlink()
        (self._intermediate(project_dir) / "theme_groups.json").unlink()

        import_project(db, project_dir)

        assert db.query(Quote).count() == quotes_before
        assert db.query(QuoteState).filter_by(is_hidden=True).count() == 1
        assert db.query(QuoteState).filter_by(is_starred=True).count() == 1
        assert db.query(QuoteEdit).count() == 1

    def test_one_absent_file_keeps_quotes(self, db: Session, project_dir: Path) -> None:
        self._seed_state(db, project_dir)
        quotes_before = db.query(Quote).count()
        (self._intermediate(project_dir) / "theme_groups.json").unlink()

        import_project(db, project_dir)

        assert db.query(Quote).count() == quotes_before
        assert db.query(QuoteState).filter_by(is_hidden=True).count() == 1

    def test_absent_quotes_and_transcripts_keep_sessions(
        self, db: Session, project_dir: Path,
    ) -> None:
        import shutil

        self._seed_state(db, project_dir)
        sessions_before = db.query(SessionModel).count()
        (self._intermediate(project_dir) / "screen_clusters.json").unlink()
        (self._intermediate(project_dir) / "theme_groups.json").unlink()
        out = project_dir / "bristlenose-output"
        for name in ("transcripts-raw", "transcripts-cooked", "raw_transcripts",
                     "cooked_transcripts"):
            if (out / name).exists():
                shutil.rmtree(out / name)

        import_project(db, project_dir)

        assert db.query(SessionModel).count() == sessions_before
        assert db.query(QuoteState).filter_by(is_starred=True).count() == 1
        assert db.query(QuoteEdit).count() == 1

    def test_present_but_empty_files_still_remove_quotes(
        self, db: Session, project_dir: Path,
    ) -> None:
        """Empty lists are the pipeline saying "no quotes" — that is honoured."""
        self._seed_state(db, project_dir)
        (self._intermediate(project_dir) / "screen_clusters.json").write_text("[]")
        (self._intermediate(project_dir) / "theme_groups.json").write_text("[]")

        import_project(db, project_dir)

        # Pinned quotes (starred, edited) survive by design; the rest go.
        assert db.query(Quote).count() == 2
        assert db.query(QuoteState).filter_by(is_hidden=True).count() == 0


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
        json.dumps({"project_name": project_name}), encoding="utf-8"
    )
    (intermediate / "screen_clusters.json").write_text(json.dumps(clusters), encoding="utf-8")
    (intermediate / "theme_groups.json").write_text(json.dumps(themes), encoding="utf-8")
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
    (raw / f"{sid}.txt").write_text(content, encoding="utf-8")


def _write_people_yaml(output_dir: Path, participants: dict) -> None:
    """Write a people.yaml file into the output directory."""
    import yaml

    data = {
        "generated_by": "bristlenose",
        "last_updated": "2026-02-23T10:00:00Z",
        "participants": participants,
    }
    (output_dir / "people.yaml").write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8"
    )


class TestImportPeopleYaml:
    """People.yaml names should populate Person rows on import."""

    def _make_project(self, tmp_path: Path) -> Path:
        """Create a minimal project with transcripts and people.yaml."""
        out = tmp_path / "bristlenose-output"
        out.mkdir()
        intermediate = out / ".bristlenose" / "intermediate"
        intermediate.mkdir(parents=True)
        (intermediate / "metadata.json").write_text('{"project_name": "Name Test"}', encoding="utf-8")
        (intermediate / "screen_clusters.json").write_text("[]", encoding="utf-8")
        (intermediate / "theme_groups.json").write_text("[]", encoding="utf-8")

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

        # m1: people.yaml names participants only. Its one ``m1`` entry stood
        # for every session's moderator, so it is not evidence about any one
        # of them (owner, 3 Oct 2026; route C) — the slot stays unidentified.
        m1_sp = [sp for sp in speakers if sp.speaker_code == "m1"][0]
        assert m1_sp.person_id is None

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
        assert m1_sp.person_id is None  # nothing names it (route C)


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
        (cooked / "s1.txt").write_text("# Transcript: s1\n", encoding="utf-8")
        raw = output / "transcripts-raw"
        raw.mkdir()
        (raw / "s1.txt").write_text("# Transcript: s1\n", encoding="utf-8")

        result = _find_transcripts_dir(tmp_path, output)
        assert result == cooked

    def test_finds_raw_in_output(self, tmp_path: Path) -> None:
        """Standard pipeline layout: transcripts-raw in output dir."""
        output = tmp_path / "output"
        output.mkdir()
        raw = output / "transcripts-raw"
        raw.mkdir()
        (raw / "s1.txt").write_text("# Transcript: s1\n", encoding="utf-8")

        result = _find_transcripts_dir(tmp_path, output)
        assert result == raw

    def test_falls_back_to_project_transcripts(self, tmp_path: Path) -> None:
        """Non-standard layout: transcripts/ in project dir (Plato case)."""
        output = tmp_path / "output"
        output.mkdir()
        transcripts = tmp_path / "transcripts"
        transcripts.mkdir()
        (transcripts / "s1.txt").write_text("# Transcript: s1\n", encoding="utf-8")

        result = _find_transcripts_dir(tmp_path, output)
        assert result == transcripts

    def test_falls_back_to_project_transcripts_raw(self, tmp_path: Path) -> None:
        """Input-dir layout: transcripts-raw/ in project dir."""
        output = tmp_path / "output"
        output.mkdir()
        raw = tmp_path / "transcripts-raw"
        raw.mkdir()
        (raw / "s1.txt").write_text("# Transcript: s1\n", encoding="utf-8")

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
        (transcripts / "s1.txt").write_text("# Transcript: s1\n", encoding="utf-8")

        result = _find_transcripts_dir(tmp_path, output)
        assert result == transcripts


# ---------------------------------------------------------------------------
# Word enrichment from intermediate JSON
# ---------------------------------------------------------------------------


def _write_transcript_and_words(
    tmp_path: Path,
    *,
    words: list[dict] | None = None,
) -> Path:
    """Write a minimal project with transcript + optional word timing data.

    Returns the project input directory.
    """
    out = tmp_path / "bristlenose-output"
    out.mkdir(exist_ok=True)
    intermediate = out / ".bristlenose" / "intermediate"
    intermediate.mkdir(parents=True, exist_ok=True)

    (intermediate / "metadata.json").write_text('{"project_name": "Word Test"}', encoding="utf-8")
    (intermediate / "screen_clusters.json").write_text("[]", encoding="utf-8")
    (intermediate / "theme_groups.json").write_text("[]", encoding="utf-8")

    # Write transcript txt (the regex-based importer reads this)
    transcripts = out / "transcripts-raw"
    transcripts.mkdir(exist_ok=True)
    (transcripts / "s1.txt").write_text(
        "# Transcript: s1\n"
        "# Duration: 00:00:30\n"
        "\n"
        "[00:02] [m1] Hello, how are you today?\n"
        "[00:10] [p1] I'm doing well, thanks for asking.\n", encoding="utf-8"
    )

    # Write session_segments.json (the word enrichment reads this)
    seg_words_0 = words if words is not None else []
    seg_words_1 = (
        [
            {"text": "I'm", "start_time": 10.0, "end_time": 10.3, "confidence": 0.9},
            {"text": "doing", "start_time": 10.3, "end_time": 10.6, "confidence": 0.95},
            {"text": "well,", "start_time": 10.6, "end_time": 10.9, "confidence": 0.92},
            {"text": "thanks", "start_time": 11.0, "end_time": 11.3, "confidence": 0.9},
            {"text": "for", "start_time": 11.3, "end_time": 11.4, "confidence": 0.9},
            {"text": "asking.", "start_time": 11.4, "end_time": 11.8, "confidence": 0.9},
        ]
        if words  # only include second seg words when first seg has words too
        else []
    )
    (intermediate / "session_segments.json").write_text(
        json.dumps({
            "s1": [
                {
                    "start_time": 2.0,
                    "end_time": 10.0,
                    "text": "Hello, how are you today?",
                    "speaker_label": "",
                    "speaker_role": "unknown",
                    "speaker_code": "m1",
                    "words": seg_words_0,
                    "source": "mlx-whisper",
                    "segment_index": 0,
                },
                {
                    "start_time": 10.0,
                    "end_time": 20.0,
                    "text": "I'm doing well, thanks for asking.",
                    "speaker_label": "",
                    "speaker_role": "unknown",
                    "speaker_code": "p1",
                    "words": seg_words_1,
                    "source": "mlx-whisper",
                    "segment_index": 1,
                },
            ],
        }), encoding="utf-8"
    )

    return tmp_path


_HELLO_WORDS = [
    {"text": "Hello,", "start_time": 2.0, "end_time": 2.5, "confidence": 0.9},
    {"text": "how", "start_time": 2.5, "end_time": 2.8, "confidence": 0.95},
    {"text": "are", "start_time": 2.8, "end_time": 3.0, "confidence": 0.95},
    {"text": "you", "start_time": 3.0, "end_time": 3.2, "confidence": 0.95},
    {"text": "today?", "start_time": 3.2, "end_time": 3.7, "confidence": 0.95},
]


class TestWordEnrichment:
    """Test that word-level timing from intermediate JSON populates words_json."""

    def test_words_populated_when_available(self, db: Session, tmp_path: Path) -> None:
        """Segments with word data in session_segments.json get words_json."""
        project_dir = _write_transcript_and_words(
            tmp_path,
            words=_HELLO_WORDS,
        )
        import_project(db, project_dir)

        segs = (
            db.query(TranscriptSegment)
            .order_by(TranscriptSegment.start_time)
            .all()
        )
        assert len(segs) == 2

        # First segment (m1) has word data
        assert segs[0].words_json is not None
        parsed = json.loads(segs[0].words_json)
        assert len(parsed) == 5
        assert parsed[0]["t"] == "Hello,"
        assert parsed[0]["s"] == 2.0
        assert parsed[0]["e"] == 2.5

        # Second segment (p1) also has word data
        assert segs[1].words_json is not None
        parsed1 = json.loads(segs[1].words_json)
        assert len(parsed1) == 6
        assert parsed1[0]["t"] == "I'm"

    def test_last_segment_ends_at_the_header_duration(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """The final segment has no successor; `# Duration:` is its end.

        A flat start + 10 s cut the playback glow off 28 s early on an
        interview whose last answer ran to the end of the recording.
        """
        project_dir = _write_transcript_and_words(tmp_path, words=[])
        import_project(db, project_dir)

        last = (
            db.query(TranscriptSegment)
            .order_by(TranscriptSegment.start_time.desc())
            .first()
        )
        assert last is not None
        assert last.start_time == 10.0
        assert last.end_time == 30.0  # "# Duration: 00:00:30"

    def test_partial_words_are_refused(self, db: Session, tmp_path: Path) -> None:
        """Words that do not spell the segment's text are not attached to it.

        The transcript page renders word spans *in place of* the text, so two
        words for a five-word line would display as a two-word line.
        """
        project_dir = _write_transcript_and_words(tmp_path, words=_HELLO_WORDS[:2])
        import_project(db, project_dir)

        first = (
            db.query(TranscriptSegment)
            .order_by(TranscriptSegment.start_time)
            .first()
        )
        assert first is not None
        assert first.words_json is None

    def test_merged_segments_get_their_own_words(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """The .txt is post-merge; session_segments.json is pre-merge.

        Stage 6 merges consecutive same-speaker segments, so the intermediate
        holds more segments than the transcript, all with segment_index -1.
        Matching by position gave the paragraph at 0:20 the words spoken at
        0:05 — the shape of an 18-minute interview whose transcript page showed
        only its first two and a half minutes (27 Sep 2026).
        """
        out = tmp_path / "bristlenose-output"
        intermediate = out / ".bristlenose" / "intermediate"
        intermediate.mkdir(parents=True)
        (intermediate / "metadata.json").write_text('{"project_name": "Merge Test"}', encoding="utf-8")
        (intermediate / "screen_clusters.json").write_text("[]", encoding="utf-8")
        (intermediate / "theme_groups.json").write_text("[]", encoding="utf-8")
        (out / "transcripts-raw").mkdir()
        (out / "transcripts-raw" / "s1.txt").write_text(
            "# Transcript: s1\n"
            "# Duration: 00:00:30\n"
            "\n"
            "[00:00] [m1] (Speaker A) Tell me about it. What happened next?\n"
            "[00:20] [p1] (Speaker B) We went to the shop.\n", encoding="utf-8"
        )

        def raw(start: float, text: str) -> dict:
            toks = text.split()
            return {
                "start_time": start,
                "end_time": start + len(toks) * 0.5,
                "text": text,
                "speaker_label": None,
                "speaker_role": "unknown",
                "speaker_code": "",
                "source": "mlx-whisper",
                "segment_index": -1,
                "words": [
                    {"text": t, "start_time": start + i * 0.5,
                     "end_time": start + i * 0.5 + 0.4, "confidence": 0.9}
                    for i, t in enumerate(toks)
                ],
            }

        (intermediate / "session_segments.json").write_text(json.dumps({
            "s1": [
                raw(0.4, "Tell me about it."),
                raw(5.0, "What happened next?"),
                raw(20.3, "We went to the shop."),
            ],
        }), encoding="utf-8")
        import_project(db, tmp_path)

        segs = (
            db.query(TranscriptSegment)
            .order_by(TranscriptSegment.start_time)
            .all()
        )
        assert [s.start_time for s in segs] == [0.0, 20.0]
        first = json.loads(segs[0].words_json or "[]")
        second = json.loads(segs[1].words_json or "[]")
        assert [w["t"] for w in first] == (
            "Tell me about it. What happened next?".split()
        )
        assert [w["t"] for w in second] == "We went to the shop.".split()
        assert second[0]["s"] == 20.3

    @staticmethod
    def _import_one_paragraph(
        db: Session, tmp_path: Path, line: str, raw: list[tuple[float, list[str]]],
    ) -> TranscriptSegment:
        """Import a one-paragraph transcript whose raw segments carry ``raw``."""
        out = tmp_path / "bristlenose-output"
        intermediate = out / ".bristlenose" / "intermediate"
        intermediate.mkdir(parents=True)
        (intermediate / "metadata.json").write_text('{"project_name": "CJK Test"}', encoding="utf-8")
        (intermediate / "screen_clusters.json").write_text("[]", encoding="utf-8")
        (intermediate / "theme_groups.json").write_text("[]", encoding="utf-8")
        (out / "transcripts-raw").mkdir()
        (out / "transcripts-raw" / "s1.txt").write_text(
            "# Transcript: s1\n# Duration: 00:00:30\n\n" + line + "\n",
            encoding="utf-8",
        )
        segments = [
            {
                "start_time": start,
                "end_time": start + len(toks) * 0.4,
                "text": "".join(toks),
                "speaker_label": None,
                "speaker_role": "unknown",
                "speaker_code": "",
                "source": "mlx-whisper",
                "segment_index": -1,
                "words": [
                    {"text": t, "start_time": start + i * 0.4,
                     "end_time": start + i * 0.4 + 0.3, "confidence": 0.9}
                    for i, t in enumerate(toks)
                ],
            }
            for start, toks in raw
        ]
        (intermediate / "session_segments.json").write_text(
            json.dumps({"s1": segments}, ensure_ascii=False), encoding="utf-8",
        )
        import_project(db, tmp_path)
        return db.query(TranscriptSegment).one()

    def test_japanese_words_are_attached(self, db: Session, tmp_path: Path) -> None:
        """Japanese has no spaces, so Whisper's word boundaries are not the text's.

        ``ありがとう`` + ``ございます。`` is two ``\\w+`` runs against the
        transcript's one; the token comparison refused every ja paragraph and
        the transcript page and clip subtitles fell back to an even spread.
        """
        first = ["ありがとう", "ございます。"]
        second = ["今日", "は", "よろしく", "お願い", "します。"]
        seg = self._import_one_paragraph(
            db, tmp_path,
            "[00:01] [p1] (Yuki) ありがとうございます。今日はよろしくお願いします。",
            [(1.2, first), (3.0, second)],
        )
        words = json.loads(seg.words_json or "[]")
        assert [w["t"] for w in words] == first + second
        assert words[0]["s"] == 1.2

    def test_traditional_chinese_words_are_attached(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """Same shape in Traditional Chinese, with full-width punctuation."""
        toks = ["我們", "上週", "去了", "那家", "店，", "覺得", "服務", "很好。"]
        seg = self._import_one_paragraph(
            db, tmp_path,
            "[00:04] [p1] (美玲) 我們上週去了那家店，覺得服務很好。",
            [(4.5, toks)],
        )
        words = json.loads(seg.words_json or "[]")
        assert [w["t"] for w in words] == toks
        assert words[0]["s"] == 4.5

    def test_cjk_words_from_another_paragraph_are_refused(self) -> None:
        """Comparing characters must still tell two paragraphs apart."""
        words = [{"text": t} for t in ["我們", "上週", "去了", "那家", "店。"]]
        assert _words_read_as(words, "(美玲) 我們上週去了那家店。")
        assert not _words_read_as(words, "(美玲) 覺得服務很好，價格也合理。")
        assert not _words_read_as(words[:2], "(美玲) 我們上週去了那家店。")

    def test_words_null_when_no_intermediate(self, db: Session) -> None:
        """Smoke-test fixture (VTT source, no session_segments.json with words)."""
        import_project(db, _FIXTURE_DIR)
        segs = db.query(TranscriptSegment).all()
        for seg in segs:
            assert seg.words_json is None

    def test_words_null_when_empty_words_array(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """Segments with empty words arrays get no words_json."""
        project_dir = _write_transcript_and_words(tmp_path, words=[])
        import_project(db, project_dir)

        segs = db.query(TranscriptSegment).all()
        for seg in segs:
            assert seg.words_json is None

    def test_compact_json_format(self, db: Session, tmp_path: Path) -> None:
        """words_json uses compact keys (t, s, e) and no whitespace."""
        project_dir = _write_transcript_and_words(
            tmp_path,
            words=_HELLO_WORDS,
        )
        import_project(db, project_dir)

        seg = (
            db.query(TranscriptSegment)
            .order_by(TranscriptSegment.start_time)
            .first()
        )
        assert seg is not None
        assert seg.words_json is not None
        # No whitespace (compact separators)
        assert " " not in seg.words_json
        # Uses short keys
        assert '"t":' in seg.words_json
        assert '"s":' in seg.words_json
        assert '"e":' in seg.words_json
        # Does NOT include confidence
        assert "confidence" not in seg.words_json


# ---------------------------------------------------------------------------
# Sentiment auto-import and auto-tag
# ---------------------------------------------------------------------------


class TestSentimentAutoImport:
    """Sentiment framework is auto-imported and quotes are auto-tagged."""

    def test_auto_imports_sentiment_framework(self, db: Session) -> None:
        """Import creates CodebookGroup + TagDefinitions for sentiment."""
        import_project(db, _FIXTURE_DIR)

        group = (
            db.query(CodebookGroup)
            .filter(CodebookGroup.framework_id == "sentiment")
            .first()
        )
        assert group is not None
        assert group.name == "Sentiment"
        assert group.colour_set == "sentiment"

        tags = db.query(TagDefinition).filter_by(codebook_group_id=group.id).all()
        tag_names = {t.name for t in tags}
        assert tag_names == {
            "frustration", "confusion", "doubt", "surprise",
            "satisfaction", "delight", "confidence",
        }

    def test_auto_imports_project_codebook_group(self, db: Session) -> None:
        """Sentiment framework is linked to the project with sort_order=0."""
        project = import_project(db, _FIXTURE_DIR)

        pcg = (
            db.query(ProjectCodebookGroup)
            .join(CodebookGroup)
            .filter(
                ProjectCodebookGroup.project_id == project.id,
                CodebookGroup.framework_id == "sentiment",
            )
            .first()
        )
        assert pcg is not None
        assert pcg.sort_order == 0

    def test_auto_tags_quotes_from_sentiment_field(self, db: Session) -> None:
        """Quotes with a sentiment field get QuoteTag rows for sentiment tags."""
        import_project(db, _FIXTURE_DIR)

        # The smoke-test fixture has quotes with sentiments (e.g. confusion, delight)
        quotes_with_sentiment = (
            db.query(Quote)
            .filter(Quote.sentiment.isnot(None), Quote.sentiment != "")
            .all()
        )
        assert len(quotes_with_sentiment) > 0

        for quote in quotes_with_sentiment:
            # Each should have a QuoteTag linking to the sentiment TagDefinition
            tag = (
                db.query(QuoteTag)
                .join(TagDefinition)
                .join(CodebookGroup)
                .filter(
                    QuoteTag.quote_id == quote.id,
                    CodebookGroup.framework_id == "sentiment",
                    TagDefinition.name == quote.sentiment,
                )
                .first()
            )
            assert tag is not None, (
                f"Quote {quote.id} has sentiment={quote.sentiment!r} "
                f"but no matching QuoteTag"
            )

    def test_null_sentiment_gets_no_tag(self, db: Session, tmp_path: Path) -> None:
        """Quotes with no sentiment field do not get sentiment tags."""
        clusters = [
            {
                "screen_label": "Home",
                "description": "",
                "display_order": 1,
                "quotes": [
                    _make_quote("s1", "p1", 10.0, "Just navigating", sentiment=""),
                ],
            },
        ]
        _write_pipeline_output(tmp_path, clusters, [])
        import_project(db, tmp_path)

        quote = db.query(Quote).first()
        assert quote is not None

        sentiment_tags = (
            db.query(QuoteTag)
            .join(TagDefinition)
            .join(CodebookGroup)
            .filter(
                QuoteTag.quote_id == quote.id,
                CodebookGroup.framework_id == "sentiment",
            )
            .all()
        )
        assert len(sentiment_tags) == 0

    def test_idempotent_reimport(self, db: Session) -> None:
        """Re-importing does not duplicate sentiment tags or framework."""
        import_project(db, _FIXTURE_DIR)
        import_project(db, _FIXTURE_DIR)

        # Only one sentiment CodebookGroup
        groups = (
            db.query(CodebookGroup)
            .filter(CodebookGroup.framework_id == "sentiment")
            .all()
        )
        assert len(groups) == 1

        # Only one ProjectCodebookGroup link per group
        pcgs = (
            db.query(ProjectCodebookGroup)
            .join(CodebookGroup)
            .filter(CodebookGroup.framework_id == "sentiment")
            .all()
        )
        assert len(pcgs) == 1

        # QuoteTags not duplicated
        quotes_with_sentiment = (
            db.query(Quote)
            .filter(Quote.sentiment.isnot(None), Quote.sentiment != "")
            .all()
        )
        for quote in quotes_with_sentiment:
            tags = (
                db.query(QuoteTag)
                .join(TagDefinition)
                .join(CodebookGroup)
                .filter(
                    QuoteTag.quote_id == quote.id,
                    CodebookGroup.framework_id == "sentiment",
                )
                .all()
            )
            assert len(tags) == 1, (
                f"Quote {quote.id} has {len(tags)} sentiment tags, expected 1"
            )


class TestTranscriptLanguageHeader:
    """The detected language reaches the session row (it used to stop at the file)."""

    def test_header_language_is_parsed(self, tmp_path: Path) -> None:
        from bristlenose.server.importer import _parse_transcript_headers

        (tmp_path / "s1.txt").write_text(
            "# Transcript: s1\n# Source: a.mp4\n# Language: ja (detected)\n# Duration: 00:10\n",
            encoding="utf-8",
        )
        (tmp_path / "s2.txt").write_text(
            "# Transcript: s2\n# Source: b.mp4\n# Duration: 00:10\n", encoding="utf-8",
        )
        meta = _parse_transcript_headers(tmp_path)
        assert meta["s1"]["language"] == "ja"
        assert meta["s2"]["language"] is None

    def test_language_lands_on_the_session_row(self, db: Session) -> None:
        from unittest.mock import patch

        import bristlenose.server.importer as importer

        real = importer._parse_transcript_headers

        def with_language(transcripts_dir):  # type: ignore[no-untyped-def]
            meta = real(transcripts_dir)
            for entry in meta.values():
                entry["language"] = "ja"
            return meta

        with patch.object(importer, "_parse_transcript_headers", with_language):
            import_project(db, _FIXTURE_DIR)
        assert db.query(SessionModel).one().language == "ja"


class TestRedactedSourceHeader:
    """A cooked transcript says ``# Source: [REDACTED]``; the importer must
    still find the recording, and takes the real name from the raw sibling."""

    def _write(self, directory: Path, sid: str, source: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{sid}.txt").write_text(
            f"# Transcript: {sid}\n# Source: {source}\n# Duration: 00:10\n", encoding="utf-8",
        )

    def test_redacted_source_resolves_to_the_raw_transcripts_source(self, tmp_path: Path) -> None:
        from bristlenose.server.importer import (
            _parse_transcript_headers,
            _resolve_redacted_sources,
        )

        self._write(tmp_path / "transcripts-cooked", "s1", "[REDACTED]")
        self._write(tmp_path / "transcripts-raw", "s1", "Interview with Sarah Jones.mp4")
        meta = _parse_transcript_headers(tmp_path / "transcripts-cooked")
        assert meta["s1"]["source"] == "[REDACTED]"

        _resolve_redacted_sources(meta, tmp_path / "transcripts-raw")
        assert meta["s1"]["source"] == "Interview with Sarah Jones.mp4"

    def test_a_real_source_is_left_alone(self, tmp_path: Path) -> None:
        from bristlenose.server.importer import (
            _parse_transcript_headers,
            _resolve_redacted_sources,
        )

        self._write(tmp_path / "transcripts-raw", "s1", "a.mp4")
        meta = _parse_transcript_headers(tmp_path / "transcripts-raw")
        _resolve_redacted_sources(meta, tmp_path / "does-not-exist")
        assert meta["s1"]["source"] == "a.mp4"

    def test_no_raw_sibling_means_no_source_file(self, tmp_path: Path) -> None:
        """The marker never reaches the database as a filename."""
        from bristlenose.server.importer import (
            _parse_transcript_headers,
            _resolve_redacted_sources,
        )

        self._write(tmp_path / "transcripts-cooked", "s1", "[REDACTED]")
        meta = _parse_transcript_headers(tmp_path / "transcripts-cooked")
        _resolve_redacted_sources(meta, tmp_path / "transcripts-raw")
        assert meta["s1"]["source"] == ""


# ---------------------------------------------------------------------------
# Two quotes from one speaker with one start (R86)
# ---------------------------------------------------------------------------


#: Past difflib's 200-character autojunk line. With autojunk on, the re-worded form below
#: scores 0.19 against this (most letters are "popular" and cannot start a match); with it
#: off, 0.81. Measured 21 Oct 2026.
LONG = ("So I went to the orders page and I looked for the button that would let me go back, and it "
        "was not where I expected it to be, and I scrolled the whole page twice before I found the "
        "small link at the bottom that took me there, which honestly I would never have found on "
        "my own.")
LONG_REWORDED = ("So I navigated to the orders page and I searched for the control that would let me "
                 "go backwards and it was not where I assumed it to be, and I dragged the whole page "
                 "repeatedly before I found the tiny link at the foot that took me there, which "
                 "frankly I would not have found on my initiative.")


def _same_start_pair() -> list[dict]:
    """Stage 9 cuts two quotes from one paragraph: one start, two ends, two texts."""
    first = _make_quote("s1", "p1", 53.0, "The first half of the paragraph")
    second = _make_quote("s1", "p1", 53.0, "And the second half, cut apart")
    second["end_timecode"] = 71.0
    return [first, second]


class TestSameStartQuotes:
    """A quote's identity is its start *and* its rank within that second."""

    @staticmethod
    def _clusters(quotes: list[dict]) -> list[dict]:
        return [{"screen_label": "Checkout", "description": "", "display_order": 1,
                 "quotes": quotes}]

    def test_two_quotes_with_one_start_are_two_rows(self, db: Session, tmp_path: Path) -> None:
        proj = _write_pipeline_output(tmp_path, self._clusters(_same_start_pair()), [])
        project = import_project(db, proj)
        rows = (db.query(Quote).filter_by(project_id=project.id)
                .order_by(Quote.ordinal).all())
        assert [(r.ordinal, r.text) for r in rows] == [
            (0, "The first half of the paragraph"),
            (1, "And the second half, cut apart"),
        ]

    def test_same_start_pair_keeps_each_star_across_reimport(
        self, db: Session, tmp_path: Path,
    ) -> None:
        proj = _write_pipeline_output(tmp_path, self._clusters(_same_start_pair()), [])
        project = import_project(db, proj)
        rows = db.query(Quote).filter_by(project_id=project.id).order_by(Quote.ordinal).all()
        assert len(rows) == 2
        ids = [r.id for r in rows]
        db.add(QuoteState(quote_id=ids[1], is_starred=True))
        db.add(QuoteState(quote_id=ids[0], is_hidden=True))
        db.commit()

        import_project(db, proj)

        again = db.query(Quote).filter_by(project_id=project.id).order_by(Quote.ordinal).all()
        assert [r.id for r in again] == ids
        starred = db.query(QuoteState).filter_by(quote_id=ids[1]).one()
        hidden = db.query(QuoteState).filter_by(quote_id=ids[0]).one()
        assert starred.is_starred is True and starred.is_hidden is False
        assert hidden.is_hidden is True and hidden.is_starred is False

    def test_progressive_and_final_paths_agree_on_ordinals(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """The quotes a run hands over session by session keep their rows when the
        whole project lands at the end: both paths rank a same-start pair alike."""
        from bristlenose.server.importer import import_session_quotes

        opener = _make_quote("s1", "p1", 10.0, "An opener")
        proj = _write_pipeline_output(tmp_path, self._clusters([opener]), [])
        project = import_project(db, proj)
        intermediate = tmp_path / "bristlenose-output" / ".bristlenose" / "intermediate"
        # Progressive: the session's quotes, pair included, in the order stage 9 wrote them
        # (second before first, so the rank is not the file order).
        pair = _same_start_pair()
        (intermediate / "extracted_quotes.json").write_text(
            json.dumps([opener, pair[1], pair[0]]), encoding="utf-8")
        _, counts = import_session_quotes(db, proj, {"s1"})
        assert counts == {"s1": 3}
        progressive = {
            (r.start_timecode, r.ordinal): (r.id, r.text)
            for r in db.query(Quote).filter_by(project_id=project.id).all()
        }
        assert len(progressive) == 3

        # Final: the same quotes, now spread over a section and a theme.
        (intermediate / "screen_clusters.json").write_text(
            json.dumps(self._clusters([opener, pair[0]])), encoding="utf-8")
        (intermediate / "theme_groups.json").write_text(
            json.dumps([{"theme_label": "Cuts", "description": "", "display_order": 1,
                         "quotes": [pair[1]]}]), encoding="utf-8")
        import_project(db, proj)
        final = {
            (r.start_timecode, r.ordinal): (r.id, r.text)
            for r in db.query(Quote).filter_by(project_id=project.id).all()
        }
        assert final == progressive

    def test_prune_keeps_a_second_quote_card(self, db: Session, tmp_path: Path) -> None:
        """A Screens card keyed ``q-p1-53-1`` names a live quote and stays; one that names
        no quote goes."""
        from bristlenose.server.importer import _prune_arrangements
        from bristlenose.server.models import ScreenArrangement

        proj = _write_pipeline_output(tmp_path, self._clusters(_same_start_pair()), [])
        project = import_project(db, proj)
        cards = {"q-p1-53": {"kind": "edge", "edge": "left", "i": 0},
                 "q-p1-53-1": {"kind": "edge", "edge": "left", "i": 1},
                 "q-p1-99": {"kind": "edge", "edge": "left", "i": 2}}
        db.add(ScreenArrangement(project_id=project.id, screen_key="url:/checkout",
                                 session_id="s1", cards=json.dumps(cards)))
        db.commit()
        _prune_arrangements(db, project)
        db.commit()
        row = db.query(ScreenArrangement).filter_by(project_id=project.id).one()
        assert set(json.loads(row.cards)) == {"q-p1-53", "q-p1-53-1"}

    @staticmethod
    def _rewrite(tmp_path: Path, quotes: list[dict]) -> None:
        intermediate = tmp_path / "bristlenose-output" / ".bristlenose" / "intermediate"
        (intermediate / "screen_clusters.json").write_text(
            json.dumps([{"screen_label": "Checkout", "description": "", "display_order": 1,
                         "quotes": quotes}]), encoding="utf-8")

    @staticmethod
    def _by_text(db: Session, project_id: int) -> dict[str, tuple[int, int, bool, bool]]:
        """text → (row id, ordinal, starred, hidden)."""
        states = {s.quote_id: (s.is_starred, s.is_hidden) for s in db.query(QuoteState).all()}
        return {
            r.text: (r.id, r.ordinal, *states.get(r.id, (False, False)))
            for r in db.query(Quote).filter_by(project_id=project_id).all()
        }

    def test_a_rerun_that_reorders_a_pair_keeps_each_star_on_its_words(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """The ordinal is the row's, not the batch's: a re-run whose ends sort the pair the
        other way round leaves every star and hide on the words it was put on (review S1)."""
        first, second = _same_start_pair()
        proj = _write_pipeline_output(tmp_path, self._clusters([first, second]), [])
        project = import_project(db, proj)
        before = self._by_text(db, project.id)
        db.add(QuoteState(quote_id=before[second["text"]][0], is_starred=True))
        db.add(QuoteState(quote_id=before[first["text"]][0], is_hidden=True))
        db.commit()

        first["end_timecode"] = 80.0  # the model now ends the first later than the second
        self._rewrite(tmp_path, [first, second])
        import_project(db, proj)

        after = self._by_text(db, project.id)
        assert after[second["text"]] == (before[second["text"]][0], 1, True, False)
        assert after[first["text"]] == (before[first["text"]][0], 0, False, True)

    def test_a_rerun_that_drops_the_first_of_a_pair_keeps_the_second_on_its_row(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """The second quote stays on its own row and ordinal, with its star and without the
        first's hide; the first goes as any stale quote does (review S2)."""
        first, second = _same_start_pair()
        proj = _write_pipeline_output(tmp_path, self._clusters([first, second]), [])
        project = import_project(db, proj)
        before = self._by_text(db, project.id)
        db.add(QuoteState(quote_id=before[second["text"]][0], is_starred=True))
        db.add(QuoteState(quote_id=before[first["text"]][0], is_hidden=True))
        db.commit()

        self._rewrite(tmp_path, [second])
        import_project(db, proj)

        assert db.query(Quote).filter_by(project_id=project.id).count() == 1
        after = self._by_text(db, project.id)
        assert after == {second["text"]: (before[second["text"]][0], 1, True, False)}

    def test_a_lone_quote_reworded_keeps_its_row(self, db: Session, tmp_path: Path) -> None:
        """One quote at a start, re-emitted in other words: the same row, star and all
        (Freeze's promise; the content rule applies only where a second holds a pair)."""
        lone = _make_quote("s1", "p1", 10.0, "Something said once")
        proj = _write_pipeline_output(tmp_path, self._clusters([lone]), [])
        project = import_project(db, proj)
        [(row_id, _, _, _)] = self._by_text(db, project.id).values()
        db.add(QuoteState(quote_id=row_id, is_starred=True))
        db.commit()
        reworded = _make_quote("s1", "p1", 10.0, "Entirely different wording from the model")
        self._rewrite(tmp_path, [reworded])
        import_project(db, proj)
        assert self._by_text(db, project.id) == {reworded["text"]: (row_id, 0, True, False)}

    def test_a_new_quote_in_the_second_never_takes_a_stale_rows_ordinal(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """The first is dropped and a third quote arrives in the same second: it takes
        ordinal 2, not the dropped row's 0, which still exists until the stale sweep."""
        first, second = _same_start_pair()
        proj = _write_pipeline_output(tmp_path, self._clusters([first, second]), [])
        project = import_project(db, proj)
        before = self._by_text(db, project.id)
        db.add(QuoteState(quote_id=before[second["text"]][0], is_starred=True))
        db.commit()

        third = _make_quote("s1", "p1", 53.0, "A third thing, said in the same breath")
        third["end_timecode"] = 90.0
        self._rewrite(tmp_path, [second, third])
        import_project(db, proj)

        after = self._by_text(db, project.id)
        assert after == {
            second["text"]: (before[second["text"]][0], 1, True, False),
            third["text"]: (after[third["text"]][0], 2, False, False),
        }

    def test_an_upgraded_projects_starred_row_keeps_its_words(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """Before R86 the pair was one row holding the second's words, and the researcher
        starred those words. The first re-analysis after upgrading gives the first half a
        new row; the starred row keeps the words it showed (review finding 2)."""
        first, second = _same_start_pair()
        proj = _write_pipeline_output(tmp_path, self._clusters([second]), [])
        project = import_project(db, proj)
        [(row_id, ordinal, _, _)] = self._by_text(db, project.id).values()
        assert ordinal == 0
        db.add(QuoteState(quote_id=row_id, is_starred=True))
        db.commit()

        self._rewrite(tmp_path, [first, second])
        import_project(db, proj)

        after = self._by_text(db, project.id)
        assert after[second["text"]] == (row_id, 0, True, False)
        assert after[first["text"]][1:] == (1, False, False)

    def test_a_reworded_quote_under_researcher_state_is_said(
        self, db: Session, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A re-run that changes the words of a starred quote is said per quote at INFO and
        totalled once at WARNING; the same change on an untouched quote is not."""
        import logging

        first, second = _same_start_pair()
        proj = _write_pipeline_output(tmp_path, self._clusters([first, second]), [])
        project = import_project(db, proj)
        before = self._by_text(db, project.id)
        db.add(QuoteState(quote_id=before[second["text"]][0], is_starred=True))
        db.commit()

        first["verbatim_excerpt"] = "the first half, reworded"
        second["verbatim_excerpt"] = "and the second half, reworded"
        self._rewrite(tmp_path, [first, second])
        with caplog.at_level(logging.INFO, logger="bristlenose.server.importer"):
            import_project(db, proj)
        said = [r for r in caplog.records if "reworded by this run" in r.getMessage()]
        assert [r.levelno for r in said] == [logging.INFO, logging.WARNING]
        assert f"row {before[second['text']][0]}" in said[0].getMessage()
        assert said[1].getMessage().startswith("1 curated quote reworded")
        assert all("second half" not in r.getMessage() for r in said)  # words stay out

    def test_a_pair_with_one_long_reworded_quote_keeps_each_star(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """A long quote (past difflib's 200-character autojunk line) re-worded on a re-run is
        still its row: each star stays on its own words (review, blocker 1)."""
        first, second = _same_start_pair()
        second["text"] = second["verbatim_excerpt"] = LONG
        proj = _write_pipeline_output(tmp_path, self._clusters([first, second]), [])
        project = import_project(db, proj)
        before = self._by_text(db, project.id)
        db.add(QuoteState(quote_id=before[second["text"]][0], is_starred=True))
        db.add(QuoteState(quote_id=before[first["text"]][0], is_hidden=True))
        db.commit()

        reworded = LONG_REWORDED
        second["text"] = second["verbatim_excerpt"] = reworded
        self._rewrite(tmp_path, [first, second])
        import_project(db, proj)

        after = self._by_text(db, project.id)
        assert len(after) == 2
        assert after[reworded] == (before[LONG][0], 1, True, False)
        assert after[first["text"]] == (before[first["text"]][0], 0, False, True)

    def test_a_quote_unlike_its_neighbour_is_new_not_a_rewording(
        self, db: Session, tmp_path: Path,
    ) -> None:
        """Below the closeness line the quote is new: its own row and ordinal, and the row
        it did not match goes as stale (it carried no researcher state)."""
        first, second = _same_start_pair()
        proj = _write_pipeline_output(tmp_path, self._clusters([first, second]), [])
        project = import_project(db, proj)
        before = self._by_text(db, project.id)
        db.add(QuoteState(quote_id=before[first["text"]][0], is_starred=True))
        db.commit()

        other = _make_quote("s1", "p1", 53.0, "Completely unrelated words about the checkout")
        other["end_timecode"] = 71.0
        self._rewrite(tmp_path, [first, other])
        import_project(db, proj)

        after = self._by_text(db, project.id)
        assert after[first["text"]] == (before[first["text"]][0], 0, True, False)
        assert after[other["text"]][1:] == (2, False, False)
        assert len(after) == 2 and second["text"] not in after

    def test_two_quotes_sharing_an_excerpt_but_not_text_are_said(
        self, db: Session, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """One key is one quote: two incoming quotes with the same excerpt, start and end but
        different text import as one row, and the import says so."""
        import logging

        first, second = _same_start_pair()
        second["end_timecode"] = first["end_timecode"]
        second["verbatim_excerpt"] = first["verbatim_excerpt"]
        proj = _write_pipeline_output(tmp_path, self._clusters([first, second]), [])
        with caplog.at_level(logging.WARNING, logger="bristlenose.server.importer"):
            project = import_project(db, proj)
        assert db.query(Quote).filter_by(project_id=project.id).count() == 1
        assert any("share one excerpt" in r.getMessage() for r in caplog.records)


    def test_a_quote_without_an_ordinal_is_refused(self, db: Session, tmp_path: Path) -> None:
        """A caller that skips the pre-pass fails loudly rather than re-creating R86."""
        from datetime import datetime, timezone

        from bristlenose.server.importer import _get_or_create_quote

        proj = _write_pipeline_output(tmp_path, self._clusters([]), [])
        project = import_project(db, proj)
        with pytest.raises(KeyError, match="ordinal"):
            _get_or_create_quote(db, project, _make_quote("s1", "p1", 1.0, "no pre-pass"),
                                 datetime.now(timezone.utc))

    def test_a_third_way_in_is_refused(self, db: Session, tmp_path: Path) -> None:
        """The stable key is unique: a duplicate row cannot be written past the importer."""
        from sqlalchemy.exc import IntegrityError

        proj = _write_pipeline_output(tmp_path, self._clusters(_same_start_pair()), [])
        project = import_project(db, proj)
        db.add(Quote(project_id=project.id, session_id="s1", participant_id="p1",
                     start_timecode=53.0, end_timecode=60.0, text="a third", ordinal=1,
                     quote_type="screen_specific"))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
