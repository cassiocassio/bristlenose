"""Tests for the full domain schema in server/models.py.

Verifies all tables create, basic CRUD round-trips, unique constraints,
foreign key relationships, and the assigned_by/created_by patterns.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bristlenose.server.db import create_session_factory, get_engine, init_db
from bristlenose.server.models import (
    ClusterQuote,
    CodebookGroup,
    DeletedBadge,
    DismissedSignal,
    HeadingEdit,
    ImportConflict,
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
    TopicBoundary,
    TranscriptSegment,
)
from bristlenose.server.models import (
    Session as SessionModel,
)


@pytest.fixture()
def engine():
    """In-memory SQLite engine with all tables created."""
    eng = get_engine("sqlite://")
    init_db(eng)
    return eng


@pytest.fixture()
def db(engine) -> Session:  # type: ignore[no-untyped-def]
    """A fresh database session (rolled back after each test)."""
    factory = create_session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------


class TestTableCreation:
    """Verify all tables are created by init_db."""

    EXPECTED_TABLES = {
        "persons",
        "codebook_groups",
        "tag_definitions",
        "projects",
        "project_codebook_groups",
        "sessions",
        "source_files",
        "session_speakers",
        "transcript_segments",
        "quotes",
        "screen_clusters",
        "theme_groups",
        "cluster_quotes",
        "theme_quotes",
        "topic_boundaries",
        "quote_tags",
        "quote_states",
        "quote_edits",
        "heading_edits",
        "deleted_badges",
        "dismissed_signals",
        "import_conflicts",
        "autocode_jobs",
        "proposed_tags",
    }

    def test_all_tables_exist(self, engine) -> None:  # type: ignore[no-untyped-def]
        inspector = inspect(engine)
        actual = set(inspector.get_table_names())
        missing = self.EXPECTED_TABLES - actual
        assert not missing, f"Missing tables: {missing}"

    def test_no_unexpected_tables(self, engine) -> None:  # type: ignore[no-untyped-def]
        inspector = inspect(engine)
        actual = set(inspector.get_table_names())
        unexpected = actual - self.EXPECTED_TABLES
        assert not unexpected, f"Unexpected tables: {unexpected}"

    def test_init_db_idempotent(self, engine) -> None:  # type: ignore[no-untyped-def]
        """Calling init_db twice must not raise."""
        init_db(engine)
        init_db(engine)


# ---------------------------------------------------------------------------
# Instance-scoped models
# ---------------------------------------------------------------------------


class TestPerson:
    def test_create_and_read(self, db: Session) -> None:
        person = Person(full_name="Sarah Chen", short_name="Sarah", role_title="UX Researcher")
        db.add(person)
        db.commit()

        loaded = db.query(Person).first()
        assert loaded is not None
        assert loaded.full_name == "Sarah Chen"
        assert loaded.short_name == "Sarah"
        assert loaded.role_title == "UX Researcher"
        assert loaded.created_at is not None

    def test_defaults(self, db: Session) -> None:
        person = Person()
        db.add(person)
        db.commit()

        loaded = db.query(Person).first()
        assert loaded is not None
        assert loaded.full_name == ""
        assert loaded.short_name == ""
        assert loaded.notes == ""


class TestCodebookGroup:
    def test_create_with_tags(self, db: Session) -> None:
        group = CodebookGroup(name="Friction", subtitle="Points of friction", colour_set="ux")
        tag1 = TagDefinition(codebook_group=group, name="slow loading")
        tag2 = TagDefinition(codebook_group=group, name="confusing layout")
        db.add_all([group, tag1, tag2])
        db.commit()

        loaded = db.query(CodebookGroup).first()
        assert loaded is not None
        assert loaded.name == "Friction"
        assert len(loaded.tag_definitions) == 2
        names = {t.name for t in loaded.tag_definitions}
        assert names == {"slow loading", "confusing layout"}


# ---------------------------------------------------------------------------
# Project-scoped models
# ---------------------------------------------------------------------------


class TestProject:
    def test_create_project(self, db: Session) -> None:
        proj = Project(
            name="Smoke Test",
            slug="smoke-test",
            input_dir="/tmp/input",
            output_dir="/tmp/output",
        )
        db.add(proj)
        db.commit()

        loaded = db.query(Project).first()
        assert loaded is not None
        assert loaded.name == "Smoke Test"
        assert loaded.imported_at is None

    def test_imported_at_update(self, db: Session) -> None:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()

        now = datetime.now(timezone.utc)
        proj.imported_at = now
        db.commit()

        loaded = db.query(Project).first()
        assert loaded is not None
        assert loaded.imported_at is not None


class TestProjectCodebookGroup:
    def test_link_codebook_group_to_project(self, db: Session) -> None:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        group = CodebookGroup(name="Trust")
        db.add_all([proj, group])
        db.commit()

        link = ProjectCodebookGroup(
            project_id=proj.id, codebook_group_id=group.id, sort_order=1
        )
        db.add(link)
        db.commit()

        loaded = db.query(ProjectCodebookGroup).first()
        assert loaded is not None
        assert loaded.project_id == proj.id
        assert loaded.codebook_group_id == group.id


# ---------------------------------------------------------------------------
# Session + related
# ---------------------------------------------------------------------------


class TestSession:
    def _make_project(self, db: Session) -> Project:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()
        return proj

    def test_create_session(self, db: Session) -> None:
        proj = self._make_project(db)
        sess = SessionModel(
            project_id=proj.id,
            session_id="s1",
            session_number=1,
            duration_seconds=78.0,
            has_media=True,
            has_video=False,
        )
        db.add(sess)
        db.commit()

        loaded = db.query(SessionModel).first()
        assert loaded is not None
        assert loaded.session_id == "s1"
        assert loaded.duration_seconds == 78.0

    def test_unique_session_id_per_project(self, db: Session) -> None:
        proj = self._make_project(db)
        s1 = SessionModel(project_id=proj.id, session_id="s1", session_number=1)
        db.add(s1)
        db.commit()

        s1_dup = SessionModel(project_id=proj.id, session_id="s1", session_number=2)
        db.add(s1_dup)
        with pytest.raises(IntegrityError):
            db.commit()

    def test_session_with_source_files(self, db: Session) -> None:
        proj = self._make_project(db)
        sess = SessionModel(project_id=proj.id, session_id="s1", session_number=1)
        db.add(sess)
        db.commit()

        sf = SourceFile(
            session_id=sess.id,
            file_type="subtitle_vtt",
            path="/data/Session 1.vtt",
            size_bytes=1024,
        )
        db.add(sf)
        db.commit()

        loaded = db.query(SessionModel).first()
        assert loaded is not None
        assert len(loaded.source_files) == 1
        assert loaded.source_files[0].file_type == "subtitle_vtt"

    def test_session_speakers(self, db: Session) -> None:
        proj = self._make_project(db)
        sess = SessionModel(project_id=proj.id, session_id="s1", session_number=1)
        person_m = Person(full_name="Sarah", short_name="Sarah")
        person_p = Person(full_name="", short_name="")
        db.add_all([sess, person_m, person_p])
        db.commit()

        sp_m = SessionSpeaker(
            session_id=sess.id,
            person_id=person_m.id,
            speaker_code="m1",
            speaker_role="researcher",
        )
        sp_p = SessionSpeaker(
            session_id=sess.id,
            person_id=person_p.id,
            speaker_code="p1",
            speaker_role="participant",
        )
        db.add_all([sp_m, sp_p])
        db.commit()

        loaded = db.query(SessionModel).first()
        assert loaded is not None
        assert len(loaded.session_speakers) == 2
        codes = {sp.speaker_code for sp in loaded.session_speakers}
        assert codes == {"m1", "p1"}

    def test_unique_speaker_code_per_session(self, db: Session) -> None:
        proj = self._make_project(db)
        sess = SessionModel(project_id=proj.id, session_id="s1", session_number=1)
        person = Person(full_name="Sarah")
        db.add_all([sess, person])
        db.commit()

        sp1 = SessionSpeaker(
            session_id=sess.id, person_id=person.id, speaker_code="m1", speaker_role="researcher"
        )
        db.add(sp1)
        db.commit()

        sp2 = SessionSpeaker(
            session_id=sess.id, person_id=person.id, speaker_code="m1", speaker_role="researcher"
        )
        db.add(sp2)
        with pytest.raises(IntegrityError):
            db.commit()


class TestTranscriptSegment:
    def test_create_segment(self, db: Session) -> None:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()
        sess = SessionModel(project_id=proj.id, session_id="s1", session_number=1)
        db.add(sess)
        db.commit()

        seg = TranscriptSegment(
            session_id=sess.id,
            speaker_code="p1",
            start_time=10.0,
            end_time=18.0,
            text="I found the dashboard pretty confusing.",
            source="vtt",
        )
        db.add(seg)
        db.commit()

        loaded = db.query(TranscriptSegment).first()
        assert loaded is not None
        assert loaded.speaker_code == "p1"
        assert loaded.start_time == 10.0


# ---------------------------------------------------------------------------
# Quotes + groupings
# ---------------------------------------------------------------------------


class TestQuote:
    def _make_project_with_quote(self, db: Session) -> tuple[Project, Quote]:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()

        q = Quote(
            project_id=proj.id,
            session_id="s1",
            participant_id="p1",
            start_timecode=10.0,
            end_timecode=18.0,
            text="I found the dashboard pretty confusing.",
            quote_type="screen_specific",
            sentiment="confusion",
            intensity=2,
            last_imported_at=datetime.now(timezone.utc),
        )
        db.add(q)
        db.commit()
        return proj, q

    def test_create_quote(self, db: Session) -> None:
        _proj, q = self._make_project_with_quote(db)
        loaded = db.query(Quote).first()
        assert loaded is not None
        assert loaded.text == "I found the dashboard pretty confusing."
        assert loaded.sentiment == "confusion"
        assert loaded.intensity == 2
        assert loaded.last_imported_at is not None


class TestScreenCluster:
    def test_create_cluster_with_quotes(self, db: Session) -> None:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()

        cluster = ScreenCluster(
            project_id=proj.id,
            screen_label="Dashboard",
            description="Dashboard confusion",
            created_by="pipeline",
            last_imported_at=datetime.now(timezone.utc),
        )
        q = Quote(
            project_id=proj.id,
            session_id="s1",
            participant_id="p1",
            start_timecode=10.0,
            end_timecode=18.0,
            text="Confusing dashboard",
            quote_type="screen_specific",
        )
        db.add_all([cluster, q])
        db.commit()

        cq = ClusterQuote(
            cluster_id=cluster.id, quote_id=q.id, assigned_by="pipeline"
        )
        db.add(cq)
        db.commit()

        loaded = db.query(ClusterQuote).first()
        assert loaded is not None
        assert loaded.assigned_by == "pipeline"
        assert loaded.assigned_at is not None

    def test_unique_cluster_label_per_project(self, db: Session) -> None:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()

        c1 = ScreenCluster(project_id=proj.id, screen_label="Dashboard")
        db.add(c1)
        db.commit()

        c2 = ScreenCluster(project_id=proj.id, screen_label="Dashboard")
        db.add(c2)
        with pytest.raises(IntegrityError):
            db.commit()

    def test_unique_cluster_quote_pair(self, db: Session) -> None:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()

        cluster = ScreenCluster(project_id=proj.id, screen_label="Dashboard")
        q = Quote(
            project_id=proj.id,
            session_id="s1",
            participant_id="p1",
            start_timecode=10.0,
            end_timecode=18.0,
            text="test",
            quote_type="screen_specific",
        )
        db.add_all([cluster, q])
        db.commit()

        cq1 = ClusterQuote(cluster_id=cluster.id, quote_id=q.id)
        db.add(cq1)
        db.commit()

        cq2 = ClusterQuote(cluster_id=cluster.id, quote_id=q.id)
        db.add(cq2)
        with pytest.raises(IntegrityError):
            db.commit()


class TestThemeGroup:
    def test_create_theme_with_quotes(self, db: Session) -> None:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()

        theme = ThemeGroup(
            project_id=proj.id,
            theme_label="Onboarding gaps",
            description="Participants felt lost",
            created_by="pipeline",
        )
        q = Quote(
            project_id=proj.id,
            session_id="s1",
            participant_id="p1",
            start_timecode=66.0,
            end_timecode=78.0,
            text="Onboarding could be better",
            quote_type="general_context",
        )
        db.add_all([theme, q])
        db.commit()

        tq = ThemeQuote(theme_id=theme.id, quote_id=q.id, assigned_by="pipeline")
        db.add(tq)
        db.commit()

        loaded = db.query(ThemeQuote).first()
        assert loaded is not None
        assert loaded.assigned_by == "pipeline"

    def test_unique_theme_label_per_project(self, db: Session) -> None:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()

        t1 = ThemeGroup(project_id=proj.id, theme_label="Onboarding gaps")
        db.add(t1)
        db.commit()

        t2 = ThemeGroup(project_id=proj.id, theme_label="Onboarding gaps")
        db.add(t2)
        with pytest.raises(IntegrityError):
            db.commit()


# ---------------------------------------------------------------------------
# Researcher state
# ---------------------------------------------------------------------------


class TestResearcherState:
    def _make_quote(self, db: Session) -> Quote:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()
        q = Quote(
            project_id=proj.id,
            session_id="s1",
            participant_id="p1",
            start_timecode=10.0,
            end_timecode=18.0,
            text="test quote",
            quote_type="screen_specific",
        )
        db.add(q)
        db.commit()
        return q

    def test_quote_state_hidden(self, db: Session) -> None:
        q = self._make_quote(db)
        state = QuoteState(quote_id=q.id, is_hidden=True, hidden_at=datetime.now(timezone.utc))
        db.add(state)
        db.commit()

        loaded = db.query(QuoteState).first()
        assert loaded is not None
        assert loaded.is_hidden is True
        assert loaded.is_starred is False

    def test_quote_state_unique_per_quote(self, db: Session) -> None:
        q = self._make_quote(db)
        s1 = QuoteState(quote_id=q.id, is_hidden=True)
        db.add(s1)
        db.commit()

        s2 = QuoteState(quote_id=q.id, is_starred=True)
        db.add(s2)
        with pytest.raises(IntegrityError):
            db.commit()

    def test_quote_edit(self, db: Session) -> None:
        q = self._make_quote(db)
        edit = QuoteEdit(quote_id=q.id, edited_text="corrected text")
        db.add(edit)
        db.commit()

        loaded = db.query(QuoteEdit).first()
        assert loaded is not None
        assert loaded.edited_text == "corrected text"

    def test_quote_tag(self, db: Session) -> None:
        q = self._make_quote(db)
        group = CodebookGroup(name="Friction")
        db.add(group)
        db.commit()
        tag = TagDefinition(codebook_group_id=group.id, name="slow loading")
        db.add(tag)
        db.commit()

        qt = QuoteTag(quote_id=q.id, tag_definition_id=tag.id)
        db.add(qt)
        db.commit()

        loaded = db.query(QuoteTag).first()
        assert loaded is not None
        assert loaded.quote_id == q.id

    def test_unique_quote_tag(self, db: Session) -> None:
        q = self._make_quote(db)
        group = CodebookGroup(name="Friction")
        db.add(group)
        db.commit()
        tag = TagDefinition(codebook_group_id=group.id, name="slow")
        db.add(tag)
        db.commit()

        qt1 = QuoteTag(quote_id=q.id, tag_definition_id=tag.id)
        db.add(qt1)
        db.commit()

        qt2 = QuoteTag(quote_id=q.id, tag_definition_id=tag.id)
        db.add(qt2)
        with pytest.raises(IntegrityError):
            db.commit()

    def test_heading_edit(self, db: Session) -> None:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()

        edit = HeadingEdit(
            project_id=proj.id,
            heading_key="section-dashboard:title",
            edited_text="Landing page",
        )
        db.add(edit)
        db.commit()

        loaded = db.query(HeadingEdit).first()
        assert loaded is not None
        assert loaded.heading_key == "section-dashboard:title"
        assert loaded.edited_text == "Landing page"

    def test_deleted_badge(self, db: Session) -> None:
        q = self._make_quote(db)
        badge = DeletedBadge(quote_id=q.id, sentiment="confusion")
        db.add(badge)
        db.commit()

        loaded = db.query(DeletedBadge).first()
        assert loaded is not None
        assert loaded.sentiment == "confusion"

    def test_unique_deleted_badge(self, db: Session) -> None:
        q = self._make_quote(db)
        b1 = DeletedBadge(quote_id=q.id, sentiment="confusion")
        db.add(b1)
        db.commit()

        b2 = DeletedBadge(quote_id=q.id, sentiment="confusion")
        db.add(b2)
        with pytest.raises(IntegrityError):
            db.commit()

    def test_dismissed_signal(self, db: Session) -> None:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()

        ds = DismissedSignal(project_id=proj.id, signal_key="section:Dashboard|frustration")
        db.add(ds)
        db.commit()

        loaded = db.query(DismissedSignal).first()
        assert loaded is not None
        assert loaded.signal_key == "section:Dashboard|frustration"

    def test_unique_dismissed_signal(self, db: Session) -> None:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()

        ds1 = DismissedSignal(project_id=proj.id, signal_key="section:Dashboard|frustration")
        db.add(ds1)
        db.commit()

        ds2 = DismissedSignal(project_id=proj.id, signal_key="section:Dashboard|frustration")
        db.add(ds2)
        with pytest.raises(IntegrityError):
            db.commit()


class TestImportConflict:
    def test_create_conflict(self, db: Session) -> None:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()

        conflict = ImportConflict(
            project_id=proj.id,
            entity_type="screen_cluster",
            entity_id=1,
            conflict_type="label_collision",
            description='Pipeline created "Landing page" but researcher renamed it',
        )
        db.add(conflict)
        db.commit()

        loaded = db.query(ImportConflict).first()
        assert loaded is not None
        assert loaded.entity_type == "screen_cluster"
        assert loaded.resolved is False

    def test_resolve_conflict(self, db: Session) -> None:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()

        conflict = ImportConflict(
            project_id=proj.id, entity_type="theme_group", entity_id=2,
            conflict_type="label_collision", description="test",
        )
        db.add(conflict)
        db.commit()

        conflict.resolved = True
        conflict.resolved_at = datetime.now(timezone.utc)
        db.commit()

        loaded = db.query(ImportConflict).first()
        assert loaded is not None
        assert loaded.resolved is True
        assert loaded.resolved_at is not None


# ---------------------------------------------------------------------------
# Cross-cutting: assigned_by / created_by patterns
# ---------------------------------------------------------------------------


class TestAssignedByPattern:
    """Verify the pipeline/researcher ownership tracking works correctly."""

    def _setup(self, db: Session) -> tuple[Project, Quote, ScreenCluster, ThemeGroup]:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()

        q = Quote(
            project_id=proj.id,
            session_id="s1",
            participant_id="p1",
            start_timecode=10.0,
            end_timecode=18.0,
            text="test",
            quote_type="screen_specific",
        )
        cluster = ScreenCluster(
            project_id=proj.id, screen_label="Dashboard", created_by="pipeline"
        )
        theme = ThemeGroup(
            project_id=proj.id, theme_label="Onboarding", created_by="pipeline"
        )
        db.add_all([q, cluster, theme])
        db.commit()
        return proj, q, cluster, theme

    def test_pipeline_assigns_quote_to_cluster(self, db: Session) -> None:
        _proj, q, cluster, _theme = self._setup(db)
        cq = ClusterQuote(cluster_id=cluster.id, quote_id=q.id, assigned_by="pipeline")
        db.add(cq)
        db.commit()

        loaded = db.query(ClusterQuote).first()
        assert loaded is not None
        assert loaded.assigned_by == "pipeline"

    def test_researcher_moves_quote(self, db: Session) -> None:
        """Simulate: researcher moves a quote from one cluster to another."""
        _proj, q, cluster, _theme = self._setup(db)

        # Pipeline assigns
        cq = ClusterQuote(cluster_id=cluster.id, quote_id=q.id, assigned_by="pipeline")
        db.add(cq)
        db.commit()

        # Researcher moves — delete old, insert new with assigned_by="researcher"
        db.delete(cq)
        db.commit()

        cluster2 = ScreenCluster(
            project_id=_proj.id, screen_label="Search", created_by="pipeline"
        )
        db.add(cluster2)
        db.commit()

        cq_new = ClusterQuote(cluster_id=cluster2.id, quote_id=q.id, assigned_by="researcher")
        db.add(cq_new)
        db.commit()

        loaded = db.query(ClusterQuote).first()
        assert loaded is not None
        assert loaded.assigned_by == "researcher"
        assert loaded.cluster_id == cluster2.id

    def test_researcher_created_cluster_survives(self, db: Session) -> None:
        """Researcher-created clusters have created_by='researcher'."""
        proj, _q, _cluster, _theme = self._setup(db)

        researcher_cluster = ScreenCluster(
            project_id=proj.id, screen_label="My custom section", created_by="researcher"
        )
        db.add(researcher_cluster)
        db.commit()

        # Verify we can query by created_by
        researcher_clusters = (
            db.query(ScreenCluster).filter_by(created_by="researcher").all()
        )
        assert len(researcher_clusters) == 1
        assert researcher_clusters[0].screen_label == "My custom section"

        pipeline_clusters = (
            db.query(ScreenCluster).filter_by(created_by="pipeline").all()
        )
        assert len(pipeline_clusters) == 1
        assert pipeline_clusters[0].screen_label == "Dashboard"

    def test_unsorted_pool_query(self, db: Session) -> None:
        """Quotes without cluster_quote or theme_quote rows are 'unsorted'."""
        proj, q, cluster, _theme = self._setup(db)

        # q has no cluster_quote or theme_quote — it's unsorted
        unsorted = (
            db.query(Quote)
            .filter(
                ~Quote.id.in_(db.query(ClusterQuote.quote_id)),
                ~Quote.id.in_(db.query(ThemeQuote.quote_id)),
            )
            .all()
        )
        assert len(unsorted) == 1
        assert unsorted[0].id == q.id

        # Assign the quote — it's no longer unsorted
        cq = ClusterQuote(cluster_id=cluster.id, quote_id=q.id, assigned_by="pipeline")
        db.add(cq)
        db.commit()

        unsorted = (
            db.query(Quote)
            .filter(
                ~Quote.id.in_(db.query(ClusterQuote.quote_id)),
                ~Quote.id.in_(db.query(ThemeQuote.quote_id)),
            )
            .all()
        )
        assert len(unsorted) == 0


# ---------------------------------------------------------------------------
# Topic boundary
# ---------------------------------------------------------------------------


class TestTopicBoundary:
    def test_create_topic_boundary(self, db: Session) -> None:
        proj = Project(name="Test", input_dir="/tmp/i", output_dir="/tmp/o")
        db.add(proj)
        db.commit()
        sess = SessionModel(project_id=proj.id, session_id="s1", session_number=1)
        db.add(sess)
        db.commit()

        tb = TopicBoundary(
            session_id=sess.id,
            timecode_seconds=39.0,
            topic_label="Search",
            transition_type="moderator_question",
            confidence=0.85,
        )
        db.add(tb)
        db.commit()

        loaded = db.query(TopicBoundary).first()
        assert loaded is not None
        assert loaded.topic_label == "Search"
        assert loaded.confidence == 0.85
