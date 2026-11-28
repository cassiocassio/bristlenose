"""A ``uv tool install`` has no pip, and nothing at run time may assume one.

uv builds its environments without pip (checked on uv 0.10.11: ``python -m pip``
in a fresh ``uv venv`` is "No module named pip"). Two run-time installs used to
shell out to it:

* PII redaction's first run, through ``spacy download``. With no pip, spaCy
  falls back to ``uv pip install``, which targets the virtualenv the working
  folder sits in, not this one: "No virtual environment found", or 400 MB into
  an unrelated ``.venv`` above the project folder.
* ``doctor --fix`` for MLX on Apple silicon, through ``python -m pip``.

And the doctor hints gave a uv user pip and pipx commands. Design:
``docs/design-uv-install-route.md`` §3.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bristlenose import doctor_fixes
from bristlenose.stages import s07_pii_removal as s07
from bristlenose.utils import install_channel

_UV_PREFIX = "/home/r/.local/share/uv/tools/bristlenose"


@pytest.fixture
def no_pip(monkeypatch: pytest.MonkeyPatch) -> None:
    """This Python is a uv tool env: no pip, not frozen, not a package."""
    monkeypatch.setattr(install_channel, "pip_available", lambda: False)
    monkeypatch.setattr(doctor_fixes, "detect_install_method", lambda: "pip")
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)


@pytest.fixture
def uv_channel(monkeypatch: pytest.MonkeyPatch, no_pip: None) -> None:
    monkeypatch.setattr(sys, "prefix", _UV_PREFIX)


# ---------------------------------------------------------------------------
# PII model: a pip-less install takes the user-cache fetch, never `spacy download`
# ---------------------------------------------------------------------------


def test_a_pip_less_install_needs_the_user_cache(no_pip: None) -> None:
    assert s07.spacy_model_needs_user_cache() is True


def test_an_install_with_pip_keeps_spacy_download(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(install_channel, "pip_available", lambda: True)
    monkeypatch.setattr(doctor_fixes, "detect_install_method", lambda: "pip")
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
    assert s07.spacy_model_needs_user_cache() is False


@pytest.mark.parametrize("frozen_by", ["sys.frozen", "desktop sentinel"])
def test_a_frozen_build_keeps_its_own_answer(
    frozen_by: str, no_pip: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Mac app ships the model and the winget build says PII isn't in it;
    neither has pip, and neither may start a 400 MB download from GitHub."""
    if frozen_by == "sys.frozen":
        monkeypatch.setattr(sys, "frozen", True, raising=False)
    else:
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")
    assert s07.spacy_model_needs_user_cache() is False


