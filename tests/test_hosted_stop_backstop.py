"""A hosted run that cannot unwind is ended by a backstop, with one terminus (R19).

Once a hosted run is stopping, further signals are ignored (R19), so a quit
whose unwind blocks, for instance a thread pool joining a stalled first-run
Whisper download, waited out huggingface_hub's own timeouts. The first hosted
signal now arms a timer: if the process is still alive at the deadline it
writes run_cancelled (unless a terminus is already written) and exits. A lock
around every terminus write means the timer and the normal path never both
write one.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

import pytest

from bristlenose.events import (
    RunCancelledEvent,
    RunCompletedEvent,
    RunFailedEvent,
    events_path,
    read_events,
)
from tests.test_run_lifecycle import (
    _spawn_lifecycle_subprocess,
    _wait_for_ready,
    _wait_for_run_started,
)

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")

HOSTED = {"_BRISTLENOSE_HOSTED_BY_DESKTOP": "1"}
GRACE = "import bristlenose.run_lifecycle as _r\n_r._HOSTED_STOP_GRACE_S = {grace}"


def _termini(f: Path) -> list[object]:
    return [
        e for e in read_events(f)
        if isinstance(e, (RunCancelledEvent, RunCompletedEvent, RunFailedEvent))
    ]


def _stuck_body(sentinel: Path) -> str:
    """Pause, then never finish unwinding, as a pool joining a stalled download."""
    return f"""
        import signal, threading
        Path({str(sentinel)!r}).write_text("ready")
        try:
            signal.pause()
        finally:
            threading.Event().wait()
    """


def _exit_held_elsewhere() -> bool:
    """Whether another thread holds the exit hold (it is re-entrant, so ask from
    a thread of our own, and release there what we take)."""
    import threading

    import bristlenose.run_lifecycle as rl

    free: list[bool] = []

    def _probe() -> None:
        ok = rl._exit_hold.acquire(blocking=False)
        if ok:
            rl._exit_hold.release()
        free.append(ok)

    t = threading.Thread(target=_probe)
    t.start()
    t.join()
    return not free[0]


def _wait_exit(proc, timeout: float) -> int | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return proc.returncode
        time.sleep(0.05)
    return None


def test_a_stuck_hosted_stop_is_ended_and_recorded_cancelled(tmp_path: Path) -> None:
    sentinel = tmp_path / "ready"
    proc = _spawn_lifecycle_subprocess(
        tmp_path, _stuck_body(sentinel), preamble=GRACE.format(grace=1.0), env=HOSTED,
    )
    f = events_path(tmp_path)
    try:
        _wait_for_run_started(f)
        _wait_for_ready(sentinel)
        from bristlenose.run_lifecycle import pid_file_path

        assert pid_file_path(tmp_path).exists(), "precondition: the run wrote its run.pid"
        proc.send_signal(signal.SIGINT)
        code = _wait_exit(proc, 30.0)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    assert code == 128 + signal.SIGINT, code
    (terminus,) = _termini(f)
    assert isinstance(terminus, RunCancelledEvent)
    assert terminus.cause.signal_name == "SIGINT"
    from bristlenose.run_lifecycle import pid_file_path

    # Stuck short of the normal path's removal: the backstop removes its own.
    assert not pid_file_path(tmp_path).exists(), "the backstop left its own run.pid"


def test_a_stop_that_wrote_its_terminus_and_then_hung_writes_no_second(tmp_path: Path) -> None:
    """The normal path writes run_cancelled; the exit then hangs (an atexit join);
    the timer ends the process and finds the terminus already there."""
    sentinel = tmp_path / "ready"
    preamble = GRACE.format(grace=1.0) + (
        "\nimport atexit, threading\natexit.register(lambda: threading.Event().wait())"
    )
    body = f"""
        import signal
        Path({str(sentinel)!r}).write_text("ready")
        signal.pause()
    """
    proc = _spawn_lifecycle_subprocess(tmp_path, body, preamble=preamble, env=HOSTED)
    f = events_path(tmp_path)
    try:
        _wait_for_run_started(f)
        _wait_for_ready(sentinel)
        proc.send_signal(signal.SIGINT)
        code = _wait_exit(proc, 30.0)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    assert code == 128 + signal.SIGINT, code
    (terminus,) = _termini(f)
    assert isinstance(terminus, RunCancelledEvent)


def test_a_backstop_leaves_a_newer_runs_pid_file(tmp_path: Path) -> None:
    """The normal path writes its terminus and removes run.pid, then the exit hangs.
    A new run (a CLI run, say) writes its own run.pid in that window; the stopped
    run's backstop must not delete it (decision #51)."""
    import json

    from bristlenose.run_lifecycle import pid_file_path

    sentinel = tmp_path / "ready"
    preamble = GRACE.format(grace=3.0) + (
        "\nimport atexit, threading\natexit.register(lambda: threading.Event().wait())"
    )
    body = f"""
        import signal
        Path({str(sentinel)!r}).write_text("ready")
        signal.pause()
    """
    proc = _spawn_lifecycle_subprocess(tmp_path, body, preamble=preamble, env=HOSTED)
    f = events_path(tmp_path)
    pid_file = pid_file_path(tmp_path)
    newer = {"pid": os.getpid(), "start_time": "0.0", "run_id": "a-newer-run"}
    try:
        _wait_for_run_started(f)
        _wait_for_ready(sentinel)
        assert pid_file.exists()
        proc.send_signal(signal.SIGINT)
        deadline = time.time() + 2.5
        while (pid_file.exists() or not _termini(f)) and time.time() < deadline:
            time.sleep(0.01)
        assert not pid_file.exists() and _termini(f), "the stop never unwound"
        assert proc.poll() is None, "the run exited before its backstop could fire"
        pid_file.write_text(json.dumps(newer))
        code = _wait_exit(proc, 30.0)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    assert code == 128 + signal.SIGINT, f"ended by {code}, not the backstop"
    assert pid_file.exists(), "the backstop deleted a newer run's run.pid"
    assert json.loads(pid_file.read_text())["run_id"] == "a-newer-run"


