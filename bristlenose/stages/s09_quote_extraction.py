"""Stage 9: LLM-based verbatim quote extraction with editorial cleanup."""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from bristlenose.events import StageFailure, StageOutcome
from bristlenose.llm import telemetry
from bristlenose.llm.boundary import wrap_untrusted
from bristlenose.llm.client import LLMClient, TruncatedResponseError
from bristlenose.llm.prompts import get_prompt_template
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
    SpeakerRole,
    TopicBoundary,
    TranscriptSegment,
    format_timecode,
)
from bristlenose.run_lifecycle import _build_cause
from bristlenose.utils.text import apply_smart_quotes
from bristlenose.utils.timecodes import parse_timecode

logger = logging.getLogger(__name__)


_FAIL_THRESHOLD = 3  # Stop stage after this many consecutive LLM failures

# Smart-split (low-output-cap recovery). When a quote-extraction response is
# truncated at the model's output cap (gpt-4o → 16384, Local → ~2–4K), split
# the session and re-extract per chunk, then merge. See
# docs/private/handoffs/chunked-quote-extraction.md.
# Depth 3 ⇒ at most 8 leaf chunks. Rationale (8 Jun 2026 measurement: a dense
# 361-segment gpt-4o session truncated): depth-1 halves (~180 seg) can still
# truncate on the densest sessions; depth-2 quarters (~90 seg) almost always
# fit; depth-3 eighths are insurance. Worst-case sequential LLM calls if EVERY
# chunk at every level truncates is 1+2+4+8 = 15 (depth-first, all-or-nothing),
# each timeout-bounded — but index-based halving (see _split_transcript) halves
# the output each level, so a chunk that fits at depth N never truncates at
# N+1; the 15-call worst case is therefore nearly unreachable in practice.
_SPLIT_MAX_DEPTH = 3
_SPLIT_OVERLAP_FRACTION = 0.1  # 10% boundary overlap absorbs cross-seam quotes
_BOUNDARY_MIDDLE_FRACTION = 0.2  # eligible topic boundaries sit in middle 60%


def _resolve_segment_index(
    start_timecode: float,
    segments: list[TranscriptSegment],
) -> int:
    """Find the segment ordinal that best matches a quote's start timecode.

    For timecoded transcripts, returns the ``segment_index`` of the last
    segment whose ``start_time`` is at or before the quote start, provided
    the quote falls within the segment's time range (with a small tolerance).

    For non-timecoded transcripts (all ``start_time == 0.0``), returns -1
    because timecode matching is meaningless — sequence detection for these
    sources uses ordinal proximity via the ORM transcript segments.

    See ``docs/design-quote-sequences.md`` for rationale.
    """
    if not segments:
        return -1

    # Non-timecoded transcripts: all segments start at 0.0
    if all(s.start_time == 0.0 for s in segments):
        return -1

    # Binary-ish scan: find last segment whose start_time <= start_timecode
    best_idx = -1
    for i, seg in enumerate(segments):
        if seg.start_time <= start_timecode:
            best_idx = i
        else:
            break

    if best_idx < 0:
        return -1

    # Verify the quote falls within or very close to the segment
    seg = segments[best_idx]
    if start_timecode <= seg.end_time + 5.0:
        return seg.segment_index

    return -1


