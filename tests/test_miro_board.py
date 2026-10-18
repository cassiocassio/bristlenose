"""Unit tests for the pure Miro board layout engine (no network, no DB)."""

from __future__ import annotations

import itertools

import pytest

from bristlenose.board_layout import (
    DEFAULT_QUOTE_TOKEN,
    HEADER_TOKEN,
    Column,
    QuoteCard,
    layout_board,
)


def _q(text: str, sid: str, tc: float, sentiment: str | None = None) -> QuoteCard:
    return QuoteCard(text=text, participant_id="p1", session_id=sid,
                     start_timecode=tc, sentiment=sentiment)


def _columns() -> list[Column]:
    return [
        Column("Dashboard", "section", [_q("a", "s1", 26, "frustration"),
                                        _q("b", "s1", 10, "confusion")]),
        Column("Search", "section", [_q("c", "s2", 5, "delight")]),
        Column("Onboarding", "theme", [_q("d", "s1", 66)]),
    ]


def test_two_named_frames_sections_then_themes() -> None:
    board = layout_board(_columns(), "T")
    assert [(f.title, f.kind) for f in board.frames] == [
        ("Sections", "section"),
        ("Themes", "theme"),
    ]
    # Sections frame is left of the Themes frame.
    assert board.frames[0].x < board.frames[1].x


def test_header_sticky_per_column() -> None:
    board = layout_board(_columns(), "T")
    headers = [s for s in board.stickies if s.kind == "header"]
    assert len(headers) == 3  # one per column
    assert all(s.colour == HEADER_TOKEN for s in headers)
    assert any("Dashboard" in s.text for s in headers)


def test_header_count_is_singular_or_plural_never_parenthesised() -> None:
    # A board is a client-facing deliverable, so "1 quote(s)" is not acceptable.
    # Dashboard has 2 quotes, Search has 1 — pin both branches.
    board = layout_board(_columns(), "T")
    text = {s.text.split("\n")[0]: s.text for s in board.stickies if s.kind == "header"}
    assert text["Dashboard"].endswith("2 quotes")
    assert text["Search"].endswith("1 quote")
    assert not any("(s)" in s for s in text.values())


def test_quotes_sorted_session_then_time() -> None:
    board = layout_board(_columns(), "T")
    # Dashboard column: s1@10 before s1@26 -> "b" above "a" (smaller y first).
    quotes = [s for s in board.stickies if s.kind == "quote"]
    dash = sorted([s for s in quotes if "a" in s.text or "b" in s.text],
                  key=lambda s: s.y)
    assert dash[0].text == "“b”"
    assert dash[1].text == "“a”"


def test_colour_by_sentiment_maps_tokens() -> None:
    board = layout_board(_columns(), "T", colour_by="sentiment")
    by_text = {s.text: s.colour for s in board.stickies if s.kind == "quote"}
    assert by_text["“c”"] == "green"          # delight
    assert by_text["“a”"] == "red"            # frustration
    assert by_text["“d”"] == DEFAULT_QUOTE_TOKEN  # no sentiment -> default


def test_colour_by_none_is_default() -> None:
    board = layout_board(_columns(), "T", colour_by="none")
    quotes = [s for s in board.stickies if s.kind == "quote"]
    assert all(s.colour == DEFAULT_QUOTE_TOKEN for s in quotes)


def test_no_overlap_within_column() -> None:
    board = layout_board(_columns(), "T")
    # Stickies in the same column (same x) must not vertically overlap.
    by_x: dict[float, list] = {}
    for s in board.stickies:
        by_x.setdefault(s.x, []).append(s)
    for col in by_x.values():
        col.sort(key=lambda s: s.y)
        for upper, lower in itertools.pairwise(col):
            assert upper.y + upper.height <= lower.y + 0.01


def test_empty_columns_safe() -> None:
    board = layout_board([], "Empty")
    assert board.frames == []
    assert board.width > 0 and board.height > 0


