"""Tests for the MCP endpoint (§9a spike) — tools, auth, and hard exclusions.

Layers:
- direct tool-function tests against the smoke fixture (business behaviour:
  report-view semantics, filter validation, framework resolution);
- the anonymisation sweep (sentinel names seeded in-test — the smoke fixture
  ships no names, so without seeding the sweep would pass vacuously);
- mechanical pins for the design doc's hard exclusions (read-only module,
  no .bristlenose reach, instructions carry every invariant);
- protocol round-trips through the real ASGI stack with lifespan running
  (auth, explainer, per-tool serialization — datetimes fail live, not in
  direct-call tests).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.grounding import INVARIANTS, load_signals
from bristlenose.server.mcp_server import (
    LIVE_CODEBOOK_ID,
    SEARCH_LIMIT_CAP,
    ToolInputError,
    _tool_get_framework,
    _tool_get_project_overview,
    _tool_get_signals,
    _tool_search_quotes,
    build_instructions,
)
from bristlenose.server.models import (
    ClusterQuote,
    CodebookGroup,
    Person,
    ProjectCodebookGroup,
    Quote,
    QuoteEdit,
    QuoteState,
    QuoteTag,
    ScreenCluster,
    SessionSpeaker,
    TagDefinition,
    TagPrompt,
)
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_SERVER_DIR = Path(__file__).parent.parent / "bristlenose" / "server"

# Smoke fixture quotes: q-p1-10 (Dashboard/confusion), q-p1-26
# (Dashboard/frustration), q-p1-46 (Search/delight), q-p1-66
# (Onboarding gaps/frustration).


@pytest.fixture()
def app_fx():
    return create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")


@pytest.fixture()
def db(app_fx):
    session = app_fx.state.db_factory()
    yield session
    session.close()


def _search(db, **kwargs):
    defaults = dict(
        project_id=1, query=None, tag=None, sentiment=None, participant=None,
        section=None, theme=None, starred_only=False, limit=20, offset=0,
    )
    defaults.update(kwargs)
    return _tool_search_quotes(db, **defaults)


def _seed_second_frustration(db) -> None:
    """Give Dashboard|frustration two quotes so a signal cell forms."""
    dashboard = db.query(ScreenCluster).filter_by(screen_label="Dashboard").one()
    extra = Quote(
        project_id=1,
        session_id="s1",
        participant_id="p1",
        start_timecode=80.0,
        end_timecode=88.0,
        text="Honestly the dashboard buttons made no sense to me at all.",
        quote_type="screen_specific",
        sentiment="frustration",
        intensity=2,
    )
    db.add(extra)
    db.flush()
    db.add(ClusterQuote(cluster_id=dashboard.id, quote_id=extra.id))
    db.commit()


def _seed_tagged_group(db) -> None:
    """A hand-rolled group with one tag applied to BOTH Dashboard quotes,
    so the tags lens has a Dashboard|group cell of two."""
    group = CodebookGroup(name="Trust wobbles", subtitle="", colour_set="trust")
    db.add(group)
    db.flush()
    db.add(ProjectCodebookGroup(project_id=1, codebook_group_id=group.id))
    tag = TagDefinition(codebook_group_id=group.id, name="hesitation")
    db.add(tag)
    db.flush()
    for start in (10, 26):
        q = (
            db.query(Quote)
            .filter(Quote.start_timecode >= start, Quote.start_timecode < start + 1)
            .one()
        )
        db.add(QuoteTag(quote_id=q.id, tag_definition_id=tag.id))
    db.commit()


def _hide(db, dom_start: float, participant: str = "p1") -> None:
    q = (
        db.query(Quote)
        .filter(
            Quote.participant_id == participant,
            Quote.start_timecode >= dom_start,
            Quote.start_timecode < dom_start + 1,
        )
        .one()
    )
    db.add(QuoteState(quote_id=q.id, is_hidden=True))
    db.commit()


class TestOverview:
    def test_shape_and_counts(self, db) -> None:
        overview = _tool_get_project_overview(db, 1, {"outcome": "completed"})
        assert overview["quotes"]["visible"] == 4
        assert overview["quotes"]["hidden_by_researcher"] == 0
        assert overview["sessions"]["count"] == 1
        assert overview["last_run"] == {"outcome": "completed"}
        labels = {s["label"] for s in overview["sections"]}
        assert "Dashboard" in labels
        dashboard = next(s for s in overview["sections"] if s["label"] == "Dashboard")
        assert dashboard["quote_count"] == 2

    def test_participants_are_codes_with_roles(self, db) -> None:
        overview = _tool_get_project_overview(db, 1, None)
        speakers = {s["code"]: s["role"] for s in overview["participants"]["speakers"]}
        assert "p1" in speakers
        assert set(speakers.values()) <= {"participant", "researcher", "observer", "moderator"}

    def test_available_frameworks_include_live_codebook(self, db) -> None:
        overview = _tool_get_project_overview(db, 1, None)
        assert LIVE_CODEBOOK_ID in overview["codebook"]["available_framework_ids"]

    def test_hidden_quote_leaves_counts(self, db) -> None:
        _hide(db, 26)
        overview = _tool_get_project_overview(db, 1, None)
        assert overview["quotes"]["visible"] == 3
        assert overview["quotes"]["hidden_by_researcher"] == 1
        dashboard = next(s for s in overview["sections"] if s["label"] == "Dashboard")
        assert dashboard["quote_count"] == 1
        # The buckets are DISJOINT, and the section counts live in the same
        # universe as `visible`. A reader that sums them gets a corpus that
        # doesn't exist — which happened: 14 + 7 was announced as "21 quotes",
        # and the phantom 7 was then reported to the researcher as unsectioned
        # coverage in their own study.
        assert sum(s["quote_count"] for s in overview["sections"]) <= overview["quotes"]["visible"]

    def test_unknown_project_lists_valid_ids(self, db) -> None:
        with pytest.raises(ToolInputError, match=r"unknown project_id 7.*\[1\]"):
            _tool_get_project_overview(db, 7, None)

    def test_empty_db_is_honest(self) -> None:
        app = create_app(dev=True, db_url="sqlite://")
        session = app.state.db_factory()
        try:
            with pytest.raises(ToolInputError, match="no analysed data yet"):
                _tool_get_project_overview(session, 1, None)
        finally:
            session.close()


class TestSearchQuotes:
    def test_returns_all_visible(self, db) -> None:
        result = _search(db)
        assert result["total_matched"] == 4
        assert result["has_more"] is False
        assert {q["quote_id"] for q in result["quotes"]} == {
            "q-p1-10", "q-p1-26", "q-p1-46", "q-p1-66",
        }

    def test_sentiment_filter(self, db) -> None:
        result = _search(db, sentiment="frustration")
        assert result["total_matched"] == 2

    def test_mistyped_sentiment_errors_with_vocabulary(self, db) -> None:
        with pytest.raises(ToolInputError, match="frustration"):
            _search(db, sentiment="frustrated")

    def test_participant_filter_is_case_insensitive(self, db) -> None:
        assert _search(db, participant="P1")["total_matched"] == 4
        assert _search(db, participant="p9")["total_matched"] == 0

    def test_hidden_quotes_are_excluded(self, db) -> None:
        _hide(db, 26)
        result = _search(db)
        assert result["total_matched"] == 3
        assert "q-p1-26" not in {q["quote_id"] for q in result["quotes"]}

    def test_researcher_edit_wins(self, db) -> None:
        q = db.query(Quote).filter(Quote.start_timecode >= 10, Quote.start_timecode < 11).one()
        db.add(QuoteEdit(quote_id=q.id, edited_text="The dashboard confused me (edited)."))
        db.commit()
        result = _search(db, query="(edited)")
        assert result["total_matched"] == 1
        assert result["quotes"][0]["quote_id"] == "q-p1-10"

    def test_deleted_badge_suppresses_sentiment_in_rows_and_filter(self, db) -> None:
        from bristlenose.server.models import DeletedBadge

        q = db.query(Quote).filter(Quote.start_timecode >= 26, Quote.start_timecode < 27).one()
        db.add(DeletedBadge(quote_id=q.id, sentiment="frustration"))
        db.commit()
        row = next(r for r in _search(db)["quotes"] if r["quote_id"] == "q-p1-26")
        assert row["sentiment"] is None
        # The filter agrees with the display: only q-p1-66 still matches.
        assert _search(db, sentiment="frustration")["total_matched"] == 1

    def test_starred_only(self, db) -> None:
        q = db.query(Quote).filter(Quote.start_timecode >= 46, Quote.start_timecode < 47).one()
        db.add(QuoteState(quote_id=q.id, is_starred=True))
        db.commit()
        result = _search(db, starred_only=True)
        assert result["total_matched"] == 1
        assert result["quotes"][0]["starred"] is True

    def test_limit_is_clamped_and_paginated(self, db) -> None:
        result = _search(db, limit=99999)
        assert result["returned"] <= SEARCH_LIMIT_CAP
        page = _search(db, limit=2)
        assert page["returned"] == 2
        assert page["has_more"] is True
        assert page["next_offset"] == 2
        rest = _search(db, limit=2, offset=2)
        assert rest["has_more"] is False
        assert {q["quote_id"] for q in page["quotes"]}.isdisjoint(
            {q["quote_id"] for q in rest["quotes"]}
        )


class TestSignals:
    def test_unknown_lens_errors_with_vocabulary(self, db) -> None:
        with pytest.raises(ToolInputError, match="sentiment"):
            _tool_get_signals(db, 1, "vibes", 10)

    def test_sentiment_signal_over_curated_corpus(self, db) -> None:
        _seed_second_frustration(db)
        result = _tool_get_signals(db, 1, "sentiment", 10)
        cell = next(
            (s for s in result["signals"]
             if s["location"] == "Dashboard" and s["sentiment"] == "frustration"),
            None,
        )
        assert cell is not None
        assert cell["quote_count"] == 2
        assert len(cell["supporting_quotes"]) <= 3
        assert cell["supporting_quotes"][0]["quote_id"].startswith("q-p1-")

    def test_deleted_badge_drops_out_of_sentiment_signals(self, db) -> None:
        from bristlenose.server.models import DeletedBadge

        _seed_second_frustration(db)
        q = db.query(Quote).filter(Quote.start_timecode >= 80, Quote.start_timecode < 81).one()
        db.add(DeletedBadge(quote_id=q.id, sentiment="frustration"))
        db.commit()
        result = _tool_get_signals(db, 1, "sentiment", 10)
        assert not any(
            s["location"] == "Dashboard" and s["sentiment"] == "frustration"
            and s["quote_count"] == 2
            for s in result["signals"]
        ), "a de-badged quote must not drive a sentiment cell"

    def test_tool_and_route_diverge_on_hidden_quotes_by_design(self, app_fx, db) -> None:
        """Report view vs engine view — the divergence is intentional (review
        contradiction ruling A): hiding a quote changes the tool's signals
        and deliberately does NOT change the analysis route's."""
        _seed_second_frustration(db)
        before = _tool_get_signals(db, 1, "sentiment", 10)
        assert any(
            s["location"] == "Dashboard" and s["sentiment"] == "frustration"
            and s["quote_count"] == 2
            for s in before["signals"]
        )
        _hide(db, 80)
        after = _tool_get_signals(db, 1, "sentiment", 10)
        assert not any(
            s["location"] == "Dashboard" and s["sentiment"] == "frustration"
            and s["quote_count"] == 2
            for s in after["signals"]
        )
        route = AuthTestClient(app_fx).get("/api/projects/1/analysis/sentiment").json()
        assert any(
            s["location"] == "Dashboard" and s["sentiment"] == "frustration"
            and s["count"] == 2
            for s in route["signals"]
        ), "engine view should still count the hidden quote"

    def test_numbers_match_direct_analysis_call(self, db) -> None:
        _seed_second_frustration(db)
        tool = _tool_get_signals(db, 1, "sentiment", 10)
        direct = load_signals(db, 1, "sentiment", top_n=10)
        by_key = {
            (s.location, s.source_type, s.sentiment): s for s in direct.signals
        }
        for card in tool["signals"]:
            s = by_key[(card["location"], card["source_type"], card["sentiment"])]
            assert card["quote_count"] == s.count
            assert card["composite_signal"] == round(s.composite_signal, 4)
            assert card["n_eff"] == round(s.n_eff, 2)


