"""Target-agnostic board IR + trivial layout engine for the whiteboard bridges.

Near-pure stdlib (no pydantic models, no I/O) so it stays fast, testable, and
renderer-agnostic. The layout engine turns grouped quotes into a `Board` of
frames + stickies + text items in absolute board coordinates; renderers
(`miro_render_svg` for preview, `miro_client`/`server.miro_export` for the real
Miro push) translate the IR to a concrete surface. `board_manifest` reads the
same columns, ordering and colour tokens but not the geometry: FigJam stickies
grow with their text, so the in-editor plugin does its own vertical layout.

**The board's words arrive as `BoardStrings`; this module never resolves them.**
A Miro board is a deliverable a researcher hands to a client, which puts it on
the localised side of the surface table (`docs/design-i18n.md`) — so the locale
belongs to `server.miro_export`, which knows who asked, and geometry stays here.
The defaults are the English the board shipped with, so a caller that has no
locale is unchanged; `count_noun` is one of them, because English plurals have
exactly one source of truth in this repo (CLAUDE.md § CLI plurals) and a local
mirror would be a second.

Ported and generalised from experiments/board-layout-poc/.
"""

from __future__ import annotations

import difflib
import functools
import itertools
import math
import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from bristlenose.utils.text import count_noun
from bristlenose.utils.timecodes import format_timecode

# --- layout constants (board px) -------------------------------------------
#: A Miro board's stickies are the wide rectangle by default: a quote wraps in longer, fewer lines
#: than in a square, and the board stays dense (owner, 17 Oct 2026: "nearly always better"). The
#: export dialogs offer Square / Rectangle, "users will want to pick"; FigJam defaults to square.
STICKY_SHAPE = "rectangle"
STICKY_SHAPES = ("rectangle", "square")
#: Miro sizes a sticky from its width alone and keeps the shape's proportion, so the height the
#: layout reserves must be the one Miro draws. Measured 17 Oct 2026: a rectangle 300 wide is
#: 195.43 tall (450 is 293.14); a square 200 wide is 229.15. The old fixed heights (quote 200,
#: header 76) were less than a 240-wide square's 275, so a column's stickies overlapped.
RECT_ASPECT = 195.42857142857142 / 300
SQUARE_ASPECT = 229.14572864321605 / 200
ASPECT = {"rectangle": RECT_ASPECT, "square": SQUARE_ASPECT}
#: 300, not the 240 the squares had: a rectangle that narrow is 156 tall, and Miro shrinks a long
#: quote's type to fit (project-ikea's quotes: median 122 characters, p90 256). Owner, 17 Oct 2026.
STICKY_W = 300.0
QUOTE_H = STICKY_W * RECT_ASPECT
HEADER_H = QUOTE_H
GAP_X = 36.0
GAP_Y = 24.0
FRAME_PAD = 28.0
FRAME_GAP = 72.0
MARGIN = 64.0
TITLE_Y = 46.0
FRAMES_Y = 120.0

# --- colour tokens (Miro named-palette values; renderers map to their own) ---
# Tokens ARE Miro's named sticky colours, so the Miro renderer is identity and
# only the SVG preview needs a token->hex map.
HEADER_TOKEN = "light_pink"
DEFAULT_QUOTE_TOKEN = "light_yellow"

# Bristlenose sentiment -> colour token. Unknown/None -> default.
SENTIMENT_TOKEN = {
    "positive": "light_green",
    "delight": "green",
    "negative": "light_pink",
    "frustration": "red",
    "confusion": "light_blue",
    "neutral": "gray",
    "mixed": "light_yellow",
}


def english_quote_count(n: int) -> str:
    return count_noun(n, "quote")


@dataclass(frozen=True)
class BoardStrings:
    """Every word the board says that is not the researcher's own data.

    `quote_count` is a callable rather than a template because the plural form
    is a function of the number in fourteen of the twenty-one languages, and
    `2 cytaty` / `5 cytatów` is not something a format string can reach.
    """

    sections: str = "Sections"
    themes: str = "Themes"
    quote_count: Callable[[int], str] = english_quote_count


@dataclass
class QuoteCard:
    """The minimal quote shape the layout engine needs (decoupled from DB)."""

    text: str
    participant_id: str
    session_id: str
    start_timecode: float
    sentiment: str | None = None
    link_url: str | None = None  # optional clip link
    #: The speaker's pauses inside the quote (`quote_pauses`), which tell a split where to fall.
    pauses: Mapping[int, float] | None = None
    #: The session's spoken language, whose `break_rules` the split follows.
    language: str | None = None


@dataclass
class Column:
    """One section or theme + its quotes."""

    label: str
    kind: str  # "section" | "theme"
    quotes: list[QuoteCard]