def test_stickies_are_rectangles_and_the_layout_reserves_what_miro_draws() -> None:
    """Miro sizes a sticky from its width and keeps the shape's proportion (measured 17 Oct 2026:
    a rectangle 300 wide is 195.43 tall). A column spaced for any other height overlaps."""
    from bristlenose import board_layout as bl
    from bristlenose.server.miro_export import _sticky_item

    assert bl.STICKY_SHAPE == "rectangle"
    assert bl.QUOTE_H == bl.HEADER_H == bl.STICKY_W * 195.42857142857142 / 300
    s = bl.Sticky(kind="quote", x=0, y=0, width=bl.STICKY_W, height=bl.QUOTE_H, colour="light_yellow",
                  text="hello", participant_id="p1", timecode=1.0)
    assert _sticky_item(s)["data"]["shape"] == "rectangle"


# ── Long quotes as two or three stickies (owner, 17 Oct 2026) ─────────────────────────────────


def _between(lo: int, hi: int) -> str:
    """A quote of whole sentences longer than ``lo`` and no longer than ``hi``: two parts."""
    out = ""
    i = 0
    while len(out) <= lo:
        out = (out + f" Sentence {i} is about the jars and the shelf.").strip()
        i += 1
    assert len(out) <= hi
    return out


def test_a_quote_under_the_split_stays_whole_and_a_long_one_breaks_at_sentence_ends() -> None:
    from bristlenose.board_layout import SPLIT_AT, quote_part_texts, split_quote

    short = "It was fine. I found the jars."
    assert split_quote(short) == [short]
    long_ = _between(SPLIT_AT, 2 * SPLIT_AT)
    parts = split_quote(long_)
    assert len(parts) == 2 and all(len(p) <= SPLIT_AT + 60 for p in parts)
    assert parts[0].endswith("…") and parts[1].startswith("…")
    # Only the breaks change: take the dots off and the words are the quote's, in order.
    joined = " ".join(p.strip("…") for p in parts)
    assert joined.replace(". ", " ").replace(".", "") == long_.replace(". ", " ").replace(".", "")
    shown = quote_part_texts(long_)
    assert shown[0].startswith("“") and shown[-1].endswith("”") and not shown[1].startswith("“")


def test_never_more_than_three_parts_and_never_a_split_when_asked_not_to() -> None:
    from bristlenose.board_layout import quote_part_texts, split_quote

    huge = "A sentence. " * 400
    assert len(split_quote(huge)) == 3
    assert quote_part_texts(huge, split=False) == [f"“{huge.strip()}”"]


#: An unpunctuated run, as Whisper writes one on a long unbroken stretch: no full stop or comma
#: anywhere, so where a split falls is down to the words, the elisions and the pauses.
_RUN = ("we tried every one of the tools they had on offer that year and none of them stayed "
        "open long enough to finish a single thing we started on a monday morning before the "
        "coffee ran out and the meeting room filled up with the people from the other floor who "
        "wanted it for their planning session which always ran over by at least an hour or two "
        "because nobody ever wrote down what had been decided the week before so it all came round")


def _words(text: str, pause_after: int | None = None, pause: float = 1.2) -> list[dict]:
    """Word timings for ``text`` as the transcript keeps them, edge to edge as Whisper puts
    them, with one silence after word ``pause_after``."""
    out, t = [], 10.0
    for i, w in enumerate(text.split()):
        out.append({"t": w, "s": t, "e": t + 0.3})
        t += 0.3 + (pause if i == pause_after else 0.0)
    return out


def test_an_unpunctuated_quote_never_ends_a_part_on_a_word_that_leads_into_the_next() -> None:
    """The board in the owner's screenshot (18 Oct 2026) broke "back in the… / …day": with no
    mark to go on, a part may not end on an article, a preposition or a pronoun."""
    from bristlenose.board_layout import ENGLISH, _word, split_quote

    parts = split_quote(_RUN, at=200)
    assert len(parts) == 3
    for part in parts[:-1]:
        assert _word(part.rstrip("…").split()[-1]) not in ENGLISH.leads, part[-30:]
    assert " ".join(p.strip("…") for p in parts) == _RUN


def test_an_elision_is_the_break_and_becomes_its_ellipsis() -> None:
    """The extraction cut words out at " ... "; that seam is where a part breaks, and the parts
    carry one ellipsis each side, never "..." beside "…"."""
    from bristlenose.board_layout import split_quote

    words = _RUN.split()
    # A third of the way in, where an even split would not look.
    text = " ".join(words[:19]) + " ... " + " ".join(words[19:51])
    first, second = split_quote(text, at=200)
    assert first.endswith(" stayed open…")
    assert second.startswith("…long enough")
    assert "..." not in first + second


