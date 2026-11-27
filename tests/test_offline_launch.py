"""The Mac app with the network off: the serve comes up, and the checks fail fast and plainly.

App reviewers often test a launch offline, and before this file nothing did. The Python half
of that launch is the sidecar's ``serve --no-open --port 0 <project>`` (``ServeManager``'s
arguments); the first Analyse adds the run's preflight. With every non-loopback connection
refused (``tests/offline_guard.py``, the Wi-Fi-off shape: the name does not resolve):

1. the serve binds, prints its Report line and answers ``/report/`` within the app's 30 s,
   with no font or other request to fail on the way. The smoke study, as a clean checkout
   has it, has no Signals snapshot yet, so the serve's startup repair asks the provider for
   one in the background (``_schedule_missing_signal_snapshot``, by design), with the
   Signals lens withheld meanwhile. Offline the SDK retries for about 21 s and the repair
   gives up; until then, every attempt out is to the provider (the guard logs each one),
   and afterwards the serve still answers and Signals is no longer withheld. A launch-time
   call to the same provider host, a key check say, would hide among the repair's: the
   guard sees hosts, not callers;
2. the run's preflight answers each provider's network and key check in seconds with
   ``network`` / "Can't reach", never a hang and never "key rejected".

Wi-Fi off only: the lookup fails at once. A network that accepts a connection and then
says nothing (a captive portal) is not modelled here.

The Swift half (Welcome window, news check, meeting sources) is walked by hand: the
checklist is in the launch tracker's ``c-offline`` note.
"""

from __future__ import annotations

import io
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from bristlenose.config import BristlenoseSettings
from tests import offline_guard

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_RUN_GUARD = "from tests.offline_guard import main; main()"
#: The app shows its Welcome window within this; the serve must be up well inside it.
_APP_BUDGET_S = 30.0
_REPORT_LINE = re.compile(r"http://127\.0\.0\.1:(\d+)/report/")
_TOKEN_LINE = "[bristlenose] auth-token: "


def _child_env(home: Path) -> dict[str, str]:
    route_around = set(offline_guard.strip_proxies(os.environ))
    env = {
        k: v
        for k, v in os.environ.items()
        if not (
            k.endswith("_API_KEY")
            or k.startswith(("BRISTLENOSE_", "_BRISTLENOSE_"))
            or k in route_around
        )
    }
    env.update(
        HOME=str(home),
        USERPROFILE=str(home),
        PYTHONPATH=str(_ROOT),
        # Three of what the Mac app sets on the sidecar (`childEnvironment(for:)`,
        # `overlayPreferences`): the ones that change what a launch does here.
        BRISTLENOSE_PLATFORM="desktop",
        _BRISTLENOSE_HOSTED_BY_DESKTOP="1",
        # The host always hands a key over, and with one the startup Signals repair runs.
        BRISTLENOSE_ANTHROPIC_API_KEY="sk-ant-offline-test-0000000000",
        PYTHONUNBUFFERED="1",
        # Windows' piped stdout is cp1252 otherwise, and the reader decodes UTF-8.
        PYTHONIOENCODING="utf-8",
    )
    return env


def _copy_tracked(src: Path, dst: Path) -> None:
    """Copy the files git tracks under ``src``, so this study is the one CI starts from.

    A working tree's fixture can carry a gitignored ``bristlenose.db`` from an earlier
    serve, with a Signals snapshot already in it. That study owes nothing, and the test
    passed on the Mac while a clean checkout failed it (27 Nov 2026).
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", "."], cwd=src, capture_output=True,
    )
    assert listed.returncode == 0, listed.stderr.decode("utf-8", "replace")
    names = [n for n in listed.stdout.decode("utf-8").split("\0") if n]
    assert names, f"git tracks nothing under {src}"
    for name in names:
        target = dst / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / name, target)


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text(
        (_ROOT / "frontend" / "index.html").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return static


@dataclass
class _Serve:
    port: int
    token: str
    log: Path  #: the guard's refusals, one a line
    lines: queue.Queue[str | None]  #: the serve's output still to come
    seen: list[str]  #: the serve's output read so far

    def wait_for(self, text: str, budget: float) -> bool:
        """Read the serve's output until a line holds ``text`` (True) or ``budget`` runs out."""
        deadline = time.monotonic() + budget
        while (left := deadline - time.monotonic()) > 0:
            try:
                line = self.lines.get(timeout=left)
            except queue.Empty:
                return False
            if line is None:
                return False  # the serve exited
            self.seen.append(line)
            if text in line:
                return True
        return False


