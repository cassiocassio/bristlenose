"""Dynamic codebook builder — synthesise and refine a tag's own prompt.

Where ``autocode.py`` *applies* a fixed framework's discrimination prompts to
every quote, this module *builds* those prompts for the researcher's own tags,
from the quotes they coded by hand, and *refines* them from accept/reject
review. It is the engine behind turning a manual tag (a name) into a cultivated
code (a framework entry with operational boundaries).

Two entry points, covering the researcher's loop:

    synthesize_prompt(...)  → infer definition / apply_when / not_this from the
                              quotes already coded with the tag. Passing
                              ``current`` + accept/reject feedback turns the *same*
                              call into a refinement pass (fold judgements back in
                              so the next pass is sharper — one template handles both)
    find_candidates(...)    → score uncoded quotes against that prompt, ranked

The pure formatting / ranking / hashing helpers carry no LLM dependency and are
unit-tested directly; the three ``async`` functions orchestrate the LLM calls.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bristlenose.config import BristlenoseSettings

logger = logging.getLogger(__name__)

#: Quotes per LLM call when scanning for candidates. Matches the AutoCode
#: batch size so token budgets stay predictable.
CANDIDATE_BATCH_SIZE = 25

#: A tag needs at least this many hand-coded exemplars before synthesis is
#: meaningful — fewer than this and the inferred boundary is noise.
MIN_EXAMPLES_FOR_SYNTHESIS = 3


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExampleQuote:
    """A quote already coded with the tag — a positive exemplar to learn from."""

    text: str
    session_id: str = ""
    participant_id: str = ""
    topic_label: str = ""
    sentiment: str = ""


@dataclass(frozen=True)
class CandidateQuote:
    """An uncoded quote to be scored against a tag's prompt."""

    db_id: int
    text: str
    session_id: str = ""
    participant_id: str = ""
    topic_label: str = ""
    sentiment: str = ""


@dataclass(frozen=True)
class DecisionFeedback:
    """One reviewed candidate: was it a good match, and why (in the human's words)."""

    text: str
    reason: str = ""


@dataclass(frozen=True)
class PromptDraft:
    """A synthesised inclusion/exclusion prompt for a tag."""

    summary: str = ""
    definition: str = ""
    apply_when: str = ""
    not_this: str = ""

    @property
    def version(self) -> str:
        """Content hash of the prompt text — the row stored against decisions."""
        return prompt_version(self.definition, self.apply_when, self.not_this)


@dataclass
class Candidate:
    """A scored candidate match, ready for researcher review."""

    db_id: int
    text: str
    confidence: float
    rationale: str
    session_id: str = ""
    participant_id: str = ""


@dataclass
class CandidateScan:
    """Result of scanning a quote pool for a tag's prompt."""

    candidates: list[Candidate] = field(default_factory=list)
    scanned: int = 0
    errors: int = 0


# ---------------------------------------------------------------------------
# Pure helpers (no LLM) — directly unit-tested
# ---------------------------------------------------------------------------


def prompt_version(definition: str, apply_when: str, not_this: str) -> str:
    """Return the sha256[:8] content hash of a prompt's discrimination text.

    Mirrors the rejection-telemetry methodology's version derivation
    (``docs/methodology/tag-rejections-are-great.md``): the version is a
    content hash so it can never drift from the wording it describes. Decisions
    record this hash, so a later edit to the prompt is visible as a new version.
    """
    joined = "\n".join((definition.strip(), apply_when.strip(), not_this.strip()))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:8]


def _format_quote_line(index: int, text: str, session_id: str,
                       participant_id: str, topic_label: str,
                       sentiment: str) -> str:
    """Format one numbered quote line, mirroring autocode.build_quote_batch."""
    parts = [f"{index}."]
    sp = "/".join(p for p in (session_id, participant_id) if p)
    if sp:
        parts.append(f"[{sp}]")
    if topic_label:
        parts.append(f"[{topic_label}]")
    if sentiment:
        parts.append(f"[{sentiment}]")
    parts.append(f'"{text}"')
    return " ".join(parts)


