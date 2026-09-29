"""Subtitles for exported clips: timed tokens → cues → WebVTT / SRT.

Pure logic, like ``clip_manifest``: no DB, no filesystem, no subprocess.
The route loads transcript segments and researcher corrections, this module
turns them into cues, and the backend muxes them into the clip.

Styling follows the BBC Subtitle Guidelines
(bbc.co.uk/accessibility/forproducts/guides/subtitles/), which the
maintainer adopted as the spec on 29 Sep 2026 (docs/design-export-clips.md
§ Future: subtitles on clips):

- at most 2 lines per cue (§3.3), at most 37 characters per line (§3.1);
- no speaker labels; speakers are told apart by colour, in the BBC order
  white, yellow, cyan, green (§8.3). The clip's own participant is always
  white, and anyone else takes the next colour in order of first appearance.

Everything audible in the clip range is subtitled, whoever is speaking.

Timings come from Whisper's word timings where the transcript has them.
Where it doesn't (platform transcripts, or a PII-redacted project, whose
word timings are deliberately dropped), each segment's text is spread
across the segment's time in proportion to character count.

A researcher's quote correction (acronyms, product names, mis-hearings) is
applied as the difference between the pipeline's quote text and the edited
text, so the pipeline's own tidying (dropped fillers, ``…`` elisions) never
removes audible words from the subtitles. A change that can't be placed in
the transcript falls back to the corrected wording spread evenly across the
time the participant spoke the quote.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, replace

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: BBC §3.1 — the character count for a line (broadcast figure).
MAX_LINE_CHARS = 37
#: BBC §3.3 — at most two lines per cue.
MAX_LINES = 2
#: Netflix General Requirements: an event is at most 7 s and at least 5/6 s.
MAX_CUE_SECONDS = 7.0
MIN_CUE_SECONDS = 5 / 6
#: A cue already this long is closed at the end of a sentence rather than
#: carrying the next sentence's first words.
_SENTENCE_BREAK_MIN_CHARS = 20

#: BBC §8.3 speaker colours, in order. The first is the clip's participant.
SPEAKER_COLOURS: tuple[str, ...] = ("white", "yellow", "cyan", "green")
#: WebVTT's built-in colour classes spell BBC green (#00FF00) as ``lime``.
_VTT_CLASS = {"yellow": "yellow", "cyan": "cyan", "green": "lime"}

_SENTENCE_END = re.compile(r"[.?!…]['\"”’)]*$")
#: A line may end after these; a break there reads more naturally (BBC §3.1:
#: break at natural linguistic points).
_CLAUSE_END = re.compile(r"[,;:.?!…]['\"”’)]*$")
#: How much longer a line may be to buy a break at a clause end.
_CLAUSE_BREAK_SLACK = 6
#: A segment's text can open with its speaker's label, e.g. ``(Speaker B)``
#: or a real name in brackets — the same prefix the importer strips before
#: matching word timings (``importer._SPEAKER_PREFIX_RE``). Never subtitled.
_SPEAKER_PREFIX = re.compile(r"^\([^)]*\)\s*")
_NORM_STRIP = re.compile(r"[^\w']+", re.UNICODE)
#: Tokens a researcher's edit carries that are never spoken: elision marks
#: and bracketed editorial insertions such as ``[the app]``.
_UNSPOKEN = re.compile(r"^(…|\.\.\.|\[.*\])$")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WordTiming:
    """One word as the transcriber timed it (``words_json`` row)."""

    text: str
    start: float
    end: float


@dataclass(frozen=True)
class SegmentInput:
    """One transcript segment, as stored in ``transcript_segments``."""

    speaker_code: str
    start: float
    end: float
    text: str
    words: tuple[WordTiming, ...] | None = None


@dataclass(frozen=True)
class Correction:
    """A researcher's edit of a quote: pipeline text → corrected text."""

    speaker_code: str
    start: float
    end: float
    original: str
    corrected: str


@dataclass(frozen=True)
class Token:
    """A word to be shown, with its time in the source recording."""

    text: str
    start: float
    end: float
    speaker_code: str


@dataclass(frozen=True)
class Cue:
    """One subtitle event, in clip time (0 = the clip's first frame)."""

    start: float
    end: float
    speaker_code: str
    colour: str
    lines: tuple[str, ...]


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------


