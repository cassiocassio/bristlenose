"""Stress tests for the data API — edge cases, large payloads, and rapid writes.

Tests in this file exercise boundary conditions that go beyond the happy-path
coverage in test_serve_data_api.py.  Scenarios include:

- Unicode edge cases (emoji, CJK, RTL, zero-width chars in names/tags/edits)
- Very long strings (10 KB quote edits, 1 KB tag names, 200-char heading keys)
- Large state maps (hundreds of entries in a single PUT)
- Rapid sequential PUTs (simulates fast clicking — last writer wins)
- Empty and whitespace-only values
- Malformed DOM IDs and boundary timecodes
- Hidden + starred interaction under rapid toggling
- Duplicate tags on the same quote
- Tag names that differ only by case
- Heading keys with special characters
- Deleted badges with duplicate sentiment names
- PUT with a mix of valid and invalid quote IDs (partial success)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.fixture()
def client() -> TestClient:
    """Create a test client with imported smoke-test data."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return TestClient(app)


# ---------------------------------------------------------------------------
# Unicode edge cases
# ---------------------------------------------------------------------------


class TestUnicodeEdgeCases:
    """Verify that emoji, CJK, RTL, and combining characters survive round-trip."""

    def test_emoji_in_person_name(self, client: TestClient) -> None:
        client.put(
            "/api/projects/1/people",
            json={"p1": {"full_name": "Alice 🧪🔬", "short_name": "🧪", "role": "participant"}},
        )
        data = client.get("/api/projects/1/people").json()
        assert data["p1"]["full_name"] == "Alice 🧪🔬"
        assert data["p1"]["short_name"] == "🧪"

    def test_cjk_in_edit_text(self, client: TestClient) -> None:
        text = "ユーザーはダッシュボードで困惑していた"
        client.put("/api/projects/1/edits", json={"q-p1-10": text})
        data = client.get("/api/projects/1/edits").json()
        assert data["q-p1-10"] == text

    def test_rtl_arabic_in_tag_name(self, client: TestClient) -> None:
        client.put("/api/projects/1/tags", json={"q-p1-10": ["مشكلة", "حلول"]})
        data = client.get("/api/projects/1/tags").json()
        assert set(data["q-p1-10"]) == {"مشكلة", "حلول"}

    def test_combining_chars_in_edit(self, client: TestClient) -> None:
        """Combining diacritical marks (é = e + ́)."""
        text = "e\u0301dite\u0301"  # é using combining acute accent
        client.put("/api/projects/1/edits", json={"q-p1-10": text})
        data = client.get("/api/projects/1/edits").json()
        assert data["q-p1-10"] == text

    def test_zero_width_chars_in_tag(self, client: TestClient) -> None:
        """Zero-width joiner / non-joiner shouldn't break storage."""
        tag = "design\u200breview"  # zero-width space
        client.put("/api/projects/1/tags", json={"q-p1-10": [tag]})
        data = client.get("/api/projects/1/tags").json()
        assert data["q-p1-10"] == [tag]

    def test_newlines_in_edit_text(self, client: TestClient) -> None:
        text = "Line one\nLine two\nLine three"
        client.put("/api/projects/1/edits", json={"q-p1-10": text})
        data = client.get("/api/projects/1/edits").json()
        assert data["q-p1-10"] == text

    def test_emoji_in_heading_edit(self, client: TestClient) -> None:
        client.put(
            "/api/projects/1/edits",
            json={"section-dashboard:title": "🔥 Hot Dashboard Issues"},
        )
        data = client.get("/api/projects/1/edits").json()
        assert data["section-dashboard:title"] == "🔥 Hot Dashboard Issues"


# ---------------------------------------------------------------------------
# Large payloads
# ---------------------------------------------------------------------------


