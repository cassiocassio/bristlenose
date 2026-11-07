"""Trust gate: what an HTML export must not carry (trust map rows 34, 36, 63).

The export is built from the API's own return values and embedded as one JSON object. Participants'
screens (the hover frames, the Screens lens stills), transcription diagnostics and subtitles are
server-only; the embedded ``endpoints`` map must hold none of them, and nothing in the object may
name the folder the researcher's recordings sit in on their own machine.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from bristlenose.server.app import create_app
from bristlenose.server.routes.export import EMBED_PATH_TEMPLATES, SERVER_ONLY_PATH_TEMPLATES
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_SERVER_ONLY_WORDS = ("turn-frames", "screens", "transcription-quality", "subtitles")


@pytest.fixture
def exported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[dict, str, Path]:
    monkeypatch.delenv("BRISTLENOSE_MCP_ANONYMISE", raising=False)
    project = tmp_path / "Client Acme interviews"
    shutil.copytree(_FIXTURE_DIR, project, ignore=shutil.ignore_patterns("bristlenose.log*"))
    client = AuthTestClient(create_app(project_dir=project, dev=False, db_url="sqlite://"))
    resp = client.get("/api/projects/1/export")
    assert resp.status_code == 200, resp.text
    match = re.search(r"window\.BRISTLENOSE_EXPORT=(.*?);\n</script>", resp.text, re.S)
    assert match, "the embedded data object was not found"
    return json.loads(match.group(1)), match.group(1), project


def test_positive_control_the_embedded_object_holds_the_report_data(exported) -> None:
    data, _, _ = exported
    assert data["endpoints"], "no embedded endpoints"
    assert any("/quotes" in key for key in data["endpoints"]), list(data["endpoints"])[:5]


def test_no_participant_screen_or_diagnostic_endpoint_is_embedded(exported) -> None:
    data, _, _ = exported
    bad = [k for k in data["endpoints"] if any(w in k for w in _SERVER_ONLY_WORDS)]
    assert not bad, bad


def test_the_server_only_routes_are_not_also_embed_routes() -> None:
    assert not (EMBED_PATH_TEMPLATES & SERVER_ONLY_PATH_TEMPLATES)
    for word in _SERVER_ONLY_WORDS:
        assert any(word in t for t in SERVER_ONLY_PATH_TEMPLATES), word
        assert not any(word in t for t in EMBED_PATH_TEMPLATES), word


def test_the_export_names_no_folder_on_the_researchers_machine(exported) -> None:
    _, raw, project = exported
    for needle in (str(project), project.name, str(project).replace("/", "\\/")):
        assert needle not in raw, f"the export carries {needle!r}"
