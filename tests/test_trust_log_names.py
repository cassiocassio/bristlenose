"""Trust gate: file names and model-typed values stay out of the log (T20, trust map rows 14/31/76).

Owner ruling, 6 Nov 2026: log files are debug output and must not leak names, filenames or
quote text. Two sites were left at INFO: the session registry's "keeps its number" line named the
recording, and the MCP tool-input-error line echoed the value the model sent, which can be text
it copied from a transcript. Each is exercised through its real code with a positive control
that the line itself is still written.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.output_paths import project_output_dir
from bristlenose.server.app import create_app
from bristlenose.session_registry import SessionRegistry
from tests.test_mcp_server import _FIXTURE_DIR, _rpc
from tests.test_session_registry import _file, _ingest

_NAME = "Zephyrine Quillfeather"


def test_the_registry_log_line_for_a_kept_number_names_no_recording(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    out = tmp_path / "out"
    b, c = _file(tmp_path, "client-acme-b.wav", 1), _file(tmp_path, "client-acme-c.wav", 2)
    reg = SessionRegistry.load(out)
    reg.apply(_ingest([b, c]))
    reg.save()
    a = _file(tmp_path, "client-acme-a.wav", 0)  # recorded first, arrives last
    with caplog.at_level(logging.DEBUG, logger="bristlenose.session_registry"):
        SessionRegistry.load(out).apply(_ingest([a, b, c]))
    lines = [r.getMessage() for r in caplog.records]
    assert any("keeps" in line for line in lines), "positive control: the line is written"
    assert not any("acme" in line for line in lines), lines


def test_an_mcp_input_error_does_not_log_what_the_model_sent(tmp_path: Path) -> None:
    """Read from the real log file: the MCP SDK's own logger also writes the failed tool's
    message, which echoes the value the model sent, so the file is the only honest witness.
    The serve attaches its own log file to the project it serves, so serve a copy."""
    project = tmp_path / "input"
    # Without the fixture's own log, which earlier runs fill with whatever they logged.
    shutil.copytree(_FIXTURE_DIR, project, ignore=shutil.ignore_patterns("bristlenose.log*"))
    app = create_app(project_dir=project, dev=True, db_url="sqlite://")
    app.state.auth_token = "test-mcp-token"
    try:
        with TestClient(app, base_url="http://127.0.0.1:8150") as client:
            resp = _rpc(
                client, "test-mcp-token", "tools/call",
                {"name": "search_quotes",
                 "arguments": {"project_id": 1, "query": "x", "sentiment": _NAME}},
                id_=61,
            )
        for h in logging.getLogger().handlers:
            h.flush()
        log = (project_output_dir(project) / ".bristlenose" / "bristlenose.log").read_text(
            encoding="utf-8")
    finally:
        for h in logging.getLogger().handlers[:]:
            logging.getLogger().removeHandler(h)
            h.close()
    assert resp.json()["result"].get("isError") is True, resp.text
    assert "mcp_tool_input_error" in log, "positive control: our own line is written"
    assert "Zephyrine" not in log, log
