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
- The run that holds the lock writes its progress to
  `~/.cache/bristlenose/pytest-live.txt`, so there is one place to watch a
  full run whoever started it (`tail -f` it): a header, a progress line every
  `LIVE_EVERY_S`, each failure as it happens, and a `finished` line. The file
  is overwritten by the next full run.
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
LIVE_EVERY_S = 5.0
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


OUTCOMES = ("passed", "failed", "error", "skipped", "xfailed")


@dataclass
class Live:
    """The progress file of the run holding the lock."""

    handle: IO[str]
    started: float = field(default_factory=time.time)
    total: int | None = None
    done: int = 0
    counts: dict[str, int] = field(default_factory=lambda: dict.fromkeys(OUTCOMES, 0))
    last_write: float = 0.0


_LIVE: Live | None = None


def live_start(path: Path, *, describe: str) -> Live | None:
    """Start a fresh progress file; a file we cannot write is no reason to fail a run."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(path, "w", encoding="utf-8")  # noqa: SIM115 - held for the run
    except OSError:
        return None
    live = Live(handle=handle)
    _live_write(live, f"full test run · pid {os.getpid()} · started "
                      f"{time.strftime('%H:%M:%S', time.localtime(live.started))} · {os.getcwd()}\n"
                      f"args: {describe}\n")
    return live


def _outcome(report: Any) -> str | None:
    """One outcome per test: the call phase, or setup when setup didn't pass."""
    xfail = hasattr(report, "wasxfail")
    if report.when == "call":
        if xfail:
            return "xfailed" if report.skipped else "passed"
        return str(report.outcome)
    if report.when == "setup" and not report.passed:
        if report.skipped:
            return "xfailed" if xfail else "skipped"
        return "error"
    if report.when == "teardown" and report.failed:
        return "error"
    return None


def live_record(live: Live, report: Any) -> None:
    outcome = _outcome(report)
    if outcome is None:
        return
    live.counts[outcome] = live.counts.get(outcome, 0) + 1
    if report.when != "teardown":  # a teardown error is a second report for a test already done
        live.done += 1
    if outcome in ("failed", "error"):
        _live_write(live, f"{outcome.upper()} {report.nodeid}\n")
    if time.time() - live.last_write >= LIVE_EVERY_S:
        _live_progress(live)


def live_collected(live: Live, n: int) -> None:
    if n and live.total is None:
        live.total = n
        _live_progress(live)


def live_finish(live: Live) -> None:
    _live_progress(live, prefix="finished")
    try:
        live.handle.close()
    except OSError:
        pass


def _live_progress(live: Live, prefix: str = " ") -> None:
    total = f"{live.total:,}" if live.total else "?"
    counts = "  ".join(f"{k} {v:,}" for k, v in live.counts.items())
    _live_write(live, f"{prefix} {live.done:,}/{total}  {counts}  · "
                      f"{time.time() - live.started:.0f} s\n")


def _live_write(live: Live, text: str) -> None:
    try:
        live.handle.write(text)
        live.handle.flush()
    except (OSError, ValueError):
        pass  # a progress file we cannot write must not fail a test run
    live.last_write = time.time()


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
    describe = " ".join(sys.argv[1:])
    held = acquire(cache_dir() / "pytest.lock", describe=describe) if full else Held(full=False)
    _STASH[id(config)] = held
    global _LIVE
    if held.handle is not None:  # only the lock's owner writes the live file
        _LIVE = live_start(cache_dir() / "pytest-live.txt", describe=describe)


def unconfigure(config: Any) -> None:
    global _LIVE
    held = _STASH.pop(id(config), None)
    if held is None:
        return
    if _LIVE is not None and held.handle is not None:
        live_finish(_LIVE)
        _LIVE = None
    log_run(cache_dir() / "pytest-runs.log", held,
            args=sys.argv[1:], workers=getattr(config.option, "numprocesses", None))
    release(held)


def record(report: Any) -> None:
    if _LIVE is not None:
        live_record(_LIVE, report)


def collected(n: int) -> None:
    if _LIVE is not None:
        live_collected(_LIVE, n)
