"""SQLAdmin model views for database browsing (dev-only).

Registered when ``bristlenose serve --dev`` is active. Provides a full
CRUD admin panel at ``/admin/`` for all 22 domain tables.
"""

from __future__ import annotations

from sqladmin import Admin, ModelView

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
    Session,
    SessionSpeaker,
    SourceFile,
    TagDefinition,
    ThemeGroup,
    ThemeQuote,
    TopicBoundary,
    TranscriptSegment,
)

# ---------------------------------------------------------------------------
# Instance-scoped
# ---------------------------------------------------------------------------


class PersonAdmin(ModelView, model=Person):
    column_list = [Person.id, Person.full_name, Person.short_name, Person.role_title]
    name = "Person"
    name_plural = "People"
    icon = "fa-solid fa-user"
    category = "Instance"


class CodebookGroupAdmin(ModelView, model=CodebookGroup):
    column_list = [CodebookGroup.id, CodebookGroup.name, CodebookGroup.colour_set,
                   CodebookGroup.sort_order]
    name = "Codebook Group"
    name_plural = "Codebook Groups"
    icon = "fa-solid fa-book"
    category = "Instance"


class TagDefinitionAdmin(ModelView, model=TagDefinition):
    column_list = [TagDefinition.id, TagDefinition.codebook_group_id, TagDefinition.name]
    name = "Tag Definition"
    name_plural = "Tag Definitions"
    icon = "fa-solid fa-tag"
    category = "Instance"


# ---------------------------------------------------------------------------
# Project core
# ---------------------------------------------------------------------------


class ProjectAdmin(ModelView, model=Project):
    column_list = [Project.id, Project.name, Project.slug, Project.created_at,
                   Project.imported_at]
    name = "Project"
    name_plural = "Projects"
    icon = "fa-solid fa-folder"
    category = "Project"


class ProjectCodebookGroupAdmin(ModelView, model=ProjectCodebookGroup):
    column_list = [ProjectCodebookGroup.id, ProjectCodebookGroup.project_id,
                   ProjectCodebookGroup.codebook_group_id, ProjectCodebookGroup.sort_order]
    name = "Project Codebook Link"
    name_plural = "Project Codebook Links"
    icon = "fa-solid fa-link"
    category = "Project"


class SessionAdmin(ModelView, model=Session):
    column_list = [Session.id, Session.project_id, Session.session_id,
                   Session.session_number, Session.duration_seconds]
    name = "Session"
    name_plural = "Sessions"
    icon = "fa-solid fa-microphone"
    category = "Raw material"


class SourceFileAdmin(ModelView, model=SourceFile):
    column_list = [SourceFile.id, SourceFile.session_id, SourceFile.file_type,
                   SourceFile.path]
    name = "Source File"
    name_plural = "Source Files"
    icon = "fa-solid fa-file"
    category = "Raw material"


class SessionSpeakerAdmin(ModelView, model=SessionSpeaker):
    column_list = [SessionSpeaker.id, SessionSpeaker.session_id, SessionSpeaker.person_id,
                   SessionSpeaker.speaker_code, SessionSpeaker.speaker_role]
    name = "Session Speaker"
    name_plural = "Session Speakers"
    icon = "fa-solid fa-users"
    category = "Raw material"


class TranscriptSegmentAdmin(ModelView, model=TranscriptSegment):
    column_list = [TranscriptSegment.id, TranscriptSegment.session_id,
                   TranscriptSegment.speaker_code, TranscriptSegment.start_time,
                   TranscriptSegment.text]
    name = "Transcript Segment"
    name_plural = "Transcript Segments"
    icon = "fa-solid fa-align-left"
    category = "Raw material"


# ---------------------------------------------------------------------------
# AI analysis
# ---------------------------------------------------------------------------


class QuoteAdmin(ModelView, model=Quote):
    column_list = [Quote.id, Quote.project_id, Quote.session_id,
                   Quote.participant_id, Quote.sentiment, Quote.topic_label]
    name = "Quote"
    name_plural = "Quotes"
    icon = "fa-solid fa-quote-left"
    category = "AI analysis"


class ScreenClusterAdmin(ModelView, model=ScreenCluster):
    column_list = [ScreenCluster.id, ScreenCluster.project_id,
                   ScreenCluster.screen_label, ScreenCluster.created_by]
    name = "Screen Cluster"
    name_plural = "Screen Clusters"
    icon = "fa-solid fa-display"
    category = "AI analysis"


class ThemeGroupAdmin(ModelView, model=ThemeGroup):
    column_list = [ThemeGroup.id, ThemeGroup.project_id,
                   ThemeGroup.theme_label, ThemeGroup.created_by]
    name = "Theme Group"
    name_plural = "Theme Groups"
    icon = "fa-solid fa-layer-group"
    category = "AI analysis"