class TestTagsLensSignals:
    """The tags-lens branch of load_signals with real data — a matrix-assembly
    bug there returns an empty list, not an exception (Bach, impl-review)."""

    def test_accepted_tags_form_a_signal_cell(self, db) -> None:
        _seed_tagged_group(db)
        result = _tool_get_signals(db, 1, "tags", 10)
        cell = next(
            (s for s in result["signals"]
             if s["location"] == "Dashboard" and s["group"] == "Trust wobbles"),
            None,
        )
        assert cell is not None
        assert cell["quote_count"] == 2
        assert cell["colour_set"] == "trust"
        assert "hesitation" in cell["supporting_quotes"][0]["tags"]

    def test_hidden_quote_drops_out_of_tags_lens(self, db) -> None:
        _seed_tagged_group(db)
        _hide(db, 26)
        result = _tool_get_signals(db, 1, "tags", 10)
        assert not any(
            s["location"] == "Dashboard" and s["group"] == "Trust wobbles"
            and s["quote_count"] == 2
            for s in result["signals"]
        )


class TestElaborationCache:
    """The cache is the ONLY elaboration source under 'no LLM spend' — an
    always-miss would pass every other test while silently dropping the
    feature (silent-failure-hunter, impl-review)."""

    def _seed_cache_row(self, db) -> None:
        from bristlenose.server.elaboration import (
            compute_content_hash,
            compute_signal_key,
        )
        from bristlenose.server.models import ElaborationCache

        sig = next(
            s for s in load_signals(db, 1, "sentiment", top_n=10).signals
            if s.location == "Dashboard" and s.sentiment == "frustration"
        )
        # Write-path derivation: duplicates preserved (elaboration.py:300) —
        # this is what pins the reader's derivation against the generate path.
        texts = [q.text for q in sig.quotes]
        tags = [t for q in sig.quotes for t in (q.tag_names or [])]
        db.add(ElaborationCache(
            project_id=1,
            signal_key=compute_signal_key(sig.source_type, sig.location, sig.sentiment),
            content_hash=compute_content_hash(texts, tags),
            signal_name="Dashboard doubt",
            pattern="gap",
            elaboration="Both participants stall on the dashboard.",
        ))
        db.commit()

    def test_cache_hit_attaches_elaboration(self, db) -> None:
        _seed_second_frustration(db)
        self._seed_cache_row(db)
        card = next(
            s for s in _tool_get_signals(db, 1, "sentiment", 10)["signals"]
            if s["location"] == "Dashboard" and s["sentiment"] == "frustration"
        )
        assert card["elaboration"]["signal_name"] == "Dashboard doubt"
        assert card["elaboration"]["pattern"] == "gap"

    def test_content_drift_degrades_to_a_miss_never_a_wrong_hit(self, db) -> None:
        _seed_second_frustration(db)
        self._seed_cache_row(db)
        # A researcher edit changes the curated text → hash diverges.
        q = db.query(Quote).filter(Quote.start_timecode >= 26, Quote.start_timecode < 27).one()
        db.add(QuoteEdit(quote_id=q.id, edited_text="Edited after elaboration."))
        db.commit()
        card = next(
            s for s in _tool_get_signals(db, 1, "sentiment", 10)["signals"]
            if s["location"] == "Dashboard" and s["sentiment"] == "frustration"
        )
        assert "elaboration" not in card


