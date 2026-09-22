"""A Miro board is a deliverable, so it speaks the researcher's language.

Until 22 Sep 2026 it did not, and nothing could see it. Every board ever
generated said `Sections`, `Themes` and `3 quotes` in English, in all 21
locales, because `miro_board.py` held those as literals — and a literal is
invisible to every gate we own. `check-locales.py` compares each locale against
English and is silent about a surface English never enrolled; the register calls
that the second blind spot, and this is it in the wild. The tell was small and
was in the file the whole time: the module's docstring named `count_noun` as its
one Bristlenose import, which is a *pluraliser*, which means the module was
composing user-facing sentences.

What this pins, in both directions:

* the board's chrome resolves in every full locale and in the `zh-Hant-HK`
  override fork, with no raw key and no unsubstituted placeholder;
* it resolves to the *values on disk* — read here straight from the JSON, not
  through the same `t_in` the board used, so a resolver that returns its input
  cannot agree with itself;
* the per-column count goes through CLDR selection, which is the half a format
  string cannot reach (`2 cytaty` vs `5 cytatów`);
* no English literal creeps back into the two modules that build the board.

The last one is the only guard that survives the next person, so it names the
words rather than counting them.
"""

from __future__ import annotations

import ast
import json
import re
import unicodedata
from pathlib import Path

import pytest

from bristlenose.i18n import SUPPORTED_LOCALES
from bristlenose.miro_render_svg import render_html
from bristlenose.server.export_core import ExportableQuote
from bristlenose.server.miro_export import build_board, build_preview_html

_ROOT = Path(__file__).resolve().parents[1]
_LOCALES = _ROOT / "bristlenose" / "locales"


def _quotes(n: int, section: str = "Checkout") -> list[ExportableQuote]:
    return [
        ExportableQuote(
            text=f"quote {i}",
            participant_code="p1",
            participant_name="",
            section=section,
            theme="",
            sentiment="delight",
            tags="",
            starred=False,
            timecode=f"0:{10 + i:02d}",
            session="s1",
            source_file="x.mp4",
        )
        for i in range(n)
    ]


@pytest.fixture
def board(monkeypatch):
    """A real board, built by the real code path, with the DB stubbed out.

    Driving `build_board` rather than `layout_board` is deliberate: the title
    and the fallback theme label are resolved in `miro_export`, one layer above
    the engine, and a test that stopped at the engine would pass while the
    title stayed English. Same shape as the harness trap in the root CLAUDE.md.
    """

    def _build(locale: str, n: int = 3, quotes=None, **kw):
        monkeypatch.setattr(
            "bristlenose.server.miro_export.extract_quotes_for_export",
            lambda *a, **k: (quotes if quotes is not None else _quotes(n)),
        )
        return build_board(None, 1, "Renfe", None, locale=locale, **kw)

    return _build


def _common(locale: str) -> dict:
    return json.loads((_LOCALES / locale / "common.json").read_text(encoding="utf-8"))


def _all_text(b) -> str:
    return "\n".join(
        [t.text for t in b.texts]
        + [f.title for f in b.frames]
        + [s.text for s in b.stickies]
    )


_FULL_LOCALES = [loc for loc in SUPPORTED_LOCALES if loc != "zh-Hant-HK"]


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_no_raw_keys_or_placeholders_survive(board, locale):
    """A miss returns the dotted key; a bad interpolation leaves the braces."""
    text = _all_text(board(locale))
    leaked = re.findall(r"\b(?:common|desktop|settings|enums)\.[a-zA-Z.]+", text)
    assert not leaked, f"{locale}: raw key(s) on the board: {leaked}"
    assert "{{" not in text and "}}" not in text, (
        f"{locale}: an unsubstituted placeholder reached the board — the locale "
        f"files are i18next ({{{{var}}}}), and Python's format_map reads that as "
        f"an escaped literal brace. See _interpolate in bristlenose/i18n.py.\n{text}"
    )


@pytest.mark.parametrize("locale", _FULL_LOCALES)
def test_frame_titles_are_the_values_on_disk(board, locale):
    """Read the expectation from the JSON, not from the resolver under test."""
    b = board(locale)
    expected = _common(locale)["quotes"]["sections"]
    titles = [f.title for f in b.frames]
    assert titles == [expected], f"{locale}: frames titled {titles}, expected {[expected]}"


