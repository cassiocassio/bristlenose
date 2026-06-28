"""Endpoint tests for the dev Run Inspector (/api/dev/run[.json]).

These import the FastAPI stack, so they run in CI (and on a dev machine), not
in the dependency-light cloud env where the pure-function tests in
``tests/test_run_inspector.py`` run. Data-shaping correctness is covered there;
here we only assert the endpoints are wired, dev-gated, and don't 500 on an
empty project.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server import run_inspector as ri
from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient


def _seed(internal: Path) -> None:
    internal.mkdir(parents=True, exist_ok=True)
    (internal / ri.JSONL_LLM).write_text(
        json.dumps(
            {
                "ts": "2026-06-27T14:22:39Z",
                "run_id": "r1",
                "stage": "quote_extraction",
                "gen_ai.system": "anthropic",
                "gen_ai.request.model": "claude-opus-4-8",
                "gen_ai.usage.input_tokens": 8000,
                "gen_ai.usage.output_tokens": 1200,
                "elapsed_ms": 4200,
                "retry_count": 0,
                "finish_reason": "stop",
                "cost_usd_actual_estimate": 0.18,
                "cost_usd_predicted": 0.17,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    # Canonical event schema (bristlenose/events.py): discriminator is the
    # `event` field (run_started/run_progress/run_completed); `kind` is the
    # LEVEL ("run"), not the event name. An earlier fixture put the event name
    # in `kind` — a shape the pipeline never writes — which let the schema bug
    # in run_inspector.py pass undetected. Keep this in sync with events.py.
    (internal / ri.JSONL_EVENTS).write_text(
        "\n".join(
            json.dumps(e)
            for e in [
                {"kind": "run", "event": "run_started", "run_id": "r1",
                 "started_at": "2026-06-27T14:18:30Z",
                 "process": {"os": "darwin-arm64"}},
                {"kind": "run", "event": "run_progress", "run_id": "r1",
                 "stage": "quote_extraction", "elapsed_seconds": 0.0, "stage_fraction": 0.5},
                {"kind": "run", "event": "run_completed", "run_id": "r1",
                 "ended_at": "2026-06-27T14:22:42Z"},
            ]
        )
        + "\n",
        encoding="utf-8",
    )


@pytest.fixture()
def dev_client(tmp_path: Path) -> TestClient:
    _seed(tmp_path / "bristlenose-output" / ".bristlenose")
    app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
    return AuthTestClient(app)


def test_run_json_returns_payload(dev_client: TestClient) -> None:
    r = dev_client.get("/api/dev/run.json")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["summary"]["n"] == 1
    assert data["prov"]["provider"] == "Claude"
    assert len(data["stages"]) == 1
    # Lifecycle fields are derived from the `event` discriminator, not `kind`.
    # These three pin the schema-mismatch regression (all were "—" when the
    # detector read the wrong field).
    assert data["prov"]["run_id"] == "r1"
    assert data["prov"]["status"] == "completed"
    assert data["prov"]["hardware"] == "darwin-arm64"


def test_run_html_renders_and_escapes(dev_client: TestClient) -> None:
    r = dev_client.get("/api/dev/run")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    body = r.text
    assert "Run Inspector" in body
    assert "</script>" in body  # the page's own closing tag exists

    # XSS: a hostile value in the data must not break out of the JSON <script>.
    # `ensure_ascii=True` alone does NOT escape '<' (it's ASCII), so the builder
    # also rewrites <,>,& to \uXXXX. The seeded fixture carries nothing
    # escapable, so the old assertion (looking for < in `body`) could never
    # pass — assert the escaping directly against a payload that has a real
    # </script> breakout attempt.
    hostile = ri.build_run_inspector_html(
        {"ok": True, "evil": "</script><script>alert(1)</script>"}
    )
    assert "</script><script>alert(1)" not in hostile  # no raw breakout
    assert "\\u003c" in hostile  # the '<' was escaped to <


def test_run_empty_project_does_not_500(tmp_path: Path) -> None:
    app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
    client = AuthTestClient(app)
    r = client.get("/api/dev/run")
    assert r.status_code == 200
    assert "No run data yet" in r.text
    j = client.get("/api/dev/run.json")
    assert j.status_code == 200 and j.json()["ok"] is False


def test_run_endpoints_absent_without_dev(tmp_path: Path) -> None:
    app = create_app(project_dir=tmp_path, dev=False, db_url="sqlite://")
    client = AuthTestClient(app)
    assert client.get("/api/dev/run").status_code == 404
    assert client.get("/api/dev/run.json").status_code == 404


def test_run_listed_in_dev_info(dev_client: TestClient) -> None:
    r = dev_client.get("/api/dev/info")
    assert r.status_code == 200
    urls = [e["url"] for e in r.json()["endpoints"]]
    assert "/api/dev/run" in urls