@dataclass
class Frame:
    title: str
    x: float
    y: float
    width: float
    height: float
    kind: str  # "section" | "theme"


@dataclass
class Sticky:
    x: float
    y: float
    width: float
    height: float
    colour: str  # colour token
    text: str
    kind: str = "quote"  # "header" | "quote"
    participant_id: str = ""
    timecode: float = 0.0
    link_url: str | None = None
    #: Only the last part of a split quote carries the attribution line and the clip link.
    attributed: bool = True
    #: The parts of one split quote share a set number, so the board groups them; None for a
    #: quote on one sticky.
    set_id: int | None = None


@dataclass
class TextItem:
    text: str
    x: float
    y: float
    size: float
    weight: str = "700"


@dataclass
class Board:
    title: str
    sticky_shape: str = STICKY_SHAPE
    frames: list[Frame] = field(default_factory=list)
    stickies: list[Sticky] = field(default_factory=list)
    texts: list[TextItem] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0


def _session_num(session_id: str) -> int:
    m = re.search(r"(\d+)", session_id or "")
    return int(m.group(1)) if m else 0


def quote_sort_key(q: QuoteCard) -> tuple[int, float]:
    return (_session_num(q.session_id), q.start_timecode)


def fmt_timecode(seconds: float) -> str:
    """The house timecode (``05:30`` / ``1:30:00``) on a sticky's attribution.

    Was ``f"{total // 60}:{total % 60:02d}"`` — minutes never rolled into hours,
    so an hour read ``60:00`` and, from 100 minutes, the output could not be
    parsed back at all. The corpus's longest session is 99.7 minutes.
    """
    return format_timecode(seconds)


#: A quote longer than this becomes two stickies, and longer than twice it, three; never more than
#: three, a longer last part simply growing. Chosen by the owner on 17 Oct 2026 from sample boards of
#: real sessions at 650, 325 and about two sentences: across the trial runs' 720 quotes, 325 leaves
#: 44% whole, 37% as pairs and 19% as trios, each part about 55 words — roughly what a researcher
#: trims a quote to by hand.
SPLIT_AT = 325
MAX_PARTS = 3
#: What a break is worth, as subtitlers rank them (BBC subtitle guidelines, "break at natural
#: points"; Gerber-Morón & Szarkowska 2018 measured the reading cost of the alternative): the end of
#: a sentence, then an elision the extraction made (" ... ", words already cut there), a clause or
#: a speaker trailing off ("but... it's"), a phrase. Japanese and Chinese punctuation counts the
#: same as its Latin kin.
#: Closing marks a sentence end may sit inside: English, German („…“), French and Spanish («…»).
_CLOSERS = "\"”“’)»›」』）"
_TRAILING_OFF = re.compile(rf"\w(\.\.\.|…)[{_CLOSERS}]*$")
_SENTENCE_END = re.compile(rf"[.?!…。！？][{_CLOSERS}]*$")
_CLAUSE_END = re.compile(r"[;:；：—–]$")
_PHRASE_END = re.compile(r"[,，、]$")
_ELISION = re.compile(r"^(\.\.\.|…)$")
#: After a mark a spaceless script runs straight on, so its breaks are found inside the text.
_CJK_BREAK = re.compile(r"[。！？][」』）)]*|[、，；：]")
_SPACELESS = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_KANA = re.compile(r"[\u3040-\u30ff]")
#: Kinsoku (JIS X 4051; W3C JLREQ §3.1.7, clreq): what may not begin a line — closing brackets,
#: marks, the long-vowel mark, small kana, iteration marks — and what may not end one.
KINSOKU_NO_START = ("、。，．・：；？！ー〜～…‥⋯」』）〕］｝〉》】〙〗⦆»〟’”)]}‐–—゠!?‼⁇⁈⁉:;.,·‧"
                    "ぁぃぅぇぉっゃゅょゎゕゖァィゥェォッャュョヮヵヶ々〻ゝゞヽヾ")