def build_example_block(examples: list[ExampleQuote]) -> str:
    """Format coded exemplars as numbered text for the synthesis prompt."""
    return "\n\n".join(
        _format_quote_line(
            i, q.text, q.session_id, q.participant_id, q.topic_label, q.sentiment
        )
        for i, q in enumerate(examples)
    )


def build_candidate_batch(quotes: list[CandidateQuote]) -> str:
    """Format a batch of candidate quotes as numbered text for scoring."""
    return "\n\n".join(
        _format_quote_line(
            i, q.text, q.session_id, q.participant_id, q.topic_label, q.sentiment
        )
        for i, q in enumerate(quotes)
    )


def format_tag_prompt(draft: PromptDraft) -> str:
    """Render a prompt draft as the discrimination text shown to the LLM.

    Same shape autocode uses per tag (definition, "Apply when:", "Not this:"),
    so the candidate-scoring model reads boundaries in a familiar layout.
    """
    lines: list[str] = []
    if draft.definition:
        lines.append(f"**Definition:** {draft.definition}")
    if draft.apply_when:
        lines.append(f"**Apply when:** {draft.apply_when}")
    if draft.not_this:
        lines.append(f"**Not this:** {draft.not_this}")
    if not lines:
        lines.append("(No discrimination criteria yet.)")
    return "\n".join(lines)


def build_current_prompt_block(draft: PromptDraft | None) -> str:
    """Render the existing prompt for a refinement pass, or '' for initial synth."""
    if draft is None:
        return ""
    return (
        "## Current prompt (to be corrected)\n\n"
        + format_tag_prompt(draft)
    )


def rank_candidates(
    verdicts: list[tuple[int, bool, float, str]],
    quotes: list[CandidateQuote],
    *,
    min_confidence: float = 0.0,
) -> list[Candidate]:
    """Turn per-quote verdicts into ranked ``Candidate`` rows.

    ``verdicts`` is ``(quote_index, matches, confidence, rationale)`` as returned
    by the LLM. Only positive matches at or above ``min_confidence`` are kept;
    out-of-range indices are dropped. Sorted by confidence descending.
    """
    out: list[Candidate] = []
    for quote_index, matches, confidence, rationale in verdicts:
        if not matches:
            continue
        if confidence < min_confidence:
            continue
        if quote_index < 0 or quote_index >= len(quotes):
            logger.warning("Candidate verdict has out-of-range index %d", quote_index)
            continue
        q = quotes[quote_index]
        out.append(
            Candidate(
                db_id=q.db_id,
                text=q.text,
                confidence=confidence,
                rationale=rationale,
                session_id=q.session_id,
                participant_id=q.participant_id,
            )
        )
    out.sort(key=lambda c: c.confidence, reverse=True)
    return out


