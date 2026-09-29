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
removes audible words from the subtitles. A bracketed group the researcher
put in place of spoken words (``Sarah`` → ``[her]``) is shown — their edit
wins; one they only inserted (``it [the app] crashed``) is not spoken and is
dropped. A correction that can't be placed word by word is not applied at
all: the transcript's own words stand, and the caller logs it. Never a
guess that could delete or repeat what was said.

Frozen dataclasses rather than Pydantic, like the sibling ``clip_manifest``:
pure internal values shared with a future AVFoundation backend, never parsed
from or serialised to the outside.
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
#: or a real name in brackets — the prefix the importer strips before
#: matching word timings (``importer._SPEAKER_PREFIX_RE``). Never subtitled.
#: One level of nesting is allowed, because a Teams or Zoom display name can
#: carry its own brackets: ``(Robert (Bob) Smith)`` must go whole, or the
#: surname is left on screen.
_SPEAKER_PREFIX = re.compile(r"^\((?:[^()]|\([^()]*\))*\)\s*")
_NORM_STRIP = re.compile(r"[^\w']+", re.UNICODE)
#: Elision marks in a quote are the pipeline's tidying, never spoken.
_ELISION = re.compile(r"^(…|\.\.\.)$")
#: A researcher's edit, tokenised with a bracketed group as ONE token, so
#: ``[the app]`` is a single editorial unit rather than ``[the`` + ``app]``.
_EDIT_TOKEN = re.compile(r"\[[^\]]*\][^\s\[]*|[^\s\[]+")
_BRACKETED = re.compile(r"^\[[^\]]*\]")
_WORD_CORE = re.compile(r"^(\W*)(.*?)(\W*)$", re.DOTALL)
#: How far past a quote's recorded end its corrected words may be spoken.
#: Quote end times come from the model, which sees only segment start times,
#: so a quote's last words often fall after them (measured 29 Sep 2026: 19 of
#: 33 IKEA quotes, 40 of 80 Rockclimbing). The route widens its query by the
#: same margin.
CORRECTION_TAIL_SECONDS = 10.0
#: Outcomes of ``apply_correction``.
APPLIED, UNPLACED, NO_WORDS = "applied", "unplaced", "no-words"


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
    #: The quote's DOM id (``q-p1-123``), so a log line can name it.
    quote_ref: str = ""


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


def _edit_tokens(text: str) -> list[str]:
    """Tokens of a quote or its edit: bracket groups whole, elisions dropped."""
    return [tok for tok in _EDIT_TOKEN.findall(text) if not _ELISION.match(tok)]


def _edit_key(token: str) -> str:
    """Comparison key: a bracket group never equals a spoken word."""
    if _BRACKETED.match(token):
        return "\x00" + token
    return _norm(token)


def _respell(spoken: str, researcher: str) -> str:
    """The researcher's letters inside the transcript word's own punctuation."""
    lead, _core, trail = _WORD_CORE.match(spoken).groups()  # type: ignore[union-attr]
    _l, core, _t = _WORD_CORE.match(researcher).groups()  # type: ignore[union-attr]
    return f"{lead}{core}{trail}"


def _retime(texts: list[str], start: float, end: float, speaker: str) -> list[Token]:
    return [
        Token(text=t, start=s, end=e, speaker_code=speaker)
        for t, (s, e) in zip(texts, spread_evenly(texts, start, end))
    ]


def apply_correction(tokens: list[Token], corr: Correction) -> tuple[list[Token], str]:
    """Apply one researcher correction to ``tokens``.

    Returns the new token list and an outcome: ``APPLIED``, ``UNPLACED`` (the
    change could not be placed word by word, so nothing was changed) or
    ``NO_WORDS`` (no words of that speaker near the quote). Tokens of other
    speakers, and words outside the quote, are never touched.
    """
    span = [
        i for i, t in enumerate(tokens)
        if t.speaker_code == corr.speaker_code
        and corr.start - 1.0 <= (t.start + t.end) / 2 <= corr.end + CORRECTION_TAIL_SECONDS
    ]
    corrected = _edit_tokens(corr.corrected)
    if not span or not corrected:
        return tokens, NO_WORDS
    span_tokens = [tokens[i] for i in span]

    original = _edit_tokens(corr.original)
    researcher = difflib.SequenceMatcher(
        None, [_edit_key(t) for t in original], [_edit_key(t) for t in corrected],
        autojunk=False,
    )
    # Map each original-quote token to its word in the transcript span. The
    # span may run past the quote; extra words simply stay unmatched.
    to_span = difflib.SequenceMatcher(
        None, [_edit_key(t) for t in original], [_norm(t.text) for t in span_tokens],
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
                    respelled[mapped] = _respell(span_tokens[mapped].text, c)
        elif tag == "replace":
            # A bracket that stands in for spoken words on its own
            # (``Sarah`` -> ``[her]``) is the researcher's substitution and is
            # shown. Beside real words (``cube ernetes`` -> ``[the] Kubernetes``)
            # it is editorial and dropped, like an inserted one.
            if any(not _BRACKETED.match(w) for w in new):
                new = [w for w in new if not _BRACKETED.match(w)]
            ks: list[int] = []
            for i in range(i1, i2):
                mapped = orig_to_span.get(i)
                if mapped is not None:
                    ks.append(mapped)
            if len(ks) != i2 - i1 or ks != list(range(ks[0], ks[0] + len(ks))):
                return tokens, UNPLACED
            replaced[ks[0]] = (ks[-1] + 1, new)
        elif tag == "insert":
            # A bracket only inserted is editorial, never spoken: dropped.
            spoken = [w for w in new if not _BRACKETED.match(w)]
            if not spoken:
                continue
            prev = orig_to_span.get(i1 - 1) if i1 > 0 else None
            nxt = orig_to_span.get(i1) if i1 < len(original) else None
            if prev is not None:
                after.setdefault(prev, []).extend(spoken)
            elif nxt is not None:
                before.setdefault(nxt, []).extend(spoken)
            else:
                return tokens, UNPLACED
        # "delete" is ignored: the audio still carries those words.

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

    # Other speakers' words inside the span stay; the corrected speaker's
    # words go back in where the span began. Order is restored by time in
    # build_cues, so an interjection still lands in the right place.
    in_span = set(span)
    rest = [t for i, t in enumerate(tokens) if i not in in_span]
    return rest[:span[0]] + rebuilt + rest[span[0]:], APPLIED


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
    # A cue with no time on screen can't be read, and the mov_text track
    # turns one into an empty event (measured 29 Sep 2026): drop it. Crosstalk
    # merging is the fuller fix, parked (review log, export-clips, Finding 8).
    return [cue for cue in cues if cue.end > cue.start]


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
            # SRT has no escape for markup, and ffmpeg's SRT reader also takes
            # ``\N`` as a line break and ``{\…}`` as a style override (a
            # doubled backslash does not help — measured 29 Sep 2026). Swap
            # the characters for look-alikes so the words survive as written.
            parts.append(
                line.replace("<", "‹").replace(">", "›").replace("\\", "\u29f5")
            )
        parts.append("")
    return "\n".join(parts)