class TestLargePayloads:
    """Verify the API handles big strings and lots of entries."""

    def test_very_long_edit_text(self, client: TestClient) -> None:
        """10 KB edited text — researcher pastes a long correction."""
        text = "x" * 10_000
        resp = client.put("/api/projects/1/edits", json={"q-p1-10": text})
        assert resp.status_code == 200
        data = client.get("/api/projects/1/edits").json()
        assert len(data["q-p1-10"]) == 10_000

    def test_very_long_heading_key(self, client: TestClient) -> None:
        """Heading key at 200 chars — near the String(500) column limit."""
        key = "section-" + "a" * 192 + ":title"
        resp = client.put("/api/projects/1/edits", json={key: "Title text"})
        assert resp.status_code == 200
        data = client.get("/api/projects/1/edits").json()
        assert data[key] == "Title text"

    def test_many_tags_on_one_quote(self, client: TestClient) -> None:
        """50 tags on a single quote."""
        tags = [f"tag-{i}" for i in range(50)]
        resp = client.put("/api/projects/1/tags", json={"q-p1-10": tags})
        assert resp.status_code == 200
        data = client.get("/api/projects/1/tags").json()
        assert len(data["q-p1-10"]) == 50

    def test_long_tag_name(self, client: TestClient) -> None:
        """Tag name at 199 chars — just within String(200) TagDefinition.name."""
        tag = "t" * 199
        resp = client.put("/api/projects/1/tags", json={"q-p1-10": [tag]})
        assert resp.status_code == 200
        data = client.get("/api/projects/1/tags").json()
        assert data["q-p1-10"] == [tag]

    def test_many_deleted_badges_on_one_quote(self, client: TestClient) -> None:
        """20 deleted badges on a single quote."""
        badges = [f"sentiment-{i}" for i in range(20)]
        resp = client.put(
            "/api/projects/1/deleted-badges",
            json={"q-p1-10": badges},
        )
        assert resp.status_code == 200
        data = client.get("/api/projects/1/deleted-badges").json()
        assert set(data["q-p1-10"]) == set(badges)

    def test_all_quotes_hidden(self, client: TestClient) -> None:
        """Hide every quote in the project at once."""
        resp = client.put(
            "/api/projects/1/hidden",
            json={
                "q-p1-10": True,
                "q-p1-26": True,
                "q-p1-46": True,
                "q-p1-66": True,
            },
        )
        assert resp.status_code == 200
        data = client.get("/api/projects/1/hidden").json()
        assert len(data) == 4

    def test_all_quotes_starred(self, client: TestClient) -> None:
        """Star every quote at once."""
        resp = client.put(
            "/api/projects/1/starred",
            json={
                "q-p1-10": True,
                "q-p1-26": True,
                "q-p1-46": True,
                "q-p1-66": True,
            },
        )
        assert resp.status_code == 200
        data = client.get("/api/projects/1/starred").json()
        assert len(data) == 4

    def test_large_person_name(self, client: TestClient) -> None:
        """Person name near the String(200) column limit."""
        name = "A" * 199
        resp = client.put(
            "/api/projects/1/people",
            json={"p1": {"full_name": name, "short_name": "A", "role": "participant"}},
        )
        assert resp.status_code == 200
        data = client.get("/api/projects/1/people").json()
        assert data["p1"]["full_name"] == name


# ---------------------------------------------------------------------------
# Rapid sequential PUTs (simulates fast clicking)
# ---------------------------------------------------------------------------


