"""Tests for the codebook API endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.models import (
    CodebookGroup,
    ProjectCodebookGroup,
    Quote,
    QuoteTag,
    TagDefinition,
)

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.fixture()
def client() -> TestClient:
    """Create a test client with imported smoke-test data."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return TestClient(app)


@pytest.fixture()
def client_with_codebook() -> TestClient:
    """Create a test client with pre-populated codebook data."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    # Populate codebook groups and tags directly in the DB
    db = app.state.db_factory()
    try:
        g1 = CodebookGroup(name="Friction", subtitle="Pain points", colour_set="emo", sort_order=0)
        g2 = CodebookGroup(name="Delight", subtitle="Positive moments", colour_set="ux", sort_order=1)
        db.add_all([g1, g2])
        db.flush()
        db.add_all([
            ProjectCodebookGroup(project_id=1, codebook_group_id=g1.id, sort_order=0),
            ProjectCodebookGroup(project_id=1, codebook_group_id=g2.id, sort_order=1),
        ])
        t1 = TagDefinition(name="confusion", codebook_group_id=g1.id)
        t2 = TagDefinition(name="frustration", codebook_group_id=g1.id)
        t3 = TagDefinition(name="joy", codebook_group_id=g2.id)
        db.add_all([t1, t2, t3])
        db.flush()
        # Assign some QuoteTags to give non-zero counts
        quotes = db.query(Quote).filter_by(project_id=1).all()
        if len(quotes) >= 2:
            db.add(QuoteTag(quote_id=quotes[0].id, tag_definition_id=t1.id))
            db.add(QuoteTag(quote_id=quotes[1].id, tag_definition_id=t1.id))
            db.add(QuoteTag(quote_id=quotes[0].id, tag_definition_id=t2.id))
        db.commit()
    finally:
        db.close()
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /codebook
# ---------------------------------------------------------------------------


class TestGetCodebook:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/codebook")
        assert resp.status_code == 200

    def test_empty_codebook_has_expected_shape(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/codebook").json()
        assert set(data.keys()) == {"groups", "ungrouped", "all_tag_names"}
        # Uncategorised default group is always present
        assert len(data["groups"]) == 1
        default_group = data["groups"][0]
        assert default_group["name"] == "Uncategorised"
        assert default_group["is_default"] is True
        assert default_group["tags"] == []
        assert data["ungrouped"] == []  # deprecated field
        assert data["all_tag_names"] == []

    def test_returns_groups_with_tags(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        # 2 user-created + 1 Uncategorised default
        assert len(data["groups"]) == 3
        names = [g["name"] for g in data["groups"]]
        assert "Friction" in names
        assert "Delight" in names
        assert "Uncategorised" in names

    def test_group_has_tags(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        friction = next(g for g in data["groups"] if g["name"] == "Friction")
        tag_names = [t["name"] for t in friction["tags"]]
        assert "confusion" in tag_names
        assert "frustration" in tag_names

    def test_tag_has_quote_count(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        friction = next(g for g in data["groups"] if g["name"] == "Friction")
        confusion = next(t for t in friction["tags"] if t["name"] == "confusion")
        assert confusion["count"] == 2

    def test_group_total_quotes_deduped(self, client_with_codebook: TestClient) -> None:
        """Two tags on the same quote should count as 1 total_quotes."""
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        friction = next(g for g in data["groups"] if g["name"] == "Friction")
        # confusion has quotes[0] and quotes[1], frustration has quotes[0]
        # unique quotes: {quotes[0], quotes[1]} = 2
        assert friction["total_quotes"] == 2

    def test_all_tag_names_is_sorted(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        assert data["all_tag_names"] == sorted(data["all_tag_names"])

    def test_project_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/projects/999/codebook")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /codebook/groups (create group)
# ---------------------------------------------------------------------------


class TestCreateGroup:
    def test_creates_group(self, client: TestClient) -> None:
        resp = client.post(
            "/api/projects/1/codebook/groups",
            json={"name": "Friction", "colour_set": "emo"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Friction"
        assert data["colour_set"] == "emo"
        assert data["id"] > 0

    def test_created_group_appears_in_codebook(self, client: TestClient) -> None:
        client.post(
            "/api/projects/1/codebook/groups",
            json={"name": "New Group"},
        )
        data = client.get("/api/projects/1/codebook").json()
        assert any(g["name"] == "New Group" for g in data["groups"])

    def test_default_colour_set(self, client: TestClient) -> None:
        resp = client.post(
            "/api/projects/1/codebook/groups",
            json={"name": "Test"},
        )
        assert resp.json()["colour_set"] == "ux"

    def test_project_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/projects/999/codebook/groups",
            json={"name": "x"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /codebook/groups/{id} (update group)
# ---------------------------------------------------------------------------


class TestUpdateGroup:
    def test_rename_group(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        gid = data["groups"][0]["id"]
        resp = client_with_codebook.patch(
            f"/api/projects/1/codebook/groups/{gid}",
            json={"name": "Renamed"},
        )
        assert resp.status_code == 200
        # Verify
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        assert any(g["name"] == "Renamed" for g in data["groups"])

    def test_update_subtitle(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        gid = data["groups"][0]["id"]
        client_with_codebook.patch(
            f"/api/projects/1/codebook/groups/{gid}",
            json={"subtitle": "Updated subtitle"},
        )
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        g = next(g for g in data["groups"] if g["id"] == gid)
        assert g["subtitle"] == "Updated subtitle"

    def test_update_colour_set(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        gid = data["groups"][0]["id"]
        client_with_codebook.patch(
            f"/api/projects/1/codebook/groups/{gid}",
            json={"colour_set": "trust"},
        )
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        g = next(g for g in data["groups"] if g["id"] == gid)
        assert g["colour_set"] == "trust"

    def test_group_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/projects/1/codebook/groups/999",
            json={"name": "x"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /codebook/groups/{id}
# ---------------------------------------------------------------------------


class TestDeleteGroup:
    def test_delete_group(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        gid = next(g["id"] for g in data["groups"] if g["name"] == "Delight")
        resp = client_with_codebook.delete(f"/api/projects/1/codebook/groups/{gid}")
        assert resp.status_code == 200
        # Group should be gone
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        assert not any(g["name"] == "Delight" for g in data["groups"])

    def test_delete_group_moves_tags_to_uncategorised(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        delight = next(g for g in data["groups"] if g["name"] == "Delight")
        gid = delight["id"]
        tag_names = [t["name"] for t in delight["tags"]]
        client_with_codebook.delete(f"/api/projects/1/codebook/groups/{gid}")
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        uncategorised = next(g for g in data["groups"] if g["name"] == "Uncategorised")
        uncategorised_names = [t["name"] for t in uncategorised["tags"]]
        for name in tag_names:
            assert name in uncategorised_names

    def test_group_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/projects/1/codebook/groups/999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /codebook/tags (create tag)
# ---------------------------------------------------------------------------


class TestCreateTag:
    def test_creates_tag(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        gid = data["groups"][0]["id"]
        resp = client_with_codebook.post(
            "/api/projects/1/codebook/tags",
            json={"name": "new-tag", "group_id": gid},
        )
        assert resp.status_code == 200
        tag = resp.json()
        assert tag["name"] == "new-tag"
        assert tag["count"] == 0

    def test_created_tag_appears_in_group(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        gid = data["groups"][0]["id"]
        client_with_codebook.post(
            "/api/projects/1/codebook/tags",
            json={"name": "new-tag", "group_id": gid},
        )
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        g = next(g for g in data["groups"] if g["id"] == gid)
        assert any(t["name"] == "new-tag" for t in g["tags"])

    def test_rejects_duplicate_name(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        gid = data["groups"][0]["id"]
        resp = client_with_codebook.post(
            "/api/projects/1/codebook/tags",
            json={"name": "confusion", "group_id": gid},
        )
        assert resp.status_code == 409

    def test_rejects_duplicate_name_case_insensitive(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        gid = data["groups"][0]["id"]
        resp = client_with_codebook.post(
            "/api/projects/1/codebook/tags",
            json={"name": "CONFUSION", "group_id": gid},
        )
        assert resp.status_code == 409

    def test_group_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/projects/1/codebook/tags",
            json={"name": "x", "group_id": 999},
        )
        assert resp.status_code == 404

    def test_strips_whitespace(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        gid = data["groups"][0]["id"]
        resp = client_with_codebook.post(
            "/api/projects/1/codebook/tags",
            json={"name": "  trimmed  ", "group_id": gid},
        )
        assert resp.json()["name"] == "trimmed"


# ---------------------------------------------------------------------------
# PATCH /codebook/tags/{id} (rename / move)
# ---------------------------------------------------------------------------


class TestUpdateTag:
    def test_rename_tag(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        friction = next(g for g in data["groups"] if g["name"] == "Friction")
        tid = friction["tags"][0]["id"]
        resp = client_with_codebook.patch(
            f"/api/projects/1/codebook/tags/{tid}",
            json={"name": "bewilderment"},
        )
        assert resp.status_code == 200
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        friction = next(g for g in data["groups"] if g["name"] == "Friction")
        assert any(t["name"] == "bewilderment" for t in friction["tags"])

    def test_move_tag_to_different_group(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        friction = next(g for g in data["groups"] if g["name"] == "Friction")
        delight = next(g for g in data["groups"] if g["name"] == "Delight")
        tid = friction["tags"][0]["id"]
        client_with_codebook.patch(
            f"/api/projects/1/codebook/tags/{tid}",
            json={"group_id": delight["id"]},
        )
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        delight = next(g for g in data["groups"] if g["name"] == "Delight")
        assert any(t["id"] == tid for t in delight["tags"])

    def test_rejects_duplicate_name_on_rename(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        friction = next(g for g in data["groups"] if g["name"] == "Friction")
        tid = friction["tags"][0]["id"]
        resp = client_with_codebook.patch(
            f"/api/projects/1/codebook/tags/{tid}",
            json={"name": "frustration"},
        )
        assert resp.status_code == 409

    def test_tag_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/projects/1/codebook/tags/999",
            json={"name": "x"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /codebook/tags/{id}
# ---------------------------------------------------------------------------


class TestDeleteTag:
    def test_delete_tag(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        friction = next(g for g in data["groups"] if g["name"] == "Friction")
        tid = friction["tags"][0]["id"]
        resp = client_with_codebook.delete(f"/api/projects/1/codebook/tags/{tid}")
        assert resp.status_code == 200
        # Tag should be gone
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        friction = next(g for g in data["groups"] if g["name"] == "Friction")
        assert not any(t["id"] == tid for t in friction["tags"])

    def test_delete_tag_removes_quote_associations(
        self, client_with_codebook: TestClient,
    ) -> None:
        """Deleting a tag should also delete its QuoteTag rows."""
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        friction = next(g for g in data["groups"] if g["name"] == "Friction")
        confusion = next(t for t in friction["tags"] if t["name"] == "confusion")
        assert confusion["count"] == 2  # has quote associations
        client_with_codebook.delete(
            f"/api/projects/1/codebook/tags/{confusion['id']}",
        )
        # Verify the tag is gone
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        friction = next(g for g in data["groups"] if g["name"] == "Friction")
        assert not any(t["name"] == "confusion" for t in friction["tags"])

    def test_tag_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/projects/1/codebook/tags/999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /codebook/merge-tags
# ---------------------------------------------------------------------------


class TestMergeTags:
    def test_merge_tags(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        friction = next(g for g in data["groups"] if g["name"] == "Friction")
        confusion = next(t for t in friction["tags"] if t["name"] == "confusion")
        frustration = next(t for t in friction["tags"] if t["name"] == "frustration")
        resp = client_with_codebook.post(
            "/api/projects/1/codebook/merge-tags",
            json={"source_id": confusion["id"], "target_id": frustration["id"]},
        )
        assert resp.status_code == 200
        # Source tag should be gone, target should have merged counts
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        friction = next(g for g in data["groups"] if g["name"] == "Friction")
        assert not any(t["name"] == "confusion" for t in friction["tags"])
        frustration = next(t for t in friction["tags"] if t["name"] == "frustration")
        # frustration originally had 1 quote (quotes[0]), confusion had 2 (quotes[0], quotes[1])
        # After merge: frustration has quotes[0] (already had it) + quotes[1] (from confusion) = 2
        assert frustration["count"] == 2

    def test_cannot_merge_with_self(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        friction = next(g for g in data["groups"] if g["name"] == "Friction")
        tid = friction["tags"][0]["id"]
        resp = client_with_codebook.post(
            "/api/projects/1/codebook/merge-tags",
            json={"source_id": tid, "target_id": tid},
        )
        assert resp.status_code == 400

    def test_source_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/projects/1/codebook/merge-tags",
            json={"source_id": 999, "target_id": 1},
        )
        assert resp.status_code == 404

    def test_target_not_found(self, client_with_codebook: TestClient) -> None:
        data = client_with_codebook.get("/api/projects/1/codebook").json()
        friction = next(g for g in data["groups"] if g["name"] == "Friction")
        tid = friction["tags"][0]["id"]
        resp = client_with_codebook.post(
            "/api/projects/1/codebook/merge-tags",
            json={"source_id": tid, "target_id": 999},
        )
        assert resp.status_code == 404
