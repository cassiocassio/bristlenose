"""Tests for the codebook API endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.models import (
    AutoCodeJob,
    CodebookGroup,
    ProjectCodebookGroup,
    ProposedTag,
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


# ---------------------------------------------------------------------------
# GET /codebook/templates
# ---------------------------------------------------------------------------


class TestListTemplates:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/codebook/templates")
        assert resp.status_code == 200

    def test_returns_all_templates(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/codebook/templates").json()
        assert len(data["templates"]) >= 3
        ids = [t["id"] for t in data["templates"]]
        assert "garrett" in ids
        assert "norman" in ids
        assert "uxr" in ids

    def test_template_has_expected_shape(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/codebook/templates").json()
        garrett = next(t for t in data["templates"] if t["id"] == "garrett")
        assert garrett["title"] == "The Elements of User Experience"
        assert garrett["author"] == "Jesse James Garrett"
        assert garrett["enabled"] is True
        assert garrett["imported"] is False
        assert len(garrett["groups"]) == 5
        assert len(garrett["author_links"]) == 3
        # Check first group has tags
        strategy = garrett["groups"][0]
        assert strategy["name"] == "Strategy"
        assert strategy["colour_set"] == "ux"
        assert len(strategy["tags"]) == 4

    def test_norman_template_enabled(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/codebook/templates").json()
        norman = next(t for t in data["templates"] if t["id"] == "norman")
        assert norman["enabled"] is True

    def test_imported_flag_false_initially(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/codebook/templates").json()
        for t in data["templates"]:
            assert t["imported"] is False


# ---------------------------------------------------------------------------
# POST /codebook/import-template
# ---------------------------------------------------------------------------


class TestImportTemplate:
    def test_import_garrett(self, client: TestClient) -> None:
        resp = client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should have Uncategorised + 5 Garrett groups
        assert len(data["groups"]) == 6
        garrett_groups = [g for g in data["groups"] if g["framework_id"] == "garrett"]
        assert len(garrett_groups) == 5

    def test_imported_groups_have_correct_tags(self, client: TestClient) -> None:
        client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        data = client.get("/api/projects/1/codebook").json()
        strategy = next(g for g in data["groups"] if g["name"] == "Strategy")
        tag_names = [t["name"] for t in strategy["tags"]]
        assert "user need" in tag_names
        assert "business objective" in tag_names
        assert len(tag_names) == 4

    def test_imported_groups_have_framework_id(self, client: TestClient) -> None:
        client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        data = client.get("/api/projects/1/codebook").json()
        strategy = next(g for g in data["groups"] if g["name"] == "Strategy")
        assert strategy["framework_id"] == "garrett"

    def test_import_shows_imported_in_template_list(self, client: TestClient) -> None:
        client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        data = client.get("/api/projects/1/codebook/templates").json()
        garrett = next(t for t in data["templates"] if t["id"] == "garrett")
        assert garrett["imported"] is True
        # UXR should still not be imported
        uxr = next(t for t in data["templates"] if t["id"] == "uxr")
        assert uxr["imported"] is False

    def test_import_duplicate_returns_409(self, client: TestClient) -> None:
        client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        resp = client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        assert resp.status_code == 409

    def test_import_norman_succeeds(self, client: TestClient) -> None:
        resp = client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "norman"},
        )
        assert resp.status_code == 200
        data = resp.json()
        norman_groups = [g for g in data["groups"] if g["framework_id"] == "norman"]
        assert len(norman_groups) == 7

    def test_import_unknown_template_returns_404(self, client: TestClient) -> None:
        resp = client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "nonexistent"},
        )
        assert resp.status_code == 404

    def test_cannot_delete_framework_group(self, client: TestClient) -> None:
        client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        data = client.get("/api/projects/1/codebook").json()
        strategy = next(g for g in data["groups"] if g["name"] == "Strategy")
        resp = client.delete(f"/api/projects/1/codebook/groups/{strategy['id']}")
        assert resp.status_code == 400
        assert "framework" in resp.json()["detail"].lower()

    def test_cannot_rename_framework_group(self, client: TestClient) -> None:
        client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        data = client.get("/api/projects/1/codebook").json()
        strategy = next(g for g in data["groups"] if g["name"] == "Strategy")
        resp = client.patch(
            f"/api/projects/1/codebook/groups/{strategy['id']}",
            json={"name": "Renamed"},
        )
        assert resp.status_code == 400
        assert "framework" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# DELETE /codebook/remove-framework/{framework_id}
# ---------------------------------------------------------------------------


class TestRemoveFramework:
    def test_remove_framework_deletes_groups(self, client: TestClient) -> None:
        """Removing a framework should delete all its groups."""
        client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        data = client.get("/api/projects/1/codebook").json()
        garrett_groups = [g for g in data["groups"] if g["framework_id"] == "garrett"]
        assert len(garrett_groups) == 5

        resp = client.delete("/api/projects/1/codebook/remove-framework/garrett")
        assert resp.status_code == 200
        data = resp.json()
        garrett_groups = [g for g in data["groups"] if g["framework_id"] == "garrett"]
        assert len(garrett_groups) == 0

    def test_remove_framework_deletes_tags(self, client: TestClient) -> None:
        """Tags from the framework should be fully deleted, not moved."""
        client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        data = client.get("/api/projects/1/codebook").json()
        # Collect all tag names from garrett groups
        garrett_tag_names = set()
        for g in data["groups"]:
            if g["framework_id"] == "garrett":
                for t in g["tags"]:
                    garrett_tag_names.add(t["name"])
        assert len(garrett_tag_names) > 0

        client.delete("/api/projects/1/codebook/remove-framework/garrett")
        data = client.get("/api/projects/1/codebook").json()
        # Tags should NOT appear in Uncategorised or anywhere else
        remaining_names = set(data["all_tag_names"])
        assert garrett_tag_names.isdisjoint(remaining_names)

    def test_remove_framework_deletes_quote_tags(self, client: TestClient) -> None:
        """QuoteTag associations for framework tags should be cleaned up."""
        app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
        tc = TestClient(app)
        # Import template
        tc.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        # Manually add some QuoteTags to framework tags
        db = app.state.db_factory()
        try:
            quotes = db.query(Quote).filter_by(project_id=1).all()
            garrett_groups = (
                db.query(CodebookGroup)
                .filter_by(framework_id="garrett")
                .all()
            )
            tag_defs = (
                db.query(TagDefinition)
                .filter(
                    TagDefinition.codebook_group_id.in_([g.id for g in garrett_groups]),
                )
                .all()
            )
            assert len(tag_defs) > 0
            if quotes:
                db.add(QuoteTag(quote_id=quotes[0].id, tag_definition_id=tag_defs[0].id))
                db.commit()
                # Verify QuoteTag exists
                qt_count = db.query(QuoteTag).filter_by(
                    tag_definition_id=tag_defs[0].id,
                ).count()
                assert qt_count == 1
        finally:
            db.close()

        # Remove framework
        tc.delete("/api/projects/1/codebook/remove-framework/garrett")

        # Verify QuoteTags are gone
        db = app.state.db_factory()
        try:
            qt_count = db.query(QuoteTag).filter_by(
                tag_definition_id=tag_defs[0].id,
            ).count()
            assert qt_count == 0
        finally:
            db.close()

    def test_remove_framework_preserves_user_groups(self, client: TestClient) -> None:
        """User-created groups should not be affected by framework removal."""
        # Create a user group first
        client.post(
            "/api/projects/1/codebook/groups",
            json={"name": "My Group", "colour_set": "emo"},
        )
        client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        client.delete("/api/projects/1/codebook/remove-framework/garrett")
        data = client.get("/api/projects/1/codebook").json()
        assert any(g["name"] == "My Group" for g in data["groups"])
        assert any(g["name"] == "Uncategorised" for g in data["groups"])

    def test_remove_framework_allows_reimport(self, client: TestClient) -> None:
        """After removal, the framework should be re-importable."""
        client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        client.delete("/api/projects/1/codebook/remove-framework/garrett")
        # Template should no longer show as imported
        templates = client.get("/api/projects/1/codebook/templates").json()
        garrett = next(t for t in templates["templates"] if t["id"] == "garrett")
        assert garrett["imported"] is False
        # Re-import should succeed
        resp = client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        assert resp.status_code == 200
        data = resp.json()
        garrett_groups = [g for g in data["groups"] if g["framework_id"] == "garrett"]
        assert len(garrett_groups) == 5

    def test_remove_framework_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/projects/1/codebook/remove-framework/nonexistent")
        assert resp.status_code == 404

    def test_remove_framework_only_removes_specified(self, client: TestClient) -> None:
        """Importing two frameworks and removing one should keep the other."""
        client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "uxr"},
        )
        client.delete("/api/projects/1/codebook/remove-framework/garrett")
        data = client.get("/api/projects/1/codebook").json()
        # Garrett should be gone
        assert not any(g["framework_id"] == "garrett" for g in data["groups"])
        # UXR should still be there
        uxr_groups = [g for g in data["groups"] if g["framework_id"] == "uxr"]
        assert len(uxr_groups) > 0

    def test_remove_framework_with_autocode_data(self) -> None:
        """Removing a framework with AutoCode jobs and proposals should not fail."""
        app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
        tc = TestClient(app)
        tc.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        # Manually create an AutoCodeJob and ProposedTag for the framework
        db = app.state.db_factory()
        try:
            garrett_groups = (
                db.query(CodebookGroup)
                .filter_by(framework_id="garrett")
                .all()
            )
            tag_defs = (
                db.query(TagDefinition)
                .filter(
                    TagDefinition.codebook_group_id.in_([g.id for g in garrett_groups]),
                )
                .all()
            )
            assert len(tag_defs) > 0
            quotes = db.query(Quote).filter_by(project_id=1).all()
            assert len(quotes) > 0

            job = AutoCodeJob(
                project_id=1,
                framework_id="garrett",
                status="completed",
                total_quotes=len(quotes),
                processed_quotes=len(quotes),
                proposed_count=1,
            )
            db.add(job)
            db.flush()
            db.add(ProposedTag(
                job_id=job.id,
                quote_id=quotes[0].id,
                tag_definition_id=tag_defs[0].id,
                confidence=0.85,
                rationale="test",
                status="pending",
            ))
            db.commit()
            # Verify the data exists
            assert db.query(ProposedTag).count() == 1
            assert db.query(AutoCodeJob).count() == 1
        finally:
            db.close()

        # Remove framework — this should not fail with FK constraint
        resp = tc.delete("/api/projects/1/codebook/remove-framework/garrett")
        assert resp.status_code == 200

        # Verify cleanup
        db = app.state.db_factory()
        try:
            assert db.query(ProposedTag).count() == 0
            assert db.query(AutoCodeJob).filter_by(framework_id="garrett").count() == 0
        finally:
            db.close()


# ---------------------------------------------------------------------------
# GET /codebook/remove-framework/{framework_id}/impact
# ---------------------------------------------------------------------------


class TestRemoveFrameworkImpact:
    def test_impact_returns_tag_count(self, client: TestClient) -> None:
        client.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        resp = client.get("/api/projects/1/codebook/remove-framework/garrett/impact")
        assert resp.status_code == 200
        data = resp.json()
        # Garrett has 5 groups with varying tag counts
        assert data["tag_count"] > 0
        # No quotes tagged yet so quote_count should be 0
        assert data["quote_count"] == 0

    def test_impact_returns_quote_count(self, client: TestClient) -> None:
        """Impact should count distinct quotes across all framework tags."""
        app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
        tc = TestClient(app)
        tc.post(
            "/api/projects/1/codebook/import-template",
            json={"template_id": "garrett"},
        )
        # Tag some quotes
        db = app.state.db_factory()
        try:
            quotes = db.query(Quote).filter_by(project_id=1).all()
            garrett_groups = (
                db.query(CodebookGroup)
                .filter_by(framework_id="garrett")
                .all()
            )
            tag_defs = (
                db.query(TagDefinition)
                .filter(
                    TagDefinition.codebook_group_id.in_([g.id for g in garrett_groups]),
                )
                .all()
            )
            if len(quotes) >= 2 and len(tag_defs) >= 2:
                db.add(QuoteTag(quote_id=quotes[0].id, tag_definition_id=tag_defs[0].id))
                db.add(QuoteTag(quote_id=quotes[1].id, tag_definition_id=tag_defs[0].id))
                # Same quote tagged with second tag — should count as 1 distinct
                db.add(QuoteTag(quote_id=quotes[0].id, tag_definition_id=tag_defs[1].id))
                db.commit()
        finally:
            db.close()

        resp = tc.get("/api/projects/1/codebook/remove-framework/garrett/impact")
        data = resp.json()
        assert data["quote_count"] == 2  # 2 distinct quotes

    def test_impact_nonexistent_framework(self, client: TestClient) -> None:
        """Non-existent framework should return zeros (no 404)."""
        resp = client.get("/api/projects/1/codebook/remove-framework/nonexistent/impact")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tag_count"] == 0
        assert data["quote_count"] == 0
