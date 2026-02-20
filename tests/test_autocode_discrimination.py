"""Evaluation harness for AutoCode prompt discrimination quality.

Two test layers:

1. **Structural tests** (CI-safe, no LLM calls): Verify the prompt text
   contains enough discriminating information — checks that ``not_this``
   fields mention confusable siblings, that all groups are present, and
   that the preamble's mutual-exclusivity instruction appears.

2. **Live LLM tests** (``@pytest.mark.slow``, skipped in CI): Actually
   send golden quotes to Claude and check accuracy.  Costs ~$0.01 per
   run.  Run manually with ``pytest -m slow``.

Golden dataset
--------------
Each entry is a quote a human UX researcher would tag with a specific
Garrett sub-tag, plus a plausible-wrong tag that the LLM might confuse
it with.  The ``not_this`` field on the correct tag should give the LLM
enough signal to discriminate.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from bristlenose.server.autocode import QuoteBatchItem, build_quote_batch, build_tag_taxonomy
from bristlenose.server.codebook import TemplateTag, get_template

# ---------------------------------------------------------------------------
# Golden dataset
# ---------------------------------------------------------------------------


@dataclass
class GoldenQuote:
    """A manually-tagged quote for evaluation."""

    text: str
    correct_tag: str
    correct_group: str
    plausible_wrong_tag: str
    plausible_wrong_group: str


GOLDEN_QUOTES: list[GoldenQuote] = [
    # --- Strategy ---
    GoldenQuote(
        text="I'm trying to find a fish that can live in my tank without a heater — that's why I'm here.",
        correct_tag="user need",
        correct_group="Strategy",
        plausible_wrong_tag="feature requirement",
        plausible_wrong_group="Scope",
    ),
    GoldenQuote(
        text="They obviously want me to sign up for the premium plan before I can see prices.",
        correct_tag="business objective",
        correct_group="Strategy",
        plausible_wrong_tag="scope creep",
        plausible_wrong_group="Scope",
    ),
    GoldenQuote(
        text="For me the test is whether I can find a compatible fish in under two minutes.",
        correct_tag="success metric",
        correct_group="Strategy",
        plausible_wrong_tag="user need",
        plausible_wrong_group="Strategy",
    ),
    GoldenQuote(
        text="Why would I use this instead of just asking in the forum? The forum is free and people know their stuff.",
        correct_tag="value proposition",
        correct_group="Strategy",
        plausible_wrong_tag="user need",
        plausible_wrong_group="Strategy",
    ),
    # --- Scope ---
    GoldenQuote(
        text="There's no way to compare two fish side by side — I have to keep going back and forth.",
        correct_tag="feature requirement",
        correct_group="Scope",
        plausible_wrong_tag="navigation pattern",
        plausible_wrong_group="Structure",
    ),
    GoldenQuote(
        text="They don't have any water parameters listed for any of the fish.",
        correct_tag="content requirement",
        correct_group="Scope",
        plausible_wrong_tag="feature requirement",
        plausible_wrong_group="Scope",
    ),
    GoldenQuote(
        text="The most important thing for me is the compatibility checker — everything else is nice to have.",
        correct_tag="priority",
        correct_group="Scope",
        plausible_wrong_tag="user need",
        plausible_wrong_group="Strategy",
    ),
    GoldenQuote(
        text="Why does a fish shop have a social media feed? I don't need this.",
        correct_tag="scope creep",
        correct_group="Scope",
        plausible_wrong_tag="business objective",
        plausible_wrong_group="Strategy",
    ),
    # --- Structure ---
    GoldenQuote(
        text="When I click 'add to tank' I expected it to show me compatibility right away, but nothing happened.",
        correct_tag="interaction design",
        correct_group="Structure",
        plausible_wrong_tag="ambiguous feedback",
        plausible_wrong_group="Feedback",  # Norman — cross-framework test
    ),
    GoldenQuote(
        text="I would have expected angelfish to be under tropical freshwater, not just in a generic 'fish' category.",
        correct_tag="information architecture",
        correct_group="Structure",
        plausible_wrong_tag="navigation pattern",
        plausible_wrong_group="Structure",
    ),
    GoldenQuote(
        text="I keep having to go back to the home page to find anything — there's no way to jump between sections.",
        correct_tag="navigation pattern",
        correct_group="Structure",
        plausible_wrong_tag="information architecture",
        plausible_wrong_group="Structure",
    ),
    GoldenQuote(
        text="First I had to create an account, then verify my email, then set up a tank profile, and only then could I browse — that's way too many steps.",
        correct_tag="task flow",
        correct_group="Structure",
        plausible_wrong_tag="interaction design",
        plausible_wrong_group="Structure",
    ),
    # --- Skeleton ---
    GoldenQuote(
        text="This page feels really cramped — there's too much going on and I can't focus on anything.",
        correct_tag="interface layout",
        correct_group="Skeleton",
        plausible_wrong_tag="wireframe issue",
        plausible_wrong_group="Skeleton",
    ),
    GoldenQuote(
        text="The 'buy now' button is massive but the species information is tiny — seems backwards.",
        correct_tag="wireframe issue",
        correct_group="Skeleton",
        plausible_wrong_tag="interface layout",
        plausible_wrong_group="Skeleton",
    ),
    GoldenQuote(
        text="Usually on other sites there's a search bar at the top — I can't find one anywhere.",
        correct_tag="convention",
        correct_group="Skeleton",
        plausible_wrong_tag="component placement",
        plausible_wrong_group="Skeleton",
    ),
    GoldenQuote(
        text="The filter button is buried at the bottom of the page — it should be up here next to the search.",
        correct_tag="component placement",
        correct_group="Skeleton",
        plausible_wrong_tag="interface layout",
        plausible_wrong_group="Skeleton",
    ),
    # --- Surface ---
    GoldenQuote(
        text="The photos of the fish are gorgeous — really high quality, you can see all the colours.",
        correct_tag="visual design",
        correct_group="Surface",
        plausible_wrong_tag="aesthetic reaction",
        plausible_wrong_group="Surface",
    ),
    GoldenQuote(
        text="The whole site just feels really premium and modern — like a proper specialist retailer.",
        correct_tag="sensory experience",
        correct_group="Surface",
        plausible_wrong_tag="brand alignment",
        plausible_wrong_group="Surface",
    ),
    GoldenQuote(
        text="This doesn't look like a real fish shop — it looks more like some generic template site.",
        correct_tag="brand alignment",
        correct_group="Surface",
        plausible_wrong_tag="sensory experience",
        plausible_wrong_group="Surface",
    ),
    GoldenQuote(
        text="Ooh, that's nice. I like that.",
        correct_tag="aesthetic reaction",
        correct_group="Surface",
        plausible_wrong_tag="visual design",
        plausible_wrong_group="Surface",
    ),
]


# ---------------------------------------------------------------------------
# Structural tests (CI-safe, no LLM calls)
# ---------------------------------------------------------------------------


class TestPromptStructure:
    """Verify the prompt gives the LLM enough discrimination info."""

    def test_all_golden_tags_in_taxonomy(self) -> None:
        """Every golden-dataset tag appears in the formatted taxonomy."""
        template = get_template("garrett")
        assert template is not None
        taxonomy = build_tag_taxonomy(template)
        seen_tags = {gq.correct_tag for gq in GOLDEN_QUOTES}
        for tag_name in seen_tags:
            assert f"**{tag_name}**" in taxonomy, f"Missing golden tag: {tag_name}"

    def test_not_this_mentions_another_tag(self) -> None:
        """Tags with not_this mention at least one other tag in the codebook.

        The mentioned tag can be in the same group (within-group
        discrimination) or in a different group (cross-group
        discrimination).  Both are valid — some tags' primary confusion
        risk is cross-group (e.g. user need ↔ feature requirement).
        """
        template = get_template("garrett")
        assert template is not None
        # Collect all tag names in the codebook
        all_tag_names: list[str] = []
        tag_lookup: dict[str, TemplateTag] = {}
        for group in template.groups:
            for tag in group.tags:
                all_tag_names.append(tag.name)
                tag_lookup[tag.name] = tag

        missing = []
        for tag_name in all_tag_names:
            tag = tag_lookup[tag_name]
            if not tag.not_this:
                continue
            # Check that not_this mentions at least one other tag
            others = [t for t in all_tag_names if t != tag_name]
            not_this_lower = tag.not_this.lower()
            mentions_any = any(
                other in not_this_lower
                or any(word in not_this_lower for word in other.split() if len(word) > 3)
                for other in others
            )
            if not mentions_any:
                missing.append(
                    f"  {tag_name}: not_this doesn't mention any other tag"
                )
        assert not missing, (
            "Tags with not_this that don't mention any other tag:\n"
            + "\n".join(missing)
        )

    def test_preamble_has_exclusivity_instruction(self) -> None:
        """Garrett preamble instructs mutual exclusivity."""
        template = get_template("garrett")
        assert template is not None
        assert "mutually exclusive" in template.preamble.lower()

    def test_preamble_has_no_tag_guard(self) -> None:
        """Preamble instructs not to tag non-product quotes."""
        template = get_template("garrett")
        assert template is not None
        assert "do not apply any tag" in template.preamble.lower()

    def test_all_five_groups_present(self) -> None:
        """All five Garrett groups are in the taxonomy."""
        template = get_template("garrett")
        assert template is not None
        taxonomy = build_tag_taxonomy(template)
        for group_name in ("Strategy", "Scope", "Structure", "Skeleton", "Surface"):
            assert f"### {group_name}" in taxonomy

    def test_cross_group_discrimination(self) -> None:
        """Tags that cross groups mention the other group's concept."""
        template = get_template("garrett")
        assert template is not None
        tag_lookup = {}
        for group in template.groups:
            for tag in group.tags:
                tag_lookup[tag.name] = tag

        # "information architecture" (Structure) should mention
        # "navigation pattern" or "Skeleton" in its not_this
        ia_tag = tag_lookup["information architecture"]
        assert ia_tag.not_this
        assert (
            "navigation" in ia_tag.not_this.lower()
            or "skeleton" in ia_tag.not_this.lower()
        )

        # "component placement" (Skeleton) should mention "navigation"
        # or "Structure" in its not_this
        cp_tag = tag_lookup["component placement"]
        assert cp_tag.not_this
        assert (
            "navigation" in cp_tag.not_this.lower()
            or "structure" in cp_tag.not_this.lower()
        )

    def test_golden_quotes_cover_all_groups(self) -> None:
        """Golden dataset has quotes from all 5 Garrett groups."""
        groups = {gq.correct_group for gq in GOLDEN_QUOTES}
        assert groups == {"Strategy", "Scope", "Structure", "Skeleton", "Surface"}

    def test_golden_quotes_cover_all_tags(self) -> None:
        """Golden dataset covers all 20 Garrett sub-tags."""
        tags = {gq.correct_tag for gq in GOLDEN_QUOTES}
        assert len(tags) == 20

    def test_golden_quotes_batch_format(self) -> None:
        """Golden quotes can be formatted into a valid batch."""
        items = [
            QuoteBatchItem(
                db_id=i,
                text=gq.text,
                session_id="s1",
                participant_id="p1",
                topic_label="",
                sentiment="",
            )
            for i, gq in enumerate(GOLDEN_QUOTES)
        ]
        text = build_quote_batch(items)
        assert "0." in text
        assert f"{len(GOLDEN_QUOTES) - 1}." in text

    def test_taxonomy_token_estimate(self) -> None:
        """Garrett taxonomy is under 4,000 tokens (~4 chars/token heuristic).

        The 4-char heuristic overestimates (BPE tokens average ~4-5 chars
        for English prose).  Real token count from the API is ~2,400.
        This test guards against taxonomy bloat, not exact measurement.
        """
        template = get_template("garrett")
        assert template is not None
        taxonomy = build_tag_taxonomy(template)
        # Rough estimate: 1 token ≈ 4 characters
        estimated_tokens = len(taxonomy) / 4
        assert estimated_tokens < 4000, f"Taxonomy too large: ~{estimated_tokens:.0f} tokens"

    def test_prompt_template_variables(self) -> None:
        """The autocode prompt file has all required template variables."""
        from bristlenose.llm.prompts import get_prompt

        prompt = get_prompt("autocode")
        assert "{codebook_title}" in prompt.user
        assert "{codebook_preamble}" in prompt.user
        assert "{formatted_tag_taxonomy}" in prompt.user
        assert "{formatted_quotes}" in prompt.user

    def test_prompt_confidence_guidance(self) -> None:
        """The prompt instructs the LLM on confidence scoring."""
        from bristlenose.llm.prompts import get_prompt

        prompt = get_prompt("autocode")
        full_text = prompt.system + " " + prompt.user
        assert "confidence" in full_text.lower()
        assert "0.7" in full_text or "0.7-1.0" in full_text


