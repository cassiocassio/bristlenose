"""Trust gate: the HTML export never carries a re-identification key (T22, trust map row 21).

``pii_summary.txt`` (every original PII value), ``llm-calls.jsonl`` (a per-call fingerprint) and
the transcription-quality record sit in the project's ``.bristlenose/`` folder. The export is built
from the API's own return values, never from files, so none of them can reach it unless someone
wires one in. A sentinel planted in each is looked for in the real export, and a planted name
proves the check reads the artefact that does carry researcher data.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from bristlenose.output_paths import project_output_dir
from bristlenose.server.app import create_app
from bristlenose.server.routes import export as export_mod
from bristlenose.transcription_quality import RECORD_VERSION, read_records, write_record
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
    # CI builds no frontend and the export route needs a bundle to inline, so a stub one stands in
    # (the pattern of test_export_anonymise_buckets.py). Never a skipif: that would take this
    # privacy gate out of CI.
    bundle = tmp_path / "static-export"
    bundle.mkdir()
    (bundle / "app.js").write_text("// stub", encoding="utf-8")
    (bundle / "app.css").write_text("/* stub */", encoding="utf-8")
    monkeypatch.setattr(export_mod, "_EXPORT_STATIC_DIR", bundle)
    project = tmp_path / "input"
    shutil.copytree(_FIXTURE_DIR, project)
    run_dir = project_output_dir(project) / ".bristlenose"
    # Each file is written the way its real reader reads it, so a route that embedded what the
    # reader returns, and not just a raw copy, would carry the sentinel (Fable review, 7 Nov):
    # a current-version quality record, and a call row with the sentinel in a field a reader
    # would surface; the PII summary is plain text.
    (run_dir).mkdir(parents=True, exist_ok=True)
    (run_dir / "pii_summary.txt").write_text(_KEYS["pii_summary.txt"] + "\n", encoding="utf-8")
    (run_dir / "llm-calls.jsonl").write_text(
        json.dumps({"model": _KEYS["llm-calls.jsonl"], "outcome": "ok", "session_id": "s1"}) + "\n",
        encoding="utf-8",
    )
    write_record(
        project_output_dir(project), "s1",
        {"version": RECORD_VERSION, "engine": _KEYS["intermediate/transcription-quality/s1.json"]},
    )
    client = AuthTestClient(create_app(project_dir=project, dev=False, db_url="sqlite://"))
    put = client.put(
        "/api/projects/1/people",
        json={"p1": {"full_name": _NAME, "short_name": "Zephyrine", "role": ""}},
    )
    assert put.status_code == 200, put.text
    resp = client.get("/api/projects/1/export")
    assert resp.status_code == 200, resp.text
    return resp.text


def test_the_quality_record_is_one_the_reader_accepts(tmp_path: Path) -> None:
    """Without this the quality leg could not fail: a record of another version is skipped."""
    write_record(tmp_path, "s1", {"version": RECORD_VERSION, "engine": "x"})
    assert read_records(tmp_path)["s1"]["engine"] == "x"


def test_positive_control_the_export_carries_a_planted_name(export_html: str) -> None:
    assert _NAME in export_html or "Zephyrine" in export_html


@pytest.mark.parametrize("rel", sorted(_KEYS))
def test_no_re_identification_key_reaches_the_export(export_html: str, rel: str) -> None:
    assert _KEYS[rel] not in export_html
