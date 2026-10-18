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


#: A word no language's rules mention, to pad a phrase out to quote length.
_FILL = "bork"


def _split_at(left: list[str], right: list[str], lang: str, off: int = 0) -> list[str]:
    """``left + right`` padded with filler so the gap between them sits at the even split, then
    moved ``off`` words to the right; the quote as `split_quote` breaks it in ``lang``."""
    from bristlenose.board_layout import split_quote

    before, after = [_FILL] * (24 + off), [_FILL] * (24 - off)
    # Pad whichever side is short, last with one-letter words, until the gap is within two
    # characters of the middle: nearer than any other gap, so it is the one the rules judge.
    while True:
        head, tail = " ".join(before + left), " ".join(right + after)
        short = len(tail) - len(head)
        if abs(short) <= 2:
            break
        pad = _FILL if abs(short) > len(_FILL) + 1 else "q"
        (before.insert(0, pad) if short > 0 else after.append(pad))
    words = before + left + right + after
    if off:  # then move the gap off the middle by ``off`` words
        words = words[off:] + [_FILL] * off

    parts = split_quote(" ".join(words), at=len(" ".join(words)) // 2 + 20, language=lang)
    assert len(parts) == 2
    return parts


def test_french_and_german_marks_stay_with_their_sentence() -> None:
    """French sets ? ! ; : and » off with a space and German closes with “: a part ends after the
    whole mark, never before a "?" standing alone, never just after an opening « or „."""
    first, second = _split_at(["trouvé"], ["?", "Non"], "fr")
    assert first.endswith("?…") and not second.startswith("…?")
    first, second = _split_at(["Vraiment", "?"], ["»", "Oui"], "fr")
    assert first.endswith("»…")
    first, _ = _split_at(["dachte", "„Wo", "ist", "das?“"], ["Dann"], "de")
    assert first.endswith("das?“…")
    first, _ = _split_at(["«"], ["Vraiment", "dit-il"], "fr")
    assert not first.endswith("«…")


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
    # No part ends straight after の, which cuts a modifier from its noun (トップレベルの | 人工芝).
    turf = "「行くけど」って言ったんですけどそれから北海道でトップレベルの人工芝があります" * 3
    for at in range(40, 160, 10):
        assert not any(p.endswith("の…") for p in split_quote(turf, at=at, language="ja"))


def _centred(left: str, right: str, filler: str, n: int = 30) -> str:
    """``left + right`` with ``filler`` either side, so the seam between them is the middle."""
    from bristlenose.board_layout import text_width

    head, tail = filler * n + left, right + filler * n
    while text_width(head) < text_width(tail):
        head = filler[0] + head
    while text_width(tail) < text_width(head):
        tail = tail + filler[0]
    return head + tail


def test_kinsoku_holds_even_where_the_segmenter_would_break() -> None:
    """JLREQ: no part starts on a closing bracket, a small kana or a long-vowel mark, nor ends on
    an opening bracket. BudouX keeps to it already; a segmenter that did not must not get its way."""
    from unittest.mock import patch

    from bristlenose import board_layout

    class Careless:  # breaks before every character, kinsoku or not
        def parse(self, run: str) -> list[str]:
            return list(run)

    with patch.object(board_layout, "_phrase_parser", lambda model: Careless()):
        # The middle falls just before a closing bracket, a small kana, a long-vowel mark, and
        # just after an opening bracket: each a break the rule must refuse.
        for left, right in (("行くけど", "」って"), ("ちょ", "っと"), ("すご", "ーい"), ("言った「", "うん")):
            text = _centred(left, right, "あいうえお")
            first, second = board_layout.split_quote(text, at=board_layout.text_width(text) // 2 + 4,
                                                     language="ja")
            assert second[1] not in board_layout.KINSOKU_NO_START, (first[-6:], second[:6])
            assert first[-2] not in board_layout.KINSOKU_NO_END, (first[-6:], second[:6])


def test_a_latin_name_in_a_chinese_quote_is_never_split() -> None:
    """BudouX's Chinese models offer breaks inside Latin words (review, 18 Oct 2026:
    "TestFlig… / …ht")."""
    from bristlenose.board_layout import split_quote, text_width

    for name in ("TestFlight", "PowerPoint", "WhatsApp", "iPhone"):
        half = len(name) // 2  # the middle of the quote falls inside the name
        text = _centred("要先下载" + name[:half], name[half:] + "才能试用", "我觉得这个很好用")
        parts = split_quote(text, at=text_width(text) // 2 + 4, language="zh-Hans")
        assert len(parts) == 2 and sum(p.count(name) for p in parts) == 1, parts


def test_an_ellipsis_with_a_comma_at_a_cut_is_one_ellipsis() -> None:
    from bristlenose.board_layout import split_quote

    for tail in ("but...,", "said...;", "then…,"):
        text = "zork " * 30 + f"and I {tail} " + "zork " * 30
        assert all("..…" not in p and "……" not in p for p in split_quote(text, at=200))


def test_chinese_breaks_before_a_conjunction_and_never_after_de() -> None:
    from bristlenose.board_layout import _breaks, break_rules, split_quote

    said = ("我覺得這個應用程式很好用但是設定的地方我一直找不到所以一開始有點困惑"
            "後來同事教我怎麼用我才知道原來在右上角的選單裡面")
    first, _ = split_quote(said, at=60, language="zh")
    assert first.removesuffix("…")[-3:] in ("很好用", "找不到", "有點困惑")
    from bristlenose.board_layout import text_width

    for left, right in (("設定", "的地方"), ("設定的", "地方")):  # the middle either side of 的
        text = _centred(left, right, "我覺得這個應用程式很好用")
        first, second = split_quote(text, at=text_width(text) // 2 + 4, language="zh-Hant")
        assert not first.endswith("的…") and not second.startswith("…的"), (first[-6:], second[:6])
    # 覺得 is "feel", not the particle 得: BudouX gives a particle its own token, so a word ending
    # in the same character is a word end like any other (the one rule only the scorer can show).
    worth = dict(_breaks(said, None, break_rules("zh", said)))
    assert worth[said.index("覺得") + 2] >= 0


def test_each_language_follows_its_own_rules() -> None:
    """The authorities' rules (docs/research/board-quote-breaks.md), each with the word in
    question at the even split: Czech typography forbids a one-letter preposition at a line end
    (ČSN 01 6910); Polish *się* is bound to the word before; Korean *수* to its modifier; German
    *aber* opens a clause; Turkish breaks after a postposition and a converb, Korean after a
    connective ending."""
    def ends(left: list[str], right: list[str], lang: str, off: int = 0) -> str:
        return _split_at(left, right, lang, off)[0].removesuffix("…").split()[-1]

    assert ends(["bydlím", "v"], ["Praze"], "cs") != "v"
    assert ends(["bydlím", "v"], ["Praze"], "cs") != ends(["bydlím", "v"], ["Praze"], "en")
    assert ends(["bardzo", "martwi"], ["się", "tym"], "pl") != "martwi"
    assert ends(["할"], ["수", "있어요"], "ko") != "할"
    assert ends(["war", "gut"], ["aber", "dann"], "de", off=2) == "gut"
    assert ends(["bunun", "için"], ["gidiyoruz"], "tr", off=2) == "için"
    assert ends(["eve", "gelince"], ["yemek", "yedik"], "tr", off=2) == "gelince"
    assert ends(["찾았는데"], ["없었어요"], "ko", off=2) == "찾았는데"


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
    # A code the rules do not cover, or rules that cannot break the quote's script: the script
    # decides (Whisper's Cantonese; an English session quoting at length in Japanese).
    assert break_rules("yue", "我覺得這個") is BREAK_RULES["zh-hant"]
    assert break_rules("en", "設定がわからないのでとても困りました") is BREAK_RULES["ja"]
    assert break_rules("en", "We went to 東京 last year") is ENGLISH


def test_every_shipped_language_has_rules_and_every_rule_its_sources() -> None:
    """One entry per spoken language the app is localised for, each citing where it came from."""
    import json
    from importlib.resources import files
    from pathlib import Path

    from bristlenose.board_layout import BREAK_RULES

    raw = json.loads(files("bristlenose.data").joinpath("break_rules.json").read_text("utf-8"))
    locales = Path(__file__).resolve().parents[1] / "bristlenose" / "locales"
    for loc in sorted(d.name for d in locales.iterdir() if d.is_dir()):
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
        MIRO_PAPER,
        SET_STAGGER,
        SPLIT_AT,
        X_HEIGHT,
        Column,
        QuoteCard,
        layout_board,
    )

    long_ = _between(SPLIT_AT, 2 * SPLIT_AT)
    for shape in ("rectangle", "square"):
        board = layout_board([Column("Basket", "section", [QuoteCard(long_, "p1", "s1", 12.0)])],
                             "B", shape=shape)
        parts = [s for s in board.stickies if s.kind == "quote"]
        assert len(parts) == 2 and parts[0].set_id == parts[1].set_id is not None
        assert [s.attributed for s in parts] == [False, True]
        assert parts[1].x == parts[0].x + SET_STAGGER
        # What shows: the next part's paper covers one x-height of the paper above (Miro draws the
        # paper in the top 199/228 of a sticky's box), in either shape, so the notch is square.
        paper_bottom = parts[0].y + parts[0].height * MIRO_PAPER
        assert paper_bottom - parts[1].y == pytest.approx(X_HEIGHT) == SET_STAGGER
    unsplit = layout_board([Column("Basket", "section", [QuoteCard(long_, "p1", "s1", 12.0)])], "B", split=False)
    assert [s.set_id for s in unsplit.stickies if s.kind == "quote"] == [None]


def test_split_sets_in_one_column_never_overlap_and_their_drawn_height_is_their_extent() -> None:
    """Sets overlap inside themselves only: one quote's parts never reach the next quote, and the
    height the layout reserves for a set is the height it draws, in either shape."""
    from bristlenose.board_layout import (
        GAP_Y,
        SPLIT_AT,
        Column,
        QuoteCard,
        layout_board,
        quote_parts,
        set_extent,
    )

    texts = [_between(SPLIT_AT, 2 * SPLIT_AT), _between(2 * SPLIT_AT, 3 * SPLIT_AT), "Short and whole."]
    cards = [QuoteCard(t, "p1", "s1", 10.0 * k) for k, t in enumerate(texts)]
    for shape in ("rectangle", "square"):
        board = layout_board([Column("Basket", "section", cards)], "B", shape=shape)
        quotes = [s for s in board.stickies if s.kind == "quote"]
        sets: dict[object, list] = {}
        for s in quotes:
            sets.setdefault(s.set_id or id(s), []).append(s)
        boxes = [(min(s.y for s in ss), max(s.y + s.height for s in ss)) for ss in sets.values()]
        for (_, bottom), (top, _) in itertools.pairwise(boxes):
            assert top - bottom == pytest.approx(GAP_Y)
        for t, (top, bottom) in zip(texts, boxes, strict=True):
            _, h = set_extent(quote_parts(t, "— P1 · 00:00", shape=shape))
            assert bottom - top == pytest.approx(h)


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


def test_a_misspelt_rule_in_the_data_file_fails_loudly() -> None:
    """A misspelt key would load as an empty list and drop a language's rules without a word."""
    import json
    from importlib.resources import files
    from unittest.mock import patch

    from bristlenose import board_layout

    raw = json.loads(files("bristlenose.data").joinpath("break_rules.json").read_text(encoding="utf-8"))
    raw["de"]["lead"] = raw["de"].pop("leads")

    class Fake:
        def joinpath(self, _name: str) -> Fake:
            return self

        def read_text(self, encoding: str) -> str:
            return json.dumps(raw)

    with patch("importlib.resources.files", lambda _pkg: Fake()), pytest.raises(ValueError, match="de"):
        board_layout._load_break_rules()


def test_the_search_cap_never_changes_where_a_quote_breaks() -> None:
    """`_KEEP` keeps the best candidates around each even point for speed; it must give the cuts
    the full search gives. Seeded quotes with marks and lead words scattered, so the best pair is
    not simply the best break at each even point."""
    import random
    from unittest.mock import patch

    from bristlenose import board_layout

    rng = random.Random(18)
    vocab = {"en": "the a of and but so we it shelf jars kitchen walk bags shop list".split(),
             "de": "der die und aber dann ich es Regal Glas Küche Weg Taschen Laden".split()}
    marks = ["", "", "", "", ",", ".", "?", "...", ";"]
    differ = 0
    for _ in range(300):
        lang = rng.choice(sorted(vocab))
        text = " ".join(rng.choice(vocab[lang]) + rng.choice(marks) for _ in range(rng.randint(60, 260)))
        at = rng.randint(120, 500)
        capped = board_layout.split_quote(text, at=at, language=lang)
        with patch.object(board_layout, "_KEEP", 10**9):
            differ += board_layout.split_quote(text, at=at, language=lang) != capped
    assert differ == 0
