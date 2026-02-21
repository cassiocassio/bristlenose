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


class Sentiment(str, Enum):
    """Research-backed sentiment categories for quote tagging.

    See docs/academic-sources.html for theoretical foundations.
    """

    FRUSTRATION = "frustration"  # Difficulty, annoyance, friction
    CONFUSION = "confusion"  # Not understanding, uncertainty
    DOUBT = "doubt"  # Scepticism, worry, distrust
    SURPRISE = "surprise"  # Expectation mismatch (neutral — flag for investigation)
    SATISFACTION = "satisfaction"  # Met expectations, task success
    DELIGHT = "delight"  # Exceeded expectations, pleasure
    CONFIDENCE = "confidence"  # Trust, feeling in control


# Deprecated enums — kept for backward compatibility with existing intermediate JSON
class QuoteIntent(str, Enum):
    NARRATION = "narration"
    CONFUSION = "confusion"
    JUDGMENT = "judgment"
    FRUSTRATION = "frustration"
    DELIGHT = "delight"
    SUGGESTION = "suggestion"
    TASK_MANAGEMENT = "task_management"


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
    """One research session — one or more participants, one or more input files."""

    session_id: str  # "s1", "s2", ... — session identity
    session_number: int  # 1, 2, ...
    participant_id: str  # primary participant "p1" — provisional until Stage 5b
    participant_number: int  # primary participant number
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
    speaker_code: str = ""  # "p1", "m1", "m2", "o1" — per-segment speaker identity
    words: list[Word] = Field(default_factory=list)
    source: str = ""  # "whisper", "srt", "vtt", "docx"
    segment_index: int = -1  # 0-based ordinal within the session transcript


class FullTranscript(BaseModel):
    """Complete transcript for one session, with all segments normalised."""

    session_id: str  # "s1", "s2", ... — session identity
    participant_id: str  # primary participant code
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

    session_id: str  # "s1", "s2", ... — session identity
    participant_id: str  # primary participant code
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

    session_id: str = ""  # "s1", "s2", ... — session identity
    participant_id: str
    start_timecode: float  # seconds
    end_timecode: float  # seconds
    text: str  # verbatim with editorial cleanup applied
    verbatim_excerpt: str = ""  # exact original substring before editorial cleanup
    topic_label: str
    quote_type: QuoteType
    researcher_context: str | None = None  # e.g. "When asked about the dashboard"

    # New sentiment field (v0.7+)
    sentiment: Sentiment | None = None  # Single dominant sentiment, or None if descriptive
    intensity: int = 1  # 1=mild, 2=moderate, 3=strong — kept for future use

    # Segment ordinal — position of the source segment in the transcript (see design-quote-sequences.md)
    segment_index: int = -1  # -1 = unknown (backward compat with pre-v0.11 data)

    # Deprecated fields — kept for backward compatibility with existing intermediate JSON
    intent: QuoteIntent = QuoteIntent.NARRATION
    emotion: EmotionalTone = EmotionalTone.NEUTRAL
    journey_stage: JourneyStage = JourneyStage.OTHER

    def formatted(self, display_name: str | None = None) -> str:
        """Render the quote in final output format."""
        from bristlenose.utils.markdown import EM_DASH, LQUOTE, RQUOTE

        tc = format_timecode(self.start_timecode)
        name = display_name if display_name else self.participant_id
        prefix = f"[{self.researcher_context}] " if self.researcher_context else ""
        return f"{prefix}[{tc}] {LQUOTE}{self.text}{RQUOTE} {EM_DASH} {name}"


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
    report_path: Path | None = None
    people: PeopleFile | None = None
    # Pipeline timing and LLM usage (populated by run/analyze, zero for render)
    elapsed_seconds: float = 0.0
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    llm_calls: int = 0
    llm_model: str = ""
    llm_provider: str = ""
    total_quotes: int = 0


# ---------------------------------------------------------------------------
# People file models (participant registry)
# ---------------------------------------------------------------------------


class PersonComputed(BaseModel):
    """Stats refreshed on every pipeline run."""

    participant_id: str
    session_id: str = ""  # "s1", "s2", ... — which session this entry belongs to
    session_date: datetime
    duration_seconds: float
    words_spoken: int
    pct_words: float  # % of total words across all participants
    pct_time_speaking: float  # % of session duration spent speaking
    source_file: str


class PersonEditable(BaseModel):
    """Human-editable fields — preserved across re-runs."""

    full_name: str = ""
    short_name: str = ""  # display name in reports
    role: str = ""  # job title or main activity
    persona: str = ""  # archetype label
    notes: str = ""


class PersonEntry(BaseModel):
    """One participant: computed stats + human-editable fields."""

    computed: PersonComputed
    editable: PersonEditable = Field(default_factory=PersonEditable)


class PeopleFile(BaseModel):
    """Complete people.yaml structure."""

    generated_by: str = "bristlenose"
    last_updated: datetime = Field(default_factory=datetime.now)
    participants: dict[str, PersonEntry] = Field(default_factory=dict)


# Resolve forward reference: PipelineResult.people uses PeopleFile defined above.
PipelineResult.model_rebuild()


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
