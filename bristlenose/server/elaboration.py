"""Signal elaboration service — LLM-generated interpretive names for signal cards.

Generates 2-4 word signal names, pattern classification (success/gap/tension/
recovery), and one-sentence findings for the top N framework signal cards.
Results are cached in SQLite keyed by a content hash — if quotes or tags
change the hash changes and a new elaboration is generated.

Public API::

    compute_signal_key(source_type, location, group_name) → str
    compute_content_hash(quote_texts, tag_names, quote_references) → str
    format_signals_for_prompt(signals, template)            → str
    generate_elaborations(signals, codebook_id, settings,
                          db, project_id)                   → dict
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session as SASession

    from bristlenose.config import BristlenoseSettings
    from bristlenose.server.codebook import CodebookTemplate
    from bristlenose.server.routes.signals import TagSignal

logger = logging.getLogger(__name__)

#: A safety valve on the prompt's payload, not a display rule.
#:
#: It replaced ``DEFAULT_TOP_N = 10``, which capped by COUNT — the wrong shape,
#: because quote length varies far more than card count does. MEASURED across
#: the trial corpus: one project carries 16.5 KB of evidence on five cards
#: while another carries 4.8 KB on twenty-nine, so ten cards can be a bigger
#: ask than thirty.
#:
#: 60 KB is roughly 15,000 tokens of evidence. The busiest real project in the
#: corpus uses 4,791 characters, so nothing real reaches this; it exists so a
#: pathological project cannot send a prompt that fails.
ELABORATION_BUDGET_CHARS = 60_000

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
    #: Validated reader records, retained with the cached narrative bundle.
    evidence_assertions: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Key / hash helpers
# ---------------------------------------------------------------------------


def _utcstamp() -> str:
    """The run-id timestamp, in autocode's shape so the two read alike."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def compute_signal_key(source_type: str, location: str, group_name: str) -> str:
    """Build a stable key for a signal card.

    Format: ``"section|Homepage|Discoverability"``
    """
    return f"{source_type}|{location}|{group_name}"


def compute_quote_reference(quote: object) -> str:
    """Return a durable quote reference for card/narrative provenance.

    Signal computation deliberately uses lightweight records rather than ORM
    rows, so a database primary key is not available on every path. This hash
    is stable for the quote's session, speaker, temporal/segment position and
    text, and changes when the quote itself changes. It is an evidence pointer
    inside an immutable snapshot, not a public database identifier.
    """
    payload = "\x1f".join((
        str(getattr(quote, "participant_id", "")),
        str(getattr(quote, "session_id", "")),
        f"{float(getattr(quote, 'start_seconds', 0.0)):.6f}",
        str(getattr(quote, "segment_index", -1)),
        str(getattr(quote, "ordinal", 0)),
        str(getattr(quote, "text", "")),
    ))
    return f"q_{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def compute_content_hash(
    quote_texts: list[str],
    tag_names: list[str],
    quote_references: list[str] | None = None,
) -> str:
    """A SHA-256 over everything that decides what the elaboration should say.

    Changes when quotes are added or removed, when their identity changes, when
    tags change — **and when the prompt changes**, which it did not until 20
    Sep 2026.  Quote references matter because an evidence assertion stores one
    as its provenance pointer; serving a cached pointer for a re-segmented or
    re-attributed quote would make an otherwise correct card untraceable.

    THE PROMPT IS PART OF THE CONTENT. Without it, rewriting an instruction
    invalidates nothing: every cached elaboration keeps the words it was given
    under the old one, forever, and the change applies only to cards generated
    afterwards. That is silent — no error, no stale marker, just two
    generations of prose sitting beside each other on the same page. It was
    found while planning exactly such a rewrite (Step 4, the headline rule),
    which would have applied to none of the 54 existing cards.

    The prompt's SHA rather than its declared `version`: a version is a number
    someone has to remember to change, and a rule nobody is obliged to check is
    indistinguishable from no rule. The cost is that a typo fix in the prompt
    regenerates the cache — one batched call, taken deliberately.
    """
    from bristlenose.llm.prompts import get_prompt_template

    prompt_sha = get_prompt_template("signal-elaboration").sha
    content = (
        "\n".join(sorted(quote_texts))
        + "\n---\n"
        + "\n".join(sorted(tag_names))
        + "\n---quote-references---\n"
        + "\n".join(sorted(quote_references or []))
        + "\n---prompt---\n"
        + str(prompt_sha)
    )
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
            lines.append(
                f"- [quote_id: {compute_quote_reference(q)}] [{q.participant_id}] "
                f"\"{q.text}\"{tag_suffix}"
            )

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cached_assertion_is_readable(assertion: object) -> bool:
    """True when a cached assertion still has the shape the reader serves."""
    if not isinstance(assertion, dict):
        return False
    required_text = ("id", "text", "source_quote_id", "participant_id", "source_excerpt")
    if not all(isinstance(assertion.get(key), str) for key in required_text):
        return False
    if not isinstance(assertion.get("ordinal"), int):
        return False
    fragment = assertion.get("intervention_fragment")
    if fragment is None:
        return True
    return (
        isinstance(fragment, dict)
        and isinstance(fragment.get("start"), int)
        and isinstance(fragment.get("end"), int)
        and isinstance(fragment.get("text"), str)
        and isinstance(fragment.get("rationale"), str)
    )


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
            try:
                assertions = json.loads(row.evidence_assertions or "[]")
            except (TypeError, json.JSONDecodeError):
                logger.warning("Ignoring malformed cached evidence assertions for %s", row.signal_key)
                assertions = []
            if not isinstance(assertions, list):
                assertions = []
            # One bad element must not fail the whole project's elaboration:
            # keep the elements that still parse, drop the rest with a warning.
            kept = [a for a in assertions if _cached_assertion_is_readable(a)]
            if len(kept) != len(assertions):
                logger.warning(
                    "Dropped %d unreadable cached evidence assertion(s) for %s",
                    len(assertions) - len(kept), row.signal_key,
                )
            assertions = kept
            results[row.signal_key] = ElaborationResult(
                signal_name=row.signal_name,
                pattern=row.pattern,
                elaboration=row.elaboration,
                evidence_assertions=assertions,
            )
    return results


