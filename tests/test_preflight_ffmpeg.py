"""Tests for bristlenose.preflight.ffmpeg."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from bristlenose.preflight.ffmpeg import (
    FfmpegPreflightAbortedError,
    _detect_distro,
    _install_table,
    preflight_ffmpeg,
)


def _silent_console() -> Console:
    return Console(force_terminal=False, no_color=True, width=80)


# ---------------------------------------------------------------------------
# _detect_distro
# ---------------------------------------------------------------------------


class TestDetectDistro:
    def test_macos_via_sys_platform(self):
        with patch("bristlenose.preflight.ffmpeg.sys.platform", "darwin"):
            assert _detect_distro() == "macos"

    def test_ubuntu_id(self, tmp_path):
        release = tmp_path / "os-release"
        release.write_text('ID=ubuntu\nID_LIKE=debian\n')
        with patch("bristlenose.preflight.ffmpeg.sys.platform", "linux"):
            with patch("bristlenose.preflight.ffmpeg.Path") as path_cls:
                path_cls.return_value = release
                assert _detect_distro() == "ubuntu"

    def test_fedora_id(self, tmp_path):
        release = tmp_path / "os-release"
        release.write_text('ID=fedora\n')
        with patch("bristlenose.preflight.ffmpeg.sys.platform", "linux"):
            with patch("bristlenose.preflight.ffmpeg.Path") as path_cls:
                path_cls.return_value = release
                assert _detect_distro() == "fedora"

    def test_arch_via_id_like(self, tmp_path):
        release = tmp_path / "os-release"
        release.write_text('ID=manjaro\nID_LIKE="arch"\n')
        with patch("bristlenose.preflight.ffmpeg.sys.platform", "linux"):
            with patch("bristlenose.preflight.ffmpeg.Path") as path_cls:
                path_cls.return_value = release
                assert _detect_distro() == "arch"

    def test_missing_os_release_falls_back_to_other(self):
        with patch("bristlenose.preflight.ffmpeg.sys.platform", "linux"):
            with patch("bristlenose.preflight.ffmpeg.Path") as path_cls:
                path_cls.return_value.read_text.side_effect = OSError("nope")
                assert _detect_distro() == "other"


# ---------------------------------------------------------------------------
# _install_table
# ---------------------------------------------------------------------------


class TestInstallTable:
    def test_matching_distro_is_first(self):
        table = _install_table("fedora")
        lines = [line for line in table.splitlines() if line.strip()]
        assert "Fedora" in lines[0]

    def test_other_distros_still_listed(self):
        table = _install_table("ubuntu")
        assert "macOS" in table
        assert "Fedora" in table
        assert "Arch" in table
        assert "ffmpeg.org" in table


# ---------------------------------------------------------------------------
# preflight_ffmpeg orchestration
# ---------------------------------------------------------------------------


class TestPreflightFfmpeg:
    def test_present_path_is_silent(self, capsys):
        console = _silent_console()
        with patch(
            "bristlenose.preflight.ffmpeg.shutil.which", return_value="/usr/bin/ffmpeg"
        ):
            preflight_ffmpeg(console=console, status=None, allow_install=True)
        assert "ffmpeg is required" not in capsys.readouterr().out

    def test_missing_non_macos_prints_table_and_raises(self, capsys):
        console = _silent_console()
        with patch("bristlenose.preflight.ffmpeg.shutil.which", return_value=None):
            with patch(
                "bristlenose.preflight.ffmpeg._detect_distro", return_value="ubuntu"
            ):
                with pytest.raises(FfmpegPreflightAbortedError):
                    preflight_ffmpeg(
                        console=console, status=None, allow_install=True,
                    )
        out = capsys.readouterr().out
        assert "ffmpeg is required" in out
        assert "apt install ffmpeg" in out

    def test_macos_with_brew_writable_and_yes_runs_brew(self, capsys):
        console = _silent_console()
        with patch("bristlenose.preflight.ffmpeg.shutil.which") as which:
            # Initial probe → missing; post-install probe → found.
            which.side_effect = [None, "/opt/homebrew/bin/ffmpeg"]
            with patch(
                "bristlenose.preflight.ffmpeg._detect_distro", return_value="macos"
            ):
                with patch(
                    "bristlenose.preflight.ffmpeg._brew_writable_prefix",
                    return_value="/opt/homebrew",
                ):
                    with patch(
                        "bristlenose.preflight.ffmpeg._confirm_brew_install",
                        return_value=True,
                    ):
                        with patch(
                            "bristlenose.preflight.ffmpeg.subprocess.run"
                        ) as run:
                            preflight_ffmpeg(
                                console=console,
                                status=None,
                                allow_install=True,
                            )
        run.assert_called_once_with(["brew", "install", "ffmpeg"], check=True)
        out = capsys.readouterr().out
        assert "ffmpeg installed" in out

    def test_macos_brew_declined_raises(self):
        console = _silent_console()
        with patch("bristlenose.preflight.ffmpeg.shutil.which", return_value=None):
            with patch(
                "bristlenose.preflight.ffmpeg._detect_distro", return_value="macos"
            ):
                with patch(
                    "bristlenose.preflight.ffmpeg._brew_writable_prefix",
                    return_value="/opt/homebrew",
                ):
                    with patch(
                        "bristlenose.preflight.ffmpeg._confirm_brew_install",
                        return_value=False,
                    ):
                        with pytest.raises(FfmpegPreflightAbortedError):
                            preflight_ffmpeg(
                                console=console,
                                status=None,
                                allow_install=True,
                            )

    def test_no_fetch_blocks_auto_install_offer(self):
        console = _silent_console()
        with patch("bristlenose.preflight.ffmpeg.shutil.which", return_value=None):
            with patch(
                "bristlenose.preflight.ffmpeg._detect_distro", return_value="macos"
            ):
                with patch(
                    "bristlenose.preflight.ffmpeg._brew_writable_prefix",
                    return_value="/opt/homebrew",
                ):
                    with patch(
                        "bristlenose.preflight.ffmpeg._confirm_brew_install"
                    ) as confirm:
                        with pytest.raises(FfmpegPreflightAbortedError):
                            preflight_ffmpeg(
                                console=console,
                                status=None,
                                allow_install=False,
                            )
        confirm.assert_not_called()

    def test_macos_brew_unwritable_skips_offer(self):
        console = _silent_console()
        with patch("bristlenose.preflight.ffmpeg.shutil.which", return_value=None):
            with patch(
                "bristlenose.preflight.ffmpeg._detect_distro", return_value="macos"
            ):
                with patch(
                    "bristlenose.preflight.ffmpeg._brew_writable_prefix",
                    return_value=None,
                ):
                    with patch(
                        "bristlenose.preflight.ffmpeg._confirm_brew_install"
                    ) as confirm:
                        with pytest.raises(FfmpegPreflightAbortedError):
                            preflight_ffmpeg(
                                console=console,
                                status=None,
                                allow_install=True,
                            )
        confirm.assert_not_called()

    def test_status_stop_start_around_brew(self):
        console = _silent_console()
        status = MagicMock()
        with patch("bristlenose.preflight.ffmpeg.shutil.which") as which:
            which.side_effect = [None, "/opt/homebrew/bin/ffmpeg"]
            with patch(
                "bristlenose.preflight.ffmpeg._detect_distro", return_value="macos"
            ):
                with patch(
                    "bristlenose.preflight.ffmpeg._brew_writable_prefix",
                    return_value="/opt/homebrew",
                ):
                    with patch(
                        "bristlenose.preflight.ffmpeg._confirm_brew_install",
                        return_value=True,
                    ):
                        with patch(
                            "bristlenose.preflight.ffmpeg.subprocess.run"
                        ):
                            preflight_ffmpeg(
                                console=console,
                                status=status,
                                allow_install=True,
                            )
        status.stop.assert_called_once()
        status.start.assert_called_once()