def test_a_cli_run_is_not_cut_short(tmp_path: Path) -> None:
    """The CLI keeps a second Ctrl-C as the user's force; no timer decides for them."""
    sentinel = tmp_path / "ready"
    proc = _spawn_lifecycle_subprocess(
        tmp_path, _stuck_body(sentinel), preamble=GRACE.format(grace=0.5),
        env={"_BRISTLENOSE_HOSTED_BY_DESKTOP": ""},
    )
    f = events_path(tmp_path)
    try:
        _wait_for_run_started(f)
        _wait_for_ready(sentinel)
        proc.send_signal(signal.SIGINT)
        assert _wait_exit(proc, 3.0) is None, "a CLI run was ended by the hosted backstop"
    finally:
        proc.kill()
        proc.wait(timeout=10)


def test_a_finished_run_leaves_nothing_to_arm(tmp_path: Path) -> None:
    """A hosted signal outside a live run must never arm a timer that ends the process."""
    import bristlenose.run_lifecycle as rl
    from bristlenose.events import KindEnum

    with rl.run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
        assert rl._hosted_backstop is not None
    assert rl._hosted_backstop is None


def test_a_backstop_that_cannot_write_still_exits_and_says_why(
    monkeypatch, caplog: pytest.LogCaptureFixture,
) -> None:
    import logging
    import threading

    import bristlenose.run_lifecycle as rl

    exited = threading.Event()
    codes: list[int] = []

    def _fake_exit(code: int) -> None:
        codes.append(code)
        exited.set()

    def _broken(_signum: int) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(rl, "_HOSTED_STOP_GRACE_S", 0.01)
    monkeypatch.setattr(rl, "_hosted_backstop", _broken)
    monkeypatch.setattr(rl.os, "_exit", _fake_exit)
    with caplog.at_level(logging.ERROR, logger="bristlenose"):
        rl._arm_hosted_backstop(signal.SIGINT)
        assert exited.wait(5)
    assert codes == [128 + signal.SIGINT]
    assert any("backstop" in r.getMessage() for r in caplog.records)