async def extract_quotes(
    transcripts: list[PiiCleanTranscript],
    topic_maps: list[SessionTopicMap],
    llm_client: LLMClient,
    min_quote_words: int = 5,
    concurrency: int = 1,
    errors: list[str] | None = None,
) -> tuple[list[ExtractedQuote], StageOutcome]:
    """Extract verbatim quotes from all transcripts.

    Args:
        transcripts: PII-cleaned transcripts.
        topic_maps: Topic boundaries for each transcript.
        llm_client: LLM client for analysis.
        min_quote_words: Minimum word count for a quote to be included.
        concurrency: Max concurrent LLM calls (default 1 = sequential).
        errors: Optional list to append error messages to (legacy short-form).

    Returns:
        Tuple of (quotes, outcome). ``outcome`` records per-session
        attempts/successes/failures so the orchestrator can decide whether
        to abandon the run.
    """
    # Build a lookup from session_id to topic map
    topic_map_lookup: dict[str, SessionTopicMap] = {
        tm.session_id: tm for tm in topic_maps
    }

    semaphore = asyncio.Semaphore(concurrency)
    stop = asyncio.Event()
    consecutive_failures = 0
    outcome = StageOutcome(attempted=len(transcripts))

    async def _process(
        transcript: PiiCleanTranscript,
    ) -> list[ExtractedQuote]:
        nonlocal consecutive_failures

        async with semaphore:
            if stop.is_set():
                # Early-stop sessions: not attempted at the LLM layer; record
                # as failures with a synthetic cause so abandon arithmetic
                # (succeeded == 0) reflects the user-visible reality.
                outcome.failed.append(StageFailure(
                    session_id=transcript.session_id,
                    cause=_build_cause(
                        RuntimeError("Skipped after consecutive upstream failures"),
                        stage="quote_extraction",
                        provider=llm_client.provider,
                        session_id=transcript.session_id,
                    ),
                ))
                return []

            logger.info(
                "%s: Extracting quotes",
                transcript.session_id,
            )
            topic_map = topic_map_lookup.get(transcript.session_id)
            try:
                with telemetry.session(transcript.participant_id):
                    quotes = await _extract_with_split(
                        transcript, topic_map, llm_client, min_quote_words
                    )
                consecutive_failures = 0
                outcome.succeeded += 1
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
                outcome.failed.append(StageFailure(
                    session_id=transcript.session_id,
                    cause=_build_cause(
                        exc,
                        stage="quote_extraction",
                        provider=llm_client.provider,
                        session_id=transcript.session_id,
                    ),
                ))
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
    return all_quotes, outcome


async def _extract_one_pass(
    transcript: PiiCleanTranscript,
    topic_map: SessionTopicMap | None,
    llm_client: LLMClient,
    min_quote_words: int,
) -> list[ExtractedQuote]:
    """Extract quotes from a single transcript (or one chunk of one).

    Topic boundaries are filtered to the transcript's own time range. On the
    full session this is a no-op (every boundary is in range); on a chunk it
    drops out-of-window boundaries so the prompt's ``boundaries_text`` never
    references topics outside the chunk (Finding 5). This is where the
    filtering lives — sub-transcripts don't carry their own topic map, so the
    recursion passes the full map down and each pass scopes it locally.
    """
    # Format topic boundaries for the prompt, scoped to this transcript's span
    relevant_boundaries = _boundaries_in_range(topic_map, transcript.segments)
    if relevant_boundaries:
        boundaries_text = "\n".join(
            f"- [{format_timecode(b.timecode_seconds)}] "
            f"{b.topic_label} ({b.transition_type.value})"
            for b in relevant_boundaries
        )
    else:
        boundaries_text = "(No topic boundaries identified)"

    # Use the full transcript text (both researcher and participant visible
    # so the LLM understands context, but it must only extract participant quotes)
    transcript_text = transcript.full_text()

    _tmpl = get_prompt_template("quote-extraction")

    result = await llm_client.analyze(
        system_prompt=_tmpl.system,
        user_prompt=_tmpl.user.format(
            topic_boundaries=boundaries_text,
            transcript_text=wrap_untrusted("transcript", transcript_text),
        ),
        response_model=QuoteExtractionResult,
        prompt_template=_tmpl,
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

        # Resolve segment ordinal (see design-quote-sequences.md)
        seg_idx = _resolve_segment_index(start_tc, transcript.segments)

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
                segment_index=seg_idx,
                # Deprecated fields (backward compat)
                intent=intent,
                emotion=emotion,
                journey_stage=journey_stage,
            )
        )

    return quotes


# ---------------------------------------------------------------------------
# Smart-split on output-cap truncation (low-output-cap model recovery)
# ---------------------------------------------------------------------------