def test_a_pause_the_speaker_made_is_where_the_quote_breaks() -> None:
    from bristlenose.board_layout import quote_pauses, split_quote

    text = _RUN[:300].rsplit(" ", 1)[0]
    at = text.split().index("finish")  # a bare word, a quarter off the even split
    assert len(" ".join(text.split()[:at + 1])) < 0.8 * len(text) / 2
    timed = quote_pauses(text, _words(text, pause_after=at))
    first, _ = split_quote(text, at=200, pauses=timed)
    assert first.rstrip("…").split()[-1] == text.split()[at]
    untimed, _ = split_quote(text, at=200)
    assert untimed.rstrip("…").split()[-1] != text.split()[at]


def test_a_pause_after_an_article_is_a_hesitation_not_a_break() -> None:
    from bristlenose.board_layout import quote_pauses, split_quote

    text = _RUN[:300].rsplit(" ", 1)[0]
    at = text.split().index("a")  # "on a | monday": the speaker looking for the word
    first, _ = split_quote(text, at=200, pauses=quote_pauses(text, _words(text, pause_after=at)))
    assert first.rstrip("…").split()[-1] != "a"


def test_pauses_align_across_a_cut_and_never_time_a_gap_the_quote_made() -> None:
    """Where the quote cut words, marked " ... " or not (a researcher's edit), the two words
    either side were not side by side when spoken, so that gap has no pause of its own; the gaps
    around the cut are still timed from the transcript."""
    from bristlenose.board_layout import quote_pauses

    said = "one two three four five six seven eight"
    words = _words(said, pause_after=1, pause=0.8)
    for w in words[3:]:  # and a silence after "three", before the words the quote cut
        w["s"] += 2.0
        w["e"] += 2.0
    assert quote_pauses("one two three ... six seven eight", words) == {
        len("one two"): pytest.approx(0.8)}
    assert quote_pauses("one two three six seven eight", words) == {
        len("one two"): pytest.approx(0.8)}


def test_french_and_german_marks_are_sentence_ends_where_they_stand() -> None:
    """French sets ? ! ; : and » off with a space and German closes with “: the break goes after
    the whole mark, never before a "?" standing alone, never after an opening « or „."""
    from bristlenose.board_layout import _breaks

    def worths(text: str) -> dict[str, float]:
        return {text[:at].split()[-1]: w for at, w in _breaks(text, None)}

    assert worths("Avez-vous trouvé ? Non") == {"Avez-vous": 0.0, "?": 10.0}
    assert worths("« Vraiment ? » Oui") == {"»": 10.0}
    assert worths("Ich dachte: „Wo ist das?“ Dann")["das?“"] == 10.0
    assert "„Wo" in worths("Ich dachte: „Wo ist das?“ Dann")  # „Wo is a word with its mark


def test_japanese_breaks_at_a_sentence_end_never_inside_a_word() -> None:
    """No spaces to fall back on: before 18 Oct 2026 a Japanese quote was cut at a bare
    character offset ("どこにあ… / …るのか")."""
    from bristlenose.board_layout import split_quote

    sentence = "このアプリはとても使いやすいと思いました。でも、設定画面がどこにあるのか分からなくて、最初は少し戸惑いました。"
    text = sentence * 3 + "最初は少し戸惑いました。"
    parts = split_quote(text, language="ja")
    assert len(parts) == 2
    assert parts[0].endswith("ました…") and parts[1][1:3] in ("でも", "この", "最初")
    assert parts[0].removesuffix("…") + "。" + parts[1].removeprefix("…") == text


def test_a_full_width_character_takes_the_room_of_two() -> None:
    """A Japanese, Chinese or Korean character is drawn full-width (UAX #11): a quote splits by
    the room it takes, and its sticky is sized for the same size of type as an English one."""
    from bristlenose.board_layout import quote_parts, split_quote, text_width

    assert text_width("abc") == 3 and text_width("日本語") == 6 and text_width("한국") == 4
    ja = "設定画面がどこにあるのか分からなくて、最初は少し戸惑いました。" * 4  # 124 chars, 248 wide
    assert len(split_quote(ja, at=200)) == 2
    [en] = quote_parts("x" * 248, "— P1 · 0:10", split=False)
    [jp] = quote_parts(ja, "— P1 · 0:10", split=False)
    assert round(jp.width) == round(en.width)


