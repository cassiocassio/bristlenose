"""Tests for the chat lens — grounding core + cited-question-box API.

What the prototype is testing is not "can it answer" — it is "are the
citations honest" (docs/design-chat-lens.md §6). So the load-bearing tests
here are the ones where the model *lies*: an invented quote id, a
malformed id, an id from another project, an id for a quote the
researcher hid. Every one must land in ``invalid_quote_ids`` — never
render as evidence, never 500.

LLM-calling paths are tested through the API with a mocked ``LLMClient``
and a test ``settings`` override on ``app.state`` — no real LLM, no
network (CI has no keys).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from bristlenose.llm.structured import ChatLensAnswer, ChatLensClaim
from bristlenose.server.app import create_app
from bristlenose.server.grounding import (
    assemble_corpus_context,
    quote_dom_id,
    resolve_quote_ids,
)
from bristlenose.server.models import (
    Project,
    Quote,
    QuoteEdit,
    QuoteState,
)
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"

# The smoke fixture's four quotes (see server/CLAUDE.md).
_FIXTURE_IDS = {"q-p1-10", "q-p1-26", "q-p1-46", "q-p1-66"}


def _mock_settings() -> MagicMock:
    s = MagicMock()
    s.llm_provider = "anthropic"
    s.llm_model = "test-model"
    s.llm_max_tokens = 1000
    s.anthropic_api_key = "sk-test"
    return s


def _patch_llm(mock_analyze: AsyncMock):
    """Patch LLMClient so service calls use a mocked analyze coroutine."""
    client = MagicMock()
    client.analyze = mock_analyze
    client.tracker = MagicMock(input_tokens=0, output_tokens=0)
    return patch("bristlenose.llm.client.LLMClient", return_value=client)


def _answer(
    claims: list[dict] | None = None, unsupported: str = ""
) -> ChatLensAnswer:
    return ChatLensAnswer(
        claims=[ChatLensClaim(**c) for c in (claims or [])],
        unsupported=unsupported,
    )


def _make_app():
    app = create_app(project_dir=_FIXTURE_DIR, dev=False, db_url="sqlite://")
    app.state.settings = _mock_settings()
    return app


def _quote_pks_by_dom_id(db) -> dict[str, int]:
    return {
        quote_dom_id(q.participant_id, q.start_timecode): q.id
        for q in db.query(Quote).filter_by(project_id=1).all()
    }


# ---------------------------------------------------------------------------
# Grounding — corpus assembly
# ---------------------------------------------------------------------------


class TestCorpusAssembly:
    def test_contains_every_fixture_quote_with_report_structure(self) -> None:
        app = _make_app()
        db = app.state.db_factory()
        try:
            corpus = assemble_corpus_context(db, 1)
        finally:
            db.close()

        assert set(corpus.quotes_by_id) == _FIXTURE_IDS
        assert corpus.quote_count == 4
        assert corpus.total_quotes == 4
        assert not corpus.truncated
        # Report structure and anonymised roster are in the prompt text.
        assert "# Study: Smoke Test" in corpus.text
        assert "Speakers: p1" in corpus.text
        assert "## Section: Dashboard" in corpus.text
        assert "## Theme: Onboarding gaps" in corpus.text
        for dom_id in _FIXTURE_IDS:
            assert f"[{dom_id}]" in corpus.text

    def test_curation_layer_starred_and_edited_text(self) -> None:
        app = _make_app()
        db = app.state.db_factory()
        try:
            pks = _quote_pks_by_dom_id(db)
            db.add(QuoteState(quote_id=pks["q-p1-10"], is_starred=True))
            db.add(
                QuoteEdit(
                    quote_id=pks["q-p1-10"],
                    edited_text="The dashboard settings were impossible to find.",
                )
            )
            db.commit()
            corpus = assemble_corpus_context(db, 1)
        finally:
            db.close()

        starred = corpus.quotes_by_id["q-p1-10"]
        assert starred.starred is True
        assert starred.text == "The dashboard settings were impossible to find."
        # The researcher's edit — not the pipeline text — is what the model sees.
        assert "impossible to find" in corpus.text
        assert "couldn't figure out where my settings were" not in corpus.text
        assert "starred" in corpus.text

    def test_hidden_quotes_are_excluded(self) -> None:
        app = _make_app()
        db = app.state.db_factory()
        try:
            pks = _quote_pks_by_dom_id(db)
            db.add(QuoteState(quote_id=pks["q-p1-26"], is_hidden=True))
            db.commit()
            corpus = assemble_corpus_context(db, 1)
        finally:
            db.close()

        assert "q-p1-26" not in corpus.quotes_by_id
        assert "q-p1-26" not in corpus.text
        assert corpus.hidden_excluded == 1
        assert corpus.total_quotes == 3

    def test_truncation_is_visible_never_silent(self) -> None:
        app = _make_app()
        db = app.state.db_factory()
        try:
            corpus = assemble_corpus_context(db, 1, max_chars=250)
        finally:
            db.close()

        assert corpus.truncated
        assert corpus.quote_count < corpus.total_quotes
        assert "[corpus truncated:" in corpus.text


# ---------------------------------------------------------------------------
# Grounding — citation validation
# ---------------------------------------------------------------------------


class TestResolveQuoteIds:
    def _corpus(self):
        app = _make_app()
        db = app.state.db_factory()
        try:
            return assemble_corpus_context(db, 1)
        finally:
            db.close()

    def test_splits_resolved_from_rejected_preserving_order(self) -> None:
        corpus = self._corpus()
        resolved, rejected = resolve_quote_ids(
            ["q-p1-46", "q-p1-999", "banana", "q-p1-10"], corpus
        )
        assert [q.dom_id for q in resolved] == ["q-p1-46", "q-p1-10"]
        assert rejected == ["q-p1-999", "banana"]

    def test_duplicates_dropped_after_first_appearance(self) -> None:
        corpus = self._corpus()
        resolved, rejected = resolve_quote_ids(
            ["q-p1-10", "q-p1-10", "q-p1-999", "q-p1-999"], corpus
        )
        assert [q.dom_id for q in resolved] == ["q-p1-10"]
        assert rejected == ["q-p1-999"]

    def test_empty_and_whitespace_ids_ignored(self) -> None:
        corpus = self._corpus()
        resolved, rejected = resolve_quote_ids(["", "   ", "q-p1-10"], corpus)
        assert [q.dom_id for q in resolved] == ["q-p1-10"]
        assert rejected == []


# ---------------------------------------------------------------------------
# API — the lab ships flag-gated, without --dev
# ---------------------------------------------------------------------------


class TestChatLensMounting:
    def test_page_and_api_ship_without_dev(self) -> None:
        app = _make_app()
        page = TestClient(app).get("/chat-lens")  # outside /api, no auth needed
        assert page.status_code == 200
        assert "Chat lens" in page.text
        # The page embeds the bearer token for its own fetches.
        assert app.state.auth_token in page.text

    def test_disabled_by_flag(self, monkeypatch) -> None:
        """Escape hatch: BRISTLENOSE_EXPERIMENTAL_CHAT_LENS=0 removes it entirely."""
        monkeypatch.setenv("BRISTLENOSE_EXPERIMENTAL_CHAT_LENS", "0")
        app = create_app(project_dir=_FIXTURE_DIR, dev=False, db_url="sqlite://")
        assert TestClient(app).get("/chat-lens").status_code == 404
        r = AuthTestClient(app).post(
            "/api/dev/chat-lens/ask", json={"question": "anything"}
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# API — honest citations (the point of the prototype)
# ---------------------------------------------------------------------------


class TestAsk:
    def test_cited_quote_is_rendered_inline(self) -> None:
        app = _make_app()
        mock = AsyncMock(
            return_value=_answer(
                [{"text": "Navigation confused participants.", "quote_ids": ["q-p1-26"]}]
            )
        )
        with _patch_llm(mock):
            r = AuthTestClient(app).post(
                "/api/dev/chat-lens/ask", json={"question": "What confused people?"}
            )
        assert r.status_code == 200
        claim = r.json()["claims"][0]
        assert claim["quote_ids"] == ["q-p1-26"]
        assert claim["invalid_quote_ids"] == []
        # The full quote payload is inline — the review affordance itself.
        assert len(claim["quotes"]) == 1
        quote = claim["quotes"][0]
        assert quote["id"] == "q-p1-26"
        assert "hamburger menu" in quote["text"]
        assert quote["where"] == "Dashboard"
        assert quote["sentiment"] == "frustration"

    def test_invented_id_is_flagged_not_rendered(self) -> None:
        """A model can invent q-p1-999. Without this check the citations
        are theatre — the feature would be worse than no feature."""
        app = _make_app()
        mock = AsyncMock(
            return_value=_answer(
                [{"text": "Everyone loved the export.", "quote_ids": ["q-p1-999"]}]
            )
        )
        with _patch_llm(mock):
            r = AuthTestClient(app).post(
                "/api/dev/chat-lens/ask", json={"question": "Did they like export?"}
            )
        assert r.status_code == 200
        claim = r.json()["claims"][0]
        assert claim["quote_ids"] == []
        assert claim["quotes"] == []
        assert claim["invalid_quote_ids"] == ["q-p1-999"]

    def test_malformed_ids_rejected_without_500(self) -> None:
        app = _make_app()
        mock = AsyncMock(
            return_value=_answer(
                [{"text": "A claim.", "quote_ids": ["banana", "q-p1-xx", "q-"]}]
            )
        )
        with _patch_llm(mock):
            r = AuthTestClient(app).post(
                "/api/dev/chat-lens/ask", json={"question": "q"}
            )
        assert r.status_code == 200
        claim = r.json()["claims"][0]
        assert claim["quotes"] == []
        assert claim["invalid_quote_ids"] == ["banana", "q-p1-xx", "q-"]

    def test_cross_project_id_rejected(self) -> None:
        """Scope check, not just syntax: a quote that exists in the DB but
        belongs to another project is not citable in this project's answer."""
        app = _make_app()
        db = app.state.db_factory()
        try:
            db.add(
                Project(
                    id=2, name="Other", slug="other",
                    input_dir="/tmp/other-in", output_dir="/tmp/other-out",
                )
            )
            db.add(
                Quote(
                    project_id=2, session_id="s9", participant_id="p9",
                    start_timecode=500.0, end_timecode=510.0,
                    text="A quote from a different study entirely.",
                    quote_type="general_context",
                )
            )
            db.commit()
        finally:
            db.close()

        mock = AsyncMock(
            return_value=_answer(
                [{"text": "Cross-project claim.", "quote_ids": ["q-p9-500"]}]
            )
        )
        with _patch_llm(mock):
            r = AuthTestClient(app).post(
                "/api/dev/chat-lens/ask",
                json={"question": "q", "project_id": 1},
            )
        assert r.status_code == 200
        claim = r.json()["claims"][0]
        assert claim["quotes"] == []
        assert claim["invalid_quote_ids"] == ["q-p9-500"]

    def test_hidden_quote_not_citable(self) -> None:
        """The corpus is the citable universe: a quote the researcher hid
        was not in context, so citing it is flagged even though it exists."""
        app = _make_app()
        db = app.state.db_factory()
        try:
            pks = _quote_pks_by_dom_id(db)
            db.add(QuoteState(quote_id=pks["q-p1-46"], is_hidden=True))
            db.commit()
        finally:
            db.close()

        mock = AsyncMock(
            return_value=_answer(
                [{"text": "Search delighted people.", "quote_ids": ["q-p1-46"]}]
            )
        )
        with _patch_llm(mock):
            r = AuthTestClient(app).post(
                "/api/dev/chat-lens/ask", json={"question": "q"}
            )
        assert r.status_code == 200
        claim = r.json()["claims"][0]
        assert claim["quotes"] == []
        assert claim["invalid_quote_ids"] == ["q-p1-46"]

    def test_unsupported_is_a_corpus_finding_not_a_refusal(self) -> None:
        app = _make_app()
        mock = AsyncMock(
            return_value=_answer(
                [], unsupported="Nothing in this study's quotes covers pricing."
            )
        )
        with _patch_llm(mock):
            r = AuthTestClient(app).post(
                "/api/dev/chat-lens/ask",
                json={"question": "What did they say about pricing?"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["claims"] == []
        assert "pricing" in body["unsupported"]

    def test_corpus_and_call_metadata_reported(self) -> None:
        app = _make_app()
        mock = AsyncMock(
            return_value=_answer([{"text": "A claim.", "quote_ids": ["q-p1-10"]}])
        )
        with _patch_llm(mock):
            r = AuthTestClient(app).post(
                "/api/dev/chat-lens/ask", json={"question": "q"}
            )
        body = r.json()
        assert body["corpus"]["quote_count"] == 4
        assert body["corpus"]["total_quotes"] == 4
        assert body["corpus"]["truncated"] is False
        assert body["corpus"]["approx_tokens"] > 0
        assert body["call"]["provider"] == "anthropic"
        assert body["call"]["model"] == "test-model"
        assert body["call"]["prompt_version"]

    def test_prompt_contains_corpus_invariants_and_question(self) -> None:
        """The user prompt carries the wrapped corpus, the invariants, and
        the question — the context-stuffed single-project route (§6)."""
        app = _make_app()
        mock = AsyncMock(return_value=_answer([]))
        with _patch_llm(mock):
            AuthTestClient(app).post(
                "/api/dev/chat-lens/ask",
                json={"question": "What about the hamburger menu?"},
            )
        assert mock.await_count == 1
        kwargs = mock.await_args.kwargs
        user_prompt = kwargs["user_prompt"]
        assert "<untrusted_corpus_" in user_prompt
        assert "[q-p1-10]" in user_prompt
        assert "exactly one report section" in user_prompt  # invariants
        assert "What about the hamburger menu?" in user_prompt
        assert kwargs["response_model"] is ChatLensAnswer


# ---------------------------------------------------------------------------
# API — input and failure edges
# ---------------------------------------------------------------------------


class TestAskEdges:
    def test_empty_question_400(self) -> None:
        app = _make_app()
        r = AuthTestClient(app).post(
            "/api/dev/chat-lens/ask", json={"question": "   "}
        )
        assert r.status_code == 400

    def test_oversized_question_400(self) -> None:
        app = _make_app()
        r = AuthTestClient(app).post(
            "/api/dev/chat-lens/ask", json={"question": "x" * 3000}
        )
        assert r.status_code == 400

    def test_missing_api_key_400_with_provider_name(self) -> None:
        app = _make_app()
        app.state.settings.anthropic_api_key = ""
        r = AuthTestClient(app).post(
            "/api/dev/chat-lens/ask", json={"question": "q"}
        )
        assert r.status_code == 400
        assert "anthropic" in r.json()["detail"]

    def test_unknown_project_404(self) -> None:
        app = _make_app()
        r = AuthTestClient(app).post(
            "/api/dev/chat-lens/ask", json={"question": "q", "project_id": 99}
        )
        assert r.status_code == 404

    def test_llm_failure_is_502_not_silent(self) -> None:
        app = _make_app()
        mock = AsyncMock(side_effect=RuntimeError("provider exploded"))
        with _patch_llm(mock):
            r = AuthTestClient(app).post(
                "/api/dev/chat-lens/ask", json={"question": "q"}
            )
        assert r.status_code == 502
        assert "RuntimeError" in r.json()["detail"]
        assert "provider exploded" in r.json()["detail"]