class TestFramework:
    def test_unknown_id_lists_valid_including_codebook(self, db) -> None:
        with pytest.raises(ToolInputError, match=LIVE_CODEBOOK_ID):
            _tool_get_framework(db, 1, "not-a-framework")

    def test_template_carries_the_stance(self, db) -> None:
        result = _tool_get_framework(db, 1, "uxr")
        assert result["kind"] == "template"
        assert result["groups"], "template should have groups"
        some_tag = result["groups"][0]["tags"][0]
        assert {"name", "definition", "apply_when", "not_this"} <= set(some_tag)
        assert result["applied_to_project"] is False

    def test_live_codebook_with_cultivated_boundaries(self, db) -> None:
        group = CodebookGroup(name="Trust wobbles", subtitle="", colour_set="trust")
        db.add(group)
        db.flush()
        db.add(ProjectCodebookGroup(project_id=1, codebook_group_id=group.id))
        tag = TagDefinition(codebook_group_id=group.id, name="hesitation")
        db.add(tag)
        db.flush()
        db.add(TagPrompt(
            tag_definition_id=tag.id,
            definition="Confidence dips mid-task",
            apply_when="The participant pauses or second-guesses the system",
            not_this="General scepticism about software",
            status="active",
        ))
        q = db.query(Quote).filter(Quote.start_timecode >= 26, Quote.start_timecode < 27).one()
        db.add(QuoteTag(quote_id=q.id, tag_definition_id=tag.id))
        db.commit()

        result = _tool_get_framework(db, 1, LIVE_CODEBOOK_ID)
        assert result["kind"] == "live_codebook"
        group_out = next(g for g in result["groups"] if g["name"] == "Trust wobbles")
        tag_out = next(t for t in group_out["tags"] if t["name"] == "hesitation")
        assert tag_out["origin"] == "hand-rolled"
        assert tag_out["usage_count"] == 1
        assert tag_out["boundaries"]["cultivated"] is True
        assert tag_out["boundaries"]["not_this"] == "General scepticism about software"


