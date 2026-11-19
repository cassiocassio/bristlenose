"""The Python half of the Azure transition model, as executable cells.

``tests/fixtures/azure-transition-contract.json`` lists what Azure can answer at the
settings-check stage (bodies recorded from Azure, each with its source) and what
doctor and the preflight must each conclude. One parametrised test drives both real
checks against a local fake Azure per cell; the invariants of the model
(docs/design-azure-state-matrix.md section 5) follow as plain tests.

The Mac half is not here: its strings and states are pinned by the Swift suite, and
reading this file from Swift is parked (owner's choice of the minimal version).
"""

from __future__ import annotations

import http.server
import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

CONTRACT = json.loads(
    (Path(__file__).parent / "fixtures" / "azure-transition-contract.json").read_text(encoding="utf-8")
)
DEPLOYMENT = "research-deployment"
API_VERSION = "2024-10-21"


@pytest.fixture(autouse=True)
def _fresh_ceilings(monkeypatch) -> Iterator[None]:
    # The learned output ceiling is process-wide; each cell starts with none.
    from bristlenose.llm import client

    client._azure_ceilings.clear()
    monkeypatch.setattr("openai._base_client.time.sleep", lambda _s: None)
    yield
    client._azure_ceilings.clear()


@pytest.fixture
def fake() -> Iterator[dict]:
    """A plain-HTTP fake Azure answering ``state["replies"]`` in order, the last one
    repeating; ``state["hits"]`` counts POSTs."""
    state: dict = {"replies": [(200, b"{}")], "hits": 0}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            if n:
                self.rfile.read(n)
            status, raw = state["replies"][min(state["hits"], len(state["replies"]) - 1)]
            state["hits"] += 1
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *a) -> None:  # noqa: ANN002
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    state["endpoint"] = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()


def _replies(cell: dict) -> list[tuple[int, bytes]]:
    return [(status, json.dumps(CONTRACT["bodies"][name]["body"]).encode())
            for status, name in cell["replies"]]


@pytest.mark.parametrize("cell", CONTRACT["cells"], ids=lambda c: c["event"])
def test_doctor_concludes_what_the_model_says(fake, cell) -> None:
    from bristlenose.doctor import _validate_azure_key

    fake["replies"] = _replies(cell)
    assert list(_validate_azure_key(fake["endpoint"], "k", DEPLOYMENT, API_VERSION)) == cell["doctor"]


@pytest.mark.parametrize("cell", CONTRACT["cells"], ids=lambda c: c["event"])
def test_the_preflight_concludes_what_the_model_says(fake, cell) -> None:
    from bristlenose.preflight.api_key import _validate_azure

    fake["replies"] = _replies(cell)
    result = _validate_azure("k", fake["endpoint"], DEPLOYMENT, API_VERSION)
    assert [result.ok, result.error_class] == cell["preflight"]


def test_every_body_names_its_source_and_every_cell_its_bodies() -> None:
    for name, entry in CONTRACT["bodies"].items():
        assert entry.get("source"), f"body {name} has no source"
    for cell in CONTRACT["cells"]:
        for _status, name in cell["replies"]:
            assert name in CONTRACT["bodies"], f"{cell['event']} names an unknown body {name}"


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def test_the_cap_retry_happens_at_most_once(fake) -> None:
    from bristlenose.doctor import _validate_azure_key

    # Each refusal names a LOWER ceiling (the recorded body with its numbers changed:
    # synthetic, to drive the bound). With the real body the retry also stops because
    # a ceiling not below the request is never retried; this isolates the attempt bound.
    real = CONTRACT["bodies"]["cap_refusal"]["body"]

    def refusal(requested: int, ceiling: int) -> bytes:
        msg = real["error"]["message"].replace("64000", str(requested)).replace("32768", str(ceiling))
        return json.dumps({"error": {**real["error"], "message": msg}}).encode()

    fake["replies"] = [(400, refusal(64000, 32768)), (400, refusal(32768, 16384)),
                       (400, refusal(16384, 8192))]
    valid, detail = _validate_azure_key(fake["endpoint"], "k", DEPLOYMENT, API_VERSION)
    assert valid is False and detail.startswith("HTTP 400")
    assert fake["hits"] == 2


def test_a_learned_ceiling_belongs_to_one_endpoint_and_deployment() -> None:
    from bristlenose.llm.client import learned_azure_ceiling, remember_azure_ceiling

    remember_azure_ceiling("https://a.openai.azure.com", "d1", 32768)
    assert learned_azure_ceiling("https://a.openai.azure.com/", "d1") == 32768
    assert learned_azure_ceiling("https://a.openai.azure.com", "d2") is None
    assert learned_azure_ceiling("https://b.openai.azure.com", "d1") is None


@pytest.mark.parametrize("changed", ["deployment", "endpoint", "api_version", "key"])
def test_a_cached_preflight_verdict_belongs_to_one_configuration(changed) -> None:
    # The 24-hour preflight cache is keyed on this fingerprint: any of the four
    # changed is a new request, checked again, never a cached green.
    from bristlenose.preflight.api_key import request_fingerprint

    base = {"deployment": "d1", "endpoint": "https://a.openai.azure.com",
            "api_version": API_VERSION, "key": "k1"}
    other = {**base, changed: base[changed] + "x"}

    def fp(c: dict) -> str:
        return request_fingerprint(c["deployment"], {"max_tokens": 64000}, key=c["key"],
                                   endpoint=(c["endpoint"], c["api_version"]))

    assert fp(base) != fp(other)