def load_cached_elaborations(
    db: SASession,
    project_id: int,
    signals: list[object],
) -> dict[str, ElaborationResult]:
    """Read-only cache lookup for computed signals — no LLM call, no writes.

    Accepts ``analysis.models.Signal`` objects (``Signal.sentiment`` carries
    the column label — group name or sentiment). Returns
    ``{signal_key: ElaborationResult}`` for cache hits whose content hash
    still matches. A derivation mismatch against the generate path degrades
    to a cache miss, never a wrong hit. NB the signal key carries no lens
    component, so a sentiment-lens lookup shares a namespace with tags-lens
    rows for a group named like a sentiment — cross-lens wrong-hits are
    excluded by the CONTENT HASH (sentiment-lens hashes have an empty tag
    section; tags-lens rows never do). The hash check is load-bearing:
    never serve a key match without it. Consumers that must never spend
    tokens (the MCP server's ``get_signals``) call this instead of
    ``generate_elaborations``.
    """
    pairs: list[tuple[str, str]] = []
    for s in signals:
        quote_texts = [q.text for q in s.quotes]  # type: ignore[attr-defined]
        # Duplicates preserved — the generate path extends per-quote tag
        # lists without deduping, and compute_content_hash sorts but keeps
        # repeats. A set here would fork the hash for any repeated tag
        # (the normal shape of a tag signal) and kill every cache hit.
        tag_names = [
            t
            for q in s.quotes  # type: ignore[attr-defined]
            for t in (q.tag_names or [])
        ]
        quote_references = [compute_quote_reference(q) for q in s.quotes]  # type: ignore[attr-defined]
        pairs.append((
            compute_signal_key(s.source_type, s.location, s.sentiment),  # type: ignore[attr-defined]
            compute_content_hash(quote_texts, tag_names, quote_references),
        ))
    return _load_cached(db, project_id, pairs)


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
            evidence_assertions=json.dumps(
                result.evidence_assertions, ensure_ascii=False, separators=(",", ":"),
            ),
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


_EVIDENCE_RATIONALES = frozenset({
    "negative_actionable_cause",
    "positive_enabling_cause",
})
_GENERIC_FRAGMENT_WORDS = frozenset({
    "frustrated", "frustration", "confused", "confusion", "delighted",
    "delight", "satisfied", "satisfaction", "surprised", "surprise",
    "doubt", "uncertain", "uncertainty",
})


def _normalise_evidence_text(value: str) -> str:
    """Normalise transcript whitespace/case without changing source meaning."""
    return " ".join(value.split()).casefold()


_MAX_EVIDENCE_ASSERTIONS = 4


def _utf16_offset(text: str, index: int) -> int:
    """Convert a code-point index into UTF-16 code units, which the SPA slices by."""
    return len(text[:index].encode("utf-16-le")) // 2


def _validated_fragment(fragment: object, text: str) -> dict[str, Any] | None:
    """The highlight for ``text``, or None when it fails the intervention contract.

    The model is poor at counting characters, so its offsets are a hint: when
    they do not select the fragment text, the fragment is located by its text
    instead, provided that match is unique. The offsets returned are UTF-16
    code units, because the SPA slices the assertion text in JavaScript.
    """
    start = getattr(fragment, "start", -1)
    end = getattr(fragment, "end", -1)
    fragment_text = str(getattr(fragment, "text", ""))
    rationale = str(getattr(fragment, "rationale", ""))
    if (
        not fragment_text
        or _normalise_evidence_text(fragment_text) in _GENERIC_FRAGMENT_WORDS
        or rationale not in _EVIDENCE_RATIONALES
    ):
        return None
    offsets_ok = (
        isinstance(start, int) and isinstance(end, int)
        and 0 <= start < end <= len(text)
        and text[start:end] == fragment_text
    )
    if not offsets_ok:
        if text.count(fragment_text) != 1:
            return None
        start = text.index(fragment_text)
        end = start + len(fragment_text)
    return {
        "start": _utf16_offset(text, start),
        "end": _utf16_offset(text, end),
        "text": fragment_text,
        "rationale": rationale,
    }


