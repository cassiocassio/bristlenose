"""Tests for the shoal word sampler (desktop in-run animation feed).

Assertions rely only on the deterministic fallback stop-word set, `min_length`,
`exclude`, and de-duplication — never on spaCy's exact list — so they pass with
or without spaCy installed (CI has no model).
"""

import random

from bristlenose import shoal


def test_filter_drops_stopwords_and_short_words():
    words = shoal.filter_words(
        ["The onboarding flow was, honestly, a bit confusing at the start"]
    )
    assert "onboarding" in words
    assert "confusing" in words
    assert "the" not in words  # stop-word
    assert "was" not in words  # stop-word
    assert "at" not in words  # 2 chars → below min_length


def test_filter_dedupes_preserving_first_seen_order():
    assert shoal.filter_words(["Search search SEARCH results search"]) == [
        "search",
        "results",
    ]


def test_filter_respects_min_length_and_exclude():
    words = shoal.filter_words(
        ["Dashboard dashboard metrics KPI ok"],
        min_length=4,
        exclude={"metrics"},
    )
    assert words == ["dashboard"]  # metrics excluded, "kpi"/"ok" below length


def test_sample_caps_count():
    texts = ["alpha bravo charlie delta echo foxtrot golf hotel india juliet"]
    assert len(shoal.sample_words(texts, count=3)) == 3


def test_sample_is_deterministic_with_seeded_rng():
    texts = ["alpha bravo charlie delta echo foxtrot golf hotel india juliet"]
    first = shoal.sample_words(texts, count=4, rng=random.Random(42))
    second = shoal.sample_words(texts, count=4, rng=random.Random(42))
    assert first == second
    assert len(first) == 4


def test_sample_without_rng_is_deterministic_prefix():
    texts = ["alpha bravo charlie delta echo"]
    assert shoal.sample_words(texts, count=2) == ["alpha", "bravo"]
