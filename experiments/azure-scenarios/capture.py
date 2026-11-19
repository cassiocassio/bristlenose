"""Capture what a researcher sees in each Azure scenario, from the running code.

    .venv/bin/python experiments/azure-scenarios/capture.py <label>

Writes ``captures-<label>.json`` beside this file. ``render.py`` turns one or two
capture files (before / after) into the scenario page under ``docs/mockups/``.

Nothing here can reach a real credential or a real Azure resource:

- The machine's configuration is isolated exactly as the test suite isolates it
  (``tests/conftest.py`` ``_isolate_machine_config``): no ``.env``, no user config,
  and an empty in-memory credential store instead of the Keychain.
- The key is a fixed fake, and Azure is a plain-HTTP fake server on localhost whose
  answers are bodies already recorded from Azure (error bodies are Azure's own words).
- The fake's address is replaced in the captured text by a placeholder resource
  URL, and the home folder by ``~``, so the page shows what a researcher would see.

Strings are never typed here: CLI frames are the CLI's own output, server frames are
the refusal the server raises plus the SPA's locale value for its reason, and Mac
frames come from ``mac_strings()`` (locale keys read from the en locale file).
"""

from __future__ import annotations

import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

# Rich decides on colour and width when bristlenose.cli is imported: set them first.
os.environ.update({"FORCE_COLOR": "1", "COLUMNS": "80", "TERM": "xterm-256color"})
os.environ.pop("NO_COLOR", None)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

FAKE_KEY = "fake-azure-key-0000000000000000"
DEPLOYMENT = "research-gpt41mini"
PLACEHOLDER = "https://contoso-research.openai.azure.com"

