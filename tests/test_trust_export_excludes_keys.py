"""Trust gate: the HTML export never carries a re-identification key (T22, trust map row 21).

``pii_summary.txt`` (every original PII value), ``llm-calls.jsonl`` (a per-call fingerprint) and
the transcription-quality record sit in the project's ``.bristlenose/`` folder. The export is built
from the API's own return values, never from files, so none of them can reach it unless someone
wires one in. A sentinel planted in each is looked for in the real export, and a planted name
proves the check reads the artefact that does carry researcher data.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from bristlenose.output_paths import project_output_dir
from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_KEYS = {
    "pii_summary.txt": "PIIKEY-zq81-sentinel",
    "llm-calls.jsonl": "LLMCALLS-zq82-sentinel",
    "intermediate/transcription-quality/s1.json": "TQKEY-zq83-sentinel",
}
_NAME = "Zephyrine Quillfeather"


@pytest.fixture
def export_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.delenv("BRISTLENOSE_MCP_ANONYMISE", raising=False)
    project = tmp_path / "input"
    shutil.copytree(_FIXTURE_DIR, project)
    run_dir = project_output_dir(project) / ".bristlenose"
    for rel, sentinel in _KEYS.items():
        path = run_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'{{"note": "{sentinel}"}}\n', encoding="utf-8")
    client = AuthTestClient(create_app(project_dir=project, dev=False, db_url="sqlite://"))
    put = client.put(
        "/api/projects/1/people",
        json={"p1": {"full_name": _NAME, "short_name": "Zephyrine", "role": ""}},
    )
    assert put.status_code == 200, put.text
    resp = client.get("/api/projects/1/export")
    assert resp.status_code == 200, resp.text
    return resp.text


def test_positive_control_the_export_carries_a_planted_name(export_html: str) -> None:
    assert _NAME in export_html or "Zephyrine" in export_html


@pytest.mark.parametrize("rel", sorted(_KEYS))
def test_no_re_identification_key_reaches_the_export(export_html: str, rel: str) -> None:
    assert _KEYS[rel] not in export_html