@pytest.fixture
def offline_serve(tmp_path: Path, static_dir: Path) -> Iterator[_Serve]:
    """Start the app's serve with the network off, and hand it over once it is listening."""
    project = tmp_path / "proj"
    _copy_tracked(_FIXTURE, project)
    home = tmp_path / "home"
    home.mkdir()
    log = tmp_path / "refused.log"
    log.touch()
    started = time.monotonic()
    proc = subprocess.Popen(
        [
            sys.executable, "-c", _RUN_GUARD, str(log), str(static_dir),
            "serve", "--no-open", "--port", "0", str(project),
        ],
        cwd=str(tmp_path),
        env=_child_env(home),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    lines: queue.Queue[str | None] = queue.Queue()

    def pump() -> None:
        # A thread, so a child that hangs before printing anything is a timeout here,
        # not a blocked readline: the hang is the thing this test exists to catch.
        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                lines.put(line)
        finally:
            lines.put(None)

    threading.Thread(target=pump, daemon=True).start()
    seen: list[str] = []
    port = None
    token = ""
    try:
        while port is None:
            left = _APP_BUDGET_S - (time.monotonic() - started)
            if left <= 0:
                break
            try:
                line = lines.get(timeout=left)
            except queue.Empty:
                break
            if line is None:
                break  # the child exited without a Report line
            seen.append(line)
            if line.startswith(_TOKEN_LINE):
                token = line[len(_TOKEN_LINE):].strip()
            m = _REPORT_LINE.search(line)
            if m:
                port = int(m.group(1))
        elapsed = time.monotonic() - started
        assert port is not None, "serve never printed its Report line:\n" + "".join(seen)
        assert elapsed < _APP_BUDGET_S, f"serve took {elapsed:.1f}s to come up offline"
        assert token, "serve printed no auth token:\n" + "".join(seen)
        yield _Serve(port, token, log, lines, seen)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def _get(port: int, path: str, token: str = "") -> tuple[int, str]:
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=10) as resp:
        return resp.status, resp.read().decode("utf-8")


def _signals_lens_ready(serve: _Serve) -> bool:
    _status, body = _get(serve.port, "/api/projects/1/condition", serve.token)
    return bool(json.loads(body)["lenses"]["signals"])


