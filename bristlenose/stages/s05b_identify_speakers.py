"""Stage 5b: Identify speaker roles (researcher vs participant vs observer)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from bristlenose.llm.boundary import wrap_untrusted
from bristlenose.models import (
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
    #: A platform transcript that names one account. Kept as written, and
    #: STATED: the splitter must not run. (A cloud transcript that names nobody
    #: was here too until 4 Oct 2026; it now splits.)
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
    * a transcript with no names at all — a cloud transcript whose writer
      said ``speakers: none``, a bare caption track, every Whisper
      transcript → split. The cloud case was held back as NOT_SEPARATED
      while whole-transcript splitting was measured; it splits since
      4 Oct 2026 (owner's call), because a guess from the whole text beats
      one voice for the whole interview.
    """
    if not segments:
        return SplitGate.SEPARATED
    labels = {seg.speaker_label or "Unknown" for seg in segments}
    if len(labels) >= 2:
        return SplitGate.SEPARATED

    from_platform = all(seg.source in PLATFORM_SOURCES for seg in segments)
    if from_platform and real_speaker_names(segments):
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

# Opening-script and facilitation phrases: what the person RUNNING a session says to
# the person being hosted. Matched as regexes on lower-cased text with reported speech
# removed. Deliberately no occupation words: "researcher" is a job title the
# interviewee may hold ("I'm a researcher for an MP"), not a sign of who is hosting.
_HOST_PHRASES = [
    # Welcome and framing
    r"thanks? (so much )?for (joining|coming|making (the )?time|taking (the )?time"
    r"|doing this|agreeing|seeing|meeting|being here)",
    r"good (morning|afternoon|evening),? (everyone|all)",
    r"no right or wrong", r"no wrong answers", r"there'?s no (normal|right|wrong)",
    r"(we'?re|i'?ll( be)?|i'?m going to be) record", r"recording (now|started)",
    r"i'?d like to (record|ask you)",
    r"i'?ll (just )?(listen|stay out|be taking notes|take notes)", r"don'?t worry about me",
    r"(we|i) (want|would like) to (hear (from|about|how)|ask you|talk (to|with) you)",
    r"we'?re (talking|speaking) to",
    r"i'?m (talking|speaking) to (a|several|some|people|customers|users|everyone)",
    r"i'?m (here|going) to (ask|show) you", r"i'?m going to (show|share)",
    r"i'?m (from|with) the [a-z' ]{3,30}(team|department)",
    r"this (session|interview) (is|will|should)", r"the (aim|goal|purpose) of (this|today)",
    r"before we (start|begin|get started)", r"any questions (before|for me)",
    # Task and open-ended prompts
    r"take your time", r"feel free to", r"i'?d love (you )?to", r"i'?d like you to",
    r"what i'?m after",
    r"(can|could) you (tell|walk|show|describe|talk|try)",
    r"(walk|take|talk) me through",
    # "Tell me about it" is the idiom for "I agree", not a prompt.
    r"tell me (about (?!(it|that|this)\b)|more about)",
    r"what do you think", r"how do you feel", r"how did (that|it) (feel|go)",
    r"what was (it|that|your) (like|reaction)", r"how did you get involved",
    r"how did that come about", r"what would you (do|expect)", r"how would you rate",
    r"on a scale of", r"what happened (next|then)", r"can you say more",
    # Conversation management
    r"let'?s (move on|talk about|look at)", r"next,? (i'?d|we'?re|let'?s)",
    r"is there anything else", r"any other thoughts", r"we'?re going to look at",
]
# What the person being hosted says to the host.
_GUEST_PHRASES = [
    r"thanks? (so much )?for having me", r"happy to help", r"(glad|happy) to (be here|take part|do this)",
    r"hope (this|i'?m) (is )?helpful", r"is that (what you(?:'re| are) (after|looking for)|helpful|normal|ok(ay)?)\b",
    r"do you want me to", r"should i (show|share|open|click|go)", r"shall i", r"do you want (me|to see)",
    r"can you hear me", r"is the recording on", r"can you see (my|the) screen", r"sorry,? (mine|i)", r"does that make sense",
]
_HOST_RE = [re.compile(p) for p in _HOST_PHRASES]
_GUEST_RE = [re.compile(p) for p in _GUEST_PHRASES]
# A question that only checks the listener is still there ("...right?", "you know?") is not
# the speaker steering the session.
_TAG_QUESTION_RE = re.compile(
    r"[,\u2014-]\s*(right|yeah|yes|ok|okay|no|eh|see|you know|y'?know|isn'?t it|innit)\?\s*$"
    r"|\b(you know|y'?know|isn'?t it|innit|does that make sense|is that normal)\?\s*$",
    re.IGNORECASE,
)
# Someone describing what they themselves say or ask ("I always say, tell me about...")
# is reporting speech, not facilitating.
_REPORTED_SPEECH_RE = re.compile(
    r"\bi (always |usually |then |just |sometimes )?(say|ask|tell (them|him|her|people))\b"
    r"|\bthey (say|ask|tell)\b",
    re.IGNORECASE,
)
_QUOTED_RE = re.compile(r"[\"\u201c\u201d][^\"\u201c\u201d]{3,}[\"\u201c\u201d]")
# The host introducing a colleague allows a second moderator.
_COLLEAGUE_RE = re.compile(
    r"my (colleague|co-?moderator|co-?researcher|note-?taker)|joined by my", re.IGNORECASE
)
#: A phrase hit is capped per segment so a long speech cannot win on volume alone.
_PHRASE_HITS_PER_SEGMENT_CAP = 2