class TestAnonymisationSweep:
    """With Anonymise ON, no name-shaped string reaches any tool payload.

    The §7 boundary is now the researcher's per-project switch (per-surface
    sticky, like the export toggles). This sweep pins the ON position;
    TestNamesFollowTheSwitch pins the default (off = names in the overview,
    codes everywhere else)."""

    SENTINEL_FULL = "Zebediah Quackenbush"
    SENTINEL_SHORT = "Zebediah"
    SENTINEL_FILE = "zebediah-quackenbush.mov"
    SENTINEL_PATH = "/Users/zebtest/Clients/AcmeCorp"

    def _seed_names(self, db) -> None:
        from bristlenose.server.models import Project, SourceFile
        from bristlenose.server.models import Session as SessionModel

        persons = db.query(Person).all()
        assert persons, "fixture import should create Person rows"
        for p in persons:
            p.full_name = self.SENTINEL_FULL
            p.short_name = self.SENTINEL_SHORT
            p.role_title = "Chief Quacking Officer"
        for sp in db.query(SessionSpeaker).all():
            sp.source_file = self.SENTINEL_FILE
        # Path-shaped sentinels too: with the §8 route gate out of scope,
        # this sweep IS the coverage for filesystem-path leakage.
        project = db.query(Project).one()
        project.input_dir = self.SENTINEL_PATH
        project.output_dir = self.SENTINEL_PATH + "/bristlenose-output"
        for s in db.query(SessionModel).all():
            s.thumbnail_path = self.SENTINEL_PATH + "/thumbs/zeb.jpg"
        for f in db.query(SourceFile).all():
            f.path = self.SENTINEL_PATH + "/interviews/zeb.mov"
        project.mcp_anonymise = True  # the position this sweep pins
        db.commit()
        # Precondition — without this the sweep passes vacuously.
        assert any(p.full_name for p in db.query(Person).all())

    def test_no_names_in_any_tool_payload(self, db) -> None:
        self._seed_names(db)
        _seed_second_frustration(db)
        payloads = [
            _tool_get_project_overview(db, 1, None),
            _search(db),
            _tool_get_signals(db, 1, "sentiment", 10),
            _tool_get_signals(db, 1, "tags", 10),
            _tool_get_framework(db, 1, LIVE_CODEBOOK_ID),
        ]
        blob = json.dumps(payloads, default=str).casefold()
        assert "zebediah" not in blob
        assert "quackenbush" not in blob
        assert "quacking" not in blob  # Person.role_title free text stays out too
        assert "zebtest" not in blob  # no filesystem paths either
        assert "/users/" not in blob
        assert ".mov" not in blob
        assert ".jpg" not in blob