def test_a_writer_stuck_holding_the_lock_does_not_hold_the_exit(tmp_path: Path) -> None:
    """The main thread stuck inside a terminus write (a stalled disk) holds the
    lock; the backstop gives up on writing and still ends the process."""
    sentinel = tmp_path / "ready"
    preamble = GRACE.format(grace=0.5) + (
        "\n_r._BACKSTOP_LOCK_TIMEOUT_S = 0.5\n_r._terminus_lock.acquire()"
    )
    proc = _spawn_lifecycle_subprocess(
        tmp_path, _stuck_body(sentinel), preamble=preamble, env=HOSTED,
    )
    f = events_path(tmp_path)
    try:
        _wait_for_run_started(f)
        _wait_for_ready(sentinel)
        proc.send_signal(signal.SIGINT)
        code = _wait_exit(proc, 30.0)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    assert code == 128 + signal.SIGINT, code


def test_the_backstop_waits_for_a_restore_under_way(tmp_path: Path) -> None:
    """Cut mid-restore, the report would sit set aside until the next run."""
    sentinel = tmp_path / "ready"
    marker = tmp_path / "restored"
    body = f"""
        import signal, time
        Path({str(sentinel)!r}).write_text("ready")
        try:
            signal.pause()
        finally:
            with _rl_mod.holding_exit():
                time.sleep(2.0)
                Path({str(marker)!r}).write_text("done")
    """
    proc = _spawn_lifecycle_subprocess(
        tmp_path, body, preamble=GRACE.format(grace=0.5), env=HOSTED,
    )
    f = events_path(tmp_path)
    try:
        _wait_for_run_started(f)
        _wait_for_ready(sentinel)
        proc.send_signal(signal.SIGINT)
        code = _wait_exit(proc, 30.0)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    assert code is not None
    assert marker.exists(), "the backstop exited in the middle of the restore"
    assert len(_termini(f)) == 1


def test_restore_holds_the_exit(tmp_path: Path, monkeypatch) -> None:
    from bristlenose.utils import output_backup

    out = tmp_path / "bristlenose-output"
    out.mkdir()
    (out / "report.html").write_text("old", encoding="utf-8")
    backup = output_backup.stash(out)
    assert backup is not None
    held: list[bool] = []
    real = output_backup._restore

    def _held_elsewhere() -> bool:
        return _exit_held_elsewhere()

    def _spy(b, o):
        held.append(_held_elsewhere())
        return real(b, o)

    monkeypatch.setattr(output_backup, "_restore", _spy)
    assert output_backup.restore(backup, out).report_is_back
    assert held == [True]
    assert not _held_elsewhere()


def test_the_cli_holds_the_exit_until_it_has_said_how_the_restore_went(
    tmp_path: Path, monkeypatch,
) -> None:
    from typer.testing import CliRunner

    from bristlenose.cli import app

    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", lambda s: None)
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None)

    async def _boom(*a, **k):
        raise RuntimeError("transcription died")

    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _boom)
    input_dir = tmp_path / "interviews"
    out = input_dir / "bristlenose-output"
    out.mkdir(parents=True)
    (out / "bristlenose-report.html").write_text("old", encoding="utf-8")

    said_while_held: list[bool] = []
    import bristlenose.cli as cli

    real_say = cli._say

    def _spy(kind, text, **kw):
        if "previous report" in text:
            said_while_held.append(_exit_held_elsewhere())
        return real_say(kind, text, **kw)

    monkeypatch.setattr(cli, "_say", _spy)
    CliRunner().invoke(app, ["run", str(input_dir), "--clean", "--yes", "--no-serve"])
    assert said_while_held == [True]


# --- The Mac app's Stop ladder against the backstop (R20 follow-up) -----------
#
# Stop sends SIGINT, then the steps of `PipelineRunner.cancelLadder`, to the run's
# process group. SIGKILL writes no terminus, so a ladder that kills before the
# backstop fires left a stop recorded as "stopped unexpectedly". These drive the
# ladder as written in the Swift source against the real lifecycle, every time
# scaled by _LADDER_SCALE so a 30 s ladder takes a few seconds.

_LADDER_SCALE = 0.15