class ClusterQuoteAdmin(ModelView, model=ClusterQuote):
    column_list = [ClusterQuote.id, ClusterQuote.cluster_id,
                   ClusterQuote.quote_id, ClusterQuote.assigned_by]
    name = "Cluster Quote"
    name_plural = "Cluster Quotes"
    icon = "fa-solid fa-arrows-to-dot"
    category = "AI analysis"


class ThemeQuoteAdmin(ModelView, model=ThemeQuote):
    column_list = [ThemeQuote.id, ThemeQuote.theme_id,
                   ThemeQuote.quote_id, ThemeQuote.assigned_by]
    name = "Theme Quote"
    name_plural = "Theme Quotes"
    icon = "fa-solid fa-arrows-to-dot"
    category = "AI analysis"


class TopicBoundaryAdmin(ModelView, model=TopicBoundary):
    column_list = [TopicBoundary.id, TopicBoundary.session_id,
                   TopicBoundary.topic_label, TopicBoundary.timecode_seconds]
    name = "Topic Boundary"
    name_plural = "Topic Boundaries"
    icon = "fa-solid fa-scissors"
    category = "AI analysis"


# ---------------------------------------------------------------------------
# Researcher edits
# ---------------------------------------------------------------------------


class QuoteTagAdmin(ModelView, model=QuoteTag):
    column_list = [QuoteTag.id, QuoteTag.quote_id, QuoteTag.tag_definition_id]
    name = "Quote Tag"
    name_plural = "Quote Tags"
    icon = "fa-solid fa-tags"
    category = "Researcher"


class QuoteStateAdmin(ModelView, model=QuoteState):
    column_list = [QuoteState.id, QuoteState.quote_id,
                   QuoteState.is_hidden, QuoteState.is_starred]
    name = "Quote State"
    name_plural = "Quote States"
    icon = "fa-solid fa-star"
    category = "Researcher"


class QuoteEditAdmin(ModelView, model=QuoteEdit):
    column_list = [QuoteEdit.id, QuoteEdit.quote_id, QuoteEdit.edited_text]
    name = "Quote Edit"
    name_plural = "Quote Edits"
    icon = "fa-solid fa-pen"
    category = "Researcher"


class HeadingEditAdmin(ModelView, model=HeadingEdit):
    column_list = [HeadingEdit.id, HeadingEdit.project_id,
                   HeadingEdit.heading_key, HeadingEdit.edited_text]
    name = "Heading Edit"
    name_plural = "Heading Edits"
    icon = "fa-solid fa-heading"
    category = "Researcher"


class DeletedBadgeAdmin(ModelView, model=DeletedBadge):
    column_list = [DeletedBadge.id, DeletedBadge.quote_id, DeletedBadge.sentiment]
    name = "Deleted Badge"
    name_plural = "Deleted Badges"
    icon = "fa-solid fa-trash"
    category = "Researcher"


class DismissedSignalAdmin(ModelView, model=DismissedSignal):
    column_list = [DismissedSignal.id, DismissedSignal.project_id,
                   DismissedSignal.signal_key]
    name = "Dismissed Signal"
    name_plural = "Dismissed Signals"
    icon = "fa-solid fa-eye-slash"
    category = "Researcher"


class ImportConflictAdmin(ModelView, model=ImportConflict):
    column_list = [ImportConflict.id, ImportConflict.project_id,
                   ImportConflict.entity_type, ImportConflict.conflict_type,
                   ImportConflict.resolved]
    name = "Import Conflict"
    name_plural = "Import Conflicts"
    icon = "fa-solid fa-triangle-exclamation"
    category = "Researcher"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_admin_views(admin: Admin) -> None:
    """Register all model views with the admin instance."""
    # Instance-scoped
    admin.add_view(PersonAdmin)
    admin.add_view(CodebookGroupAdmin)
    admin.add_view(TagDefinitionAdmin)
    # Project core
    admin.add_view(ProjectAdmin)
    admin.add_view(ProjectCodebookGroupAdmin)
    # Raw material
    admin.add_view(SessionAdmin)
    admin.add_view(SourceFileAdmin)
    admin.add_view(SessionSpeakerAdmin)
    admin.add_view(TranscriptSegmentAdmin)
    # AI analysis
    admin.add_view(QuoteAdmin)
    admin.add_view(ScreenClusterAdmin)
    admin.add_view(ThemeGroupAdmin)
    admin.add_view(ClusterQuoteAdmin)
    admin.add_view(ThemeQuoteAdmin)
    admin.add_view(TopicBoundaryAdmin)
    # Researcher edits
    admin.add_view(QuoteTagAdmin)
    admin.add_view(QuoteStateAdmin)
    admin.add_view(QuoteEditAdmin)
    admin.add_view(HeadingEditAdmin)
    admin.add_view(DeletedBadgeAdmin)
    admin.add_view(DismissedSignalAdmin)
    admin.add_view(ImportConflictAdmin)