class TestNamesFollowTheSwitch:
    """Anonymise off (the default): names ride the overview speaker map only
    — quotes keep codes as the citation currency."""

    def _name_people(self, db) -> None:
        for i, p in enumerate(db.query(Person).all()):
            p.full_name = f"Jane Example{i}"
            p.short_name = f"Jane{i}"
        db.commit()

    def test_default_puts_names_in_overview_speakers_only(self, db) -> None:
        self._name_people(db)
        overview = _tool_get_project_overview(db, 1, None)
        by_code = {s["code"]: s for s in overview["participants"]["speakers"]}
        assert any("name" in s for s in by_code.values())
        assert by_code["p1"]["name"].startswith("Jane")
        # Quotes still cite codes — names never enter search payloads.
        blob = json.dumps(_search(db), default=str)
        assert "Jane" not in blob

    def test_flipping_the_switch_takes_effect_next_call(self, db) -> None:
        from bristlenose.server.models import Project

        self._name_people(db)
        project = db.query(Project).one()
        project.mcp_anonymise = True
        db.commit()
        overview = _tool_get_project_overview(db, 1, None)
        assert all("name" not in s for s in overview["participants"]["speakers"])
        # ...and back, no restart — read at call time.
        project.mcp_anonymise = False
        db.commit()
        overview = _tool_get_project_overview(db, 1, None)
        assert any("name" in s for s in overview["participants"]["speakers"])

    def test_desktop_global_env_switch_wins_both_ways(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BRISTLENOSE_MCP_ANONYMISE present = the desktop's v1 GLOBAL
        switch; the per-project DB flag is ignored entirely (decided
        1 Aug 2026 — one switch, not a per-project matrix)."""
        from bristlenose.server.models import Project

        self._name_people(db)
        project = db.query(Project).one()

        # Global ON beats a DB flag that says names.
        project.mcp_anonymise = False
        db.commit()
        monkeypatch.setenv("BRISTLENOSE_MCP_ANONYMISE", "1")
        overview = _tool_get_project_overview(db, 1, None)
        assert all("name" not in s for s in overview["participants"]["speakers"])

        # Global OFF beats a DB flag that says anonymise — desktop
        # behaviour is purely the global preference.
        project.mcp_anonymise = True
        db.commit()
        monkeypatch.setenv("BRISTLENOSE_MCP_ANONYMISE", "0")
        overview = _tool_get_project_overview(db, 1, None)
        assert any("name" in s for s in overview["participants"]["speakers"])

        # Env absent (the CLI) → DB semantics, unchanged.
        monkeypatch.delenv("BRISTLENOSE_MCP_ANONYMISE")
        overview = _tool_get_project_overview(db, 1, None)
        assert all("name" not in s for s in overview["participants"]["speakers"])


class TestAgentSettingsAPI:
    """The sheet's read/write path for the per-project Anonymise switch."""

    def test_round_trip_reaches_the_tools(self, app_fx) -> None:
        client = AuthTestClient(app_fx)
        assert client.get("/api/projects/1/agent-settings").json() == {
            "anonymise": False,  # the export-precedent default
        }
        assert client.put(
            "/api/projects/1/agent-settings", json={"anonymise": True}
        ).status_code == 200
        assert client.get("/api/projects/1/agent-settings").json() == {
            "anonymise": True,
        }
        # The switch the API set is the one the tools read.
        db = app_fx.state.db_factory()
        try:
            for p in db.query(Person).all():
                p.full_name = "Jane Example"
            db.commit()
            overview = _tool_get_project_overview(db, 1, None)
            assert all(
                "name" not in sp for sp in overview["participants"]["speakers"]
            )
        finally:
            db.close()

    def test_unknown_project_404s(self, app_fx) -> None:
        client = AuthTestClient(app_fx)
        assert client.get("/api/projects/9/agent-settings").status_code == 404


class TestMechanicalPins:
    """Cheap source-level guards for the stated hard exclusions."""

    def test_mcp_modules_never_write(self) -> None:
        for name in ("mcp_server.py", "grounding.py"):
            source = (_SERVER_DIR / name).read_text(encoding="utf-8")
            assert "db.add(" not in source, f"{name} must stay read-only"
            assert ".commit(" not in source, f"{name} must stay read-only"
            assert ".delete(" not in source, f"{name} must stay read-only"
            assert ".flush(" not in source, f"{name} must stay read-only"

    def test_mcp_module_never_reaches_dot_bristlenose(self) -> None:
        source = (_SERVER_DIR / "mcp_server.py").read_text(encoding="utf-8")
        assert ".bristlenose" not in source.replace("bristlenose.log", "")
        assert "pii_summary" not in source
        assert "llm-calls" not in source

    def test_mcp_module_never_reads_reidentifying_tables(self) -> None:
        source = (_SERVER_DIR / "mcp_server.py").read_text(encoding="utf-8")
        assert "TagPromptDecision" not in source  # reasons are local-only
        # Names load only through grounding.resolve_speaker_names (the one
        # gated path, honouring the project's Anonymise switch) — never
        # directly from this module.
        assert "Person" not in source

    def test_instructions_contain_every_invariant(self) -> None:
        instructions = build_instructions()
        for statement in INVARIANTS:
            assert statement in instructions

    def test_invariants_cover_the_brief(self) -> None:
        blob = " ".join(INVARIANTS).casefold()
        assert "exactly one report section" in blob
        assert "comparable within one" in blob
        assert "never join a speaker" in blob
        assert "denominators" in blob
        assert "general knowledge" in blob


_PROTO_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def _rpc(client: TestClient, token: str, method: str, params: dict, id_: int = 1):
    return client.post(
        "/mcp/",
        headers={"Authorization": f"Bearer {token}", **_PROTO_HEADERS},
        json={"jsonrpc": "2.0", "id": id_, "method": method, "params": params},
    )


class TestProtocol:
    """Through the real ASGI stack — lifespan, auth, serialization."""

    @pytest.fixture()
    def live(self):
        # Function-scoped and freshly built: the session manager's run() is
        # once-per-instance, so apps must not be shared across `with` blocks.
        app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
        app.state.auth_token = "test-mcp-token"
        with TestClient(app, base_url="http://127.0.0.1:8150") as client:
            yield app, client

    def test_auth_is_bearer_only(self, live) -> None:
        app, client = live
        assert client.post("/mcp/", json={}).status_code == 401
        cookie_only = client.post(
            "/mcp/", cookies={"bristlenose_auth": "test-mcp-token"}, json={},
        )
        assert cookie_only.status_code == 401, "/mcp must ignore the auth cookie"
        # A tokenless GET that is NOT browser-shaped must 401 too — the
        # explainer exemption is text/html-only, not a GET-wide hole.
        assert client.get("/mcp/", headers={"Accept": "*/*"}).status_code == 401
        assert client.get(
            "/mcp/", headers={"Accept": "text/event-stream"},
        ).status_code == 401
        assert client.get(
            "/mcp/", headers={"Accept": "text/html, text/event-stream"},
        ).status_code == 401

    def test_browser_click_gets_explainer_without_token(self, live) -> None:
        app, client = live
        resp = client.get("/mcp/", headers={"Accept": "text/html"})
        assert resp.status_code == 200
        assert "MCP endpoint" in resp.text
        assert "/report/" in resp.text
        assert "test-mcp-token" not in resp.text

    def test_initialize_and_both_lifespan_halves(self, live) -> None:
        app, client = live
        resp = _rpc(client, "test-mcp-token", "initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "0"},
        })
        assert resp.status_code == 200
        assert resp.json()["result"]["serverInfo"]["name"] == "bristlenose"
        # The 200 above IS the composition proof: a lost session-manager
        # lifespan makes every protocol call 500 ("Task group is not
        # initialized"). last_run only proves the watcher INSTALL path ran
        # (it's set synchronously in create_app) — the watcher's own runtime
        # behaviour is covered by tests/test_serve_event_watcher.py.
        assert app.state.last_run is not None
        assert app.state.mcp_mounted is True

    def test_every_tool_serializes_through_the_protocol(self, live) -> None:
        app, client = live
        # Seed a session date so the overview's isoformat branch serializes
        # through the protocol (the fixture ships undated sessions).
        from datetime import datetime

        from bristlenose.server.models import Session as SessionModel

        session = app.state.db_factory()
        try:
            row = session.query(SessionModel).first()
            row.session_date = datetime(2026, 3, 1, 10, 30)
            session.commit()
        finally:
            session.close()

        calls = [
            ("get_project_overview", {"project_id": 1}),
            ("search_quotes", {"project_id": 1, "limit": 3}),
            ("get_signals", {"project_id": 1, "lens": "sentiment"}),
            ("get_signals", {"project_id": 1, "lens": "tags"}),
            ("get_framework", {"project_id": 1, "framework_id": "uxr"}),
            ("get_framework", {"project_id": 1, "framework_id": LIVE_CODEBOOK_ID}),
        ]
        for i, (name, arguments) in enumerate(calls, start=10):
            resp = _rpc(client, "test-mcp-token", "tools/call",
                        {"name": name, "arguments": arguments}, id_=i)
            assert resp.status_code == 200, name
            result = resp.json()["result"]
            assert not result.get("isError"), f"{name}: {result}"

    def test_unexpected_exception_is_sanitised_and_logged(
        self, live, monkeypatch, caplog,
    ) -> None:
        """The one mechanical guard on the wrapper's security purpose:
        str(exc) — which carries SQL and filesystem paths — never reaches
        the model; the traceback lands in the log instead."""
        import logging as _logging

        import bristlenose.server.mcp_server as m

        def _boom(db, project_id, last_run):
            raise RuntimeError("/Users/secret/Clients/acme/state/bristlenose.db exploded")

        monkeypatch.setattr(m, "_tool_get_project_overview", _boom)
        app, client = live
        with caplog.at_level(_logging.ERROR, logger="bristlenose.server.mcp_server"):
            resp = _rpc(client, "test-mcp-token", "tools/call",
                        {"name": "get_project_overview", "arguments": {"project_id": 1}},
                        id_=50)
        result = resp.json()["result"]
        assert result.get("isError") is True
        blob = json.dumps(result)
        assert "/Users/secret" not in blob
        assert "exploded" not in blob
        assert "bristlenose.log" in blob
        assert any("mcp_tool_failed" in r.message for r in caplog.records)

    def test_tool_schemas_take_no_filesystem_paths(self, live) -> None:
        app, client = live
        resp = _rpc(client, "test-mcp-token", "tools/list", {}, id_=2)
        tools = {t["name"]: t for t in resp.json()["result"]["tools"]}
        assert set(tools) == {
            "get_project_overview", "search_quotes", "get_signals", "get_framework",
        }
        allowed = {
            "project_id", "query", "tag", "sentiment", "participant", "section",
            "theme", "starred_only", "limit", "offset", "lens", "framework_id",
        }
        for name, tool in tools.items():
            params = set(tool["inputSchema"].get("properties", {}))
            assert params <= allowed, f"{name} grew params outside the allowlist"

    def test_openapi_is_unaffected_by_the_mount(self, live) -> None:
        app, client = live
        paths = app.openapi()["paths"]
        assert not any(p.startswith("/mcp") for p in paths)