KINSOKU_NO_END = "「『（〔［｛〈《【〘〖⦅«〝‘“([{"
_SCORE = {"sentence": 10.0, "elision": 9.0, "clause": 6.0, "phrase": 4.0}
#: Seconds of silence between two words are a break the speaker made: worth up to a sentence end,
#: where the text has no mark to say so. Only there: a pause after a full stop is usual, and
#: counting it pulled breaks off the even split for nothing (median worst part 8% → 17% off even
#: across the trial runs). Whisper's word timings put most words edge to edge, so only a real
#: pause scores.
PAUSE_WEIGHT = 8.0  # 6 until tuned, 18 Oct 2026 (docs/research/board-quote-breaks.md)
PAUSE_CAP = 1.5
@dataclass(frozen=True)
class BreakRules:
    """Where no mark or pause says, a language's rules for a bare word, as its subtitlers break a
    line: a part may begin on a word that opens a clause (``opens``, worth 1–3, and ``opens2`` for
    two-word openers), and never end on one that leads into the next (``leads``: an article, a
    preposition, a pronoun before its verb)."""

    leads: frozenset[str] = frozenset()
    opens: Mapping[str, float] = field(default_factory=dict)
    opens2: Mapping[tuple[str, str], float] = field(default_factory=dict)
    #: Words a part may not begin on, bound to the word before: Polish *się*, Czech *se*, Russian
    #: *же*, Turkish *mi* and *değil*, German *sich*; and words after which a part may end well
    #: (Turkish postpositions, *için*, *gibi*).
    no_start: frozenset[str] = frozenset()
    closes: Mapping[str, float] = field(default_factory=dict)
    #: For a script written without spaces, the BudouX model whose phrase ends are its bare
    #: breaks (``"ja"``, ``"zh-hans"``, ``"zh-hant"``: `_phrase_parser`); and how a phrase
    #: ending reads, as the language's ``opens`` and ``leads`` do: ``ends_well`` (a clause-final
    #: particle, worth 1–3), ``ends_badly`` (a modifier bound to what follows), ``starts_well``
    #: (a conjunction opening the next phrase).
    phrases: str | None = None
    ends_well: Mapping[str, float] = field(default_factory=dict)
    ends_badly: frozenset[str] = frozenset()
    starts_well: Mapping[str, float] = field(default_factory=dict)
    starts_badly: frozenset[str] = frozenset()


_RULE_KEYS = frozenset({"leads", "opens", "opens2", "no_start", "closes", "phrases", "ends_well",
                        "ends_badly", "starts_well", "starts_badly", "sources"})


def _load_break_rules() -> dict[str, BreakRules]:
    """``data/break_rules.json``: each language's rules, compiled from its subtitling and
    typography authorities (Netflix's per-language Timed Text Style Guides and General
    Requirements, ÚJČ for Czech, Blanquerna for Catalan, SKTL for Finnish, ATAA for French, W3C
    JLREQ, clreq and KLREQ…), every entry carrying its sources;
    docs/research/board-quote-breaks.md has the research."""
    import json
    from importlib.resources import files

    raw = json.loads(files("bristlenose.data").joinpath("break_rules.json").read_text(encoding="utf-8"))

    def words(xs: Sequence[str]) -> frozenset[str]:
        return frozenset(_word(x) for x in xs)

    def weights(xs: Mapping[str, float], fold: bool = True) -> dict[str, float]:
        return {(_word(k) if fold else k): float(v) for k, v in xs.items()}

    out: dict[str, BreakRules] = {}
    for code, r in raw.items():
        if code.startswith("_"):
            continue
        # A misspelt key would load as an empty list and quietly drop a language's rules.
        unknown = set(r) - _RULE_KEYS
        if unknown or r.get("phrases") not in (None, "ja", "zh-hans", "zh-hant"):
            raise ValueError(f"break_rules.json: {code} has {sorted(unknown) or r.get('phrases')!r}")
        spaceless = bool(r.get("phrases"))
        out[code] = BreakRules(
            leads=words(r.get("leads", [])), opens=weights(r.get("opens", {})),
            opens2={(_word(a), _word(b)): float(w) for a, b, w in r.get("opens2", [])},
            no_start=words(r.get("no_start", [])), closes=weights(r.get("closes", {})),
            phrases=r.get("phrases"),
            ends_well=weights(r.get("ends_well", {}), fold=not spaceless),
            ends_badly=frozenset(r.get("ends_badly", [])),
            starts_well=weights(r.get("starts_well", {}), fold=False),
            starts_badly=frozenset(r.get("starts_badly", [])))
    return out


_LEAD_PENALTY = 4.0


#: A handful of characters that differ between the two Chinese scripts, to pick BudouX's model.
_SIMPLIFIED = set("这个们说会来时对为还过后么见经发问题实现开关东车长门")
_TRADITIONAL = set("這個們說會來時對為還過後麼見經發問題實現開關東車長門")


