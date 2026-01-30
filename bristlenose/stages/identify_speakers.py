"""Stage 5b: Identify speaker roles (researcher vs participant vs observer)."""

from __future__ import annotations

import logging

from bristlenose.models import SpeakerRole, TranscriptSegment

logger = logging.getLogger(__name__)

# Keywords suggesting a researcher/interviewer role
_RESEARCHER_PHRASES = [
    "can you tell me",
    "could you tell me",
    "what do you think",
    "how do you feel",
    "walk me through",
    "describe for me",
    "let me show you",
    "i'm going to show",
    "let's move on to",
    "next i'd like",
    "next we're going to",
    "thank you for",
    "thanks for joining",
    "thanks for coming",
    "we're going to look at",
    "i'd like you to",
    "can you try",
    "could you try",
    "what would you do",
    "what would you expect",
    "is there anything else",
    "any other thoughts",
    "any questions",
    "how would you rate",
    "on a scale of",
]


def identify_speaker_roles_heuristic(
    segments: list[TranscriptSegment],
) -> list[TranscriptSegment]:
    """Assign speaker roles using heuristic analysis.

    Uses conversational patterns to distinguish researcher from participant:
    - The speaker who asks more questions is likely the researcher
    - The speaker who uses prompting/facilitation language is likely the researcher
    - The speaker who talks first (introduction) is often the researcher
    - The speaker with less total speaking time is often the researcher

    This is a fast first pass; the LLM refines these labels in the pipeline.

    Args:
        segments: Transcript segments with speaker_label set (e.g. "Speaker A").

    Returns:
        Same segments with speaker_role updated.
    """
    # Collect unique speakers
    speakers: dict[str, _SpeakerStats] = {}
    for seg in segments:
        label = seg.speaker_label or "Unknown"
        if label not in speakers:
            speakers[label] = _SpeakerStats(label=label)
        stats = speakers[label]
        stats.segment_count += 1
        stats.total_duration += seg.end_time - seg.start_time
        stats.total_words += len(seg.text.split())

        # Count questions
        if seg.text.strip().endswith("?"):
            stats.question_count += 1

        # Check for researcher phrases
        text_lower = seg.text.lower()
        for phrase in _RESEARCHER_PHRASES:
            if phrase in text_lower:
                stats.researcher_phrase_hits += 1

    if len(speakers) < 2:
        # Single speaker — assume participant
        for seg in segments:
            seg.speaker_role = SpeakerRole.PARTICIPANT
        return segments

    # Score each speaker: higher = more likely researcher
    for stats in speakers.values():
        if stats.segment_count > 0:
            stats.question_ratio = stats.question_count / stats.segment_count
        stats.researcher_score = (
            stats.question_ratio * 3.0
            + stats.researcher_phrase_hits * 2.0
        )

    # The speaker with highest researcher score is the researcher
    sorted_speakers = sorted(
        speakers.values(),
        key=lambda s: s.researcher_score,
        reverse=True,
    )

    researcher_label = sorted_speakers[0].label
    # If the top scorer barely differs from #2, check who spoke first
    if (
        len(sorted_speakers) > 1
        and sorted_speakers[0].researcher_score - sorted_speakers[1].researcher_score < 1.0
    ):
        # Tiebreaker: first speaker is often the researcher
        first_speaker = segments[0].speaker_label if segments else None
        if first_speaker:
            researcher_label = first_speaker

    logger.info(
        "Identified researcher: %s (score=%.1f), %d total speakers",
        researcher_label,
        speakers[researcher_label].researcher_score,
        len(speakers),
    )

    # Assign roles
    for seg in segments:
        label = seg.speaker_label or "Unknown"
        if label == researcher_label:
            seg.speaker_role = SpeakerRole.RESEARCHER
        elif speakers[label].segment_count <= 2 and speakers[label].total_words < 20:
            # Very minimal participation — likely observer
            seg.speaker_role = SpeakerRole.OBSERVER
        else:
            seg.speaker_role = SpeakerRole.PARTICIPANT

    return segments


async def identify_speaker_roles_llm(
    segments: list[TranscriptSegment],
    llm_client: object,
) -> list[TranscriptSegment]:
    """Refine speaker role identification using an LLM.

    Takes the first few minutes of transcript and asks the LLM to
    classify each speaker as researcher, participant, or observer.

    Args:
        segments: Transcript segments (heuristic roles already assigned).
        llm_client: The LLM client for analysis.

    Returns:
        Segments with refined speaker_role values.
    """
    from bristlenose.llm.client import LLMClient
    from bristlenose.llm.prompts import SPEAKER_IDENTIFICATION_PROMPT

    client: LLMClient = llm_client  # type: ignore[assignment]

    # Build a sample of the first ~5 minutes of conversation
    sample_lines: list[str] = []
    for seg in segments:
        if seg.start_time > 300:  # 5 minutes
            break
        label = seg.speaker_label or "Unknown"
        sample_lines.append(f"[{label}] {seg.text}")

    if not sample_lines:
        return segments

    sample_text = "\n".join(sample_lines)

    # Collect unique speakers
    unique_speakers = sorted(set(
        seg.speaker_label or "Unknown" for seg in segments
    ))

    prompt = SPEAKER_IDENTIFICATION_PROMPT.format(
        transcript_sample=sample_text,
        speaker_list=", ".join(unique_speakers),
    )

    try:
        from bristlenose.llm.structured import SpeakerRoleAssignment
        result = await client.analyze(
            system_prompt="You are an expert at analysing user-research interview transcripts.",
            user_prompt=prompt,
            response_model=SpeakerRoleAssignment,
        )

        # Apply LLM assignments
        role_map: dict[str, SpeakerRole] = {}
        for assignment in result.assignments:  # type: ignore[attr-defined]
            role_map[assignment.speaker_label] = SpeakerRole(assignment.role)

        for seg in segments:
            label = seg.speaker_label or "Unknown"
            if label in role_map:
                seg.speaker_role = role_map[label]

        logger.info("LLM speaker identification: %s", role_map)

    except Exception as exc:
        logger.warning("LLM speaker identification failed, using heuristics: %s", exc)

    return segments


class _SpeakerStats:
    """Accumulated statistics for one speaker."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.segment_count = 0
        self.total_duration = 0.0
        self.total_words = 0
        self.question_count = 0
        self.researcher_phrase_hits = 0
        self.question_ratio = 0.0
        self.researcher_score = 0.0