def _norm(text: str) -> str:
    return _NORM_STRIP.sub("", text.lower())


def spread_evenly(texts: list[str], start: float, end: float) -> list[tuple[float, float]]:
    """Share ``[start, end]`` across ``texts`` in proportion to their length."""
    if not texts:
        return []
    end = max(end, start)
    weights = [len(t) + 1 for t in texts]
    total = sum(weights)
    spans: list[tuple[float, float]] = []
    cursor = start
    for w in weights:
        nxt = cursor + (end - start) * w / total
        spans.append((cursor, nxt))
        cursor = nxt
    return spans


def _align_times(
    tokens: list[str], timed: tuple[WordTiming, ...], start: float, end: float,
) -> list[tuple[float, float]]:
    """Give each token a time: its matched word's where the words agree,
    otherwise spread across the gap between its matched neighbours."""
    times: list[tuple[float, float] | None] = [None] * len(tokens)
    matcher = difflib.SequenceMatcher(
        None, [_norm(t) for t in tokens], [_norm(w.text) for w in timed], autojunk=False,
    )
    for tag, i1, i2, j1, _j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                w = timed[j1 + k]
                times[i1 + k] = (w.start, w.end)

    out: list[tuple[float, float]] = []
    i = 0
    prev_end = start
    while i < len(tokens):
        known = times[i]
        if known is not None:
            s, e = max(known[0], prev_end), max(known[1], known[0], prev_end)
            out.append((s, e))
            prev_end = e
            i += 1
            continue
        j = i
        while j < len(tokens) and times[j] is None:
            j += 1
        nxt = times[j] if j < len(tokens) else None
        gap_end = nxt[0] if nxt is not None else end
        out.extend(spread_evenly(tokens[i:j], prev_end, max(gap_end, prev_end)))
        prev_end = out[-1][1]
        i = j
    return out


def tokens_for_segment(seg: SegmentInput) -> list[Token]:
    """Split a segment into timed tokens (word timings, or an even spread)."""
    words = _SPEAKER_PREFIX.sub("", seg.text.strip()).split()
    if not words:
        return []
    if seg.words:
        spans = _align_times(words, seg.words, seg.start, seg.end)
    else:
        spans = spread_evenly(words, seg.start, seg.end)
    return [
        Token(text=w, start=s, end=e, speaker_code=seg.speaker_code)
        for w, (s, e) in zip(words, spans)
    ]


# ---------------------------------------------------------------------------
# Researcher corrections
# ---------------------------------------------------------------------------


def _spoken(text: str) -> list[str]:
    return [t for t in text.split() if not _UNSPOKEN.match(t)]


def _retime(texts: list[str], start: float, end: float, speaker: str) -> list[Token]:
    return [
        Token(text=t, start=s, end=e, speaker_code=speaker)
        for t, (s, e) in zip(texts, spread_evenly(texts, start, end))
    ]


