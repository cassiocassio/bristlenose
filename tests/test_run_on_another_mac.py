"""A run on another Mac, seen through a synced study folder (R114, partly fixed).

Two Macs share one study folder through a sync provider (iCloud Drive,
Dropbox, OneDrive). Machine B starts a run; its files sync to machine A:

- ``bristlenose-output/.bristlenose/run.pid`` names B's pid and B's process
  start time. On A that pid names no process, or an unrelated one;
- ``pipeline-events.jsonl`` ends on B's ``run_started``, whose process
  envelope records B's hostname;
- for a Re-analyse, the old report is set aside at
  ``.bristlenose-output-previous/``.

Every liveness check (``_is_alive_owned``: pid plus start time, on this
machine's process table) reads B's live run as dead, and the study-folder
``flock`` in ``output_backup._settling`` is local to each machine: a sync
provider carries files, not locks. So A treats B's live run as a crash.

Observed 24 Oct 2026, before the startup guard (RE#R114):

1. Opening the study in the Mac app on A starts a serve, whose
   ``reclaim_after_crash`` puts the old report back over B's live Re-analyse
   and deletes B's tree.
2. ``bristlenose run`` on A records B's run as failed ("Analysis stopped
   unexpectedly."), replaces B's ``run.pid`` with its own, and writes into
   B's tree.
3. ``read_condition`` (the serve's status) reads B's run as stranded.

The startup-recovery case is fixed with stable ownership; explicit run and
status cases remain strict xfails, pending the broader read-only design. Whatever the
decision, a run another Mac started a moment ago must not be destroyed
or recorded as failed from this one. The controls below pin that the same
fixture, with this machine's hostname and a dead pid, is still a crash that
is recovered: the fixture differs only in where the run lives.
"""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bristlenose.cli import app
from bristlenose.events import (
    KindEnum,
    Process,
    RunCompletedEvent,
    RunStartedEvent,
    _now_iso,
    append_event,
    events_path,
    new_run_id,
)
from bristlenose.run_condition import RunStateEnum, read_condition
from bristlenose.run_lifecycle import pid_file_path
from bristlenose.utils import output_backup
from bristlenose.utils.machine_identity import machine_id

_MARKER = "bristlenose-report.html"
_OTHER_MAC = "another-mac.local"

_OPEN = pytest.mark.xfail(strict=True, reason=(
    "R114, broader v1 open: explicit run/status still use the local process "
    "table. The startup-recovery guard does not implement a study-wide "
    "read-only mode (design-study-read-only.md)."
))


