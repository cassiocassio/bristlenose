"""Property-based tests for how a long quote splits over stickies (`board_layout.split_quote`).

What a researcher would notice if it broke, in every language and script the rules cover: the
participant's words change, a part is a scrap, a quote runs to four stickies, or a part ends on
a word that leads into the next ("the…"). The weights behind each break are tuned on a corpus
(docs/research/board-quote-breaks.md), so nothing here pins a weight or a score; these hold
whatever the tuning. Placement rule: docs/design-test-philosophy.md.

CI runs these derandomised (tests/conftest.py); a kill that matters is pinned with @example.
"""

from __future__ import annotations

import re

from hypothesis import example, given, settings
from hypothesis import strategies as st

from bristlenose.board_layout import (
    BREAK_RULES,
    MAX_PARTS,
    MIN_PART,
    _word,
    break_rules,
    split_quote,
    text_width,
)

LANGUAGES = sorted(BREAK_RULES)
#: Words in each script the rules cover: Latin, Cyrillic, Turkish and Hangul with spaces, and
#: Japanese and Chinese without, as their speakers write them.
SCRIPTS = {
    "latin": st.text(alphabet="abcdefghijklmnoprstuvwyzéèàçñüößøåæ", min_size=1, max_size=9),
    "cyrillic": st.text(alphabet="абвгдежзийклмнопрстуфхцчшщыэюяёіїє", min_size=1, max_size=9),
    "turkish": st.text(alphabet="abcçdefgğhıijklmnoöprsştuüvyzİ", min_size=1, max_size=9),
    "hangul": st.text(alphabet="가나다라마바사아자차카타파하는데지만고서면", min_size=1, max_size=5),
}
SPACELESS = st.text(alphabet="これはとてもいいと思いましたでも設定画面我覺得這個很好用但是的了嗎", min_size=1,
                    max_size=6)
MARKS = st.sampled_from(["", "", "", ",", ".", "?", "!", "...", " ...", ";", "…", "。", "、"])


def _words_of(text: str) -> str:
    """The participant's words, without the marks a split may move or drop at a seam."""
    return re.sub(r"[\W_]", "", text)


@st.composite
def quotes(draw: st.DrawFn) -> tuple[str, str]:
    lang = draw(st.sampled_from(LANGUAGES))
    if break_rules(lang).phrases:
        chunks = draw(st.lists(st.tuples(SPACELESS, MARKS), min_size=20, max_size=120))
        return lang, "".join(w + m.strip() for w, m in chunks)
    script = draw(st.sampled_from(list(SCRIPTS.values())))
    chunks = draw(st.lists(st.tuples(script, MARKS), min_size=20, max_size=160))
    return lang, " ".join(w + m for w, m in chunks)


@settings(max_examples=300, deadline=None)
@given(quotes(), st.integers(min_value=40, max_value=400))
@example(("en", "we tried every one of the tools they had ... and none of them stayed open " * 6), 200)
@example(("ja", "このアプリはとても使いやすいと思いました。でも、設定画面がどこにあるのか分からなくて。" * 5), 100)
@example(("fr", "Vous avez trouvé ? Non, pas du tout. « Vraiment ? » Oui ! " * 8), 150)
def test_a_split_keeps_every_word_in_order_in_one_to_three_parts(quote: tuple[str, str],
                                                                 at: int) -> None:
    lang, text = quote
    parts = split_quote(text, at=at, language=lang)
    assert 1 <= len(parts) <= MAX_PARTS
    assert _words_of("".join(parts)) == _words_of(text)
    if len(parts) > 1:
        assert all(p.endswith("…") for p in parts[:-1])
        assert all(p.startswith("…") for p in parts[1:])


@settings(max_examples=300, deadline=None)
@given(quotes(), st.integers(min_value=40, max_value=400))
def test_no_part_is_a_scrap(quote: tuple[str, str], at: int) -> None:
    """No part under MIN_PART of an even share: a part is a stretch of the quote, never a word."""
    lang, text = quote
    parts = split_quote(text, at=at, language=lang)
    if len(parts) == 1:
        return
    even = text_width(text.strip()) / len(parts)
    for part in parts:
        # Allow for the marks a seam adds or drops: two ellipses, a stop, a space.
        assert text_width(part) >= MIN_PART * even - 6, (lang, part)


@st.composite
def lead_heavy(draw: st.DrawFn) -> tuple[str, str]:
    """A quote that alternates the language's lead words with plain words, so every other gap
    is one a part must not end on and the gap beside it is one it may."""
    lang = draw(st.sampled_from([lang for lang in LANGUAGES if not BREAK_RULES[lang].phrases]))
    rules = BREAK_RULES[lang]
    leads = sorted(rules.leads)
    plain = st.text(alphabet="bcdfghklmnpqrstvwxz", min_size=4, max_size=8).filter(
        lambda w: w not in rules.leads and w not in rules.no_start and w not in rules.opens)
    pairs = draw(st.lists(st.tuples(st.sampled_from(leads), plain), min_size=40, max_size=120))
    return lang, " ".join(f"{lead} {word}" for lead, word in pairs)


@settings(max_examples=200, deadline=None)
@given(lead_heavy(), st.integers(min_value=120, max_value=400))
def test_a_part_never_ends_on_a_word_that_leads_into_the_next(quote: tuple[str, str],
                                                              at: int) -> None:
    """Netflix's General Requirements and every language's own guide: never separate an article
    from its noun, a preposition from its object, a pronoun from its verb."""
    lang, text = quote
    for part in split_quote(text, at=at, language=lang)[:-1]:
        assert _word(part.removesuffix("…").split()[-1]) not in break_rules(lang).leads, (lang, part)
