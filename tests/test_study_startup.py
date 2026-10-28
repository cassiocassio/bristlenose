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
from bristlenose.utils.output_backup import backup_path_for
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
        json.dumps({"run_id": "attempt", "machine_id": owner, "pid": 99000, "start_time": "dead"})
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
        path.write_text("{")
    elif problem == "bad-unicode":
        path.write_bytes(b"\xff")
    elif problem == "wrong-run":
        path.write_text(json.dumps({"run_id": "different", "machine_id": "local"}))
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
    events_path(tmp_path).write_text(history)
    assert startup_refusal(tmp_path) is StartupRefusal.UNVERIFIED_UNFINISHED


def test_orphan_marker_refuses(tmp_path):
    pid_file_path(tmp_path).parent.mkdir()
    pid_file_path(tmp_path).write_text("{}")
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
    (backup_path_for(out) / "old-report.html").write_text("saved")
    if new_output_exists:
        out.mkdir()
    before = tree(tmp_path)
    assert startup_refusal(out) is StartupRefusal.UNVERIFIED_UNFINISHED
    assert tree(tmp_path) == before


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
    with events_path(tmp_path).open("a") as log:
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
    marker = json.loads(pid_file_path(tmp_path).read_text())
    marker[key] = value
    pid_file_path(tmp_path).write_text(json.dumps(marker))
    assert startup_refusal(tmp_path) is StartupRefusal.UNVERIFIED_UNFINISHED