class TestCliConnectBlock:
    """The printed connect block stays vendor-neutral (review Finding 18 —
    a reversed decision; nothing else would catch a vendor command creeping
    back into product output)."""

    def test_prints_primitives_and_docs_url_never_a_vendor_command(
        self, capsys, monkeypatch,
    ) -> None:
        monkeypatch.setenv("_BRISTLENOSE_AUTH_TOKEN", "tok-abc123")
        from bristlenose.cli import _print_mcp_connect

        _print_mcp_connect(8150)
        out = capsys.readouterr().out
        assert "http://127.0.0.1:8150/mcp/" in out
        assert "Authorization: Bearer tok-abc123" in out
        assert "bristlenose.app/docs/connect-an-agent" in out
        assert "claude mcp add" not in out
        assert "codex mcp add" not in out

    def test_pre_mints_token_when_none_exists(self, capsys, monkeypatch) -> None:
        """The run path prints before create_app — the helper must mint so
        the header is never silently absent (impl-review finding 31)."""
        import os

        from bristlenose.cli import _print_mcp_connect

        monkeypatch.delenv("_BRISTLENOSE_AUTH_TOKEN", raising=False)
        _print_mcp_connect(8150)
        out = capsys.readouterr().out
        assert "Authorization: Bearer " in out
        minted = os.environ.get("_BRISTLENOSE_AUTH_TOKEN", "")
        assert len(minted) >= 40  # token_urlsafe(32)
        assert minted in out  # printed header IS the one create_app will serve

    def test_unavailable_variant_names_the_fix(self, capsys, monkeypatch) -> None:
        import sys

        from bristlenose.cli import _print_mcp_connect

        # A None entry makes `import mcp` raise ImportError — the same
        # probe the mount gate uses, so this exercises the real branch.
        monkeypatch.setitem(sys.modules, "mcp", None)
        _print_mcp_connect(8150)
        out = capsys.readouterr().out
        assert "unavailable" in out
        assert "bristlenose[mcp]" in out


