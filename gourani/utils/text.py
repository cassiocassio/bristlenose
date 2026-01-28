"""Text cleanup utilities: smart quotes, disfluency removal, editorial helpers."""

from __future__ import annotations

import re


def apply_smart_quotes(text: str) -> str:
    """Replace straight double quotes with smart (curly) double quotes.

    Opening: \u201c  Closing: \u201d
    Also handles single quotes: \u2018 \u2019
    """
    # Double quotes
    result = text
    # Opening double quote: after start-of-string, whitespace, or open paren/bracket
    result = re.sub(r'(^|[\s(\[])"', "\\1\u201c", result)
    # Closing double quote: everything else
    result = result.replace('"', "\u201d")

    # Single quotes / apostrophes
    # Apostrophes within words (don't, it's, I'm) — use right single quote
    result = re.sub(r"(\w)'(\w)", "\\1\u2019\\2", result)

    return result


def wrap_in_smart_quotes(text: str) -> str:
    """Wrap text in smart double quotes, stripping any existing outer quotes."""
    text = text.strip()
    # Remove existing outer quotes (straight or smart)
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("\u201c") and text.endswith("\u201d")
    ):
        text = text[1:-1].strip()
    return f"\u201c{text}\u201d"


# Filler patterns to remove — replaced with ellipsis
_FILLER_WORDS = re.compile(
    r"\b(?:"
    r"um+|uh+|ah+|er+|hmm+|"
    r"you know|"
    r"sort of|kind of|"
    r"I mean"
    r")\b",
    re.IGNORECASE,
)

# "like" when used as filler (not comparison/simile)
# Heuristic: "like" preceded by a comma or start, and followed by a comma or common filler context
_LIKE_FILLER = re.compile(
    r"(?:^|,)\s*like\s*(?:,|\s)", re.IGNORECASE
)


def remove_disfluencies(text: str) -> str:
    """Remove filler words and replace with ellipsis.

    Handles: um, uh, ah, er, hmm, "you know", "sort of", "kind of", "I mean",
    and "like" when used as filler.

    Returns cleaned text with `...` where fillers were removed.
    """
    result = text

    # Remove filler words, replace with ellipsis marker
    result = _FILLER_WORDS.sub("\u2026", result)

    # Handle filler "like" — only when clearly filler, not comparison
    # Replace ", like," and ", like " patterns
    result = re.sub(r",\s*like\s*,", " \u2026", result, flags=re.IGNORECASE)
    result = re.sub(r",\s*like\s+", " \u2026 ", result, flags=re.IGNORECASE)

    # Clean up multiple consecutive ellipses
    result = re.sub(r"(?:\u2026\s*)+", "... ", result)
    result = re.sub(r"\.\.\.\s*\.\.\.", "...", result)

    # Clean up whitespace
    result = re.sub(r"\s{2,}", " ", result)
    result = result.strip()

    # Don't start or end with ellipsis
    result = re.sub(r"^\.\.\.\s*", "", result)
    result = re.sub(r"\s*\.\.\.$", "", result)

    return result


def format_editorial_insertion(word: str) -> str:
    """Format a word as an editorial insertion: [word]."""
    return f"[{word}]"


def format_researcher_context(context: str) -> str:
    """Format researcher context prefix: [When asked about X]."""
    context = context.strip()
    if not context.startswith("["):
        context = f"[{context}]"
    return context


def clean_transcript_text(text: str) -> str:
    """Basic cleanup of raw transcript text.

    - Collapse whitespace
    - Strip leading/trailing whitespace
    - Fix common transcription artefacts
    """
    result = text
    result = re.sub(r"\s+", " ", result)
    result = result.strip()
    # Fix double periods
    result = re.sub(r"\.{2}(?!\.)", ".", result)
    return result