def test_hk_inherits_the_traditional_pair(board):
    """`zh-Hant-HK` carries no board keys by design — absence must resolve up."""
    b = board("zh-Hant-HK")
    tw = _common("zh-Hant")
    assert [f.title for f in b.frames] == [tw["quotes"]["sections"]]
    assert tw["miro"]["boardQuoteCount_other"].replace("{{count}}", "3") in _all_text(b)
    # The fork ships no `common.json` at all today, and that is the point: an
    # English placeholder seeded here would PIN the key and break the deliberate
    # zh-Hant-HK → zh-Hant → en chain. If the file ever arrives for a genuine HK
    # idiom, it still must not carry these.
    hk = _LOCALES / "zh-Hant-HK" / "common.json"
    if hk.is_file():
        miro = json.loads(hk.read_text(encoding="utf-8")).get("miro", {})
        seeded = [k for k in miro if k.startswith(("boardTitle", "boardQuoteCount"))]
        assert not seeded, f"{seeded} pin the HK fork and break its inheritance"


@pytest.mark.parametrize("locale", [loc for loc in _FULL_LOCALES if loc != "en"])
def test_the_english_chrome_is_gone(board, locale):
    """The actual defect: English words on a non-English researcher's board.

    An English needle is only a defect when this locale's own value does not
    contain it — French for "Sections" is *Sections*, and da/de/nl legitimately
    borrow "board". Checking the needle against the locale's own JSON is what
    separates a leak from a translation that happens to look English; a flat
    blocklist calls both a failure and gets deleted the first time it is wrong.
    """
    text = _all_text(board(locale))
    loc = _common(locale)
    needles = {
        "Sections": loc["quotes"]["sections"],
        "Themes": loc["quotes"]["themes"],
        "research board": loc["miro"]["boardTitle"],
        " quote": " ".join(v for k, v in loc["miro"].items()
                           if k.startswith("boardQuoteCount")),
    }
    leaked = [n for n, own in needles.items() if n in text and n not in own]
    assert not leaked, f"{locale}: English chrome still on the board: {leaked}\n{text}"
    assert "Checkout" in text, "the researcher's own section label must not be translated"


@pytest.mark.parametrize(
    "n,expected_stem",
    [(1, "cytat"), (2, "cytaty"), (5, "cytatów"), (22, "cytaty"), (25, "cytatów")],
)
def test_the_count_goes_through_cldr_selection(board, n, expected_stem):
    """Polish is the proof: `2 cytaty` and `5 cytatów` differ by the *rule*, not
    by a suffix a format string could append."""
    header = board("pl", n=n).stickies[0]
    assert header.kind == "header"
    assert header.text.split("\n")[1] == f"{n} {expected_stem}"


def test_one_quote_reads_one_quote_in_english(board):
    """The board title said "1 quotes" — hand-rolled `({n} quotes)`, no plural.

    Wrong in English, before any of this was about translation.
    """
    assert board("en", n=1).title == "Renfe — research board (1 quote)"
    assert board("en", n=3).title == "Renfe — research board (3 quotes)"


def test_the_untitled_theme_fallback_is_translated(board):
    """A quote with neither section nor theme lands in a column labelled
    `Other`, which was the fourth English literal and the easiest to miss —
    it only appears when the data is incomplete."""
    orphans = _quotes(2, section="")
    b = board("es", quotes=orphans)
    assert [f.title for f in b.frames] == [_common("es")["quotes"]["themes"]]
    assert b.stickies[0].text.startswith(_common("es")["tags"]["other"])


@pytest.mark.parametrize("locale", ["en", "es", "ja", "zh-Hant-HK"])
def test_the_preview_page_declares_its_language(monkeypatch, locale):
    """`<html lang="en">` was hardcoded, so a screen reader read a Spanish board
    in English. The hint below it was hardcoded too."""
    monkeypatch.setattr(
        "bristlenose.server.miro_export.extract_quotes_for_export",
        lambda *a, **k: _quotes(3),
    )
    html = build_preview_html(None, 1, "Renfe", None, locale=locale)
    assert f'<html lang="{locale}">' in html
    expected = _common(locale if locale != "zh-Hant-HK" else "zh-Hant")["miro"]["previewHint"]
    assert expected in html