class TestRapidPuts:
    """Simulate rapid clicks — multiple PUTs in quick succession.

    The last PUT wins because each PUT replaces the full state map.
    """

    def test_rapid_star_toggle(self, client: TestClient) -> None:
        """Star → unstar → star → unstar rapidly — final state should be unstarred."""
        client.put("/api/projects/1/starred", json={"q-p1-10": True})
        client.put("/api/projects/1/starred", json={})
        client.put("/api/projects/1/starred", json={"q-p1-10": True})
        client.put("/api/projects/1/starred", json={})

        data = client.get("/api/projects/1/starred").json()
        assert data == {}

    def test_rapid_hide_toggle(self, client: TestClient) -> None:
        """Hide → unhide → hide rapidly — final state should be hidden."""
        client.put("/api/projects/1/hidden", json={"q-p1-10": True})
        client.put("/api/projects/1/hidden", json={})
        client.put("/api/projects/1/hidden", json={"q-p1-10": True})

        data = client.get("/api/projects/1/hidden").json()
        assert data["q-p1-10"] is True

    def test_rapid_tag_changes(self, client: TestClient) -> None:
        """Add tags → change tags → clear tags → add different tags rapidly."""
        client.put("/api/projects/1/tags", json={"q-p1-10": ["first"]})
        client.put("/api/projects/1/tags", json={"q-p1-10": ["second", "third"]})
        client.put("/api/projects/1/tags", json={})
        client.put("/api/projects/1/tags", json={"q-p1-10": ["final"]})

        data = client.get("/api/projects/1/tags").json()
        assert data["q-p1-10"] == ["final"]

    def test_rapid_edit_overwrites(self, client: TestClient) -> None:
        """Multiple edits to the same quote — last one wins."""
        for i in range(20):
            client.put("/api/projects/1/edits", json={"q-p1-10": f"Edit #{i}"})

        data = client.get("/api/projects/1/edits").json()
        assert data["q-p1-10"] == "Edit #19"

    def test_rapid_hidden_starred_interleave(self, client: TestClient) -> None:
        """Interleave hidden and starred PUTs — they use the same QuoteState row."""
        client.put("/api/projects/1/hidden", json={"q-p1-10": True})
        client.put("/api/projects/1/starred", json={"q-p1-10": True})
        client.put("/api/projects/1/hidden", json={})  # unhide, should keep star
        client.put("/api/projects/1/starred", json={"q-p1-10": True, "q-p1-46": True})
        client.put("/api/projects/1/hidden", json={"q-p1-46": True})

        hidden = client.get("/api/projects/1/hidden").json()
        starred = client.get("/api/projects/1/starred").json()
        assert "q-p1-10" not in hidden  # unhidden
        assert starred["q-p1-10"] is True  # still starred
        assert hidden["q-p1-46"] is True  # hidden
        assert starred["q-p1-46"] is True  # also starred

    def test_rapid_people_edits(self, client: TestClient) -> None:
        """Rename a person 10 times rapidly — last name wins."""
        for i in range(10):
            client.put(
                "/api/projects/1/people",
                json={"p1": {"full_name": f"Name {i}", "short_name": f"N{i}", "role": ""}},
            )
        data = client.get("/api/projects/1/people").json()
        assert data["p1"]["full_name"] == "Name 9"
        assert data["p1"]["short_name"] == "N9"


# ---------------------------------------------------------------------------
# Empty and whitespace values
# ---------------------------------------------------------------------------


class TestEmptyAndWhitespace:
    """Edge cases with empty strings, whitespace, and null-like values."""

    def test_empty_edit_text(self, client: TestClient) -> None:
        """Empty string edit — should be stored (different from "no edit")."""
        client.put("/api/projects/1/edits", json={"q-p1-10": ""})
        data = client.get("/api/projects/1/edits").json()
        assert data["q-p1-10"] == ""

    def test_whitespace_only_edit(self, client: TestClient) -> None:
        client.put("/api/projects/1/edits", json={"q-p1-10": "   \t\n  "})
        data = client.get("/api/projects/1/edits").json()
        assert data["q-p1-10"] == "   \t\n  "

    def test_empty_person_fields(self, client: TestClient) -> None:
        client.put(
            "/api/projects/1/people",
            json={"p1": {"full_name": "", "short_name": "", "role": ""}},
        )
        data = client.get("/api/projects/1/people").json()
        assert data["p1"]["full_name"] == ""

    def test_empty_tag_list(self, client: TestClient) -> None:
        """PUT with an empty tag list for a quote — should clear tags."""
        client.put("/api/projects/1/tags", json={"q-p1-10": ["initial"]})
        client.put("/api/projects/1/tags", json={"q-p1-10": []})
        data = client.get("/api/projects/1/tags").json()
        # Empty list means no tags — key might be absent or have empty list
        if "q-p1-10" in data:
            assert data["q-p1-10"] == []

    def test_empty_badge_list(self, client: TestClient) -> None:
        client.put("/api/projects/1/deleted-badges", json={"q-p1-10": ["confusion"]})
        client.put("/api/projects/1/deleted-badges", json={"q-p1-10": []})
        data = client.get("/api/projects/1/deleted-badges").json()
        if "q-p1-10" in data:
            assert data["q-p1-10"] == []

    def test_put_empty_map_clears_everything(self, client: TestClient) -> None:
        """PUT {} to every endpoint should clear all state."""
        # Set some state first
        client.put("/api/projects/1/hidden", json={"q-p1-10": True})
        client.put("/api/projects/1/starred", json={"q-p1-10": True})
        client.put("/api/projects/1/tags", json={"q-p1-10": ["tag"]})
        client.put("/api/projects/1/deleted-badges", json={"q-p1-10": ["confusion"]})
        client.put("/api/projects/1/edits", json={"q-p1-10": "Edit"})

        # Clear everything
        client.put("/api/projects/1/hidden", json={})
        client.put("/api/projects/1/starred", json={})
        client.put("/api/projects/1/tags", json={})
        client.put("/api/projects/1/deleted-badges", json={})
        client.put("/api/projects/1/edits", json={})

        assert client.get("/api/projects/1/hidden").json() == {}
        assert client.get("/api/projects/1/starred").json() == {}
        assert client.get("/api/projects/1/tags").json() == {}
        assert client.get("/api/projects/1/deleted-badges").json() == {}
        assert client.get("/api/projects/1/edits").json() == {}