def _scaled_backstop_preamble() -> str:
    import bristlenose.run_lifecycle as rl

    return (
        "import bristlenose.run_lifecycle as _r\n"
        f"_r._HOSTED_STOP_GRACE_S = {rl._HOSTED_STOP_GRACE_S * _LADDER_SCALE}\n"
        f"_r._BACKSTOP_LOCK_TIMEOUT_S = {rl._BACKSTOP_LOCK_TIMEOUT_S * _LADDER_SCALE}"
    )


def _press_stop(proc) -> None:
    """SIGINT, then each ladder step while the run is alive, to its group."""
    from tests.test_swift_python_contract import swift_cancel_ladder

    os.killpg(proc.pid, signal.SIGINT)
    for name, after in swift_cancel_ladder():
        time.sleep(after * _LADDER_SCALE)
        if proc.poll() is not None:
            return
        os.killpg(proc.pid, getattr(signal, name))


def _stop_with_the_ladder(tmp_path: Path, body: str) -> tuple[int, list[object]]:
    sentinel = tmp_path / "ready"
    proc = _spawn_lifecycle_subprocess(
        tmp_path, body.format(sentinel=str(sentinel)),
        preamble=_scaled_backstop_preamble(), env=HOSTED,
    )
    f = events_path(tmp_path)
    try:
        _wait_for_run_started(f)
        _wait_for_ready(sentinel)
        _press_stop(proc)
        code = _wait_exit(proc, 10.0)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    assert code is not None
    return code, _termini(f)


def test_a_stop_whose_unwind_outlasts_the_old_ladder_is_recorded_stopped(
    tmp_path: Path,
) -> None:
    """An unwind that ends inside the grace (a join on a slow C call) writes its
    own run_cancelled; the ladder must not kill it first."""
    import bristlenose.run_lifecycle as rl

    unwind = 0.75 * rl._HOSTED_STOP_GRACE_S * _LADDER_SCALE
    body = f"""
        import signal, threading
        Path({{sentinel!r}}).write_text("ready")
        try:
            signal.pause()
        finally:
            threading.Event().wait({unwind})
    """
    code, termini = _stop_with_the_ladder(tmp_path, body)
    assert code != -signal.SIGKILL, "the ladder killed a run that was unwinding"
    assert len(termini) == 1 and isinstance(termini[0], RunCancelledEvent), termini


def test_a_stop_that_never_unwinds_is_recorded_by_the_backstop_not_killed(
    tmp_path: Path,
) -> None:
    code, termini = _stop_with_the_ladder(tmp_path, """
        import signal, threading
        Path({sentinel!r}).write_text("ready")
        try:
            signal.pause()
        finally:
            threading.Event().wait()
    """)
    assert code == 128 + signal.SIGINT, f"ended by {code}, not the backstop"
    assert len(termini) == 1 and isinstance(termini[0], RunCancelledEvent), termini


# --- The backstop settles a set-aside report (#29) -----------------------------


def test_a_stuck_stop_puts_the_previous_report_back_before_it_exits(
    tmp_path: Path,
) -> None:
    """A Re-analyse whose unwind sticks short of the CLI's own settle used to
    exit with the report set aside, and the server will not reclaim it: a
    cancelled run is not a crash. The researcher saw the half-built attempt.
    Stopped before any session landed, the report comes back (`settle`)."""
    from bristlenose.utils import output_backup

    out = tmp_path / "study" / "bristlenose-output"
    out.mkdir(parents=True)
    (out / "bristlenose-report.html").write_text("old", encoding="utf-8")
    backup = output_backup.stash(out)
    assert backup is not None
    out.mkdir()
    sentinel = tmp_path / "ready"
    preamble = GRACE.format(grace=0.5) + (
        "\nfrom bristlenose.utils import output_backup as _ob"
        f"\n_rl_mod.set_backstop_settle(lambda: _ob.settle("
        f"Path({str(backup)!r}), Path({str(out)!r})))"
    )
    proc = _spawn_lifecycle_subprocess(out, _stuck_body(sentinel), preamble=preamble, env=HOSTED)
    f = events_path(out)
    try:
        _wait_for_run_started(f)
        _wait_for_ready(sentinel)
        proc.send_signal(signal.SIGINT)
        code = _wait_exit(proc, 30.0)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    assert code == 128 + signal.SIGINT, code
    assert (out / "bristlenose-report.html").read_text(encoding="utf-8") == "old"
    assert not backup.exists()
    # The stop is recorded on the report that is back.
    (terminus,) = _termini(events_path(out))
    assert isinstance(terminus, RunCancelledEvent)


