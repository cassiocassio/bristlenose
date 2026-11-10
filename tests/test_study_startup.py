"""No writers or cloud APIs: admission classifies only local evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bristlenose.events import (
    KindEnum,
    Process,
    RunCompletedEvent,
    RunStartedEvent,
    _now_iso,
    append_event,
    events_path,
)
from bristlenose.run_lifecycle import pid_file_path
from bristlenose.utils.output_backup import _OWNER_MARKER, backup_path_for
from bristlenose.utils.study_startup import StartupRefusal, startup_refusal


def seed(out: Path, *, owner="local", completed=False):
    now = _now_iso()
    append_event(
        events_path(out),
        RunStartedEvent(
            ts=now,
            run_id="attempt",
            kind=KindEnum.RUN,
            started_at=now,
            process=Process(
                pid=99000,
                start_time="dead",
                hostname="home.local",
                user="u",
                bristlenose_version="0",
                python_version="3.12",
                os="darwin-arm64",
            ),
        ),
    )
    pid_file_path(out).write_text(
        json.dumps({"run_id": "attempt", "machine_id": owner, "pid": 99000, "start_time": "dead"}), encoding="utf-8"
    )
    if completed:
        append_event(
            events_path(out),
            RunCompletedEvent(
                ts=now, run_id="attempt", kind=KindEnum.RUN, started_at=now, ended_at=now
            ),
        )


@pytest.fixture(autouse=True)
def local(monkeypatch):
    monkeypatch.setattr("bristlenose.utils.study_startup.machine_id", lambda: "local")


def tree(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("foreign", [False, True])
def test_retry_probe_never_starts_server_or_writes(tmp_path, monkeypatch, foreign):
    from typer.testing import CliRunner

    from bristlenose.cli import app
    from bristlenose.output_paths import project_output_dir

    out = project_output_dir(tmp_path)
    if foreign:
        seed(out, owner="other-mac")
    before = tree(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("A startup-only probe reached settings or server construction")

    monkeypatch.setattr("bristlenose.cli.load_settings", forbidden)
    monkeypatch.setattr("bristlenose.cli._create_admitted_app", forbidden)
    result = CliRunner().invoke(app, ["serve", str(tmp_path), "--check-startup-only"])
    assert result.exit_code == (75 if foreign else 0), result.output
    assert tree(tmp_path) == before


@pytest.mark.parametrize(
    "owner,completed,expected",
    [
        ("local", False, None),
        ("foreign", False, StartupRefusal.FOREIGN_UNFINISHED),
        (None, False, StartupRefusal.UNVERIFIED_UNFINISHED),
        ("", False, StartupRefusal.UNVERIFIED_UNFINISHED),
        (12, False, StartupRefusal.UNVERIFIED_UNFINISHED),
        ("foreign", True, None),
        (None, True, None),
    ],
)
def test_classifies_without_changing_a_byte(tmp_path, owner, completed, expected):
    out = tmp_path / "output"
    seed(out, owner=owner, completed=completed)
    before = tree(tmp_path)
    assert startup_refusal(out) is expected
    assert tree(tmp_path) == before


@pytest.mark.parametrize(
    "problem", ["missing", "bad-json", "bad-unicode", "wrong-run", "unknown-local"]
)
def test_uncertain_unfinished_ownership_refuses(tmp_path, monkeypatch, problem):
    seed(tmp_path)
    path = pid_file_path(tmp_path)
    if problem == "missing":
        path.unlink()
    elif problem == "bad-json":
        path.write_text("{", encoding="utf-8")
    elif problem == "bad-unicode":
        path.write_bytes(b"\xff")
    elif problem == "wrong-run":
        path.write_text(json.dumps({"run_id": "different", "machine_id": "local"}), encoding="utf-8")
    else:
        monkeypatch.setattr("bristlenose.utils.study_startup.machine_id", lambda: None)
    before = tree(tmp_path)
    assert startup_refusal(tmp_path) is StartupRefusal.UNVERIFIED_UNFINISHED
    assert tree(tmp_path) == before


def test_new_folder_is_not_created(tmp_path):
    out = tmp_path / "absent"
    assert startup_refusal(out) is None
    assert not out.exists()


@pytest.mark.parametrize(
    "history", ["garbage", '{"event":"run_started"}', '{"event":"run_started"']
)
def test_uninterpretable_history_is_not_a_clean_start(tmp_path, history):
    events_path(tmp_path).parent.mkdir()
    events_path(tmp_path).write_text(history, encoding="utf-8")
    assert startup_refusal(tmp_path) is StartupRefusal.UNVERIFIED_UNFINISHED


def test_orphan_marker_refuses(tmp_path):
    pid_file_path(tmp_path).parent.mkdir()
    pid_file_path(tmp_path).write_text("{}", encoding="utf-8")
    assert startup_refusal(tmp_path) is StartupRefusal.UNVERIFIED_UNFINISHED


def test_unreadable_condition_refuses(tmp_path, monkeypatch):
    def unreadable(*args, **kwargs):
        raise PermissionError("unreadable")

    monkeypatch.setattr("bristlenose.utils.study_startup.reduce_lines", unreadable)
    assert startup_refusal(tmp_path) is StartupRefusal.UNVERIFIED_UNFINISHED


@pytest.mark.parametrize("new_output_exists", [False, True])
def test_reanalysis_startup_gap_is_not_a_clean_start(tmp_path, new_output_exists):
    out = tmp_path / "output"
    backup_path_for(out).mkdir()
    (backup_path_for(out) / "old-report.html").write_text("saved", encoding="utf-8")
    if new_output_exists:
        out.mkdir()
    before = tree(tmp_path)
    assert startup_refusal(out) is StartupRefusal.UNVERIFIED_UNFINISHED
    assert tree(tmp_path) == before



def _set_aside(out: Path, *, owner: str | None, alive: bool = False) -> None:
    """A report set aside and nothing written since: a run starting, or killed."""
    import os

    from bristlenose.run_lifecycle import _ps_start_time

    backup = backup_path_for(out)
    backup.mkdir(parents=True)
    (backup / "old-report.html").write_text("saved", encoding="utf-8")
    if owner is not None:
        (backup / _OWNER_MARKER).write_text(json.dumps({
            "machine_id": owner, "pid": os.getpid(),
            "start_time": _ps_start_time(os.getpid()) if alive else "dead",
        }), encoding="utf-8")


@pytest.fixture
def this_mac(monkeypatch):
    monkeypatch.setattr("bristlenose.utils.machine_identity.machine_id", lambda: "local")


@pytest.mark.parametrize("alive", [True, False])
def test_a_set_aside_this_mac_owns_is_the_ordinary_flow(tmp_path, this_mac, alive):
    """Still starting, or killed before its first event: never "unverified"."""
    out = tmp_path / "output"
    _set_aside(out, owner="local", alive=alive)
    assert startup_refusal(out) is None


def test_a_set_aside_by_another_mac_says_so(tmp_path, this_mac):
    out = tmp_path / "output"
    _set_aside(out, owner="other-mac", alive=True)
    before = tree(tmp_path)
    assert startup_refusal(out) is StartupRefusal.FOREIGN_UNFINISHED
    assert tree(tmp_path) == before


def test_a_quiet_set_aside_from_an_older_build_is_the_ordinary_flow(tmp_path, monkeypatch):
    out = tmp_path / "output"
    _set_aside(out, owner=None)
    monkeypatch.setattr("bristlenose.utils.output_backup._QUIET_S", 0.0)
    assert startup_refusal(out) is None


def test_an_unreadable_owner_note_refuses(tmp_path, this_mac):
    out = tmp_path / "output"
    _set_aside(out, owner=None)
    (backup_path_for(out) / _OWNER_MARKER).write_text("{broken", encoding="utf-8")
    assert startup_refusal(out) is StartupRefusal.UNVERIFIED_UNFINISHED


@pytest.mark.parametrize("owner,alive,restored", [
    ("local", False, True),  # killed before its first event: put back at once
    ("local", True, False),  # a run still starting: never under it
    ("other-mac", False, False),  # another Mac's, whatever its pid says here
])
def test_the_servers_reclaim_reads_the_owner_note(tmp_path, this_mac, owner, alive, restored):
    from bristlenose.utils import output_backup

    out = tmp_path / "output"
    _set_aside(out, owner=owner, alive=alive)
    outcome = output_backup.reclaim_after_crash(out)
    assert (outcome is output_backup.RestoreOutcome.RESTORED) is restored
    assert backup_path_for(out).exists() is not restored
    if restored:
        assert (out / "old-report.html").read_text(encoding="utf-8") == "saved"
        assert not (out / _OWNER_MARKER).exists(), "the note outlived the set-aside"


def test_the_next_run_leaves_a_run_still_starting_alone(tmp_path, this_mac):
    from bristlenose.utils import output_backup

    out = tmp_path / "output"
    _set_aside(out, owner="local", alive=True)
    assert output_backup.reclaim_stale(out) is output_backup.RestoreOutcome.NOTHING_TO_DO
    assert backup_path_for(out).exists()


def test_the_stash_writes_the_note_and_the_restore_removes_it(tmp_path, this_mac):
    from bristlenose.utils import output_backup

    out = tmp_path / "output"
    out.mkdir()
    (out / "report.html").write_text("r", encoding="utf-8")
    backup = output_backup.stash(out)
    assert backup is not None
    note = json.loads((backup / _OWNER_MARKER).read_text(encoding="utf-8"))
    assert note["machine_id"] == "local"
    assert output_backup.set_aside_owner(out) is output_backup.SetAside.LOCAL_LIVE
    assert output_backup.restore(backup, out).report_is_back
    assert sorted(p.name for p in out.iterdir()) == ["report.html"]


def test_terminated_run_with_no_marker_uses_ordinary_flow(tmp_path):
    seed(tmp_path, owner="foreign", completed=True)
    pid_file_path(tmp_path).unlink()
    assert startup_refusal(tmp_path) is None


def test_symlinked_marker_is_not_ownership(tmp_path):
    out = tmp_path / "output"
    seed(out)
    marker = pid_file_path(out)
    original = marker.read_bytes()
    marker.unlink()
    target = tmp_path / "external-marker"
    target.write_bytes(original)
    marker.symlink_to(target)
    before = tree(tmp_path)
    assert startup_refusal(out) is StartupRefusal.UNVERIFIED_UNFINISHED
    assert tree(tmp_path) == before


@pytest.mark.parametrize("tail", ['{"event":"run_started"', "garbage", '{"event":"future_event"}'])
def test_old_completion_does_not_hide_damaged_or_unknown_new_history(tmp_path, tail):
    seed(tmp_path, completed=True)
    pid_file_path(tmp_path).unlink()
    with events_path(tmp_path).open("a", encoding="utf-8") as log:
        log.write(tail)
    before = tree(tmp_path)
    assert startup_refusal(tmp_path) is StartupRefusal.UNVERIFIED_UNFINISHED
    assert tree(tmp_path) == before


@pytest.mark.parametrize(
    "key,value",
    [
        ("pid", None),
        ("pid", True),
        ("pid", -1),
        ("pid", "123"),
        ("start_time", None),
        ("start_time", " "),
    ],
)
def test_local_unfinished_requires_usable_process_marker(tmp_path, key, value):
    seed(tmp_path)
    marker = json.loads(pid_file_path(tmp_path).read_text(encoding="utf-8"))
    marker[key] = value
    pid_file_path(tmp_path).write_text(json.dumps(marker), encoding="utf-8")
    assert startup_refusal(tmp_path) is StartupRefusal.UNVERIFIED_UNFINISHED


@pytest.mark.parametrize("command", ["serve", "run", "transcribe", "analyze", "analyse"])
@pytest.mark.parametrize("owner", ["foreign", None])
def test_real_cli_refuses_before_any_protected_write(tmp_path, command, owner):
    from typer.testing import CliRunner

    from bristlenose.cli import app

    root = tmp_path / "study"
    root.mkdir()
    out = root / "bristlenose-output"
    seed(out, owner=owner)
    backup_path_for(out).mkdir()
    (backup_path_for(out) / "old.html").write_text("previous report", encoding="utf-8")
    inputs = root
    args = [command]
    if command in {"analyze", "analyse"}:
        inputs = out / "transcripts-raw"
        inputs.mkdir()
    args.append(str(inputs))
    if command == "serve":
        args += ["--no-open", "--port", "0"]
    elif command == "run":
        args += ["--no-serve", "--clean"]
    before = tree(tmp_path)
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 75, result.output
    assert "This study cannot be viewed or edited here." in " ".join(result.output.split())
    assert tree(tmp_path) == before


def test_direct_lifecycle_refuses_before_marker_or_failure_events(tmp_path):
    from bristlenose.run_lifecycle import run_lifecycle
    from bristlenose.utils.study_startup import StudyStartupRefusedError

    seed(tmp_path, owner="foreign")
    before = tree(tmp_path)
    with pytest.raises(StudyStartupRefusedError):
        with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
            pytest.fail("protected body ran")
    assert tree(tmp_path) == before


def test_native_host_receives_reason_without_writing_project_history(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from bristlenose.cli import app

    root = tmp_path / "study"
    out = root / "bristlenose-output"
    seed(out, owner="foreign")
    monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")
    before = tree(tmp_path)
    result = CliRunner().invoke(app, ["serve", str(root), "--no-open", "--port", "0"])
    assert result.exit_code == 75
    assert '"reason": "foreign_unfinished"' in result.output
    assert "@study-startup-refused " in result.output
    assert tree(tmp_path) == before


def test_refusal_carries_optional_display_metadata_without_changing_authority(tmp_path):
    from bristlenose.utils.study_startup import StudyStartupRefusedError, require_study_startup
    seed(tmp_path, owner="foreign")
    path = pid_file_path(tmp_path)
    marker = json.loads(path.read_text(encoding="utf-8"))
    marker["machine_name"] = "Cassio’s Mac Studio"
    path.write_text(json.dumps(marker), encoding="utf-8")
    before = tree(tmp_path)
    with pytest.raises(StudyStartupRefusedError) as caught:
        require_study_startup(tmp_path)
    assert caught.value.reason is StartupRefusal.FOREIGN_UNFINISHED
    assert caught.value.machine_name == "Cassio’s Mac Studio"
    assert caught.value.started_at is not None
    assert tree(tmp_path) == before


def test_unverified_origin_does_not_invent_display_metadata(tmp_path):
    from bristlenose.utils.study_startup import StudyStartupRefusedError, require_study_startup
    seed(tmp_path, owner=None)
    with pytest.raises(StudyStartupRefusedError) as caught:
        require_study_startup(tmp_path)
    assert caught.value.machine_name is None
    assert caught.value.started_at is None



def test_late_factory_refusal_uses_dedicated_exit(tmp_path, monkeypatch):
    import typer

    from bristlenose.cli import _create_admitted_app
    from bristlenose.utils.study_startup import StartupRefusal, StudyStartupRefusedError

    def refused(**kwargs):
        raise StudyStartupRefusedError(StartupRefusal.UNVERIFIED_UNFINISHED)

    monkeypatch.setattr("bristlenose.server.app.create_app", refused)
    with pytest.raises(typer.Exit) as caught:
        _create_admitted_app(tmp_path, False, False)
    assert caught.value.exit_code == 75



def test_native_refusal_exit_code_matches_python_contract():
    import re

    from bristlenose.utils.study_startup import STUDY_STARTUP_REFUSAL_EXIT_CODE
    swift = (Path(__file__).resolve().parents[1] / "desktop/Bristlenose/Bristlenose/StudyStartupRefusal.swift").read_text(encoding="utf-8")
    match = re.search(r"static let exitCode: Int32 = (\d+)", swift)
    assert match is not None
    assert int(match.group(1)) == STUDY_STARTUP_REFUSAL_EXIT_CODE