def _chunk(items: list[CandidateQuote], size: int) -> list[list[CandidateQuote]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


# ---------------------------------------------------------------------------
# LLM orchestration
# ---------------------------------------------------------------------------


def _draft_from_result(result: object) -> PromptDraft:
    """Build a PromptDraft from a SynthesizedTagPrompt LLM result."""
    return PromptDraft(
        summary=getattr(result, "summary", "").strip(),
        definition=getattr(result, "definition", "").strip(),
        apply_when=getattr(result, "apply_when", "").strip(),
        not_this=getattr(result, "not_this", "").strip(),
    )


async def synthesize_prompt(
    tag_name: str,
    examples: list[ExampleQuote],
    settings: BristlenoseSettings,
    *,
    current: PromptDraft | None = None,
    accepted: list[DecisionFeedback] | None = None,
    rejected: list[DecisionFeedback] | None = None,
) -> PromptDraft:
    """Infer (or refine) a tag's inclusion/exclusion prompt via one LLM call.

    With only ``examples`` this is initial synthesis. Passing ``current`` plus
    ``accepted`` / ``rejected`` feedback turns it into a refinement pass — the
    same prompt template handles both, so the boundary the researcher taught by
    accepting and rejecting candidates folds straight back into the wording.
    """
    from bristlenose.llm import telemetry
    from bristlenose.llm.boundary import wrap_untrusted
    from bristlenose.llm.client import LLMClient
    from bristlenose.llm.prompts import get_prompt_template
    from bristlenose.llm.structured import SynthesizedTagPrompt

    feedback_block = _build_feedback_block(accepted or [], rejected or [])
    current_block = build_current_prompt_block(current)

    prompt_tmpl = get_prompt_template("codebook-synthesize")
    user_prompt = prompt_tmpl.user.format(
        tag_name=tag_name,
        example_block=wrap_untrusted("examples", build_example_block(examples)),
        current_prompt_block=current_block,
        feedback_block=feedback_block,
    )
    llm_client = LLMClient(settings)
    with telemetry.stage("serve_codebook_synthesize"):
        result = await llm_client.analyze(
            system_prompt=prompt_tmpl.system,
            user_prompt=user_prompt,
            response_model=SynthesizedTagPrompt,
            prompt_template=prompt_tmpl,
        )
    return _draft_from_result(result)


def _build_feedback_block(
    accepted: list[DecisionFeedback], rejected: list[DecisionFeedback]
) -> str:
    """Render reviewer accept/reject judgements (with reasons) for the refine pass."""
    if not accepted and not rejected:
        return ""
    from bristlenose.llm.boundary import wrap_untrusted

    parts: list[str] = ["## Reviewer feedback"]
    if accepted:
        lines = []
        for i, d in enumerate(accepted):
            tail = f" — why it fits: {d.reason}" if d.reason else ""
            lines.append(f"{i}. \"{d.text}\"{tail}")
        parts.append(
            "Accepted — these ARE good matches; keep matching them:\n"
            + wrap_untrusted("examples", "\n".join(lines))
        )
    if rejected:
        lines = []
        for i, d in enumerate(rejected):
            tail = f" — why it does NOT fit: {d.reason}" if d.reason else ""
            lines.append(f"{i}. \"{d.text}\"{tail}")
        parts.append(
            "Rejected — these are NOT this tag; exclude them and tighten the boundary:\n"
            + wrap_untrusted("examples", "\n".join(lines))
        )
    return "\n\n".join(parts)


async def find_candidates(
    tag_name: str,
    draft: PromptDraft,
    quotes: list[CandidateQuote],
    settings: BristlenoseSettings,
    *,
    min_confidence: float = 0.0,
) -> CandidateScan:
    """Score a pool of uncoded quotes against a tag's prompt, ranked by fit.

    Batches the quotes, runs one LLM call per batch with bounded concurrency,
    and returns the positive matches sorted by confidence. Per-batch errors are
    counted, not fatal — a partial scan still returns its good batches.
    """
    from bristlenose.llm import telemetry
    from bristlenose.llm.boundary import wrap_untrusted
    from bristlenose.llm.client import LLMClient
    from bristlenose.llm.prompts import get_prompt_template
    from bristlenose.llm.structured import CandidateMatchResult

    if not quotes:
        return CandidateScan()

    prompt_tmpl = get_prompt_template("codebook-candidates")
    tag_prompt_text = format_tag_prompt(draft)
    llm_client = LLMClient(settings)
    batches = _chunk(quotes, CANDIDATE_BATCH_SIZE)
    semaphore = asyncio.Semaphore(settings.llm_concurrency)

    async def _score(batch: list[CandidateQuote]) -> list[Candidate]:
        async with semaphore:
            user_prompt = prompt_tmpl.user.format(
                tag_name=tag_name,
                tag_prompt=tag_prompt_text,
                formatted_quotes=wrap_untrusted("quotes", build_candidate_batch(batch)),
            )
            with telemetry.stage("serve_codebook_candidates"):
                result = await llm_client.analyze(
                    system_prompt=prompt_tmpl.system,
                    user_prompt=user_prompt,
                    response_model=CandidateMatchResult,
                    prompt_template=prompt_tmpl,
                )
            verdicts = [
                (m.quote_index, m.matches, m.confidence, m.rationale)
                for m in result.matches
            ]
            return rank_candidates(verdicts, batch, min_confidence=min_confidence)

    results = await asyncio.gather(
        *(_score(b) for b in batches), return_exceptions=True
    )

    scan = CandidateScan(scanned=len(quotes))
    for r in results:
        if isinstance(r, BaseException):
            logger.error("Candidate batch failed: %s", r)
            scan.errors += 1
            continue
        scan.candidates.extend(r)
    scan.candidates.sort(key=lambda c: c.confidence, reverse=True)
    return scan
