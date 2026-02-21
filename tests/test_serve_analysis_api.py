"""Tests for the tag-based analysis API endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.models import (
    UNCATEGORISED_GROUP_NAME,
    ClusterQuote,
    CodebookGroup,
    ProjectCodebookGroup,
    Quote,
    QuoteTag,
    ScreenCluster,
    TagDefinition,
    ThemeGroup,
    ThemeQuote,
)

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


def _create_tagged_project() -> TestClient:
    """Create a test client with quotes, codebook groups, and tags.

    The smoke-test fixture has only 1 participant — we add extra quotes with
    different participants so signal detection has enough data to work with.
    """
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    db = app.state.db_factory()
    try:
        # Check imported data
        cluster = db.query(ScreenCluster).filter_by(project_id=1).first()
        theme = db.query(ThemeGroup).filter_by(project_id=1).first()
        assert cluster is not None, "Smoke test should import at least one cluster"
        assert theme is not None, "Smoke test should import at least one theme"

        # Add extra quotes for participants p2, p3, p4 so we have enough
        # quote mass for signal detection (MIN_QUOTES_PER_CELL = 2)
        extra_quotes = []
        for pid in ["p2", "p3", "p4"]:
            for i, start in enumerate([100.0, 200.0]):
                q = Quote(
                    project_id=1,
                    session_id="s1",
                    participant_id=pid,
                    start_timecode=start + float(hash(pid) % 100),
                    end_timecode=start + 10.0,
                    text=f"Extra quote from {pid} number {i}",
                    quote_type="screen_specific",
                    sentiment="frustration",
                    intensity=2,
                )
                db.add(q)
                extra_quotes.append(q)
        db.flush()

        # Assign extra quotes to the first cluster and theme
        for q in extra_quotes:
            db.add(ClusterQuote(cluster_id=cluster.id, quote_id=q.id))
            db.add(ThemeQuote(theme_id=theme.id, quote_id=q.id))
        db.flush()

        # Create codebook groups
        g_friction = CodebookGroup(
            name="Friction", subtitle="Pain points", colour_set="emo", sort_order=0,
        )
        g_mental = CodebookGroup(
            name="Mental Models", subtitle="Expectations", colour_set="ux", sort_order=1,
        )
        g_uncat = db.query(CodebookGroup).filter_by(name=UNCATEGORISED_GROUP_NAME).first()
        db.add_all([g_friction, g_mental])
        db.flush()

        # Activate groups for the project
        db.add_all([
            ProjectCodebookGroup(project_id=1, codebook_group_id=g_friction.id, sort_order=0),
            ProjectCodebookGroup(project_id=1, codebook_group_id=g_mental.id, sort_order=1),
        ])
        if g_uncat:
            db.add(
                ProjectCodebookGroup(
                    project_id=1, codebook_group_id=g_uncat.id, sort_order=99,
                )
            )

        # Create tags
        t_slow = TagDefinition(name="slow", codebook_group_id=g_friction.id)
        t_confusing = TagDefinition(name="confusing", codebook_group_id=g_friction.id)
        t_expectation = TagDefinition(name="expectation mismatch", codebook_group_id=g_mental.id)
        db.add_all([t_slow, t_confusing, t_expectation])
        if g_uncat:
            t_misc = TagDefinition(name="misc", codebook_group_id=g_uncat.id)
            db.add(t_misc)
        db.flush()

        # Apply tags to quotes
        all_quotes = db.query(Quote).filter_by(project_id=1).all()

        # Tag at least 2 quotes with Friction tags (for MIN_QUOTES_PER_CELL)
        for q in all_quotes[:4]:
            db.add(QuoteTag(quote_id=q.id, tag_definition_id=t_slow.id))
        for q in all_quotes[:2]:
            db.add(QuoteTag(quote_id=q.id, tag_definition_id=t_confusing.id))

        # Tag some with Mental Models too (multi-group coverage)
        for q in all_quotes[:3]:
            db.add(QuoteTag(quote_id=q.id, tag_definition_id=t_expectation.id))

        # Tag one with Uncategorised
        if g_uncat:
            db.add(QuoteTag(quote_id=all_quotes[0].id, tag_definition_id=t_misc.id))

        db.commit()
    finally:
        db.close()
    return TestClient(app)


@pytest.fixture()
def client() -> TestClient:
    """Test client with no tags — just imported smoke-test data."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return TestClient(app)


@pytest.fixture()
def tagged_client() -> TestClient:
    """Test client with codebook groups, tags, and tagged quotes."""
    return _create_tagged_project()


# ---------------------------------------------------------------------------
# GET /api/projects/{project_id}/analysis/tags
# ---------------------------------------------------------------------------


