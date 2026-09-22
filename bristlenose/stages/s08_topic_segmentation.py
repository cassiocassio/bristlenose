"""Stage 8: LLM-based topic/screen transition identification."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from bristlenose.events import StageFailure, StageOutcome
from bristlenose.llm import telemetry
from bristlenose.llm.boundary import wrap_untrusted
from bristlenose.llm.client import LLMClient
from bristlenose.llm.output_language import output_language_steer
from bristlenose.llm.prompts import get_prompt_template
from bristlenose.llm.structured import TopicSegmentationResult
from bristlenose.models import (
    PiiCleanTranscript,
    SessionTopicMap,
    TopicBoundary,
    TransitionType,
)
from bristlenose.run_lifecycle import _build_cause
from bristlenose.stages.timecode_guard import repair_timecode, timecode_ceiling
from bristlenose.utils.timecodes import parse_timecode

logger = logging.getLogger(__name__)


_FAIL_THRESHOLD = 3  # Stop stage after this many consecutive LLM failures


async def segment_topics(
    transcripts: list[PiiCleanTranscript],
    llm_client: LLMClient,
    concurrency: int = 1,
    errors: list[str] | None = None,
    *,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[list[SessionTopicMap], StageOutcome]:
    """Identify topic/screen transitions in each transcript.

    Args:
        transcripts: PII-cleaned transcripts to analyse.
        llm_client: LLM client for analysis.
        concurrency: Max concurrent LLM calls (default 1 = sequential).
        errors: Optional list to append error messages to (legacy short-form).
        on_progress: Optional ``callback(completed, total)`` fired as each
            session finishes — the same shape ``transcribe_sessions`` and
            ``remove_pii`` use, so the caller's handler is their sibling rather
            than a third convention. **Completions, not position:** this stage
            runs ``concurrency`` sessions at once and they finish out of order,
            so ``completed`` counts how many are done and never identifies
            which. That is what an "N of M" display needs; it is not a
            "now on session N".

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

    _completed = 0

    async def _process_counted(transcript: PiiCleanTranscript) -> SessionTopicMap:
        # `finally`, so the count advances on a handled failure too — the
        # session is done being attempted either way, and a count that stalls
        # on the one that failed is worse than no count.
        nonlocal _completed
        try:
            return await _process(transcript)
        finally:
            _completed += 1
            if on_progress is not None:
                on_progress(_completed, len(transcripts))

    results = list(
        await asyncio.gather(*(_process_counted(t) for t in transcripts))
    )
    return results, outcome


async def _segment_single(
    transcript: PiiCleanTranscript,
    llm_client: LLMClient,
) -> SessionTopicMap:
    """Segment topics for a single transcript."""
    transcript_text = transcript.full_text()

    _tmpl = get_prompt_template("topic-segmentation")

    result = await llm_client.analyze(
        # Generated text follows the UI language (V1, 22 Sep 2026). Empty for
        # English, so the prompt stays byte-identical to the one that shipped
        # before this existed — see bristlenose/llm/output_language.py.
        system_prompt=_tmpl.system + output_language_steer(),
        user_prompt=_tmpl.user.format(transcript_text=wrap_untrusted("transcript", transcript_text)),
        response_model=TopicSegmentationResult,
        prompt_template=_tmpl,
    )

    # Convert LLM output to our domain models
    ceiling = timecode_ceiling(transcript)
    repairs = {"scaled": 0, "dropped": 0, "unparseable": 0}
    boundaries: list[TopicBoundary] = []
    for item in result.boundaries:
        try:
            timecode_seconds = parse_timecode(item.timecode)
        except ValueError:
            logger.warning(
                "boundary_timecode_unparseable | session=%s | raw=%r",
                transcript.session_id, item.timecode,
            )
            repairs["unparseable"] += 1
            continue

        # See stages/timecode_guard.py. `drop` rather than s09's `clamp`: a
        # clamped boundary would invent a topic transition at the session end and
        # then PASS `_boundaries_in_range`, which is worse than losing it.
        timecode_seconds, outcome = repair_timecode(
            timecode_seconds, ceiling,
            session_id=transcript.session_id,
            field="timecode", raw=item.timecode,
            kind="boundary", out_of_range="drop",
        )
        if outcome:
            repairs[outcome] += 1
            if outcome == "dropped":
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

    if any(repairs.values()):
        # s09's sibling line. `boundaries` is the model's own output count — the
        # population the rate is measured over, before any drop above.
        logger.warning(
            "boundary_timecodes_repaired | session=%s | boundaries=%d | scaled=%d | "
            "dropped=%d | unparseable=%d",
            transcript.session_id, len(result.boundaries),
            repairs["scaled"], repairs["dropped"], repairs["unparseable"],
        )

    # Sort by timecode
    boundaries.sort(key=lambda b: b.timecode_seconds)

    return SessionTopicMap(
        session_id=transcript.session_id,
        participant_id=transcript.participant_id,
        boundaries=boundaries,
    )