class TestScopedMcpToken:
    """The desktop injects _BRISTLENOSE_MCP_TOKEN — the one credential that
    leaves the trust boundary. It must open /mcp and nothing else, and the
    server token must stop opening /mcp when a scoped token exists."""

    @pytest.fixture()
    def scoped(self, monkeypatch):
        monkeypatch.setenv("_BRISTLENOSE_MCP_TOKEN", "durable-mcp-token")
        app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
        app.state.auth_token = "rotating-server-token"
        with TestClient(app, base_url="http://127.0.0.1:8150") as client:
            yield client

    def test_mcp_token_opens_mcp_only(self, scoped) -> None:
        ok = _rpc(scoped, "durable-mcp-token", "tools/call",
                  {"name": "get_project_overview", "arguments": {}})
        assert ok.status_code == 200
        # The same credential must NOT reach the persons endpoint or any
        # other /api route — that is the proven leak this scoping closes.
        api = scoped.get(
            "/api/projects/1/people",
            headers={"Authorization": "Bearer durable-mcp-token"},
        )
        assert api.status_code == 401

    def test_server_token_no_longer_opens_mcp(self, scoped) -> None:
        resp = _rpc(scoped, "rotating-server-token", "tools/call",
                    {"name": "get_project_overview", "arguments": {}})
        assert resp.status_code == 401

    def test_cli_fallback_unchanged(self) -> None:
        # No _BRISTLENOSE_MCP_TOKEN → the single printed token still works
        # for /mcp, exactly as the CLI connect block promises.
        app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
        app.state.auth_token = "single-cli-token"
        app.state.mcp_token = None
        with TestClient(app, base_url="http://127.0.0.1:8150") as client:
            resp = _rpc(client, "single-cli-token", "tools/call",
                        {"name": "get_project_overview", "arguments": {}})
            assert resp.status_code == 200


