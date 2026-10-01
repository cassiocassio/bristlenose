"""Stage 3: Parse .srt and .vtt subtitle files into TranscriptSegments.

Two kinds of ``.vtt`` arrive here. A **vendor** file (Teams' download, Zoom's
``Name: text`` cues, a YouTube export) is read as it comes, with every
heuristic on. A **cloud transcript** is one Bristlenose's own import wrote —
it announces itself with a ``NOTE bristlenose-cloud-transcript`` block (the
contract in ``docs/design-cloud-import-transcripts.md`` §4), carries exactly
one ``<v>`` per cue or none at all, and is trusted: no colon heuristic, no
invented speaker. ``read_cloud_transcript_note`` is the reader for that block.
"""

from __future__ import annotations

import html
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from bristlenose.models import (
    CLOUD_TRANSCRIPT_SOURCE,
    SUBTITLE_SOURCES,
    FileType,
    InputFile,
    TranscriptSegment,
)
from bristlenose.utils.timecodes import parse_timecode

__all__ = [
    "CLOUD_TRANSCRIPT_SOURCE",
    "SUBTITLE_PARSER_VERSION",
    "SUBTITLE_SOURCES",
    "CloudTranscriptNote",
    "CloudTranscriptVersionError",
    "parse_subtitle_file",
    "read_cloud_transcript_note",
]

logger = logging.getLogger(__name__)

#: Bump when this module changes what it emits for the same bytes. The
#: pipeline folds it into the transcribe stage's input fingerprint, so a
#: platform-transcript session is re-parsed on the next run instead of served
#: from a cache the old parser wrote (``docs/design-cloud-import-transcripts.md``
#: §0, "The parser version goes into the transcribe input hash").
SUBTITLE_PARSER_VERSION = 2

# One voice span in a cue: <v Speaker Name>text</v>. Teams omits the closing
# tag on the last voice, and a cue can carry two voices back to back, so the
# text runs until the next voice tag, a closing tag, or the end of the cue.
_VTT_VOICE_RE = re.compile(
    r"<v(?:\.[^\s>]*)?\s+([^>]+)>(.*?)(?=<v[\s.]|</v>|$)",
    re.DOTALL,
)

# Kept for its importers (tests pin it): the single-voice form of the above.
_VTT_SPEAKER_PATTERN = re.compile(r"<v\s+([^>]+)>(.+?)(?:</v>)?$", re.DOTALL)

# Speaker label at the start of a cue: "Speaker Name: text". Zoom writes its
# cloud transcripts this way, with whatever the participant typed as their
# display name — any script, a comma before an affiliation, "(Guest)".
#
# The regex only finds the first colon (ASCII or fullwidth); whether what
# precedes it is a name is decided by `_looks_like_speaker_name`, because a
# character class cannot say "letters in any script plus their combining
# marks" and a regex cannot say "but not the word Honestly".
_COLON_SPEAKER_PATTERN = re.compile(r"^(?P<name>[^:：\n]{1,60}?)\s*[:：]\s*(?P<text>\S.*)$")

_NAME_PUNCTUATION = frozenset(" .'’,-()/|&")
_NAME_JOINERS = frozenset("‌‍")  # ZWNJ / ZWJ, inside Indic and Persian names
_MAX_NAME_TOKENS = 6

# Words that open a sentence and take a colon. A mononym ("Suharto: Welcome")
# and a discourse word ("Honestly: I never found it") have the same shape, so
# this is the only thing that tells them apart. Discourse words, labels and
# URL schemes only — never anything that is somebody's given name (Hope,
# Frank, Grace, Will, June and Mark are people).
_NOT_SPEAKER_WORDS = frozenset({
    # English
    "honestly", "note", "notes", "also", "well", "okay", "ok", "yes", "no",
    "right", "basically", "actually", "example", "warning", "question",
    "answer", "summary", "update", "edit", "reminder", "important", "ps",
    "nb", "re", "fwd", "subject", "translation", "transcript", "caption",
    "captions", "anyway", "because", "however", "meanwhile", "finally",
    "obviously", "clearly", "frankly", "seriously", "listen", "wait", "hmm",
    "hm", "oh", "ah", "mm", "mhm", "huh", "hey", "hi", "hello", "thanks",
    "sorry", "please", "cheers", "maybe", "perhaps", "probably", "certainly",
    "sure", "exactly", "totally", "absolutely", "definitely", "really",
    "truly", "yep", "nope", "nah", "um", "uh", "yeah", "like", "so", "then",
    # URL schemes
    "http", "https", "mailto", "tel",
    # German
    "gern", "hinweis", "anmerkung", "beispiel", "frage", "antwort", "achtung",
    "wichtig", "genau", "übrigens", "ähm",
    # Spanish / Portuguese / French
    "nota", "ejemplo", "exemplo", "exemple", "pregunta", "respuesta",
    "resposta", "réponse", "atención", "atenção", "attention", "bueno",
    "pues", "alors", "donc", "voilà", "enfin", "bref", "então", "pois",
})