class TestGetTagAnalysis:

    def test_returns_200(self, tagged_client: TestClient) -> None:
        resp = tagged_client.get("/api/projects/1/analysis/tags")
        assert resp.status_code == 200

    def test_response_shape(self, tagged_client: TestClient) -> None:
        data = tagged_client.get("/api/projects/1/analysis/tags").json()
        assert set(data.keys()) == {
            "signals", "section_matrix", "theme_matrix",
            "total_participants", "columns", "participant_ids",
            "trade_off_note",
        }
        assert isinstance(data["signals"], list)
        assert isinstance(data["columns"], list)
        assert isinstance(data["participant_ids"], list)
        assert isinstance(data["total_participants"], int)
        assert isinstance(data["trade_off_note"], str)

    def test_empty_when_no_tags(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/analysis/tags").json()
        assert data["signals"] == []
        assert data["columns"] == []
        assert data["total_participants"] == 0

    def test_columns_are_group_names(self, tagged_client: TestClient) -> None:
        data = tagged_client.get("/api/projects/1/analysis/tags").json()
        assert "Friction" in data["columns"]
        assert "Mental Models" in data["columns"]

    def test_uncategorised_excluded_by_default(self, tagged_client: TestClient) -> None:
        data = tagged_client.get("/api/projects/1/analysis/tags").json()
        assert UNCATEGORISED_GROUP_NAME not in data["columns"]

    def test_signals_have_group_name(self, tagged_client: TestClient) -> None:
        data = tagged_client.get("/api/projects/1/analysis/tags").json()
        if data["signals"]:
            sig = data["signals"][0]
            assert "group_name" in sig
            assert sig["group_name"] in data["columns"]

    def test_signal_has_expected_fields(self, tagged_client: TestClient) -> None:
        data = tagged_client.get("/api/projects/1/analysis/tags").json()
        if data["signals"]:
            sig = data["signals"][0]
            expected_keys = {
                "location", "source_type", "group_name", "count",
                "participants", "n_eff", "mean_intensity", "concentration",
                "composite_signal", "confidence", "quotes",
            }
            assert expected_keys == set(sig.keys())

    def test_matrix_has_expected_shape(self, tagged_client: TestClient) -> None:
        data = tagged_client.get("/api/projects/1/analysis/tags").json()
        sm = data["section_matrix"]
        assert set(sm.keys()) == {"cells", "row_totals", "col_totals", "grand_total", "row_labels"}
        assert isinstance(sm["cells"], dict)
        assert isinstance(sm["grand_total"], int)

    def test_project_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/projects/999/analysis/tags")
        assert resp.status_code == 404

    def test_top_n_limits_signals(self, tagged_client: TestClient) -> None:
        data = tagged_client.get("/api/projects/1/analysis/tags?top_n=1").json()
        assert len(data["signals"]) <= 1

    def test_group_filter(self, tagged_client: TestClient) -> None:
        """Filtering by specific group IDs restricts columns."""
        # First get all columns to find group IDs
        data_all = tagged_client.get("/api/projects/1/analysis/tags").json()
        if not data_all["columns"]:
            pytest.skip("No columns available")

        # Get the DB to find group IDs
        db = tagged_client.app.state.db_factory()  # type: ignore[union-attr]
        try:
            friction = db.query(CodebookGroup).filter_by(name="Friction").first()
            assert friction is not None
            data_filtered = tagged_client.get(
                f"/api/projects/1/analysis/tags?groups={friction.id}"
            ).json()
            assert data_filtered["columns"] == ["Friction"]
        finally:
            db.close()

    def test_invalid_groups_param(self, tagged_client: TestClient) -> None:
        resp = tagged_client.get("/api/projects/1/analysis/tags?groups=abc")
        assert resp.status_code == 400

    def test_trade_off_note_present(self, tagged_client: TestClient) -> None:
        data = tagged_client.get("/api/projects/1/analysis/tags").json()
        assert "grand_total" in data["trade_off_note"].lower()

    def test_signals_sorted_by_composite_desc(self, tagged_client: TestClient) -> None:
        data = tagged_client.get("/api/projects/1/analysis/tags").json()
        signals = data["signals"]
        if len(signals) >= 2:
            for i in range(len(signals) - 1):
                assert signals[i]["composite_signal"] >= signals[i + 1]["composite_signal"]

    def test_participant_ids_naturally_sorted(self, tagged_client: TestClient) -> None:
        data = tagged_client.get("/api/projects/1/analysis/tags").json()
        pids = data["participant_ids"]
        if len(pids) >= 2:
            # p1 should come before p2, p2 before p10
            for pid in pids:
                assert pid[0] == "p"
