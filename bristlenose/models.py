"""Data models shared across all pipeline stages."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FileType(str, Enum):
    AUDIO = "audio"
    VIDEO = "video"
    SUBTITLE_SRT = "subtitle_srt"
    SUBTITLE_VTT = "subtitle_vtt"
    DOCX = "docx"


class SpeakerRole(str, Enum):
    RESEARCHER = "researcher"
    PARTICIPANT = "participant"
    OBSERVER = "observer"
    UNKNOWN = "unknown"


class TransitionType(str, Enum):
    SCREEN_CHANGE = "screen_change"
    TOPIC_SHIFT = "topic_shift"
    TASK_CHANGE = "task_change"
    GENERAL_CONTEXT = "general_context"


class QuoteType(str, Enum):
    SCREEN_SPECIFIC = "screen_specific"
    GENERAL_CONTEXT = "general_context"


class QuoteIntent(str, Enum):
    NARRATION = "narration"  # Describing actions: "I'm clicking beds"
    CONFUSION = "confusion"  # Expressing confusion: "Why is that not working?"
    JUDGMENT = "judgment"  # Evaluating: "That's quite cheap"
    FRUSTRATION = "frustration"  # Expressing frustration: "Something's up"
    DELIGHT = "delight"  # Positive reaction: "Oh I like that"
    SUGGESTION = "suggestion"  # Proposing alternatives: "Maybe brown and orange"
    TASK_MANAGEMENT = "task_management"  # Session admin: "This is enough data"


class EmotionalTone(str, Enum):
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"
    DELIGHTED = "delighted"
    CONFUSED = "confused"
    AMUSED = "amused"
    SARCASTIC = "sarcastic"
    CRITICAL = "critical"


class JourneyStage(str, Enum):
    LANDING = "landing"
    BROWSE = "browse"
    SEARCH = "search"
    PRODUCT_DETAIL = "product_detail"
    CART = "cart"
    CHECKOUT = "checkout"
    ERROR_RECOVERY = "error_recovery"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Ingestion models
# ---------------------------------------------------------------------------


AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".wma", ".aac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
SUBTITLE_SRT_EXTENSIONS = {".srt"}
SUBTITLE_VTT_EXTENSIONS = {".vtt"}
DOCX_EXTENSIONS = {".docx"}

ALL_EXTENSIONS = (
    AUDIO_EXTENSIONS | VIDEO_EXTENSIONS | SUBTITLE_SRT_EXTENSIONS | SUBTITLE_VTT_EXTENSIONS | DOCX_EXTENSIONS
)


def classify_file(path: Path) -> FileType | None:
    """Return the FileType for a path, or None if unsupported."""
    ext = path.suffix.lower()
    if ext in AUDIO_EXTENSIONS:
        return FileType.AUDIO
    if ext in VIDEO_EXTENSIONS:
        return FileType.VIDEO
    if ext in SUBTITLE_SRT_EXTENSIONS:
        return FileType.SUBTITLE_SRT
    if ext in SUBTITLE_VTT_EXTENSIONS:
        return FileType.SUBTITLE_VTT
    if ext in DOCX_EXTENSIONS:
        return FileType.DOCX
    return None


class InputFile(BaseModel):
    """A single input file discovered during ingestion."""

    path: Path
    file_type: FileType
    created_at: datetime
    size_bytes: int
    duration_seconds: float | None = None
    error: str | None = None


class InputSession(BaseModel):
    """One research session — one participant, one or more input files."""

    participant_id: str  # "p1", "p2", ...
    participant_number: int  # 1, 2, ...
    files: list[InputFile]
    audio_path: Path | None = None
    has_existing_transcript: bool = False
    session_date: datetime

    @property
    def has_audio(self) -> bool:
        return any(f.file_type == FileType.AUDIO for f in self.files)

    @property
    def has_video(self) -> bool:
        return any(f.file_type == FileType.VIDEO for f in self.files)

    @property
    def has_subtitles(self) -> bool:
        return any(
            f.file_type in (FileType.SUBTITLE_SRT, FileType.SUBTITLE_VTT) for f in self.files
        )

    @property
    def has_docx(self) -> bool:
        return any(f.file_type == FileType.DOCX for f in self.files)


# ---------------------------------------------------------------------------
# Transcript models
# ---------------------------------------------------------------------------


class Word(BaseModel):
    """A single word with timing information."""

    text: str
    start_time: float  # seconds
    end_time: float  # seconds
    confidence: float = 1.0


class TranscriptSegment(BaseModel):
    """A contiguous segment of speech from one speaker."""

    start_time: float  # seconds
    end_time: float  # seconds
    text: str
    speaker_label: str | None = None  # "Speaker A", "John Smith", etc.
    speaker_role: SpeakerRole = SpeakerRole.UNKNOWN
    words: list[Word] = Field(default_factory=list)
    source: str = ""  # "whisper", "srt", "vtt", "docx"


class FullTranscript(BaseModel):
    """Complete transcript for one session, with all segments normalised."""

    participant_id: str
    source_file: str
    session_date: datetime
    duration_seconds: float
    segments: list[TranscriptSegment]

    def full_text(self) -> str:
        """Return the full transcript as timestamped text."""
        lines: list[str] = []
        for seg in self.segments:
            tc = format_timecode(seg.start_time)
            role_tag = f" [{seg.speaker_role.value.upper()}]" if seg.speaker_role != SpeakerRole.UNKNOWN else ""
            lines.append(f"[{tc}]{role_tag} {seg.text}")
        return "\n\n".join(lines)

    def participant_text(self) -> str:
        """Return only participant speech as timestamped text."""
        lines: list[str] = []
        for seg in self.segments:
            if seg.speaker_role == SpeakerRole.PARTICIPANT:
                tc = format_timecode(seg.start_time)
                lines.append(f"[{tc}] {seg.text}")
        return "\n\n".join(lines)


class PiiCleanTranscript(FullTranscript):
    """Same structure as FullTranscript, but with PII redacted from text."""

    pii_entities_found: int = 0


# ---------------------------------------------------------------------------
# Topic segmentation models
# ---------------------------------------------------------------------------


class TopicBoundary(BaseModel):
    """A point in the transcript where the topic or screen changes."""

    timecode_seconds: float
    topic_label: str
    transition_type: TransitionType
    confidence: float = 1.0


class SessionTopicMap(BaseModel):
    """All topic boundaries for one session."""

    participant_id: str
    boundaries: list[TopicBoundary]

    def topic_at(self, seconds: float) -> TopicBoundary | None:
        """Return the topic boundary active at a given timecode."""
        active: TopicBoundary | None = None
        for b in self.boundaries:
            if b.timecode_seconds <= seconds:
                active = b
            else:
                break
        return active


# ---------------------------------------------------------------------------
# Quote models
# ---------------------------------------------------------------------------


class ExtractedQuote(BaseModel):
    """A single verbatim quote extracted from participant speech."""

    participant_id: str
    start_timecode: float  # seconds
    end_timecode: float  # seconds
    text: str  # verbatim with editorial cleanup applied
    topic_label: str
    quote_type: QuoteType
    researcher_context: str | None = None  # e.g. "When asked about the dashboard"
    intent: QuoteIntent = QuoteIntent.NARRATION
    emotion: EmotionalTone = EmotionalTone.NEUTRAL
    intensity: int = 1  # 1=low, 2=medium, 3=high
    journey_stage: JourneyStage = JourneyStage.OTHER

    def formatted(self) -> str:
        """Render the quote in final output format."""
        tc = format_timecode(self.start_timecode)
        prefix = f"[{self.researcher_context}] " if self.researcher_context else ""
        return f'{prefix}[{tc}] \u201c{self.text}\u201d \u2014 {self.participant_id}'


class ScreenCluster(BaseModel):
    """A group of quotes about the same screen or task."""

    screen_label: str
    description: str
    display_order: int
    quotes: list[ExtractedQuote]


class ThemeGroup(BaseModel):
    """A group of general/contextual quotes sharing an emergent theme."""

    theme_label: str
    description: str
    quotes: list[ExtractedQuote]


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------


class PipelineResult(BaseModel):
    """Top-level result object for the entire pipeline run."""

    project_name: str
    participants: list[InputSession]
    raw_transcripts: list[FullTranscript]
    clean_transcripts: list[PiiCleanTranscript]
    screen_clusters: list[ScreenCluster]
    theme_groups: list[ThemeGroup]
    output_dir: Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def format_timecode(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS (hours only when >= 1 h)."""
    total = max(0, int(seconds))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def parse_timecode(tc: str) -> float:
    """Parse HH:MM:SS or MM:SS into seconds."""
    parts = tc.strip().split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    raise ValueError(f"Cannot parse timecode: {tc!r}")
