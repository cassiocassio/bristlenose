"""Pydantic models for structured LLM output parsing."""

from __future__ import annotations

import json
from typing import Any, cast

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Speaker identification (Stage 5b)
# ---------------------------------------------------------------------------


class SpeakerBoundary(BaseModel):
    """A speaker change boundary in a single-speaker transcript."""

    segment_index: int = Field(
        ge=0,
        description=(
            "0-based index of the transcript line where this speaker starts talking. "
            "The first boundary must have segment_index=0."
        ),
    )
    speaker_id: str = Field(
        description="Speaker identifier, e.g. 'Speaker A', 'Speaker B'"
    )
    person_name: str = Field(
        default="",
        description=(
            "The speaker's real name if mentioned in the transcript "
            "(e.g. 'my name is Brian', 'thank you Daniel'). "
            "Empty string if unknown."
        ),
    )


class SpeakerSplitAssignment(BaseModel):
    """LLM output for splitting a single-speaker transcript into multiple speakers."""

    speaker_count: int = Field(description="Number of distinct speakers detected")
    boundaries: list[SpeakerBoundary] = Field(
        description=(
            "Speaker change boundaries in chronological order. "
            "Each boundary means 'from this segment index onwards, this speaker is talking'. "
            "Must start with segment_index=0."
        )
    )


class SpeakerRoleItem(BaseModel):
    """A single speaker-to-role assignment with optional name extraction."""

    speaker_label: str = Field(
        description="The speaker label from the transcript (e.g. 'Speaker A', 'John Smith')"
    )
    role: str = Field(description="One of: researcher, participant, observer")
    reasoning: str = Field(description="Brief explanation for the assignment")
    person_name: str = Field(
        default="",
        description=(
            "The person's real name if mentioned in the transcript "
            "(e.g. from a self-introduction like 'Hi, I'm Sarah'). "
            "Empty string if unknown."
        ),
    )
    job_title: str = Field(
        default="",
        description=(
            "The person's job title or professional role if mentioned "
            "(e.g. 'product manager', 'UX designer'). "
            "Empty string if unknown."
        ),
    )


class SpeakerRoleAssignment(BaseModel):
    """LLM output for speaker role identification."""

    assignments: list[SpeakerRoleItem] = Field(description="Role assignment for each speaker")


# ---------------------------------------------------------------------------
# Topic segmentation (Stage 8)
# ---------------------------------------------------------------------------


class TopicBoundaryItem(BaseModel):
    """A single topic transition point."""

    timecode: str = Field(description="Timestamp where the transition occurs (HH:MM:SS)")
    topic_label: str = Field(description="Concise 3-8 word label for the new topic or screen")
    transition_type: str = Field(
        description="One of: screen_change, topic_shift, task_change, general_context"
    )
    confidence: float = Field(
        description="Confidence score 0.0-1.0",
        ge=0.0,
        le=1.0,
    )


class TopicSegmentationResult(BaseModel):
    """LLM output for topic segmentation of one transcript."""

    boundaries: list[TopicBoundaryItem] = Field(
        description="All topic/screen transitions found in the transcript, in chronological order"
    )


# ---------------------------------------------------------------------------
# Quote extraction (Stage 9)
# ---------------------------------------------------------------------------


class ExtractedQuoteItem(BaseModel):
    """A single extracted quote with editorial cleanup applied."""

    start_timecode: str = Field(description="Start timestamp of the quote (HH:MM:SS)")
    end_timecode: str = Field(description="End timestamp of the quote (HH:MM:SS)")
    text: str = Field(
        description=(
            "The verbatim quote text with editorial cleanup: "
            "filler words replaced with '...', "
            "gentle grammar fixes with [inserted words] in square brackets, "
            "preserving natural emotion and expression"
        )
    )
    verbatim_excerpt: str = Field(
        default="",
        description=(
            "The EXACT original substring from the transcript that this quote "
            "is based on, before any editorial cleanup. Copy-paste the "
            "participant's words verbatim — including filler words, grammar "
            "errors, and disfluencies. Must be a contiguous substring of the "
            "transcript text."
        ),
    )
    topic_label: str = Field(description="The topic/screen this quote relates to")
    quote_type: str = Field(description="One of: screen_specific, general_context")
    researcher_context: str | None = Field(
        default=None,
        description=(
            "Optional context from the researcher's question, "
            "e.g. 'When asked about the settings page'. "
            "Only include if the quote is unintelligible without it."
        ),
    )
    # New sentiment field (v0.7+)
    sentiment: str | None = Field(
        default=None,
        description=(
            "Single dominant sentiment: frustration, confusion, doubt, surprise, "
            "satisfaction, delight, confidence. Leave empty/null if purely descriptive."
        ),
    )
    intensity: int = Field(
        default=1,
        description="Sentiment intensity: 1 (mild), 2 (moderate), 3 (strong)",
        ge=1,
        le=3,
    )
    # Deprecated fields — kept for backward compatibility
    intent: str = Field(
        default="narration",
        description="DEPRECATED: use sentiment instead",
    )
    emotion: str = Field(
        default="neutral",
        description="DEPRECATED: use sentiment instead",
    )
    journey_stage: str = Field(
        default="other",
        description="DEPRECATED",
    )


