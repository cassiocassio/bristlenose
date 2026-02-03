"""Stage 8: LLM-based topic/screen transition identification."""

from __future__ import annotations

import asyncio
import logging

from bristlenose.llm.client import LLMClient
from bristlenose.llm.prompts import TOPIC_SEGMENTATION_PROMPT
from bristlenose.llm.structured import TopicSegmentationResult
from bristlenose.models import (
    PiiCleanTranscript,
    SessionTopicMap,
    TopicBoundary,
    TransitionType,
)
from bristlenose.utils.timecodes import parse_timecode

logger = logging.getLogger(__name__)


async def segment_topics(
    transcripts: list[PiiCleanTranscript],
    llm_client: LLMClient,
    concurrency: int = 1,
    errors: list[str] | None = None,
) -> list[SessionTopicMap]:
    """Identify topic/screen transitions in each transcript.

    Args:
        transcripts: PII-cleaned transcripts to analyse.
        llm_client: LLM client for analysis.
        concurrency: Max concurrent LLM calls (default 1 = sequential).
        errors: Optional list to append error messages to.

    Returns:
        List of SessionTopicMap objects, one per transcript.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _process(transcript: PiiCleanTranscript) -> SessionTopicMap:
        async with semaphore:
            logger.info(
                "%s: Segmenting topics (duration=%.0fs)",
                transcript.session_id,
                transcript.duration_seconds,
            )
            try:
                topic_map = await _segment_single(transcript, llm_client)
                logger.info(
                    "%s: Found %d topic boundaries",
                    transcript.session_id,
                    len(topic_map.boundaries),
                )
                return topic_map
            except Exception as exc:
                logger.debug(
                    "%s: Topic segmentation failed: %s",
                    transcript.session_id,
                    exc,
                )
                if errors is not None:
                    errors.append(str(exc))
                return SessionTopicMap(
                    session_id=transcript.session_id,
                    participant_id=transcript.participant_id,
                    boundaries=[],
                )

    return list(await asyncio.gather(*(_process(t) for t in transcripts)))


async def _segment_single(
    transcript: PiiCleanTranscript,
    llm_client: LLMClient,
) -> SessionTopicMap:
    """Segment topics for a single transcript."""
    transcript_text = transcript.full_text()

    prompt = TOPIC_SEGMENTATION_PROMPT.format(
        transcript_text=transcript_text,
    )

    result = await llm_client.analyze(
        system_prompt=(
            "You are an expert user-research analyst. "
            "You identify topic and screen transitions in research interview transcripts."
        ),
        user_prompt=prompt,
        response_model=TopicSegmentationResult,
    )

    # Convert LLM output to our domain models
    boundaries: list[TopicBoundary] = []
    for item in result.boundaries:
        try:
            timecode_seconds = parse_timecode(item.timecode)
        except ValueError:
            logger.warning(
                "Could not parse timecode %r, skipping boundary",
                item.timecode,
            )
            continue

        try:
            transition_type = TransitionType(item.transition_type)
        except ValueError:
            transition_type = TransitionType.TOPIC_SHIFT

        boundaries.append(
            TopicBoundary(
                timecode_seconds=timecode_seconds,
                topic_label=item.topic_label,
                transition_type=transition_type,
                confidence=item.confidence,
            )
        )

    # Sort by timecode
    boundaries.sort(key=lambda b: b.timecode_seconds)

    return SessionTopicMap(
        session_id=transcript.session_id,
        participant_id=transcript.participant_id,
        boundaries=boundaries,
    )