def test_first_redact_pii_run_on_uv_fetches_into_the_cache(
    no_pip: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The outcome, through the real route: no subprocess, the fetch, then a load."""
    monkeypatch.delenv(s07.PII_MODEL_DIR_ENV, raising=False)
    monkeypatch.setattr(s07, "cached_spacy_model", lambda: None)
    cached = Path("/cache/en_core_web_lg-3.8.0")
    fetched: list[int] = []
    monkeypatch.setattr(s07, "fetch_spacy_model", lambda **k: fetched.append(1) or cached)
    fake_spacy = MagicMock()
    fake_spacy.load.side_effect = [OSError("not found"), MagicMock()]
    with patch.dict(sys.modules, {"spacy": fake_spacy}), \
            patch("bristlenose.utils.package_install.ensure_spacy_model") as installer, \
            patch("subprocess.run") as run:
        s07._ensure_spacy_model()
    installer.assert_not_called()
    run.assert_not_called()
    assert fetched == [1]
    fake_spacy.load.assert_called_with(str(cached))


def test_the_spacy_hint_on_uv_names_the_cache_not_pip(
    no_pip: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    fix = doctor_fixes.get_fix("spacy_model_missing", "pip")
    assert "on the first --redact-pii run" in fix
    assert "spacy download" not in fix and "pip" not in fix


# ---------------------------------------------------------------------------
# MLX: `doctor --fix` installs with uv where there is no pip
# ---------------------------------------------------------------------------


def test_mlx_fix_on_uv_installs_into_this_python_with_uv(
    no_pip: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/uv" if name == "uv" else None)
    ran: list[list[str]] = []
    monkeypatch.setattr("subprocess.run", lambda cmd, **k: ran.append(cmd) or MagicMock(returncode=0))
    assert doctor_fixes.install_mlx() is True
    assert ran == [[
        "/usr/local/bin/uv", "pip", "install", "--python", sys.executable, "mlx", "mlx-whisper",
    ]]
    _cmd, display = doctor_fixes.get_mlx_install_command()
    assert display.startswith("uv pip install --python ")


def test_mlx_fix_with_pip_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(install_channel, "pip_available", lambda: True)
    cmd, _display = doctor_fixes.get_mlx_install_command()
    assert cmd == [sys.executable, "-m", "pip", "install", "mlx", "mlx-whisper"]


def test_the_mlx_hint_on_uv_adds_the_apple_extra(
    uv_channel: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(install_channel, "installed_extras", lambda: ["voice"])
    fix = doctor_fixes.get_fix("mlx_not_installed", "pip")
    assert 'uv tool install --force "bristlenose[apple,voice]"' in fix
    assert "pipx" not in fix and "pip install" not in fix


def test_a_later_extra_keeps_apple(uv_channel: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """`uv tool install --force` rebuilds from what it names, so a voice hint
    given after MLX was added must name apple too, or it takes MLX away."""
    real = install_channel._importable
    monkeypatch.setattr(
        install_channel, "_importable", lambda name: name == "mlx_whisper" or real(name)
    )
    assert "apple" in install_channel.installed_extras()
    assert "apple" in install_channel.add_extra_command("voice")


# ---------------------------------------------------------------------------
# Presidio: a core dependency missing from a uv env means rebuild, not inject
# ---------------------------------------------------------------------------


def test_the_presidio_hint_on_uv_rebuilds_the_install(uv_channel: None) -> None:
    fix = doctor_fixes.get_fix("presidio_missing", "pip")
    assert "uv tool install --reinstall bristlenose" in fix
    assert "pipx" not in fix


# ---------------------------------------------------------------------------
# The other "install this extra" hints follow the install channel too
# ---------------------------------------------------------------------------


def test_the_transcription_backend_hint_on_uv_rebuilds(uv_channel: None) -> None:
    fix = doctor_fixes.get_fix("backend_import_fail", "pip")
    assert "uv tool install --reinstall bristlenose" in fix
    assert "pipx" not in fix


def test_the_apple_silicon_log_names_the_channel_command(
    uv_channel: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from bristlenose.stages import s05_transcribe
    from bristlenose.utils.hardware import AcceleratorType

    monkeypatch.setattr(install_channel, "installed_extras", list)
    hw = MagicMock(accelerator=AcceleratorType.APPLE_SILICON, mlx_available=False)
    with caplog.at_level("INFO"):
        s05_transcribe._resolve_backend("auto", hw)
    assert 'uv tool install --force "bristlenose[apple]"' in caplog.text
    assert "pip install" not in caplog.text


def test_the_mcp_unavailable_line_on_uv(
    uv_channel: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from bristlenose.cli import _print_mcp_connect

    monkeypatch.setitem(sys.modules, "mcp", None)
    monkeypatch.setattr(install_channel, "installed_extras", list)
    _print_mcp_connect(8150)
    out = capsys.readouterr().out
    assert 'uv tool install --force "bristlenose[mcp]"' in out


# ---------------------------------------------------------------------------
# The channel is read from the tool's own marker, wherever the env lives
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("marker", "channel"), [("uv-receipt.toml", "uv"), ("pipx_metadata.json", "pipx")]
)
def test_a_moved_tool_dir_is_still_recognised(
    marker: str, channel: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UV_TOOL_DIR or PIPX_HOME can put the env anywhere; on 28 Nov 2026 a uv
    install under a custom UV_TOOL_DIR was told to `pip install` its extras."""
    env = tmp_path / "my-tools" / "bristlenose"
    env.mkdir(parents=True)
    (env / marker).write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "prefix", str(env))
    monkeypatch.setattr(install_channel, "installed_extras", list)
    assert install_channel.install_channel() == channel
    assert install_channel.add_extra_command("voice").startswith(channel)
    fix = doctor_fixes.get_fix("serve_deps_missing", "pip")
    assert ("reinstall" in fix) and (channel in fix)


def test_every_uv_rebuild_names_the_running_python(
    uv_channel: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`uv tool install --force` picks a Python again unless told. On an Intel
    Mac (28 Nov 2026) a working 3.12 install was rebuilt on 3.14, which has no
    onnxruntime wheel there. Every rebuild we suggest names the running one."""
    monkeypatch.setattr(sys, "version_info", (3, 12, 16, "final", 0))
    monkeypatch.setattr(install_channel, "installed_extras", list)
    for command in (
        install_channel.add_extra_command("voice"),
        install_channel.inject_command("any-llm-sdk[cohere]==1.44.0"),
        doctor_fixes.get_fix("serve_deps_missing", "pip"),
        doctor_fixes.get_fix("presidio_missing", "pip"),
        doctor_fixes.get_fix("backend_import_fail", "pip"),
    ):
        assert "--python 3.12" in command, command


def test_windows_on_arm_names_the_x64_python(
    uv_channel: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On the Windows 11 Arm VM (28 Nov 2026) an Arm64 uv asked for "3.13" chose an
    Arm64 Python, which has no ctranslate2 wheel; the x64 one installs and runs."""
    import platform

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "version_info", (3, 13, 18, "final", 0))
    monkeypatch.setattr(sys, "version", "3.13.18 (main) [MSC v.1944 64 bit (AMD64)]")
    monkeypatch.setattr(platform, "machine", lambda: "ARM64")
    monkeypatch.setattr(install_channel, "installed_extras", list)
    assert install_channel.uv_python_flag() == "--python cpython-3.13-windows-x86_64-none"
    assert install_channel.add_extra_command("voice").endswith(
        "--python cpython-3.13-windows-x86_64-none"
    )
    monkeypatch.setattr(platform, "machine", lambda: "AMD64")  # an x64 PC
    assert install_channel.uv_python_flag() == "--python 3.13"


def test_the_windows_one_liner_asks_for_x64_python_on_arm() -> None:
    """The one-liner's install line must use the Arm-aware request, not the bare version."""
    from pathlib import Path

    script = (Path(__file__).resolve().parent.parent / "scripts" / "windows" / "install.ps1").read_text(
        encoding="utf-8"
    )
    assert "& uv tool install --python $PythonRequest $spec" in script
    assert "Architecture -eq 12" in script
    assert '"cpython-$PythonVersion-windows-x86_64-none"' in script
