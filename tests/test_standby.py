"""``serve --standby``: a sidecar that boots now and learns its study from one stdin line.

The Mac app starts one shortly after launch (docs/design-standby-sidecar.md). These run the real
command in a subprocess, because what matters is the process-level behaviour: nothing bound or
written before a claim, a claim that carries on exactly like ``serve <path>``, and a waiting
process that can always be stopped.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from bristlenose.output_paths import project_output_dir
from bristlenose.run_lifecycle import pid_file_path
from bristlenose.standby import CLAIM_VERSION, READY_LINE, parse_claim

FIXTURE = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
TOKEN = "claim-token-9f3c1a7e2b"


def _env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("_BRISTLENOSE_")}
    env["BRISTLENOSE_LLM_PROVIDER"] = "local"  # a serve here must never be able to spend money
    return env


def _restore_sigint() -> None:
    # A test run started as a background job inherits SIGINT ignored, which a child inherits too.
    signal.signal(signal.SIGINT, signal.default_int_handler)


def _child_kwargs() -> dict[str, Any]:
    """How the standby is started so that a stop signal reaches it, and only it.

    POSIX: SIGINT restored in the child (``preexec_fn`` is POSIX-only; Windows raises on it).
    Windows: its own process group, the one condition under which a console signal can be
    sent to a child at all.
    """
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"preexec_fn": _restore_sigint}


def _stop_signal(name: str) -> int:
    """The signal a host sends a waiting standby to stop it, by what it means.

    ``SIGTERM`` is ``Process.terminate()`` on both (``TerminateProcess`` on Windows). The
    interrupt is Ctrl-C on POSIX; on Windows ``send_signal(SIGINT)`` is unsupported and
    ``CTRL_C_EVENT`` cannot reach a child in its own process group, so ``CTRL_BREAK_EVENT``
    is the console interrupt a host can deliver.
    """
    if name == "SIGINT" and sys.platform == "win32":
        return signal.CTRL_BREAK_EVENT
    return int(getattr(signal, name))


def _spawn(*extra: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "bristlenose", "serve", "--standby", "--no-open", "--port", "0", *extra],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=_env(), **_child_kwargs(),
    )


class _Lines:
    """Lines from a pipe on a thread, so a test can wait for one with a bound."""

    def __init__(self, pipe) -> None:  # type: ignore[no-untyped-def]
        self.q: queue.Queue[str] = queue.Queue()
        threading.Thread(target=lambda: [self.q.put(ln.rstrip("\n")) for ln in pipe], daemon=True).start()

    def until(self, needle: str, timeout: float = 90.0) -> str:
        seen = []
        while True:
            try:
                line = self.q.get(timeout=timeout)
            except queue.Empty:
                raise AssertionError(f"no {needle!r} in {timeout}s; saw {seen}") from None
            seen.append(line)
            if needle in line:
                return line

    def none_within(self, seconds: float) -> list[str]:
        out = []
        try:
            while True:
                out.append(self.q.get(timeout=seconds))
        except queue.Empty:
            return out


@pytest.fixture
def study(tmp_path: Path) -> Path:
    dest = tmp_path / "study"
    shutil.copytree(FIXTURE, dest)  # serving imports the folder and writes its database
    return dest


def _claim(path: Path, token: str = TOKEN) -> str:
    return json.dumps({"v": CLAIM_VERSION, "project": str(path), "mcp_token": token}) + "\n"


@pytest.fixture
def standby():
    procs: list[subprocess.Popen[str]] = []

    def start() -> subprocess.Popen[str]:
        p = _spawn()
        procs.append(p)
        return p

    yield start
    for p in procs:
        if p.poll() is None:
            p.kill()
        p.wait(timeout=10)
        for pipe in (p.stdin, p.stdout, p.stderr):
            if pipe:
                pipe.close()


def test_a_waiting_standby_says_ready_and_nothing_else(standby, study: Path) -> None:
    p = standby()
    out = _Lines(p.stdout)
    assert out.until(READY_LINE) == READY_LINE
    assert out.none_within(1.5) == []  # no Report:, no auth-token, nothing
    assert p.poll() is None
    assert not (study / "bristlenose-output" / "bristlenose.db").exists()


def test_a_claim_carries_on_like_serve_with_the_path(standby, study: Path) -> None:
    p = standby()
    out = _Lines(p.stdout)
    out.until(READY_LINE)
    p.stdin.write(_claim(study))
    p.stdin.flush()
    report = out.until("Report: http://127.0.0.1:")
    port = report.split("127.0.0.1:")[1].split("/")[0]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=20) as r:
        assert r.status == 200


def test_closing_stdin_before_a_claim_ends_it_quietly(standby) -> None:
    p = standby()
    _Lines(p.stdout).until(READY_LINE)
    p.stdin.close()
    assert p.wait(timeout=20) == 0


@pytest.mark.parametrize("sig", ["SIGTERM", "SIGINT"])
def test_a_waiting_standby_can_always_be_stopped(standby, sig: str) -> None:
    # install_exit_logger swallows SIGTERM when installed before uvicorn: a standby that
    # installed it early could not be stopped by Process.terminate().
    p = standby()
    _Lines(p.stdout).until(READY_LINE)
    p.send_signal(_stop_signal(sig))
    assert p.wait(timeout=20) != 0


@pytest.mark.parametrize(
    "line",
    [
        f"not json {TOKEN}\n",
        json.dumps({"v": 2, "project": "/x", "mcp_token": TOKEN}) + "\n",
        json.dumps({"v": 1, "project": "", "mcp_token": TOKEN}) + "\n",
        json.dumps({"v": 1, "mcp_token": TOKEN}) + "\n",
        json.dumps([TOKEN]) + "\n",
    ],
)
def test_a_bad_claim_exits_2_and_never_echoes_the_token(standby, line: str) -> None:
    p = standby()
    _Lines(p.stdout).until(READY_LINE)
    p.stdin.write(line)
    p.stdin.flush()
    err = p.stderr.read()
    assert p.wait(timeout=20) == 2
    assert TOKEN not in err and "claim" in err


def test_a_path_with_standby_is_a_usage_error(study: Path) -> None:
    r = subprocess.run(
        [sys.executable, "-m", "bristlenose", "serve", "--standby", str(study)],
        capture_output=True, text=True, env=_env(), timeout=60, stdin=subprocess.DEVNULL,
    )
    assert r.returncode == 2


def test_an_unsafe_study_is_refused_after_a_claim_like_a_cold_start(standby, study: Path) -> None:
    # An orphaned run marker makes startup refuse (test_study_startup): the claim must hit the
    # same refusal, with the same exit code, as `serve <path>` does.
    marker = pid_file_path(project_output_dir(study))
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("{}", encoding="utf-8")
    cold = subprocess.run(
        [sys.executable, "-m", "bristlenose", "serve", "--no-open", "--port", "0", str(study)],
        capture_output=True, text=True, env=_env(), timeout=90, stdin=subprocess.DEVNULL,
    )
    p = standby()
    _Lines(p.stdout).until(READY_LINE)
    p.stdin.write(_claim(study))
    p.stdin.flush()
    assert cold.returncode != 0
    assert p.wait(timeout=60) == cold.returncode


def test_parse_claim_reads_the_path_and_token() -> None:
    assert parse_claim(_claim(Path("/a/b"))) == (Path("/a/b"), TOKEN)
    assert parse_claim(json.dumps({"v": 1, "project": "/a"})) == (Path("/a"), "")


def test_a_claim_hands_its_token_to_create_app_through_the_environment(monkeypatch) -> None:
    import io

    from bristlenose.standby import await_claim

    monkeypatch.delenv("_BRISTLENOSE_MCP_TOKEN", raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO(_claim(Path("/a/b"))))
    assert await_claim() == Path("/a/b")
    assert os.environ["_BRISTLENOSE_MCP_TOKEN"] == TOKEN  # app.py reads this inside create_app


def test_a_claim_without_a_token_leaves_the_environment_alone(monkeypatch) -> None:
    import io

    from bristlenose.standby import await_claim

    monkeypatch.setenv("_BRISTLENOSE_MCP_TOKEN", "from-the-host")
    monkeypatch.setattr(sys, "stdin", io.StringIO(_claim(Path("/a/b"), token="")))
    await_claim()
    assert os.environ["_BRISTLENOSE_MCP_TOKEN"] == "from-the-host"
