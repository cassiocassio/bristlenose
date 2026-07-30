"""Tests for the chat lens — grounding core + cited-question-box API.

What the prototype is testing is not "can it answer" — it is "are the
citations honest" (docs/design-chat-lens.md §6, corrected by §5a). The
load-bearing tests are the ones where the model *lies*:

- a fabricated citation — now an out-of-range integer, because the model
  only ever sees a server-constructed index space (§5a Correction 2);
- a resolvable citation whose evidence does not support the claim — the
  support check flags it, and a dead judge degrades to "unchecked",
  never to a hidden claim (§5a Correction 1, flag-not-gate);
- a citation to a quote the researcher hid — not in the corpus, so not
  expressible.

LLM-calling paths are tested through the API with a mocked ``LLMClient``
and a test ``settings`` override on ``app.state`` — no real LLM, no
network (CI has no keys). One ask = up to two analyze calls: the answer,
then the batched support check (skipped when nothing cites).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from bristlenose.llm.structured import (
    ChatLensAnswer,
    ChatLensClaim,
    ChatLensSupportResult,
    ChatLensSupportVerdict,
)
from bristlenose.server.app import create_app
from bristlenose.server.chat_lens import format_claims_for_support_check
from bristlenose.server.grounding import (
    assemble_corpus_context,
    quote_dom_id,
    resolve_quote_ids,
    resolve_quote_indices,
)
from bristlenose.server.models import (
    Project,
    Quote,
    QuoteEdit,
    QuoteState,
)
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"

# The smoke fixture's four quotes (see server/CLAUDE.md), in corpus order:
# sections (Dashboard, Search) then themes (Onboarding gaps).
_FIXTURE_IDS_IN_ORDER = ["q-p1-10", "q-p1-26", "q-p1-46", "q-p1-66"]


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
    claims: list[dict] | None = None,
    unsupported: str = "",
    abstain_reason: str = "",
) -> ChatLensAnswer:
    return ChatLensAnswer(
        claims=[ChatLensClaim(**c) for c in (claims or [])],
        unsupported=unsupported,
        abstain_reason=abstain_reason,
    )


def _support(verdicts: list[tuple[int, bool]]) -> ChatLensSupportResult:
    return ChatLensSupportResult(
        verdicts=[
            ChatLensSupportVerdict(claim_index=i, supported=s) for i, s in verdicts
        ]
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

        assert set(corpus.quotes_by_id) == set(_FIXTURE_IDS_IN_ORDER)
        assert corpus.quote_count == 4
        assert corpus.total_quotes == 4
        assert not corpus.truncated
        # Report structure and anonymised roster are in the prompt text.
        assert "# Study: Smoke Test" in corpus.text
        assert "Speakers: p1" in corpus.text
        assert "## Section: Dashboard" in corpus.text
        assert "## Theme: Onboarding gaps" in corpus.text

    def test_citation_space_is_server_constructed_integers(self) -> None:
        """§5a Correction 2: the model sees [1]..[n] markers, never id
        strings — quotes_by_index maps them back server-side."""
        app = _make_app()
        db = app.state.db_factory()
        try:
            corpus = assemble_corpus_context(db, 1)
        finally:
            db.close()

        assert sorted(corpus.quotes_by_index) == [1, 2, 3, 4]
        for n in range(1, 5):
            assert f"- [{n}] " in corpus.text
        # DOM ids stay out of the generator-facing text entirely.
        for dom_id in _FIXTURE_IDS_IN_ORDER:
            assert dom_id not in corpus.text
        # Index order follows corpus document order.
        assert [
            corpus.quotes_by_index[n].dom_id for n in range(1, 5)
        ] == _FIXTURE_IDS_IN_ORDER

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

    def test_hidden_quotes_are_excluded_and_indices_stay_dense(self) -> None:
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
        assert corpus.hidden_excluded == 1
        assert corpus.total_quotes == 3
        # The index space stays dense 1..3 — a hidden quote has no number
        # to cite, so it is simply not expressible.
        assert sorted(corpus.quotes_by_index) == [1, 2, 3]
        assert all(
            q.dom_id != "q-p1-26" for q in corpus.quotes_by_index.values()
        )

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


class TestResolveQuoteIndices:
    def _corpus(self):
        app = _make_app()
        db = app.state.db_factory()
        try:
            return assemble_corpus_context(db, 1)
        finally:
            db.close()

    def test_fabrication_degrades_to_out_of_range_arithmetic(self) -> None:
        corpus = self._corpus()
        resolved, rejected = resolve_quote_indices([3, 99, 0, -1, 1], corpus)
        assert [q.dom_id for q in resolved] == ["q-p1-46", "q-p1-10"]
        assert rejected == [99, 0, -1]

    def test_duplicates_dropped_after_first_appearance(self) -> None:
        corpus = self._corpus()
        resolved, rejected = resolve_quote_indices([2, 2, 99, 99], corpus)
        assert [q.dom_id for q in resolved] == ["q-p1-26"]
        assert rejected == [99]

    def test_defensive_against_non_integer_garbage(self) -> None:
        """Pydantic types the field list[int], but the resolver stays safe
        against coercible strings and drops uncoercible garbage."""
        corpus = self._corpus()
        resolved, rejected = resolve_quote_indices(
            ["2", "banana", None, 4], corpus  # type: ignore[list-item]
        )
        assert [q.dom_id for q in resolved] == ["q-p1-26", "q-p1-66"]
        assert rejected == []


class TestResolveQuoteIds:
    """The stable-id seam (§7) — what the MCP workstream consumes."""

    def test_scope_is_the_corpus_not_the_database(self) -> None:
        """A quote from another project exists in the DB but not in this
        project's corpus — its id must reject."""
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
            corpus = assemble_corpus_context(db, 1)
        finally:
            db.close()

        resolved, rejected = resolve_quote_ids(
            ["q-p1-10", "q-p9-500", "banana"], corpus
        )
        assert [q.dom_id for q in resolved] == ["q-p1-10"]
        assert rejected == ["q-p9-500", "banana"]


