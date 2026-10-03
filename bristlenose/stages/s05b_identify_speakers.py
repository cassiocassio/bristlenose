"""Stage 5b: Identify speaker roles (researcher vs participant vs observer)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from bristlenose.llm.boundary import wrap_untrusted
from bristlenose.models import (
    CLOUD_TRANSCRIPT_SOURCE,
    PLATFORM_TRANSCRIPT_SOURCES,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.people import is_generic_label


@dataclass
class SpeakerInfo:
    """Name and title extracted for one speaker during role identification."""

    speaker_label: str
    role: SpeakerRole
    person_name: str = ""
    job_title: str = ""

logger = logging.getLogger(__name__)

#: Segment sources that came from a transcript FILE rather than from Whisper.
#: The platform (or the researcher's own export) decided who spoke; nothing
#: downstream may second-guess that with a model.
PLATFORM_SOURCES = PLATFORM_TRANSCRIPT_SOURCES


class SplitGate(str, Enum):
    """What the speaker-splitting pre-pass should do with a session."""

    #: Whisper output with at most one label: hand it to `split_single_speaker_llm`.
    SPLIT = "split"
    #: Two or more speakers already — nothing to split.
    SEPARATED = "separated"
    #: A platform transcript that names one account, or a cloud transcript that
    #: names nobody. Kept as written, and STATED: the splitter must not run.
    NOT_SEPARATED = "not_separated"


def real_speaker_names(segments: list[TranscriptSegment]) -> set[str]:
    """The labels on *segments* that are people's names, not placeholders."""
    return {
        seg.speaker_label
        for seg in segments
        if seg.speaker_label and not is_generic_label(seg.speaker_label)
    }


def split_gate(segments: list[TranscriptSegment]) -> SplitGate:
    """Decide whether the LLM splitter may run on a session.

    The splitter guesses speakers from the text alone — the whole transcript,
    in parts, since 3 Oct 2026; until then the first 5–8 minutes with the last
    label carried to the end (``docs/design-speaker-splitting.md``). On a bare
    recording that is the best available; on a platform transcript it is a
    regression — it overwrote the one real name an in-room interview carried
    with "Speaker A/B" (measured, 30 Sep 2026). So:

    * two or more labels → already separated;
    * a platform transcript (subtitle or docx source) carrying a real name →
      that name is the account, not a voice; never split (product call Q3);
    * a cloud transcript whose writer said ``speakers: none`` → the platform
      could not separate them and neither should a model guessing from text
      — an INTERIM rule while whole-transcript splitting is being measured;
    * a vendor subtitle file with no names at all (a bare caption track) and
      every Whisper transcript → split, as today.
    """
    if not segments:
        return SplitGate.SEPARATED
    labels = {seg.speaker_label or "Unknown" for seg in segments}
    if len(labels) >= 2:
        return SplitGate.SEPARATED

    from_platform = all(seg.source in PLATFORM_SOURCES for seg in segments)
    if from_platform:
        if real_speaker_names(segments):
            return SplitGate.NOT_SEPARATED
        if all(seg.source == CLOUD_TRANSCRIPT_SOURCE for seg in segments):
            return SplitGate.NOT_SEPARATED
    return SplitGate.SPLIT


def speaker_info_to_dict(info: SpeakerInfo) -> dict[str, Any]:
    """Serialize a SpeakerInfo to a JSON-compatible dict."""
    return {
        "speaker_label": info.speaker_label,
        "role": info.role.value,
        "person_name": info.person_name,
        "job_title": info.job_title,
    }


def speaker_info_from_dict(d: dict[str, Any]) -> SpeakerInfo:
    """Deserialize a SpeakerInfo from a dict."""
    return SpeakerInfo(
        speaker_label=d["speaker_label"],
        role=SpeakerRole(d["role"]),
        person_name=d.get("person_name", ""),
        job_title=d.get("job_title", ""),
    )

