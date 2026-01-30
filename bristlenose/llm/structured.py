"""Pydantic models for structured LLM output parsing."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Speaker identification (Stage 5b)
# ---------------------------------------------------------------------------


class SpeakerRoleItem(BaseModel):
    """A single speaker-to-role assignment."""

    speaker_label: str = Field(description="The speaker label from the transcript (e.g. 'Speaker A', 'John Smith')")
    role: str = Field(description="One of: researcher, participant, observer")
    reasoning: str = Field(description="Brief explanation for the assignment")


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
    intent: str = Field(
        default="narration",
        description=(
            "Utterance type: narration, confusion, judgment, "
            "frustration, delight, suggestion, task_management"
        ),
    )
    emotion: str = Field(
        default="neutral",
        description=(
            "Emotional tone: neutral, frustrated, delighted, "
            "confused, amused, sarcastic, critical"
        ),
    )
    intensity: int = Field(
        default=1,
        description="Reaction intensity: 1 (low/neutral), 2 (moderate), 3 (high/strong)",
        ge=1,
        le=3,
    )
    journey_stage: str = Field(
        default="other",
        description=(
            "User journey stage: landing, browse, search, "
            "product_detail, cart, checkout, error_recovery, other"
        ),
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
        description="Indices of quotes (0-based) that belong to this theme. A quote may appear in multiple themes."
    )


class ThematicGroupingResult(BaseModel):
    """LLM output for thematic grouping of contextual quotes."""

    themes: list[ThemeGroupItem] = Field(
        description="Emergent themes identified across all contextual quotes"
    )
