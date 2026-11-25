"""One full local test run at a time, and a log line for every run.

WHY

Several agent sessions share this Mac, and each used to start the whole suite
before every commit. Two at once doubled the memory (one parallel run peaks
near 9 GB), collided on the fixed ports in `test_cli_output.py`, and produced
failures that vanished on a rerun. The house rule "one pytest at a time" was an
instruction; this makes it a mechanism.

WHAT IT DOES

- A FULL run (the whole `tests/` tree under the default marker, no `-k`,
  `--lf`, `--collect-only`) takes an exclusive `flock` on
  `~/.cache/bristlenose/pytest.lock`, shared across worktrees. A second full
  run waits, printing who holds it.
- It FAILS OPEN: after `WAIT_LIMIT_S` (longer than a serial run, so it only
  ever fires on a hung holder), or when the lock file can't be opened, the run
  goes ahead with a warning. On Windows there is no `fcntl`, so no lock, quietly.
  A hung holder must never block everyone.
- A targeted run (a file, a node id, `-k`, `--lf`, `--sw`) never waits, and
  nor do `--help`, `--markers`, `--fixtures` or `--cache-show`.
- Every run, full or not, appends one JSON line to
  `~/.cache/bristlenose/pytest-runs.log`. That log is how the test-speed plan
  measures runs per session and how often `-n` is used.
- Skipped entirely when `CI` is set, and on xdist workers (the controller
  holds the lock for its workers).
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

WAIT_LIMIT_S = 1800.0  # serial full run measured 1454 s on 25 Nov 2026
POLL_S = 2.0
DEFAULT_MARKEXPR = "not slow"


def cache_dir() -> Path:
    return Path.home() / ".cache" / "bristlenose"


def is_full_run(
    args: list[str],
    tests_dir: Path,
    *,
    keyword: str = "",
    last_failed: bool = False,
    collect_only: bool = False,
    markexpr: str = DEFAULT_MARKEXPR,
) -> bool:
    """True when the run selects the whole suite as the gate does."""
    if keyword or last_failed or collect_only or markexpr != DEFAULT_MARKEXPR:
        return False
    if not args:
        return True  # bare `pytest` falls back to testpaths = ["tests"]
    try:
        target = tests_dir.resolve()
        # `tests/`, or a directory above it (`pytest .` from the root)
        return all(Path(a).resolve() in (target, *target.parents) for a in args)
    except OSError:
        return False


@dataclass
class Held:
    """What a run holds and will log when it ends."""

    full: bool
    started: float = field(default_factory=time.time)
    waited_s: float = 0.0
    fail_open: str = ""
    handle: IO[str] | None = None


def acquire(lock_path: Path, *, limit_s: float = WAIT_LIMIT_S, poll_s: float = POLL_S,
            describe: str = "") -> Held:
    """Take the lock, waiting at most `limit_s`; never raise."""
    held = Held(full=True)
    try:
        import fcntl
    except ImportError:
        held.fail_open = "no fcntl on this platform"
        return held
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(lock_path, "a+", encoding="utf-8")  # noqa: SIM115 - held for the run
    except OSError as exc:
        held.fail_open = f"cannot open {lock_path}: {exc}"
        _say(f"full-run lock: {held.fail_open}; running unlocked")
        return held
    start = time.monotonic()
    told = False
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError:
            waited = time.monotonic() - start
            if waited >= limit_s:
                held.fail_open = f"still held after {limit_s:.0f} s by {_holder(lock_path)}"
                held.waited_s = waited
                handle.close()
                _say(f"full-run lock: {held.fail_open}; running anyway")
                return held
            if not told:
                _say(f"full-run lock: waiting for another full test run ({_holder(lock_path)}). "
                     f"This run starts by itself when that one ends; do not start another. "
                     f"Giving up after {limit_s:.0f} s")
                told = True
            time.sleep(poll_s)
    held.waited_s = time.monotonic() - start
    handle.seek(0)
    handle.truncate()
    handle.write(json.dumps({"pid": os.getpid(), "since": time.strftime("%H:%M:%S"),
                             "run": describe}))
    handle.flush()
    held.handle = handle
    return held


def release(held: Held) -> None:
    if held.handle is not None:
        held.handle.close()  # closing the descriptor drops the flock
        held.handle = None


def log_run(log_path: Path, held: Held, *, args: list[str], workers: Any) -> None:
    line = {
        "start": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(held.started)),
        "wall_s": round(time.time() - held.started, 1),
        "full": held.full,
        "workers": workers,
        "waited_s": round(held.waited_s, 1),
        "fail_open": held.fail_open,
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "cwd": os.getcwd(),
        "args": args,
    }
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line) + "\n")
    except OSError:
        pass  # a log we cannot write must not fail a test run


def _holder(lock_path: Path) -> str:
    try:
        text = lock_path.read_text(encoding="utf-8").strip()
        info = json.loads(text) if text else {}
    except (OSError, ValueError):
        info = {}
    if not info:
        return "an unknown process"
    return f"pid {info.get('pid')} since {info.get('since')}: {info.get('run', '')}".strip()


def _say(message: str) -> None:
    sys.stderr.write(message + "\n")
    sys.stderr.flush()


# ---- the two pytest hooks conftest delegates to ----

_STASH: dict[int, Held] = {}


def configure(config: Any) -> None:
    if os.environ.get("CI") or hasattr(config, "workerinput"):
        return
    opt = config.option
    args = [str(a) for a in config.args]
    informational = any(getattr(opt, name, False) for name in (
        "help", "markers", "showfixtures", "show_fixtures_per_test", "cacheshow"))
    full = not informational and is_full_run(
        args,
        Path(str(config.rootpath)) / "tests",
        keyword=getattr(opt, "keyword", "") or "",
        last_failed=bool(getattr(opt, "lf", False) or getattr(opt, "stepwise", False)),
        collect_only=bool(getattr(opt, "collectonly", False)),
        markexpr=getattr(opt, "markexpr", DEFAULT_MARKEXPR) or "",
    )
    held = (acquire(cache_dir() / "pytest.lock", describe=" ".join(sys.argv[1:]))
            if full else Held(full=False))
    _STASH[id(config)] = held


def unconfigure(config: Any) -> None:
    held = _STASH.pop(id(config), None)
    if held is None:
        return
    log_run(cache_dir() / "pytest-runs.log", held,
            args=sys.argv[1:], workers=getattr(config.option, "numprocesses", None))
    release(held)
