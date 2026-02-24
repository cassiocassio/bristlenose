"""SQLAlchemy ORM models — full domain schema.

Instance-scoped tables (no project_id): person, codebook_group, tag_definition.
Project-scoped tables: everything else.

See docs/design-serve-milestone-1.md for the domain model rationale.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bristlenose.server.db import Base

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Sentinel name for the default "Uncategorised" codebook group.
#: Tags created from the quotes tab land here by default. The group is
#: always visible, non-editable, and non-deletable.
UNCATEGORISED_GROUP_NAME = "Uncategorised"
UNCATEGORISED_GROUP_SUBTITLE = "Tags not yet assigned to any group"

#: Legacy name — used for DB migration from older databases.
_LEGACY_UNGROUPED_NAME = "Ungrouped"

# ---------------------------------------------------------------------------
# Instance-scoped (no project_id) — shared across projects
# ---------------------------------------------------------------------------


class Person(Base):
    """A person in the world — not tied to a project.

    The pipeline creates a new person row on every import. Two separate
    "Jim Smith" rows are fine — merging is a future human-driven action
    that updates session_speaker.person_id foreign keys.
    """

    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    short_name: Mapped[str] = mapped_column(String(100), default="")
    role_title: Mapped[str] = mapped_column(String(200), default="")
    persona: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    session_speakers: Mapped[list[SessionSpeaker]] = relationship(back_populates="person")


class CodebookGroup(Base):
    """A reusable analytical category — the atom of codebook reuse.

    Instance-scoped: groups live in a shared library. Projects activate
    them via project_codebook_group. colour_set is a string (not an enum)
    so new colour sets don't require schema changes.

    framework_id links to a codebook template ID ("garrett", "norman", "uxr")
    when the group was imported from a pre-built framework. Null for
    researcher-created groups. Framework groups are non-deletable and
    non-editable.
    """

    __tablename__ = "codebook_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    subtitle: Mapped[str] = mapped_column(String(500), default="")
    colour_set: Mapped[str] = mapped_column(String(50), default="ux")
    sort_order: Mapped[int] = mapped_column(default=0)
    framework_id: Mapped[str | None] = mapped_column(String(50), default=None)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    tag_definitions: Mapped[list[TagDefinition]] = relationship(back_populates="codebook_group")


class TagDefinition(Base):
    """A tag within a codebook group — the researcher's vocabulary."""

    __tablename__ = "tag_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    codebook_group_id: Mapped[int] = mapped_column(ForeignKey("codebook_groups.id"))
    name: Mapped[str] = mapped_column(String(200))

    codebook_group: Mapped[CodebookGroup] = relationship(back_populates="tag_definitions")


# ---------------------------------------------------------------------------
# Project-scoped
# ---------------------------------------------------------------------------


class Project(Base):
    """A research project (one study, one set of interviews)."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), default="")
    input_dir: Mapped[str] = mapped_column(String(500))
    output_dir: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    imported_at: Mapped[datetime | None] = mapped_column(default=None)

    sessions: Mapped[list[Session]] = relationship(back_populates="project")
    quotes: Mapped[list[Quote]] = relationship(back_populates="project")
    screen_clusters: Mapped[list[ScreenCluster]] = relationship(back_populates="project")
    theme_groups: Mapped[list[ThemeGroup]] = relationship(back_populates="project")


class ProjectCodebookGroup(Base):
    """Which codebook groups are active in this project."""

    __tablename__ = "project_codebook_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    codebook_group_id: Mapped[int] = mapped_column(ForeignKey("codebook_groups.id"))
    sort_order: Mapped[int] = mapped_column(default=0)


# ---------------------------------------------------------------------------
# The raw material
# ---------------------------------------------------------------------------


class Session(Base):
    """One research session — one or more participants, one or more files."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    session_id: Mapped[str] = mapped_column(String(50))  # "s1", "s2", ...
    session_number: Mapped[int] = mapped_column()
    session_date: Mapped[datetime | None] = mapped_column(default=None)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    has_media: Mapped[bool] = mapped_column(default=False)
    has_video: Mapped[bool] = mapped_column(default=False)
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), default=None)

    project: Mapped[Project] = relationship(back_populates="sessions")
    source_files: Mapped[list[SourceFile]] = relationship(back_populates="session")
    session_speakers: Mapped[list[SessionSpeaker]] = relationship(back_populates="session")
    transcript_segments: Mapped[list[TranscriptSegment]] = relationship(
        back_populates="session"
    )
    topic_boundaries: Mapped[list[TopicBoundary]] = relationship(back_populates="session")

    __table_args__ = (
        UniqueConstraint("project_id", "session_id", name="uq_session_project_sid"),
    )