# ---------------------------------------------------------------------------
# Live LLM tests (@pytest.mark.slow — skipped in CI)
# ---------------------------------------------------------------------------


def _run_llm_discrimination() -> list[tuple[GoldenQuote, str, float]]:
    """Run AutoCode on all golden quotes (called once, cached on class)."""
    import asyncio

    from bristlenose.config import load_settings
    from bristlenose.llm.client import LLMClient
    from bristlenose.llm.prompts import get_prompt
    from bristlenose.llm.structured import AutoCodeBatchResult

    settings = load_settings()
    if settings.llm_provider == "local":
        pytest.skip("AutoCode requires a cloud provider (not Ollama)")

    template = get_template("garrett")
    assert template is not None
    taxonomy = build_tag_taxonomy(template)
    prompt_pair = get_prompt("autocode")

    items = [
        QuoteBatchItem(
            db_id=i, text=gq.text, session_id="s1", participant_id="p1",
            topic_label="", sentiment="",
        )
        for i, gq in enumerate(GOLDEN_QUOTES)
    ]
    quote_text = build_quote_batch(items)

    user_prompt = prompt_pair.user.format(
        codebook_title=template.title,
        codebook_preamble=template.preamble,
        formatted_tag_taxonomy=taxonomy,
        formatted_quotes=quote_text,
    )

    client = LLMClient(settings)

    async def _call() -> AutoCodeBatchResult:
        return await client.analyze(
            system_prompt=prompt_pair.system,
            user_prompt=user_prompt,
            response_model=AutoCodeBatchResult,
        )

    result = asyncio.run(_call())

    results: list[tuple[GoldenQuote, str, float]] = []
    assignment_map = {a.quote_index: a for a in result.assignments}
    for i, gq in enumerate(GOLDEN_QUOTES):
        assignment = assignment_map.get(i)
        if assignment:
            results.append((gq, assignment.tag_name.lower().strip(), assignment.confidence))
        else:
            results.append((gq, "", 0.0))

    return results


