"""Tests for the dynamic codebook builder — engine + API.

Engine helpers (formatting, ranking, hashing) are tested directly. The
LLM-calling paths are tested through the API with a mocked ``LLMClient`` and a
test ``settings`` override on ``app.state`` — no real LLM, no network.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from bristlenose.llm.structured import (
    CandidateMatch,
    CandidateMatchResult,
    SynthesizedTagPrompt,
)
from bristlenose.server import codebook_builder as cb
from bristlenose.server.app import create_app
from bristlenose.server.models import (
    CodebookGroup,
    ProjectCodebookGroup,
    Quote,
    QuoteTag,
    TagDefinition,
    TagPromptDecision,
)
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


# ---------------------------------------------------------------------------
# Pure-helper unit tests (no LLM)
# ---------------------------------------------------------------------------


class TestPromptVersion:
    def test_is_stable_for_same_text(self) -> None:
        a = cb.prompt_version("def", "apply", "not")
        b = cb.prompt_version("def", "apply", "not")
        assert a == b
        assert len(a) == 8

    def test_changes_when_text_changes(self) -> None:
        a = cb.prompt_version("def", "apply", "not")
        b = cb.prompt_version("def", "apply tighter", "not")
        assert a != b

    def test_ignores_surrounding_whitespace(self) -> None:
        assert cb.prompt_version("  def ", "apply", "not") == cb.prompt_version(
            "def", " apply ", " not"
        )

    def test_draft_version_matches_helper(self) -> None:
        d = cb.PromptDraft(definition="d", apply_when="a", not_this="n")
        assert d.version == cb.prompt_version("d", "a", "n")


class TestFormatting:
    def test_example_block_numbers_from_zero(self) -> None:
        block = cb.build_example_block(
            [
                cb.ExampleQuote(text="too expensive", session_id="s1", participant_id="p1"),
                cb.ExampleQuote(text="can't afford it", session_id="s1", participant_id="p2"),
            ]
        )
        assert block.startswith("0.")
        assert "1." in block
        assert "too expensive" in block
        assert "[s1/p1]" in block

    def test_format_tag_prompt_includes_all_sections(self) -> None:
        text = cb.format_tag_prompt(
            cb.PromptDraft(definition="d", apply_when="a", not_this="n")
        )
        assert "**Definition:** d" in text
        assert "**Apply when:** a" in text
        assert "**Not this:** n" in text

    def test_format_tag_prompt_empty_draft(self) -> None:
        assert "No discrimination" in cb.format_tag_prompt(cb.PromptDraft())

    def test_current_prompt_block_empty_for_none(self) -> None:
        assert cb.build_current_prompt_block(None) == ""

    def test_current_prompt_block_for_draft(self) -> None:
        block = cb.build_current_prompt_block(cb.PromptDraft(definition="d"))
        assert "Current prompt" in block
        assert "**Definition:** d" in block


class TestRankCandidates:
    def _quotes(self, n: int) -> list[cb.CandidateQuote]:
        return [cb.CandidateQuote(db_id=100 + i, text=f"q{i}") for i in range(n)]

    def test_keeps_only_matches(self) -> None:
        quotes = self._quotes(3)
        verdicts = [
            (0, True, 0.9, "r0"),
            (1, False, 0.2, "r1"),
            (2, True, 0.5, "r2"),
        ]
        out = cb.rank_candidates(verdicts, quotes)
        assert [c.db_id for c in out] == [100, 102]

    def test_sorts_by_confidence_desc(self) -> None:
        quotes = self._quotes(3)
        verdicts = [(0, True, 0.4, "a"), (1, True, 0.95, "b"), (2, True, 0.6, "c")]
        out = cb.rank_candidates(verdicts, quotes)
        assert [c.confidence for c in out] == [0.95, 0.6, 0.4]

    def test_min_confidence_filter(self) -> None:
        quotes = self._quotes(2)
        verdicts = [(0, True, 0.3, "a"), (1, True, 0.8, "b")]
        out = cb.rank_candidates(verdicts, quotes, min_confidence=0.5)
        assert [c.db_id for c in out] == [101]

    def test_drops_out_of_range_index(self) -> None:
        quotes = self._quotes(1)
        verdicts = [(5, True, 0.9, "x")]
        assert cb.rank_candidates(verdicts, quotes) == []


# ---------------------------------------------------------------------------
# Fixtures for API tests
# ---------------------------------------------------------------------------


def _mock_settings() -> MagicMock:
    s = MagicMock()
    s.llm_concurrency = 2
    s.llm_provider = "anthropic"
    s.llm_model = "test-model"
    s.llm_max_tokens = 1000
    return s


def _patch_llm(mock_analyze: AsyncMock):
    """Patch LLMClient so engine calls use a mocked analyze coroutine."""
    client = MagicMock()
    client.analyze = mock_analyze
    client.tracker = MagicMock(input_tokens=0, output_tokens=0)
    return patch("bristlenose.llm.client.LLMClient", return_value=client)


@pytest.fixture()
def client_with_coded_tag() -> tuple[TestClient, int]:
    """A client where one tag ('prescription cost') is on 3 of the 4 quotes."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    app.state.settings = _mock_settings()
    db = app.state.db_factory()
    try:
        g = CodebookGroup(name="Cost", subtitle="Money", colour_set="emo", sort_order=0)
        db.add(g)
        db.flush()
        db.add(ProjectCodebookGroup(project_id=1, codebook_group_id=g.id, sort_order=0))
        td = TagDefinition(name="prescription cost", codebook_group_id=g.id)
        db.add(td)
        db.flush()
        tag_id = td.id
        quotes = db.query(Quote).filter_by(project_id=1).order_by(Quote.id).all()
        for q in quotes[:3]:
            db.add(QuoteTag(quote_id=q.id, tag_definition_id=tag_id))
        db.commit()
    finally:
        db.close()
    return AuthTestClient(app), tag_id


