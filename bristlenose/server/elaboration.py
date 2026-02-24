"""Signal elaboration service — LLM-generated interpretive names for signal cards.

Generates 2-4 word signal names, pattern classification (success/gap/tension/
recovery), and one-sentence findings for the top N framework signal cards.
Results are cached in SQLite keyed by a content hash — if quotes or tags
change the hash changes and a new elaboration is generated.

Public API::

    compute_signal_key(source_type, location, group_name) → str
    compute_content_hash(quote_texts, tag_names)           → str
    format_signals_for_prompt(signals, template)            → str
    generate_elaborations(signals, codebook_id, settings,
                          db, project_id)                   → dict
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession

    from bristlenose.config import BristlenoseSettings
    from bristlenose.server.codebook import CodebookTemplate
    from bristlenose.server.routes.analysis import TagSignal

logger = logging.getLogger(__name__)

#: Default number of top signals to elaborate.
DEFAULT_TOP_N = 10

#: Valid pattern types.
VALID_PATTERNS = frozenset({"success", "gap", "tension", "recovery"})


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ElaborationResult:
    """One elaboration result for a single signal card."""

    signal_name: str
    pattern: str
    elaboration: str


# ---------------------------------------------------------------------------
# Key / hash helpers
# ---------------------------------------------------------------------------


def compute_signal_key(source_type: str, location: str, group_name: str) -> str:
    """Build a stable key for a signal card.

    Format: ``"section|Homepage|Discoverability"``
    """
    return f"{source_type}|{location}|{group_name}"


def compute_content_hash(quote_texts: list[str], tag_names: list[str]) -> str:
    """Compute a SHA-256 hash of the signal's content for cache invalidation.

    Changes when quotes are added/removed or tags change.
    """
    content = "\n".join(sorted(quote_texts)) + "\n---\n" + "\n".join(sorted(tag_names))
    return hashlib.sha256(content.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------


def format_signals_for_prompt(
    signals: list[TagSignal],
    template: CodebookTemplate,
) -> str:
    """Format signals as numbered blocks for the LLM prompt.

    Each block includes the section label, group name + subtitle (the lens
    question), tag definitions for tags that appear in the signal's quotes,
    and the quotes with participant IDs and tag names.
    """
    from bristlenose.server.autocode import _format_tag

    # Build lookup: group_name -> TemplateGroup
    group_lookup = {g.name: g for g in template.groups}

    blocks: list[str] = []
    for i, sig in enumerate(signals):
        lines: list[str] = [f"### Signal {i}"]
        lines.append(f"Section: {sig.location}")

        tg = group_lookup.get(sig.group_name)
        if tg:
            lines.append(f"Group: {tg.name} — {tg.subtitle}")
        else:
            lines.append(f"Group: {sig.group_name}")

        # Collect unique tag names from all quotes in this signal
        all_tag_names: set[str] = set()
        for q in sig.quotes:
            all_tag_names.update(q.tag_names)

        # Include tag definitions for referenced tags
        if tg and all_tag_names:
            tag_lookup = {t.name: t for t in tg.tags}
            tag_lines: list[str] = []
            for tn in sorted(all_tag_names):
                tt = tag_lookup.get(tn)
                if tt:
                    tag_lines.append(_format_tag(tt))
                else:
                    tag_lines.append(f"**{tn}**")
            lines.append("")
            lines.append("Tags in this signal:")
            for tl in tag_lines:
                lines.append(tl)

        # Include quotes
        lines.append("")
        lines.append("Quotes:")
        for q in sig.quotes:
            tags_str = ", ".join(q.tag_names) if q.tag_names else ""
            tag_suffix = f" [tag: {tags_str}]" if tags_str else ""
            lines.append(f"- [{q.participant_id}] \"{q.text}\"{tag_suffix}")

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _load_cached(
    db: SASession,
    project_id: int,
    key_hash_pairs: list[tuple[str, str]],
) -> dict[str, ElaborationResult]:
    """Load cached elaborations that match their content hash."""
    from bristlenose.server.models import ElaborationCache

    if not key_hash_pairs:
        return {}

    keys = [k for k, _ in key_hash_pairs]
    hash_by_key = dict(key_hash_pairs)

    rows = (
        db.query(ElaborationCache)
        .filter(
            ElaborationCache.project_id == project_id,
            ElaborationCache.signal_key.in_(keys),
        )
        .all()
    )

    results: dict[str, ElaborationResult] = {}
    for row in rows:
        if row.content_hash == hash_by_key.get(row.signal_key):
            results[row.signal_key] = ElaborationResult(
                signal_name=row.signal_name,
                pattern=row.pattern,
                elaboration=row.elaboration,
            )
    return results


def _save_cached(
    db: SASession,
    project_id: int,
    entries: list[tuple[str, str, ElaborationResult]],
) -> None:
    """Upsert elaboration cache entries.

    Each entry is (signal_key, content_hash, ElaborationResult).
    """
    from bristlenose.server.models import ElaborationCache

    for signal_key, content_hash, result in entries:
        # Delete stale row if present
        db.query(ElaborationCache).filter(
            ElaborationCache.project_id == project_id,
            ElaborationCache.signal_key == signal_key,
        ).delete()

        db.add(ElaborationCache(
            project_id=project_id,
            signal_key=signal_key,
            content_hash=content_hash,
            signal_name=result.signal_name,
            pattern=result.pattern,
            elaboration=result.elaboration,
        ))

    db.commit()


# ---------------------------------------------------------------------------
# Pattern validation
# ---------------------------------------------------------------------------


def _normalise_pattern(raw: str) -> str:
    """Normalise a pattern string, defaulting to 'tension' for unknowns."""
    normalised = raw.strip().lower()
    if normalised in VALID_PATTERNS:
        return normalised
    logger.warning("Unknown elaboration pattern %r, defaulting to 'tension'", raw)
    return "tension"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def generate_elaborations(
    signals: list[TagSignal],
    codebook_id: str,
    settings: BristlenoseSettings,
    db: SASession,
    project_id: int,
) -> dict[str, ElaborationResult]:
    """Generate elaborations for signal cards, with caching.

    Returns a dict of signal_key -> ElaborationResult.  Cached results are
    returned immediately; uncached signals get an LLM call.  On LLM failure,
    only cached results are returned (graceful degradation).
    """
    if not signals:
        return {}

    # Guard: skip local providers (context too small for taxonomy)
    if settings.llm_provider == "local":
        logger.warning("Signal elaboration skipped: local provider not supported")
        return {}

    # Guard: skip if no API key
    if not _has_api_key(settings):
        logger.warning("Signal elaboration skipped: no API key for %s", settings.llm_provider)
        return {}

    # Load codebook template for tag definitions
    from bristlenose.server.codebook import get_template

    template = get_template(codebook_id)
    if not template:
        logger.warning("Signal elaboration skipped: template %r not found", codebook_id)
        return {}

    # Compute keys and hashes
    key_hash_pairs: list[tuple[str, str]] = []
    signal_by_key: dict[str, TagSignal] = {}
    for sig in signals:
        key = compute_signal_key(sig.source_type, sig.location, sig.group_name)
        quote_texts = [q.text for q in sig.quotes]
        tag_names: list[str] = []
        for q in sig.quotes:
            tag_names.extend(q.tag_names)
        h = compute_content_hash(quote_texts, tag_names)
        key_hash_pairs.append((key, h))
        signal_by_key[key] = sig

    # Check cache
    cached = _load_cached(db, project_id, key_hash_pairs)

    # Determine which signals need generation
    uncached_signals: list[TagSignal] = []
    uncached_keys: list[str] = []
    uncached_hashes: list[str] = []
    for key, h in key_hash_pairs:
        if key not in cached:
            uncached_signals.append(signal_by_key[key])
            uncached_keys.append(key)
            uncached_hashes.append(h)

    if not uncached_signals:
        return cached

    # Generate via LLM
    try:
        from bristlenose.llm.client import LLMClient
        from bristlenose.llm.prompts import get_prompt
        from bristlenose.llm.structured import SignalElaborationResult

        prompt_pair = get_prompt("signal-elaboration")
        signals_text = format_signals_for_prompt(uncached_signals, template)
        user_prompt = prompt_pair.user.format(signals_text=signals_text)

        client = LLMClient(settings)
        result = await client.analyze(
            prompt_pair.system,
            user_prompt,
            SignalElaborationResult,
        )

        # Process results
        new_entries: list[tuple[str, str, ElaborationResult]] = []
        for item in result.elaborations:
            if item.signal_index < 0 or item.signal_index >= len(uncached_signals):
                logger.warning(
                    "Elaboration signal_index %d out of range (0-%d), skipping",
                    item.signal_index, len(uncached_signals) - 1,
                )
                continue

            key = uncached_keys[item.signal_index]
            h = uncached_hashes[item.signal_index]
            elab = ElaborationResult(
                signal_name=item.signal_name,
                pattern=_normalise_pattern(item.pattern),
                elaboration=item.elaboration,
            )
            cached[key] = elab
            new_entries.append((key, h, elab))

        # Save to cache
        if new_entries:
            _save_cached(db, project_id, new_entries)

    except Exception:
        logger.exception("Signal elaboration LLM call failed, returning cached only")

    return cached


def _has_api_key(settings: BristlenoseSettings) -> bool:
    """Check if the configured LLM provider has an API key set."""
    provider = settings.llm_provider
    if provider == "anthropic":
        return bool(settings.anthropic_api_key)
    if provider == "openai":
        return bool(settings.openai_api_key)
    if provider == "azure":
        return bool(settings.azure_api_key)
    if provider == "google":
        return bool(settings.google_api_key)
    return False
