"""Stage 9: LLM-based verbatim quote extraction with editorial cleanup."""

from __future__ import annotations

import logging

from bristlenose.llm.client import LLMClient
from bristlenose.llm.prompts import QUOTE_EXTRACTION_PROMPT
from bristlenose.llm.structured import QuoteExtractionResult
from bristlenose.models import (
    EmotionalTone,
    ExtractedQuote,
    JourneyStage,
    PiiCleanTranscript,
    QuoteIntent,
    QuoteType,
    SessionTopicMap,
    format_timecode,
)
from bristlenose.utils.text import apply_smart_quotes
from bristlenose.utils.timecodes import parse_timecode

logger = logging.getLogger(__name__)


async def extract_quotes(
    transcripts: list[PiiCleanTranscript],
    topic_maps: list[SessionTopicMap],
    llm_client: LLMClient,
    min_quote_words: int = 5,
) -> list[ExtractedQuote]:
    """Extract verbatim quotes from all transcripts.

    Args:
        transcripts: PII-cleaned transcripts.
        topic_maps: Topic boundaries for each transcript.
        llm_client: LLM client for analysis.
        min_quote_words: Minimum word count for a quote to be included.

    Returns:
        List of all extracted quotes across all sessions.
    """
    # Build a lookup from participant_id to topic map
    topic_map_lookup: dict[str, SessionTopicMap] = {
        tm.participant_id: tm for tm in topic_maps
    }

    all_quotes: list[ExtractedQuote] = []

    for transcript in transcripts:
        logger.info(
            "%s: Extracting quotes",
            transcript.participant_id,
        )

        topic_map = topic_map_lookup.get(transcript.participant_id)

        try:
            quotes = await _extract_single(
                transcript, topic_map, llm_client, min_quote_words
            )
            all_quotes.extend(quotes)
            logger.info(
                "%s: Extracted %d quotes",
                transcript.participant_id,
                len(quotes),
            )
        except Exception as exc:
            logger.error(
                "%s: Quote extraction failed: %s",
                transcript.participant_id,
                exc,
            )

    return all_quotes


async def _extract_single(
    transcript: PiiCleanTranscript,
    topic_map: SessionTopicMap | None,
    llm_client: LLMClient,
    min_quote_words: int,
) -> list[ExtractedQuote]:
    """Extract quotes from a single transcript."""
    # Format topic boundaries for the prompt
    if topic_map and topic_map.boundaries:
        boundaries_text = "\n".join(
            f"- [{format_timecode(b.timecode_seconds)}] "
            f"{b.topic_label} ({b.transition_type.value})"
            for b in topic_map.boundaries
        )
    else:
        boundaries_text = "(No topic boundaries identified)"

    # Use the full transcript text (both researcher and participant visible
    # so the LLM understands context, but it must only extract participant quotes)
    transcript_text = transcript.full_text()

    prompt = QUOTE_EXTRACTION_PROMPT.format(
        topic_boundaries=boundaries_text,
        transcript_text=transcript_text,
    )

    result = await llm_client.analyze(
        system_prompt=(
            "You are an expert user-research analyst extracting verbatim quotes. "
            "You follow the editorial policy precisely: preserve authentic human "
            "expression, remove filler with ellipsis, insert [clarifying words] "
            "in square brackets, and never paraphrase or sanitise."
        ),
        user_prompt=prompt,
        response_model=QuoteExtractionResult,
    )

    # Convert LLM output to our domain models
    quotes: list[ExtractedQuote] = []
    for item in result.quotes:
        # Parse timecodes
        try:
            start_tc = parse_timecode(item.start_timecode)
        except ValueError:
            start_tc = 0.0
        try:
            end_tc = parse_timecode(item.end_timecode)
        except ValueError:
            end_tc = start_tc

        # Parse quote type
        try:
            quote_type = QuoteType(item.quote_type)
        except ValueError:
            quote_type = QuoteType.SCREEN_SPECIFIC

        # Parse enrichment fields
        try:
            intent = QuoteIntent(item.intent)
        except ValueError:
            intent = QuoteIntent.NARRATION
        try:
            emotion = EmotionalTone(item.emotion)
        except ValueError:
            emotion = EmotionalTone.NEUTRAL
        try:
            journey_stage = JourneyStage(item.journey_stage)
        except ValueError:
            journey_stage = JourneyStage.OTHER
        intensity = max(1, min(3, item.intensity))

        # Skip very short quotes
        word_count = len(item.text.split())
        if word_count < min_quote_words:
            logger.debug(
                "Skipping short quote (%d words): %s",
                word_count,
                item.text[:50],
            )
            continue

        # Apply smart quotes to the text (curly quotes)
        text = apply_smart_quotes(item.text)

        quotes.append(
            ExtractedQuote(
                participant_id=transcript.participant_id,
                start_timecode=start_tc,
                end_timecode=end_tc,
                text=text,
                topic_label=item.topic_label,
                quote_type=quote_type,
                researcher_context=item.researcher_context,
                intent=intent,
                emotion=emotion,
                intensity=intensity,
                journey_stage=journey_stage,
            )
        )

    return quotes
