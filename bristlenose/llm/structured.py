"""Pydantic models for structured LLM output parsing."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Speaker identification (Stage 5b)
# ---------------------------------------------------------------------------


class SpeakerRoleItem(BaseModel):
    """A single speaker-to-role assignment with optional name extraction."""

    speaker_label: str = Field(
        description="The speaker label from the transcript (e.g. 'Speaker A', 'John Smith')"
    )
    role: str = Field(description="One of: researcher, participant, observer")
    reasoning: str = Field(description="Brief explanation for the assignment")
    person_name: str = Field(
        default="",
        description=(
            "The person's real name if mentioned in the transcript "
            "(e.g. from a self-introduction like 'Hi, I'm Sarah'). "
            "Empty string if unknown."
        ),
    )
    job_title: str = Field(
        default="",
        description=(
            "The person's job title or professional role if mentioned "
            "(e.g. 'product manager', 'UX designer'). "
            "Empty string if unknown."
        ),
    )


class SpeakerRoleAssignment(BaseModel):
    """LLM output for speaker role identification."""

    assignments: list[SpeakerRoleItem] = Field(description="Role assignment for each speaker")


# ---------------------------------------------------------------------------
# Topic segmentation (Stage 8)
# ---------------------------------------------------------------------------


class TopicBoundaryItem(BaseModel):
    """A single topic transition point."""

    timecode: str = Field(description="Timestamp where the transition occurs (HH:MM:SS)")
    topic_label: str = Field(description="Concise 3-8 word label for the new topic or screen")
    transition_type: str = Field(
        description="One of: screen_change, topic_shift, task_change, general_context"
    )
    confidence: float = Field(
        description="Confidence score 0.0-1.0",
        ge=0.0,
        le=1.0,
    )


class TopicSegmentationResult(BaseModel):
    """LLM output for topic segmentation of one transcript."""

    boundaries: list[TopicBoundaryItem] = Field(
        description="All topic/screen transitions found in the transcript, in chronological order"
    )


# ---------------------------------------------------------------------------
# Quote extraction (Stage 9)
# ---------------------------------------------------------------------------


class ExtractedQuoteItem(BaseModel):
    """A single extracted quote with editorial cleanup applied."""

    start_timecode: str = Field(description="Start timestamp of the quote (HH:MM:SS)")
    end_timecode: str = Field(description="End timestamp of the quote (HH:MM:SS)")
    text: str = Field(
        description=(
            "The verbatim quote text with editorial cleanup: "
            "filler words replaced with '...', "
            "gentle grammar fixes with [inserted words] in square brackets, "
            "preserving natural emotion and expression"
        )
    )
    verbatim_excerpt: str = Field(
        default="",
        description=(
            "The EXACT original substring from the transcript that this quote "
            "is based on, before any editorial cleanup. Copy-paste the "
            "participant's words verbatim — including filler words, grammar "
            "errors, and disfluencies. Must be a contiguous substring of the "
            "transcript text."
        ),
    )
    topic_label: str = Field(description="The topic/screen this quote relates to")
    quote_type: str = Field(description="One of: screen_specific, general_context")
    researcher_context: str | None = Field(
        default=None,
        description=(
            "Optional context from the researcher's question, "
            "e.g. 'When asked about the settings page'. "
            "Only include if the quote is unintelligible without it."
        ),
    )
    # New sentiment field (v0.7+)
    sentiment: str | None = Field(
        default=None,
        description=(
            "Single dominant sentiment: frustration, confusion, doubt, surprise, "
            "satisfaction, delight, confidence. Leave empty/null if purely descriptive."
        ),
    )
    intensity: int = Field(
        default=1,
        description="Sentiment intensity: 1 (mild), 2 (moderate), 3 (strong)",
        ge=1,
        le=3,
    )
    # Deprecated fields — kept for backward compatibility
    intent: str = Field(
        default="narration",
        description="DEPRECATED: use sentiment instead",
    )
    emotion: str = Field(
        default="neutral",
        description="DEPRECATED: use sentiment instead",
    )
    journey_stage: str = Field(
        default="other",
        description="DEPRECATED",
    )


class QuoteExtractionResult(BaseModel):
    """LLM output for quote extraction from one transcript."""

    quotes: list[ExtractedQuoteItem] = Field(
        description="All substantive verbatim quotes extracted from the participant's speech"
    )


# ---------------------------------------------------------------------------
# Quote clustering by screen (Stage 10)
# ---------------------------------------------------------------------------


class ScreenClusterItem(BaseModel):
    """A screen/task cluster with assigned quote indices."""

    screen_label: str = Field(description="Normalised label for this screen or task")
    description: str = Field(description="Brief 1-2 sentence description of this screen/task")
    display_order: int = Field(description="Order in the logical product flow (1-based)")
    quote_indices: list[int] = Field(
        description="Indices of quotes (0-based) that belong to this cluster"
    )


class ScreenClusteringResult(BaseModel):
    """LLM output for clustering screen-specific quotes."""

    clusters: list[ScreenClusterItem] = Field(
        description="Screen clusters ordered by logical product flow"
    )


# ---------------------------------------------------------------------------
# Thematic grouping (Stage 11)
# ---------------------------------------------------------------------------


class ThemeGroupItem(BaseModel):
    """A theme group with assigned quote indices."""

    theme_label: str = Field(description="Concise label for this theme")
    description: str = Field(description="Brief 1-2 sentence description of this theme")
    quote_indices: list[int] = Field(
        description="Indices of quotes (0-based) that belong to this theme. Each quote should appear in exactly one theme."
    )


class ThematicGroupingResult(BaseModel):
    """LLM output for thematic grouping of contextual quotes."""

    themes: list[ThemeGroupItem] = Field(
        description="Emergent themes identified across all contextual quotes"
    )


# ---------------------------------------------------------------------------
# AutoCode — codebook tag application (serve mode)
# ---------------------------------------------------------------------------


class AutoCodeTagAssignment(BaseModel):
    """A single tag assignment for one quote in an AutoCode batch."""

    quote_index: int = Field(description="0-based index of the quote in the batch")
    tag_name: str = Field(
        description=(
            "The codebook tag name that best matches this quote. "
            "Always return the single best-matching tag — use a low "
            "confidence score (0.1-0.3) when the match is weak."
        )
    )
    confidence: float = Field(
        description="Confidence score 0.0-1.0 for this assignment",
        ge=0.0,
        le=1.0,
    )
    rationale: str = Field(
        description=(
            "Brief 1-sentence explanation for why this tag was chosen, "
            "referencing specific words in the quote and explaining why "
            "adjacent tags were ruled out"
        )
    )


class AutoCodeBatchResult(BaseModel):
    """LLM output for a batch of quote-to-tag assignments."""

    assignments: list[AutoCodeTagAssignment] = Field(
        description="Tag assignment for each quote in the batch"
    )

    @field_validator("assignments", mode="before")
    @classmethod
    def _parse_stringified_json(cls, v: object) -> object:
        """Some LLM providers double-serialize nested arrays as JSON strings."""
        if isinstance(v, str):
            return json.loads(v)
        return v


# ---------------------------------------------------------------------------
# Signal elaboration (serve mode — analysis page)
# ---------------------------------------------------------------------------


class SignalElaborationItem(BaseModel):
    """One elaboration for a single signal card."""

    signal_index: int = Field(
        description="0-based index matching the input signal order"
    )
    signal_name: str = Field(
        description=(
            "2-4 word interpretive name for this signal. "
            "Use the group's analytical vocabulary, not raw quote words."
        )
    )
    pattern: str = Field(
        description="One of: success, gap, tension, recovery"
    )
    elaboration: str = Field(
        description=(
            "Exactly one sentence. Structure: assertion clause || evidence/nuance. "
            "The || delimiter separates the bold opening (a self-contained finding) "
            "from the regular continuation (supporting detail). "
            "Place || at the first natural punctuation break: em dash, comma "
            "before a dependent clause, or opening parenthetical."
        )
    )


class SignalElaborationResult(BaseModel):
    """LLM output for a batch of signal elaborations."""

    elaborations: list[SignalElaborationItem] = Field(
        description="One elaboration per input signal, in order"
    )

    @field_validator("elaborations", mode="before")
    @classmethod
    def _parse_stringified_json(cls, v: object) -> object:
        """Some LLM providers double-serialize nested arrays as JSON strings."""
        if isinstance(v, str):
            return json.loads(v)
        return v