# Bodies Azure sent on 12 and 19 Nov 2026 (the error bodies verbatim; the 200 is the
# shape of a chat completion, reduced to what the client reads).
OK_CHAT = {"choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}],
           "id": "chatcmpl-fake", "object": "chat.completion", "model": "gpt-4.1-mini",
           "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6}}
AZ_401 = {"error": {"code": "401", "message": "Access denied due to invalid subscription key or wrong API endpoint. Make sure to provide a valid key for an active subscription and use a correct regional API endpoint for your resource."}}
AZ_404_DEPLOYMENT = {"error": {"type": "invalid_request_error", "code": "DeploymentNotFound", "message": "The API deployment for this resource does not exist. If you created the deployment within the last 5 minutes, please wait a moment and try again."}}
AZ_404_GENERIC = {"error": {"code": "404", "message": "Resource not found"}}
AZ_400_CAP = {"error": {"message": "max_tokens is too large: 64000. This model supports at most 32768 completion tokens, whereas you provided 64000.", "type": "invalid_request_error", "param": "max_tokens", "code": "invalid_value"}}


class Fake:
    """A plain-HTTP fake Azure; ``script`` is a list of (status, body, headers) replies,
    the last one repeating."""

    def __init__(self) -> None:
        self.script: list[tuple[int, Any, dict[str, str]]] = [(200, OK_CHAT, {})]
        self.hits = 0
        fake = self

        class H(http.server.BaseHTTPRequestHandler):
            def _reply(self) -> None:
                n = int(self.headers.get("Content-Length") or 0)
                if n:
                    self.rfile.read(n)
                i = min(fake.hits, len(fake.script) - 1)
                fake.hits += 1
                status, body, headers = fake.script[i]
                raw = json.dumps(body).encode() if not isinstance(body, bytes) else body
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(raw)

            do_GET = do_POST = do_HEAD = _reply  # noqa: N815

            def log_message(self, *a: Any) -> None:
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.endpoint = f"http://127.0.0.1:{self.server.server_address[1]}"

    def set(self, *script: tuple[int, Any, dict[str, str]]) -> None:
        self.script = list(script)
        self.hits = 0


class _TPF:
    """Enough of pytest's TempPathFactory for ``_isolate_machine_config``."""

    def __init__(self) -> None:
        self.base = Path(tempfile.mkdtemp(prefix="bn-azure-scenarios-"))

    def getbasetemp(self) -> Path:
        return self.base

    def mktemp(self, name: str) -> Path:
        return Path(tempfile.mkdtemp(prefix=name, dir=self.base))


def _isolate() -> Any:
    import pytest

    import bristlenose.cli  # noqa: F401  (bind module-level names before rebinding)
    from tests import conftest

    mp = pytest.MonkeyPatch()
    conftest._isolate_machine_config(mp, _TPF())
    mp.setattr("openai._base_client.time.sleep", lambda _s: None, raising=False)
    return mp


def _clean(text: str, fake: Fake | None, home: str) -> str:
    text = text.replace(FAKE_KEY, "***")
    if fake is not None:
        text = text.replace(fake.endpoint + "/", PLACEHOLDER + "/").replace(fake.endpoint, PLACEHOLDER)
        port = fake.endpoint.rsplit(":", 1)[1]
        text = text.replace(f"127.0.0.1:{port}", PLACEHOLDER.split("//")[1])
    text = text.replace(home, "~")
    text = re.sub(r"/(private/)?var/folders/[^\s/]+/[^\s/]+/T/[^\s]*", "<temp folder>", text)
    return text


def _invoke(args: list[str], env: dict[str, str], input_text: str | None = None) -> tuple[str, int]:
    from typer.testing import CliRunner

    from bristlenose.cli import app

    full = {"COLUMNS": "80", "TERM": "xterm-256color", "FORCE_COLOR": "1", "NO_COLOR": "", **env}
    result = CliRunner().invoke(app, args, env=full, input=input_text, catch_exceptions=True)
    out = result.output
    if result.exception and not isinstance(result.exception, SystemExit):
        out += f"\n[harness: exception {type(result.exception).__name__}]"
    return out, result.exit_code


def cli_scenarios(fake: Fake, work: Path) -> list[dict[str, Any]]:
    home = str(Path.home())
    base_env = {
        "BRISTLENOSE_LLM_PROVIDER": "azure",
        "BRISTLENOSE_AZURE_API_KEY": FAKE_KEY,
        "BRISTLENOSE_AZURE_ENDPOINT": fake.endpoint,
        "BRISTLENOSE_AZURE_DEPLOYMENT": DEPLOYMENT,
    }
    doctor = [
        ("doctor-ok", "Azure answers the check with 200", [(200, OK_CHAT, {})]),
        ("doctor-bad-key", "Azure answers 401 (key wrong, or wrong regional endpoint)", [(401, AZ_401, {})]),
        ("doctor-deployment-not-found", "Azure answers 404 DeploymentNotFound (deployment name wrong)", [(404, AZ_404_DEPLOYMENT, {})]),
        ("doctor-other-404", "Azure answers a generic 404 (wrong path: a portal or classic URL pasted as the endpoint)", [(404, AZ_404_GENERIC, {})]),
        ("doctor-cap", "Deployment's output limit is lower than 64000: 400, then 200 at the named limit", [(400, AZ_400_CAP, {}), (200, OK_CHAT, {})]),
        ("doctor-429", "Azure is throttling (429)", [(429, {"error": {"code": "429", "message": "Rate limit is exceeded."}}, {"Retry-After": "1"})]),
        ("doctor-5xx", "Azure has an outage (503)", [(503, {"error": {"code": "503", "message": "Service unavailable"}}, {})]),
        ("doctor-redirect", "The endpoint redirects (302)", [(302, b"", {"Location": "https://login.example.com/"})]),
    ]
    out: list[dict[str, Any]] = []
    for sid, trigger, script in doctor:
        fake.set(*script)
        text, code = _invoke(["doctor"], base_env)
        out.append({"id": sid, "surface": "cli", "command": "bristlenose doctor", "trigger": trigger,
                    "text": _clean(text, fake, home), "exit": code})

    # Network failure: an endpoint nothing listens on.
    dead = {**base_env, "BRISTLENOSE_AZURE_ENDPOINT": "http://127.0.0.1:9"}
    text, code = _invoke(["doctor"], dead)
    text = text.replace("http://127.0.0.1:9", PLACEHOLDER).replace("127.0.0.1:9", PLACEHOLDER.split("//")[1])
    out.append({"id": "doctor-network", "surface": "cli", "command": "bristlenose doctor",
                "trigger": "Nothing answers at the endpoint (offline, or a mistyped resource name)",
                "text": _clean(text, None, home), "exit": code})

    # Missing pieces: key alone, no endpoint; no deployment.
    for sid, trigger, drop in [
        ("doctor-no-endpoint", "Key saved, endpoint not set", "BRISTLENOSE_AZURE_ENDPOINT"),
        ("doctor-no-deployment", "Key and endpoint saved, deployment not set", "BRISTLENOSE_AZURE_DEPLOYMENT"),
        ("doctor-no-key", "Endpoint and deployment set, no key", "BRISTLENOSE_AZURE_API_KEY"),
    ]:
        env = {k: v for k, v in base_env.items() if k != drop}
        fake.set((200, OK_CHAT, {}))
        text, code = _invoke(["doctor"], env)
        out.append({"id": sid, "surface": "cli", "command": "bristlenose doctor", "trigger": trigger,
                    "text": _clean(text, fake, home), "exit": code})

    # Run: refused before start (the check fails) and a key revoked mid-run.
    src = REPO / "tests/fixtures/smoke-test/input/Session 1.vtt"
    for sid, trigger, script in [
        ("run-refused-bad-key", "Run started with a rejected key: the setup check stops it before any work", [(401, AZ_401, {})]),
        ("run-refused-deployment", "Run started with a deployment name that doesn't exist", [(404, AZ_404_DEPLOYMENT, {})]),
        ("run-key-revoked-mid-run", "Setup check passes, then every analysis call is refused 401 (key revoked mid-run)",
         [(200, OK_CHAT, {}), (200, OK_CHAT, {}), (401, AZ_401, {})]),
    ]:
        inp = work / sid / "input"
        inp.mkdir(parents=True)
        shutil.copy(src, inp / src.name)
        fake.set(*script)
        text, code = _invoke(["run", str(inp), "--output", str(work / sid / "out"), "--no-serve", "--yes", "--no-fetch"], base_env)
        text = text.replace(str(work / sid), "<project>")
        out.append({"id": sid, "surface": "cli", "command": "bristlenose run <project>/input", "trigger": trigger,
                    "text": _clean(text, fake, home), "exit": code})

    # configure azure: the key prompt (typed), then what it says.
    text, code = _invoke(["configure", "azure"], {}, input_text=FAKE_KEY + "\n")
    out.append({"id": "configure-azure", "surface": "cli", "command": "bristlenose configure azure",
                "trigger": "Researcher stores an Azure key (typed at the prompt)",
                "text": _clean(text, None, home), "exit": code})

    for cmd in (["run", "--help"], ["analyze", "--help"], ["doctor", "--help"], ["configure", "--help"], ["use", "--help"]):
        text, code = _invoke(cmd, {})
        out.append({"id": "help-" + cmd[0], "surface": "cli", "command": "bristlenose " + " ".join(cmd),
                    "trigger": "Help text", "text": _clean(text, None, home), "exit": code})
    return out


def server_scenarios() -> list[dict[str, Any]]:
    from bristlenose.config import BristlenoseSettings, provider_not_ready
    from bristlenose.server.refusal import RefusalError
    from bristlenose.server.routes.autocode import require_provider_ready

    common = json.loads((REPO / "bristlenose/locales/en/common.json").read_text(encoding="utf-8"))
    refusal_strings = common["codebook"]["autocodeRefusal"]
    reason_key = {"no_api_key": "noApiKey", "provider_ambiguous": "providerAmbiguous", "provider_local": "providerLocal"}
    cases = [
        ("no key", {}),
        ("key, no endpoint", {"azure_api_key": FAKE_KEY, "azure_deployment": DEPLOYMENT}),
        ("key and endpoint, no deployment", {"azure_api_key": FAKE_KEY, "azure_endpoint": PLACEHOLDER}),
        ("complete", {"azure_api_key": FAKE_KEY, "azure_endpoint": PLACEHOLDER, "azure_deployment": DEPLOYMENT}),
    ]
    out: list[dict[str, Any]] = []
    for label, fields in cases:
        s = BristlenoseSettings(llm_provider="azure", **fields)
        try:
            require_provider_ready(s)
            autocode = {"status": "starts"}
        except RefusalError as exc:
            reason = exc.reason.value if hasattr(exc.reason, "value") else str(exc.reason)
            k = reason_key.get(reason)
            autocode = {"status": exc.status_code, "reason": reason, "detail": str(exc.message if hasattr(exc, "message") else exc),
                        "spa_key": f"codebook.autocodeRefusal.{k}" if k else None,
                        "spa_text": refusal_strings.get(k) if k else None}
        out.append({"id": "server-" + label.replace(" ", "-").replace(",", ""), "surface": "server",
                    "trigger": f"Azure configured: {label}",
                    "autocode": autocode,
                    "chat_lens": {"detail": provider_not_ready(s) or "(ready)"}})
    return out


def mac_strings() -> list[dict[str, str]]:
    desktop = json.loads((REPO / "bristlenose/locales/en/desktop.json").read_text(encoding="utf-8"))

    def walk(d: Any, prefix: str) -> list[tuple[str, str]]:
        if isinstance(d, dict):
            r: list[tuple[str, str]] = []
            for k, v in d.items():
                r += walk(v, f"{prefix}.{k}")
            return r
        return [(prefix, str(d))]

    flat = dict(walk(desktop, "desktop"))
    keys = [
        "llmSettings.azureSection", "llmSettings.azureEndpoint", "llmSettings.azureDeployment",
        "llmSettings.azureAPIVersion", "llmSettings.lastVerified", "llmSettings.revalidating",
        "llmSettings.status.online", "llmSettings.status.notSetUp", "llmSettings.status.invalid",
        "llmSettings.status.unavailable", "llmSettings.status.checking",
        "llmSettings.validation.azureEndpointMissing", "llmSettings.validation.azureEndpointScheme",
        "llmSettings.validation.azureNotFound", "llmSettings.validation.keyRejected",
        "llmSettings.validation.rateLimited", "llmSettings.validation.httpStatus",
        "llmSettings.validation.timedOut", "llmSettings.validation.offline",
        "llmSettings.validation.unreachable", "llmSettings.validation.networkError",
        "pipeline.failure.auth", "pipeline.failure.apiRequest", "pipeline.failure.modelUnavailable",
        "pipeline.failure.providerNotSetUp", "providerProblem.keyRejected.pill", "providerProblem.keyRejected.body",
    ]
    out = []
    for k in keys:
        full = "desktop." + k
        out.append({"key": full, "value": flat.get(full, "(MISSING KEY)")})
    return out


def main() -> None:
    label = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    sha = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    mp = _isolate()
    try:
        fake = Fake()
        work = Path(tempfile.mkdtemp(prefix="bn-azure-scenario-runs-"))
        data = {"label": label, "sha": sha,
                "cli": cli_scenarios(fake, work),
                "server": server_scenarios(),
                "mac": mac_strings()}
        fake.server.shutdown()
    finally:
        mp.undo()
    blob = json.dumps(data, indent=1, ensure_ascii=False)
    assert FAKE_KEY not in blob
    (HERE / f"captures-{label}.json").write_text(blob, encoding="utf-8")
    print(f"captured {len(data['cli'])} cli, {len(data['server'])} server, {len(data['mac'])} mac strings at {sha}")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    main()