# Keywords suggesting a researcher/interviewer role
_RESEARCHER_PHRASES = [
    # Task-oriented prompts
    "can you tell me",
    "could you tell me",
    "what do you think",
    "how do you feel",
    "walk me through",
    "describe for me",
    "let me show you",
    "i'm going to show",
    "we're going to look at",
    "i'd like you to",
    "can you try",
    "could you try",
    "what would you do",
    "what would you expect",
    "how would you rate",
    "on a scale of",
    # Conversation management
    "let's move on to",
    "next i'd like",
    "next we're going to",
    "thank you for",
    "thanks for joining",
    "thanks for coming",
    "is there anything else",
    "any other thoughts",
    "any questions",
    # Open-ended prompting
    "tell me about",
    "can you describe",
    "what was it like",
    "how did you get involved",
    "what happened next",
    "can you say more",
    "i'd like to ask about",
    "let's talk about",
    "what was your reaction",
    "how did that come about",
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
    total_words_all = sum(s.total_words for s in speakers.values())
    for stats in speakers.values():
        if stats.segment_count > 0:
            stats.question_ratio = stats.question_count / stats.segment_count
        # Word count asymmetry: in a 1:1 interview the researcher typically
        # speaks less than the participant.  0 = most words, 1 = fewest.
        # Only applied for 2-speaker sessions — with 3+ speakers, low word
        # count could be a secondary interviewer or observer, and asymmetry
        # would inflate both equally.  Phrase hits and question ratio are
        # better discriminators for multi-speaker sessions.
        if total_words_all > 0 and len(speakers) == 2:
            word_share = stats.total_words / total_words_all
            # Invert: lower share → higher score.  Clamp to [0, 1].
            stats.word_asymmetry = max(0.0, min(1.0, 1.0 - word_share))
        else:
            stats.word_asymmetry = 0.0
        stats.researcher_score = (
            stats.question_ratio * 3.0
            + stats.researcher_phrase_hits * 2.0
            + stats.word_asymmetry * 2.0
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


#: Segments per splitter call. One 35-minute interview (377 Whisper segments)
#: came back with 281 boundaries — nearly one per segment — so a single call
#: on a 2-hour recording would exceed some providers' output caps (gpt-4o:
#: 16,384 tokens). 200 keeps each structured response well under them.
SPLIT_CHUNK_SEGMENTS = 200

#: Already-labelled lines shown ahead of each later chunk, so the model keeps
#: the same speaker identifiers for the same people from chunk to chunk.
SPLIT_CONTEXT_SEGMENTS = 12


async def split_single_speaker_llm(
    segments: list[TranscriptSegment],
    llm_client: object,
    errors: list[str] | None = None,
) -> list[TranscriptSegment]:
    """Split a single-speaker transcript into multiple speakers using an LLM.

    When a transcript has 0 or 1 unique speaker labels (e.g. raw audio
    transcribed by Whisper with no diarization), this function asks the LLM
    to detect speaker changes from conversational context (names, turn-taking,
    topic shifts) and updates ``speaker_label`` on each segment.

    The whole transcript is read, in chunks of ``SPLIT_CHUNK_SEGMENTS``,
    sequentially: each later chunk is shown the last few lines already
    labelled so the speaker identifiers carry across. Until 3 Oct 2026 only
    the first 5–8 minutes were read and the last label was carried to the end
    of the file; measured against a Teams transcript's named turns, that found
    38% of the moderator's segments where whole-transcript splitting finds
    88–97% (``docs/design-speaker-splitting.md`` § Measured).

    If the transcript already has 2+ distinct speaker labels, returns
    segments unchanged. If the model finds only one speaker overall, the
    original labels are kept. If a later chunk fails, the chunks already
    labelled stand and the rest carry the last label, as the opening-sample
    splitter did.

    Mutates *segments* in place (sets ``speaker_label``).

    Args:
        segments: Transcript segments (may all have the same or no speaker label).
        llm_client: The LLM client for analysis.
        errors: Optional list to append error messages to.

    Returns:
        The same segment list with ``speaker_label`` updated.
    """
    if not segments:
        return segments

    # Guard: only split when there's a single speaker (or none)
    unique_labels = set(seg.speaker_label or "Unknown" for seg in segments)
    if len(unique_labels) >= 2:
        return segments

    from bristlenose.llm.client import LLMClient
    from bristlenose.llm.prompts import get_prompt_template
    from bristlenose.llm.structured import SpeakerSplitAssignment

    client: LLMClient = llm_client  # type: ignore[assignment]
    _tmpl = get_prompt_template("speaker-splitting")

    labels: list[str | None] = [None] * len(segments)
    names: dict[str, str] = {}
    current: str | None = None
    n_chunks = -(-len(segments) // SPLIT_CHUNK_SEGMENTS)

    for chunk_no, first in enumerate(range(0, len(segments), SPLIT_CHUNK_SEGMENTS)):
        last = min(first + SPLIT_CHUNK_SEGMENTS, len(segments))
        lines = "\n".join(f"[{i}] {segments[i].text}" for i in range(first, last))
        prior_context = ""
        if first > 0 and current is not None:
            lo = max(0, first - SPLIT_CONTEXT_SEGMENTS)
            labelled = "\n".join(
                f"[{i}] ({labels[i]}) {segments[i].text}" for i in range(lo, first)
            )
            prior_context = (
                "These lines come just before the part to label and are already "
                "labelled. Use the same speaker identifiers for the same people:\n"
                + wrap_untrusted("labelled_lines", labelled)
                + "\n\n"
            )
        try:
            result = await client.analyze(
                system_prompt=_tmpl.system,
                user_prompt=_tmpl.user.format(
                    prior_context=prior_context,
                    transcript_sample=wrap_untrusted("transcript", lines),
                    segment_count=last - first,
                    first_index=first,
                ),
                response_model=SpeakerSplitAssignment,
                prompt_template=_tmpl,
            )
        except Exception as exc:
            if current is None:
                logger.debug("LLM speaker splitting failed, keeping single speaker: %s", exc)
                if errors is not None:
                    errors.append(f"speaker splitting: {exc}")
                return segments
            # Keep what earlier chunks found; carry the last label onward.
            logger.warning(
                "Speaker splitting failed on part %d of %d; segments from %d on "
                "keep the last detected speaker: %s",
                chunk_no + 1, n_chunks, first, exc,
            )
            if errors is not None:
                errors.append(f"speaker splitting (part {chunk_no + 1} of {n_chunks}): {exc}")
            for i in range(first, len(segments)):
                labels[i] = current
            break

        bounds = sorted(
            (b for b in result.boundaries if first <= b.segment_index < last),
            key=lambda b: b.segment_index,
        )
        if current is None and bounds:
            current = bounds[0].speaker_id  # the first chunk opens on its first boundary
        j = 0
        for i in range(first, last):
            while j < len(bounds) and i >= bounds[j].segment_index:
                current = bounds[j].speaker_id
                j += 1
            labels[i] = current
        for b in bounds:
            if b.person_name:
                names.setdefault(b.speaker_id, b.person_name)

    distinct = {label for label in labels if label is not None}
    if len(distinct) <= 1:
        logger.info("LLM speaker splitting: single speaker confirmed")
        return segments

    for seg, label in zip(segments, labels):
        if label is not None:
            seg.speaker_label = label

    logger.debug(
        "LLM speaker splitting: %d speakers over %d segments in %d part(s), names=%s",
        len(distinct), len(segments), n_chunks, names or "(none extracted)",
    )
    return segments


async def identify_speaker_roles_llm(
    segments: list[TranscriptSegment],
    llm_client: object,
    errors: list[str] | None = None,
) -> list[SpeakerInfo]:
    """Refine speaker role identification using an LLM.

    Takes the first few minutes of transcript and asks the LLM to
    classify each speaker as researcher, participant, or observer.
    Also extracts names and job titles when mentioned in the transcript.

    Mutates *segments* in place (sets ``speaker_role``).

    Args:
        segments: Transcript segments (heuristic roles already assigned).
        llm_client: The LLM client for analysis.
        errors: Optional list to append error messages to.

    Returns:
        A :class:`SpeakerInfo` for each speaker the LLM identified, or
        an empty list if the LLM call fails.
    """
    from bristlenose.llm.client import LLMClient
    from bristlenose.llm.prompts import get_prompt_template

    client: LLMClient = llm_client  # type: ignore[assignment]

    # Build a sample of the first ~5 minutes of conversation
    sample_lines: list[str] = []
    for seg in segments:
        if seg.start_time > 300:  # 5 minutes
            break
        label = seg.speaker_label or "Unknown"
        sample_lines.append(f"[{label}] {seg.text}")

    if not sample_lines:
        return []

    sample_text = "\n".join(sample_lines)

    # Collect unique speakers
    unique_speakers = sorted(set(
        seg.speaker_label or "Unknown" for seg in segments
    ))

    _tmpl = get_prompt_template("speaker-identification")

    try:
        from bristlenose.llm.structured import SpeakerRoleAssignment
        result = await client.analyze(
            system_prompt=_tmpl.system,
            user_prompt=_tmpl.user.format(
                transcript_sample=wrap_untrusted("transcript", sample_text),
                speaker_list=", ".join(unique_speakers),
            ),
            response_model=SpeakerRoleAssignment,
            prompt_template=_tmpl,
        )

        # Apply LLM assignments and collect extracted info
        infos: list[SpeakerInfo] = []
        role_map: dict[str, SpeakerRole] = {}
        for assignment in result.assignments:
            role = SpeakerRole(assignment.role)
            role_map[assignment.speaker_label] = role
            infos.append(SpeakerInfo(
                speaker_label=assignment.speaker_label,
                role=role,
                person_name=getattr(assignment, "person_name", "") or "",
                job_title=getattr(assignment, "job_title", "") or "",
            ))

        for seg in segments:
            label = seg.speaker_label or "Unknown"
            if label in role_map:
                seg.speaker_role = role_map[label]

        logger.info("LLM speaker identification: %s", role_map)
        return infos

    except Exception as exc:
        logger.debug("LLM speaker identification failed, using heuristics: %s", exc)
        if errors is not None:
            errors.append(str(exc))
        return []


def assign_speaker_codes(
    next_participant_number: int,
    segments: list[TranscriptSegment],
    known: dict[str, str] | None = None,
) -> tuple[dict[str, str], int]:
    """Assign speaker codes (p1, p2, m1, m2, o1...) based on identified roles.

    Sets ``speaker_code`` on every segment.  Returns a map of
    ``speaker_label -> speaker_code`` and the next available participant number.

    Participant numbering is global across sessions: the caller tracks
    ``next_participant_number`` so that session s1 might get p1 + p2 and
    session s2 starts at p3.

    Code prefixes:
    - ``p`` — participant (globally numbered)
    - ``m`` — moderator / researcher (per-session)
    - ``o`` — observer (per-session)

    ``known`` is the session's label → code map from an earlier run
    (``SessionRegistry.speakers_for``). A label keeps its code while its role
    still matches the code's kind, so a participant's code — and every quote,
    star and name keyed by it — survives a session being added elsewhere in
    the study. Labels it does not cover are numbered as before. With no
    ``known`` map the result is identical to a first run.

    Args:
        next_participant_number: The next available participant number (e.g. 1).
        segments: Segments with ``speaker_role`` already set.
        known: Optional label → code map to keep stable.

    Returns:
        Tuple of (label-to-code mapping, next available participant number).
    """
    # Build label → role from first occurrence
    label_role: dict[str, SpeakerRole] = {}
    for seg in segments:
        label = seg.speaker_label or "Unknown"
        if label not in label_role:
            label_role[label] = seg.speaker_role

    def _prefix(role: SpeakerRole) -> str:
        if role == SpeakerRole.RESEARCHER:
            return "m"
        if role == SpeakerRole.OBSERVER:
            return "o"
        return "p"  # PARTICIPANT and UNKNOWN get globally-numbered codes

    # Keep each label's earlier code while its role still matches.
    label_code: dict[str, str] = {}
    used: set[str] = set()
    for label, role in label_role.items():
        code = (known or {}).get(label)
        if code and code[0] == _prefix(role) and code not in used:
            label_code[label] = code
            used.add(code)

    # Number the rest. Moderator and observer codes are per session and skip
    # any kept above; participant codes are global and come from the caller.
    for label, role in label_role.items():
        if label in label_code:
            continue
        prefix = _prefix(role)
        if prefix == "p":
            code = f"p{next_participant_number}"
            next_participant_number += 1
        else:
            n = 1
            while f"{prefix}{n}" in used:
                n += 1
            code = f"{prefix}{n}"
        label_code[label] = code
        used.add(code)
    # First-appearance order: the caller takes the first ``p`` code as the
    # session's primary participant, and kept codes were inserted first.
    label_code = {label: label_code[label] for label in label_role}

    # Stamp every segment
    for seg in segments:
        label = seg.speaker_label or "Unknown"
        seg.speaker_code = label_code[label]

    return label_code, next_participant_number


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
        self.word_asymmetry = 0.0
        self.researcher_score = 0.0