def _validated_evidence_assertions(
    candidates: list[object],
    signal: TagSignal,
) -> list[dict[str, Any]]:
    """Return only attributable, structurally valid assertion records.

    The LLM can judge whether a paraphrase is entailed; this local gate proves
    its source pointer, participant and highlight range before a snapshot can
    claim that relationship. Invalid candidate assertions are intentionally
    dropped individually: a good title/claim must not disappear because one
    decorative assertion was malformed.
    """
    by_ref = {compute_quote_reference(quote): quote for quote in signal.quotes}
    seen_quote_refs: set[str] = set()
    accepted: list[dict[str, Any]] = []

    dropped: dict[str, int] = {}

    def _drop(reason: str) -> None:
        dropped[reason] = dropped.get(reason, 0) + 1

    for candidate in candidates:
        if len(accepted) >= _MAX_EVIDENCE_ASSERTIONS:
            break
        source_quote_id = str(getattr(candidate, "source_quote_id", ""))
        quote = by_ref.get(source_quote_id)
        text = str(getattr(candidate, "text", "")).strip()
        if not quote:
            _drop("unknown_quote")
            continue
        if source_quote_id in seen_quote_refs:
            _drop("duplicate_quote")
            continue
        if not text:
            _drop("empty_text")
            continue

        # ``source_quote_id`` is the supplied, stable provenance pointer.  The
        # model used to be asked to copy a second, exact source substring as
        # well; it frequently made harmless punctuation/cleanup changes and
        # we then discarded an otherwise useful cited assertion.  Preserve a
        # truthful reader record by deriving the excerpt from the canonical
        # quote instead of trusting a second LLM transcription.
        excerpt = quote.text

        fragment = getattr(candidate, "intervention_fragment", None)
        fragment_payload: dict[str, Any] | None = None
        if fragment is not None:
            fragment_payload = _validated_fragment(fragment, text)
            if fragment_payload is None:
                # An assertion can still be useful when the model's proposed
                # highlighter fails the stricter intervention contract.
                _drop("fragment")

        accepted.append({
            "id": f"ea_{source_quote_id.removeprefix('q_')}",
            "ordinal": len(accepted),
            "text": text,
            "source_quote_id": source_quote_id,
            "participant_id": quote.participant_id,
            "source_excerpt": excerpt,
            "intervention_fragment": fragment_payload,
        })
        seen_quote_refs.add(source_quote_id)

    if dropped:
        logger.info(
            "Evidence assertions for %s: kept %d of %d candidates; dropped %s",
            getattr(signal, "location", "?"), len(accepted), len(candidates),
            ", ".join(f"{reason}={count}" for reason, count in sorted(dropped.items())),
        )
    return accepted


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def generate_elaborations(
    signals: list[TagSignal],
    codebook_id: str,
    settings: BristlenoseSettings,
    db: SASession,
    project_id: int,
    project_dir: Path | None = None,
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
        h = compute_content_hash(
            quote_texts,
            tag_names,
            [compute_quote_reference(q) for q in sig.quotes],
        )
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
        from bristlenose.llm import telemetry
        from bristlenose.llm.boundary import wrap_untrusted
        from bristlenose.llm.client import LLMClient
        from bristlenose.llm.prompts import get_prompt_template
        from bristlenose.llm.structured import SignalElaborationResult

        prompt_tmpl = get_prompt_template("signal-elaboration")
        signals_text = format_signals_for_prompt(uncached_signals, template)
        user_prompt = prompt_tmpl.user.format(signals_text=wrap_untrusted("signals", signals_text))

        client = LLMClient(settings)
        # Both halves are needed and only one was here. `stage(...)` LABELS the
        # row; `serve_run_context(...)` decides whether there is a file to write
        # it to. Without the second, `record_call` finds no `_run_dir`, logs at
        # DEBUG and returns — so every elaboration call this project ever made
        # is absent from llm-calls.jsonl, with nothing anywhere saying so. Found
        # by looking for the spend and finding 260 rows, none of them these.
        run_id = f"elaboration-{project_id}-{codebook_id}-{_utcstamp()}"
        with telemetry.serve_run_context(project_dir, run_id), telemetry.stage(
            "serve_signal_elaboration"
        ):
            result = await client.analyze(
                system_prompt=prompt_tmpl.system,
                user_prompt=user_prompt,
                response_model=SignalElaborationResult,
                prompt_template=prompt_tmpl,
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
                evidence_assertions=_validated_evidence_assertions(
                    item.evidence_assertions,
                    uncached_signals[item.signal_index],
                ),
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
    if provider == "anyllm":
        # The inner provider's key, the model and the add-on: any-llm's
        # readiness answers all three, offline (docs/design-any-llm.md).
        from bristlenose.llm import anyllm

        return anyllm.readiness(settings).ready
    return False
