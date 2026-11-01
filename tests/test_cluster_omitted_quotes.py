"""A quote the model leaves out of every section or theme is placed, not lost (N143, 1 Nov 2026).

Stages 10 and 11 built their groups only from the indices the model sent back and never
checked that every quote came back, so a quote the model omitted was in no section and no
theme, the run said Done, and the researcher's quote was silently missing from the report. A
quote the model puts in two places showed twice. Decided: an unplaced quote goes where unplaced
quotes already go (the Uncategorised group for themes; a section named for its own topic for
screens), and a quote placed twice keeps its first placement. Nothing is lost.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from bristlenose.llm.structured import (
    ScreenClusteringResult,
    ScreenClusterItem,
    ThematicGroupingResult,
    ThemeGroupItem,
)
from bristlenose.models import ExtractedQuote, QuoteType


def _quote(n: int, topic: str, kind: QuoteType) -> ExtractedQuote:
    return ExtractedQuote(
        session_id="s1", participant_id="p1", start_timecode=float(n), end_timecode=n + 1.0,
        text=f"quote number {n} says something distinct", topic_label=topic, quote_type=kind,
    )


def _client(result):
    client = AsyncMock()
    client.provider = "anthropic"
    client.analyze = AsyncMock(return_value=result)
    return client


def _texts(groups) -> list[str]:
    return [q.text for g in groups for q in g.quotes]


def test_screen_quotes_the_model_left_out_still_get_a_section() -> None:
    from bristlenose.stages.s10_quote_clustering import cluster_by_screen

    quotes = [_quote(i, "Basket" if i < 3 else "Checkout", QuoteType.SCREEN_SPECIFIC)
              for i in range(5)]
    reply = ScreenClusteringResult(clusters=[
        ScreenClusterItem(screen_label="Basket", description="d", display_order=1,
                          quote_indices=[0, 1]),
    ])
    clusters, outcome = asyncio.run(cluster_by_screen(quotes, _client(reply)))
    assert sorted(_texts(clusters)) == sorted(q.text for q in quotes), "no quote may be lost"
    assert outcome.failed == []
    # The omitted quotes sit in sections named for their own topic, after the model's.
    assert [c.screen_label for c in clusters][0] == "Basket"
    assert clusters[0].display_order < min(c.display_order for c in clusters[1:])


def test_a_screen_quote_placed_twice_keeps_its_first_placement() -> None:
    from bristlenose.stages.s10_quote_clustering import cluster_by_screen

    quotes = [_quote(i, "Basket", QuoteType.SCREEN_SPECIFIC) for i in range(3)]
    reply = ScreenClusteringResult(clusters=[
        ScreenClusterItem(screen_label="A", description="d", display_order=1,
                          quote_indices=[0, 1, 1]),
        ScreenClusterItem(screen_label="B", description="d", display_order=2,
                          quote_indices=[1, 2]),
    ])
    clusters, _ = asyncio.run(cluster_by_screen(quotes, _client(reply)))
    texts = _texts(clusters)
    assert sorted(texts) == sorted(q.text for q in quotes)
    assert len(texts) == len(set(texts)), "a quote must appear once"
    assert [q.text for q in clusters[0].quotes] == [quotes[0].text, quotes[1].text]


def test_theme_quotes_the_model_left_out_land_in_uncategorised() -> None:
    from bristlenose.stages.s11_thematic_grouping import group_by_theme

    quotes = [_quote(i, "Trust", QuoteType.GENERAL_CONTEXT) for i in range(6)]
    reply = ThematicGroupingResult(themes=[
        ThemeGroupItem(theme_label="Trust", description="d", quote_indices=[0, 1, 2]),
    ])
    themes, outcome = asyncio.run(group_by_theme(quotes, _client(reply)))
    assert sorted(_texts(themes)) == sorted(q.text for q in quotes), "no quote may be lost"
    assert outcome.failed == []
    assert [t.theme_label for t in themes][0] == "Trust"
    assert len(themes) == 2, "the model's theme, plus one Uncategorised group"
    assert {q.text for q in themes[1].quotes} == {quotes[3].text, quotes[4].text, quotes[5].text}


def test_a_theme_quote_placed_twice_keeps_its_first_placement() -> None:
    from bristlenose.stages.s11_thematic_grouping import group_by_theme

    quotes = [_quote(i, "Trust", QuoteType.GENERAL_CONTEXT) for i in range(4)]
    reply = ThematicGroupingResult(themes=[
        ThemeGroupItem(theme_label="A", description="d", quote_indices=[0, 1]),
        ThemeGroupItem(theme_label="B", description="d", quote_indices=[1, 2, 3]),
    ])
    themes, _ = asyncio.run(group_by_theme(quotes, _client(reply)))
    texts = _texts(themes)
    assert len(texts) == len(set(texts)) == 4
    first = next(t for t in themes if t.theme_label == "A")
    assert [q.text for q in first.quotes] == [quotes[0].text, quotes[1].text]


def test_nothing_omitted_changes_nothing() -> None:
    from bristlenose.stages.s11_thematic_grouping import group_by_theme

    quotes = [_quote(i, "Trust", QuoteType.GENERAL_CONTEXT) for i in range(4)]
    reply = ThematicGroupingResult(themes=[
        ThemeGroupItem(theme_label="A", description="d", quote_indices=[0, 1]),
        ThemeGroupItem(theme_label="B", description="d", quote_indices=[2, 3]),
    ])
    themes, _ = asyncio.run(group_by_theme(quotes, _client(reply)))
    assert [t.theme_label for t in themes] == ["A", "B"], "no stray Uncategorised group"


def test_an_omitted_screen_quote_joins_the_model_section_of_the_same_name() -> None:
    """One 'Checkout', not two: a quote the model left out whose own topic names a section
    the model made goes into that section (matched ignoring case and surrounding space)."""
    from bristlenose.stages.s10_quote_clustering import cluster_by_screen

    quotes = [
        _quote(0, "Checkout", QuoteType.SCREEN_SPECIFIC),
        _quote(1, "Checkout", QuoteType.SCREEN_SPECIFIC),
        _quote(2, " checkout ", QuoteType.SCREEN_SPECIFIC),
        _quote(3, "Login", QuoteType.SCREEN_SPECIFIC),
    ]
    reply = ScreenClusteringResult(clusters=[
        ScreenClusterItem(screen_label="Checkout", description="the pay step", display_order=1,
                          quote_indices=[0]),
    ])
    clusters, _ = asyncio.run(cluster_by_screen(quotes, _client(reply)))
    assert sorted(_texts(clusters)) == sorted(q.text for q in quotes), "no quote may be lost"
    labels = [c.screen_label.strip().casefold() for c in clusters]
    assert labels.count("checkout") == 1, "a second Checkout section must not appear"
    checkout = clusters[0]
    assert checkout.description == "the pay step", "the model's section keeps its description"
    assert [q.text for q in checkout.quotes] == [quotes[0].text, quotes[1].text, quotes[2].text]
    assert [c.screen_label for c in clusters[1:]] == ["Login"], "an unmatched topic still gets one"
