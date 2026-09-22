"""Stage 11: LLM-based thematic grouping of general/contextual quotes."""

from __future__ import annotations

import json
import logging

from bristlenose.events import StageFailure, StageOutcome
from bristlenose.i18n import get_locale, t_in
from bristlenose.llm.boundary import wrap_untrusted
from bristlenose.llm.client import LLMClient
from bristlenose.llm.output_language import output_language_steer
from bristlenose.llm.prompts import get_prompt_template
from bristlenose.llm.structured import ThematicGroupingResult
from bristlenose.models import ExtractedQuote, QuoteType, ThemeGroup
from bristlenose.run_lifecycle import _build_cause
from bristlenose.utils.timecodes import format_timecode

logger = logging.getLogger(__name__)


async def group_by_theme(
    quotes: list[ExtractedQuote],
    llm_client: LLMClient,
) -> tuple[list[ThemeGroup], StageOutcome]:
    """Group general/contextual quotes into emergent themes.

    Takes all general_context quotes across all participants and identifies
    shared themes, patterns, and commonalities.

    Args:
        quotes: All general-context quotes from all participants.
        llm_client: LLM client for analysis.

    Returns:
        Tuple of (themes, outcome). The LLM call's success/failure is
        emitted on ``outcome`` at the call site, BEFORE any fallback fires.
        A fallback grouping by topic label is returned so the rest of the
        pipeline has structured data to render, but the orchestrator reads
        ``outcome.succeeded == 0 AND outcome.attempted > 0`` and abandons
        the run honestly rather than shipping a degraded report dressed up
        as a real one.
    """
    context_quotes = [q for q in quotes if q.quote_type == QuoteType.GENERAL_CONTEXT]

    if not context_quotes:
        logger.info("No contextual quotes to group into themes.")
        return [], StageOutcome()

    logger.info("Grouping %d contextual quotes into themes", len(context_quotes))
    outcome = StageOutcome(attempted=1)

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

    quotes_json = json.dumps(quotes_for_llm, ensure_ascii=False, separators=(",", ":"))

    _tmpl = get_prompt_template("thematic-grouping")

    try:
        result = await llm_client.analyze(
            # Generated text follows the UI language (V1, 22 Sep 2026). Empty for
            # English, so the prompt stays byte-identical to the one that shipped
            # before this existed — see bristlenose/llm/output_language.py.
            system_prompt=_tmpl.system + output_language_steer(),
            user_prompt=_tmpl.user.format(quotes_json=wrap_untrusted("quotes", quotes_json)),
            response_model=ThematicGroupingResult,
            prompt_template=_tmpl,
        )
    except Exception as exc:
        logger.error("Thematic grouping failed: %s", exc)
        outcome.failed.append(StageFailure(
            session_id=None,
            cause=_build_cause(
                exc,
                stage="cluster_and_group",
                provider=llm_client.provider,
            ),
        ))
        return _fallback_grouping(context_quotes), outcome

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
    # get folded into an "Uncategorised" bucket — quotes that don't have a home
    # yet. Deliberately NOT "observations": an observation is a proto-finding a
    # human noticed, whereas these are simply unplaced.
    min_theme_quotes = 2
    strong_themes = [t for t in themes if len(t.quotes) >= min_theme_quotes]
    weak_quotes: list[ExtractedQuote] = []
    for t in themes:
        if len(t.quotes) < min_theme_quotes:
            weak_quotes.extend(t.quotes)

    if weak_quotes:
        # Deduplicate (safety net — LLM should assign each quote once,
        # but may occasionally duplicate across weak themes)
        seen_ids: set[tuple[str, float, str]] = set()
        unique_weak: list[ExtractedQuote] = []
        for q in weak_quotes:
            key = (q.participant_id, q.start_timecode, q.text[:40])
            if key not in seen_ids:
                seen_ids.add(key)
                unique_weak.append(q)

        # OURS, not the model's — and it was the only English string left in a
        # fully-steered Spanish run (`experiments/generated-language/`), which
        # is how it was found.
        #
        # Its own keys, deliberately, after a first attempt reused the Quotes
        # lens's `uncategorisedHeading` / `uncategorisedIntro`. Those describe
        # the *floor* — pinned quotes the persistence layer froze — and the
        # sentence reads "quotes you kept aren't in any section or theme",
        # which is false here twice: these were never kept, and they ARE in a
        # theme, the one it is the description of. It was wrong in 21 languages
        # at once. The floor's copy also interpolates a count the SPA
        # recomputes live, so borrowing it froze a number into persisted prose
        # that nothing recomputes — hide one quote and the sentence contradicts
        # the cards under it. Two concepts that share a word are still two
        # concepts.
        #
        # Safe to translate: the server's uncategorised *floor* is computed by
        # join absence (`routes/quotes.py`), not by matching this label, and
        # `UNCATEGORISED_GROUP_NAME` in `server/models.py` is a codebook-group
        # sentinel that shares the spelling and nothing else. Checked before
        # changing it, because a label something routes on is not a label.
        #
        # Resolved at generation time, like everything else this stage writes,
        # so it freezes in the analysis language. Display-time would be better
        # and is a bigger change: the SPA renders `theme_label` raw.
        locale = get_locale()
        strong_themes.append(
            ThemeGroup(
                theme_label=t_in(locale, "common.quotes.thinThemeLabel"),
                description=t_in(locale, "common.quotes.thinThemeBody"),
                quotes=unique_weak,
            )
        )
        logger.info(
            "Moved %d quotes from %d thin themes into 'Uncategorised'",
            len(unique_weak),
            len(themes) - len(strong_themes) + 1,
        )

    logger.info("Created %d theme groups", len(strong_themes))
    outcome.succeeded = 1
    return strong_themes, outcome


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
