"""Stage 10: LLM-based clustering of screen-specific quotes."""

from __future__ import annotations

import json
import logging

from bristlenose.llm.client import LLMClient
from bristlenose.llm.prompts import QUOTE_CLUSTERING_PROMPT
from bristlenose.llm.structured import ScreenClusteringResult
from bristlenose.models import ExtractedQuote, QuoteType, ScreenCluster
from bristlenose.utils.timecodes import format_timecode

logger = logging.getLogger(__name__)


async def cluster_by_screen(
    quotes: list[ExtractedQuote],
    llm_client: LLMClient,
) -> list[ScreenCluster]:
    """Cluster screen-specific quotes by the screen or task discussed.

    Takes all screen_specific quotes across all participants and groups them
    into coherent clusters, normalising screen labels across participants
    who may describe the same screen differently.

    Args:
        quotes: All screen-specific quotes from all participants.
        llm_client: LLM client for analysis.

    Returns:
        List of ScreenCluster objects ordered by logical product flow.
    """
    screen_quotes = [q for q in quotes if q.quote_type == QuoteType.SCREEN_SPECIFIC]

    if not screen_quotes:
        logger.info("No screen-specific quotes to cluster.")
        return []

    logger.info("Clustering %d screen-specific quotes", len(screen_quotes))

    # Prepare quotes for the LLM — include index so it can reference them
    quotes_for_llm = [
        {
            "index": i,
            "participant": q.participant_id,
            "timecode": format_timecode(q.start_timecode),
            "topic_label": q.topic_label,
            "text": q.text,
        }
        for i, q in enumerate(screen_quotes)
    ]

    quotes_json = json.dumps(quotes_for_llm, indent=2, ensure_ascii=False)

    prompt = QUOTE_CLUSTERING_PROMPT.format(quotes_json=quotes_json)

    try:
        result = await llm_client.analyze(
            system_prompt=(
                "You are an expert user-research analyst. "
                "You organise quotes from research sessions into coherent "
                "screen-by-screen clusters."
            ),
            user_prompt=prompt,
            response_model=ScreenClusteringResult,
        )
    except Exception as exc:
        logger.error("Screen clustering failed: %s", exc)
        # Fallback: one cluster per unique topic label
        return _fallback_clustering(screen_quotes)

    # Convert LLM output to domain models
    clusters: list[ScreenCluster] = []
    for item in result.clusters:
        cluster_quotes = [
            screen_quotes[i]
            for i in item.quote_indices
            if 0 <= i < len(screen_quotes)
        ]

        if not cluster_quotes:
            continue

        clusters.append(
            ScreenCluster(
                screen_label=item.screen_label,
                description=item.description,
                display_order=item.display_order,
                quotes=cluster_quotes,
            )
        )

    # Sort by display order
    clusters.sort(key=lambda c: c.display_order)

    logger.info("Created %d screen clusters", len(clusters))
    return clusters


def _fallback_clustering(quotes: list[ExtractedQuote]) -> list[ScreenCluster]:
    """Fallback clustering: group by topic_label when LLM fails."""
    groups: dict[str, list[ExtractedQuote]] = {}
    for q in quotes:
        groups.setdefault(q.topic_label, []).append(q)

    clusters: list[ScreenCluster] = []
    for i, (label, group_quotes) in enumerate(sorted(groups.items()), start=1):
        clusters.append(
            ScreenCluster(
                screen_label=label,
                description="",
                display_order=i,
                quotes=group_quotes,
            )
        )

    return clusters