class QuoteExtractionResult(BaseModel):
    """LLM output for quote extraction from one transcript."""

    quotes: list[ExtractedQuoteItem] = Field(
        description="All substantive verbatim quotes extracted from the participant's speech"
    )


# ---------------------------------------------------------------------------
# Quote clustering by screen (Stage 10)
# ---------------------------------------------------------------------------


class ScreenClusterItem(BaseModel):
    """A screen/task cluster with assigned quote indices."""

    screen_label: str = Field(description="Normalised label for this screen or task")
    description: str = Field(description="Brief 1-2 sentence description of this screen/task")
    display_order: int = Field(description="Order in the logical product flow (1-based)")
    quote_indices: list[int] = Field(
        description="Indices of quotes (0-based) that belong to this cluster"
    )


class ScreenClusteringResult(BaseModel):
    """LLM output for clustering screen-specific quotes."""

    clusters: list[ScreenClusterItem] = Field(
        description="Screen clusters ordered by logical product flow"
    )


# ---------------------------------------------------------------------------
# Thematic grouping (Stage 11)
# ---------------------------------------------------------------------------


class ThemeGroupItem(BaseModel):
    """A theme group with assigned quote indices."""

    theme_label: str = Field(description="Concise label for this theme")
    description: str = Field(description="Brief 1-2 sentence description of this theme")
    quote_indices: list[int] = Field(
        description="Indices of quotes (0-based) that belong to this theme. Each quote should appear in exactly one theme."
    )


class ThematicGroupingResult(BaseModel):
    """LLM output for thematic grouping of contextual quotes."""

    themes: list[ThemeGroupItem] = Field(
        description="Emergent themes identified across all contextual quotes"
    )


# ---------------------------------------------------------------------------
# AutoCode — codebook tag application (serve mode)
# ---------------------------------------------------------------------------


class AutoCodeTagAssignment(BaseModel):
    """A single tag assignment for one quote in an AutoCode batch."""

    quote_index: int = Field(description="0-based index of the quote in the batch")
    tag_name: str = Field(
        description=(
            "The codebook tag name that best matches this quote. "
            "Always return the single best-matching tag — use a low "
            "confidence score (0.1-0.3) when the match is weak."
        )
    )
    confidence: float = Field(
        description="Confidence score 0.0-1.0 for this assignment",
        ge=0.0,
        le=1.0,
    )
    rationale: str = Field(
        description=(
            "Brief 1-sentence explanation for why this tag was chosen, "
            "referencing specific words in the quote and explaining why "
            "adjacent tags were ruled out"
        )
    )


class AutoCodeBatchResult(BaseModel):
    """LLM output for a batch of quote-to-tag assignments."""

    assignments: list[AutoCodeTagAssignment] = Field(
        description="Tag assignment for each quote in the batch"
    )

    @field_validator("assignments", mode="before")
    @classmethod
    def _parse_stringified_json(cls, v: object) -> object:
        """Some LLM providers double-serialize nested arrays as JSON strings."""
        if isinstance(v, str):
            return json.loads(v)
        return v


# ---------------------------------------------------------------------------
# Signal elaboration (serve mode — analysis page)
# ---------------------------------------------------------------------------


class SignalElaborationItem(BaseModel):
    """One elaboration for a single signal card."""

    signal_index: int = Field(
        description="0-based index matching the input signal order"
    )
    signal_name: str = Field(
        description=(
            "2-4 word interpretive name for this signal. "
            "Use the group's analytical vocabulary, not raw quote words."
        )
    )
    pattern: str = Field(
        description="One of: success, gap, tension, recovery"
    )
    elaboration: str = Field(
        description=(
            "Exactly one sentence. Structure: assertion clause || evidence/nuance. "
            "The || delimiter separates the bold opening (a self-contained finding) "
            "from the regular continuation (supporting detail). "
            "Place || at the first natural punctuation break: em dash, comma "
            "before a dependent clause, or opening parenthetical."
        )
    )


