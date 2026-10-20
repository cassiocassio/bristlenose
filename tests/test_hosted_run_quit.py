"""Leaving the Mac app stops its run (R19, 20 Oct 2026).

A hosted run's stdout is a pipe to the app. A run that outlived the app failed
at its next print — EPIPE, ``run_failed`` "CLI exited with code 1" — after a
relaunch had attached and read "Resuming…". ⌘Q now SIGINTs the run
(`PipelineRunner.stopAllForQuit`), and a force-quit or crash reaches it through
the parent-death watcher, so both record ``run_cancelled``: "Stopped",
resumable. The second signal that combination sends must not lose the cancel;
the subprocess form of that is in ``test_run_lifecycle.py``.
"""

from __future__ import annotations

import signal
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

import bristlenose.run_lifecycle as rl
from bristlenose.cli import app

HOSTED = "_BRISTLENOSE_HOSTED_BY_DESKTOP"


def _invoke_run(monkeypatch, tmp_path: Path, *, hosted: bool) -> list[dict]:
    calls: list[dict] = []

    def _watcher(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("bristlenose.server.lifecycle.install_parent_death_watcher", _watcher)
    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)

    def _stop(settings: object) -> None:
        raise typer.Exit(0)

    # Leave right after the watcher's place: nothing further is under test.
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", _stop)
    if hosted:
        monkeypatch.setenv(HOSTED, "1")
    else:
        monkeypatch.delenv(HOSTED, raising=False)
    input_dir = tmp_path / "interviews"
    input_dir.mkdir()
    result = CliRunner().invoke(app, ["run", str(input_dir), "--no-serve"])
    assert result.exit_code == 0, result.output
    return calls


def test_a_hosted_run_watches_for_the_app_leaving(monkeypatch, tmp_path: Path) -> None:
    calls = _invoke_run(monkeypatch, tmp_path, hosted=True)
    assert calls == [{"poll_interval_sec": 0.5}]


def test_a_cli_run_does_not(monkeypatch, tmp_path: Path) -> None:
    """A CLI user may nohup a run and close the terminal; it must carry on."""
    assert _invoke_run(monkeypatch, tmp_path, hosted=False) == []


@pytest.fixture()
def fresh_handler(monkeypatch):
    monkeypatch.setattr(rl, "_caught_signal", None)


def test_a_hosted_run_already_stopping_ignores_a_second_signal(monkeypatch, fresh_handler) -> None:
    monkeypatch.setenv(HOSTED, "1")
    with pytest.raises(KeyboardInterrupt):
        rl._signal_handler(signal.SIGINT, None)
    try:
        rl._signal_handler(signal.SIGTERM, None)
    except KeyboardInterrupt:
        # Caught here: an escaping KeyboardInterrupt aborts the pytest session
        # instead of failing this test.
        pytest.fail("a second signal interrupted a hosted run already stopping")
    assert rl._caught_signal == signal.SIGINT, "the cancel records the first signal"


def test_a_cli_run_keeps_a_second_ctrl_c_as_force(monkeypatch, fresh_handler) -> None:
    monkeypatch.delenv(HOSTED, raising=False)
    with pytest.raises(KeyboardInterrupt):
        rl._signal_handler(signal.SIGINT, None)
    with pytest.raises(KeyboardInterrupt):
        rl._signal_handler(signal.SIGINT, None)