@pytest.fixture(autouse=True)
def known_local_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario ownership is deterministic; OS discovery has separate tests."""
    monkeypatch.setattr("bristlenose.utils.machine_identity.machine_id", lambda: "this-machine")
    monkeypatch.setattr("bristlenose.run_lifecycle.machine_id", lambda: "this-machine")
    monkeypatch.setattr(__name__ + ".machine_id", lambda: "this-machine")
    monkeypatch.setattr("bristlenose.utils.study_startup.machine_id", lambda: "this-machine")


def _dead_pid() -> int:
    pid = 99_000
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return pid
        except PermissionError:
            pass
        except OSError:  # Windows says "no such process" as WinError 87
            return pid
        pid += 1


def _seed_report(out: Path, marker: str) -> None:
    """A finished report: a deliverable, a manifest and a completed run."""
    state = out / ".bristlenose"
    state.mkdir(parents=True, exist_ok=True)
    (out / _MARKER).write_text(marker, encoding="utf-8")
    (state / "pipeline-manifest.json").write_text("{}", encoding="utf-8")
    run_id, now = new_run_id(), _now_iso()
    append_event(events_path(out), RunStartedEvent(
        ts=now, run_id=run_id, kind=KindEnum.RUN, started_at=now,
        process=_process(1, "1.0", socket.gethostname())))
    append_event(events_path(out), RunCompletedEvent(
        ts=now, run_id=run_id, kind=KindEnum.RUN, started_at=now, ended_at=now))


def _process(pid: int, start: str, host: str) -> Process:
    return Process(pid=pid, start_time=start, hostname=host, user="u",
                   bristlenose_version="0", python_version="3.12", os="darwin-arm64")


def _seed_run_in_flight(out: Path, *, host: str) -> str:
    """A run started a moment ago, as its files read here. Returns its run id.

    Its pid names no process on this machine. On *host* = another Mac that is
    what a live run there looks like; on this machine's own name it is a crash.
    ``machine_id`` models the stable ownership written by new builds; hostname
    remains diagnostic only.
    """
    state = out / ".bristlenose"
    state.mkdir(parents=True, exist_ok=True)
    (out / _MARKER).write_text("THE RUN IN FLIGHT IS WRITING HERE", encoding="utf-8")
    (state / "pipeline-manifest.json").write_text("{}", encoding="utf-8")
    run_id, now = new_run_id(), _now_iso()
    pid, start = _dead_pid(), "1761300000.123456"
    pid_file_path(out).write_text(json.dumps(
        {"pid": pid, "start_time": start, "run_id": run_id, "hostname": host,
         "machine_id": machine_id() if host == socket.gethostname() else "other-machine"}),
        encoding="utf-8")
    append_event(events_path(out), RunStartedEvent(
        ts=now, run_id=run_id, kind=KindEnum.RUN, started_at=now,
        process=_process(pid, start, host)))
    return run_id


def _events(out: Path) -> list[dict]:
    text = events_path(out).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _ends_of(out: Path, run_id: str) -> list[str]:
    return [e["event"] for e in _events(out)
            if e.get("run_id") == run_id and e["event"] != "run_started"]


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", lambda s: None)
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None)
    return CliRunner()


class _Result:
    llm_model = "claude-sonnet-4-6"
    llm_input_tokens = 0
    llm_output_tokens = 0
    llm_calls = 1
    summary = None
    total_quotes = 3


def _stub_pipeline(monkeypatch) -> dict:
    # Hardware selection is unrelated to ownership; do not initialise Metal/MLX.
    monkeypatch.setattr("bristlenose.cli._print_header", lambda *a, **k: None)
    monkeypatch.setattr("bristlenose.cli._build_estimator", lambda *a, **k: (None, None))
    seen: dict = {}

    async def _run(_self, _in, out, *a, **k):
        report = Path(out) / _MARKER
        seen["started_on"] = report.read_text(encoding="utf-8") if report.exists() else None
        return _Result()

    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _run)
    return seen


def _study(tmp_path: Path) -> Path:
    return tmp_path / "interviews" / "bristlenose-output"


# --- Opening the study on A while B re-analyses ------------------------------


def test_opening_the_study_leaves_a_re_analyse_on_another_mac_alone(tmp_path: Path) -> None:
    """The serve's reclaim at launch, on A, mid B's Re-analyse."""
    out = _study(tmp_path)
    _seed_report(output_backup.backup_path_for(out), "THE PREVIOUS REPORT")
    _seed_run_in_flight(out, host=_OTHER_MAC)

    output_backup.reclaim_after_crash(out)

    assert (out / _MARKER).read_text(encoding="utf-8") == "THE RUN IN FLIGHT IS WRITING HERE"
    assert output_backup.backup_path_for(out).is_dir()


def test_control_opening_the_study_after_a_crash_here_puts_the_report_back(
    tmp_path: Path,
) -> None:
    out = _study(tmp_path)
    _seed_report(output_backup.backup_path_for(out), "THE PREVIOUS REPORT")
    _seed_run_in_flight(out, host=socket.gethostname())

    outcome = output_backup.reclaim_after_crash(out)

    assert outcome is output_backup.RestoreOutcome.RESTORED
    assert (out / _MARKER).read_text(encoding="utf-8") == "THE PREVIOUS REPORT"


# --- A run on A while B runs ------------------------------------------------


def test_a_run_here_does_not_fail_a_run_on_another_mac(
    runner, tmp_path: Path, monkeypatch,
) -> None:
    out = _study(tmp_path)
    run_id = _seed_run_in_flight(out, host=_OTHER_MAC)
    seen = _stub_pipeline(monkeypatch)

    result = runner.invoke(app, ["run", str(out.parent), "--no-serve"])

    assert result.exit_code != 0, result.output
    assert "started_on" not in seen, "the pipeline ran in the other Mac's tree"
    assert _ends_of(out, run_id) == []
    assert json.loads(pid_file_path(out).read_text(encoding="utf-8"))["run_id"] == run_id


def test_a_run_here_does_not_put_a_report_back_over_a_re_analyse_on_another_mac(
    runner, tmp_path: Path, monkeypatch,
) -> None:
    out = _study(tmp_path)
    _seed_report(output_backup.backup_path_for(out), "THE PREVIOUS REPORT")
    _seed_run_in_flight(out, host=_OTHER_MAC)
    _stub_pipeline(monkeypatch)

    runner.invoke(app, ["run", str(out.parent), "--no-serve"])

    assert (out / _MARKER).read_text(encoding="utf-8") == "THE RUN IN FLIGHT IS WRITING HERE"
    assert output_backup.backup_path_for(out).is_dir()


def test_control_a_run_here_after_a_crash_here_records_it_and_carries_on(
    runner, tmp_path: Path, monkeypatch,
) -> None:
    out = _study(tmp_path)
    run_id = _seed_run_in_flight(out, host=socket.gethostname())
    seen = _stub_pipeline(monkeypatch)

    result = runner.invoke(app, ["run", str(out.parent), "--no-serve"])

    assert result.exit_code == 0, result.output
    assert seen["started_on"] == "THE RUN IN FLIGHT IS WRITING HERE"
    assert _ends_of(out, run_id) == ["run_failed"]


# --- What the serve's status says on A --------------------------------------


@_OPEN
def test_the_status_here_does_not_call_a_run_on_another_mac_stranded(tmp_path: Path) -> None:
    out = _study(tmp_path)
    _seed_run_in_flight(out, host=_OTHER_MAC)

    latest = read_condition(out).latest

    assert latest is not None
    assert latest.state is not RunStateEnum.STRANDED


def test_control_the_status_here_calls_a_crash_here_stranded(tmp_path: Path) -> None:
    out = _study(tmp_path)
    _seed_run_in_flight(out, host=socket.gethostname())

    latest = read_condition(out).latest

    assert latest is not None
    assert latest.state is RunStateEnum.STRANDED


@pytest.mark.parametrize("marker_kind", ["foreign", "legacy", "missing", "malformed", "wrong-run", "unknown-local"])
def test_startup_recovery_requires_positive_ownership(tmp_path, monkeypatch, marker_kind):
    """All protected files survive byte-for-byte, including history and backups."""
    out = _study(tmp_path)
    _seed_report(output_backup.backup_path_for(out), "THE PREVIOUS REPORT")
    _seed_run_in_flight(out, host=socket.gethostname())
    path = pid_file_path(out)
    marker = json.loads(path.read_text())
    if marker_kind == "foreign":
        marker["machine_id"] = "another-machine"
    elif marker_kind == "legacy":
        marker.pop("machine_id")
    elif marker_kind == "wrong-run":
        marker["run_id"] = "different-run"
    elif marker_kind == "unknown-local":
        monkeypatch.setattr("bristlenose.utils.machine_identity.machine_id", lambda: None)
    path.write_text(json.dumps(marker))
    if marker_kind == "missing":
        path.unlink()
    elif marker_kind == "malformed":
        path.write_text("{broken")
    before = {p.relative_to(out.parent): p.read_bytes()
              for p in out.parent.rglob("*") if p.is_file()}

    assert output_backup.reclaim_after_crash(out) is output_backup.RestoreOutcome.NOTHING_TO_DO

    after = {p.relative_to(out.parent): p.read_bytes()
             for p in out.parent.rglob("*") if p.is_file()}
    assert after == before


def test_pid_writer_records_machine_ownership(tmp_path, monkeypatch):
    from bristlenose.run_lifecycle import _write_pid_file

    monkeypatch.setattr("bristlenose.run_lifecycle.machine_id", lambda: "stable-owner")
    path = _write_pid_file(tmp_path, "attempt", "process-start")
    assert json.loads(path.read_text())["machine_id"] == "stable-owner"


@pytest.mark.parametrize("ownership", ["foreign", "legacy", "wrong-run"])
def test_server_factory_preserves_uncertain_run_before_first_write(tmp_path, monkeypatch, ownership):
    """Exercise the real factory through recovery, stopping at its first writer.

    Ordinary server startup still writes after this boundary; refusing that
    startup is the separate admission step, not a promise made by this fix.
    """
    from bristlenose.server.app import create_app
    out = _study(tmp_path)
    _seed_report(output_backup.backup_path_for(out), "PREVIOUS")
    _seed_run_in_flight(out, host=_OTHER_MAC)
    marker_path = pid_file_path(out)
    marker = json.loads(marker_path.read_text())
    if ownership == "legacy":
        marker.pop("machine_id")
    elif ownership == "wrong-run":
        marker.update(machine_id=machine_id(), run_id="another-attempt")
    marker_path.write_text(json.dumps(marker))
    before = {p.relative_to(out.parent): p.read_bytes() for p in out.parent.rglob("*") if p.is_file()}

    class FirstWriterReachedError(Exception):
        pass

    def stop_before_logging(**kwargs):
        raise FirstWriterReachedError

    monkeypatch.setattr("bristlenose.logging.setup_logging", stop_before_logging)
    from bristlenose.utils.study_startup import StudyStartupRefusedError

    with pytest.raises(StudyStartupRefusedError):
        create_app(project_dir=out.parent)
    after = {p.relative_to(out.parent): p.read_bytes() for p in out.parent.rglob("*") if p.is_file()}
    assert after == before


@pytest.mark.parametrize("key,value", [("pid", None), ("pid", True), ("pid", -1),
                                      ("pid", "123"), ("start_time", None), ("start_time", " ")])
def test_local_malformed_process_marker_never_authorises_recovery(tmp_path, key, value):
    out = _study(tmp_path)
    _seed_report(output_backup.backup_path_for(out), "PREVIOUS")
    _seed_run_in_flight(out, host=socket.gethostname())
    path = pid_file_path(out)
    marker = json.loads(path.read_text())
    marker[key] = value
    path.write_text(json.dumps(marker))
    before = {p.relative_to(out.parent): p.read_bytes() for p in out.parent.rglob("*") if p.is_file()}
    assert output_backup.reclaim_after_crash(out) is output_backup.RestoreOutcome.NOTHING_TO_DO
    after = {p.relative_to(out.parent): p.read_bytes() for p in out.parent.rglob("*") if p.is_file()}
    assert after == before


def test_invalid_utf8_marker_is_unavailable_not_destructive(tmp_path):
    from bristlenose.run_lifecycle import _read_pid_file
    out = _study(tmp_path)
    _seed_report(output_backup.backup_path_for(out), "PREVIOUS")
    _seed_run_in_flight(out, host=socket.gethostname())
    pid_file_path(out).write_bytes(b"\xff")
    before = {p.relative_to(out.parent): p.read_bytes() for p in out.parent.rglob("*") if p.is_file()}
    assert _read_pid_file(out) is None
    assert output_backup.reclaim_after_crash(out) is output_backup.RestoreOutcome.NOTHING_TO_DO
    after = {p.relative_to(out.parent): p.read_bytes() for p in out.parent.rglob("*") if p.is_file()}
    assert after == before