# ---------------------------------------------------------------------------
# Malformed and boundary DOM IDs
# ---------------------------------------------------------------------------


class TestMalformedDomIds:
    """Edge cases in DOM ID parsing and resolution."""

    def test_dom_id_with_no_prefix(self, client: TestClient) -> None:
        """DOM ID missing the 'q-' prefix — should be silently skipped."""
        resp = client.put("/api/projects/1/hidden", json={"p1-10": True})
        assert resp.status_code == 200

    def test_dom_id_with_extra_dashes(self, client: TestClient) -> None:
        """DOM ID with dashes in participant_id — uses rfind('-')."""
        from bristlenose.server.routes.data import _parse_dom_quote_id

        # Multi-dash participant like "q-long-name-123"
        pid, tc = _parse_dom_quote_id("q-long-name-123")
        assert pid == "long-name"
        assert tc == 123

    def test_dom_id_timecode_zero(self, client: TestClient) -> None:
        """Timecode 0 — valid but unusual (quote at the very start)."""
        from bristlenose.server.routes.data import _parse_dom_quote_id

        pid, tc = _parse_dom_quote_id("q-p1-0")
        assert pid == "p1"
        assert tc == 0

    def test_dom_id_large_timecode(self, client: TestClient) -> None:
        """Very large timecode — 3-hour interview at 10800 seconds."""
        from bristlenose.server.routes.data import _parse_dom_quote_id

        pid, tc = _parse_dom_quote_id("q-p1-10800")
        assert pid == "p1"
        assert tc == 10800

    def test_dom_id_negative_timecode(self, client: TestClient) -> None:
        """Negative timecode 'q-p1--5' — rfind splits at the last dash.

        This is a degenerate input (timecodes are always >= 0).  The parser
        uses rfind('-') so 'p1--5' splits into participant='p1-' and
        timecode='5'.  This won't match any real quote, which is fine.
        """
        from bristlenose.server.routes.data import _parse_dom_quote_id

        pid, tc = _parse_dom_quote_id("q-p1--5")
        assert pid == "p1-"
        assert tc == 5

    def test_dom_id_empty_string(self, client: TestClient) -> None:
        from bristlenose.server.routes.data import _parse_dom_quote_id

        with pytest.raises(ValueError):
            _parse_dom_quote_id("")

    def test_dom_id_just_prefix(self, client: TestClient) -> None:
        from bristlenose.server.routes.data import _parse_dom_quote_id

        with pytest.raises(ValueError):
            _parse_dom_quote_id("q-")

    def test_mixed_valid_invalid_in_hidden_put(self, client: TestClient) -> None:
        """PUT with mix of valid + invalid quote IDs — valid ones still persist."""
        resp = client.put(
            "/api/projects/1/hidden",
            json={
                "q-p1-10": True,         # valid
                "q-p99-999": True,        # invalid (no such participant)
                "not-a-quote": True,      # completely wrong format
                "q-p1-46": True,          # valid
            },
        )
        assert resp.status_code == 200
        data = client.get("/api/projects/1/hidden").json()
        assert data["q-p1-10"] is True
        assert data["q-p1-46"] is True
        assert "q-p99-999" not in data

    def test_mixed_valid_invalid_in_tags_put(self, client: TestClient) -> None:
        """Valid quote gets tags, invalid quote is skipped."""
        resp = client.put(
            "/api/projects/1/tags",
            json={
                "q-p1-10": ["valid-tag"],
                "q-p99-999": ["orphan-tag"],
            },
        )
        assert resp.status_code == 200
        data = client.get("/api/projects/1/tags").json()
        assert "q-p1-10" in data
        assert "q-p99-999" not in data