def test_the_guard_refuses_an_outbound_fetch_and_logs_it(tmp_path: Path) -> None:
    """The canary: without it, a guard that let everything through would pass the serve test."""
    log = tmp_path / "refused.log"
    started = time.monotonic()
    out = subprocess.run(
        [sys.executable, "-c", _RUN_GUARD, str(log), str(tmp_path), "probe",
         "https://api.anthropic.com/"],
        env=_child_env(tmp_path), capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert out.stdout.strip() == "refused: URLError", out.stdout + out.stderr
    assert time.monotonic() - started < 15
    assert "getaddrinfo 'api.anthropic.com'" in log.read_text(encoding="utf-8")


#: The startup repair gives up within this offline: about 21 s of SDK retries on a Mac.
_REPAIR_BUDGET_S = 90.0


def test_serve_comes_up_offline_and_only_the_signals_repair_tries_the_network(
    offline_serve: _Serve,
) -> None:
    serve = offline_serve
    port = serve.port

    status, html = _get(port, "/report/")
    assert status == 200
    # End to end through the real CLI and HTTP: the env the app sets reaches the served
    # head. The head's own rule is pinned by
    # test_server_status_page.py::test_desktop_head_waits_for_no_webfont.
    # The desktop's first paint owes the network nothing: Inter's render-blocking link is
    # left out (a degraded route held it 71.7 s, 14 Sep 2026), so with Wi-Fi off there is
    # no Google Fonts request to fail at all.
    assert "fonts.googleapis.com" not in html
    assert 'href="https://' not in html.split("</head>")[0]

    status, _body = _get(port, "/api/health")
    assert status == 200

    # The study owes a Signals snapshot, so the startup repair asks Claude for one in the
    # background, and the Signals lens is withheld while it does.
    assert not _signals_lens_ready(serve), "Signals was not withheld while its report is owed"

    # Wait for the repair to give up, not only for its first refused lookup: the SDK
    # retries for about 21 s, and the failure path (the fallback, then clearing the
    # pending flag) only runs after that.
    started = time.monotonic()
    gave_up = serve.wait_for("Signal snapshot materialisation skipped", _REPAIR_BUDGET_S)
    output = "".join(serve.seen)
    assert gave_up, (
        f"the startup repair had not given up after {time.monotonic() - started:.0f}s:\n"
        + output
    )
    # The provider calls were the repair's own, not some other launch-time call.
    assert "schema=SignalElaborationResult" in output, output

    # Every attempt out, over the whole repair, was to the provider.
    refused = serve.log.read_text(encoding="utf-8").splitlines()
    assert refused, "the guard saw no attempt: did the repair reach the network another way?"
    assert all("api.anthropic.com" in line for line in refused), (
        "the launch tried something besides the provider:\n" + "\n".join(refused)
    )

    # The refused calls took nothing down, and left nothing stuck: the serve answers,
    # and Signals is no longer withheld waiting for a report that will not come.
    assert _signals_lens_ready(serve), "Signals stayed withheld after the repair gave up"
    status, _body = _get(port, "/api/health")
    assert status == 200
    status, _html = _get(port, "/report/")
    assert status == 200


# --- The first Analyse: the run's preflight, in-process, with the network off --------------


@pytest.fixture
def offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_home: Path) -> Path:
    for name in offline_guard.strip_proxies(os.environ):
        monkeypatch.delenv(name)
    log = tmp_path / "refused.log"
    log.touch()
    offline_guard.install(log, monkeypatch.setattr)
    return log


def test_the_guard_refuses_the_other_routes_out_and_allows_loopback(offline: Path) -> None:
    """The resolvers and the connectionless send are refused too; loopback still works."""
    import socket

    with pytest.raises(socket.gaierror):
        socket.gethostbyname("example.com")
    with pytest.raises(socket.gaierror):
        socket.gethostbyname_ex("example.com")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp, pytest.raises(OSError):
        udp.sendto(b"x", ("192.0.2.1", 9))
    if hasattr(socket.socket, "sendmsg"):  # POSIX; Windows has none to guard
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp, pytest.raises(OSError):
            udp.sendmsg([b"x"], [], 0, ("192.0.2.1", 9))
        assert "sendmsg ('192.0.2.1', 9)" in offline.read_text(encoding="utf-8")
    assert socket.gethostbyname("localhost").startswith("127.")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        assert udp.sendto(b"x", ("127.0.0.1", 9)) == 1
    log = offline.read_text(encoding="utf-8")
    assert "gethostbyname 'example.com'" in log
    assert "gethostbyname_ex 'example.com'" in log
    assert "sendto ('192.0.2.1', 9)" in log
    assert "127.0.0.1" not in log and "localhost" not in log


def _settings(provider: str) -> BristlenoseSettings:
    return BristlenoseSettings(
        llm_provider=provider,
        anthropic_api_key="sk-ant-offline-test-0000000000",
        openai_api_key="sk-offline-test-0000000000",
        google_api_key="AIza-offline-test-0000000000",
    )


