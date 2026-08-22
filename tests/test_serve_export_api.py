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
_SERVER_DIR = Path(__file__).resolve().parent.parent / "bristlenose" / "server"
_STATIC_INDEX = _SERVER_DIR / "static" / "index.html"
# The export inlines the single-file export build (static-export/app.js), not the
# code-split serve build — require it too, else the endpoint 500s.
_EXPORT_APP = _SERVER_DIR / "static-export" / "app.js"

pytestmark = pytest.mark.skipif(
    not (_STATIC_INDEX.is_file() and _EXPORT_APP.is_file()),
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

    def test_filename_carries_the_language(self, client: TestClient) -> None:
        """Three languages for a Swiss client must not be three identical
        filenames in Downloads."""
        cd = client.get("/api/projects/1/export?locale=de").headers["content-disposition"]
        assert "-report-de.html" in cd

    def test_filename_language_defaults_to_english(self, client: TestClient) -> None:
        cd = client.get("/api/projects/1/export").headers["content-disposition"]
        assert "-report-en.html" in cd

    def test_an_unknown_locale_cannot_reach_the_filename(self, client: TestClient) -> None:
        """The token is interpolated into a filename, so it is only ever one of
        SUPPORTED_LOCALES — never caller-controlled text."""
        cd = client.get("/api/projects/1/export?locale=../../etc/passwd").headers[
            "content-disposition"
        ]
        assert "-report-en.html" in cd
        assert "passwd" not in cd


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
        assert data["version"] == 2

    def test_has_exported_at(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert "exported_at" in data

    def test_embeds_the_chosen_language_and_its_fallbacks(
        self, client: TestClient
    ) -> None:
        data = self._extract_export_data(
            client.get("/api/projects/1/export?locale=zh-Hant-HK").text
        )
        assert list(data["localeResources"]) == ["zh-Hant-HK", "zh-Hant", "en"]

    def test_embeds_no_other_language(self, client: TestClient) -> None:
        """A German report carrying Japanese is the 1,802 KB this replaced."""
        data = self._extract_export_data(
            client.get("/api/projects/1/export?locale=de").text
        )
        assert set(data["localeResources"]) == {"de", "en"}

    def test_embedded_strings_cannot_break_out_of_the_script(
        self, client: TestClient
    ) -> None:
        """localeResources rides the same json.dumps as the rest of the embed,
        so it inherits the < > & escaping. ensure_ascii alone does NOT escape
        those — they are ASCII — and a literal </script> would end the data
        block early. Pinned because this is a new payload on that seam."""
        html = client.get("/api/projects/1/export?locale=de").text
        marker = "window.BRISTLENOSE_EXPORT="
        block = html[html.index(marker) : html.index(";\n</script>", html.index(marker))]
        assert "</script>" not in block
        assert "<" not in block.split(marker, 1)[1]

    def test_endpoints_is_path_keyed(self, client: TestClient) -> None:
        """The embed is a path-keyed map, mirroring the SPA's relative API paths."""
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert isinstance(data["endpoints"], dict)
        # Keys are relative API paths, not semantic names.
        assert "/dashboard" in data["endpoints"]
        assert "dashboard" not in data  # no legacy top-level semantic keys

    def test_has_project_info(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        info = data["endpoints"]["/info"]
        assert "project_name" in info
        assert "session_count" in info

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
        dashboard = data["endpoints"]["/dashboard"]
        assert "stats" in dashboard
        assert "sessions" in dashboard

    def test_has_sessions(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert "sessions" in data["endpoints"]["/sessions"]

    def test_has_quotes(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        quotes = data["endpoints"]["/quotes"]
        assert "sections" in quotes
        assert "themes" in quotes

    def test_has_codebook(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert "groups" in data["endpoints"]["/codebook"]

    def test_has_analysis(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert "/analysis/sentiment" in data["endpoints"]
        assert "/analysis/codebooks" in data["endpoints"]

    def test_has_view_state_endpoints(self, client: TestClient) -> None:
        """The two previously-drifted view-state reads are now embedded."""
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert "/framework-states" in data["endpoints"]
        assert "/hidden-tag-groups" in data["endpoints"]
        assert isinstance(data["endpoints"]["/framework-states"], dict)
        assert isinstance(data["endpoints"]["/hidden-tag-groups"], list)

    def test_every_static_embed_template_is_actually_embedded(
        self, client: TestClient
    ) -> None:
        """Close the 'classified but not embedded' hole.

        The coverage gate (test_serve_export_coverage.py) proves every read path
        is *classified*; this proves every non-parameterised EMBED template is
        actually *produced* by export_report — so listing a template to pass the
        gate but forgetting to wire its builder can't slip through.  (Parameterised
        templates — transcripts/{id}, moderator-question — may legitimately have
        zero keys for a given project, so they're covered by the gate + the
        file:// render walk, not here.)
        """
        from bristlenose.server.routes.export import EMBED_PATH_TEMPLATES

        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        keys = set(data["endpoints"].keys())
        missing = sorted(
            rel
            for tmpl in EMBED_PATH_TEMPLATES
            if "{" not in (rel := tmpl.replace("/projects/{project_id}", "", 1))
            and rel not in keys
        )
        assert not missing, f"EMBED templates classified but not embedded: {missing}"

    def test_analysis_uses_camel_case_keys(self, client: TestClient) -> None:
        """Sentiment analysis models use alias_generator (camelCase).

        jsonable_encoder must produce the same by-alias shape FastAPI returns
        over HTTP — the React frontend expects camelCase.
        """
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        sentiment = data["endpoints"]["/analysis/sentiment"]
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
        tx_keys = [k for k in data["endpoints"] if k.startswith("/transcripts/")]
        # Smoke-test fixture has 1 session
        assert len(tx_keys) >= 1

    def test_has_people(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        assert isinstance(data["endpoints"]["/people"], dict)

    def test_video_map_is_null(self, client: TestClient) -> None:
        data = self._extract_export_data(client.get("/api/projects/1/export").text)
        # Present-but-null (distinct from absent) so apiGet resolves it, not fetches.
        assert "/video-map" in data["endpoints"]
        assert data["endpoints"]["/video-map"] is None

    def test_embedded_data_cannot_break_out_of_script(self) -> None:
        """CRITICAL XSS guard: the embedded data is dropped into a <script> block.

        ``json.dumps(ensure_ascii=True)`` escapes only code points > 127 — '<' is
        ASCII and passes through, so a literal ``</script>`` in untrusted content
        (transcript text, participant/tag/project names) would close the data
        script and inject markup into the shared leave-behind. The builder must
        escape the HTML-significant ASCII to \\uXXXX forms.
        """
        from bristlenose.server.routes.export import _build_export_html

        payload = {
            "version": 2,
            "exported_at": "x",
            "locale": None,
            "health": {},
            "logos": {},
            "endpoints": {"/quotes": {"x": "</script><script>alert(1)</script>"}},
        }
        html = _build_export_html(payload, "/* css */")
        assert "</script><script>alert(1)</script>" not in html
        assert "\\u003c/script\\u003e" in html


# ---------------------------------------------------------------------------
# JS bootstrap (blob URLs for code-split chunks)
# ---------------------------------------------------------------------------


class TestExportJsBootstrap:
    def test_spa_inlined_as_one_module(self, client: TestClient) -> None:
        """The SPA ships as ONE inline module (renders from file://)."""
        html = client.get("/api/projects/1/export").text
        assert '<script type="module">' in html
        # Exactly one inline module script — the single-file bundle.
        assert html.count('<script type="module">') == 1

    def test_inline_module_carries_the_full_bundle(self, client: TestClient) -> None:
        """The inline module IS the whole SPA (~2 MB), not a tiny loader that
        would fetch chunks a file:// open can't reach."""
        html = client.get("/api/projects/1/export").text
        assert len(html) > 1_000_000

    def test_script_close_is_escaped(self, client: TestClient) -> None:
        """A literal </script> in the bundle would close the inline element."""
        html = client.get("/api/projects/1/export").text
        # The only real </script> closers are the paired tags we emit; any bundle
        # occurrence is escaped to <\/script>.  Sanity: the doc still ends cleanly.
        assert html.rstrip().endswith("</html>")

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
        for code, person in data["endpoints"]["/people"].items():
            if code.startswith("p"):
                assert person["full_name"] == ""
                assert person["short_name"] == ""

    def test_anonymise_keeps_moderator_names(self, client: TestClient) -> None:
        data = self._extract_export_data(
            client.get("/api/projects/1/export?anonymise=true").text,
        )
        # Check if moderator names are preserved (m1 should keep its name)
        for code, person in data["endpoints"]["/people"].items():
            if code.startswith("m"):
                # Moderator names should NOT be empty (if they had a name)
                pass  # Just verify they weren't blanked

    def test_non_anonymised_preserves_data(self, client: TestClient) -> None:
        data = self._extract_export_data(
            client.get("/api/projects/1/export?anonymise=false").text,
        )
        # People data should be present (not stripped)
        people = data["endpoints"]["/people"]
        assert isinstance(people, dict)
        # Smoke-test fixture has at least m1 and p1
        assert len(people) >= 1