def test_unspaced_japanese_breaks_at_a_clause_particle() -> None:
    """Whisper on a bad run writes Japanese with no marks at all; the phrase rule still finds
    the clause end: "…思ったのですが / ただ…", not inside a word."""
    from bristlenose.board_layout import split_quote

    said = ("高校生の時英語が得意だったのでそれを活かせる大学に入ろうと思ったのですが"
            "ただ英語を学ぶだけではなくてそれプラス何か新しいことを学べる大学がないかなと思い受験しました")
    first, second = split_quote(said, at=100, language="ja")
    assert first.endswith(("ので…", "ですが…", "なくて…")), first
    assert first.removesuffix("…") + second.removeprefix("…") == said
    # Kinsoku (JLREQ): no break before a small kana, a long-vowel mark or a closing bracket.
    from bristlenose.board_layout import KINSOKU_NO_START, _breaks, break_rules

    tricky = "「行くけど」って言ったんですけどそれから「来るから」って" * 2
    assert all(tricky[at] not in KINSOKU_NO_START for at, _ in _breaks(tricky, None, break_rules("ja")))
    # Never straight after の: that cuts a modifier from its noun (トップレベルの | 人工芝).
    turf = "北海道でトップレベルの人工芝があります"
    worth = dict(_breaks(turf, None, break_rules("ja")))
    assert worth[turf.index("人工芝")] < 0 < worth[turf.index("トップ")] + 5


def test_chinese_breaks_before_a_conjunction_and_never_after_de() -> None:
    from bristlenose.board_layout import _breaks, break_rules, split_quote

    said = ("我覺得這個應用程式很好用但是設定的地方我一直找不到所以一開始有點困惑"
            "後來同事教我怎麼用我才知道原來在右上角的選單裡面")
    first, _ = split_quote(said, at=60, language="zh")
    assert first.removesuffix("…")[-3:] in ("很好用", "找不到", "有點困惑")
    rules = break_rules("zh", said)
    assert all(not said[:at].endswith("的") for at, _ in _breaks(said, None, rules))


def test_each_language_follows_its_own_rules() -> None:
    """The authorities' rules (docs/research/board-quote-breaks.md): Czech typography forbids a
    one-letter preposition at a line end (ČSN 01 6910), Polish *się* is bound to the word before,
    German *aber* opens a clause."""
    from bristlenose.board_layout import _breaks, break_rules

    def worth(text: str, after: str, lang: str) -> float:
        return dict(_breaks(text, None, break_rules(lang)))[text.index(after) + len(after)]

    assert worth("bydlím v Praze", "v", "cs") < 0 < worth("bydlím v Praze", "bydlím", "cs") + 5
    assert worth("on bardzo martwi się tym", "martwi", "pl") < 0
    assert worth("das war gut aber dann", "gut", "de") > 0
    # The same words under English rules are neither: the language decides.
    assert worth("das war gut aber dann", "gut", "en") == 0
    # Turkish breaks after a postposition and a converb; Korean after a connective ending, and
    # never before a bound noun (*할 수 있다*).
    assert worth("bunun için gidiyoruz", "için", "tr") > 0
    assert worth("eve gelince yemek yedik", "gelince", "tr") > 0
    assert worth("찾았는데 없었어요", "찾았는데", "ko") > 0
    assert worth("할 수 있어요", "할", "ko") < 0


def test_turkish_capitals_and_russian_yo_match_their_lists() -> None:
    from bristlenose.board_layout import _word, break_rules

    assert _word("İçin") == "için" and _word("Ещё") == "еще"
    assert "için" in break_rules("tr").closes


def test_a_no_break_space_is_never_a_break() -> None:
    from bristlenose.board_layout import _breaks

    text = "Vous avez trouvé\u202f? Non, 40\u00a0kilomètres avec M.\u00a0Dupont"
    assert all(text[at] not in "\u202f\u00a0" for at, _ in _breaks(text, None))