class SignalElaborationResult(BaseModel):
    """LLM output for a batch of signal elaborations."""

    elaborations: list[SignalElaborationItem] = Field(
        description="One elaboration per input signal, in order"
    )

    @field_validator("elaborations", mode="before")
    @classmethod
    def _parse_stringified_json(cls, v: object) -> object:
        """Some LLM providers double-serialize nested arrays as JSON strings."""
        if isinstance(v, str):
            return json.loads(v)
        return v


# ---------------------------------------------------------------------------
# Dynamic codebook builder (serve mode — codebook cultivation loop)
# ---------------------------------------------------------------------------


class SynthesizedTagPrompt(BaseModel):
    """LLM output: an inclusion/exclusion prompt inferred from coded exemplars.

    Produced both for the initial synthesis (from the researcher's first few
    coded quotes) and for each refinement pass (folding in accept/reject
    judgements with their reasons).
    """

    summary: str = Field(
        description=(
            "One plain-language sentence naming the shared idea behind the "
            "exemplar quotes — what this code is really about. Researcher-facing."
        )
    )
    definition: str = Field(
        description=(
            "A one-to-two sentence definition of the concept this tag captures, "
            "written in the researcher's analytical vocabulary, not raw quote words."
        )
    )
    apply_when: str = Field(
        description=(
            "Inclusion criteria: when a quote SHOULD get this tag. Concrete and "
            "operational — the signals a reader can check a quote against."
        )
    )
    not_this: str = Field(
        description=(
            "Exclusion criteria: adjacent cases that look similar but should NOT "
            "get this tag, and why. Empty string only if no boundary is yet clear."
        )
    )


class CandidateMatch(BaseModel):
    """LLM verdict on whether one quote matches a single tag's prompt."""

    quote_index: int = Field(description="0-based index of the quote in the batch")
    matches: bool = Field(
        description="True if this quote satisfies the inclusion criteria and is not excluded"
    )
    confidence: float = Field(
        description="Confidence 0.0-1.0 that the quote belongs to this tag",
        ge=0.0,
        le=1.0,
    )
    rationale: str = Field(
        description=(
            "Brief 1-sentence reason, referencing specific words in the quote and "
            "the inclusion/exclusion criteria that decided the verdict"
        )
    )


class CandidateMatchResult(BaseModel):
    """LLM output: per-quote match verdicts for one tag's prompt over a batch."""

    matches: list[CandidateMatch] = Field(
        description="One verdict per quote in the batch, in order"
    )

    @field_validator("matches", mode="before")
    @classmethod
    def _parse_stringified_json(cls, v: object) -> object:
        """Some LLM providers double-serialize nested arrays as JSON strings."""
        if isinstance(v, str):
            return json.loads(v)
        return v


# ---------------------------------------------------------------------------
# Chat lens (serve mode — cited question box)
# ---------------------------------------------------------------------------


class ChatLensClaim(BaseModel):
    """One claim in a chat-lens answer, with its supporting citations.

    The model cites server-constructed integer indices, never quote-id
    strings (design-chat-lens.md §5a Correction 2) — the server maps
    indices back to stable quote ids, so the surface vocabulary stays
    ``claims[].text`` / ``claims[].quote_ids`` / ``unsupported`` (§7).
    """

    text: str = Field(
        description="One finding, stated plainly, standing on its own"
    )
    quote_indices: list[int] = Field(
        default_factory=list,
        description=(
            "The bracketed citation numbers of the quotes that directly "
            "support this claim, copied exactly from the corpus [n] "
            "markers. Cite only numbers that appear in the corpus."
        ),
    )
    citation_exempt: bool = Field(
        default=False,
        description=(
            "True only for connective framing or transition sentences that "
            "assert no finding of their own and so carry no citations. "
            "Any sentence that states something about the participants or "
            "the product is a finding and must cite."
        ),
    )

    @field_validator("quote_indices", mode="before")
    @classmethod
    def _parse_stringified_json(cls, v: object) -> object:
        """Some LLM providers double-serialize nested arrays as JSON strings."""
        if isinstance(v, str):
            return json.loads(v)
        return v