# ---------------------------------------------------------------------------
# Support-check formatting
# ---------------------------------------------------------------------------


class TestSupportCheckFormatting:
    def test_numbers_match_claim_positions_and_uncited_skipped(self) -> None:
        from bristlenose.server.chat_lens import ClaimResult
        from bristlenose.server.grounding import CorpusQuote

        quote = CorpusQuote(
            dom_id="q-p1-10", participant_id="p1", session_id="s1",
            text="quoted words", sentiment="confusion",
        )
        claims = [
            ClaimResult(text="Uncited framing.", citation_exempt=True),
            ClaimResult(text="Cited finding.", quotes=[quote]),
        ]
        block = format_claims_for_support_check(claims)
        # Claim numbering is positional — the cited claim is Claim 1.
        assert "### Claim 1" in block
        assert "### Claim 0" not in block
        assert "Cited finding." in block
        assert '"quoted words"' in block
        assert "Uncited framing." not in block


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
        # Both layouts ship — §5a contests inline as the right default.
        assert "quotes inline" in page.text
        assert "quotes in a sidebar" in page.text

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
    def test_cited_quote_resolves_to_id_and_renders_payload(self) -> None:
        app = _make_app()
        mock = AsyncMock(
            side_effect=[
                _answer(
                    [{"text": "Navigation confused participants.", "quote_indices": [2]}]
                ),
                _support([(0, True)]),
            ]
        )
        with _patch_llm(mock):
            r = AuthTestClient(app).post(
                "/api/dev/chat-lens/ask", json={"question": "What confused people?"}
            )
        assert r.status_code == 200
        claim = r.json()["claims"][0]
        # The surface vocabulary is stable ids (§7), mapped from the index.
        assert claim["quote_ids"] == ["q-p1-26"]
        assert claim["invalid_citations"] == []
        assert claim["support"] == "supported"
        assert len(claim["quotes"]) == 1
        quote = claim["quotes"][0]
        assert quote["id"] == "q-p1-26"
        assert "hamburger menu" in quote["text"]
        assert quote["where"] == "Dashboard"
        assert quote["sentiment"] == "frustration"

    def test_fabricated_citation_is_flagged_not_rendered(self) -> None:
        """The model can only fabricate an out-of-range integer now.
        Without this check the citations are theatre."""
        app = _make_app()
        mock = AsyncMock(
            return_value=_answer(
                [{"text": "Everyone loved the export.", "quote_indices": [99]}]
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
        assert claim["invalid_citations"] == [99]
        # Nothing resolved → nothing judgeable → answer call only.
        assert mock.await_count == 1

    def test_hidden_quote_is_not_expressible(self) -> None:
        """Hiding a quote removes it from the corpus; the index space is
        dense over what remains, so citing past the end is fabrication."""
        app = _make_app()
        db = app.state.db_factory()
        try:
            pks = _quote_pks_by_dom_id(db)
            db.add(QuoteState(quote_id=pks["q-p1-66"], is_hidden=True))
            db.commit()
        finally:
            db.close()

        mock = AsyncMock(
            return_value=_answer(
                [{"text": "Onboarding needs work.", "quote_indices": [4]}]
            )
        )
        with _patch_llm(mock):
            r = AuthTestClient(app).post(
                "/api/dev/chat-lens/ask", json={"question": "q"}
            )
        assert r.status_code == 200
        claim = r.json()["claims"][0]
        assert claim["quotes"] == []
        assert claim["invalid_citations"] == [4]

    def test_support_check_flags_unsupported_claims(self) -> None:
        """§5a Correction 1: existence is not support. The judge's negative
        verdict flags the claim — it never suppresses it."""
        app = _make_app()
        mock = AsyncMock(
            side_effect=[
                _answer(
                    [
                        {"text": "Search delighted everyone.", "quote_indices": [3]},
                        {"text": "Pricing was the top complaint.", "quote_indices": [1]},
                    ]
                ),
                _support([(0, True), (1, False)]),
            ]
        )
        with _patch_llm(mock):
            r = AuthTestClient(app).post(
                "/api/dev/chat-lens/ask", json={"question": "q"}
            )
        claims = r.json()["claims"]
        assert claims[0]["support"] == "supported"
        assert claims[1]["support"] == "unsupported"
        # Flagged, not suppressed: the claim and its quotes still render.
        assert claims[1]["text"] == "Pricing was the top complaint."
        assert claims[1]["quote_ids"] == ["q-p1-10"]

    def test_dead_judge_degrades_to_unchecked_not_failure(self) -> None:
        app = _make_app()
        mock = AsyncMock(
            side_effect=[
                _answer([{"text": "A cited claim.", "quote_indices": [1]}]),
                RuntimeError("judge exploded"),
            ]
        )
        with _patch_llm(mock):
            r = AuthTestClient(app).post(
                "/api/dev/chat-lens/ask", json={"question": "q"}
            )
        assert r.status_code == 200
        claim = r.json()["claims"][0]
        assert claim["support"] == "unchecked"
        assert claim["quote_ids"] == ["q-p1-10"]

    def test_citation_exempt_connective_claims_pass_through(self) -> None:
        app = _make_app()
        mock = AsyncMock(
            side_effect=[
                _answer(
                    [
                        {
                            "text": "Two things stood out.",
                            "quote_indices": [],
                            "citation_exempt": True,
                        },
                        {"text": "The menu frustrated people.", "quote_indices": [2]},
                    ]
                ),
                _support([(1, True)]),
            ]
        )
        with _patch_llm(mock):
            r = AuthTestClient(app).post(
                "/api/dev/chat-lens/ask", json={"question": "q"}
            )
        claims = r.json()["claims"]
        assert claims[0]["citation_exempt"] is True
        assert claims[0]["support"] == ""  # nothing to judge, and that's fine
        assert claims[1]["citation_exempt"] is False
        assert claims[1]["support"] == "supported"

    def test_abstention_carries_a_reason(self) -> None:
        app = _make_app()
        mock = AsyncMock(
            return_value=_answer(
                [],
                unsupported="Nothing in this study's quotes covers pricing.",
                abstain_reason="no_evidence",
            )
        )
        with _patch_llm(mock):
            r = AuthTestClient(app).post(
                "/api/dev/chat-lens/ask",
                json={"question": "What did they say about pricing?"},
            )
        body = r.json()
        assert body["claims"] == []
        assert body["abstain_reason"] == "no_evidence"
        assert "pricing" in body["unsupported"]

    def test_invented_abstain_reason_normalised(self) -> None:
        app = _make_app()
        mock = AsyncMock(
            return_value=_answer([], unsupported="Off the map.", abstain_reason="vibes")
        )
        with _patch_llm(mock):
            r = AuthTestClient(app).post(
                "/api/dev/chat-lens/ask", json={"question": "q"}
            )
        assert r.json()["abstain_reason"] == "no_evidence"

    def test_answered_question_has_empty_abstain_reason(self) -> None:
        app = _make_app()
        mock = AsyncMock(
            side_effect=[
                _answer([{"text": "A claim.", "quote_indices": [1]}]),
                _support([(0, True)]),
            ]
        )
        with _patch_llm(mock):
            r = AuthTestClient(app).post(
                "/api/dev/chat-lens/ask", json={"question": "q"}
            )
        assert r.json()["abstain_reason"] == ""

    def test_corpus_and_call_metadata_reported(self) -> None:
        app = _make_app()
        mock = AsyncMock(
            side_effect=[
                _answer([{"text": "A claim.", "quote_indices": [1]}]),
                _support([(0, True)]),
            ]
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

    def test_prompt_carries_corpus_invariants_question_and_restated_rules(self) -> None:
        """The context-stuffed single-project route, §5a-shaped: integer
        markers in the corpus, and the core rules restated *after* the
        corpus (long instructions can silently degrade; end placement is
        the reliable slot)."""
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
        assert "- [2] " in user_prompt  # server-constructed citation markers
        assert "q-p1-10" not in user_prompt  # ids never reach the model
        assert "exactly one report section" in user_prompt  # invariants
        assert "What about the hamburger menu?" in user_prompt
        # Restated after the corpus: the restatement sits below the question.
        assert user_prompt.index("Core rules, restated") > user_prompt.index(
            "What about the hamburger menu?"
        )
        assert kwargs["response_model"] is ChatLensAnswer

    def test_support_check_prompt_is_wrapped_and_scoped(self) -> None:
        app = _make_app()
        mock = AsyncMock(
            side_effect=[
                _answer([{"text": "The menu frustrated people.", "quote_indices": [2]}]),
                _support([(0, True)]),
            ]
        )
        with _patch_llm(mock):
            AuthTestClient(app).post(
                "/api/dev/chat-lens/ask", json={"question": "q"}
            )
        assert mock.await_count == 2
        support_kwargs = mock.await_args_list[1].kwargs
        assert support_kwargs["response_model"] is ChatLensSupportResult
        support_prompt = support_kwargs["user_prompt"]
        assert "<untrusted_claims_" in support_prompt
        assert "The menu frustrated people." in support_prompt
        assert "hamburger menu" in support_prompt  # the cited evidence text


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
