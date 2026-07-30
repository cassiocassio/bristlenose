"""Chat lens service — a cited question box over one project's corpus.

Prototype per ``docs/design-chat-lens.md`` §6 as corrected by §5a,
templated on ``elaboration.py``: an LLM call from serve mode,
provider-agnostic via ``LLMClient(settings)``, structured output through
``analyze(..., response_model=ChatLensAnswer)``. No retrieval — the whole
curated corpus is context-stuffed (a few hundred quotes fit comfortably).
No history, no streaming, no cache: every ask is a live call metered on
the researcher's own key.

Two mechanisms make the answer honest, and they are different jobs:

- **Citation resolution** (§5a Correction 2): the model cites
  server-constructed integer indices, so a fabricated citation is an
  out-of-range int caught by arithmetic (``grounding.resolve_quote_indices``).
- **The support check** (§5a Correction 1): existence is not support — a
  resolvable citation can still fail to carry its claim, and its apparent
  validity buys unearned trust. A second, batched, prompted-judge call
  marks each cited claim supported/unsupported. The verdicts *flag*, never
  gate: the best judges are ~75% accurate here, so a failed check renders
  as a warning, not a suppressed claim, and a failed judge call degrades
  to "unchecked" rather than sinking the answer.

Public API::

    ask_question(question, settings, db, project_id) → AskResult
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from bristlenose.server.grounding import (
    INVARIANTS,
    CorpusContext,
    CorpusQuote,
    assemble_corpus_context,
    resolve_quote_indices,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession

    from bristlenose.config import BristlenoseSettings
    from bristlenose.llm.client import LLMClient

logger = logging.getLogger(__name__)

#: Longest accepted question, in characters. A question is a question, not
#: a pasted document; the corpus is where the tokens belong.
MAX_QUESTION_CHARS = 2000

#: Support-check outcomes for one claim. Empty string = not applicable
#: (the claim resolved no citations, so there is nothing to judge).
SUPPORT_SUPPORTED = "supported"
SUPPORT_UNSUPPORTED = "unsupported"
SUPPORT_UNCHECKED = "unchecked"

#: The three-way abstention vocabulary (§5a: one empty-result message is
#: not enough — out of scope, in scope but no evidence, and evidence that
#: would not ground are different findings for the researcher).
ABSTAIN_REASONS = frozenset({"out_of_scope", "no_evidence", "ungroundable"})


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ClaimResult:
    """One claim with resolved citations, rejects, and a support verdict."""

    text: str
    quotes: list[CorpusQuote] = field(default_factory=list)
    invalid_citations: list[int] = field(default_factory=list)
    citation_exempt: bool = False
    support: str = ""


@dataclass
class AskResult:
    """A validated answer plus the corpus and call metadata behind it."""

    claims: list[ClaimResult]
    unsupported: str
    abstain_reason: str
    corpus: CorpusContext
    provider: str
    model: str
    elapsed_ms: int
    prompt_version: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def has_usable_provider(settings: BristlenoseSettings) -> tuple[bool, str]:
    """Check the configured provider can be called at all.

    Local (Ollama) needs no key — whether the corpus fits its context is
    exactly the kind of thing the lab exists to find out, so it is not
    blocked here.
    """
    provider = settings.llm_provider
    if provider == "local":
        return True, ""
    key_by_provider = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "azure": settings.azure_api_key,
        "google": settings.google_api_key,
    }
    if key_by_provider.get(provider):
        return True, ""
    return False, f"No API key configured for provider {provider!r}"


def _normalise_abstain_reason(raw: str, has_claims: bool) -> str:
    """Normalise the model's abstain reason against the allowed vocabulary.

    An answered question carries no reason. An empty answer always
    carries one — ``no_evidence`` is the fallback when the model omitted
    or invented the reason, so the empty state is never headline-less.
    """
    reason = raw.strip().lower()
    if reason in ABSTAIN_REASONS:
        return reason
    if reason:
        logger.warning("Unknown chat-lens abstain_reason %r, dropping", raw)
    return "" if has_claims else "no_evidence"


def format_claims_for_support_check(claims: list[ClaimResult]) -> str:
    """Format cited claims + their evidence for the judge prompt.

    Claim numbering matches the position in ``claims`` so verdicts map
    back directly; claims with no resolved citations are skipped (there
    is nothing to judge).
    """
    blocks: list[str] = []
    for i, claim in enumerate(claims):
        if not claim.quotes:
            continue
        lines = [f"### Claim {i}", claim.text, "Evidence:"]
        for quote in claim.quotes:
            lines.append(f'- [{quote.dom_id}] "{quote.text}"')
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


async def _run_support_check(
    claims: list[ClaimResult],
    client: LLMClient,
) -> None:
    """Judge each cited claim against its own evidence; flag, never gate.

    Mutates ``claims`` in place: cited claims get ``supported`` /
    ``unsupported`` from the judge, or ``unchecked`` when the judge call
    fails or skips them. Uncited claims keep ``support == ""`` (nothing
    to judge — the uncited state is its own, louder, flag).
    """
    judgeable = [c for c in claims if c.quotes]
    if not judgeable:
        return
    for claim in judgeable:
        claim.support = SUPPORT_UNCHECKED

    from bristlenose.llm import telemetry
    from bristlenose.llm.boundary import wrap_untrusted
    from bristlenose.llm.prompts import get_prompt_template
    from bristlenose.llm.structured import ChatLensSupportResult

    try:
        prompt_tmpl = get_prompt_template("chat-lens-support")
        claims_block = format_claims_for_support_check(claims)
        user_prompt = prompt_tmpl.user.format(
            claims_block=wrap_untrusted("claims", claims_block)
        )
        with telemetry.stage("serve_chat_lens_support"):
            result = await client.analyze(
                system_prompt=prompt_tmpl.system,
                user_prompt=user_prompt,
                response_model=ChatLensSupportResult,
                prompt_template=prompt_tmpl,
            )
    except Exception:
        # Flag-not-gate: a dead judge must not sink the answer. Claims
        # stay "unchecked", which the lab renders as exactly that.
        logger.exception("chat_lens_support_check_failed, claims left unchecked")
        return

    for verdict in result.verdicts:
        if verdict.claim_index < 0 or verdict.claim_index >= len(claims):
            logger.warning(
                "Support verdict claim_index %d out of range (0-%d), skipping",
                verdict.claim_index,
                len(claims) - 1,
            )
            continue
        claim = claims[verdict.claim_index]
        if not claim.quotes:
            continue  # nothing was sent for this claim; don't trust a verdict
        claim.support = (
            SUPPORT_SUPPORTED if verdict.supported else SUPPORT_UNSUPPORTED
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def ask_question(
    question: str,
    settings: BristlenoseSettings,
    db: SASession,
    project_id: int,
) -> AskResult:
    """Answer a researcher's question from the project corpus, cited.

    Raises ``ValueError`` for unusable input (empty/oversized question, no
    usable provider); answer-call failures propagate to the caller — the
    ask is the payload, so there is no graceful-degradation path for it.
    (The support check is the exception: it degrades to "unchecked".)
    """
    question = question.strip()
    if not question:
        raise ValueError("Question is empty")
    if len(question) > MAX_QUESTION_CHARS:
        raise ValueError(
            f"Question is too long ({len(question)} chars, max {MAX_QUESTION_CHARS})"
        )
    ok, reason = has_usable_provider(settings)
    if not ok:
        raise ValueError(reason)

    corpus = assemble_corpus_context(db, project_id)

    from bristlenose.llm import telemetry
    from bristlenose.llm.boundary import wrap_untrusted
    from bristlenose.llm.client import LLMClient
    from bristlenose.llm.prompts import get_prompt_template
    from bristlenose.llm.structured import ChatLensAnswer

    prompt_tmpl = get_prompt_template("chat-lens")
    user_prompt = prompt_tmpl.user.format(
        invariants="\n".join(f"- {statement}" for statement in INVARIANTS),
        corpus_text=wrap_untrusted("corpus", corpus.text),
        question=question,
    )

    client = LLMClient(settings)
    t0 = time.perf_counter()
    with telemetry.stage("serve_chat_lens"):
        answer = await client.analyze(
            system_prompt=prompt_tmpl.system,
            user_prompt=user_prompt,
            response_model=ChatLensAnswer,
            prompt_template=prompt_tmpl,
        )

    claims: list[ClaimResult] = []
    for claim in answer.claims:
        resolved, rejected = resolve_quote_indices(claim.quote_indices, corpus)
        if rejected:
            logger.warning(
                "chat_lens_invalid_citations | project=%s | claim=%r | rejected=%s",
                project_id,
                claim.text[:80],
                rejected,
            )
        claims.append(
            ClaimResult(
                text=claim.text,
                quotes=resolved,
                invalid_citations=rejected,
                citation_exempt=claim.citation_exempt,
            )
        )

    await _run_support_check(claims, client)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    return AskResult(
        claims=claims,
        unsupported=answer.unsupported.strip(),
        abstain_reason=_normalise_abstain_reason(
            answer.abstain_reason, has_claims=bool(claims)
        ),
        corpus=corpus,
        provider=settings.llm_provider,
        model=settings.llm_model,
        elapsed_ms=elapsed_ms,
        prompt_version=prompt_tmpl.version,
    )