class SourceFile(Base):
    """A source recording or transcript file linked to a session.

    verified_at tracks when we last confirmed the file exists on disk.
    Enables stale-path detection and relinking when files move.
    """

    __tablename__ = "source_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    file_type: Mapped[str] = mapped_column(String(50))  # audio, video, subtitle_srt, ...
    path: Mapped[str] = mapped_column(String(1000))
    size_bytes: Mapped[int] = mapped_column(default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Float, default=None)
    created_at: Mapped[datetime | None] = mapped_column(default=None)
    verified_at: Mapped[datetime | None] = mapped_column(default=None)

    session: Mapped[Session] = relationship(back_populates="source_files")


class SessionSpeaker(Base):
    """The join between person and session — 'this person in this session'.

    Carries speaker code, role, and per-session stats. This is what makes
    cross-session moderator linking possible: session_speaker rows for the
    same person across sessions point to the same person_id.
    """

    __tablename__ = "session_speakers"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"))
    speaker_code: Mapped[str] = mapped_column(String(20))  # "p1", "m1", "o1"
    speaker_role: Mapped[str] = mapped_column(String(50))  # researcher, participant, observer
    words_spoken: Mapped[int] = mapped_column(default=0)
    pct_words: Mapped[float] = mapped_column(Float, default=0.0)
    pct_time_speaking: Mapped[float] = mapped_column(Float, default=0.0)
    source_file: Mapped[str] = mapped_column(String(500), default="")

    session: Mapped[Session] = relationship(back_populates="session_speakers")
    person: Mapped[Person] = relationship(back_populates="session_speakers")

    __table_args__ = (
        UniqueConstraint("session_id", "speaker_code", name="uq_speaker_session_code"),
    )


class TranscriptSegment(Base):
    """A contiguous segment of speech from one speaker."""

    __tablename__ = "transcript_segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    speaker_code: Mapped[str] = mapped_column(String(20))
    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), default="")  # whisper, srt, vtt, docx
    segment_index: Mapped[int] = mapped_column(Integer, default=-1)

    session: Mapped[Session] = relationship(back_populates="transcript_segments")


# ---------------------------------------------------------------------------
# The AI's analysis
# ---------------------------------------------------------------------------


class Quote(Base):
    """A single verbatim quote extracted from participant speech.

    last_imported_at tracks when this quote was last seen in pipeline
    output.  On re-import, quotes not touched (last_imported_at < now)
    are deleted along with their researcher state — they belong to
    sessions that were removed between pipeline runs.
    """

    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(50))  # "s1" — matches Session.session_id
    participant_id: Mapped[str] = mapped_column(String(50))
    start_timecode: Mapped[float] = mapped_column(Float)
    end_timecode: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)
    verbatim_excerpt: Mapped[str] = mapped_column(Text, default="")
    topic_label: Mapped[str] = mapped_column(String(200), default="")
    quote_type: Mapped[str] = mapped_column(String(50))  # screen_specific, general_context
    researcher_context: Mapped[str | None] = mapped_column(Text, default=None)
    sentiment: Mapped[str | None] = mapped_column(String(50), default=None)
    intensity: Mapped[int] = mapped_column(Integer, default=1)
    segment_index: Mapped[int] = mapped_column(Integer, default=-1)
    last_imported_at: Mapped[datetime | None] = mapped_column(default=None)

    project: Mapped[Project] = relationship(back_populates="quotes")

    __table_args__ = (
        Index(
            "ix_quote_stable_key",
            "project_id",
            "session_id",
            "participant_id",
            "start_timecode",
        ),
    )


