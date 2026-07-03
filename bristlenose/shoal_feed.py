"""Best-effort feed writer for the desktop "shoal" in-run animation.

During a desktop-hosted run, appends sampled transcript words, topic labels, and
sentiment-tagged fragments to ``<output>/.bristlenose/shoal-feed.jsonl``. The
macOS app tails this file and flocks the words (the ``ShoalFeed`` reader on the
Swift side); see ``docs/private/handoffs/shoal-completion.md``.

Purely decorative — a failure here must NEVER affect the run, so every public
function is wrapped best-effort and logs at WARNING (never a bare ``pass``: a
silently-never-written feed must be greppable, not invisible). Gated to
desktop-hosted runs (the app tails it; CLI users get no stray file). It holds
verbatim pre-PII fragments, so it lives in ``.bristlenose/`` alongside the other
re-identification keys (``pii_summary.txt``, ``llm-calls.jsonl``) — hidden and
never exported. Truncated at run start (so words never carry across runs) and
deleted on *successful* completion; a failed/abandoned run's feed persists there
until the next run's ``start()`` truncates it — consistent with those siblings,
which also survive a failed run. (A ``finally`` around the whole run would delete
it eagerly; deferred — the write-path fail-safe is the load-bearing invariant,
not eager cleanup.)

A SEPARATE file from ``pipeline-events.jsonl`` by design — that one is kept
string-free / travel-clean; this one carries content.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from pathlib import Path

from bristlenose import shoal
from bristlenose.config import hosted_by_desktop

logger = logging.getLogger(__name__)

_FEED_NAME = "shoal-feed.jsonl"

# The LLM sentiment vocabulary (models.Sentiment) → the three-way scale the Swift
# ShoalSentiment renders (green / red / neutral). Anything else, or missing → neutral.
_POSITIVE = {"satisfaction", "delight", "confidence"}
_NEGATIVE = {"frustration", "confusion", "doubt"}

# How many words to sample into a single "word" batch — a pool the scene draws
# and cycles from (it only ever shows ~45–50 at once), not a per-frame count.
_WORD_SAMPLE = 50

# Interesting words to pull from each tagged quote (we flock short fragments, not
# whole quotes).
_WORDS_PER_QUOTE = 2


def _feed_path(output_dir: Path) -> Path:
    # Mirrors OutputPaths.internal_dir (.bristlenose/) without importing it, to
    # keep this module dependency-light and unit-testable with a plain tmp dir.
    return output_dir / ".bristlenose" / _FEED_NAME


def _sentiment_bucket(value: str | None) -> str:
    if value in _POSITIVE:
        return "positive"
    if value in _NEGATIVE:
        return "negative"
    return "neutral"


def _write(path: Path, *, line: str | None) -> None:
    """Append one JSONL line, or truncate to empty (``line=None``).

    Mirrors ``events.append_event``: ``mkdir(parents)`` first, ``O_NOFOLLOW`` +
    ``0o600`` (this file carries verbatim participant words, same hygiene as its
    ``.bristlenose/`` siblings).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if line is None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
        payload = b""
    else:
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW
        payload = (line + "\n").encode("utf-8")
    fd = os.open(path, flags, 0o600)
    try:
        if payload:
            os.write(fd, payload)
    finally:
        os.close(fd)


def _emit(output_dir: Path, batch: dict) -> None:
    if not batch.get("texts"):
        return
    _write(_feed_path(output_dir), line=json.dumps(batch, ensure_ascii=True))


def start(output_dir: Path) -> None:
    """Truncate (or create empty) the feed at run start — a re-run must not flock
    the previous run's leftover words. No-op unless desktop-hosted."""
    if not hosted_by_desktop():
        return
    try:
        _write(_feed_path(output_dir), line=None)
    except Exception as exc:  # decoration — must never fail the run
        logger.warning("shoal feed start failed: %s", exc)


def finish(output_dir: Path) -> None:
    """Delete the feed on *successful* completion (the happy path). A failed run
    leaves it for the next ``start()`` to truncate — see the module docstring.
    No-op unless desktop-hosted."""
    if not hosted_by_desktop():
        return
    try:
        _feed_path(output_dir).unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("shoal feed finish failed: %s", exc)


def emit_words(output_dir: Path, texts: Iterable[str]) -> None:
    """Sample stop-word-filtered words from transcript text → one ``word`` batch.

    Pass a generator; it is consumed inside the guard so an extraction error
    can't escape either.
    """
    if not hosted_by_desktop():
        return
    try:
        words = shoal.sample_words(list(texts), _WORD_SAMPLE)
        _emit(output_dir, {"kind": "word", "texts": words})
    except Exception as exc:
        logger.warning("shoal feed emit_words failed: %s", exc)


def emit_themes(output_dir: Path, labels: Iterable[str]) -> None:
    """Topic/section labels, verbatim + de-duped → one ``theme`` batch.

    Labels are already curated short phrases ("First impression") — do NOT run
    them through the word sampler, which would shred them into tokens.
    """
    if not hosted_by_desktop():
        return
    try:
        seen: dict[str, None] = {}
        for raw in labels:
            label = (raw or "").strip()
            if label:
                seen.setdefault(label, None)
        _emit(output_dir, {"kind": "theme", "texts": list(seen)})
    except Exception as exc:
        logger.warning("shoal feed emit_themes failed: %s", exc)


def emit_sentiment(output_dir: Path, quotes: Iterable[tuple[str, str | None]]) -> None:
    """Short fragments sampled from tagged quotes, grouped by sentiment bucket →
    up to three ``sentiment`` batches (one per positive/negative/neutral present).

    ``quotes`` is an iterable of ``(quote_text, sentiment_value)``. We sample a
    couple of interesting words per quote rather than flocking whole quotes.
    """
    if not hosted_by_desktop():
        return
    try:
        buckets: dict[str, list[str]] = {}
        for text, value in quotes:
            picked = shoal.sample_words([text or ""], _WORDS_PER_QUOTE)
            if picked:
                buckets.setdefault(_sentiment_bucket(value), []).extend(picked)
        for sentiment, words in buckets.items():
            deduped = list(dict.fromkeys(words))
            _emit(output_dir, {"kind": "sentiment", "texts": deduped, "sentiment": sentiment})
    except Exception as exc:
        logger.warning("shoal feed emit_sentiment failed: %s", exc)
