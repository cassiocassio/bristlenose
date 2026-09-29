"""Subtitles for exported clips: timed tokens → cues → WebVTT / SRT.

Pure logic, like ``clip_manifest``: no DB, no filesystem, no subprocess.
The route loads transcript segments and researcher corrections, this module
turns them into cues, and the backend muxes them into the clip.

Styling follows the BBC Subtitle Guidelines
(bbc.co.uk/accessibility/forproducts/guides/subtitles/), which the
maintainer adopted as the spec on 29 Sep 2026 (docs/design-export-clips.md
§ Future: subtitles on clips):

- at most 2 lines per cue (§3.3), at most 37 characters per line (§3.1);
- Japanese and Chinese, which the BBC doesn't cover, take Netflix's line
  lengths (13 and 16 full-width characters) and break between characters,
  never before closing punctuation or after an opening bracket (kinsoku);
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
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: BBC §3.1 — the character count for a line (broadcast figure).
MAX_LINE_CHARS = 37
#: The BBC gives no figure for Japanese or Chinese, so these extend the spec
#: (decided 29 Sep 2026, docs/design-export-clips.md § Styling). Netflix's
#: Japanese Timed Text Style Guide: 13 full-width characters per horizontal
#: line, a half-width character counting 0.5. Its Traditional Chinese guide:
#: 16 characters. Measured in full-width units by ``_cjk_width``.
MAX_LINE_WIDTH_JA = 13
MAX_LINE_WIDTH_ZH = 16
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

_SENTENCE_END = re.compile(r"[.?!…。？！．]['\"”’)」』）】]*$")
#: A line may end after these; a break there reads more naturally (BBC §3.1:
#: break at natural linguistic points).
_CLAUSE_END = re.compile(r"[,;:.?!…、。，；：．？！]['\"”’)」』）】]*$")
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

#: Scripts written without spaces: CJK punctuation, kana, Bopomofo, Han, and
#: full-width punctuation. Full-width letters and digits are left out, so
#: ``２０２６`` stays one run like ``2026``. Hangul is written with spaces and
#: is not here.
_CJK_CHAR = re.compile(
    "[\u2e80-\u2fdf\u3000-\u303f\u3040-\u30ff\u3100-\u312f\u3190-\u31ff"
    "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\ufe30-\ufe4f\uff01-\uff0f"
    "\uff1a-\uff20\uff3b-\uff40\uff5b-\uff9f\U00020000-\U0003134f]"
)
_KANA = re.compile("[\u3040-\u30ff\u31f0-\u31ff\uff66-\uff9f]")
_HAN = re.compile("[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0003134f]")
#: Kinsoku: may not open a line (W3C JLREQ cl-02 to cl-07 and cl-10 —
#: closing brackets, stops, commas, middle dots, small kana, the long vowel
#: mark, iteration marks; CLREQ agrees for Chinese). Joined to the character
#: before, so no break can fall ahead of them.
_NO_LINE_START = frozenset(
    "、。，．！？‼⁇⁈⁉；：・」』）］｝〕〉》】〙〗〟’”｠»…‥〜゠"
    "ぁぃぅぇぉっゃゅょゎゕゖァィゥェォッャュョヮヵヶㇰㇱㇲㇳㇴㇵㇶㇷㇸㇹㇺㇻㇼㇽㇾㇿ"
    "ーゝゞヽヾ々〻"
)
#: Kinsoku: may not close a line. Joined to the character after.
_NO_LINE_END = frozenset("「『（［｛〔〈《【〘〖〝‘“｟«([{")


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
    #: What goes between this token and the one before it on a line: the
    #: transcript's own spacing (``""`` inside a run of Japanese or Chinese),
    #: or None to decide by script (``_join``).
    sep: str | None = None


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


def _split_cjk(chunk: str) -> list[str]:
    """Split a space-free chunk into the units a line may break between.

    Latin text is returned whole. Japanese and Chinese become one character
    each, with a run of Latin letters or digits inside them kept whole
    (``Figmaで`` → ``Figma``, ``で``), closing punctuation joined to the
    character before and an opening bracket to the character after.
    """
    if not _CJK_CHAR.search(chunk):
        return [chunk]
    pieces: list[str] = []
    pending = ""  # opening brackets waiting for what they open
    in_run = False  # the last piece is a Latin run still being read
    for c in chunk:
        cjk = _CJK_CHAR.match(c) is not None
        if not cjk and in_run:
            pieces[-1] += c
            continue
        if c in _NO_LINE_START and pieces and not pending:
            pieces[-1] += c
            in_run = False
            continue
        if c in _NO_LINE_END:
            pending += c
            continue
        pieces.append(pending + c)
        pending = ""
        in_run = not cjk
    if pending:
        if pieces:
            pieces[-1] += pending
        else:
            pieces.append(pending)
    return pieces


def _pieces(text: str) -> list[tuple[str, str | None]]:
    """``(piece, sep)`` for each unit of ``text``, keeping its own spacing."""
    out: list[tuple[str, str | None]] = []
    for chunk in text.split():
        for k, piece in enumerate(_split_cjk(chunk)):
            out.append((piece, None if not out else (" " if k == 0 else "")))
    return out


def _split_timing(word: WordTiming) -> tuple[WordTiming, ...]:
    """A timed word cut into the same units as the text, sharing its time.

    Whisper times Japanese and Chinese in chunks of several characters, so
    each character takes its share of its chunk's time.
    """
    pieces = [p for chunk in word.text.split() for p in _split_cjk(chunk)]
    if len(pieces) <= 1:
        return (word,)
    return tuple(
        WordTiming(text=p, start=s, end=e)
        for p, (s, e) in zip(pieces, spread_evenly(pieces, word.start, word.end))
    )


def _cjk_width(line: str) -> float:
    """A line's width in full-width characters: half-width ones count 0.5."""
    return sum(1.0 if unicodedata.east_asian_width(c) in "WF" else 0.5 for c in line)


