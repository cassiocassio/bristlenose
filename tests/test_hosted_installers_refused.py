"""No installer runs inside the Mac app: App Store guideline 2.5.2, made structural.

An app may not download or install code. Bristlenose has installer shellouts
for the CLI (``brew install ollama``, ``curl … | sh``, ``sudo snap install``,
``winget install``, ``pip install mlx``, ``brew install ffmpeg``,
``python -m spacy download``). Before this test they were unreachable from the
sandboxed sidecar only because nothing in serve happened to call them.

Each entry point is called twice with ``subprocess`` replaced by a recorder:
hosted (the desktop sentinel, or macOS's own ``APP_SANDBOX_CONTAINER_ID``),
where nothing may be launched at all; and as the CLI, where the installer must
still be launched exactly as before.
"""

from __future__ import annotations

import io
import subprocess
import sys
from typing import Any

import pytest
from rich.console import Console

from bristlenose import doctor_fixes, ollama
from bristlenose.preflight import ffmpeg
from bristlenose.utils import package_install
from bristlenose.utils.package_install import HostedInstallRefusedError

_HOST_SIGNALS = {
    "desktop-sentinel": ("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1"),
    "app-sandbox": ("APP_SANDBOX_CONTAINER_ID", "app.bristlenose"),
}

_OLLAMA_METHODS = ("brew", "snap", "curl", "winget")


class _Recorder:
    """Stands in for ``subprocess.run`` and ``subprocess.Popen``; records every argv."""

    def __init__(self) -> None:
        self.argvs: list[list[str]] = []

    def run(self, args: Any, *_a: Any, **_k: Any) -> subprocess.CompletedProcess[bytes]:
        self.argvs.append([str(a) for a in args])
        # A non-empty stdout so the curl arm goes on to run `sh`.
        return subprocess.CompletedProcess(args, 0, stdout=b"echo ok\n", stderr=b"")

    def popen(self, args: Any, *_a: Any, **_k: Any) -> None:
        self.argvs.append([str(a) for a in args])
        raise AssertionError("Popen is not an installer path")


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    rec = _Recorder()
    monkeypatch.setattr(subprocess, "run", rec.run)
    monkeypatch.setattr(subprocess, "Popen", rec.popen)
    # The winget arm resolves the executable before running it.
    monkeypatch.setattr(ollama, "safe_which", lambda name: f"C:/fake/{name}.exe")
    return rec


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, _value in _HOST_SIGNALS.values():
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(params=sorted(_HOST_SIGNALS))
def hosted(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str:
    for name, _value in _HOST_SIGNALS.values():
        monkeypatch.delenv(name, raising=False)
    name, value = _HOST_SIGNALS[request.param]
    monkeypatch.setenv(name, value)
    return str(request.param)


@pytest.fixture
def ffmpeg_missing_on_a_brew_mac(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every precondition for the brew offer true, the user's answer yes."""
    monkeypatch.delenv("BRISTLENOSE_SKIP_PREFLIGHT", raising=False)
    monkeypatch.setattr(ffmpeg, "bundled_binary_path", lambda _name: None)
    monkeypatch.setattr(ffmpeg, "_detect_distro", lambda: "macos")
    monkeypatch.setattr(ffmpeg, "_brew_writable_prefix", lambda: "/opt/homebrew")
    monkeypatch.setattr(ffmpeg, "_confirm_brew_install", lambda _console: True)


def _quiet_console() -> Console:
    return Console(file=io.StringIO())


def _spacy_model_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    spacy = pytest.importorskip("spacy")

    def _load(*_a: Any, **_k: Any) -> None:
        raise OSError("not installed")

    monkeypatch.setattr(spacy, "load", _load)
    monkeypatch.setattr(doctor_fixes, "detect_install_method", lambda: "pip")
    monkeypatch.setattr(sys, "frozen", False, raising=False)


# ---------------------------------------------------------------------------
# Hosted: nothing is launched, and the refusal is loud
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", [*_OLLAMA_METHODS, None])
def test_hosted_install_ollama_launches_nothing(
    recorder: _Recorder, hosted: str, method: str | None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ollama, "get_install_method", lambda: "brew")
    with pytest.raises(HostedInstallRefusedError):
        ollama.install_ollama(method)
    assert recorder.argvs == []


def test_hosted_install_mlx_launches_nothing(recorder: _Recorder, hosted: str) -> None:
    with pytest.raises(HostedInstallRefusedError):
        doctor_fixes.install_mlx()
    assert recorder.argvs == []


def test_hosted_ffmpeg_preflight_does_not_offer_brew(
    recorder: _Recorder, hosted: str, ffmpeg_missing_on_a_brew_mac: None,
) -> None:
    """The offer itself is withheld, so the user gets the plain abort, not a refusal."""
    with pytest.raises(ffmpeg.FfmpegPreflightAbortedError):
        ffmpeg.preflight_ffmpeg(console=_quiet_console(), status=None, allow_install=True)
    assert recorder.argvs == []


def test_hosted_brew_install_ffmpeg_launches_nothing(recorder: _Recorder, hosted: str) -> None:
    with pytest.raises(HostedInstallRefusedError):
        ffmpeg._run_brew_install(_quiet_console(), None)
    assert recorder.argvs == []


def test_hosted_spacy_download_launches_nothing(
    recorder: _Recorder, hosted: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _spacy_model_missing(monkeypatch)
    with pytest.raises(package_install.FrozenSidecarError):
        package_install.ensure_spacy_model("en_core_web_lg")
    assert recorder.argvs == []


# ---------------------------------------------------------------------------
# CLI: the installers run exactly as before
# ---------------------------------------------------------------------------

_EXPECTED_OLLAMA = {
    "brew": [["brew", "install", "ollama"]],
    "snap": [["sudo", "snap", "install", "ollama"]],
    "curl": [["curl", "-fsSL", ollama.INSTALL_SCRIPT_URL], ["sh"]],
    "winget": [["C:/fake/winget.exe", *ollama.WINGET_INSTALL_CMD[1:]]],
}


@pytest.mark.parametrize("method", _OLLAMA_METHODS)
def test_cli_install_ollama_runs_the_installer(
    recorder: _Recorder, cli: None, method: str,
) -> None:
    assert ollama.install_ollama(method) is True
    assert recorder.argvs == _EXPECTED_OLLAMA[method]


def test_cli_install_mlx_runs_pip(recorder: _Recorder, cli: None) -> None:
    assert doctor_fixes.install_mlx() is True
    assert recorder.argvs == [[sys.executable, "-m", "pip", "install", "mlx", "mlx-whisper"]]


def test_cli_ffmpeg_preflight_runs_brew_on_yes(
    recorder: _Recorder, cli: None, ffmpeg_missing_on_a_brew_mac: None,
) -> None:
    # bundled_binary_path still finds nothing after the fake install, so the
    # preflight ends in its abort; what matters is that brew was asked.
    with pytest.raises(ffmpeg.FfmpegPreflightAbortedError):
        ffmpeg.preflight_ffmpeg(console=_quiet_console(), status=None, allow_install=True)
    assert recorder.argvs == [["brew", "install", "ffmpeg"]]


def test_cli_spacy_download_runs(
    recorder: _Recorder, cli: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _spacy_model_missing(monkeypatch)
    package_install.ensure_spacy_model("en_core_web_lg")
    assert recorder.argvs == [[sys.executable, "-m", "spacy", "download", "en_core_web_lg"]]