# ---------------------------------------------------------------------------
# Tag edge cases
# ---------------------------------------------------------------------------


class TestTagEdgeCases:
    """Tag-specific stress tests: duplicates, case sensitivity, special chars."""

    def test_duplicate_tag_on_same_quote(self, client: TestClient) -> None:
        """Same tag name twice in one PUT — deduplicated, no unique constraint crash."""
        resp = client.put(
            "/api/projects/1/tags",
            json={"q-p1-10": ["duplicate", "duplicate"]},
        )
        assert resp.status_code == 200
        data = client.get("/api/projects/1/tags").json()
        assert data["q-p1-10"] == ["duplicate"]

    def test_tag_names_differ_by_case(self, client: TestClient) -> None:
        """Tags that differ only by case — resolve to the same TagDefinition.

        The tag_defs cache is keyed by lowercased name, so 'Usability' and
        'usability' map to the same td_id.  The dedup set (seen_td_ids)
        prevents inserting two QuoteTag rows for the same definition.
        """
        resp = client.put(
            "/api/projects/1/tags",
            json={"q-p1-10": ["Usability", "usability"]},
        )
        assert resp.status_code == 200
        data = client.get("/api/projects/1/tags").json()
        # Only one survives — they share the same TagDefinition
        assert len(data["q-p1-10"]) == 1

    def test_tag_with_special_characters(self, client: TestClient) -> None:
        """Tags with colons, pipes, and brackets."""
        tags = ["key:value", "pipe|char", "[bracketed]", "slash/tag"]
        resp = client.put("/api/projects/1/tags", json={"q-p1-10": tags})
        assert resp.status_code == 200
        data = client.get("/api/projects/1/tags").json()
        assert set(data["q-p1-10"]) == set(tags)

    def test_same_tag_on_multiple_quotes(self, client: TestClient) -> None:
        """One tag applied to all 4 quotes — shares one TagDefinition."""
        resp = client.put(
            "/api/projects/1/tags",
            json={
                "q-p1-10": ["shared-tag"],
                "q-p1-26": ["shared-tag"],
                "q-p1-46": ["shared-tag"],
                "q-p1-66": ["shared-tag"],
            },
        )
        assert resp.status_code == 200
        data = client.get("/api/projects/1/tags").json()
        for qid in ["q-p1-10", "q-p1-26", "q-p1-46", "q-p1-66"]:
            assert data[qid] == ["shared-tag"]

    def test_uncategorised_codebook_group_reused(self, client: TestClient) -> None:
        """Adding tags in two separate PUTs should reuse the same Uncategorised group."""
        client.put("/api/projects/1/tags", json={"q-p1-10": ["tag-a"]})
        client.put("/api/projects/1/tags", json={"q-p1-10": ["tag-b"]})
        # If _get_or_create_uncategorised works correctly, no duplicate group error
        resp = client.get("/api/projects/1/tags")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Heading edit edge cases
# ---------------------------------------------------------------------------


