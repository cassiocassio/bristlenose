"""Word sampling for the desktop "shoal" in-run animation.

The macOS app shows a flocking-words animation while an analysis runs (see
`docs/design-llm-call-telemetry.md` §In-run UX). This module picks a small,
stop-word-filtered sample of words from transcript text to feed that animation.

Purely cosmetic: words are chosen to be visually interesting — nobody wants to
watch "the" and "and" flock — not to convey information. The real progress
signal is the determinate ring/subtitle; the shoal is decoration on top.
"""

from __future__ import annotations

import random
import re
from collections.abc import Iterable

# Grammatical function words to drop. spaCy's English list (imported lazily in
# `_stop_words` — no model download needed) is richer, but this fallback keeps
# the behaviour deterministic and environment-independent when spaCy isn't
# installed (e.g. CI), per the "tests must not depend on local environment" rule.
_FALLBACK_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "did",
        "do", "does", "for", "from", "had", "has", "have", "he", "her", "his",
        "i", "if", "in", "is", "it", "its", "me", "my", "no", "not", "of", "on",
        "or", "our", "she", "so", "that", "the", "their", "them", "then",
        "there", "they", "this", "to", "up", "us", "was", "we", "were", "what",
        "when", "which", "who", "will", "with", "would", "you", "your",
    }
)


def _stop_words() -> frozenset[str]:
    """The fallback set, enriched with spaCy's English stop-words if available."""
    try:
        from spacy.lang.en.stop_words import STOP_WORDS
    except Exception:
        return _FALLBACK_STOP_WORDS
    return _FALLBACK_STOP_WORDS | {w.lower() for w in STOP_WORDS}


# A word is an alphabetic run of 2+ letters (internal apostrophes allowed), so
# punctuation, digits, and lone letters never reach the flock.
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’]*[A-Za-z]")


def filter_words(
    texts: Iterable[str],
    *,
    min_length: int = 3,
    exclude: Iterable[str] = (),
) -> list[str]:
    """Extract interesting lowercase word tokens from transcript text.

    Deterministic and order-preserving: tokenises each text, lowercases, drops
    stop-words, tokens shorter than ``min_length``, and anything in ``exclude``
    (words already flocking), then de-duplicates keeping first-seen order.
    """
    stop = _stop_words()
    excluded = {w.lower() for w in exclude}
    seen: dict[str, None] = {}
    for text in texts:
        for match in _WORD_RE.finditer(text):
            word = match.group(0).lower()
            if len(word) < min_length or word in stop or word in excluded:
                continue
            seen.setdefault(word, None)
    return list(seen)


def sample_words(
    texts: Iterable[str],
    count: int,
    *,
    rng: random.Random | None = None,
    min_length: int = 3,
    exclude: Iterable[str] = (),
) -> list[str]:
    """Return up to ``count`` filtered words, shuffled when an ``rng`` is given.

    With no ``rng`` the first ``count`` words are returned in first-seen order
    (deterministic — used by tests). Pass a seeded ``random.Random`` for the
    varied sample the animation actually wants.
    """
    words = filter_words(texts, min_length=min_length, exclude=exclude)
    if rng is not None:
        rng.shuffle(words)
    return words[:count]