def _cli_runner(monkeypatch):
    from typer.testing import CliRunner

    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", lambda s: None)
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None)
    return CliRunner()


def test_the_cli_gives_the_backstop_its_settle_while_the_report_is_aside(
    tmp_path: Path, monkeypatch,
) -> None:
    import bristlenose.run_lifecycle as rl
    from bristlenose.cli import app

    input_dir = tmp_path / "interviews"
    out = input_dir / "bristlenose-output"
    out.mkdir(parents=True)
    (out / "bristlenose-report.html").write_text("old", encoding="utf-8")
    seen: list[str] = []

    async def _stuck_then_backstop(*a, **k):
        # What the backstop does from its thread, holding the exit.
        rl._run_backstop_settle()
        seen.append((out / "bristlenose-report.html").read_text(encoding="utf-8"))
        raise RuntimeError("never reached in a real stuck stop")

    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _stuck_then_backstop)
    _cli_runner(monkeypatch).invoke(app, ["run", str(input_dir), "--clean", "--yes", "--no-serve"])

    assert seen == ["old"]
    assert rl._backstop_settle is None


def test_a_stuck_stop_after_a_session_landed_keeps_the_fresh_analysis(
    tmp_path: Path, monkeypatch,
) -> None:
    """The backstop decides as the CLI would have (owner, 23 Oct 2026)."""
    import bristlenose.run_lifecycle as rl
    from bristlenose.cli import app
    from bristlenose.utils import output_backup
    from tests.test_output_backup import _land_a_session

    input_dir = tmp_path / "interviews"
    out = input_dir / "bristlenose-output"
    out.mkdir(parents=True)
    (out / "bristlenose-report.html").write_text("old", encoding="utf-8")

    seen: list[tuple[str, bool]] = []

    async def _landed_then_stuck(_self, _in, o, *a, **k):
        (Path(o) / "bristlenose-report.html").write_text("fresh", encoding="utf-8")
        _land_a_session(Path(o))
        # What the backstop does from its thread; read before the CLI's own
        # `finally` settles, so this pins the backstop, not the CLI.
        rl._run_backstop_settle()
        seen.append((
            (out / "bristlenose-report.html").read_text(encoding="utf-8"),
            output_backup.backup_path_for(out).exists(),
        ))
        raise RuntimeError("never reached in a real stuck stop")

    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _landed_then_stuck)
    _cli_runner(monkeypatch).invoke(app, ["run", str(input_dir), "--clean", "--yes", "--no-serve"])

    assert seen == [("fresh", False)]


def test_a_backstop_after_the_report_was_replaced_settles_nothing(
    tmp_path: Path, monkeypatch,
) -> None:
    import bristlenose.run_lifecycle as rl
    from bristlenose.cli import app
    from bristlenose.events import PipelineSummary
    from bristlenose.utils import output_backup

    input_dir = tmp_path / "interviews"
    out = input_dir / "bristlenose-output"
    out.mkdir(parents=True)
    (out / "bristlenose-report.html").write_text("old", encoding="utf-8")

    class _Result:
        llm_model = "claude-sonnet-4-6"
        llm_input_tokens = llm_output_tokens = 0
        llm_calls = 1
        total_quotes = 3
        summary = PipelineSummary()

    async def _run(_self, _in, o, *a, **k):
        (Path(o) / "bristlenose-report.html").write_text("new", encoding="utf-8")
        return _Result()

    real_discard = output_backup.discard

    def _backstop_fires_as_the_discard_starts(backup):
        rl._run_backstop_settle()
        return real_discard(backup)

    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _run)
    monkeypatch.setattr(output_backup, "discard", _backstop_fires_as_the_discard_starts)
    _cli_runner(monkeypatch).invoke(app, ["run", str(input_dir), "--clean", "--yes", "--no-serve"])

    assert (out / "bristlenose-report.html").read_text(encoding="utf-8") == "new"
