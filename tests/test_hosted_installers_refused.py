"""No installer runs inside the Mac app: App Store guideline 2.5.2, made structural.

An app may not download or install code. Bristlenose has installer shellouts
for the CLI (``brew install ollama``, ``curl … | sh``, ``sudo snap install``,
``winget install``, ``pip install mlx``, ``brew install ffmpeg``,
``python -m spacy download``). Before this test they were unreachable from the
sandboxed sidecar only because nothing in serve happened to call them.

Each entry point is called twice with ``subprocess`` replaced by a recorder:
hosted (the desktop sentinel), where nothing may be launched at all; and as
the CLI, where the installer must still be launched exactly as before. A
sweep at the end holds the invariant for installers nobody has written yet.
"""

from __future__ import annotations

import ast
import io
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console

from bristlenose import doctor_fixes, ollama
from bristlenose.preflight import ffmpeg
from bristlenose.utils import package_install
from bristlenose.utils.package_install import HostedInstallRefusedError

_SENTINEL = "_BRISTLENOSE_HOSTED_BY_DESKTOP"
#: macOS sets this in a sandboxed process. It is NOT a hosted signal: the host's
#: allowlisted child environment leaves it out, and a CLI run from a sandboxed
#: terminal app inherits it. Set in the CLI cases to keep that true.
_MACOS_SANDBOX_VAR = "APP_SANDBOX_CONTAINER_ID"

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


@pytest.fixture(params=["plain-terminal", "sandboxed-terminal"])
def cli(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_SENTINEL, raising=False)
    if request.param == "sandboxed-terminal":
        monkeypatch.setenv(_MACOS_SANDBOX_VAR, "com.example.terminal")
    else:
        monkeypatch.delenv(_MACOS_SANDBOX_VAR, raising=False)


@pytest.fixture
def hosted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_SENTINEL, "1")


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
    recorder: _Recorder, hosted: None, method: str | None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ollama, "get_install_method", lambda: "brew")
    with pytest.raises(HostedInstallRefusedError):
        ollama.install_ollama(method)
    assert recorder.argvs == []


def test_hosted_install_mlx_launches_nothing(recorder: _Recorder, hosted: None) -> None:
    with pytest.raises(HostedInstallRefusedError):
        doctor_fixes.install_mlx()
    assert recorder.argvs == []


def test_hosted_ffmpeg_preflight_does_not_offer_brew(
    recorder: _Recorder, hosted: None, ffmpeg_missing_on_a_brew_mac: None,
) -> None:
    """The offer itself is withheld, so the user gets the plain abort, not a refusal."""
    with pytest.raises(ffmpeg.FfmpegPreflightAbortedError):
        ffmpeg.preflight_ffmpeg(console=_quiet_console(), status=None, allow_install=True)
    assert recorder.argvs == []


def test_hosted_brew_install_ffmpeg_launches_nothing(recorder: _Recorder, hosted: None) -> None:
    with pytest.raises(HostedInstallRefusedError):
        ffmpeg._run_brew_install(_quiet_console(), None)
    assert recorder.argvs == []


def test_hosted_spacy_download_launches_nothing(
    recorder: _Recorder, hosted: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _spacy_model_missing(monkeypatch)
    with pytest.raises(package_install.FrozenSidecarError):
        package_install.ensure_spacy_model("en_core_web_lg")
    assert recorder.argvs == []


def test_hosted_spacy_shellout_guard_stands_alone(
    recorder: _Recorder, hosted: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The older `_is_frozen_sidecar` refusal fires first; the shellout's own guard
    must still hold if that one is ever narrowed (it answers a different question)."""
    _spacy_model_missing(monkeypatch)
    monkeypatch.setattr(package_install, "_is_frozen_sidecar", lambda: False)
    with pytest.raises(HostedInstallRefusedError):
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


# ---------------------------------------------------------------------------
# The invariant, not today's list: every installer argv in bristlenose/ is guarded
# ---------------------------------------------------------------------------

_PACKAGE = Path(__file__).resolve().parent.parent / "bristlenose"
_GUARDS = {"refuse_install_when_hosted", "installs_forbidden"}

#: Installer argv built where it is not launched. Each names the guarded function
#: that launches it, and the sweep checks that function is still guarded.
_BUILDERS = {
    ("doctor_fixes.py", "get_mlx_install_command"): ("doctor_fixes.py", "install_mlx"),
    ("ollama.py", "<module>"): ("ollama.py", "install_ollama"),  # WINGET_INSTALL_CMD
}


def _is_installer_argv(node: ast.List | ast.Tuple) -> bool:
    words = [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    if not words:
        return False
    if "install" in words or ("spacy" in words and "download" in words):
        return True
    if words[0] in {"curl", "wget"}:
        return True
    return any(a == "-m" and b in {"pip", "ensurepip"} for a, b in zip(words, words[1:], strict=False))


def _owning_functions(tree: ast.Module) -> dict[ast.AST, str]:
    """Each node mapped to the name of the innermost function holding it, or ``<module>``."""
    owners: dict[ast.AST, str] = {}
    stack: list[tuple[ast.AST, str]] = [(tree, "<module>")]
    while stack:
        node, owner = stack.pop()
        for child in ast.iter_child_nodes(node):
            name = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else owner
            owners[child] = name
            stack.append((child, name))
    return owners


def _installer_sites() -> tuple[dict[tuple[str, str], int], set[tuple[str, str]]]:
    """(file, owning function) -> first line of an installer argv; and guarded functions."""
    sites: dict[tuple[str, str], int] = {}
    guarded: set[tuple[str, str]] = set()
    for path in sorted(_PACKAGE.rglob("*.py")):
        rel = path.relative_to(_PACKAGE).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        owners = _owning_functions(tree)
        for node in ast.walk(tree):
            owner = owners.get(node, "<module>")
            if isinstance(node, (ast.List, ast.Tuple)) and _is_installer_argv(node):
                sites.setdefault((rel, owner), node.lineno)
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                if name in _GUARDS:
                    guarded.add((rel, owner))
    return sites, guarded


def test_every_installer_argv_in_the_package_is_guarded() -> None:
    sites, guarded = _installer_sites()
    # Not vacuous: the six behavioural entry points above live in these.
    assert len(sites) >= 5, sites
    unguarded = []
    for site, line in sites.items():
        if site in guarded:
            continue
        launcher = _BUILDERS.get(site)
        if launcher is not None and launcher in guarded:
            continue
        unguarded.append(f"bristlenose/{site[0]}:{line} in {site[1]}")
    assert not unguarded, (
        "installer argv with no refuse_install_when_hosted() in the function that "
        "launches it (App Store guideline 2.5.2):\n  " + "\n  ".join(unguarded)
    )
    # A builder entry that no longer builds an installer is stale.
    assert set(_BUILDERS) <= set(sites), set(_BUILDERS) - set(sites)