def _measure(text: str) -> tuple[Callable[[str], float], float]:
    """How to measure a line of ``text``, and its limit, by the text's script."""
    if _KANA.search(text):
        return _cjk_width, MAX_LINE_WIDTH_JA
    if _HAN.search(text):
        return _cjk_width, MAX_LINE_WIDTH_ZH
    return len, MAX_LINE_CHARS


def _join(texts: Sequence[str], seps: Sequence[str | None]) -> str:
    """Join tokens into a line: their own spacing, else a space unless
    either side is Japanese or Chinese."""
    if not texts:
        return ""
    out = texts[0]
    for prev, text, sep in zip(texts, texts[1:], seps[1:]):
        if sep is None:
            cjk = _CJK_CHAR.match(prev[-1:]) or _CJK_CHAR.match(text[:1])
            sep = "" if cjk else " "
        out += sep + text
    return out


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
    """Split a segment into timed tokens (word timings, or an even spread).

    A token is a word, or in Japanese and Chinese a character (``_split_cjk``).
    """
    pieces = _pieces(_SPEAKER_PREFIX.sub("", seg.text.strip()))
    if not pieces:
        return []
    words = [p for p, _sep in pieces]
    if seg.words:
        timed = tuple(t for w in seg.words for t in _split_timing(w))
        spans = _align_times(words, timed, seg.start, seg.end)
    else:
        spans = spread_evenly(words, seg.start, seg.end)
    return [
        Token(text=w, start=s, end=e, speaker_code=seg.speaker_code, sep=sep)
        for (w, sep), (s, e) in zip(pieces, spans)
    ]


# ---------------------------------------------------------------------------
# Researcher corrections
# ---------------------------------------------------------------------------


def _edit_tokens(text: str) -> list[str]:
    """Tokens of a quote or its edit: bracket groups whole, elisions dropped,
    Japanese and Chinese split as the transcript is (``_split_cjk``)."""
    return [
        piece
        for tok in _EDIT_TOKEN.findall(text) if not _ELISION.match(tok)
        for piece in ([tok] if _BRACKETED.match(tok) else _split_cjk(tok))
    ]


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


def wrap_lines(
    words: list[str], seps: Sequence[str | None] | None = None,
) -> tuple[str, ...] | None:
    """Wrap words into at most 2 lines of at most 37 characters, or 13 / 16
    full-width characters for Japanese / Chinese (``_measure``).

    Picks the break that keeps the longer line shortest, preferring a break
    after a comma or full stop when that costs a few characters, and a
    shorter top line on a tie. Returns None when the words won't fit. A single word
    longer than a line (a URL) is allowed on a line of its own. ``seps`` is
    each word's ``Token.sep``; by default words are joined by script.
    """
    seps = list(seps) if seps is not None else [None] * len(words)
    text = _join(words, seps)
    width, limit = _measure(text)
    if width(text) <= limit or len(words) == 1:
        return (text,)
    # Between words a clause end is worth a few characters. Between Japanese
    # or Chinese characters any other break falls inside a word, so a clause
    # end is worth up to half a line.
    slack = _CLAUSE_BREAK_SLACK if limit == MAX_LINE_CHARS else limit / 2
    best: tuple[float, float, int] | None = None  # (longest, top length, break index)
    for k in range(1, len(words)):
        top, bottom = _join(words[:k], seps[:k]), _join(words[k:], seps[k:])
        top_w, bottom_w = width(top), width(bottom)
        if top_w > limit or bottom_w > limit:
            continue
        penalty = 0 if _CLAUSE_END.search(words[k - 1]) else slack
        key = (max(top_w, bottom_w) + penalty, top_w, k)
        if best is None or key < best:
            best = key
    if best is None:
        return None
    k = best[2]
    return (_join(words[:k], seps[:k]), _join(words[k:], seps[k:]))