class TestHeadingEditEdgeCases:
    """Heading key format stress tests."""

    def test_heading_key_with_colons(self, client: TestClient) -> None:
        """Key with multiple colons — only first splits scope:field."""
        key = "section-dashboard:sub:title"
        resp = client.put("/api/projects/1/edits", json={key: "Nested key"})
        assert resp.status_code == 200
        data = client.get("/api/projects/1/edits").json()
        assert data[key] == "Nested key"

    def test_heading_key_with_unicode(self, client: TestClient) -> None:
        key = "section-données:title"
        resp = client.put("/api/projects/1/edits", json={key: "French section"})
        assert resp.status_code == 200
        data = client.get("/api/projects/1/edits").json()
        assert data[key] == "French section"

    def test_many_heading_edits(self, client: TestClient) -> None:
        """50 heading edits in one PUT — stress the heading bulk path."""
        edits = {f"section-s{i}:title": f"Title {i}" for i in range(50)}
        resp = client.put("/api/projects/1/edits", json=edits)
        assert resp.status_code == 200
        data = client.get("/api/projects/1/edits").json()
        for key, expected in edits.items():
            assert data[key] == expected


# ---------------------------------------------------------------------------
# Deleted badges edge cases
# ---------------------------------------------------------------------------


class TestDeletedBadgeEdgeCases:
    def test_duplicate_sentiment_in_one_put(self, client: TestClient) -> None:
        """Same sentiment twice for one quote — deduplicated, no constraint crash."""
        resp = client.put(
            "/api/projects/1/deleted-badges",
            json={"q-p1-10": ["confusion", "confusion"]},
        )
        assert resp.status_code == 200
        data = client.get("/api/projects/1/deleted-badges").json()
        assert data["q-p1-10"] == ["confusion"]

    def test_many_sentiments_per_quote(self, client: TestClient) -> None:
        sentiments = [f"sentiment-{i}" for i in range(15)]
        resp = client.put(
            "/api/projects/1/deleted-badges",
            json={"q-p1-10": sentiments},
        )
        assert resp.status_code == 200
        data = client.get("/api/projects/1/deleted-badges").json()
        assert set(data["q-p1-10"]) == set(sentiments)

    def test_badges_across_all_quotes(self, client: TestClient) -> None:
        resp = client.put(
            "/api/projects/1/deleted-badges",
            json={
                "q-p1-10": ["confusion"],
                "q-p1-26": ["frustration"],
                "q-p1-46": ["delight"],
                "q-p1-66": ["frustration"],
            },
        )
        assert resp.status_code == 200
        data = client.get("/api/projects/1/deleted-badges").json()
        assert len(data) == 4


# ---------------------------------------------------------------------------
# Cross-endpoint interactions
# ---------------------------------------------------------------------------