async def _extract_with_split(
    transcript: PiiCleanTranscript,
    topic_map: SessionTopicMap | None,
    llm_client: LLMClient,
    min_quote_words: int,
    depth: int = 0,
) -> list[ExtractedQuote]:
    """Extract quotes, splitting the session on output-cap truncation.

    Reactive: one normal pass first; only on ``TruncatedResponseError`` do we
    split and re-extract per chunk (Map-Reduce, no cross-chunk context). The
    per-session semaphore slot is held across the whole recursive chain by the
    caller (``extract_quotes._process``) — never released between sub-calls, so
    depth-N chains don't concurrently hammer the API.
    """
    try:
        return await _extract_one_pass(
            transcript, topic_map, llm_client, min_quote_words
        )
    except TruncatedResponseError:
        if depth >= _SPLIT_MAX_DEPTH:
            # Re-raise: the outer _process records exactly ONE StageFailure for
            # this session (Finding 10), categorised OUTPUT_TRUNCATED.
            raise
        chunks, reason = _split_transcript(
            transcript, topic_map, _SPLIT_OVERLAP_FRACTION
        )
        logger.info(
            "quote_extraction_split | session=%s | depth=%d | chunks=%d | reason=%s",
            transcript.session_id,
            depth + 1,
            len(chunks),
            reason,
        )
        # ALL-OR-NOTHING per session: if any chunk re-raises after exhausting
        # its own depth budget, the whole session fails (Decision F3). The full
        # topic map is passed down; each pass scopes it to its own span.
        results: list[ExtractedQuote] = []
        for chunk in chunks:
            results.extend(
                await _extract_with_split(
                    chunk, topic_map, llm_client, min_quote_words, depth + 1
                )
            )
        # Dedup runs at every recursion level; each re-resolves segment_index
        # against *this* level's segments. The outermost call (depth 0) resolves
        # against the full transcript and is authoritative — intermediate
        # resolutions are harmless but not globally final. Don't add an
        # early-return that would let an intermediate (chunk-local) resolution
        # be the last word.
        return _dedupe_overlapping_quotes(results, transcript.segments)


def _boundaries_in_range(
    topic_map: SessionTopicMap | None,
    segments: list[TranscriptSegment],
) -> list[TopicBoundary]:
    """Topic boundaries whose timecode falls within the segments' time span."""
    if not topic_map or not topic_map.boundaries:
        return []
    if not segments:
        return list(topic_map.boundaries)
    lo = min(s.start_time for s in segments)
    hi = max(s.end_time for s in segments)
    return [b for b in topic_map.boundaries if lo <= b.timecode_seconds <= hi]


def _has_participant_speech(segments: list[TranscriptSegment]) -> bool:
    """True if any segment is participant-attributable speech.

    Mirrors ``coverage._is_participant_code``: an explicit PARTICIPANT role, a
    ``p``-prefixed speaker code, or untagged speech (legacy / single-speaker
    transcripts, where everything is the participant). A chunk that is
    moderator/observer-only has no extractable quotes — treated as a split bug,
    not a silent zero-quote result.
    """
    for s in segments:
        if s.speaker_role == SpeakerRole.PARTICIPANT:
            return True
        code = s.speaker_code or ""
        if code.startswith("p"):
            return True
        if not code and s.speaker_role == SpeakerRole.UNKNOWN:
            return True
    return False


def _adjacent_gap(
    t: float,
    boundary_times: list[float],
    start: float,
    end: float,
) -> float:
    """Largest gap to a neighbouring boundary (or span edge) around time ``t``.

    A boundary bordering a long mono-topic run scores high, so the tiebreaker
    prefers splitting next to long uninterrupted runs over clean ones.
    """
    points = sorted({start, end, *boundary_times})
    try:
        i = points.index(t)
    except ValueError:
        return 0.0
    left = points[i] - points[i - 1] if i > 0 else 0.0
    right = points[i + 1] - points[i] if i < len(points) - 1 else 0.0
    return max(left, right)


def _choose_split_time(
    topic_map: SessionTopicMap | None,
    segments: list[TranscriptSegment],
    start: float,
    end: float,
    span: float,
) -> tuple[float, Literal["topic", "halves"]]:
    """Pick a split timecode. Tier 1: s08 topic boundary; tier 2: halves."""
    eligible: list[TopicBoundary] = []
    if topic_map and topic_map.boundaries and span > 0:
        lo = start + _BOUNDARY_MIDDLE_FRACTION * span
        hi = end - _BOUNDARY_MIDDLE_FRACTION * span
        eligible = [
            b for b in topic_map.boundaries if lo <= b.timecode_seconds <= hi
        ]

    if eligible:
        all_times = [b.timecode_seconds for b in topic_map.boundaries]  # type: ignore[union-attr]
        best = max(
            eligible,
            key=lambda b: (
                b.confidence,
                _adjacent_gap(b.timecode_seconds, all_times, start, end),
            ),
        )
        return best.timecode_seconds, "topic"

    # Mechanical halves — segment-count midpoint. Session-specific timecode
    # (durations differ), which the s10/s11 cross-session correction relies on.
    # CRITICAL: never a fixed clock-time cut — that correlates split bias
    # across the cohort and defeats the voting argument.
    mid_idx = len(segments) // 2
    return segments[mid_idx].start_time, "halves"