def _clause_carry(current: list[Token], tok: Token) -> list[Token]:
    """Japanese and Chinese: the tokens to move from a full cue to the next.

    Filling a cue to the last character that fits breaks mid-word and can
    leave a character or two to flash up alone (``で。`` for 0.4 s, measured
    on the ja-JP demo, 29 Sep 2026). So the cue ends at its last clause end
    in its back half instead, if what follows still makes a cue with ``tok``.
    Latin text needs none of this: it already breaks between words.
    """
    for i in range(len(current) - 2, len(current) // 2 - 1, -1):
        if _CLAUSE_END.search(current[i].text):
            carry = current[i + 1:]
            nxt = [*carry, tok]
            if (
                tok.end - carry[0].start <= MAX_CUE_SECONDS
                and wrap_lines([t.text for t in nxt], [t.sep for t in nxt]) is not None
            ):
                return carry
            return []
    return []


def _fill_runts(groups: list[list[Token]]) -> None:
    """Japanese and Chinese: give a runt cue characters from the one before.

    Where a sentence has no clause end to break at, its last character or two
    can still land alone (``ン。`` for 0.4 s). Move characters back from the
    same speaker's previous cue until the runt is a third of a line wide.
    """
    for i in range(1, len(groups)):
        prev, runt = groups[i - 1], groups[i]
        if prev[-1].speaker_code != runt[0].speaker_code:
            continue
        width, limit = _measure(_join([t.text for t in runt], [t.sep for t in runt]))
        if limit == MAX_LINE_CHARS:
            continue
        while len(prev) > 1 and runt[-1].end - prev[-1].start <= MAX_CUE_SECONDS:
            if width(_join([t.text for t in runt], [t.sep for t in runt])) >= limit / 3:
                break
            runt.insert(0, prev.pop())


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
            fits = wrap_lines(
                [t.text for t in current] + [tok.text], [t.sep for t in current] + [tok.sep],
            ) is not None
            short_enough = tok.end - current[0].start <= MAX_CUE_SECONDS
            text = _join([t.text for t in current], [t.sep for t in current])
            width, limit = _measure(text)
            sentence_break = (
                _SENTENCE_END.search(current[-1].text) is not None
                and width(text) >= _SENTENCE_BREAK_MIN_CHARS * limit / MAX_LINE_CHARS
            )
            if not (same_speaker and fits and short_enough) or sentence_break:
                carry: list[Token] = []
                if same_speaker and not sentence_break and limit != MAX_LINE_CHARS:
                    carry = _clause_carry(current, tok)
                groups.append(current[:len(current) - len(carry)])
                current = carry
        current.append(tok)
    if current:
        groups.append(current)
    _fill_runts(groups)

    colours = assign_colours([g[0].speaker_code for g in groups], primary_speaker)
    cues: list[Cue] = []
    for g in groups:
        texts, seps = [t.text for t in g], [t.sep for t in g]
        lines = wrap_lines(texts, seps) or (_join(texts, seps),)
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
# Language tag
# ---------------------------------------------------------------------------

#: Whisper's language codes (ISO 639-1, plus its own ``haw``/``yue``/``jw``)
#: to ISO 639-2/T, which is what an MP4 track's language field carries.
_ISO639_2 = {
    "af": "afr", "am": "amh", "ar": "ara", "as": "asm", "az": "aze", "ba": "bak",
    "be": "bel", "bg": "bul", "bn": "ben", "bo": "bod", "br": "bre", "bs": "bos",
    "ca": "cat", "cs": "ces", "cy": "cym", "da": "dan", "de": "deu", "el": "ell",
    "en": "eng", "es": "spa", "et": "est", "eu": "eus", "fa": "fas", "fi": "fin",
    "fo": "fao", "fr": "fra", "gl": "glg", "gu": "guj", "ha": "hau", "haw": "haw",
    "he": "heb", "hi": "hin", "hr": "hrv", "ht": "hat", "hu": "hun", "hy": "hye",
    "id": "ind", "is": "isl", "it": "ita", "ja": "jpn", "jw": "jav", "jv": "jav",
    "ka": "kat", "kk": "kaz", "km": "khm", "kn": "kan", "ko": "kor", "la": "lat",
    "lb": "ltz", "ln": "lin", "lo": "lao", "lt": "lit", "lv": "lav", "mg": "mlg",
    "mi": "mri", "mk": "mkd", "ml": "mal", "mn": "mon", "mr": "mar", "ms": "msa",
    "mt": "mlt", "my": "mya", "nb": "nob", "ne": "nep", "nl": "nld", "nn": "nno",
    "no": "nor", "oc": "oci", "pa": "pan", "pl": "pol", "ps": "pus", "pt": "por",
    "ro": "ron", "ru": "rus", "sa": "san", "sd": "snd", "si": "sin", "sk": "slk",
    "sl": "slv", "sn": "sna", "so": "som", "sq": "sqi", "sr": "srp", "su": "sun",
    "sv": "swe", "sw": "swa", "ta": "tam", "te": "tel", "tg": "tgk", "th": "tha",
    "tk": "tuk", "tl": "tgl", "tr": "tur", "tt": "tat", "uk": "ukr", "ur": "urd",
    "uz": "uzb", "vi": "vie", "yi": "yid", "yo": "yor", "yue": "yue", "zh": "zho",
}


def iso639_2(code: str | None) -> str:
    """ISO 639-2/T for a language code or locale tag; ``und`` if unknown.

    Accepts Whisper's codes (``en``, ``yue``) and the app's locale tags
    (``pt-BR``, ``zh-Hant-HK``), taking the primary subtag. A track tagged
    ``und`` is not matched by a player's "subtitles in my language" setting,
    so macOS shows an empty Forced variant instead (measured 29 Sep 2026).
    """
    if not code:
        return "und"
    primary = code.replace("_", "-").split("-")[0].lower()
    if len(primary) == 3 and primary not in _ISO639_2:
        return primary
    return _ISO639_2.get(primary, "und")


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


#: ASS colours are ``&HAABBGGRR``: alpha first (00 = opaque), then blue,
#: green, red. The BBC order, as overrides on the white default.
_ASS_COLOUR = {"yellow": "&H0000FFFF&", "cyan": "&H00FFFF00&", "green": "&H0000FF00&"}
#: The bundled face for burned-in subtitles (Inter, SIL OFL; docs §Font).
BURN_FONT_FAMILY = "Inter"


def _ass_time(seconds: float) -> str:
    cs = int(round(max(seconds, 0.0) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _ass_text(line: str) -> str:
    """Keep a transcript line from being read as ASS markup.

    ``{`` opens a style override and ``\\`` starts an escape (``\\N`` is a
    line break), so both are swapped for look-alikes, as in ``to_srt``.
    """
    return line.replace("\\", "\u29f5").replace("{", "(").replace("}", ")")


def to_ass(cues: list[Cue], width: int, height: int) -> str:
    """Burn-in subtitles for a ``width`` × ``height`` video, to the BBC spec.

    - Inter, text 1/15 of the frame height (BBC §9.2.1).
    - White on a 75% black box, not an outline (§9.2.4; 75% by decision, so a
      screen share's interface stays readable behind it). ``BorderStyle=3``
      draws the box; ``Outline`` is its padding.
    - Lines no wider than 68% of the frame (§3.1) — 16% side margins — and
      bottom-centre with a 5% margin, inside the central 90% (§10).
    - The cues' own line breaks are kept (``WrapStyle: 2``); speaker colour is
      an override on the white default, in the BBC order.

    Measured 29 Sep 2026 on 720p FOSSDA clips: about 0.6 s per clip to burn.
    """
    font_size = max(12, round(height / 15))
    pad = max(1, round(font_size * 0.15))
    side = round(width * 0.16)
    bottom = round(height * 0.05)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: Default,{BURN_FONT_FAMILY},{font_size},&H00FFFFFF,&H00FFFFFF,"
        f"&H40000000,&H40000000,0,0,0,0,100,100,0,0,3,{pad},0,2,{side},{side},{bottom},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for cue in cues:
        colour = _ASS_COLOUR.get(cue.colour)
        text = "\\N".join(_ass_text(line) for line in cue.lines)
        if colour:
            text = f"{{\\c{colour}}}{text}"
        lines.append(
            f"Dialogue: 0,{_ass_time(cue.start)},{_ass_time(cue.end)},Default,,0,0,0,,{text}"
        )
    return "\n".join(lines) + "\n"


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