class TestCrossEndpointInteractions:
    """Verify that different endpoints don't interfere with each other."""

    def test_edit_and_hide_same_quote(self, client: TestClient) -> None:
        """Editing a quote and hiding it should both persist independently."""
        client.put("/api/projects/1/edits", json={"q-p1-10": "Edited text"})
        client.put("/api/projects/1/hidden", json={"q-p1-10": True})

        edits = client.get("/api/projects/1/edits").json()
        hidden = client.get("/api/projects/1/hidden").json()
        assert edits["q-p1-10"] == "Edited text"
        assert hidden["q-p1-10"] is True

    def test_tag_and_star_same_quote(self, client: TestClient) -> None:
        client.put("/api/projects/1/tags", json={"q-p1-10": ["important"]})
        client.put("/api/projects/1/starred", json={"q-p1-10": True})

        tags = client.get("/api/projects/1/tags").json()
        starred = client.get("/api/projects/1/starred").json()
        assert tags["q-p1-10"] == ["important"]
        assert starred["q-p1-10"] is True

    def test_delete_badge_and_add_tag_same_quote(self, client: TestClient) -> None:
        client.put("/api/projects/1/deleted-badges", json={"q-p1-10": ["confusion"]})
        client.put("/api/projects/1/tags", json={"q-p1-10": ["my-tag"]})

        badges = client.get("/api/projects/1/deleted-badges").json()
        tags = client.get("/api/projects/1/tags").json()
        assert badges["q-p1-10"] == ["confusion"]
        assert tags["q-p1-10"] == ["my-tag"]

    def test_full_workflow_on_one_quote(self, client: TestClient) -> None:
        """Apply every possible state to one quote simultaneously."""
        client.put("/api/projects/1/edits", json={"q-p1-10": "Better text"})
        client.put("/api/projects/1/hidden", json={"q-p1-10": True})
        client.put("/api/projects/1/starred", json={"q-p1-10": True})
        client.put("/api/projects/1/tags", json={"q-p1-10": ["important", "follow-up"]})
        client.put("/api/projects/1/deleted-badges", json={"q-p1-10": ["confusion"]})
        client.put(
            "/api/projects/1/people",
            json={"p1": {"full_name": "Jane Doe", "short_name": "Jane", "role": "PM"}},
        )

        edits = client.get("/api/projects/1/edits").json()
        hidden = client.get("/api/projects/1/hidden").json()
        starred = client.get("/api/projects/1/starred").json()
        tags = client.get("/api/projects/1/tags").json()
        badges = client.get("/api/projects/1/deleted-badges").json()
        people = client.get("/api/projects/1/people").json()

        assert edits["q-p1-10"] == "Better text"
        assert hidden["q-p1-10"] is True
        assert starred["q-p1-10"] is True
        assert set(tags["q-p1-10"]) == {"important", "follow-up"}
        assert badges["q-p1-10"] == ["confusion"]
        assert people["p1"]["full_name"] == "Jane Doe"

    def test_clear_all_state_for_quote(self, client: TestClient) -> None:
        """Set everything, then clear everything — quote returns to baseline."""
        # Set
        client.put("/api/projects/1/edits", json={"q-p1-10": "Edit"})
        client.put("/api/projects/1/hidden", json={"q-p1-10": True})
        client.put("/api/projects/1/starred", json={"q-p1-10": True})
        client.put("/api/projects/1/tags", json={"q-p1-10": ["tag"]})
        client.put("/api/projects/1/deleted-badges", json={"q-p1-10": ["confusion"]})

        # Clear
        client.put("/api/projects/1/edits", json={})
        client.put("/api/projects/1/hidden", json={})
        client.put("/api/projects/1/starred", json={})
        client.put("/api/projects/1/tags", json={})
        client.put("/api/projects/1/deleted-badges", json={})

        assert client.get("/api/projects/1/edits").json() == {}
        assert client.get("/api/projects/1/hidden").json() == {}
        assert client.get("/api/projects/1/starred").json() == {}
        assert client.get("/api/projects/1/tags").json() == {}
        assert client.get("/api/projects/1/deleted-badges").json() == {}


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    """PUTting the same state twice should produce the same result."""

    def test_hidden_put_idempotent(self, client: TestClient) -> None:
        payload = {"q-p1-10": True, "q-p1-46": True}
        client.put("/api/projects/1/hidden", json=payload)
        client.put("/api/projects/1/hidden", json=payload)

        data = client.get("/api/projects/1/hidden").json()
        assert data == payload

    def test_starred_put_idempotent(self, client: TestClient) -> None:
        payload = {"q-p1-26": True}
        client.put("/api/projects/1/starred", json=payload)
        client.put("/api/projects/1/starred", json=payload)

        data = client.get("/api/projects/1/starred").json()
        assert data == payload

    def test_tags_put_idempotent(self, client: TestClient) -> None:
        payload = {"q-p1-10": ["tag-a", "tag-b"]}
        client.put("/api/projects/1/tags", json=payload)
        client.put("/api/projects/1/tags", json=payload)

        data = client.get("/api/projects/1/tags").json()
        assert set(data["q-p1-10"]) == {"tag-a", "tag-b"}

    def test_edits_put_idempotent(self, client: TestClient) -> None:
        payload = {"q-p1-10": "Same text", "section-search:title": "Same title"}
        client.put("/api/projects/1/edits", json=payload)
        client.put("/api/projects/1/edits", json=payload)

        data = client.get("/api/projects/1/edits").json()
        assert data["q-p1-10"] == "Same text"
        assert data["section-search:title"] == "Same title"

    def test_deleted_badges_put_idempotent(self, client: TestClient) -> None:
        payload = {"q-p1-10": ["confusion"]}
        client.put("/api/projects/1/deleted-badges", json=payload)
        client.put("/api/projects/1/deleted-badges", json=payload)

        data = client.get("/api/projects/1/deleted-badges").json()
        assert data["q-p1-10"] == ["confusion"]