def test_render_html_still_defaults_to_english():
    """Every default in this chain is English, so a caller that sends nothing
    gets what the board produced before — which is what keeps this a fix rather
    than a behaviour change for anyone who has not been updated."""
    from bristlenose.miro_board import Board

    assert 'lang="en"' in render_html(Board(title="T"))


_CHROME_LITERALS = {
    '"Sections"': "common.quotes.sections",
    '"Themes"': "common.quotes.themes",
    '"Other"': "common.tags.other",
    "research board": "common.miro.boardTitle",
    "▶ clip<": "common.miro.clipLink",
    "Miro board preview": "common.miro.previewHint",
}


@pytest.mark.parametrize(
    "module",
    [
        "bristlenose/miro_board.py",
        "bristlenose/miro_render_svg.py",
        "bristlenose/server/miro_export.py",
    ],
)
def test_no_english_literal_creeps_back(module):
    """The guard that outlives this commit.

    The English defaults in `BoardStrings` are deliberate and live in one place;
    anywhere else, an English literal in these three files is a string that will
    ship untranslated to twenty-one languages and that no locale gate can see.
    """
    tree = ast.parse((_ROOT / module).read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    # Prose is not code. The first run of this gate failed on its own module
    # docstring, which quotes the very words it forbids — the same shape as the
    # `innerHTML` guard that tripped on the comment explaining it. Walk the AST
    # and read only string constants that are *not* docstrings.
    strings = [
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and id(n) not in docstrings
    ]
    code = "\n".join(strings)
    offenders = {
        lit: key for lit, key in _CHROME_LITERALS.items()
        if lit.strip('"<') in code
        and not (module.endswith("miro_board.py") and lit in ('"Sections"', '"Themes"'))
    }
    assert not offenders, (
        f"{module} carries English the board says out loud: "
        + ", ".join(f"{lit} → use {key}" for lit, key in offenders.items())
    )


# ── the preview's own rendering, which is where a translated board lands ─────


def _measure(s: str) -> int:
    """The test's own ruler, deliberately not the module's.

    The first version of this assertion imported `_width` and measured the wrap
    with the same function the wrap uses — so reverting `_width` to `len()` left
    all 84 tests green, because the ruler shrank with the thing it measured. A
    cross-check licenses claims about the function it names and nothing past it
    (root CLAUDE.md, the reconstruction-harness entry). Written out longhand
    here so the two cannot move together.
    """
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


_JA = "駅の券売機で往復を選んだつもりが片道になっていて、改札で初めて気づきました。表示がとても小さいんです。"
_KO = "표를 왕복으로 골랐다고 생각했는데 편도였고, 개찰구에서야 알았습니다."
_ZH = "我在售票機上以為選了來回票，結果是單程，到了閘門才發現。"
_EN = "I thought I had selected a return at the ticket machine but it was a single."


@pytest.mark.parametrize("text", [_JA, _KO, _ZH, _EN])
def test_every_preview_line_fits_the_sticky(text):
    """`raw.split(" ")` is a Latin assumption, and it was load-bearing.

    Japanese, Chinese and Korean prose carries no spaces, so the splitter handed
    back the whole sentence as one token and the sticky rendered one line 3.3×
    its own width, over the top of its neighbours. The truncation path could not
    catch it either — one line is never more than the nine-line budget.

    Width, not length: a CJK glyph is about two Latin advances, so a line of 31
    *characters* is twice the card. Measured 22 Sep 2026; this is the number.
    """
    from bristlenose.miro_render_svg import _wrap

    budget = 31  # what a 240px sticky fits at 14px, per _sticky_svg's max_chars
    lines = _wrap(text, budget)
    over = [(line, _measure(line)) for line in lines if _measure(line) > budget]
    assert not over, f"line(s) wider than the sticky: {over}"
    assert "".join(lines).replace(" ", "") == text.replace(" ", ""), (
        "wrapping must not drop or duplicate a participant's words"
    )


def test_a_single_glyph_wider_than_the_card_still_terminates():
    """The degenerate case the loop has to survive rather than hang on."""
    from bristlenose.miro_render_svg import _wrap

    assert _wrap("漢" * 5, 1) == ["漢"] * 5
