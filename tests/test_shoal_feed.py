"""Tests for the shoal feed writer (desktop in-run animation).

Gated on the desktop-host env var; tests set/unset it explicitly so they pass in
CI (no desktop, var absent) with or without it in the ambient environment.
"""

import json

import pytest

from bristlenose import shoal_feed

_ENV = "_BRISTLENOSE_HOSTED_BY_DESKTOP"


@pytest.fixture
def hosted(monkeypatch):
    monkeypatch.setenv(_ENV, "1")


def _feed(output_dir):
    return output_dir / ".bristlenose" / "shoal-feed.jsonl"


def _batches(output_dir):
    path = _feed(output_dir)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_not_hosted_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv(_ENV, raising=False)
    shoal_feed.start(tmp_path)
    shoal_feed.emit_words(tmp_path, ["onboarding was honestly confusing"])
    shoal_feed.emit_themes(tmp_path, ["Checkout"])
    assert not _feed(tmp_path).exists()


def test_start_truncates_prior_content(tmp_path, hosted):
    shoal_feed.emit_words(tmp_path, ["stale leftover words from a previous run"])
    assert _batches(tmp_path)  # something was written
    shoal_feed.start(tmp_path)
    assert _feed(tmp_path).exists()
    assert _feed(tmp_path).read_text() == ""  # truncated to empty


def test_emit_words_filters_and_batches(tmp_path, hosted):
    shoal_feed.emit_words(tmp_path, ["The onboarding flow was honestly confusing at the start"])
    batches = _batches(tmp_path)
    assert len(batches) == 1
    assert batches[0]["kind"] == "word"
    assert "onboarding" in batches[0]["texts"]
    assert "the" not in batches[0]["texts"]  # stop-word filtered


def test_emit_themes_are_verbatim_and_deduped(tmp_path, hosted):
    shoal_feed.emit_themes(tmp_path, ["First impression", "Checkout", "First impression", "  ", ""])
    batches = _batches(tmp_path)
    assert batches[0]["kind"] == "theme"
    # curated phrases kept whole (not tokenised), de-duped, blanks dropped
    assert batches[0]["texts"] == ["First impression", "Checkout"]


def test_emit_sentiment_buckets_the_feeling_enum(tmp_path, hosted):
    quotes = [
        ("the checkout process was delightful", "delight"),          # → positive
        ("navigation is frustrating and confusing", "frustration"),  # → negative
        ("i was surprised by the whole layout", "surprise"),         # → neutral
        ("no sentiment recorded here", None),                        # → neutral
    ]
    shoal_feed.emit_sentiment(tmp_path, quotes)
    by_sentiment = {b["sentiment"]: b for b in _batches(tmp_path)}
    assert set(by_sentiment) == {"positive", "negative", "neutral"}
    assert all(b["kind"] == "sentiment" for b in by_sentiment.values())
    # positive bucket drew interesting words from the delight quote
    assert "checkout" in by_sentiment["positive"]["texts"]


def test_finish_deletes_feed(tmp_path, hosted):
    shoal_feed.emit_words(tmp_path, ["some interesting content words to sample"])
    assert _feed(tmp_path).exists()
    shoal_feed.finish(tmp_path)
    assert not _feed(tmp_path).exists()


def test_finish_is_safe_when_absent(tmp_path, hosted):
    shoal_feed.finish(tmp_path)  # never created — must not raise


def test_best_effort_never_raises(tmp_path, hosted, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(shoal_feed, "_write", boom)
    # All of these must swallow + log, never propagate.
    shoal_feed.start(tmp_path)
    shoal_feed.emit_words(tmp_path, ["content words here now"])
    shoal_feed.emit_themes(tmp_path, ["Checkout"])
    shoal_feed.emit_sentiment(tmp_path, [("delightful checkout flow", "delight")])