class CloudTranscriptVersionError(ValueError):
    """The file announces a cloud-transcript contract this reader does not know.

    Raised, never logged-and-skipped: a ``2`` writer may have changed what a
    cue means, and reading it as ``1`` would be a silent misparse. The
    pipeline records it as a parse failure for that file, which is a stated
    row in the run summary.
    """


@dataclass(frozen=True)
class CloudTranscriptNote:
    """The provenance block a cloud-imported transcript carries (§4 item 4)."""

    version: str
    source: str | None  # teams | meet | zoom
    speakers: str | None  # named | none
    language: str | None  # BCP-47 tag as the platform gave it: "pt-BR", "de"
    media: str | None  # the sibling media file's name
    media_duration: float | None  # seconds, from the probe at import time
    rebased_by: float | None  # seconds added to every cue to reach the media's t=0
    dropped_outside_media: int | None  # cues that fell outside the media's span

    @property
    def is_named(self) -> bool:
        return self.speakers == "named"


_NOTE_MARKER = "bristlenose-cloud-transcript"
_SUPPORTED_MAJOR = "1"
_SECONDS_RE = re.compile(r"^(-?\d+(?:\.\d+)?)\s*s?$")


def read_cloud_transcript_note(path: Path) -> CloudTranscriptNote | None:
    """Return the cloud-transcript NOTE from *path*, or None for a vendor file.

    webvtt-py already separates header NOTE blocks from cues
    (``WebVTT.header_comments``), so this reads the file once through the
    same parser the cues come from.

    Raises:
        CloudTranscriptVersionError: the marker names a major version other
            than the one this reader implements. A minor (``1.3``) is accepted
            — a later writer may add fields, and unknown keys are ignored.
    """
    import webvtt

    return _note_from_comments(webvtt.read(str(path)).header_comments)


def _note_from_comments(comments: list[str]) -> CloudTranscriptNote | None:
    for block in comments:
        lines = [ln.strip() for ln in block.strip().splitlines()]
        if not lines:
            continue
        marker = lines[0].split()
        if not marker or marker[0] != _NOTE_MARKER:
            continue
        version = marker[1] if len(marker) > 1 else ""
        if version.split(".")[0] != _SUPPORTED_MAJOR:
            raise CloudTranscriptVersionError(
                f"cloud transcript version {version or '(none)'!s} is not "
                f"supported by this reader (knows {_SUPPORTED_MAJOR}.x)"
            )
        fields: dict[str, str] = {}
        for line in lines[1:]:
            key, sep, value = line.partition(":")
            if sep:
                fields[key.strip().lower()] = html.unescape(value.strip())
        return CloudTranscriptNote(
            version=version,
            source=fields.get("source"),
            speakers=fields.get("speakers"),
            language=fields.get("language"),
            media=fields.get("media"),
            media_duration=_parse_seconds(fields.get("media-duration")),
            rebased_by=_parse_seconds(fields.get("rebased-by")),
            dropped_outside_media=_parse_int(fields.get("dropped-outside-media")),
        )
    return None


def _parse_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    m = _SECONDS_RE.match(value)
    return float(m.group(1)) if m else None


def _parse_int(value: str | None) -> int | None:
    if value is None or not value.lstrip("-").isdigit():
        return None
    return int(value)


def parse_subtitle_file(input_file: InputFile) -> list[TranscriptSegment]:
    """Parse a subtitle file into transcript segments.

    Supports .srt and .vtt formats.
    """
    if input_file.file_type == FileType.SUBTITLE_SRT:
        return _parse_srt(input_file.path)
    elif input_file.file_type == FileType.SUBTITLE_VTT:
        return _parse_vtt(input_file.path)
    else:
        raise ValueError(f"Not a subtitle file: {input_file.file_type}")


def _parse_srt(path: Path) -> list[TranscriptSegment]:
    """Parse an SRT file."""
    import pysrt

    subs = pysrt.open(str(path), encoding="utf-8")
    segments: list[TranscriptSegment] = []

    for sub in subs:
        start = (
            sub.start.hours * 3600
            + sub.start.minutes * 60
            + sub.start.seconds
            + sub.start.milliseconds / 1000
        )
        end = (
            sub.end.hours * 3600
            + sub.end.minutes * 60
            + sub.end.seconds
            + sub.end.milliseconds / 1000
        )
        text = _clean_subtitle_text(sub.text)
        speaker = _extract_speaker(text)
        if speaker:
            text = _remove_speaker_prefix(text, speaker)

        if text.strip():
            segments.append(
                TranscriptSegment(
                    start_time=start,
                    end_time=end,
                    text=text.strip(),
                    speaker_label=speaker,
                    source="srt",
                )
            )

    return _merge_adjacent_segments(segments)