def _count_speakers(segments: list[TranscriptSegment]) -> dict[str, _SpeakerStats]:
    """Per-speaker counts over a whole session, keyed by label, in order of first appearance."""
    speakers: dict[str, _SpeakerStats] = {}
    for seg in segments:
        label = seg.speaker_label or "Unknown"
        stats = speakers.setdefault(label, _SpeakerStats(label=label))
        text = seg.text
        stats.segment_count += 1
        stats.total_duration += seg.end_time - seg.start_time
        stats.total_words += len(text.split())

        stripped = text.strip()
        if stripped.endswith("?") and not _TAG_QUESTION_RE.search(stripped):
            stats.question_count += 1

        if _COLLEAGUE_RE.search(text):
            stats.introduces_colleague = True

        # Reported or quoted speech is not the speaker facilitating.
        reported = _REPORTED_SPEECH_RE.search(text)
        before_report = text[: reported.start()] if reported else text
        lowered = _QUOTED_RE.sub(" ", before_report.lower())
        host = sum(1 for r in _HOST_RE if r.search(lowered))
        guest = sum(1 for r in _GUEST_RE if r.search(lowered))
        stats.host_phrase_hits += min(host, _PHRASE_HITS_PER_SEGMENT_CAP)
        stats.guest_phrase_hits += min(guest, _PHRASE_HITS_PER_SEGMENT_CAP)
    return speakers


def speaker_facts(segments: list[TranscriptSegment]) -> str:
    """The per-speaker counts as plain lines for the speaker-identification prompt.

    Measured over the whole session, not just the sample the model reads: turns, share of
    words, real questions, host-style and guest-style opening-script phrases, who spoke
    first. They are facts for the model to weigh, never verdicts.
    """
    speakers = _count_speakers(segments)
    total_words = sum(s.total_words for s in speakers.values()) or 1
    first = (segments[0].speaker_label or "Unknown") if segments else ""
    lines = []
    for label, s in speakers.items():
        share = round(100 * s.total_words / total_words)
        lines.append(
            f"- {label}: {s.segment_count} turns, {s.total_words} words ({share}% of words), "
            f"{s.question_count} questions, {s.host_phrase_hits} host-style opening-script "
            f"phrases, {s.guest_phrase_hits} guest-style"
            + (", spoke first" if label == first else "")
        )
    return "\n".join(lines)