class ScreenCluster(Base):
    """A product-anchored grouping of screen-specific quotes.

    created_by tracks whether this cluster was created by the pipeline
    or the researcher. Pipeline-created clusters are upserted on re-import;
    researcher-created clusters are never touched by import.
    """

    __tablename__ = "screen_clusters"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    screen_label: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    display_order: Mapped[int] = mapped_column(default=0)
    created_by: Mapped[str] = mapped_column(String(20), default="pipeline")
    last_imported_at: Mapped[datetime | None] = mapped_column(default=None)

    project: Mapped[Project] = relationship(back_populates="screen_clusters")

    __table_args__ = (
        UniqueConstraint(
            "project_id", "screen_label", name="uq_cluster_project_label"
        ),
    )


class ThemeGroup(Base):
    """An emergent cross-cutting grouping of general-context quotes.

    created_by tracks whether this theme was created by the pipeline
    or the researcher. Pipeline-created themes are upserted on re-import;
    researcher-created themes are never touched by import.
    """

    __tablename__ = "theme_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    theme_label: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(20), default="pipeline")
    last_imported_at: Mapped[datetime | None] = mapped_column(default=None)

    project: Mapped[Project] = relationship(back_populates="theme_groups")

    __table_args__ = (
        UniqueConstraint(
            "project_id", "theme_label", name="uq_theme_project_label"
        ),
    )


class ClusterQuote(Base):
    """Join: which quotes belong to which screen cluster.

    assigned_by tracks whether the pipeline or the researcher made this
    assignment. On re-import, pipeline replaces its own assignments but
    never touches researcher assignments.

    Quotes with no ClusterQuote or ThemeQuote row are in the unsorted pool.
    """

    __tablename__ = "cluster_quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("screen_clusters.id"))
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"))
    assigned_by: Mapped[str] = mapped_column(String(20), default="pipeline")
    assigned_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        UniqueConstraint("cluster_id", "quote_id", name="uq_cluster_quote"),
    )


class ThemeQuote(Base):
    """Join: which quotes belong to which theme group.

    assigned_by tracks whether the pipeline or the researcher made this
    assignment. On re-import, pipeline replaces its own assignments but
    never touches researcher assignments.
    """

    __tablename__ = "theme_quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    theme_id: Mapped[int] = mapped_column(ForeignKey("theme_groups.id"))
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"))
    assigned_by: Mapped[str] = mapped_column(String(20), default="pipeline")
    assigned_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        UniqueConstraint("theme_id", "quote_id", name="uq_theme_quote"),
    )


class TopicBoundary(Base):
    """A point in the transcript where the topic changes."""

    __tablename__ = "topic_boundaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    timecode_seconds: Mapped[float] = mapped_column(Float)
    topic_label: Mapped[str] = mapped_column(String(200))
    transition_type: Mapped[str] = mapped_column(String(50))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    session: Mapped[Session] = relationship(back_populates="topic_boundaries")


# ---------------------------------------------------------------------------
# The researcher's analysis
# ---------------------------------------------------------------------------


class QuoteTag(Base):
    """Join: researcher-applied tag on a quote."""

    __tablename__ = "quote_tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    tag_definition_id: Mapped[int] = mapped_column(ForeignKey("tag_definitions.id"))
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        UniqueConstraint("quote_id", "tag_definition_id", name="uq_quote_tag"),
    )


class QuoteState(Base):
    """Researcher state on a quote: hidden, starred.

    One row per quote. Nullable timestamps — null means not hidden/starred.
    """

    __tablename__ = "quote_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), unique=True)
    is_hidden: Mapped[bool] = mapped_column(default=False)
    hidden_at: Mapped[datetime | None] = mapped_column(default=None)
    is_starred: Mapped[bool] = mapped_column(default=False)
    starred_at: Mapped[datetime | None] = mapped_column(default=None)


class QuoteEdit(Base):
    """Researcher-corrected transcription text for a quote."""

    __tablename__ = "quote_edits"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    edited_text: Mapped[str] = mapped_column(Text)
    edited_at: Mapped[datetime] = mapped_column(default=func.now())


class HeadingEdit(Base):
    """Researcher-renamed section or theme title/description.

    heading_key format: "section-{slug}:title", "theme-{slug}:desc".
    """

    __tablename__ = "heading_edits"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    heading_key: Mapped[str] = mapped_column(String(500))
    edited_text: Mapped[str] = mapped_column(Text)
    edited_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        UniqueConstraint("project_id", "heading_key", name="uq_heading_edit"),
    )


