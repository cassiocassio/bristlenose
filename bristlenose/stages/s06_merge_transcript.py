"""Stage 6: Merge all transcript sources into unified format and write raw files."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from bristlenose.models import (
    FullTranscript,
    InputSession,
    TranscriptSegment,
    format_timecode,
)

logger = logging.getLogger(__name__)


def _language_header(transcript: FullTranscript) -> dict[str, str] | None:
    """The `Language:` line for a transcript header, or nothing.

    ``(detected)`` when Whisper decided; ``(set)`` when the run pinned it with
    ``--whisper-language`` — never a pinned value dressed as a detection.
    Absent for a transcript that came from a subtitle or docx file, where
    nothing knew the language. The importer reads either form, so an exported
    clip's subtitle track can be tagged with it. The code is printed rather
    than a language name: the names live in the backends' own tables (100
    entries), and importing a backend here to pretty-print one string would
    couple the merge stage to whichever one happened to run.
    """
    if transcript.detected_language:
        return {"Language": f"{transcript.detected_language} (detected)"}
    if transcript.pinned_language:
        return {"Language": f"{transcript.pinned_language} (set)"}
    return None


#: The header line that marks a transcript paragraphed by the reading rule.
PARAGRAPHS_HEADER = ("Paragraphs", "sentences")
_PARAGRAPHS_LINE_RE = re.compile(r"^#\s*Paragraphs:\s*sentences$")


def sentence_paragraph_sessions(
    raw_dir: Path,
    session_ids: list[str],
    analysed: set[str] | frozenset[str] = frozenset(),
) -> set[str]:
    """Which sessions get the reading rule (`PARAGRAPH_LENGTH`) this run.

    A session's paragraphs are what a researcher's splits, joins and speaker
    moves are keyed to (by position and first words), and this stage re-runs
    on every pipeline run. So a session keeps the paragraphing it was first
    written with: one whose transcript exists without the ``# Paragraphs:
    sentences`` line stays on the gap rule; one already carrying the line, or a
    new one, gets the reading rule.

    "New" means no transcript file AND no analysis on record (``analysed``:
    sessions the manifest already has topics or quotes for). A deleted ``.txt``
    in an analysed project is not a new session. A file that exists but cannot
    be read (an evicted cloud file, a permission error) keeps the gap rule.

    The marker lives in the file, not on `FullTranscript`: the topic and quote
    caches fingerprint the whole model, so a new field would change every
    session's fingerprint and re-run paid analysis across every project.
    """
    chosen: set[str] = set()
    for sid in session_ids:
        path = raw_dir / f"{sid}.txt"
        if not path.exists():
            if sid not in analysed:
                chosen.add(sid)
            continue
        try:
            with path.open(encoding="utf-8") as fh:
                for line in fh:  # the header block, however long its lines
                    if _PARAGRAPHS_LINE_RE.match(line.strip()):
                        chosen.add(sid)
                        break
                    if line.strip() and not line.startswith("#"):
                        break
        except (OSError, UnicodeDecodeError):
            continue
    return chosen


def _headers(
    transcript: FullTranscript, sentence_paragraphs: set[str] | None,
) -> dict[str, str] | None:
    headers = dict(_language_header(transcript) or {})
    if sentence_paragraphs and transcript.session_id in sentence_paragraphs:
        headers[PARAGRAPHS_HEADER[0]] = PARAGRAPHS_HEADER[1]
    return headers or None


def merge_transcripts(
    sessions: list[InputSession],
    session_segments: dict[str, list[TranscriptSegment]],
    input_dir: Path | None = None,
    *,
    session_languages: dict[str, str] | None = None,
    pinned_languages: dict[str, str] | None = None,
    sentence_paragraphs: set[str] | None = None,
) -> list[FullTranscript]:
    """Merge all transcript sources into unified FullTranscript objects.

    Args:
        sessions: The input sessions.
        session_segments: Map of session_id -> segments from any source
            (whisper, subtitle, docx).
        input_dir: Project input directory.  When provided, source file
            paths are stored relative to this directory (preserving
            subdirectories like ``interviews/``).  Without it, only the
            filename is stored (legacy behaviour).

    Returns:
        List of FullTranscript objects, one per session.
    """
    transcripts: list[FullTranscript] = []

    for session in sessions:
        segments = session_segments.get(session.session_id, [])
        if not segments:
            logger.warning(
                "%s: No transcript segments available.",
                session.session_id,
            )
            continue

        # Sort segments by start time
        segments.sort(key=lambda s: s.start_time)

        # Merge overlapping same-speaker segments
        merged = _merge_same_speaker(
            segments,
            sentence_paragraphs=session.session_id in (sentence_paragraphs or set()),
        )

        # Assign canonical segment ordinals (see design-quote-sequences.md)
        for i, seg in enumerate(merged):
            seg.segment_index = i

        # Compute duration
        duration = 0.0
        if merged:
            duration = merged[-1].end_time

        # Determine source file path (relative to input_dir when possible,
        # so the importer can locate the file without guessing subdirectories).
        source_file = "unknown"
        if session.files:
            fpath = session.files[0].path
            if input_dir is not None:
                try:
                    source_file = str(fpath.relative_to(input_dir))
                except ValueError:
                    source_file = fpath.name
            else:
                source_file = fpath.name

        transcript = FullTranscript(
            session_id=session.session_id,
            participant_id=session.participant_id,
            source_file=source_file,
            session_date=session.session_date,
            duration_seconds=duration,
            segments=merged,
            detected_language=(session_languages or {}).get(session.session_id),
            pinned_language=(pinned_languages or {}).get(session.session_id),
        )
        transcripts.append(transcript)
        logger.info(
            "%s: Merged %d segments, duration=%.0fs",
            session.session_id,
            len(merged),
            duration,
        )

    return transcripts


#: The readme beside the raw transcripts. Never a ``.txt``: every reader of this
#: folder (``analyze``, the serve importer, the transcript pages) takes each
#: ``*.txt`` for a transcript, and a ``README.txt`` would be one (#120).
RAW_README_NAME = "README.md"


def write_raw_readme(output_dir: Path) -> None:
    """Write the folder's readme: these files are RAW, and rewritten every run.

    Advisory, never a deliverable: a readme the researcher locked in Finder (told
    not to edit these files, they protect one) is logged and left, and the run goes on.
    """
    from bristlenose.utils.markdown import RAW_TRANSCRIPTS_README

    path = output_dir / RAW_README_NAME
    try:
        path.write_text(RAW_TRANSCRIPTS_README, encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not write %s (%s); the transcripts are unaffected", path, exc)


def write_raw_transcripts(
    transcripts: list[FullTranscript],
    output_dir: Path,
    *,
    sentence_paragraphs: set[str] | None = None,
) -> list[Path]:
    """Write raw transcript text files, and the folder's readme.

    Format uses the markdown style template from
    :mod:`bristlenose.utils.markdown`.

    Args:
        transcripts: Transcripts to write.
        output_dir: Directory to write to.

    Returns:
        List of written transcript paths (not the readme).
    """
    from bristlenose.utils.markdown import (
        format_raw_segment_txt,
        format_transcript_header_txt,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for transcript in transcripts:
        # New naming: s1.txt (was s1_raw.txt — directory name now indicates raw/cooked)
        filename = f"{transcript.session_id}.txt"
        path = output_dir / filename

        header = format_transcript_header_txt(
            participant_id=transcript.session_id,
            source_file=transcript.source_file,
            session_date=transcript.session_date.isoformat(),
            duration=format_timecode(transcript.duration_seconds),
            extra_headers=_headers(transcript, sentence_paragraphs),
        )

        lines: list[str] = [header, ""]

        for seg in transcript.segments:
            tc = format_timecode(seg.start_time)
            code = seg.speaker_code or transcript.participant_id
            lines.append(
                format_raw_segment_txt(tc, code, seg.speaker_label, seg.line_text)
            )
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        paths.append(path)
        logger.info("Wrote raw transcript: %s", path)

    write_raw_readme(output_dir)
    return paths


def write_raw_transcripts_md(
    transcripts: list[FullTranscript],
    output_dir: Path,
    *,
    sentence_paragraphs: set[str] | None = None,
) -> list[Path]:
    """Write raw transcript Markdown files alongside the .txt files.

    The ``.md`` version provides a more readable format with bold
    participant code labels and structured metadata.  Files are named
    ``{session_id}.md`` and placed in ``transcripts-raw/``.

    Args:
        transcripts: Transcripts to write.
        output_dir: Directory to write to.

    Returns:
        List of written file paths.
    """
    from bristlenose.utils.markdown import (
        format_raw_segment_md,
        format_transcript_header_md,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for transcript in transcripts:
        # New naming: s1.md (was s1_raw.md)
        filename = f"{transcript.session_id}.md"
        path = output_dir / filename

        header = format_transcript_header_md(
            participant_id=transcript.session_id,
            source_file=transcript.source_file,
            session_date=transcript.session_date.isoformat(),
            duration=format_timecode(transcript.duration_seconds),
            extra_headers=_headers(transcript, sentence_paragraphs),
        )

        lines: list[str] = [header, ""]

        for seg in transcript.segments:
            tc = format_timecode(seg.start_time)
            code = seg.speaker_code or transcript.participant_id
            lines.append(
                format_raw_segment_md(tc, code, seg.speaker_label, seg.line_text)
            )
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        paths.append(path)
        logger.info("Wrote raw transcript (md): %s", path)

    return paths


#: A paragraph this long ends at the next sentence end (the reading rule; see
#: `_merge_same_speaker`). About four sentences of conversational English; people
#: paragraphing TED talks by hand averaged 4.4 sentences (docs/design-transcript-
#: readability.md §3.1). Measured on an 18-minute interview: no paragraph over
#: 150 words, against 73% of all words in such paragraphs under the gap rule alone.
PARAGRAPH_LENGTH = 60

#: Sentence-final punctuation, with an optional closing quote or bracket after it.
_SENTENCE_END = re.compile(r"[.?!…。？！؟۔][\"'”’)\]」』]*$")

#: Scripts written without spaces between words (kana, Han, Thai). Hangul is
#: spaced, so it counts in words like everything else.
_NO_SPACE_CHAR = re.compile(
    "[\u0e00-\u0e7f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
    "\U00020000-\U0003134f]"
)


def reading_length(text: str) -> float:
    """Length in words, counting a no-space character as 0.4 of a word.

    So 60 is about 60 English words or about 150 Japanese characters.
    Punctuation alone is not a word.
    """
    chars = len(_NO_SPACE_CHAR.findall(text))
    rest = _NO_SPACE_CHAR.sub(" ", text)
    return sum(1 for tok in rest.split() if re.search(r"\w", tok)) + 0.4 * chars


def ends_sentence(text: str) -> bool:
    return bool(_SENTENCE_END.search(text.rstrip()))


def _merge_same_speaker(
    segments: list[TranscriptSegment],
    max_gap: float = 2.0,
    *,
    sentence_paragraphs: bool = False,
) -> list[TranscriptSegment]:
    """Merge consecutive segments from the same speaker within max_gap.

    With ``sentence_paragraphs`` a paragraph that has reached
    `PARAGRAPH_LENGTH` also ends at the next sentence end, so a long answer
    reads as several paragraphs instead of one. Breaks fall only between
    segments, never inside one, and never where the text has no sentence end.
    """
    if not segments:
        return []

    merged: list[TranscriptSegment] = [segments[0].model_copy()]
    # Running length of the last paragraph, and whether its newest piece ends a
    # sentence: recomputing either over the whole paragraph made a long
    # unpunctuated monologue quadratic (3,000 segments: 15.9 s against 0.02 s).
    length = reading_length(segments[0].text) if sentence_paragraphs else 0.0
    last_ends = ends_sentence(segments[0].text)

    for seg in segments[1:]:
        prev = merged[-1]
        same_speaker = (
            prev.speaker_label is not None
            and prev.speaker_label == seg.speaker_label
        )
        close = (seg.start_time - prev.end_time) <= max_gap
        full = sentence_paragraphs and length >= PARAGRAPH_LENGTH and last_ends

        if same_speaker and close and (prev.inaudible or seg.inaudible):
            # A gap never joins speech: it stays its own paragraph, and two
            # gaps side by side become one.
            if prev.inaudible and seg.inaudible:
                prev.end_time = max(prev.end_time, seg.end_time)
            else:
                merged.append(seg.model_copy())
                length = reading_length(seg.text) if sentence_paragraphs else 0.0
        elif same_speaker and close and not full:
            prev.end_time = max(prev.end_time, seg.end_time)
            prev.text = f"{prev.text} {seg.text}"
            prev.words.extend(seg.words)
            if sentence_paragraphs:
                length += reading_length(seg.text)
        else:
            merged.append(seg.model_copy())
            length = reading_length(seg.text) if sentence_paragraphs else 0.0
        last_ends = ends_sentence(seg.text)

    return merged