def _split_transcript(
    transcript: PiiCleanTranscript,
    topic_map: SessionTopicMap | None,
    overlap_fraction: float,
) -> tuple[list[PiiCleanTranscript], Literal["topic", "halves"]]:
    """Split a transcript at the best available natural boundary.

    Two-tier hierarchy (see handoff): high-confidence s08 topic boundary in the
    middle 60% (tiebreak by bordering the longest mono-topic run) → mechanical
    halves. The topic tier cuts by time around the boundary; the halves tier
    cuts by segment index (output scales with segment count, not elapsed time).
    Either way both chunks share a ~10% overlap band so cross-seam quotes
    survive; ``segment_index`` values are preserved from the parent.

    Returns ``(chunks, reason)`` with ``reason`` a closed enum so the re-id-key
    log line stays bristlenose-controlled (Finding 16).

    Raises:
        ValueError("empty chunk"): if either chunk has no participant speech
            (Finding 7) — the caller records a StageFailure rather than
            silently producing zero quotes.
    """
    segments = transcript.segments
    if len(segments) < 2:
        raise ValueError("empty chunk")

    start = min(s.start_time for s in segments)
    end = max(s.end_time for s in segments)
    span = end - start
    if span <= 0:
        # No temporal extent to split on (e.g. a non-timecoded transcript where
        # every segment starts at 0.0). Splitting can't reduce output here —
        # fail loudly rather than recurse fruitlessly to the depth cap.
        raise ValueError("empty chunk")

    split_time, reason = _choose_split_time(topic_map, segments, start, end, span)

    if reason == "topic":
        # Cut by time around the boundary. Safe from "one chunk keeps almost
        # everything" because tier-1 eligibility already bounds the boundary to
        # the middle 60% of the span (so split_time ± overlap stays inside the
        # transcript with room to spare on both sides).
        overlap = overlap_fraction * span
        left_segs = [s for s in segments if s.start_time <= split_time + overlap]
        right_segs = [s for s in segments if s.start_time >= split_time - overlap]
    else:
        # Mechanical halves: cut by SEGMENT INDEX, not time. Output scales with
        # the amount of speech (≈ segment count), and an index split guarantees
        # each half is ~half the segments regardless of how speech is
        # distributed in time. A time cut around the count-midpoint timecode
        # could pull nearly all segments into one chunk when density is
        # back-loaded (long sparse intro, dense tail) — that stalls the
        # recursion at full depth without ever shrinking the output. Index
        # halving can't stall and can't empty a half on lopsided density.
        logger.warning(
            "split_fallback_halves | session=%s | duration=%.1f",
            transcript.session_id,
            span,
        )
        mid_idx = len(segments) // 2
        overlap_count = max(1, round(len(segments) * overlap_fraction))
        left_segs = segments[: mid_idx + overlap_count]
        right_segs = segments[mid_idx - overlap_count :]

    if not _has_participant_speech(left_segs) or not _has_participant_speech(
        right_segs
    ):
        raise ValueError("empty chunk")

    left = transcript.model_copy(update={"segments": left_segs})
    right = transcript.model_copy(update={"segments": right_segs})
    return [left, right], reason


def _dedupe_overlapping_quotes(
    quotes: list[ExtractedQuote],
    full_segments: list[TranscriptSegment],
) -> list[ExtractedQuote]:
    """Merge quotes extracted from overlapping chunks.

    Dedup key is ``verbatim_excerpt`` (Decision F6 — the original substring
    before editorial cleanup, so smart-quote/whitespace variants of ``text``
    collapse). Quotes with an empty ``verbatim_excerpt`` can't be keyed and are
    all kept. After dedup, ``segment_index`` is re-resolved against the FULL
    original transcript so global ordinals are correct (Finding 22).
    """
    seen: set[str] = set()
    merged: list[ExtractedQuote] = []
    for q in quotes:
        key = q.verbatim_excerpt
        if key:
            if key in seen:
                continue
            seen.add(key)
        new_idx = _resolve_segment_index(q.start_timecode, full_segments)
        merged.append(q.model_copy(update={"segment_index": new_idx}))
    return merged