def apply_correction(tokens: list[Token], corr: Correction) -> tuple[list[Token], bool]:
    """Apply one researcher correction to ``tokens``.

    Returns the new token list and whether the even-spread fallback was used.
    Tokens outside the quote's speaker and time are never touched.
    """
    span = [
        i for i, t in enumerate(tokens)
        if t.speaker_code == corr.speaker_code
        and corr.start <= (t.start + t.end) / 2 <= corr.end
    ]
    corrected = _spoken(corr.corrected)
    if not span or not corrected:
        return tokens, False
    # The span is contiguous in time for one speaker; other speakers' words
    # inside it (an interjection) stay where they are.
    span_tokens = [tokens[i] for i in span]

    original = _spoken(corr.original)
    researcher = difflib.SequenceMatcher(
        None, [_norm(t) for t in original], [_norm(t) for t in corrected], autojunk=False,
    )
    # Map each original-quote token to its token in the transcript span.
    to_span = difflib.SequenceMatcher(
        None, [_norm(t) for t in original], [_norm(t.text) for t in span_tokens],
        autojunk=False,
    )
    orig_to_span: dict[int, int] = {}
    for tag, i1, i2, j1, _j2 in to_span.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                orig_to_span[i1 + k] = j1 + k

    # Three kinds of change, keyed by the transcript-span word they touch, so
    # a respelling and an insertion beside the same word compose.
    replaced: dict[int, tuple[int, list[str]]] = {}  # first word -> (end, new words)
    respelled: dict[int, str] = {}                   # word -> researcher's spelling
    after: dict[int, list[str]] = {}                 # word -> words inserted after it
    before: dict[int, list[str]] = {}                # word -> words inserted before it
    placed = True
    for tag, i1, i2, j1, j2 in researcher.get_opcodes():
        new = corrected[j1:j2]
        if tag == "equal":
            # Same word, different capitals: ``ux`` -> ``UX``, ``iphone`` ->
            # ``iPhone``. A punctuation-only difference is the quote's own
            # tidying (or a trimmed quote's moved full stop), so it is left.
            for k in range(i2 - i1):
                mapped = orig_to_span.get(i1 + k)
                o, c = original[i1 + k], corrected[j1 + k]
                if mapped is not None and _NORM_STRIP.sub("", o) != _NORM_STRIP.sub("", c):
                    respelled[mapped] = c
        elif tag == "replace":
            ks: list[int] = []
            for i in range(i1, i2):
                mapped = orig_to_span.get(i)
                if mapped is not None:
                    ks.append(mapped)
            if len(ks) != i2 - i1 or ks != list(range(ks[0], ks[0] + len(ks))):
                placed = False
                break
            replaced[ks[0]] = (ks[-1] + 1, new)
        elif tag == "insert":
            prev = orig_to_span.get(i1 - 1) if i1 > 0 else None
            nxt = orig_to_span.get(i1) if i1 < len(original) else None
            if prev is not None:
                after.setdefault(prev, []).extend(new)
            elif nxt is not None:
                before.setdefault(nxt, []).extend(new)
            else:
                placed = False
                break
        # "delete" is ignored: the audio still carries those words.

    fallback = not placed
    if fallback:
        first, last = span_tokens[0], span_tokens[-1]
        span_tokens = _retime(corrected, first.start, last.end, corr.speaker_code)
    else:
        rebuilt: list[Token] = []
        i = 0
        while i < len(span_tokens):
            tok = span_tokens[i]
            if i in replaced:
                stop, words = replaced[i]
                start, end = tok.start, span_tokens[stop - 1].end
                words = [*before.get(i, []), *words, *after.get(stop - 1, [])]
                rebuilt.extend(_retime(words, start, end, corr.speaker_code))
                i = stop
                continue
            words = [*before.get(i, []), respelled.get(i, tok.text), *after.get(i, [])]
            if len(words) == 1:
                rebuilt.append(replace(tok, text=words[0]))
            else:
                # Inserted words share the neighbouring word's time.
                rebuilt.extend(_retime(words, tok.start, tok.end, corr.speaker_code))
            i += 1
        span_tokens = rebuilt

    # Other speakers' words inside the span stay; the corrected speaker's
    # words go back in where the span began. Order is restored by time in
    # build_cues, so an interjection still lands in the right place.
    in_span = set(span)
    rest = [t for i, t in enumerate(tokens) if i not in in_span]
    return rest[:span[0]] + span_tokens + rest[span[0]:], fallback


# ---------------------------------------------------------------------------
# Cues
# ---------------------------------------------------------------------------


def wrap_lines(words: list[str]) -> tuple[str, ...] | None:
    """Wrap words into at most 2 lines of at most 37 characters.

    Picks the break that keeps the longer line shortest, preferring a break
    after a comma or full stop when that costs a few characters, and a
    shorter top line on a tie. Returns None when the words won't fit. A single word
    longer than a line (a URL) is allowed on a line of its own.
    """
    text = " ".join(words)
    if len(text) <= MAX_LINE_CHARS or len(words) == 1:
        return (text,)
    best: tuple[int, int, int] | None = None  # (longest, top length, break index)
    for k in range(1, len(words)):
        top, bottom = " ".join(words[:k]), " ".join(words[k:])
        if len(top) > MAX_LINE_CHARS or len(bottom) > MAX_LINE_CHARS:
            continue
        penalty = 0 if _CLAUSE_END.search(words[k - 1]) else _CLAUSE_BREAK_SLACK
        key = (max(len(top), len(bottom)) + penalty, len(top), k)
        if best is None or key < best:
            best = key
    if best is None:
        return None
    k = best[2]
    return (" ".join(words[:k]), " ".join(words[k:]))