class ChatLensAnswer(BaseModel):
    """LLM output: a cited answer to a researcher's question about their study."""

    claims: list[ChatLensClaim] = Field(
        default_factory=list,
        description=(
            "The findings that answer the question, each cited to corpus "
            "citation numbers. Empty if the corpus does not answer the "
            "question."
        ),
    )
    unsupported: str = Field(
        default="",
        description=(
            "What the question asked that the corpus does not answer, stated "
            "plainly as a fact about the study's coverage. Empty string if "
            "the question is fully answered."
        ),
    )
    abstain_reason: str = Field(
        default="",
        description=(
            "Why the answer is empty or partial, when it is: 'out_of_scope' "
            "(the question is not about this study), 'no_evidence' (in "
            "scope, but no quotes address it), or 'ungroundable' (quotes "
            "seem related but do not actually support an answer). Empty "
            "when the question is answered."
        ),
    )

    @field_validator("claims", mode="before")
    @classmethod
    def _parse_stringified_json(cls, v: object) -> object:
        """Some LLM providers double-serialize nested arrays as JSON strings."""
        if isinstance(v, str):
            return json.loads(v)
        return v


class ChatLensSupportVerdict(BaseModel):
    """One support judgement: does the cited evidence entail the claim?"""

    claim_index: int = Field(
        description="0-based index matching the input claim order"
    )
    supported: bool = Field(
        description=(
            "True if the quoted evidence, on its own, supports the claim as "
            "stated; false if it does not (irrelevant, partial, or "
            "contradicting). Judge only from the quoted evidence."
        )
    )


class ChatLensSupportResult(BaseModel):
    """LLM output: per-claim support verdicts (sentence granularity)."""

    verdicts: list[ChatLensSupportVerdict] = Field(
        default_factory=list,
        description="One verdict per claim, in input order",
    )

    @field_validator("verdicts", mode="before")
    @classmethod
    def _parse_stringified_json(cls, v: object) -> object:
        """Some LLM providers double-serialize nested arrays as JSON strings."""
        if isinstance(v, str):
            return json.loads(v)
        return v


def openai_strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """A Pydantic JSON schema rewritten for OpenAI Structured Outputs.

    Structured Outputs constrains the model at decode time, so the response is
    *guaranteed* to match the schema. JSON mode — what this path used before —
    only guarantees valid JSON, and matches the schema roughly 80% of the time.
    The remaining 20% arrived here as a ``ValidationError`` that failed the run,
    because there is no repair step: ``model_validate`` is the first and only
    check.

    Strict mode imposes two rules Pydantic's output does not satisfy:

    1. **Every object needs ``additionalProperties: false``.**
    2. **Every property must appear in ``required``.** Pydantic omits any field
       that has a default, which is 17 fields across our models.

    Rule 2 has a wrinkle: forcing a defaulted field to be required means the
    model must emit *something*, and the honest something is ``null``. So those
    fields are also made nullable here, and :func:`drop_nulls` removes them
    again before validation, letting Pydantic apply the default it already has.
    That round trip is why the two functions belong together.

    Safe because a Pydantic field is absent from ``required`` **iff** it has a
    default — so a dropped null always resolves to that default, never to a
    missing value.
    """
    schema = model.model_json_schema()

    def rewrite(node: Any) -> Any:
        if isinstance(node, list):
            return [rewrite(v) for v in node]
        if not isinstance(node, dict):
            return node
        # `default` is not in the keyword subset Structured Outputs accepts, and
        # it is meaningless in a response schema anyway — the model is being
        # asked to emit a value, and defaults are applied here afterwards.
        out = {k: rewrite(v) for k, v in node.items() if k != "default"}
        if "properties" in out:
            props = out["properties"]
            was_required = set(out.get("required", []))
            for name, prop in props.items():
                if name in was_required:
                    continue
                # Defaulted field: strict mode wants it required, so give the
                # model a way to say "nothing here".
                if "anyOf" in prop:
                    if {"type": "null"} not in prop["anyOf"]:
                        prop["anyOf"] = [*prop["anyOf"], {"type": "null"}]
                elif "type" in prop:
                    prop["anyOf"] = [{"type": prop.pop("type")}, {"type": "null"}]
                    for key in ("items", "enum"):
                        if key in prop:
                            prop["anyOf"][0][key] = prop.pop(key)
            out["required"] = list(props)
            out["additionalProperties"] = False
        return out

    # `rewrite` is recursive over arbitrary JSON, so it is typed Any; the
    # top level of a Pydantic schema is always an object.
    return cast("dict[str, Any]", rewrite(schema))


