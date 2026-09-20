"""The sentiment chip's label.

The goal being pinned, before any arithmetic: **the chip must never say
"Sentiment"**. That is the framework's name, and naming the framework tells a
researcher nothing. Everything else here is the rule that decides *what it says
instead*, fitted to 27 human judgements — see ``docs/design-signal-card.md`` §5.
"""

from __future__ import annotations

import pytest

from bristlenose.analysis.sentiment_label import (
    MIN_WEIGHT,
    MIXED,
    NEGATIVE,
    POSITIVE,
    VALENCE,
    sentiment_label,
)


def q(sentiment: str, intensity: int = 2) -> dict:
    return {"sentiment": sentiment, "intensity": intensity}


class TestTheChipNeverSaysSentiment:
    """The one invariant the whole rule exists to serve."""

    @pytest.mark.parametrize(
        "quotes",
        [
            [q("frustration")],
            [q("delight"), q("satisfaction")],
            [q("frustration"), q("delight")],
            [q("frustration"), q("delight"), q("surprise", 3)],
            [q("surprise"), q("confidence")],
        ],
        ids=["one", "two-positive", "clash", "clash-plus-neutral", "neutral-plus-positive"],
    )
    def test_never_returns_the_framework_name(self, quotes: list[dict]) -> None:
        label = sentiment_label(quotes)
        assert label is not None
        assert label.text != "Sentiment"
        assert label.text in set(VALENCE) | {POSITIVE, NEGATIVE, MIXED}

    def test_returns_none_when_there_is_no_sentiment_at_all(self) -> None:
        # A codebook card. It names itself and must not be relabelled.
        assert sentiment_label([{"sentiment": None, "intensity": 2}]) is None
        assert sentiment_label([]) is None


class TestVolumeDecidesNotRatio:
    """The one MEASURED finding, and the thing most likely to be 'fixed' wrong.

    A strong ratio on thin evidence is not a signal; a weak ratio on thick
    evidence is. Both cases below come from the calibration set.
    """

    def test_a_strong_ratio_on_thin_evidence_refuses_to_name_a_feeling(self) -> None:
        # The real case, from `IKEA with uxfriends · Shopping Bag`: confusion 3,
        # surprise 2, satisfaction 1. Three-to-one against, on six units of
        # feeling — and the researcher judged it mixed.
        quotes = [q("confusion", 3), q("surprise", 2), q("satisfaction", 1)]
        assert sum(x["intensity"] for x in quotes) < MIN_WEIGHT
        label = sentiment_label(quotes)
        assert label is not None and label.kind == "mixed"

    def test_a_weak_ratio_on_thick_evidence_names_the_feeling(self) -> None:
        # ~60/40, thirty units. Judged by its leading feeling.
        quotes = [q("doubt", 3)] * 6 + [q("delight", 3)] * 4
        label = sentiment_label(quotes)
        assert label is not None and label.kind == "value"
        assert label.text == "doubt"

    def test_the_cut_is_on_total_weight(self) -> None:
        below = [q("frustration", 1), q("frustration", 1), q("delight", 1)]
        assert sum(x["intensity"] for x in below) < MIN_WEIGHT
        assert sentiment_label(below).kind == "mixed"

        above = [q("frustration", 3), q("frustration", 3), q("delight", 2)]
        assert sum(x["intensity"] for x in above) >= MIN_WEIGHT
        assert sentiment_label(above).kind == "value"


class TestSurpriseIsNeutral:
    """MEASURED: four real cards were labelled mixed on a neutral quote alone,
    one of them carrying 76 units of positive weight against 4 of neutral."""

    def test_a_neutral_quote_does_not_make_a_card_mixed(self) -> None:
        quotes = [q("delight", 3), q("satisfaction", 3), q("confidence", 3), q("surprise", 2)]
        label = sentiment_label(quotes)
        assert label is not None and label.kind != "mixed"

    def test_surprise_can_still_be_the_label_when_it_leads_alone(self) -> None:
        assert sentiment_label([q("surprise", 3), q("surprise", 2)]).text == "surprise"


class TestTheSummaryLabels:
    def test_several_positive_values_with_no_leader_give_positive(self) -> None:
        quotes = [q("delight", 2), q("satisfaction", 2)]
        assert sentiment_label(quotes).text == POSITIVE

    def test_several_negative_values_with_no_leader_give_negative(self) -> None:
        quotes = [q("frustration", 2), q("confusion", 2)]
        assert sentiment_label(quotes).text == NEGATIVE

    def test_a_clear_leader_beats_the_direction(self) -> None:
        # Naming a feeling is preferred to naming a direction wherever honest.
        quotes = [q("frustration", 3), q("frustration", 3), q("confusion", 1)]
        assert sentiment_label(quotes).text == "frustration"


class TestTheReasonIsCarried:
    """Every label says why. The run inspector reads it, and a label with no
    stated reason is one nobody can argue with."""

    def test_each_rung_reports_itself(self) -> None:
        assert "nothing opposing" in sentiment_label([q("delight", 2)] * 3).why
        assert "enough feeling" in sentiment_label(
            [q("doubt", 3)] * 3 + [q("delight", 2)]
        ).why
        assert "pulling both ways" in sentiment_label(
            [q("doubt", 1), q("delight", 1)]
        ).why


class TestTheShapeThatActuallyRenders:
    """A quote on the CODEBOOK path carries NO `sentiment` field.

    This class exists because the rule was first written against a harvest
    whose `sentiment` key the harvest itself had invented, and it agreed with
    the validated experiment on all 87 real cards while being unable to read a
    single one of them through the path the lens uses. The API test caught it;
    nothing else would have.

    On the codebook path the sentiment framework's TAGS are the seven values,
    so they arrive in `tag_names`.
    """

    def test_reads_the_sentiment_out_of_tag_names(self) -> None:
        quotes = [
            {"tag_names": ["frustration"], "intensity": 3},
            {"tag_names": ["frustration"], "intensity": 3},
            {"tag_names": ["delight"], "intensity": 2},
        ]
        label = sentiment_label(quotes)
        assert label is not None
        assert label.text == "frustration"

    def test_a_dataclass_quote_with_no_sentiment_attribute_still_works(self) -> None:
        from bristlenose.analysis.models import SignalQuote

        quotes = [
            SignalQuote("a", "p1", "s1", 0.0, 3, ["confusion"]),
            SignalQuote("b", "p1", "s1", 1.0, 3, ["confusion"]),
            SignalQuote("c", "p2", "s1", 2.0, 2, ["satisfaction"]),
        ]
        assert not hasattr(quotes[0], "sentiment")
        assert sentiment_label(quotes).text == "confusion"

    def test_a_quote_carrying_two_feelings_counts_for_both(self) -> None:
        # Splitting the weight would make a quote saying two things count for
        # less than one saying one.
        quotes = [{"tag_names": ["confusion", "frustration"], "intensity": 2}]
        label = sentiment_label(quotes)
        assert label is not None and label.text == NEGATIVE

    def test_non_sentiment_tags_are_ignored(self) -> None:
        # A codebook card's tags are not sentiments and must not be read as any.
        assert sentiment_label([{"tag_names": ["system response"], "intensity": 3}]) is None