class DeletedBadge(Base):
    """Researcher removed an AI-assigned sentiment badge from a quote."""

    __tablename__ = "deleted_badges"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    sentiment: Mapped[str] = mapped_column(String(50))
    deleted_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        UniqueConstraint("quote_id", "sentiment", name="uq_deleted_badge"),
    )


class DismissedSignal(Base):
    """Researcher dismissed a signal ('I've seen this, it's not interesting').

    signal_key identifies the signal (e.g. "section:Dashboard|frustration").
    Signals are recomputed, not stored — this table just tracks dismissals.
    """

    __tablename__ = "dismissed_signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    signal_key: Mapped[str] = mapped_column(String(500))
    dismissed_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        UniqueConstraint("project_id", "signal_key", name="uq_dismissed_signal"),
    )


class ElaborationCache(Base):
    """Cached LLM-generated signal elaboration.

    Keyed by (project_id, signal_key) where signal_key encodes
    source_type, location, and group_name.  content_hash is a SHA-256
    of the signal's quote texts and tag names — when the underlying
    data changes the hash changes and a new elaboration is generated.
    """

    __tablename__ = "elaboration_caches"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    signal_key: Mapped[str] = mapped_column(String(500))
    content_hash: Mapped[str] = mapped_column(String(64))
    signal_name: Mapped[str] = mapped_column(String(200))
    pattern: Mapped[str] = mapped_column(String(20))
    elaboration: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "project_id", "signal_key", name="uq_elaboration_project_signal"
        ),
    )


class ImportConflict(Base):
    """Pipeline wanted to change something the researcher touched.

    Written during import when a conflict is detected. The researcher
    reviews and resolves conflicts after re-import.
    """

    __tablename__ = "import_conflicts"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    import_run_at: Mapped[datetime] = mapped_column(default=func.now())
    entity_type: Mapped[str] = mapped_column(String(50))  # quote, cluster, theme, ...
    entity_id: Mapped[int] = mapped_column()
    conflict_type: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    resolved: Mapped[bool] = mapped_column(default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(default=None)


# ---------------------------------------------------------------------------
# AutoCode — LLM-assisted codebook tag application
# ---------------------------------------------------------------------------


class AutoCodeJob(Base):
    """An AutoCode run — one framework applied to one project's quotes.

    The unique constraint on (project_id, framework_id) enforces "no re-run"
    at the database level. One AutoCode pass per framework per project.
    """

    __tablename__ = "autocode_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    framework_id: Mapped[str] = mapped_column(String(50))  # "garrett", "norman", "uxr"
    status: Mapped[str] = mapped_column(String(20))  # pending, running, completed, failed, cancelled
    total_quotes: Mapped[int] = mapped_column(default=0)
    processed_quotes: Mapped[int] = mapped_column(default=0)
    proposed_count: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    llm_provider: Mapped[str] = mapped_column(String(50), default="")
    llm_model: Mapped[str] = mapped_column(String(100), default="")
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime] = mapped_column(default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(default=None)

    proposed_tags: Mapped[list[ProposedTag]] = relationship(back_populates="job")

    __table_args__ = (
        UniqueConstraint(
            "project_id", "framework_id", name="uq_autocode_project_framework"
        ),
    )


class ProposedTag(Base):
    """An LLM-proposed tag assignment, pending researcher review.

    Every quote gets a ProposedTag row — including low-confidence
    assignments. The API filters by min_confidence to control what
    the researcher sees. Denied rows stay for telemetry (analysing
    which tags the LLM consistently gets wrong).
    """

    __tablename__ = "proposed_tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("autocode_jobs.id"), index=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    tag_definition_id: Mapped[int] = mapped_column(ForeignKey("tag_definitions.id"))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, accepted, denied
    reviewed_at: Mapped[datetime | None] = mapped_column(default=None)

    job: Mapped[AutoCodeJob] = relationship(back_populates="proposed_tags")

    __table_args__ = (
        UniqueConstraint("job_id", "quote_id", name="uq_proposed_tag_job_quote"),
    )