class TestHealthAdvertisesMount:
    """The desktop host reads mcp.mounted from /api/health (auth-exempt) to
    decide whether its Connect Agent sheet can offer an address at all."""

    def test_health_reports_mounted(self, app_fx) -> None:
        payload = AuthTestClient(app_fx).get("/api/health").json()
        assert payload["mcp"]["mounted"] is True

    def test_tool_call_marks_activity_in_health(self) -> None:
        # Through the protocol, not a direct tool call — the recorder is
        # wired at mount time, so only the mounted path can prove it.
        app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
        app.state.auth_token = "test-mcp-token"
        with TestClient(app, base_url="http://127.0.0.1:8150") as client:
            before = client.get("/api/health").json()["mcp"]
            assert before["active"] is False
            resp = _rpc(client, "test-mcp-token", "tools/call",
                        {"name": "get_project_overview", "arguments": {}})
            assert resp.status_code == 200
            after = client.get("/api/health").json()["mcp"]
            # A bare bool, deliberately: the auth-exempt health route must
            # not publish an activity timeline (elapsed seconds) to every
            # local process.
            assert after["active"] is True
            assert "active_seconds_ago" not in after

    def test_agent_activity_counter_increments_per_tool_call(self) -> None:
        # The sidebar antenna's animation trigger. Counts, not timestamps —
        # the host animates on the EDGE, and an integer can't be skewed by
        # the monotonic clock's sleep pause.
        app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
        app.state.auth_token = "test-mcp-token"
        with TestClient(app, base_url="http://127.0.0.1:8150") as client:
            hdr = {"Authorization": "Bearer test-mcp-token"}
            assert client.get("/api/agent-activity", headers=hdr).json()["calls"] == 0
            for expected in (1, 2):
                resp = _rpc(client, "test-mcp-token", "tools/call",
                            {"name": "get_project_overview", "arguments": {}})
                assert resp.status_code == 200
                got = client.get("/api/agent-activity", headers=hdr).json()["calls"]
                assert got == expected

    def test_agent_activity_requires_the_bearer(self) -> None:
        # The whole reason this isn't in the /api/health payload: health is
        # auth-exempt, and a call counter IS the activity timeline health
        # deliberately withholds from every local process.
        app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
        app.state.auth_token = "test-mcp-token"
        with TestClient(app, base_url="http://127.0.0.1:8150") as client:
            assert client.get("/api/agent-activity").status_code == 401
            assert "calls" not in client.get("/api/health").json()["mcp"]

    def test_absent_mount_reports_false(self, monkeypatch) -> None:
        # create_app imports the symbol at call time, so patch the source
        # module — patching the app module's namespace would silently no-op.
        import bristlenose.server.mcp_server as mcp_module

        monkeypatch.setattr(mcp_module, "mount_mcp_server", lambda app, sf: None)
        app = create_app(dev=True, db_url="sqlite://")
        assert app.state.mcp_mounted is False
        assert AuthTestClient(app).get("/api/health").json()["mcp"]["mounted"] is False

    def test_instance_id_is_per_serve_and_stable_within_one(self) -> None:
        # The proxy compares this with its handshake BEFORE transmitting the
        # bearer — so a stale handshake naming a recycled ephemeral port
        # cannot hand a durable credential to whatever now owns it.
        a = create_app(dev=True, db_url="sqlite://")
        b = create_app(dev=True, db_url="sqlite://")
        ca, cb = AuthTestClient(a), AuthTestClient(b)
        first = ca.get("/api/health").json()["mcp"]["instance_id"]
        assert first and len(first) == 16
        assert ca.get("/api/health").json()["mcp"]["instance_id"] == first
        assert cb.get("/api/health").json()["mcp"]["instance_id"] != first

    def test_raising_activity_recorder_never_fails_the_tool(self, db) -> None:
        # The recorder is decoration — same non-fatal rule the AutoCode
        # progress write learned the hard way. A recorder that raises must
        # not sink the payload.
        from bristlenose.server.mcp_server import create_mcp_server

        def _boom() -> None:
            raise RuntimeError("recorder exploded")

        server = create_mcp_server(
            lambda: db, lambda: {"outcome": "completed"}, _boom
        )
        assert server is not None
        # Reach the wrapper through a registered tool function.
        import anyio

        async def _call():
            return await server.call_tool("get_project_overview", {"project_id": 1})

        result = anyio.run(_call)
        assert result is not None


class TestProjectIdentityInEveryPayload:
    """`project_id` is a SLOT, not a name.

    It resolves to whichever project is currently exposed, so a researcher
    switching studies mid-conversation silently re-points it. Observed 20 Aug
    2026 through the installed extension: the same id returned "foo" and then
    "IKEA with uxfriends" in one session, and the agent noticed only because
    the overview happened to carry a name to compare.

    The tool that carries the EVIDENCE carried no identity at all — so quotes
    from the second study would arrive under the first study's frame, correctly
    retrieved and wrongly attributed, with no error anywhere. That is the worst
    shape a bug can take in a research deliverable.

    Parametrised over every tool deliberately: a per-tool test invites the NEXT
    tool to ship without an echo, which is exactly how search_quotes came to
    lack one.
    """

    @pytest.fixture()
    def _tools(self):
        return {
            "get_project_overview": lambda db: _tool_get_project_overview(db, 1, None),
            "search_quotes": lambda db: _search(db),
            "get_signals": lambda db: _tool_get_signals(db, 1, "sentiment", 10),
            "get_framework": lambda db: _tool_get_framework(db, 1, LIVE_CODEBOOK_ID),
            "get_framework_template": lambda db: _tool_get_framework(db, 1, "uxr"),
        }

    def test_every_tool_names_its_project(self, db, _tools) -> None:
        missing = []
        for name, call in _tools.items():
            payload = call(db)
            project = payload.get("project")
            if not isinstance(project, dict) or not project.get("name"):
                missing.append(name)
        assert not missing, f"tools returning no project identity: {missing}"

    def test_the_name_is_the_real_one(self, db, _tools) -> None:
        # Not just "a name is present" — the SAME name from every tool, so a
        # consumer can compare across calls and notice a switch.
        names = {name: call(db)["project"]["name"] for name, call in _tools.items()}
        assert len(set(names.values())) == 1, names