def _parse_vtt(path: Path) -> list[TranscriptSegment]:
    """Parse a WebVTT file."""
    import webvtt

    vtt = webvtt.read(str(path))
    note = _note_from_comments(vtt.header_comments)
    is_cloud = note is not None
    source = CLOUD_TRANSCRIPT_SOURCE if is_cloud else "vtt"

    segments: list[TranscriptSegment] = []

    for caption in vtt:
        start = _vtt_timestamp_to_seconds(caption.start)
        end = _vtt_timestamp_to_seconds(caption.end)
        raw = caption.raw_text or caption.text

        for speaker, text, v_start, v_end in _split_voices(raw, start, end):
            text = html.unescape(_clean_subtitle_text(text))
            if speaker is not None:
                speaker = html.unescape(speaker).strip() or None

            # The colon heuristic is for vendor files that write "Name: text".
            # A cloud transcript's writer put every name in a <v> tag and
            # none in the text, so a colon there is speech.
            if speaker is None and not is_cloud:
                speaker = _extract_speaker(text)
                if speaker:
                    text = _remove_speaker_prefix(text, speaker)

            if text.strip():
                segments.append(
                    TranscriptSegment(
                        start_time=v_start,
                        end_time=v_end,
                        text=text.strip(),
                        speaker_label=speaker,
                        source=source,
                    )
                )

    return _merge_adjacent_segments(segments)


def _split_voices(
    raw: str, start: float, end: float
) -> list[tuple[str | None, str, float, float]]:
    """Split a cue into ``(speaker, text, start, end)`` per voice span.

    A cue with no ``<v>`` is one unnamed span over the whole cue. A cue with
    several voices (Teams packs two speakers into one cue when they overlap)
    gives each voice its own span, the cue's time shared out in proportion to
    how much each said — the real boundary is not in the file, and an even
    share would put a one-word interjection on a par with a paragraph. Every
    span keeps ``end > start`` whenever the cue itself does.
    """
    voices = [(m.group(1), m.group(2)) for m in _VTT_VOICE_RE.finditer(raw)]
    if not voices:
        return [(None, raw, start, end)]

    voices = [(name, text) for name, text in voices if _clean_subtitle_text(text)]
    if not voices:
        return []
    if len(voices) == 1:
        return [(voices[0][0], voices[0][1], start, end)]

    weights = [max(1, len(_clean_subtitle_text(text))) for _, text in voices]
    total = float(sum(weights))
    span = end - start
    spans: list[tuple[str | None, str, float, float]] = []
    cursor = start
    for i, ((name, text), weight) in enumerate(zip(voices, weights, strict=True)):
        v_end = end if i == len(voices) - 1 else cursor + span * (weight / total)
        spans.append((name, text, cursor, v_end))
        cursor = v_end
    return spans


def _vtt_timestamp_to_seconds(ts: str) -> float:
    """Convert a VTT timestamp string to seconds."""
    return parse_timecode(ts)


def _clean_subtitle_text(text: str) -> str:
    """Remove HTML tags and common subtitle artefacts."""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Remove position/alignment cues
    text = re.sub(r"\{\\an?\d+\}", "", text)
    # Normalise whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_speaker(text: str) -> str | None:
    """Try to extract a speaker label from the text."""
    match = _COLON_SPEAKER_PATTERN.match(text)
    if not match:
        return None
    name = match.group("name").strip()
    return name if _looks_like_speaker_name(name) else None


def _looks_like_speaker_name(name: str) -> bool:
    """Is the text before a colon a display name, rather than a clause?

    Letters in any script with their combining marks, the punctuation real
    display names carry (``O'Brien``, ``Jean-Pierre``, ``Dr.``, ``Gupta, WUD``,
    ``(Guest)``, ``(she/her)``, ``Name | Team``), at most six words, no
    digits, and not a word that merely opens a sentence.
    """
    if not name or not name[0].isalpha():
        return False
    if len(name.split()) > _MAX_NAME_TOKENS:
        return False
    for ch in name:
        if ch.isalpha() or ch in _NAME_PUNCTUATION or ch in _NAME_JOINERS:
            continue
        if unicodedata.category(ch).startswith("M"):
            continue
        return False
    if name.lower() in _NOT_SPEAKER_WORDS:
        return False
    return True


def _remove_speaker_prefix(text: str, speaker: str) -> str:
    """Remove the speaker prefix from text."""
    pattern = re.escape(speaker) + r"\s*[:：]\s*"
    return re.sub(f"^{pattern}", "", text, count=1)


def _merge_adjacent_segments(
    segments: list[TranscriptSegment],
    max_gap: float = 2.0,
) -> list[TranscriptSegment]:
    """Merge consecutive segments from the same speaker that are close together.

    Args:
        segments: Sorted list of segments.
        max_gap: Maximum gap in seconds to merge across.
    """
    if not segments:
        return []

    merged: list[TranscriptSegment] = [segments[0].model_copy()]

    for seg in segments[1:]:
        prev = merged[-1]
        same_speaker = (
            prev.speaker_label is not None
            and prev.speaker_label == seg.speaker_label
        )
        close_enough = (seg.start_time - prev.end_time) <= max_gap

        if same_speaker and close_enough:
            # Merge: extend the previous segment
            prev.end_time = seg.end_time
            prev.text = f"{prev.text} {seg.text}"
            prev.words.extend(seg.words)
        else:
            merged.append(seg.model_copy())

    return merged
