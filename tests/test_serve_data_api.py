"""Tests for the data API endpoints (Phase 1 — researcher state sync)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"

# Quote DOM IDs present in the smoke-test fixture:
# q-p1-10 (Dashboard - confusion), q-p1-26 (Dashboard - frustration),
# q-p1-46 (Search - delight), q-p1-66 (Onboarding gaps - frustration)


@pytest.fixture()
def client() -> TestClient:
    """Create a test client with imported smoke-test data."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return TestClient(app)


@pytest.fixture()
def client_empty() -> TestClient:
    """Create a test client with no project data."""
    app = create_app(dev=True, db_url="sqlite://")
    return TestClient(app)


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------


class TestPeopleGet:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/people")
        assert resp.status_code == 200

    def test_returns_speaker_codes(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/people").json()
        assert "m1" in data
        assert "p1" in data

    def test_person_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/people").json()
        person = data["p1"]
        assert "full_name" in person
        assert "short_name" in person
        assert "role" in person

    def test_404_nonexistent_project(self, client: TestClient) -> None:
        resp = client.get("/api/projects/999/people")
        assert resp.status_code == 404


class TestPeoplePut:
    def test_put_updates_person(self, client: TestClient) -> None:
        resp = client.put(
            "/api/projects/1/people",
            json={"p1": {"full_name": "Alice Test", "short_name": "Alice", "role": "participant"}},
        )
        assert resp.status_code == 200

        # Verify the change persisted
        data = client.get("/api/projects/1/people").json()
        assert data["p1"]["full_name"] == "Alice Test"
        assert data["p1"]["short_name"] == "Alice"

    def test_put_ignores_unknown_speaker(self, client: TestClient) -> None:
        resp = client.put(
            "/api/projects/1/people",
            json={"p99": {"full_name": "Nobody", "short_name": "", "role": ""}},
        )
        assert resp.status_code == 200

    def test_404_nonexistent_project(self, client: TestClient) -> None:
        resp = client.put(
            "/api/projects/999/people",
            json={"p1": {"full_name": "Test", "short_name": "", "role": ""}},
        )
        assert resp.status_code == 404


class TestPeoplePutWriteThrough:
    """PUT /people should write-through to people.yaml on disk."""

    def test_updates_people_yaml(self, tmp_path: Path) -> None:
        """Name edits via API are written back to people.yaml."""
        import yaml

        # Set up a synthetic project with people.yaml
        out = tmp_path / "bristlenose-output"
        out.mkdir()
        intermediate = out / ".bristlenose" / "intermediate"
        intermediate.mkdir(parents=True)
        (intermediate / "metadata.json").write_text('{"project_name": "Writethrough"}')
        (intermediate / "screen_clusters.json").write_text("[]")
        (intermediate / "theme_groups.json").write_text("[]")

        raw = out / "transcripts-raw"
        raw.mkdir()
        (raw / "s1.txt").write_text(
            "# Transcript: s1\n# Date: 2026-02-20\n# Duration: 00:01:00\n\n"
            "[00:02] [m1] Welcome.\n[00:10] [p1] Thanks.\n"
        )

        people_data = {
            "generated_by": "bristlenose",
            "last_updated": "2026-02-23T10:00:00Z",
            "participants": {
                "p1": {
                    "computed": {
                        "participant_id": "p1",
                        "session_id": "s1",
                        "duration_seconds": 60.0,
                        "words_spoken": 100,
                        "pct_words": 50.0,
                        "pct_time_speaking": 50.0,
                        "source_file": "test.vtt",
                    },
                    "editable": {
                        "full_name": "Frederick Thompson",
                        "short_name": "Frederick",
                        "role": "",
                        "persona": "",
                        "notes": "",
                    },
                },
                "m1": {
                    "computed": {
                        "participant_id": "m1",
                        "session_id": "s1",
                        "duration_seconds": 60.0,
                        "words_spoken": 50,
                        "pct_words": 25.0,
                        "pct_time_speaking": 25.0,
                        "source_file": "test.vtt",
                    },
                    "editable": {
                        "full_name": "",
                        "short_name": "",
                        "role": "",
                        "persona": "",
                        "notes": "",
                    },
                },
            },
        }
        people_path = out / "people.yaml"
        people_path.write_text(yaml.dump(people_data, default_flow_style=False))

        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client = TestClient(app)

        # Verify names were imported from people.yaml
        data = client.get("/api/projects/1/people").json()
        assert data["p1"]["full_name"] == "Frederick Thompson"

        # Edit p1's name via API
        resp = client.put(
            "/api/projects/1/people",
            json={"p1": {"full_name": "Fred Thompson", "short_name": "Fred", "role": "CEO"}},
        )
        assert resp.status_code == 200

        # Verify DB was updated
        data = client.get("/api/projects/1/people").json()
        assert data["p1"]["full_name"] == "Fred Thompson"
        assert data["p1"]["short_name"] == "Fred"
        assert data["p1"]["role"] == "CEO"

        # Verify people.yaml was updated on disk
        raw_yaml = yaml.safe_load(people_path.read_text(encoding="utf-8"))
        p1_ed = raw_yaml["participants"]["p1"]["editable"]
        assert p1_ed["full_name"] == "Fred Thompson"
        assert p1_ed["short_name"] == "Fred"
        assert p1_ed["role"] == "CEO"

        # m1 should be unchanged
        m1_ed = raw_yaml["participants"]["m1"]["editable"]
        assert m1_ed["full_name"] == ""

    def test_no_people_yaml_does_not_error(self, client: TestClient) -> None:
        """PUT /people without a people.yaml file should not raise."""
        resp = client.put(
            "/api/projects/1/people",
            json={"p1": {"full_name": "Test", "short_name": "T", "role": ""}},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Edits
# ---------------------------------------------------------------------------


class TestEditsGet:
    def test_returns_200_empty(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/edits")
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_404_nonexistent_project(self, client: TestClient) -> None:
        resp = client.get("/api/projects/999/edits")
        assert resp.status_code == 404


class TestEditsPut:
    def test_put_quote_edit(self, client: TestClient) -> None:
        resp = client.put(
            "/api/projects/1/edits",
            json={"q-p1-10": "Corrected transcription text"},
        )
        assert resp.status_code == 200

        data = client.get("/api/projects/1/edits").json()
        assert data["q-p1-10"] == "Corrected transcription text"

    def test_put_heading_edit(self, client: TestClient) -> None:
        resp = client.put(
            "/api/projects/1/edits",
            json={"section-dashboard:title": "My Dashboard Section"},
        )
        assert resp.status_code == 200

        data = client.get("/api/projects/1/edits").json()
        assert data["section-dashboard:title"] == "My Dashboard Section"

    def test_put_mixed_edits(self, client: TestClient) -> None:
        resp = client.put(
            "/api/projects/1/edits",
            json={
                "q-p1-10": "Edited quote",
                "section-search:title": "Edited heading",
            },
        )
        assert resp.status_code == 200

        data = client.get("/api/projects/1/edits").json()
        assert data["q-p1-10"] == "Edited quote"
        assert data["section-search:title"] == "Edited heading"

    def test_put_updates_existing_edit(self, client: TestClient) -> None:
        client.put("/api/projects/1/edits", json={"q-p1-10": "First edit"})
        client.put("/api/projects/1/edits", json={"q-p1-10": "Second edit"})

        data = client.get("/api/projects/1/edits").json()
        assert data["q-p1-10"] == "Second edit"

    def test_put_skips_unknown_quote(self, client: TestClient) -> None:
        resp = client.put(
            "/api/projects/1/edits",
            json={"q-p99-999": "Unknown quote"},
        )
        assert resp.status_code == 200
        data = client.get("/api/projects/1/edits").json()
        assert "q-p99-999" not in data


# ---------------------------------------------------------------------------
# Hidden
# ---------------------------------------------------------------------------


class TestHiddenGet:
    def test_returns_200_empty(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/hidden")
        assert resp.status_code == 200
        assert resp.json() == {}


class TestHiddenPut:
    def test_put_hidden(self, client: TestClient) -> None:
        resp = client.put(
            "/api/projects/1/hidden",
            json={"q-p1-10": True, "q-p1-26": True},
        )
        assert resp.status_code == 200

        data = client.get("/api/projects/1/hidden").json()
        assert data["q-p1-10"] is True
        assert data["q-p1-26"] is True

    def test_put_unhide(self, client: TestClient) -> None:
        client.put("/api/projects/1/hidden", json={"q-p1-10": True})
        client.put("/api/projects/1/hidden", json={})

        data = client.get("/api/projects/1/hidden").json()
        assert data == {}

    def test_put_skips_unknown_quote(self, client: TestClient) -> None:
        resp = client.put(
            "/api/projects/1/hidden",
            json={"q-p99-999": True},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Starred
# ---------------------------------------------------------------------------


class TestStarredGet:
    def test_returns_200_empty(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/starred")
        assert resp.status_code == 200
        assert resp.json() == {}


class TestStarredPut:
    def test_put_starred(self, client: TestClient) -> None:
        resp = client.put(
            "/api/projects/1/starred",
            json={"q-p1-46": True},
        )
        assert resp.status_code == 200

        data = client.get("/api/projects/1/starred").json()
        assert data["q-p1-46"] is True

    def test_put_unstar(self, client: TestClient) -> None:
        client.put("/api/projects/1/starred", json={"q-p1-46": True})
        client.put("/api/projects/1/starred", json={})

        data = client.get("/api/projects/1/starred").json()
        assert data == {}

    def test_hidden_and_starred_independent(self, client: TestClient) -> None:
        """Hiding and starring use the same QuoteState row but are independent."""
        client.put("/api/projects/1/hidden", json={"q-p1-10": True})
        client.put("/api/projects/1/starred", json={"q-p1-10": True})

        hidden = client.get("/api/projects/1/hidden").json()
        starred = client.get("/api/projects/1/starred").json()
        assert hidden["q-p1-10"] is True
        assert starred["q-p1-10"] is True


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


class TestTagsGet:
    def test_returns_200_empty(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/tags")
        assert resp.status_code == 200
        assert resp.json() == {}


class TestTagsPut:
    def test_put_tags(self, client: TestClient) -> None:
        resp = client.put(
            "/api/projects/1/tags",
            json={"q-p1-10": ["usability", "navigation"]},
        )
        assert resp.status_code == 200

        data = client.get("/api/projects/1/tags").json()
        assert "q-p1-10" in data
        assert set(data["q-p1-10"]) == {"usability", "navigation"}

    def test_put_replaces_tags(self, client: TestClient) -> None:
        client.put("/api/projects/1/tags", json={"q-p1-10": ["old-tag"]})
        client.put("/api/projects/1/tags", json={"q-p1-10": ["new-tag"]})

        data = client.get("/api/projects/1/tags").json()
        assert data["q-p1-10"] == ["new-tag"]

    def test_put_empty_clears_tags(self, client: TestClient) -> None:
        client.put("/api/projects/1/tags", json={"q-p1-10": ["tag1"]})
        client.put("/api/projects/1/tags", json={})

        data = client.get("/api/projects/1/tags").json()
        assert data == {}

    def test_put_creates_tag_definitions(self, client: TestClient) -> None:
        """New tag names should auto-create TagDefinition rows."""
        resp = client.put(
            "/api/projects/1/tags",
            json={"q-p1-10": ["brand-new-tag"]},
        )
        assert resp.status_code == 200

        data = client.get("/api/projects/1/tags").json()
        assert data["q-p1-10"] == ["brand-new-tag"]

    def test_put_multiple_quotes(self, client: TestClient) -> None:
        resp = client.put(
            "/api/projects/1/tags",
            json={
                "q-p1-10": ["shared-tag", "only-first"],
                "q-p1-46": ["shared-tag", "only-second"],
            },
        )
        assert resp.status_code == 200

        data = client.get("/api/projects/1/tags").json()
        assert "shared-tag" in data["q-p1-10"]
        assert "shared-tag" in data["q-p1-46"]


# ---------------------------------------------------------------------------
# Deleted badges
# ---------------------------------------------------------------------------


class TestDeletedBadgesGet:
    def test_returns_200_empty(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/deleted-badges")
        assert resp.status_code == 200
        assert resp.json() == {}


class TestDeletedBadgesPut:
    def test_put_deleted_badges(self, client: TestClient) -> None:
        resp = client.put(
            "/api/projects/1/deleted-badges",
            json={"q-p1-10": ["confusion"]},
        )
        assert resp.status_code == 200

        data = client.get("/api/projects/1/deleted-badges").json()
        assert data["q-p1-10"] == ["confusion"]

    def test_put_replaces_badges(self, client: TestClient) -> None:
        client.put("/api/projects/1/deleted-badges", json={"q-p1-10": ["confusion"]})
        client.put(
            "/api/projects/1/deleted-badges",
            json={"q-p1-10": ["confusion", "frustration"]},
        )

        data = client.get("/api/projects/1/deleted-badges").json()
        assert set(data["q-p1-10"]) == {"confusion", "frustration"}

    def test_put_empty_clears(self, client: TestClient) -> None:
        client.put("/api/projects/1/deleted-badges", json={"q-p1-10": ["confusion"]})
        client.put("/api/projects/1/deleted-badges", json={})

        data = client.get("/api/projects/1/deleted-badges").json()
        assert data == {}


# ---------------------------------------------------------------------------
# DOM ID parsing
# ---------------------------------------------------------------------------


class TestDomIdParsing:
    """Verify that the _parse_dom_quote_id helper works correctly."""

    def test_valid_id(self) -> None:
        from bristlenose.server.routes.data import _parse_dom_quote_id

        pid, tc = _parse_dom_quote_id("q-p1-123")
        assert pid == "p1"
        assert tc == 123

    def test_moderator_id(self) -> None:
        from bristlenose.server.routes.data import _parse_dom_quote_id

        pid, tc = _parse_dom_quote_id("q-m1-45")
        assert pid == "m1"
        assert tc == 45

    def test_invalid_prefix(self) -> None:
        from bristlenose.server.routes.data import _parse_dom_quote_id

        with pytest.raises(ValueError, match="Invalid quote DOM ID"):
            _parse_dom_quote_id("x-p1-123")

    def test_no_timecode(self) -> None:
        from bristlenose.server.routes.data import _parse_dom_quote_id

        with pytest.raises(ValueError, match="Invalid quote DOM ID"):
            _parse_dom_quote_id("q-p1")

    def test_non_numeric_timecode(self) -> None:
        from bristlenose.server.routes.data import _parse_dom_quote_id

        with pytest.raises(ValueError, match="Invalid timecode"):
            _parse_dom_quote_id("q-p1-abc")
