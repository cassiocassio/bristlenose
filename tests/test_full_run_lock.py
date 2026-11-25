"""The full-run lock: full runs queue, targeted runs don't, nothing blocks forever.

The lock (tests/full_run_lock.py) is what turns "one pytest at a time" from an
instruction into a mechanism. These tests pin the four promises it makes, and
pin the caller, because a lock nobody takes is a gate that cannot fail.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests import full_run_lock as lock

TESTS_DIR = Path(__file__).resolve().parent
needs_flock = pytest.mark.skipif(sys.platform == "win32", reason="no fcntl.flock on Windows")
HOLD = """
import sys, time
sys.path.insert(0, {root!r})
from tests import full_run_lock as lock
from pathlib import Path
held = lock.acquire(Path({path!r}), limit_s=5, poll_s=0.05, describe="holder")
print("held", flush=True)
time.sleep({seconds})
lock.release(held)
"""


def _hold_in_another_process(path: Path, seconds: float) -> subprocess.Popen[str]:
    code = HOLD.format(root=str(TESTS_DIR.parent), path=str(path), seconds=seconds)
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8")
    assert proc.stdout is not None
    line = proc.stdout.readline().strip()
    if line != "held":
        proc.kill()
        _, err = proc.communicate(timeout=10)
        pytest.fail(f"the holder process never took the lock: {err}")
    return proc


@pytest.mark.parametrize(
    ("args", "kwargs", "full"),
    [
        ([], {}, True),
        (["tests"], {}, True),
        (["tests/"], {}, True),
        (["tests/test_default_port.py"], {}, False),
        (["tests/test_default_port.py::test_x"], {}, False),
        (["tests"], {"keyword": "port"}, False),
        (["tests"], {"last_failed": True}, False),
        (["tests"], {"collect_only": True}, False),
        (["tests"], {"markexpr": "slow"}, False),
        (["."], {}, True),
        (["bristlenose"], {}, False),
    ],
)
def test_only_a_whole_suite_run_counts_as_full(
    args: list[str], kwargs: dict[str, object], full: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(TESTS_DIR.parent)
    assert lock.is_full_run(args, TESTS_DIR, **kwargs) is full  # type: ignore[arg-type]


@needs_flock
def test_a_second_full_run_waits_for_the_first(tmp_path: Path) -> None:
    path = tmp_path / "pytest.lock"
    holder = _hold_in_another_process(path, seconds=1.5)
    started = time.monotonic()
    held = lock.acquire(path, limit_s=30, poll_s=0.05)
    waited = time.monotonic() - started
    lock.release(held)
    holder.communicate(timeout=10)
    assert held.fail_open == ""
    assert waited >= 1.0, f"the second run did not wait (waited {waited:.2f} s)"


@needs_flock
def test_a_stuck_holder_fails_open_and_names_itself(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "pytest.lock"
    holder = _hold_in_another_process(path, seconds=10)
    try:
        started = time.monotonic()
        held = lock.acquire(path, limit_s=0.5, poll_s=0.05)
        elapsed = time.monotonic() - started
    finally:
        holder.kill()
        holder.communicate(timeout=10)
    assert held.handle is None
    assert "still held" in held.fail_open
    assert f"pid {holder.pid}" in held.fail_open
    assert elapsed < 5
    assert "running anyway" in capsys.readouterr().err


def test_an_unwritable_cache_fails_open(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("", encoding="utf-8")
    held = lock.acquire(blocker / "pytest.lock", limit_s=1)
    assert held.handle is None
    assert held.fail_open


@pytest.mark.parametrize("flag", ["help", "markers", "showfixtures", "cacheshow", "stepwise"])
def test_help_and_inspection_runs_never_wait(
    flag: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []
    monkeypatch.setattr(lock, "acquire", lambda path, **_: calls.append(path) or lock.Held(True))
    monkeypatch.setattr(lock, "cache_dir", lambda: tmp_path)
    monkeypatch.delenv("CI", raising=False)

    class Opt:
        keyword, lf, collectonly, markexpr, numprocesses = "", False, False, "not slow", None

    opt = Opt()
    setattr(opt, flag, True)

    class Config:
        option, args, rootpath = opt, [], TESTS_DIR.parent

    config = Config()
    lock.configure(config)
    lock.unconfigure(config)
    assert calls == []


def test_every_run_leaves_one_log_line(tmp_path: Path) -> None:
    log = tmp_path / "runs.log"
    lock.log_run(log, lock.Held(full=True, waited_s=3.2), args=["tests/", "-n", "auto"], workers=12)
    lock.log_run(log, lock.Held(full=False), args=["tests/test_x.py"], workers=None)
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [r["full"] for r in rows] == [True, False]
    assert rows[0]["workers"] == 12
    assert rows[0]["waited_s"] == 3.2
    assert {"start", "wall_s", "fail_open", "pid", "args"} <= rows[0].keys()


def test_ci_and_xdist_workers_never_take_the_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []
    monkeypatch.setattr(lock, "acquire", lambda path, **_: calls.append(path) or lock.Held(True))
    monkeypatch.setattr(lock, "cache_dir", lambda: tmp_path)

    class Opt:
        keyword, lf, collectonly, markexpr, numprocesses = "", False, False, "not slow", None

    class Config:
        option, args, rootpath = Opt(), [], TESTS_DIR.parent

    monkeypatch.setenv("CI", "1")
    lock.configure(Config())
    monkeypatch.delenv("CI")
    worker = Config()
    worker.workerinput = {}  # type: ignore[attr-defined]
    lock.configure(worker)
    assert calls == []
    controller = Config()
    lock.configure(controller)
    lock.unconfigure(controller)
    assert calls == [tmp_path / "pytest.lock"]


def test_conftest_takes_and_releases_the_lock() -> None:
    """Pin the caller: the helper is useless if conftest stops calling it."""
    tree = ast.parse((TESTS_DIR / "conftest.py").read_text(encoding="utf-8"))
    hooks = {
        node.name: ast.unparse(node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("pytest_")
    }
    assert "_full_run_lock.configure(config)" in hooks.get("pytest_configure", "")
    assert "_full_run_lock.unconfigure(config)" in hooks.get("pytest_unconfigure", "")