@pytest.mark.slow
class TestLiveLLMDiscrimination:
    """Send golden quotes to Claude and check discrimination accuracy.

    These tests actually call the LLM and cost ~$0.01 per run.
    Run with: ``pytest -m slow tests/test_autocode_discrimination.py``
    Skip with: ``pytest -m "not slow"``
    """

    _cache: list[tuple[GoldenQuote, str, float]] | None = None

    @pytest.fixture()
    def llm_results(self) -> list[tuple[GoldenQuote, str, float]]:
        """Run LLM once and cache on the class for all tests."""
        if TestLiveLLMDiscrimination._cache is None:
            TestLiveLLMDiscrimination._cache = _run_llm_discrimination()
        return TestLiveLLMDiscrimination._cache

    def test_high_confidence_accuracy(
        self, llm_results: list[tuple[GoldenQuote, str, float]]
    ) -> None:
        """≥80% of high-confidence (≥0.7) assignments match the golden tag."""
        high_conf = [
            (gq, tag, conf) for gq, tag, conf in llm_results if conf >= 0.7
        ]
        if not high_conf:
            pytest.skip("No high-confidence assignments")
        correct = sum(1 for gq, tag, _ in high_conf if tag == gq.correct_tag)
        accuracy = correct / len(high_conf)
        assert accuracy >= 0.8, (
            f"High-confidence accuracy {accuracy:.0%} ({correct}/{len(high_conf)}) "
            f"below 80% threshold"
        )

    def test_confidence_signal_quality(
        self, llm_results: list[tuple[GoldenQuote, str, float]]
    ) -> None:
        """Average confidence for correct matches is higher than for incorrect."""
        correct_confs = [conf for gq, tag, conf in llm_results if tag == gq.correct_tag]
        incorrect_confs = [conf for gq, tag, conf in llm_results if tag != gq.correct_tag]
        if not correct_confs or not incorrect_confs:
            pytest.skip("Need both correct and incorrect to compare")
        avg_correct = sum(correct_confs) / len(correct_confs)
        avg_incorrect = sum(incorrect_confs) / len(incorrect_confs)
        assert avg_correct > avg_incorrect, (
            f"Correct avg confidence ({avg_correct:.2f}) should be higher "
            f"than incorrect ({avg_incorrect:.2f})"
        )

    def test_no_high_confidence_wrong_plane(
        self, llm_results: list[tuple[GoldenQuote, str, float]]
    ) -> None:
        """No high-confidence tag from the wrong Garrett plane is assigned."""
        template = get_template("garrett")
        assert template is not None
        # Build tag → group lookup
        tag_to_group: dict[str, str] = {}
        for group in template.groups:
            for tag in group.tags:
                tag_to_group[tag.name] = group.name

        violations = []
        for gq, tag, conf in llm_results:
            if conf >= 0.7 and tag in tag_to_group:
                predicted_group = tag_to_group[tag]
                if predicted_group != gq.correct_group:
                    violations.append(
                        f"  '{gq.text[:60]}…' → {tag} ({predicted_group}) "
                        f"should be {gq.correct_group}, confidence={conf:.2f}"
                    )
        assert not violations, (
            "High-confidence wrong-plane assignments:\n"
            + "\n".join(violations)
        )