def drop_nulls(data: Any) -> Any:
    """Strip ``null`` values so Pydantic applies its own defaults.

    Companion to :func:`openai_strict_schema` — see its docstring for why the
    nulls are there in the first place.
    """
    if isinstance(data, list):
        return [drop_nulls(v) for v in data]
    if isinstance(data, dict):
        return {k: drop_nulls(v) for k, v in data.items() if v is not None}
    return data


# ---------------------------------------------------------------------------
# Malformed-payload repair — for providers with no decode-time enforcement
# ---------------------------------------------------------------------------


def _as_json(value: Any) -> Any:
    """``json.loads`` a string that looks like JSON; otherwise return it unchanged."""
    if not isinstance(value, str):
        return value
    s = value.strip()
    if not s or s[0] not in "[{":
        return value
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return value


def repair_candidates(data: Any, model: type[BaseModel]) -> list[tuple[str, Any]]:
    """Plausible re-readings of a payload that failed ``model_validate``.

    Two shapes were observed on ``claude-sonnet-5`` at quote-clustering and
    thematic-grouping (see ``docs/design-llm-live-checking.md``): a field
    arriving as a **JSON string** carrying the whole result re-serialised, and a
    field arriving as a **dict** carrying the expected container inside it. Both
    are one level deep, so this looks exactly one level and no further.

    Every candidate is derived from ``model``'s own declared fields — this is not
    a general "make it parse" pass. A repair that guesses is a repair that hides
    the next genuine break, which is the whole reason it is confined to the
    providers where the API makes no shape guarantee at all.

    Returns ``(what_was_done, candidate)`` pairs, cheapest reading first. The
    caller validates each in turn; nothing here decides anything.
    """
    out: list[tuple[str, Any]] = []
    fields = set(model.model_fields)

    # 1. The whole payload came back re-serialised as one string.
    if isinstance(data, str):
        decoded = _as_json(data)
        if decoded is not data:
            out.append(("whole payload was a JSON string", decoded))
        return out

    if not isinstance(data, dict):
        return out

    # 1b. The whole result nested under a key the model does NOT declare.
    #
    # Measured on claude-sonnet-5 at quote-clustering, 5 Sep 2026: the tool input
    # came back as {"parameters": {"clusters": [...]}} -- the JSON-Schema keyword
    # for a tool's argument object, leaking into the argument object itself. The
    # recorded analysis had named only the str/dict field shapes, so the first
    # version of this repair could not touch it: it iterates the model's own
    # fields, and `parameters` is not one.
    #
    # The guard is structural rather than a list of wrapper names, so a different
    # vendor's leak (`arguments`, `input`, `properties`) is covered too -- but it
    # is narrow: exactly one key, not a field of the model, and an inner object
    # whose keys look like the model's. A wrapper carrying anything else is left
    # alone to fail.
    if len(data) == 1:
        key, inner = next(iter(data.items()))
        inner = _as_json(inner)
        if (
            key not in fields
            and isinstance(inner, dict)
            and fields & set(inner)
            and set(inner) <= fields
        ):
            out.append((f"the whole result was wrapped in a {key!r} envelope", inner))

    for name in model.model_fields:
        if name not in data:
            continue
        value = data[name]

        # 2. The field arrived as a JSON string.
        decoded = _as_json(value)
        if decoded is not value:
            out.append((f"field {name!r} was a JSON string", {**data, name: decoded}))

        # 3. The field arrived as a dict wrapping what was expected.
        if isinstance(decoded, dict):
            # 3a. ...the parent object, nested inside one of its own fields.
            if fields & set(decoded) and set(decoded) <= fields:
                out.append((f"the whole result was nested inside {name!r}", decoded))
            # 3b. ...a dict keyed by the field's own name.
            if name in decoded:
                out.append((f"field {name!r} was wrapped in a dict keyed {name!r}",
                            {**data, name: decoded[name]}))
            # 3c. ...a single-key dict whose value is the container.
            elif len(decoded) == 1:
                only = next(iter(decoded.values()))
                if isinstance(only, list):
                    out.append((f"field {name!r} was wrapped in a single-key dict",
                                {**data, name: only}))

    return out
