"""The Norman codebook against its decision register and its golden fixture.

Two layers, as in ``test_autocode_discrimination.py``:

1. **Structural** (CI-safe): the YAML carries Norman's own terms, every tag
   has full discrimination prompts, the not-this rules do not contradict each
   other, and the register in ``docs/design-codebook-norman.md`` and the
   fixture in ``tests/fixtures/codebook-golden/norman.json`` agree — every
   settled decision with fixture evidence has a witness quote, and every
   witness names a decision that exists. That is what makes a decision
   something that fails rather than something that gets remembered.

2. **Live** (``@pytest.mark.slow``, ~£0.10 per run, deselected by default):
   the fixture through the real autocode prompt. Assertions are per quote for
   the boundary pairs and the canon, so a regression names its seam.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from bristlenose.llm.failure_classifier import LLMFailureKind, classify_exception
from bristlenose.server.autocode import (
    BATCH_SIZE,
    QuoteBatchItem,
    build_quote_batch,
    build_tag_taxonomy,
)
from bristlenose.server.codebook import get_template

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "tests" / "fixtures" / "codebook-golden" / "norman.json"
REGISTER = REPO / "docs" / "design-codebook-norman.md"

# Terms v1 used that are not Norman's, or that the 2013 edition folds away.
# ``perceived affordance`` is a kind of signifier (p. 18); the others were
# invented. A tag carrying one of these is a regression against the register.
NOT_HIS = {"system model", "logical layout", "false signifier", "perceived affordance"}


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _tags() -> dict[str, tuple[str, object]]:
    template = get_template("norman")
    assert template is not None
    return {t.name: (g.name, t) for g in template.groups for t in g.tags}


# ---------------------------------------------------------------------------
# Structural
# ---------------------------------------------------------------------------


class TestVocabulary:
    def test_description_names_his_seven_principles(self) -> None:
        template = get_template("norman")
        assert template is not None
        d = template.description.lower()
        for word in ("discoverability", "feedback", "conceptual model", "affordances",
                     "signifiers", "mappings", "constraints", "slips", "mistakes"):
            assert word in d, word

    def test_no_invented_terms_survive(self) -> None:
        assert not NOT_HIS & set(_tags()), NOT_HIS & set(_tags())

    def test_his_terms_present(self) -> None:
        names = set(_tags())
        for name in ("system image", "misleading signifier", "clear signifier", "spatial correspondence",
                     "no feedback", "excessive feedback", "mode error", "knowledge in the world",
                     "safeguard", "grouping"):
            assert name in names, name

    def test_every_tag_has_full_prompts(self) -> None:
        for name, (_, tag) in _tags().items():
            assert tag.definition and tag.apply_when and tag.not_this, name

    def test_every_not_this_names_another_tag(self) -> None:
        names = list(_tags())
        missing = []
        for name, (_, tag) in _tags().items():
            text = tag.not_this.lower()
            if not any(other in text for other in names if other != name):
                missing.append(name)
        assert not missing, missing

    def test_no_response_routes_to_no_feedback_from_both_sides(self) -> None:
        """v1's delayed and ambiguous each sent the 'no response at all' case
        to the other. Both must now name the tag that owns it (N-06)."""
        tags = _tags()
        assert "no feedback" in tags["delayed feedback"][1].not_this
        assert "no feedback" in tags["uninformative feedback"][1].not_this

    def test_colour_convention_is_cultural(self) -> None:
        tags = _tags()
        assert "colour" in tags["cultural constraint"][1].not_this.lower() or \
               "colour" in tags["cultural constraint"][1].definition.lower()
        assert "red" not in tags["semantic constraint"][1].apply_when.lower()

    def test_committed_errors_route_to_the_error_group(self) -> None:
        tags = _tags()
        assert "rule-based mistake" in tags["model mismatch"][1].not_this
        assert "rule-based mistake" in tags["learned behaviour"][1].not_this

    def test_taxonomy_token_budget(self) -> None:
        """Guards bloat, not exact count: the 4-chars-per-token heuristic
        overestimates (Garrett's 20 tags read ~2,400 real tokens against ~4,000
        estimated). 32 tags at v2.3 estimate ~6,600."""
        template = get_template("norman")
        assert template is not None
        assert len(build_tag_taxonomy(template)) / 4 < 7500

    def test_renamed_from_never_names_a_live_tag(self) -> None:
        live = set(_tags())
        for name, (_, tag) in _tags().items():
            for old in tag.renamed_from:
                assert old not in live, (name, old)


class TestRegisterIntegrity:
    """The register and the fixture must agree, both ways."""

    @staticmethod
    def _entries() -> dict[str, str]:
        text = REGISTER.read_text(encoding="utf-8")
        entries: dict[str, str] = {}
        for m in re.finditer(r"^- \*\*(N-\d\d) · ([^\n]*?)\*\* —\s+(.*?)(?=^- \*\*N-\d\d|^## )", text, re.M | re.S):
            entries[m.group(1)] = m.group(2) + " " + m.group(3)
        assert len(entries) >= 18, "register not parsed"
        return entries

    def test_every_fixture_decision_exists(self) -> None:
        entries = self._entries()
        for q in _fixture()["quotes"]:
            if q.get("decision"):
                assert q["decision"] in entries, (q["id"], q["decision"])

    def test_every_settled_decision_with_fixture_evidence_has_a_witness(self) -> None:
        entries = self._entries()
        witnessed = {q["decision"] for q in _fixture()["quotes"] if q.get("decision")}
        missing = [
            nid for nid, body in entries.items()
            if "settled" in body.split("**")[0].lower() and "E1" in body and nid not in witnessed
        ]
        assert not missing, missing

    def test_fixture_accept_tags_exist(self) -> None:
        names = set(_tags())
        for q in _fixture()["quotes"]:
            for a in q["accept"]:
                assert a in names, (q["id"], a)

    def test_fixture_matches_shipped_version(self) -> None:
        template = get_template("norman")
        assert template is not None
        assert _fixture()["version"] == template.version

    def test_fixture_covers_every_tag(self) -> None:
        covered = {a for q in _fixture()["quotes"] for a in q["accept"]}
        missing = set(_tags()) - covered
        # excessive feedback is Norman's and kept on the strength of the text;
        # no corpus has produced a witness yet (N-06).
        assert missing <= {"excessive feedback"}, missing


# ---------------------------------------------------------------------------
# Live
# ---------------------------------------------------------------------------

_ENVIRONMENTAL = frozenset({
    LLMFailureKind.OUT_OF_CREDIT, LLMFailureKind.INVALID_KEY,
    LLMFailureKind.NETWORK, LLMFailureKind.RATE_LIMITED, LLMFailureKind.SERVER_ERROR,
})


def _run_live() -> dict[str, tuple[str, float]]:
    """Every fixture quote through the real prompt; id → (tag, confidence)."""
    import asyncio

    from bristlenose.config import load_settings
    from bristlenose.llm.client import LLMClient
    from bristlenose.llm.prompts import get_prompt
    from bristlenose.llm.structured import AutoCodeBatchResult

    settings = load_settings()
    if settings.llm_provider == "local":
        pytest.skip("AutoCode requires a cloud provider (not Ollama)")
    template = get_template("norman")
    assert template is not None
    taxonomy = build_tag_taxonomy(template)
    prompt_pair = get_prompt("autocode")
    client = LLMClient(settings)
    quotes = _fixture()["quotes"]

    async def batch(items: list[dict]) -> dict[str, tuple[str, float]]:
        qs = [QuoteBatchItem(db_id=i, text=q["text"], session_id="s1", participant_id="p1",
                             topic_label="", sentiment="") for i, q in enumerate(items)]
        user_prompt = prompt_pair.user.format(
            codebook_title=template.title, codebook_preamble=template.preamble,
            formatted_tag_taxonomy=taxonomy, formatted_quotes=build_quote_batch(qs),
        )
        res: AutoCodeBatchResult = await client.analyze(
            system_prompt=prompt_pair.system, user_prompt=user_prompt,
            response_model=AutoCodeBatchResult,
        )
        amap = {a.quote_index: a for a in res.assignments}
        return {
            q["id"]: ((amap[i].tag_name.lower().strip(), amap[i].confidence) if i in amap else ("", 0.0))
            for i, q in enumerate(items)
        }

    async def go() -> dict[str, tuple[str, float]]:
        out: dict[str, tuple[str, float]] = {}
        for i in range(0, len(quotes), BATCH_SIZE):
            out.update(await batch(quotes[i:i + BATCH_SIZE]))
        return out

    try:
        return asyncio.run(go())
    except Exception as exc:
        if classify_exception(settings.llm_provider, exc) in _ENVIRONMENTAL:
            pytest.skip(f"SKIPPED, NOT PASSED — {settings.llm_provider}: {exc}")
        raise


_BY_KIND: dict[str, list[dict]] = {}
for _q in _fixture()["quotes"]:
    _BY_KIND.setdefault(_q["kind"], []).append(_q)


@pytest.mark.slow
class TestLiveNorman:
    _cache: dict[str, tuple[str, float]] | None = None

    @pytest.fixture()
    def results(self) -> dict[str, tuple[str, float]]:
        if TestLiveNorman._cache is None:
            TestLiveNorman._cache = _run_live()
        return TestLiveNorman._cache

    def test_golden_floor(self, results: dict[str, tuple[str, float]]) -> None:
        """The golden set echoes the wording; ≥ 90% correct at ≥ 0.7 is the floor."""
        rows = _BY_KIND["golden"]
        ok = sum(1 for q in rows if results[q["id"]][0] in q["accept"] and results[q["id"]][1] >= 0.7)
        assert ok / len(rows) >= 0.9, f"{ok}/{len(rows)}"

    @pytest.mark.parametrize("q", _BY_KIND["pair"], ids=[q["id"] for q in _BY_KIND["pair"]])
    def test_boundary_pair(self, results: dict[str, tuple[str, float]], q: dict) -> None:
        tag, conf = results[q["id"]]
        assert tag in q["accept"], f"{q['text'][:80]!r}: got {tag}@{conf:.2f}, want {q['accept']}"

    @pytest.mark.parametrize("q", _BY_KIND["canon"], ids=[q["id"] for q in _BY_KIND["canon"]])
    def test_canon(self, results: dict[str, tuple[str, float]], q: dict) -> None:
        tag, conf = results[q["id"]]
        if q["accept"]:
            assert tag in q["accept"], f"{q['text'][:80]!r}: got {tag}@{conf:.2f}, want {q['accept']}"
        else:
            assert conf < 0.4, f"{q['text'][:80]!r}: no tag applies, got {tag}@{conf:.2f}"

    def test_out_of_scope_stays_low(self, results: dict[str, tuple[str, float]]) -> None:
        leaks = [(q["text"], results[q["id"]]) for q in _BY_KIND["oos"] if results[q["id"]][1] >= 0.4]
        assert not leaks, leaks

    def test_messy_majority(self, results: dict[str, tuple[str, float]]) -> None:
        rows = [q for q in _BY_KIND["messy"] if q["accept"]]
        ok = sum(1 for q in rows if results[q["id"]][0] in q["accept"])
        assert ok / len(rows) >= 0.7, f"{ok}/{len(rows)}"

    @pytest.mark.xfail(reason="N-19 open: read-aloud narration still lands on system image ~0.55", strict=False)
    def test_trap_read_aloud_takes_no_tag(self, results: dict[str, tuple[str, float]]) -> None:
        for q in _BY_KIND["trap"]:
            tag, conf = results[q["id"]]
            assert conf < 0.4, f"got {tag}@{conf:.2f}"