def _script_language(text: str) -> str | None:
    """The language a quote's script says, when most of its letters are Japanese, Chinese or
    Korean: kana is Japanese, Han without kana Chinese, Hangul Korean."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return None
    if sum(1 for c in letters if _SPACELESS.match(c)) * 2 > len(letters):
        return "ja" if _KANA.search(text) else "zh"
    if sum(1 for c in letters if "\uac00" <= c <= "\ud7af") * 2 > len(letters):
        return "ko"
    return None


def break_rules(language: str | None, text: str = "") -> BreakRules:
    """The rules for a session's spoken language (``"pt"``, ``"pt-BR"``, ``"zh-Hant"``): its own
    if Bristlenose has them. Where it has none — no language stored (a platform or docx
    transcript), a code the rules do not cover (Whisper's Cantonese ``yue``), or a language whose
    rules cannot break the quote's script (an English session quoting at length in Japanese) — the
    script of ``text`` decides, and failing that English, which is how every quote split before."""
    code = (language or "").replace("_", "-").split("-")[0].casefold()
    code = {"no": "nb", "nn": "nb", "yue": "zh"}.get(code, code)
    script = _script_language(text)
    known = BREAK_RULES.get(code) if code != "zh" else BREAK_RULES["zh-hans"]
    if script and (known is None or (script != "ko" and not known.phrases)):
        code = script
    if code == "zh":
        tag = (language or "").casefold()
        hant = ("hant" in tag or tag.endswith(("-tw", "-hk", "-mo")) or tag.startswith("yue")
                or sum(c in _TRADITIONAL for c in text) > sum(c in _SIMPLIFIED for c in text))
        return BREAK_RULES["zh-hant" if hant else "zh-hans"]
    return BREAK_RULES.get(code, ENGLISH)


def text_width(text: str) -> int:
    """How much room ``text`` takes, a Latin letter being one: a Japanese, Chinese or Korean
    character is drawn full-width, two (Unicode East Asian Width, UAX #11). A quote's length is
    measured this way, so a Japanese sticky holds as much type as an English one."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
#: The parts stay near even: a sentence end well off the even split still beats a bare word right
#: on it, as the owner's ~55-word parts expect, and no part is under 45% of even. 40 until tuned on
#: the held-out corpus (18 Oct 2026): 30 lands more breaks on a mark in every language and moves
#: the median part 1 point further from even (docs/research/board-quote-breaks.md).
BALANCE_WEIGHT = 30.0
#: Candidate breaks kept around each even point (`_cuts`).
_KEEP = 24
MIN_PART = 0.45


_WORDY = re.compile(r"\w")
_OPENER = re.compile(r"[«‹„“‘(\[¿¡]+")


def _word(token: str) -> str:
    """A word as the lists hold it: case folded, Russian *ё* as *е* (writers and Whisper
    alternate), curly apostrophe straight, and nothing but letters and apostrophes — which also
    drops the dot that Turkish *İ* keeps when folded, so *İçin* is *için*."""
    folded = token.casefold().replace("ё", "е").replace("’", "'")
    return re.sub(r"[^\w']", "", folded)


BREAK_RULES: dict[str, BreakRules] = _load_break_rules()
ENGLISH = BREAK_RULES["en"]


def _breaks(text: str, pauses: Mapping[int, float] | None,
            rules: BreakRules = ENGLISH) -> list[tuple[int, float]]:
    """Every place ``text`` could break, as (offset of the end of the part before, worth)."""
    out: list[tuple[int, float]] = []
    # A no-break space is there to forbid a break (French before ; : ! ?, a number and its unit).
    gaps = list(re.finditer(r"[^\S\u00a0\u202f\u2007]+", text))

    def token(k: int) -> str:  # the word after gap k (k = -1: the first)
        a = gaps[k].end() if k >= 0 else 0
        return text[a:gaps[k + 1].start() if k + 1 < len(gaps) else len(text)]

    for k, gap in enumerate(gaps):
        before, after = token(k - 1), token(k)
        if not _WORDY.search(after) and not _ELISION.match(after):
            continue  # French sets "?", ";" and "»" off with a space: never break before them
        if _OPENER.fullmatch(before):
            continue  # nor after an opening mark standing alone ("« Vraiment")
        if not _WORDY.search(before) and not _ELISION.match(before) and k:
            before = token(k - 2) + before  # "Vraiment ? »": the mark belongs to its word
        if _ELISION.match(before):  # it becomes the part's "…" (`split_quote`)
            worth = _SCORE["elision"]
        elif _TRAILING_OFF.search(before):
            worth = _SCORE["clause"] - (_LEAD_PENALTY if _word(before) in rules.leads else 0.0)
        elif _SENTENCE_END.search(before):
            worth = _SCORE["sentence"]
        elif _CLAUSE_END.search(before) or after[:1] in "—–":
            worth = _SCORE["clause"]
        elif _PHRASE_END.search(before):
            worth = _SCORE["phrase"]
        else:
            nxt = _word(after)
            worth = rules.opens.get(nxt, 0.0)
            if rules.opens2 and k + 1 < len(gaps):
                worth = max(worth, rules.opens2.get((nxt, _word(token(k + 1))), 0.0))
            last = _word(before)
            worth = max(worth, rules.closes.get(last, 0.0),
                        max((w for end, w in rules.ends_well.items() if last.endswith(end)),
                            default=0.0))
            if last in rules.leads or nxt in rules.no_start:
                # Inside a phrase a pause is the speaker looking for the word ("on a… Monday"),
                # not a break they made, so it earns nothing.
                worth -= _LEAD_PENALTY
            elif pauses:
                worth += min(pauses.get(gap.start(), 0.0), PAUSE_CAP) * PAUSE_WEIGHT
        out.append((gap.start(), worth))
    marked = set()
    for m in _CJK_BREAK.finditer(text):
        if m.end() < len(text) and not text[m.end()].isspace():
            mark = m.group()[0]
            out.append((m.end(), _SCORE["sentence"] if mark in "。！？" else _SCORE["phrase"]))
            marked.add(m.end())
    if rules.phrases and _SPACELESS.search(text):
        for run in re.finditer(r"\S+", text):
            phrases = _phrase_parser(rules.phrases).parse(run.group())
            o = run.start()
            for before, after in itertools.pairwise(phrases):
                o += len(before)
                if o in marked or text[o] in KINSOKU_NO_START or text[o - 1] in KINSOKU_NO_END:
                    continue
                # BudouX's Chinese models will split a Latin name inside a Chinese sentence
                # ("TestFlig… / …ht"): never between two letters of another script.
                if (text[o - 1].isalnum() and text[o].isalnum()
                        and not _SPACELESS.match(text[o - 1]) and not _SPACELESS.match(text[o])):
                    continue
                out.append((o, _phrase_worth(before, after, rules)))
    return out


@functools.cache
def _phrase_parser(model: str) -> Any:
    """BudouX's parser for ``model`` (``"ja"``, ``"zh-hans"``, ``"zh-hant"``): Google's phrase
    segmenter, the one Chrome breaks lines with for CSS ``word-break: auto-phrase``."""
    import budoux

    return {"ja": budoux.load_default_japanese_parser,
            "zh-hans": budoux.load_default_simplified_chinese_parser,
            "zh-hant": budoux.load_default_traditional_chinese_parser}[model]()


def _phrase_worth(before: str, after: str, rules: BreakRules) -> float:
    """A break between two of BudouX's phrases: a Japanese bunsetsu, a Chinese word. The phrase
    before ending in a clause-final particle reads well (*ので*, *吧*), the next opening with a
    conjunction too (*でも*, *但是*); ending in a modifier bound to the next word reads badly
    (*の*, *的*), as does the next phrase being a particle bound to this one (*了*, *嗎*).

    A Japanese bunsetsu carries its particle at its end, so endings are matched. Chinese words
    end in the same characters as the particles (覺得 "feel", 地方 "place"), and BudouX gives a
    particle its own token, so for Chinese a particle is a whole phrase — except 的, which almost
    always ends its phrase as the particle."""
    chinese = (rules.phrases or "").startswith("zh")
    worth = max((w for end, w in rules.ends_well.items() if before.endswith(end)), default=0.0)
    worth = max(worth, max((w for st, w in rules.starts_well.items() if after.startswith(st)),
                           default=0.0))
    if chinese:
        bad = (before in rules.ends_badly or before.endswith("的") or after in rules.starts_badly)
    else:
        bad = (any(before.endswith(end) for end in rules.ends_badly)
               or any(after.startswith(st) for st in rules.starts_badly))
    return worth - (_LEAD_PENALTY if bad else 0.0)


def _cuts(text: str, n: int, pauses: Mapping[int, float] | None,
          rules: BreakRules = ENGLISH) -> list[int]:
    """The ``n - 1`` offsets that make the best-reading parts: the breaks' worth, less how far
    the parts stray from an even split, measured in `text_width`."""
    room = list(itertools.accumulate((text_width(c) for c in text), initial=0))
    length = room[-1]
    even = length / n
    # The offsets where the room taken reaches each even share.
    targets = [next(i for i, r in enumerate(room) if r >= even * k) for k in range(1, n)]
    found = sorted(_breaks(text, pauses, rules))
    if not found:
        return targets  # a spaceless script with no mark near: an even cut, as before
    # Only a break that scores well near some even point can win, so keep the best `_KEEP` around
    # each: trying every pair of every candidate grew with the square of a long quote's length
    # (a 3,000-character Japanese quote took 0.3 s). 24 gives the full search's cuts on all 5,507
    # trial quotes in 19 languages, punctuated and stripped; 12 changed 19 of them.
    keep: set[int] = set()
    for t in targets:
        def near(i: int, t: int = t) -> float:
            return found[i][1] - BALANCE_WEIGHT * ((room[found[i][0]] - room[t]) / even) ** 2
        keep.update(sorted(range(len(found)), key=near, reverse=True)[:_KEEP])
    cands = [found[i] for i in sorted(keep)]

    def cost(cuts: Sequence[tuple[int, float]]) -> float:
        edges = [0, *(c for c, _ in cuts), len(text)]
        sizes = [room[b] - room[a] for a, b in zip(edges, edges[1:], strict=False)]
        if min(sizes) < MIN_PART * even:
            return math.inf
        stray = sum(((s - even) / even) ** 2 for s in sizes)
        return BALANCE_WEIGHT * stray - sum(w for _, w in cuts)

    best = min(itertools.combinations(cands, n - 1), key=cost, default=None)
    if best is None or cost(best) == math.inf:
        return targets
    return [c for c, _ in best]


def split_quote(text: str, at: int = SPLIT_AT, max_parts: int = MAX_PARTS,
                pauses: Mapping[int, float] | None = None,
                language: str | None = None) -> list[str]:
    """A quote as one, two or three parts that each read on their own, as researchers split a
    long quote by hand: at the best-reading break near each even split, a part that goes on ending
    in "…" and the next beginning with one. The words are never changed, only where they break.

    ``pauses`` (`quote_pauses`) is the speaker's silence, in seconds, at the whitespace that
    starts at each offset — the breaks the speaker made, which an unpunctuated transcript has
    nothing else to show (Whisper drops punctuation on long unbroken runs). ``language`` is the
    session's spoken language, whose `break_rules` apply; ``at`` is a `text_width`."""
    lead = len(text) - len(text.lstrip())
    if pauses and lead:
        pauses = {at - lead: gap for at, gap in pauses.items()}
    text = text.strip()
    n = max(1, min(max_parts, -(-text_width(text) // at)))
    if n == 1:
        return [text]
    cuts = _cuts(text, n, pauses, break_rules(language, text))
    parts = [text[a:b].strip() for a, b in zip([0, *cuts], [*cuts, len(text)], strict=True)]
    out: list[str] = []
    for i, part in enumerate(parts):
        if i < len(parts) - 1:
            # "successful." goes on as "successful…": the full stop gives way to the ellipsis, as
            # in a hand-split quote; a question or an exclamation keeps its mark. An elision at
            # the break is already an ellipsis, so it becomes this one.
            # Marks off first, then the elision they followed ("but...," / "said...;").
            part = re.sub(r"\s*(\.\.\.|…)$", "", part.rstrip(",;:—–、，；： ")).rstrip(",;:—–、，；： ")
            part = part.removesuffix(".").removesuffix("。") + ("" if part.endswith("…") else "…")
        if i > 0:
            part = "…" + re.sub(r"^(\.\.\.|…)\s*", "", part)
        out.append(part)
    return out


def quote_pauses(text: str, words: Sequence[Mapping[str, object]]) -> dict[int, float]:
    """The speaker's silence at each gap in ``text``, from the transcript's word timings
    (``words_json``: ``{"t", "s", "e"}``), keyed by the offset where the gap starts.

    The quote is the transcript's words with some cut (" ... ") and perhaps a researcher's edit,
    so the two are aligned word by word and a gap is timed only where both its words sit side by
    side in the transcript too. Spaceless scripts have no gaps to time."""
    tokens = list(re.finditer(r"\S+", text))
    said = [_word(str(w.get("t", ""))) for w in words]
    match = difflib.SequenceMatcher(None, [_word(t.group()) for t in tokens], said, autojunk=False)
    at: dict[int, int] = {}
    for block in match.get_matching_blocks():
        for k in range(block.size):
            at[block.a + k] = block.b + k
    out: dict[int, float] = {}
    for i in range(len(tokens) - 1):
        j = at.get(i)
        if j is None or at.get(i + 1) != j + 1:
            continue
        try:
            gap = float(words[j + 1]["s"]) - float(words[j]["e"])  # type: ignore[arg-type]
        except (KeyError, TypeError, ValueError):
            continue
        if gap > 0:
            out[tokens[i].end()] = gap
    return out


#: Miro refuses a sticky whose content, markup included, is longer than this, and with it the
#: whole batch the sticky was in.
MIRO_STICKY_MAX = 6000


def fit_miro_sticky(body: str, rest: str) -> str:
    """``escape(body) + rest`` as a sticky's content, the body cut only if Miro would refuse it.

    Quotes are never shortened for readability (owner, 17 Oct 2026): a rectangle sticky shrinks
    its type to fit, and a participant's words cut from a deliverable are words lost with nothing
    to say so. Across the trial runs 62% of quotes ran past the old 300-character cut; the longest
    was 2,157 characters, a third of Miro's limit."""
    from html import escape

    out = escape(body) + rest
    while len(out) > MIRO_STICKY_MAX and body:
        body = body[: max(0, len(body) - (len(out) - MIRO_STICKY_MAX) - 1)].rstrip()
        out = escape(body + "…") + rest
    return out


def attribution(participant_id: str, timecode: float) -> str:
    """The italic line under a quote: ``— P2 · 00:22``. One copy for every board."""
    return f"— {participant_id.upper()} · {fmt_timecode(timecode)}"


def quoted(text: str) -> str:
    """A quote as a sticky shows it, in curly marks."""
    return f"“{text.strip()}”"


#: Sticky width from its text: Miro fits the type to the box and a rectangle keeps its
#: proportions, so for every sticky to show the same size of type its area must follow its text —
#: its width the square root of its length. The factor is the owner's own hand: resizing split
#: quotes in Miro until the type matched, 207 characters came to 255 wide, 293 to 281, 329 to 330,
#: 227 to 255 (17 Oct 2026). Lines then run about 8–10 words, which is a comfortable measure.
SIZE_K = 17.0
#: The parts of one quote overlap by about one x-height of the board's type, the head of each
#: covering the foot of the one before, so they read as connected; and each steps right by the same
#: amount, so the notch at every left edge is a small square the eye completes into a line (owner,
#: 17 Oct 2026). One size of type makes it one number: measured off the owner's screenshot as about
#: 4.5 board units. Later parts are created later, so they are drawn on top.
X_HEIGHT = 5.0
SET_STAGGER = X_HEIGHT
#: Miro's sticky box is not all paper. Its default stickies are 199 × 228 (square) and 350 × 228
#: (rectangle), every size keeps those proportions (measured on a live board, 18 Oct 2026: a square
#: is 1.1457 times as tall as wide, a rectangle 0.6514), and Miro's Web SDK reference says the
#: height "includes the sticky note shadow". How much is shadow was measured off the owner's
#: screenshot of a check board (18 Oct 2026, 0.539 px per board unit from the columns' spacing):
#: the paper is 0.82–0.84 of the box's height in both shapes, so the bottom sixth is shadow. Taking
#: 199/228 (0.873) for the paper left the parts 2–4 px apart where they should overlap ("closer but
#: not overlapping"). 0.825 sits at the low end, so an error shows as a deeper overlap, not a gap.
#: FigJam's stickies are all paper, so the plugin overlaps the boxes by the x-height alone.
MIRO_PAPER = 0.825


def set_overlap(upper: QuotePart) -> float:
    """How far a set's next sticky climbs over ``upper``'s box: past its shadow, then one
    x-height of paper."""
    return upper.height * (1 - MIRO_PAPER) + X_HEIGHT


def set_tops(parts: Sequence[QuotePart]) -> list[float]:
    """Each part's top, from the top of its set: the one stacking every Miro board uses."""
    tops: list[float] = []
    y = 0.0
    for k, part in enumerate(parts):
        tops.append(y)
        y += part.height - (set_overlap(part) if k < len(parts) - 1 else 0.0)
    return tops


def sticky_width(chars: int, shape: str = STICKY_SHAPE) -> float:
    """The width that shows ``chars`` characters at the board's one size of type. A square sticky
    is taller for its width, so it needs less width for the same area — the same type size.
    ``chars`` is a `text_width`: a full-width character needs the room of two."""
    return SIZE_K * math.sqrt(max(chars, 1) * RECT_ASPECT / ASPECT.get(shape, RECT_ASPECT))


@dataclass
class QuotePart:
    """One sticky of a quote: its words (with the quote marks it carries), whether the attribution
    goes on it, and its size."""

    text: str
    attributed: bool
    width: float
    height: float


def quote_part_texts(text: str, split: bool = True,
                     pauses: Mapping[int, float] | None = None,
                     language: str | None = None) -> list[str]:
    """A quote's words as each sticky shows them, board-neutral: one string, or with ``split`` a
    long quote's two or three parts (`split_quote`), the opening mark on the first and the closing
    mark on the last. The attribution goes on the last part; the board adds it. FigJam and Miro both
    build on this, so a quote breaks in the same places on either board."""
    parts = split_quote(text, SPLIT_AT, MAX_PARTS, pauses, language) if split else [text.strip()]
    return [("“" if k == 0 else "") + part + ("”" if k == len(parts) - 1 else "")
            for k, part in enumerate(parts)]


def quote_parts(text: str, attribution_line: str, split: bool = True,
                shape: str = STICKY_SHAPE,
                pauses: Mapping[int, float] | None = None,
                language: str | None = None) -> list[QuotePart]:
    """A quote as the stickies a Miro board shows it on (`quote_part_texts`), each sized so the
    type comes out the same."""
    shown = quote_part_texts(text, split, pauses, language)
    out: list[QuotePart] = []
    for k, part in enumerate(shown):
        last = k == len(shown) - 1
        w = sticky_width(text_width(part) + (text_width(attribution_line) if last else 0), shape)
        out.append(QuotePart(part, last, w, w * ASPECT.get(shape, RECT_ASPECT)))
    return out


def set_extent(parts: Sequence[QuotePart]) -> tuple[float, float]:
    """(width, height) of a quote's stickies laid out as a set."""
    w = max((p.width + k * SET_STAGGER for k, p in enumerate(parts)), default=0.0)
    h = max((top + p.height for top, p in zip(set_tops(parts), parts, strict=True)), default=0.0)
    return w, h


def quote_colour(q: QuoteCard, colour_by: str) -> str:
    if colour_by != "sentiment":  # "none" (or anything else) -> single colour
        return DEFAULT_QUOTE_TOKEN
    if q.sentiment:
        return SENTIMENT_TOKEN.get(q.sentiment, DEFAULT_QUOTE_TOKEN)
    return DEFAULT_QUOTE_TOKEN


def _build_frame(
    columns: list[Column], kind: str, title: str, left_x: float, colour_by: str,
    strings: BoardStrings, split: bool = True, set_ids: list[int] | None = None,
    shape: str = STICKY_SHAPE,
) -> tuple[Frame, list[Sticky]]:
    """A frame of columns, each a header and its quotes stacked to their real heights. A column is
    as wide as its widest quote set: stickies are sized by their text, not to a grid."""
    set_ids = set_ids if set_ids is not None else [0]
    stickies: list[Sticky] = []
    cx = left_x + FRAME_PAD
    header_h = STICKY_W * ASPECT.get(shape, RECT_ASPECT)
    bottom = FRAMES_Y + FRAME_PAD + header_h
    for col in columns:
        sets = [(q, quote_parts(q.text, attribution(q.participant_id, q.start_timecode), split, shape,
                                q.pauses, q.language))
                for q in sorted(col.quotes, key=quote_sort_key)]
        col_w = max([STICKY_W] + [set_extent(parts)[0] for _, parts in sets])
        stickies.append(Sticky(
            kind="header", x=cx, y=FRAMES_Y + FRAME_PAD, width=STICKY_W, height=header_h,
            colour=HEADER_TOKEN, text=f"{col.label}\n{strings.quote_count(len(col.quotes))}",
        ))
        sy = FRAMES_Y + FRAME_PAD + header_h + GAP_Y
        for q, parts in sets:
            set_id = None
            if len(parts) > 1:
                set_ids[0] += 1
                set_id = set_ids[0]
            for k, (top, part) in enumerate(zip(set_tops(parts), parts, strict=True)):
                stickies.append(Sticky(
                    x=cx + k * SET_STAGGER, y=sy + top, width=part.width, height=part.height,
                    colour=quote_colour(q, colour_by), text=part.text,
                    participant_id=q.participant_id, timecode=q.start_timecode, link_url=q.link_url,
                    attributed=part.attributed, set_id=set_id,
                ))
            sy += set_extent(parts)[1] + GAP_Y
        bottom = max(bottom, sy - GAP_Y)
        cx += col_w + GAP_X
    frame_w = (cx - GAP_X if columns else cx) - left_x + FRAME_PAD
    frame = Frame(title=title, x=left_x, y=FRAMES_Y, width=frame_w,
                  height=bottom - FRAMES_Y + FRAME_PAD, kind=kind)
    return frame, stickies


def layout_board(columns: list[Column], title: str, colour_by: str = "sentiment",
                 strings: BoardStrings | None = None, split: bool = True,
                 shape: str = STICKY_SHAPE) -> Board:
    """Two named frames: sections (left) then themes (right). Pure geometry."""
    strings = strings or BoardStrings()
    sections = [c for c in columns if c.kind == "section"]
    themes = [c for c in columns if c.kind == "theme"]

    shape = shape if shape in STICKY_SHAPES else STICKY_SHAPE
    board = Board(title=title, sticky_shape=shape)
    board.texts.append(TextItem(title, MARGIN, TITLE_Y, 22.0, "700"))

    x = MARGIN
    set_ids = [0]  # one count across both frames, so every set's number is its own
    if sections:
        frame, stk = _build_frame(sections, "section", strings.sections, x, colour_by, strings,
                                  split, set_ids, shape)
        board.frames.append(frame)
        board.stickies.extend(stk)
        x = frame.x + frame.width + FRAME_GAP
    if themes:
        frame, stk = _build_frame(themes, "theme", strings.themes, x, colour_by, strings,
                                  split, set_ids, shape)
        board.frames.append(frame)
        board.stickies.extend(stk)

    right = max((f.x + f.width for f in board.frames), default=MARGIN)
    bottom = max((f.y + f.height for f in board.frames), default=FRAMES_Y)
    board.width = right + MARGIN
    board.height = bottom + MARGIN
    return board