def identify_speaker_roles_heuristic(
    segments: list[TranscriptSegment],
) -> list[TranscriptSegment]:
    """Assign speaker roles from counts alone, with no model.

    This decides on its own only when the LLM pass fails or is skipped; otherwise the
    same counts go to the model as facts (see :func:`speaker_facts`). Signals, by weight:

    - Host-style opening-script phrases ("thanks for joining", "no right or wrong",
      "walk me through"), as a rate per turn, minus guest-style phrases ("thanks for
      having me"). Reported speech ("I always say, tell me about...") does not count.
    - The share of turns that are real questions (tag questions like "right?" excluded).
    - A weak word-share nudge in two-speaker sessions (the host tends to say less).

    Who spoke first is not a signal (it depends on who joined the call first); only an
    exact tie in score goes to the earlier speaker, as a last resort. In a session of
    three or more, a second researcher is recognised when the host introduces a colleague
    and that speaker only asks, or when they carry the host-style script and ask.

    Args:
        segments: Transcript segments with speaker_label set (e.g. "Speaker A").

    Returns:
        Same segments with speaker_role updated.
    """
    speakers = _count_speakers(segments)

    if len(speakers) < 2:
        # Single speaker — assume participant
        for seg in segments:
            seg.speaker_role = SpeakerRole.PARTICIPANT
        return segments

    total_words_all = sum(s.total_words for s in speakers.values()) or 1
    for stats in speakers.values():
        turns = stats.segment_count
        stats.question_ratio = stats.question_count / turns
        # Weak: in a 1:1 the interviewer often says less. Two-speaker sessions only; with
        # three or more, a low word count may be a second interviewer or an observer.
        if len(speakers) == 2:
            stats.word_asymmetry = 1.0 - stats.total_words / total_words_all
        stats.researcher_score = (
            stats.question_ratio * 1.5
            + stats.host_phrase_hits / turns * 4.0
            - stats.guest_phrase_hits / turns * 3.0
            + stats.word_asymmetry * 0.5
        )

    # sorted() is stable: an exact tie goes to the earlier speaker, the last resort.
    ranked = sorted(speakers.values(), key=lambda s: s.researcher_score, reverse=True)
    top = ranked[0]
    researchers = {top.label}
    for stats in ranked[1:]:
        if stats.segment_count <= 2 and stats.total_words < 20:
            continue  # observer, below
        asks_only = stats.question_count >= 3 and stats.question_ratio >= 0.6
        if (
            top.introduces_colleague
            and len(speakers) >= 3  # a 1:1 always keeps its participant
            and stats.guest_phrase_hits == 0
            and asks_only
        ):
            researchers.add(stats.label)  # introduced by the host, and only asks
        elif (
            stats.host_phrase_hits >= 3
            and stats.question_count >= 2  # a moderator asks; a grumbling guest does not
            and stats.researcher_score >= max(0.5, 0.6 * top.researcher_score)
        ):
            researchers.add(stats.label)  # carries the host script itself

    logger.info(
        "Identified researcher(s): %s (score=%.1f), %d total speakers",
        sorted(researchers),
        top.researcher_score,
        len(speakers),
    )

    for seg in segments:
        label = seg.speaker_label or "Unknown"
        if label in researchers:
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
    unique_labels = {seg.speaker_label or "Unknown" for seg in segments}
    if len(unique_labels) >= 2:
        return segments

    from bristlenose.llm.client import LLMClient, failure_summary
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
        lines = "\n".join(f"[{i}] {segments[i].line_text}" for i in range(first, last))
        prior_context = ""
        if first > 0 and current is not None:
            lo = max(0, first - SPLIT_CONTEXT_SEGMENTS)
            labelled = "\n".join(
                f"[{i}] ({labels[i]}) {segments[i].line_text}" for i in range(lo, first)
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
                logger.debug(
                    "LLM speaker splitting failed, keeping single speaker: %s", failure_summary(exc)
                )
                if errors is not None:
                    errors.append(f"speaker splitting: {exc}")
                return segments
            # Keep what earlier chunks found; carry the last label onward.
            logger.warning(
                "Speaker splitting failed on part %d of %d; segments from %d on "
                "keep the last detected speaker: %s",
                chunk_no + 1, n_chunks, first, failure_summary(exc),
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

    for seg, label in zip(segments, labels, strict=True):
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
    from bristlenose.llm.client import LLMClient, failure_summary
    from bristlenose.llm.prompts import get_prompt_template

    client: LLMClient = llm_client  # type: ignore[assignment]

    # Build a sample of the first ~5 minutes of conversation
    sample_lines: list[str] = []
    for seg in segments:
        if seg.start_time > 300:  # 5 minutes
            break
        label = seg.speaker_label or "Unknown"
        sample_lines.append(f"[{label}] {seg.line_text}")

    if not sample_lines:
        return []

    sample_text = "\n".join(sample_lines)

    # Collect unique speakers
    unique_speakers = sorted({
        seg.speaker_label or "Unknown" for seg in segments
    })

    _tmpl = get_prompt_template("speaker-identification")

    try:
        from bristlenose.llm.structured import SpeakerRoleAssignment
        result = await client.analyze(
            system_prompt=_tmpl.system,
            user_prompt=_tmpl.user.format(
                transcript_sample=wrap_untrusted("transcript", sample_text),
                speaker_list=wrap_untrusted("speaker_list", ", ".join(unique_speakers)),
                speaker_facts=wrap_untrusted("speaker_facts", speaker_facts(segments)),
            ),
            response_model=SpeakerRoleAssignment,
            prompt_template=_tmpl,
        )

        # One speaker is one research subject doing a solo think-aloud: a
        # participant, whatever the model says (owner rule, 8 Nov 2026). The
        # model's "researcher" here coded a lone voice m1, and quotes come only
        # from participants, so the session gave nothing. Its name is kept.
        solo = len(unique_speakers) == 1

        # Apply LLM assignments and collect extracted info
        infos: list[SpeakerInfo] = []
        role_map: dict[str, SpeakerRole] = {}
        for assignment in result.assignments:
            role = SpeakerRole.PARTICIPANT if solo else SpeakerRole(assignment.role)
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

        # Roles only: on platform transcripts the label is the participant's real name.
        logger.info(
            "LLM speaker identification: %s",
            sorted(role.value for role in role_map.values()),
        )
        return infos

    except Exception as exc:
        logger.debug(
            "LLM speaker identification failed, using heuristics: %s", failure_summary(exc)
        )
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
    # any kept above, and every one this session ever issued: a speaker not
    # heard this run, or retired by a role flip, keeps its code out of reach,
    # or the next new voice would take it and wear that speaker's name
    # (design-people.md §J7). Participant codes are global, from the caller.
    reserved = {c for c in (known or {}).values() if c[:1] in ("m", "o")}
    for label, role in label_role.items():
        if label in label_code:
            continue
        prefix = _prefix(role)
        if prefix == "p":
            code = f"p{next_participant_number}"
            next_participant_number += 1
        else:
            n = 1
            while f"{prefix}{n}" in used or f"{prefix}{n}" in reserved:
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
        self.host_phrase_hits = 0
        self.guest_phrase_hits = 0
        self.introduces_colleague = False
        self.question_ratio = 0.0
        self.word_asymmetry = 0.0
        self.researcher_score = 0.0
