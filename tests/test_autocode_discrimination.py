"""Evaluation harness for AutoCode prompt discrimination quality.

Two test layers:

1. **Structural tests** (CI-safe, no LLM calls): Verify the prompt text
   contains enough discriminating information — checks that ``not_this``
   fields mention confusable siblings, that all groups are present, and
   that the preamble's mutual-exclusivity instruction appears.

2. **Live LLM tests** (``@pytest.mark.slow``): Actually send golden
   quotes to Claude and check accuracy.  Costs ~$0.01 per run.  **Not
   collected by default** — ``addopts = -m "not slow"`` in ``pyproject.toml``
   keeps the everyday ``pytest tests/`` free.  Opt in with ``pytest -m slow``.

Golden dataset
--------------
Each entry is a quote a human UX researcher would tag with a specific
Garrett sub-tag, plus a plausible-wrong tag that the LLM might confuse
it with.  The ``not_this`` field on the correct tag should give the LLM
enough signal to discriminate.
"""

from __future__ import annotations

from collections.abc import Coroutine
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from bristlenose.server.autocode import QuoteBatchItem, build_quote_batch, build_tag_taxonomy
from bristlenose.server.codebook import TemplateTag, get_template
from tests.conftest import run_paid_autocode

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
        plausible_wrong_tag="functional requirement",
        plausible_wrong_group="Scope",
    ),
    GoldenQuote(
        text="They obviously want me to sign up for the premium plan before I can see prices.",
        correct_tag="product objective",
        correct_group="Strategy",
        plausible_wrong_tag="scope creep",
        plausible_wrong_group="Scope",
    ),
    GoldenQuote(
        text="Honestly I'd come back to this every week if it stayed like this — I've already spent half an hour on it.",
        correct_tag="success metric",
        correct_group="Strategy",
        plausible_wrong_tag="user need",
        plausible_wrong_group="Strategy",
    ),
    GoldenQuote(
        text="This doesn't look like a real fish shop — it looks more like some generic template site, not them at all.",
        correct_tag="brand identity",
        correct_group="Strategy",
        plausible_wrong_tag="visual design",
        plausible_wrong_group="Surface",
    ),
    # --- Scope ---
    GoldenQuote(
        text="There's no way to compare two fish side by side — I have to keep going back and forth.",
        correct_tag="functional requirement",
        correct_group="Scope",
        plausible_wrong_tag="navigation design",
        plausible_wrong_group="Skeleton",
    ),
    GoldenQuote(
        text="They don't have any water parameters listed for any of the fish.",
        correct_tag="content requirement",
        correct_group="Scope",
        plausible_wrong_tag="functional requirement",
        plausible_wrong_group="Scope",
    ),
    GoldenQuote(
        text="The most important thing for me is the compatibility checker — everything else is nice to have.",
        correct_tag="requirement priority",
        correct_group="Scope",
        plausible_wrong_tag="user need",
        plausible_wrong_group="Strategy",
    ),
    GoldenQuote(
        text="Why does a fish shop have a social media feed? I don't need this.",
        correct_tag="scope creep",
        correct_group="Scope",
        plausible_wrong_tag="product objective",
        plausible_wrong_group="Strategy",
    ),
    # --- Structure ---
    GoldenQuote(
        text="When I click 'add to tank' I expected it to show me compatibility right away, but nothing happened.",
        correct_tag="interaction design",
        correct_group="Structure",
        plausible_wrong_tag="uninformative feedback",
        plausible_wrong_group="Feedback",  # Norman — cross-framework test
    ),
    GoldenQuote(
        text="I would have expected angelfish to be under tropical freshwater, not just in a generic 'fish' category.",
        correct_tag="information architecture",
        correct_group="Structure",
        plausible_wrong_tag="navigation design",
        plausible_wrong_group="Skeleton",
    ),
    GoldenQuote(
        text="It wouldn't let me check out without a delivery date, fine, but once I'd paid there was no way to fix the address.",
        correct_tag="error handling",
        correct_group="Structure",
        plausible_wrong_tag="interaction design",
        plausible_wrong_group="Structure",
    ),
    # --- Skeleton ---
    GoldenQuote(
        text="This page feels really cramped — there's too much going on and I can't focus on anything.",
        correct_tag="interface design",
        correct_group="Skeleton",
        plausible_wrong_tag="information design",
        plausible_wrong_group="Skeleton",
    ),
    GoldenQuote(
        text="I keep having to go back to the home page to find anything — there's no way to jump between sections.",
        correct_tag="navigation design",
        correct_group="Skeleton",
        plausible_wrong_tag="information architecture",
        plausible_wrong_group="Structure",
    ),
    GoldenQuote(
        text="The 'buy now' button is massive but the species information is tiny — seems backwards.",
        correct_tag="information design",
        correct_group="Skeleton",
        plausible_wrong_tag="interface design",
        plausible_wrong_group="Skeleton",
    ),
    GoldenQuote(
        text="Usually on other sites there's a search bar at the top — I can't find one anywhere.",
        correct_tag="convention",
        correct_group="Skeleton",
        plausible_wrong_tag="interface design",
        plausible_wrong_group="Skeleton",
    ),
    # --- Surface ---
    GoldenQuote(
        text="The photos of the fish are gorgeous — really high quality, you can see all the colours.",
        correct_tag="visual design",
        correct_group="Surface",
        plausible_wrong_tag="contrast and uniformity",
        plausible_wrong_group="Surface",
    ),
    GoldenQuote(
        text="I didn't see the checkout button at all — it's the same grey as everything else around it.",
        correct_tag="contrast and uniformity",
        correct_group="Surface",
        plausible_wrong_tag="interface design",
        plausible_wrong_group="Skeleton",
    ),
    GoldenQuote(
        text="This page looks like a completely different site from the last one — the buttons are all different shapes.",
        correct_tag="consistency",
        correct_group="Surface",
        plausible_wrong_tag="convention",
        plausible_wrong_group="Skeleton",
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

    def test_preamble_states_plane_dependence(self) -> None:
        """Garrett 2.0: the planes are dependent (ch. 2), not mutually exclusive;
        the single-tag rule is stated as ours, not his."""
        template = get_template("garrett")
        assert template is not None
        assert "depends on the one below" in template.preamble.lower()

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
        # "navigation design" or "Skeleton" in its not_this
        ia_tag = tag_lookup["information architecture"]
        assert ia_tag.not_this
        assert (
            "navigation" in ia_tag.not_this.lower()
            or "skeleton" in ia_tag.not_this.lower()
        )

        # "interface design" (Skeleton) should mention "navigation"
        # or "Structure" in its not_this
        cp_tag = tag_lookup["interface design"]
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
        """Golden dataset covers all 18 Garrett tags (2.0)."""
        tags = {gq.correct_tag for gq in GOLDEN_QUOTES}
        assert len(tags) == 18

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
# Live LLM tests (@pytest.mark.slow — deselected by default; opt in with -m slow)
# ---------------------------------------------------------------------------


class _ProviderError(Exception):
    """An SDK-shaped error: a status and a message, as the classifier reads them."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status


class TestPaidRunnerSkipsOnlyForTheEnvironment:
    """``run_paid_autocode`` (tests/conftest.py) holds the paid harnesses' two skips.

    Free: every call here is a stub, nothing reaches a provider. Pinned because the
    three live harnesses that share it never run outside a deliberate ``-m slow``.
    """

    @staticmethod
    def _provider(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
        from bristlenose import config

        monkeypatch.setattr(config, "load_settings", lambda: SimpleNamespace(llm_provider=name))

    def test_a_local_provider_skips_before_building_the_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._provider(monkeypatch, "local")

        def build(settings: Any) -> Coroutine[Any, Any, None]:
            raise AssertionError("built a paid call for a local provider")

        with pytest.raises(pytest.skip.Exception, match="cloud provider"):
            run_paid_autocode(build)

    def test_an_unfunded_account_skips_and_says_not_passed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._provider(monkeypatch, "anthropic")

        async def call() -> None:
            raise _ProviderError(400, "Your credit balance is too low to access the API.")

        with pytest.raises(pytest.skip.Exception, match="SKIPPED, NOT PASSED — anthropic"):
            run_paid_autocode(lambda settings: call())

    def test_a_bad_request_still_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._provider(monkeypatch, "anthropic")

        async def call() -> None:
            raise _ProviderError(400, "messages: field required")

        with pytest.raises(_ProviderError):
            run_paid_autocode(lambda settings: call())

    def test_a_cloud_call_returns_its_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._provider(monkeypatch, "anthropic")

        async def call() -> str:
            return "coded"

        assert run_paid_autocode(lambda settings: call()) == "coded"


def _run_llm_discrimination() -> list[tuple[GoldenQuote, str, float]]:
    """Run AutoCode on all golden quotes (called once, cached on class).

    The two skips (a local provider; an account, key or network that could not
    run the call) are ``run_paid_autocode``'s, shared with the other paid
    AutoCode harnesses in ``tests/conftest.py``.
    """
    from bristlenose.config import BristlenoseSettings
    from bristlenose.llm.client import LLMClient
    from bristlenose.llm.prompts import get_prompt
    from bristlenose.llm.structured import AutoCodeBatchResult

    def build(settings: BristlenoseSettings) -> Coroutine[Any, Any, AutoCodeBatchResult]:
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
        return client.analyze(
            system_prompt=prompt_pair.system,
            user_prompt=user_prompt,
            response_model=AutoCodeBatchResult,
        )

    result = run_paid_autocode(build)

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

    These tests actually call the LLM and cost ~$0.01 per run, so they are
    **opt-in**: ``addopts`` in ``pyproject.toml`` deselects the ``slow`` marker,
    and a ``-m`` typed on the command line overrides it.

    Run with: ``pytest -m slow tests/test_autocode_discrimination.py``

    If the account has no credit these SKIP rather than error — a provider
    billing wall is an environment condition, not a discrimination failure.
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
        # Not a skip: the golden quotes are written to their tags' wording, so a run
        # in which nothing reaches the accept line is AutoCode proposing nothing a
        # researcher would take, and test_no_high_confidence_wrong_plane would pass
        # it vacuously.
        assert high_conf, (
            "No assignment reached 0.7 confidence on the golden quotes: AutoCode "
            "proposed nothing above the accept line"
        )
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