def test_the_language_comes_from_the_script_when_the_session_does_not_say() -> None:
    from bristlenose.board_layout import BREAK_RULES, ENGLISH, break_rules

    assert break_rules(None, "設定がわからない") is BREAK_RULES["ja"]
    assert break_rules(None, "我覺得這個") is BREAK_RULES["zh-hant"]
    assert break_rules(None, "我觉得这个") is BREAK_RULES["zh-hans"]
    assert break_rules(None, "설정을 찾을 수") is BREAK_RULES["ko"]
    assert break_rules("pt-BR") is BREAK_RULES["pt"] and break_rules("no") is BREAK_RULES["nb"]
    assert break_rules(None, "plain words") is ENGLISH and break_rules("xx") is ENGLISH


def test_every_shipped_language_has_rules_and_every_rule_its_sources() -> None:
    """One entry per spoken language the app is localised for, each citing where it came from."""
    import json
    from importlib.resources import files
    from pathlib import Path

    from bristlenose.board_layout import BREAK_RULES, break_rules

    raw = json.loads(files("bristlenose.data").joinpath("break_rules.json").read_text("utf-8"))
    locales = Path(__file__).resolve().parents[1] / "bristlenose" / "locales"
    for loc in sorted(d.name for d in locales.iterdir() if d.is_dir()):
        assert break_rules(loc, "") is not None
        code = {"zh-Hant": "zh-hant", "zh-Hant-HK": "zh-hant"}.get(loc, loc.split("-")[0])
        assert code in BREAK_RULES, loc
        assert raw[code]["sources"], loc


def test_every_sticky_shows_the_same_size_of_type() -> None:
    """Miro fits type to the box and a rectangle keeps its shape, so the area follows the text:
    the width goes with the square root of the length (the owner's hand: 207 chars → 255 wide)."""
    from bristlenose.board_layout import SIZE_K, quote_parts, sticky_width

    assert round(sticky_width(207)) == round(SIZE_K * 207 ** 0.5) and 240 < sticky_width(207) < 260
    [p] = quote_parts("x" * 100, "— P1 · 0:10", split=False)
    [q] = quote_parts("x" * 400, "— P1 · 0:10", split=False)
    assert q.width / p.width == pytest.approx(((400 + 13) / (100 + 13)) ** 0.5, rel=0.01)


def test_the_quotes_board_stacks_a_set_stepping_right_with_only_the_last_attributed() -> None:
    from bristlenose.board_layout import (
        SET_GAP,
        SET_STAGGER,
        SPLIT_AT,
        Column,
        QuoteCard,
        layout_board,
    )

    long_ = _between(SPLIT_AT, 2 * SPLIT_AT)
    board = layout_board([Column("Basket", "section", [QuoteCard(long_, "p1", "s1", 12.0)])], "B")
    parts = [s for s in board.stickies if s.kind == "quote"]
    assert len(parts) == 2 and parts[0].set_id == parts[1].set_id is not None
    assert [s.attributed for s in parts] == [False, True]
    assert parts[1].x == parts[0].x + SET_STAGGER
    assert parts[1].y == pytest.approx(parts[0].y + parts[0].height + SET_GAP)
    unsplit = layout_board([Column("Basket", "section", [QuoteCard(long_, "p1", "s1", 12.0)])], "B", split=False)
    assert [s.set_id for s in unsplit.stickies if s.kind == "quote"] == [None]


def test_a_square_sticky_keeps_the_same_size_of_type_and_reaches_miro() -> None:
    """A square is taller for its width, so it needs less width for the same area: same type."""
    from bristlenose.board_layout import Column, QuoteCard, layout_board, quote_parts
    from bristlenose.server.miro_export import _sticky_item

    [r] = quote_parts("x" * 200, "— P1 · 0:10", split=False, shape="rectangle")
    [s] = quote_parts("x" * 200, "— P1 · 0:10", split=False, shape="square")
    assert s.width < r.width and s.width * s.height == pytest.approx(r.width * r.height)
    board = layout_board([Column("A", "section", [QuoteCard("hello", "p1", "s1", 1.0)])], "B", shape="square")
    assert board.sticky_shape == "square"
    quote = next(st for st in board.stickies if st.kind == "quote")
    assert _sticky_item(quote, shape=board.sticky_shape)["data"]["shape"] == "square"
    assert layout_board([], "B", shape="hexagon").sticky_shape == "rectangle"  # an unknown shape falls back
