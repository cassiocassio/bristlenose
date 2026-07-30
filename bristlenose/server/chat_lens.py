"""Chat lens service — a cited question box over one project's corpus.

Prototype per ``docs/design-chat-lens.md`` §6, templated on
``elaboration.py``: an LLM call from serve mode, provider-agnostic via
``LLMClient(settings)``, structured output through ``analyze(...,
response_model=ChatLensAnswer)``. No retrieval — the whole curated corpus
is context-stuffed (a few hundred quotes fit comfortably). No history, no
streaming, no cache: every ask is a live call metered on the researcher's
own key, and the response is only as good as its citations.

What makes the answer trustworthy is not the model — it is that every
returned quote id is validated against the corpus that was actually in
context (``grounding.resolve_quote_ids``), so an invented citation is
flagged instead of rendered as evidence.

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
    resolve_quote_ids,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession

    from bristlenose.config import BristlenoseSettings

logger = logging.getLogger(__name__)

#: Longest accepted question, in characters. A question is a question, not
#: a pasted document; the corpus is where the tokens belong.
MAX_QUESTION_CHARS = 2000


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ClaimResult:
    """One claim with its citations split into resolved and rejected."""

    text: str
    quotes: list[CorpusQuote] = field(default_factory=list)
    invalid_quote_ids: list[str] = field(default_factory=list)


@dataclass
class AskResult:
    """A validated answer plus the corpus and call metadata behind it."""

    claims: list[ClaimResult]
    unsupported: str
    corpus: CorpusContext
    provider: str
    model: str
    elapsed_ms: int
    prompt_version: str


# ---------------------------------------------------------------------------
# Entry point
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


async def ask_question(
    question: str,
    settings: BristlenoseSettings,
    db: SASession,
    project_id: int,
) -> AskResult:
    """Answer a researcher's question from the project corpus, cited.

    Raises ``ValueError`` for unusable input (empty/oversized question, no
    usable provider); LLM/provider failures propagate to the caller — the
    ask is the payload, so there is no graceful-degradation path here.
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
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    claims: list[ClaimResult] = []
    for claim in answer.claims:
        resolved, rejected = resolve_quote_ids(claim.quote_ids, corpus)
        if rejected:
            logger.warning(
                "chat_lens_invalid_citations | project=%s | claim=%r | rejected=%s",
                project_id,
                claim.text[:80],
                rejected,
            )
        claims.append(
            ClaimResult(text=claim.text, quotes=resolved, invalid_quote_ids=rejected)
        )

    return AskResult(
        claims=claims,
        unsupported=answer.unsupported.strip(),
        corpus=corpus,
        provider=settings.llm_provider,
        model=settings.llm_model,
        elapsed_ms=elapsed_ms,
        prompt_version=prompt_tmpl.version,
    )
