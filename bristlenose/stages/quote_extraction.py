"""Stage 9: LLM-based verbatim quote extraction with editorial cleanup."""

from __future__ import annotations

import asyncio
import logging

from bristlenose.llm.client import LLMClient
from bristlenose.llm.prompts import get_prompt
from bristlenose.llm.structured import QuoteExtractionResult
from bristlenose.models import (
    EmotionalTone,
    ExtractedQuote,
    JourneyStage,
    PiiCleanTranscript,
    QuoteIntent,
    QuoteType,
    Sentiment,
    SessionTopicMap,
    format_timecode,
)
from bristlenose.utils.text import apply_smart_quotes
from bristlenose.utils.timecodes import parse_timecode

logger = logging.getLogger(__name__)


_FAIL_THRESHOLD = 3  # Stop stage after this many consecutive LLM failures


async def extract_quotes(
    transcripts: list[PiiCleanTranscript],
    topic_maps: list[SessionTopicMap],
    llm_client: LLMClient,
    min_quote_words: int = 5,
    concurrency: int = 1,
    errors: list[str] | None = None,
) -> list[ExtractedQuote]:
    """Extract verbatim quotes from all transcripts.

    Args:
        transcripts: PII-cleaned transcripts.
        topic_maps: Topic boundaries for each transcript.
        llm_client: LLM client for analysis.
        min_quote_words: Minimum word count for a quote to be included.
        concurrency: Max concurrent LLM calls (default 1 = sequential).
        errors: Optional list to append error messages to.

    Returns:
        List of all extracted quotes across all sessions.
    """
    # Build a lookup from session_id to topic map
    topic_map_lookup: dict[str, SessionTopicMap] = {
        tm.session_id: tm for tm in topic_maps
    }

    semaphore = asyncio.Semaphore(concurrency)
    stop = asyncio.Event()
    consecutive_failures = 0

    async def _process(
        transcript: PiiCleanTranscript,
    ) -> list[ExtractedQuote]:
        nonlocal consecutive_failures

        async with semaphore:
            if stop.is_set():
                return []

            logger.info(
                "%s: Extracting quotes",
                transcript.session_id,
            )
            topic_map = topic_map_lookup.get(transcript.session_id)
            try:
                quotes = await _extract_single(
                    transcript, topic_map, llm_client, min_quote_words
                )
                consecutive_failures = 0
                logger.info(
                    "%s: Extracted %d quotes",
                    transcript.session_id,
                    len(quotes),
                )
                return quotes
            except Exception as exc:
                logger.debug(
                    "%s: Quote extraction failed: %s",
                    transcript.session_id,
                    exc,
                )
                if errors is not None:
                    errors.append(str(exc))
                consecutive_failures += 1
                if consecutive_failures >= _FAIL_THRESHOLD:
                    logger.warning(
                        "Stopping quote extraction early — %d consecutive failures",
                        consecutive_failures,
                    )
                    stop.set()
                return []

    results = await asyncio.gather(*(_process(t) for t in transcripts))
    # Flatten per-participant quote lists into a single list
    all_quotes: list[ExtractedQuote] = []
    for quotes in results:
        all_quotes.extend(quotes)
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

    _prompt = get_prompt("quote-extraction")

    result = await llm_client.analyze(
        system_prompt=_prompt.system,
        user_prompt=_prompt.user.format(
            topic_boundaries=boundaries_text,
            transcript_text=transcript_text,
        ),
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

        # Parse new sentiment field (v0.7+)
        sentiment: Sentiment | None = None
        if item.sentiment:
            try:
                sentiment = Sentiment(item.sentiment)
            except ValueError:
                sentiment = None
        intensity = max(1, min(3, item.intensity))

        # Parse deprecated fields for backward compatibility
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
                session_id=transcript.session_id,
                participant_id=transcript.participant_id,
                start_timecode=start_tc,
                end_timecode=end_tc,
                text=text,
                verbatim_excerpt=item.verbatim_excerpt or "",
                topic_label=item.topic_label,
                quote_type=quote_type,
                researcher_context=item.researcher_context,
                sentiment=sentiment,
                intensity=intensity,
                # Deprecated fields (backward compat)
                intent=intent,
                emotion=emotion,
                journey_stage=journey_stage,
            )
        )

    return quotes
