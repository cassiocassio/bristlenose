"""Local AI on Windows: Ollama installs through winget and starts from its tray app.

Every shell-out is mocked. The real-machine check is the Windows 11 Arm VM
(docs/design-windows-port.md); these pin the decisions that run on it.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

import pytest

from bristlenose import ollama


def _status(running: bool) -> ollama.OllamaStatus:
    return ollama.OllamaStatus(
        is_running=running,
        has_suitable_model=running,
        recommended_model=None,
        available_models=[],
        message="",
    )


@pytest.fixture
def windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A Windows host whose LOCALAPPDATA is tmp_path, with nothing on PATH."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr("time.sleep", lambda s: None)
    return tmp_path


@pytest.fixture
def no_shellouts(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Record every subprocess command instead of running it."""
    calls: list[list[str]] = []

    def run(cmd, *a, **k):  # noqa: ANN001, ANN002, ANN003
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    def popen(cmd, *a, **k):  # noqa: ANN001, ANN002, ANN003
        calls.append(list(cmd))
        return None

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", popen)
    return calls


def _install(folder: Path, *names: str) -> Path:
    app = folder / "Programs" / "Ollama"
    app.mkdir(parents=True)
    for name in names:
        (app / name).write_bytes(b"")
    return app


# --- install method ---------------------------------------------------------


def test_windows_with_winget_installs_with_winget(
    windows: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("shutil.which", lambda n: "C:/winget.exe" if n == "winget" else None)
    assert ollama.get_install_method() == "winget"


def test_windows_without_winget_falls_back_to_the_download_page(windows: Path) -> None:
    assert ollama.get_install_method() is None


def test_winget_install_names_the_package_and_accepts_once(
    windows: Path, no_shellouts: list[list[str]]
) -> None:
    assert ollama.install_ollama("winget") is True
    assert no_shellouts == [[
        "winget", "install", "--id", "Ollama.Ollama", "-e", "--source", "winget",
        "--accept-package-agreements", "--accept-source-agreements",
    ]]


# --- after install: the new user PATH has not reached this process ----------


def test_a_fresh_install_is_found_off_path(windows: Path) -> None:
    assert ollama.is_ollama_installed() is False
    app = _install(windows, "ollama.exe")
    assert ollama.is_ollama_installed() is True
    assert ollama.ollama_executable() == str(app / "ollama.exe")


def test_pull_uses_the_installed_exe_not_bare_ollama(
    windows: Path, no_shellouts: list[list[str]]
) -> None:
    app = _install(windows, "ollama.exe")
    assert ollama.pull_model("llama3.2:3b") is True
    assert no_shellouts == [[str(app / "ollama.exe"), "pull", "llama3.2:3b"]]


# --- start --------------------------------------------------------------------


def test_already_running_starts_nothing(
    windows: Path, no_shellouts: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(windows, "ollama.exe", "ollama app.exe")
    monkeypatch.setattr(ollama, "check_ollama", lambda: _status(True))
    assert ollama.start_ollama_serve() is True
    assert no_shellouts == []


def test_the_installer_launched_tray_app_is_waited_for_not_doubled(
    windows: Path, no_shellouts: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """winget's installer starts the tray app without waiting; it comes up a beat later."""
    _install(windows, "ollama.exe", "ollama app.exe")
    answers = iter([False, False, True])
    monkeypatch.setattr(ollama, "check_ollama", lambda: _status(next(answers)))
    assert ollama.start_ollama_serve() is True
    assert no_shellouts == []


def test_windows_starts_the_tray_app_never_brew_or_systemctl(
    windows: Path, no_shellouts: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _install(windows, "ollama.exe", "ollama app.exe")
    cmd, display = ollama.get_start_command()
    assert cmd == [str(app / "ollama app.exe")]
    assert "Start menu" in display

    answers = iter([False] * 6 + [True])  # down through the grace window, up after launch
    monkeypatch.setattr(ollama, "check_ollama", lambda: _status(next(answers)))
    assert ollama.start_ollama_serve() is True
    assert no_shellouts == [[str(app / "ollama app.exe")]]


def test_without_the_tray_app_serve_runs_from_the_resolved_exe(windows: Path) -> None:
    app = _install(windows, "ollama.exe")
    cmd, _display = ollama.get_start_command()
    assert cmd == [str(app / "ollama.exe"), "serve"]


# --- doctor -------------------------------------------------------------------


def test_doctor_offers_winget_on_windows(windows: Path) -> None:
    from bristlenose.doctor_fixes import get_fix

    text = get_fix("ollama_not_installed", "pip")
    assert "winget install --id Ollama.Ollama -e --source winget" in text
    assert "bristlenose configure local" in text
