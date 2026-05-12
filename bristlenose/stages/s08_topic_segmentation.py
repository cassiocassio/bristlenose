"""Stage 8: LLM-based topic/screen transition identification."""

from __future__ import annotations

import asyncio
import logging

from bristlenose.events import StageFailure, StageOutcome
from bristlenose.llm import telemetry
from bristlenose.llm.boundary import wrap_untrusted
from bristlenose.llm.client import LLMClient
from bristlenose.llm.prompts import get_prompt_template
from bristlenose.llm.structured import TopicSegmentationResult
from bristlenose.models import (
    PiiCleanTranscript,
    SessionTopicMap,
    TopicBoundary,
    TransitionType,
)
from bristlenose.run_lifecycle import _build_cause
from bristlenose.utils.timecodes import parse_timecode

logger = logging.getLogger(__name__)


_FAIL_THRESHOLD = 3  # Stop stage after this many consecutive LLM failures


async def segment_topics(
    transcripts: list[PiiCleanTranscript],
    llm_client: LLMClient,
    concurrency: int = 1,
    errors: list[str] | None = None,
) -> tuple[list[SessionTopicMap], StageOutcome]:
    """Identify topic/screen transitions in each transcript.

    Args:
        transcripts: PII-cleaned transcripts to analyse.
        llm_client: LLM client for analysis.
        concurrency: Max concurrent LLM calls (default 1 = sequential).
        errors: Optional list to append error messages to (legacy short-form).

    Returns:
        Tuple of (topic_maps, outcome). ``outcome`` records per-session
        attempts/successes/failures so the orchestrator can decide whether
        to abandon the run when every topic-segmentation call fails.
    """
    semaphore = asyncio.Semaphore(concurrency)
    stop = asyncio.Event()
    consecutive_failures = 0
    outcome = StageOutcome(attempted=len(transcripts))

    async def _process(transcript: PiiCleanTranscript) -> SessionTopicMap:
        nonlocal consecutive_failures

        empty = SessionTopicMap(
            session_id=transcript.session_id,
            participant_id=transcript.participant_id,
            boundaries=[],
        )

        async with semaphore:
            if stop.is_set():
                # Early-stop sessions: not attempted at the LLM layer; record
                # as failures with a synthetic cause so abandon arithmetic
                # (succeeded == 0) reflects the user-visible reality.
                outcome.failed.append(StageFailure(
                    session_id=transcript.session_id,
                    cause=_build_cause(
                        RuntimeError("Skipped after consecutive upstream failures"),
                        stage="topic_segmentation",
                        provider=llm_client.provider,
                        session_id=transcript.session_id,
                    ),
                ))
                return empty

            logger.info(
                "%s: Segmenting topics (duration=%.0fs)",
                transcript.session_id,
                transcript.duration_seconds,
            )
            try:
                with telemetry.session(transcript.participant_id):
                    topic_map = await _segment_single(transcript, llm_client)
                consecutive_failures = 0
                outcome.succeeded += 1
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
                outcome.failed.append(StageFailure(
                    session_id=transcript.session_id,
                    cause=_build_cause(
                        exc,
                        stage="topic_segmentation",
                        provider=llm_client.provider,
                        session_id=transcript.session_id,
                    ),
                ))
                consecutive_failures += 1
                if consecutive_failures >= _FAIL_THRESHOLD:
                    logger.warning(
                        "Stopping topic segmentation early — %d consecutive failures",
                        consecutive_failures,
                    )
                    stop.set()
                return empty

    results = list(await asyncio.gather(*(_process(t) for t in transcripts)))
    return results, outcome


async def _segment_single(
    transcript: PiiCleanTranscript,
    llm_client: LLMClient,
) -> SessionTopicMap:
    """Segment topics for a single transcript."""
    transcript_text = transcript.full_text()

    _tmpl = get_prompt_template("topic-segmentation")

    result = await llm_client.analyze(
        system_prompt=_tmpl.system,
        user_prompt=_tmpl.user.format(transcript_text=wrap_untrusted("transcript", transcript_text)),
        response_model=TopicSegmentationResult,
        prompt_template=_tmpl,
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
