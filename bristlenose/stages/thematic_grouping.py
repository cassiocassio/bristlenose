"""Stage 11: LLM-based thematic grouping of general/contextual quotes."""

from __future__ import annotations

import json
import logging

from bristlenose.llm.client import LLMClient
from bristlenose.llm.prompts import THEMATIC_GROUPING_PROMPT
from bristlenose.llm.structured import ThematicGroupingResult
from bristlenose.models import ExtractedQuote, QuoteType, ThemeGroup
from bristlenose.utils.timecodes import format_timecode

logger = logging.getLogger(__name__)


async def group_by_theme(
    quotes: list[ExtractedQuote],
    llm_client: LLMClient,
) -> list[ThemeGroup]:
    """Group general/contextual quotes into emergent themes.

    Takes all general_context quotes across all participants and identifies
    shared themes, patterns, and commonalities.

    Args:
        quotes: All general-context quotes from all participants.
        llm_client: LLM client for analysis.

    Returns:
        List of ThemeGroup objects.
    """
    context_quotes = [q for q in quotes if q.quote_type == QuoteType.GENERAL_CONTEXT]

    if not context_quotes:
        logger.info("No contextual quotes to group into themes.")
        return []

    logger.info("Grouping %d contextual quotes into themes", len(context_quotes))

    # Prepare quotes for the LLM
    quotes_for_llm = [
        {
            "index": i,
            "participant": q.participant_id,
            "timecode": format_timecode(q.start_timecode),
            "topic_label": q.topic_label,
            "text": q.text,
        }
        for i, q in enumerate(context_quotes)
    ]

    quotes_json = json.dumps(quotes_for_llm, indent=2, ensure_ascii=False)

    prompt = THEMATIC_GROUPING_PROMPT.format(quotes_json=quotes_json)

    try:
        result = await llm_client.analyze(
            system_prompt=(
                "You are an expert user-research analyst. "
                "You identify emergent themes across participant quotes "
                "about their broader context, workflows, and experiences."
            ),
            user_prompt=prompt,
            response_model=ThematicGroupingResult,
        )
    except Exception as exc:
        logger.error("Thematic grouping failed: %s", exc)
        return _fallback_grouping(context_quotes)

    # Convert LLM output to domain models
    themes: list[ThemeGroup] = []
    for item in result.themes:
        theme_quotes = [
            context_quotes[i]
            for i in item.quote_indices
            if 0 <= i < len(context_quotes)
        ]

        if not theme_quotes:
            continue

        themes.append(
            ThemeGroup(
                theme_label=item.theme_label,
                description=item.description,
                quotes=theme_quotes,
            )
        )

    # Enforce minimum evidence threshold: themes with fewer than 2 quotes
    # get folded into an "Uncategorised observations" bucket.
    min_theme_quotes = 2
    strong_themes = [t for t in themes if len(t.quotes) >= min_theme_quotes]
    weak_quotes: list[ExtractedQuote] = []
    for t in themes:
        if len(t.quotes) < min_theme_quotes:
            weak_quotes.extend(t.quotes)

    if weak_quotes:
        # Deduplicate (a quote could appear in multiple weak themes)
        seen_ids: set[tuple[str, float, str]] = set()
        unique_weak: list[ExtractedQuote] = []
        for q in weak_quotes:
            key = (q.participant_id, q.start_timecode, q.text[:40])
            if key not in seen_ids:
                seen_ids.add(key)
                unique_weak.append(q)

        strong_themes.append(
            ThemeGroup(
                theme_label="Uncategorised observations",
                description="Individual observations that did not cluster into a broader theme.",
                quotes=unique_weak,
            )
        )
        logger.info(
            "Moved %d quotes from %d thin themes into 'Uncategorised observations'",
            len(unique_weak),
            len(themes) - len(strong_themes) + 1,
        )

    logger.info("Created %d theme groups", len(strong_themes))
    return strong_themes


def _fallback_grouping(quotes: list[ExtractedQuote]) -> list[ThemeGroup]:
    """Fallback grouping: group by topic_label when LLM fails."""
    groups: dict[str, list[ExtractedQuote]] = {}
    for q in quotes:
        groups.setdefault(q.topic_label, []).append(q)

    themes: list[ThemeGroup] = []
    for label, group_quotes in sorted(groups.items()):
        themes.append(
            ThemeGroup(
                theme_label=label,
                description="",
                quotes=group_quotes,
            )
        )

    return themes
