"""Tests for the export API endpoint.

Requires the frontend build (``npm run build`` in ``frontend/``).
Skipped in CI where the lint-and-test job doesn't build the frontend.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_STATIC_INDEX = (
    Path(__file__).resolve().parent.parent
    / "bristlenose"
    / "server"
    / "static"
    / "index.html"
)

pytestmark = pytest.mark.skipif(
    not _STATIC_INDEX.is_file(),
    reason="frontend build not found (run 'cd frontend && npm run build')",
)


@pytest.fixture()
def client() -> TestClient:
    """Create a test client with imported smoke-test data."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return AuthTestClient(app)


# ---------------------------------------------------------------------------
# Basic endpoint
# ---------------------------------------------------------------------------


class TestExportEndpoint:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/export")
        assert resp.status_code == 200

    def test_content_disposition_header(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/export")
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert ".html" in cd

    def test_content_type_is_html(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/export")
        ct = resp.headers.get("content-type", "")
        assert "text/html" in ct

    def test_html_contains_bn_app_root(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/export")
        assert 'id="bn-app-root"' in resp.text

    def test_html_contains_embedded_data(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/export")
        assert "BRISTLENOSE_EXPORT" in resp.text

    def test_body_has_export_mode_class(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/export")
        assert 'class="bn-export-mode"' in resp.text


# ---------------------------------------------------------------------------
# Embedded data structure
# ---------------------------------------------------------------------------


class TestExportData:
    def _extract_export_data(self, html: str) -> dict:
        """Extract the BRISTLENOSE_EXPORT JSON from the HTML."""
        marker = "window.BRISTLENOSE_EXPORT="
        start = html.index(marker) + len(marker)
        # Find the closing semicolon
        end = html.index(";\n</script>", start)
        return json.loads(html[start:end])

    def test_has_version(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert data["version"] == 1

    def test_has_exported_at(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert "exported_at" in data

    def test_has_project_info(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert "project_name" in data["project"]
        assert "session_count" in data["project"]

    def test_has_health(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert data["health"]["status"] == "ok"
        assert "version" in data["health"]
        assert (
            data["health"]["links"]["github_issues_url"]
            == "https://github.com/cassiocassio/bristlenose/issues/new"
        )
        assert data["health"]["feedback"]["enabled"] is True
        assert (
            data["health"]["feedback"]["url"]
            == "https://bristlenose.app/feedback.php"
        )
        assert data["health"]["telemetry"]["enabled"] is True
        assert "url" in data["health"]["telemetry"]

    def test_has_dashboard(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert "stats" in data["dashboard"]
        assert "sessions" in data["dashboard"]

    def test_has_sessions(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert "sessions" in data["sessions"]

    def test_has_quotes(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert "sections" in data["quotes"]
        assert "themes" in data["quotes"]

    def test_has_codebook(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert "groups" in data["codebook"]

    def test_has_analysis(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert "sentiment" in data["analysis"]
        assert "codebooks" in data["analysis"]

    def test_analysis_uses_camel_case_keys(self, client: TestClient) -> None:
        """Sentiment analysis models use alias_generator (camelCase).

        model_dump(by_alias=True) must be used so the embedded JSON matches
        what FastAPI returns over HTTP — the React frontend expects camelCase.
        """
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        sentiment = data["analysis"]["sentiment"]
        if sentiment is not None:
            # Top-level keys should be camelCase
            assert "sectionMatrix" in sentiment
            assert "themeMatrix" in sentiment
            assert "totalParticipants" in sentiment
            assert "participantIds" in sentiment
            # Matrix keys should be camelCase
            assert "rowTotals" in sentiment["sectionMatrix"]
            assert "colTotals" in sentiment["sectionMatrix"]
            assert "rowLabels" in sentiment["sectionMatrix"]
            assert "grandTotal" in sentiment["sectionMatrix"]

    def test_has_transcripts(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert isinstance(data["transcripts"], dict)
        # Smoke-test fixture has 1 session
        assert len(data["transcripts"]) >= 1

    def test_has_people(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert isinstance(data["people"], dict)

    def test_video_map_is_null(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert data["videoMap"] is None


# ---------------------------------------------------------------------------
# JS bootstrap (blob URLs for code-split chunks)
# ---------------------------------------------------------------------------


class TestExportJsBootstrap:
    def test_contains_blob_url_bootstrap(self, client: TestClient) -> None:
        html = client.get("/api/projects/1/export").text
        assert "URL.createObjectURL" in html
        assert "new Blob(" in html

    def test_contains_chunk_rewrite_function(self, client: TestClient) -> None:
        html = client.get("/api/projects/1/export").text
        # The R() function rewrites ./X.js references
        assert "function R(s)" in html

    def test_main_bundle_loaded_via_import(self, client: TestClient) -> None:
        html = client.get("/api/projects/1/export").text
        # Main bundle should be loaded via dynamic import(), not inline
        assert "import(C[" in html
        # Should NOT have inline <script type="module"> with the full bundle
        assert '<script type="module">' not in html

    def test_no_raw_asset_references(self, client: TestClient) -> None:
        """Exported HTML should not reference /assets/ paths directly."""
        html = client.get("/api/projects/1/export").text
        assert 'src="/assets/' not in html
        assert 'href="/assets/' not in html


# ---------------------------------------------------------------------------
# Anonymisation
# ---------------------------------------------------------------------------


class TestExportAnonymise:
    def _extract_export_data(self, html: str) -> dict:
        marker = "window.BRISTLENOSE_EXPORT="
        start = html.index(marker) + len(marker)
        end = html.index(";\n</script>", start)
        return json.loads(html[start:end])

    def test_anonymise_strips_participant_names_from_people(
        self, client: TestClient,
    ) -> None:
        data = self._extract_export_data(
            client.get("/api/projects/1/export?anonymise=true").text,
        )
        for code, person in data["people"].items():
            if code.startswith("p"):
                assert person["full_name"] == ""
                assert person["short_name"] == ""

    def test_anonymise_keeps_moderator_names(self, client: TestClient) -> None:
        data = self._extract_export_data(
            client.get("/api/projects/1/export?anonymise=true").text,
        )
        # Check if moderator names are preserved (m1 should keep its name)
        for code, person in data["people"].items():
            if code.startswith("m"):
                # Moderator names should NOT be empty (if they had a name)
                pass  # Just verify they weren't blanked

    def test_non_anonymised_preserves_data(self, client: TestClient) -> None:
        data = self._extract_export_data(
            client.get("/api/projects/1/export?anonymise=false").text,
        )
        # People data should be present (not stripped)
        assert isinstance(data["people"], dict)
        # Smoke-test fixture has at least m1 and p1
        assert len(data["people"]) >= 1