#: Each check answers inside this with the network off (SDK retry backoff included).
_CHECK_BUDGET_S = 15.0


@pytest.mark.parametrize(
    ("provider", "host"),
    [
        ("anthropic", "api.anthropic.com"),
        ("openai", "api.openai.com"),
        ("google", "generativelanguage.googleapis.com"),
    ],
)
def test_the_network_check_says_cant_reach_in_seconds(
    offline: Path, provider: str, host: str
) -> None:
    from bristlenose.doctor import CheckStatus, check_network

    started = time.monotonic()
    result = check_network(_settings(provider))
    elapsed = time.monotonic() - started

    assert result.status is CheckStatus.FAIL
    assert result.detail == f"Can't reach {host}"
    assert result.fix_key == "network_unreachable"
    assert elapsed < _CHECK_BUDGET_S
    assert host in offline.read_text(encoding="utf-8"), "the check never asked the network"


_HOSTS = {
    "anthropic": "api.anthropic.com",
    "openai": "api.openai.com",
    "google": "generativelanguage.googleapis.com",
}


@pytest.mark.parametrize("provider", ["anthropic", "openai", "google"])
def test_the_key_check_keeps_the_key_and_says_it_could_not_validate(
    offline: Path, provider: str
) -> None:
    """Offline is not a rejected key: the doctor's key row stays OK, with the reason."""
    from bristlenose.doctor import CheckStatus, check_api_key

    started = time.monotonic()
    result = check_api_key(_settings(provider))
    elapsed = time.monotonic() - started

    assert result.status is CheckStatus.OK, result.detail
    assert "could not validate" in result.detail
    assert elapsed < _CHECK_BUDGET_S
    assert _HOSTS[provider] in offline.read_text(encoding="utf-8"), "never asked the network"


@pytest.mark.parametrize("provider", ["anthropic", "openai", "google"])
def test_the_runs_key_preflight_classifies_offline_as_network(
    offline: Path, provider: str
) -> None:
    """The run's own request (preflight/api_key.py) fails as ``network``, in seconds.

    ``network`` is the class whose copy says to check the connection; the other classes
    say the key, the billing or the model is wrong, which offline is not.
    """
    from bristlenose.llm.client import request_params
    from bristlenose.preflight import api_key

    settings = _settings(provider)
    key = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "google": settings.google_api_key,
    }[provider]
    params = request_params(
        provider, settings.llm_model, settings.llm_max_tokens, settings.llm_temperature
    )
    validator = getattr(api_key, f"_validate_{provider}")

    started = time.monotonic()
    result = validator(key, settings.llm_model, params=params)
    elapsed = time.monotonic() - started

    assert result.ok is False
    assert result.error_class == "network", (result.error_class, result.raw_message)
    assert elapsed < _CHECK_BUDGET_S, f"{provider} took {elapsed:.1f}s to fail offline"
    assert _HOSTS[provider] in offline.read_text(encoding="utf-8"), "never asked the network"


def test_the_runs_key_preflight_stops_with_the_connection_copy(
    offline: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The caller, not only the helper: offline ends the run with "Couldn't reach ...".

    That copy carries "DNS", which the Mac app's failure classifier reads as a network
    failure (``PipelineRunner.categoriseFailure``), so the row says to check the connection.
    """
    from rich.console import Console

    from bristlenose.preflight.api_key import ApiKeyPreflightAbortedError, preflight_api_key

    monkeypatch.delenv("BRISTLENOSE_SKIP_PREFLIGHT", raising=False)  # conftest sets it
    started = time.monotonic()
    with pytest.raises(ApiKeyPreflightAbortedError) as caught:
        preflight_api_key(settings=_settings("anthropic"), console=Console(file=io.StringIO()))
    elapsed = time.monotonic() - started

    message = str(caught.value)
    assert message.startswith("Couldn't reach the provider"), message
    assert "DNS" in message
    assert elapsed < _CHECK_BUDGET_S
    assert "api.anthropic.com" in offline.read_text(encoding="utf-8")
