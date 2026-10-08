"""FFmpeg and ffprobe on Windows are never run from the current directory.

A researcher unzips a client's "interviews" folder, cds into it, and runs
`bristlenose run .`. CPython's shutil.which on Windows looks in the current
directory before PATH and honours PATHEXT, and CreateProcess searches it for a
bare command name, so an ffmpeg.exe/.bat/.cmd planted there would run. These
tests fake that host: `windows_which` reproduces the lookup, so the old
behaviour is what they catch. Every subprocess call is recorded, never run.
"""

from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

import pytest

import bristlenose
from bristlenose.utils import bundled_binary

_NAMES = ("ffmpeg", "ffprobe")


@pytest.fixture
def shellouts(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def run(cmd, *a, **k):  # noqa: ANN001, ANN002, ANN003
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    return calls


@pytest.fixture
def hostile_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """A pipx/uv install on Windows, run from a folder holding ffmpeg/ffprobe."""
    cwd = tmp_path_factory.mktemp("interviews")
    for name in _NAMES:
        for ext in (".exe", ".bat", ".cmd"):
            (cwd / f"{name}{ext}").write_bytes(b"")
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setenv("PATH", "")
    for var in ("BRISTLENOSE_FFMPEG", "BRISTLENOSE_FFPROBE", "_BRISTLENOSE_HOSTED_BY_DESKTOP"):
        monkeypatch.delenv(var, raising=False)

    def windows_which(name: str) -> str | None:
        import os

        dirs = [str(cwd), *filter(None, os.environ.get("PATH", "").split(os.pathsep))]
        for d in dirs:
            for ext in ("", ".exe", ".bat", ".cmd"):
                if (Path(d) / f"{name}{ext}").is_file():
                    return str(Path(d) / f"{name}{ext}")
        return None

    monkeypatch.setattr("shutil.which", windows_which)
    return cwd


@pytest.fixture
def damaged_frozen(hostile_cwd: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """The winget build with tools\\ffmpeg.exe quarantined."""
    app = tmp_path / "Bristlenose"
    (app / "tools").mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(app / "bristlenose.exe"))
    return app


# --- resolution ---------------------------------------------------------------


@pytest.mark.parametrize("name", _NAMES)
def test_the_current_directory_is_not_searched(hostile_cwd: Path, name: str) -> None:
    assert bundled_binary.bundled_binary_path(name) is None
    with pytest.raises(FileNotFoundError):
        bundled_binary.binary_command(name)


def test_a_relative_path_entry_does_not_reach_the_current_directory(
    hostile_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    monkeypatch.setenv("PATH", os.pathsep.join([".", "", "sub"]))
    assert bundled_binary.bundled_binary_path("ffmpeg") is None


def test_an_ffmpeg_on_an_absolute_path_entry_is_found(
    hostile_cwd: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The other answer: a user-installed FFmpeg (winget, scoop) on PATH is used."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "ffmpeg.exe").write_bytes(b"")
    monkeypatch.setenv("PATH", str(bin_dir))
    assert bundled_binary.binary_command("ffmpeg") == str(bin_dir / "ffmpeg.exe")


def test_off_windows_a_missing_binary_keeps_its_bare_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """exec searches PATH only, so the bare name fails exactly as it always did."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("BRISTLENOSE_FFMPEG", raising=False)
    monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
    monkeypatch.setattr("shutil.which", lambda n: None)
    assert bundled_binary.binary_command("ffmpeg") == "ffmpeg"
    monkeypatch.setattr("shutil.which", lambda n: f"/usr/bin/{n}")
    assert bundled_binary.binary_command("ffmpeg") == "/usr/bin/ffmpeg"


# --- the call sites: nothing runs ---------------------------------------------


@pytest.fixture(params=["pipx", "frozen"])
def no_ffmpeg_host(request: pytest.FixtureRequest, hostile_cwd: Path) -> Path:
    if request.param == "frozen":
        request.getfixturevalue("damaged_frozen")
    return hostile_cwd


def _media(tmp_path: Path) -> Path:
    media = tmp_path / "session.mp4"
    media.write_bytes(b"\0" * 16)
    return media


def test_probe_runs_nothing(
    no_ffmpeg_host: Path, shellouts: list[list[str]], tmp_path: Path
) -> None:
    from bristlenose.utils.audio import probe_media

    assert probe_media(_media(tmp_path)) == (None, None)
    assert shellouts == []


def test_audio_stream_check_fails_loud_and_runs_nothing(
    no_ffmpeg_host: Path, shellouts: list[list[str]], tmp_path: Path
) -> None:
    from bristlenose.utils.audio import AudioToolError, has_audio_stream

    with pytest.raises(AudioToolError):
        has_audio_stream(_media(tmp_path))
    assert shellouts == []


def test_audio_extraction_runs_nothing(
    no_ffmpeg_host: Path, shellouts: list[list[str]], tmp_path: Path
) -> None:
    from bristlenose.utils.audio import extract_audio_from_video

    with pytest.raises(FileNotFoundError):
        extract_audio_from_video(_media(tmp_path), tmp_path / "out.wav")
    assert shellouts == []


def test_thumbnail_runs_nothing(
    no_ffmpeg_host: Path, shellouts: list[list[str]], tmp_path: Path
) -> None:
    from bristlenose.utils.video import extract_thumbnail

    assert extract_thumbnail(_media(tmp_path), tmp_path / "t.jpg", 1.0) is None
    assert shellouts == []


def test_scene_colours_run_nothing(
    no_ffmpeg_host: Path, shellouts: list[list[str]], tmp_path: Path
) -> None:
    from bristlenose.utils.scene_colour import sample_keyframes

    with pytest.raises(FileNotFoundError):
        sample_keyframes(_media(tmp_path))
    assert shellouts == []


def test_voice_decode_runs_nothing(
    no_ffmpeg_host: Path, shellouts: list[list[str]], tmp_path: Path
) -> None:
    from bristlenose.stages.s05b_voice import load_audio_16k

    with pytest.raises(FileNotFoundError):
        load_audio_16k(_media(tmp_path))
    assert shellouts == []


def test_clips_run_nothing(
    no_ffmpeg_host: Path, shellouts: list[list[str]], tmp_path: Path
) -> None:
    from bristlenose.server.clip_backend import FFmpegBackend

    backend = FFmpegBackend()
    media = _media(tmp_path)
    assert backend.extract_clip(media, tmp_path / "c.mp4", 0.0, 1.0) is None
    assert backend.burn_subtitles(media, [], tmp_path / "b.mp4") is None
    assert shellouts == []


def test_preflight_is_not_satisfied_by_the_current_directory(
    hostile_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rich.console import Console

    from bristlenose.preflight.ffmpeg import FfmpegPreflightAbortedError, preflight_ffmpeg

    monkeypatch.delenv("BRISTLENOSE_SKIP_PREFLIGHT", raising=False)
    with pytest.raises(FfmpegPreflightAbortedError):
        preflight_ffmpeg(
            console=Console(file=io.StringIO()),
            status=None,
            allow_install=False,
        )


# --- the gate -----------------------------------------------------------------


def test_no_call_site_falls_back_to_a_bare_ffmpeg_name() -> None:
    """`bundled_binary_path(x) or "x"` runs a cwd binary on Windows; use binary_command."""
    pkg = Path(bristlenose.__file__).parent
    offenders = [
        f"{path.relative_to(pkg)}:{n}"
        for path in pkg.rglob("*.py")
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r'\bor\s+"ff(mpeg|probe)"', line)
    ]
    assert offenders == [], f"use bundled_binary.binary_command: {offenders}"