def _synth_result() -> SynthesizedTagPrompt:
    return SynthesizedTagPrompt(
        summary="Participants worry about the price of medication.",
        definition="The participant expresses concern about the cost of prescriptions.",
        apply_when="The quote names affordability, price, or cost of medication.",
        not_this="General money worries unrelated to medication.",
    )


# ---------------------------------------------------------------------------
# State endpoint
# ---------------------------------------------------------------------------


class TestBuilderState:
    def test_reports_coded_count_and_readiness(self, client_with_coded_tag) -> None:
        client, tag_id = client_with_coded_tag
        data = client.get(f"/api/projects/1/codebook/tags/{tag_id}/builder").json()
        assert data["coded_count"] == 3
        assert data["ready_to_synthesize"] is True
        assert data["min_examples"] == 3
        assert data["prompt"] is None

    def test_404_for_unknown_tag(self, client_with_coded_tag) -> None:
        client, _ = client_with_coded_tag
        assert client.get("/api/projects/1/codebook/tags/9999/builder").status_code == 404


# ---------------------------------------------------------------------------
# Synthesize
# ---------------------------------------------------------------------------


class TestSynthesize:
    def test_synthesizes_and_persists(self, client_with_coded_tag) -> None:
        client, tag_id = client_with_coded_tag
        with _patch_llm(AsyncMock(return_value=_synth_result())):
            resp = client.post(
                f"/api/projects/1/codebook/tags/{tag_id}/builder/synthesize"
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["definition"].startswith("The participant expresses")
        assert body["apply_when"]
        assert body["example_count"] == 3
        assert len(body["version"]) == 8
        # Persisted — visible via state
        state = client.get(f"/api/projects/1/codebook/tags/{tag_id}/builder").json()
        assert state["prompt"]["definition"] == body["definition"]

    def test_rejects_when_too_few_examples(self) -> None:
        app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
        app.state.settings = _mock_settings()
        db = app.state.db_factory()
        try:
            g = CodebookGroup(name="C", subtitle="", colour_set="emo", sort_order=0)
            db.add(g)
            db.flush()
            db.add(ProjectCodebookGroup(project_id=1, codebook_group_id=g.id, sort_order=0))
            td = TagDefinition(name="sparse", codebook_group_id=g.id)
            db.add(td)
            db.flush()
            tag_id = td.id
            q = db.query(Quote).filter_by(project_id=1).first()
            db.add(QuoteTag(quote_id=q.id, tag_definition_id=tag_id))
            db.commit()
        finally:
            db.close()
        client = AuthTestClient(app)
        with _patch_llm(AsyncMock(return_value=_synth_result())) as _:
            resp = client.post(
                f"/api/projects/1/codebook/tags/{tag_id}/builder/synthesize"
            )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Edit prompt directly
# ---------------------------------------------------------------------------


class TestEditPrompt:
    def test_direct_edit_recomputes_version(self, client_with_coded_tag) -> None:
        client, tag_id = client_with_coded_tag
        with _patch_llm(AsyncMock(return_value=_synth_result())):
            v1 = client.post(
                f"/api/projects/1/codebook/tags/{tag_id}/builder/synthesize"
            ).json()["version"]
        edited = client.put(
            f"/api/projects/1/codebook/tags/{tag_id}/builder/prompt",
            json={"apply_when": "Only when the participant names a specific drug price."},
        ).json()
        assert edited["apply_when"].startswith("Only when")
        assert edited["version"] != v1  # content hash moved

    def test_edit_creates_prompt_when_absent(self, client_with_coded_tag) -> None:
        client, tag_id = client_with_coded_tag
        resp = client.put(
            f"/api/projects/1/codebook/tags/{tag_id}/builder/prompt",
            json={"definition": "hand-written", "status": "active"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_rejects_bad_status(self, client_with_coded_tag) -> None:
        client, tag_id = client_with_coded_tag
        resp = client.put(
            f"/api/projects/1/codebook/tags/{tag_id}/builder/prompt",
            json={"status": "published"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


def _candidate_result_all_match(n: int, conf: float = 0.8) -> CandidateMatchResult:
    return CandidateMatchResult(
        matches=[
            CandidateMatch(quote_index=i, matches=True, confidence=conf, rationale=f"r{i}")
            for i in range(n)
        ]
    )


class TestCandidates:
    def test_requires_a_prompt_first(self, client_with_coded_tag) -> None:
        client, tag_id = client_with_coded_tag
        resp = client.post(
            f"/api/projects/1/codebook/tags/{tag_id}/builder/candidates",
            json={"min_confidence": 0.5},
        )
        assert resp.status_code == 400

    def test_scans_uncoded_pool(self, client_with_coded_tag) -> None:
        client, tag_id = client_with_coded_tag
        with _patch_llm(AsyncMock(return_value=_synth_result())):
            client.post(f"/api/projects/1/codebook/tags/{tag_id}/builder/synthesize")
        # Only 1 of 4 quotes is uncoded → pool size 1.
        with _patch_llm(AsyncMock(return_value=_candidate_result_all_match(1, 0.9))):
            resp = client.post(
                f"/api/projects/1/codebook/tags/{tag_id}/builder/candidates",
                json={"min_confidence": 0.5, "limit": 50},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["scanned"] == 1
        assert len(body["candidates"]) == 1
        c = body["candidates"][0]
        assert c["quote_id"].startswith("q-")
        assert c["confidence"] == 0.9

    def test_min_confidence_filters(self, client_with_coded_tag) -> None:
        client, tag_id = client_with_coded_tag
        with _patch_llm(AsyncMock(return_value=_synth_result())):
            client.post(f"/api/projects/1/codebook/tags/{tag_id}/builder/synthesize")
        with _patch_llm(AsyncMock(return_value=_candidate_result_all_match(1, 0.2))):
            resp = client.post(
                f"/api/projects/1/codebook/tags/{tag_id}/builder/candidates",
                json={"min_confidence": 0.5},
            )
        assert resp.json()["candidates"] == []


# ---------------------------------------------------------------------------
# Decisions + refine
# ---------------------------------------------------------------------------


class TestDecisions:
    def _seed_prompt(self, client: TestClient, tag_id: int) -> None:
        with _patch_llm(AsyncMock(return_value=_synth_result())):
            client.post(f"/api/projects/1/codebook/tags/{tag_id}/builder/synthesize")

    def test_accept_applies_tag_and_logs_decision(self, client_with_coded_tag) -> None:
        client, tag_id = client_with_coded_tag
        self._seed_prompt(client, tag_id)
        app = client.app
        # The 4th quote is uncoded — accept it.
        db = app.state.db_factory()
        uncoded_dom = None
        try:
            coded = {
                r[0]
                for r in db.query(QuoteTag.quote_id)
                .filter_by(tag_definition_id=tag_id)
                .all()
            }
            from bristlenose.server.routes.data import _quote_dom_id

            for q in db.query(Quote).filter_by(project_id=1).all():
                if q.id not in coded:
                    uncoded_dom = _quote_dom_id(q)
                    break
        finally:
            db.close()
        assert uncoded_dom is not None

        refined = SynthesizedTagPrompt(
            summary="s", definition="tighter def", apply_when="tighter apply",
            not_this="tighter not",
        )
        with _patch_llm(AsyncMock(return_value=refined)):
            resp = client.post(
                f"/api/projects/1/codebook/tags/{tag_id}/builder/decisions",
                json={
                    "decisions": [
                        {"quote_id": uncoded_dom, "decision": "accept",
                         "reason": "names the copay"},
                    ],
                    "refine": True,
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["accepted"] == 1
        assert body["applied_tags"] == 1
        assert body["prompt"]["definition"] == "tighter def"  # refined

        # The tag is now on that quote, and a decision row exists.
        db = app.state.db_factory()
        try:
            assert db.query(TagPromptDecision).count() == 1
            d = db.query(TagPromptDecision).first()
            assert d.decision == "accept"
            assert d.reason == "names the copay"
            # 4 quotes now carry the tag
            assert (
                db.query(QuoteTag).filter_by(tag_definition_id=tag_id).count() == 4
            )
        finally:
            db.close()

    def test_reject_logs_without_applying(self, client_with_coded_tag) -> None:
        client, tag_id = client_with_coded_tag
        self._seed_prompt(client, tag_id)
        db = client.app.state.db_factory()
        try:
            coded = {
                r[0]
                for r in db.query(QuoteTag.quote_id)
                .filter_by(tag_definition_id=tag_id).all()
            }
            from bristlenose.server.routes.data import _quote_dom_id

            uncoded_dom = next(
                _quote_dom_id(q)
                for q in db.query(Quote).filter_by(project_id=1).all()
                if q.id not in coded
            )
            before = db.query(QuoteTag).filter_by(tag_definition_id=tag_id).count()
        finally:
            db.close()

        with _patch_llm(AsyncMock(return_value=_synth_result())):
            resp = client.post(
                f"/api/projects/1/codebook/tags/{tag_id}/builder/decisions",
                json={
                    "decisions": [
                        {"quote_id": uncoded_dom, "decision": "reject",
                         "reason": "about rent, not meds"},
                    ],
                    "refine": False,
                },
            )
        assert resp.status_code == 200
        assert resp.json()["rejected"] == 1
        assert resp.json()["applied_tags"] == 0
        db = client.app.state.db_factory()
        try:
            assert db.query(QuoteTag).filter_by(tag_definition_id=tag_id).count() == before
            assert db.query(TagPromptDecision).first().decision == "reject"
        finally:
            db.close()

    def test_rejects_bad_decision_value(self, client_with_coded_tag) -> None:
        client, tag_id = client_with_coded_tag
        self._seed_prompt(client, tag_id)
        resp = client.post(
            f"/api/projects/1/codebook/tags/{tag_id}/builder/decisions",
            json={"decisions": [{"quote_id": "q-p1-10", "decision": "maybe"}]},
        )
        assert resp.status_code == 400