def assign_colours(speakers_in_order: list[str], primary: str) -> dict[str, str]:
    """BBC order: the clip's participant is white, others follow in order."""
    colours = {primary: SPEAKER_COLOURS[0]}
    others = SPEAKER_COLOURS[1:]
    n = 0
    for code in speakers_in_order:
        if code not in colours:
            colours[code] = others[n % len(others)]
            n += 1
    return colours


def build_cues(
    tokens: list[Token], clip_start: float, clip_end: float, primary_speaker: str,
) -> list[Cue]:
    """Turn source-time tokens into clip-time cues for ``[clip_start, clip_end]``."""
    duration = max(clip_end - clip_start, 0.0)
    inside = [
        replace(
            t,
            start=min(max(t.start - clip_start, 0.0), duration),
            end=min(max(t.end - clip_start, 0.0), duration),
        )
        for t in sorted(tokens, key=lambda t: t.start)
        if t.end > clip_start and t.start < clip_end
    ]
    if not inside:
        return []

    groups: list[list[Token]] = []
    current: list[Token] = []
    for tok in inside:
        if current:
            same_speaker = tok.speaker_code == current[0].speaker_code
            fits = wrap_lines([t.text for t in current] + [tok.text]) is not None
            short_enough = tok.end - current[0].start <= MAX_CUE_SECONDS
            chars = len(" ".join(t.text for t in current))
            sentence_break = (
                _SENTENCE_END.search(current[-1].text) is not None
                and chars >= _SENTENCE_BREAK_MIN_CHARS
            )
            if not (same_speaker and fits and short_enough) or sentence_break:
                groups.append(current)
                current = []
        current.append(tok)
    if current:
        groups.append(current)

    colours = assign_colours([g[0].speaker_code for g in groups], primary_speaker)
    cues: list[Cue] = []
    for g in groups:
        lines = wrap_lines([t.text for t in g]) or (" ".join(t.text for t in g),)
        cues.append(Cue(
            start=g[0].start,
            end=g[-1].end,
            speaker_code=g[0].speaker_code,
            colour=colours[g[0].speaker_code],
            lines=lines,
        ))

    # Minimum duration, never running into the next cue or past the clip.
    for i, cue in enumerate(cues):
        limit = cues[i + 1].start if i + 1 < len(cues) else duration
        end = max(cue.end, min(cue.start + MIN_CUE_SECONDS, limit))
        cues[i] = replace(cue, end=max(end, cue.start))
    return cues


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def _timestamp(seconds: float, sep: str) -> str:
    ms_total = int(round(max(seconds, 0.0) * 1000))
    h, rem = divmod(ms_total, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def _vtt_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_webvtt(cues: list[Cue]) -> str:
    """WebVTT with no labels; non-white speakers use WebVTT's colour classes."""
    parts = ["WEBVTT", ""]
    for cue in cues:
        parts.append(f"{_timestamp(cue.start, '.')} --> {_timestamp(cue.end, '.')}")
        cls = _VTT_CLASS.get(cue.colour)
        for line in cue.lines:
            body = _vtt_escape(line)
            parts.append(f"<c.{cls}>{body}</c>" if cls else body)
        parts.append("")
    return "\n".join(parts)


def to_srt(cues: list[Cue]) -> str:
    """Plain SRT, the input ffmpeg muxes into the clip's ``mov_text`` track.

    Uncoloured on purpose: ffmpeg 8.1.1's ``mov_text`` encoder keeps bold and
    italic but drops a colour override, writing no style record for it
    (measured 29 Sep 2026). A ``<font color>`` here would be thrown away
    silently, so the embedded track is plain and the ``.vtt`` carries colour.
    """
    parts: list[str] = []
    for n, cue in enumerate(cues, start=1):
        parts.append(str(n))
        parts.append(f"{_timestamp(cue.start, ',')} --> {_timestamp(cue.end, ',')}")
        for line in cue.lines:
            # SRT has no escape for markup; keep a literal bracket from
            # being read as a tag.
            parts.append(line.replace("<", "‹").replace(">", "›"))
        parts.append("")
    return "\n".join(parts)
