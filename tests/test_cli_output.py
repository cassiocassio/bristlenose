"""Tests for CLI output formatting helpers and hardware label."""

from __future__ import annotations

import socket
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bristlenose.cli import (
    _COMMANDS,
    _find_open_port,
    _install_hint,
    _maybe_inject_run,
    _print_pipeline_summary,
)
from bristlenose.pipeline import _format_duration
from bristlenose.utils.hardware import AcceleratorType, HardwareInfo

# ---------------------------------------------------------------------------
# _maybe_inject_run (default command)
# ---------------------------------------------------------------------------


class TestMaybeInjectRun:
    def test_injects_run_for_directory(self, tmp_path: Path) -> None:
        """A bare directory argument gets 'run' injected."""
        test_dir = tmp_path / "interviews"
        test_dir.mkdir()
        with patch.object(sys, "argv", ["bristlenose", str(test_dir)]):
            _maybe_inject_run()
            assert sys.argv == ["bristlenose", "run", str(test_dir)]

    def test_no_injection_for_known_command(self, tmp_path: Path) -> None:
        """Known commands are not treated as directories."""
        # Even if a directory named 'doctor' exists, the command takes precedence
        (tmp_path / "doctor").mkdir()
        with patch.object(sys, "argv", ["bristlenose", "doctor"]):
            _maybe_inject_run()
            assert sys.argv == ["bristlenose", "doctor"]

    def test_no_injection_for_flags(self) -> None:
        """Flags like --version are passed through."""
        with patch.object(sys, "argv", ["bristlenose", "--version"]):
            _maybe_inject_run()
            assert sys.argv == ["bristlenose", "--version"]

    def test_no_injection_for_nonexistent_path(self) -> None:
        """Non-existent paths are passed through (let Typer handle the error)."""
        with patch.object(sys, "argv", ["bristlenose", "nonexistent-folder"]):
            _maybe_inject_run()
            assert sys.argv == ["bristlenose", "nonexistent-folder"]

    def test_no_injection_with_no_args(self) -> None:
        """No arguments means show help — don't inject anything."""
        with patch.object(sys, "argv", ["bristlenose"]):
            _maybe_inject_run()
            assert sys.argv == ["bristlenose"]

    def test_all_commands_in_set(self) -> None:
        """Sanity check: all expected commands are in _COMMANDS."""
        expected = {"run", "transcribe", "analyze", "analyse", "render", "doctor", "help", "configure", "serve", "status"}
        assert _COMMANDS == expected

# ---------------------------------------------------------------------------
# _format_duration
# ---------------------------------------------------------------------------


class TestFormatDuration:
    def test_sub_second(self) -> None:
        assert _format_duration(0.1) == "0.1s"

    def test_seconds(self) -> None:
        assert _format_duration(42.7) == "42.7s"

    def test_exactly_one_minute(self) -> None:
        assert _format_duration(60) == "1m 00s"

    def test_minutes_and_seconds(self) -> None:
        assert _format_duration(125) == "2m 05s"

    def test_large_duration(self) -> None:
        assert _format_duration(3599) == "59m 59s"

    def test_zero(self) -> None:
        assert _format_duration(0.0) == "0.0s"

    def test_just_under_one_minute(self) -> None:
        assert _format_duration(59.9) == "59.9s"


# ---------------------------------------------------------------------------
# HardwareInfo.label
# ---------------------------------------------------------------------------


class TestHardwareLabel:
    def test_apple_silicon_mlx(self) -> None:
        hw = HardwareInfo(
            accelerator=AcceleratorType.APPLE_SILICON,
            chip_name="Apple M2 Max",
            mlx_available=True,
        )
        assert hw.label == "Apple M2 Max · MLX"

    def test_apple_silicon_no_mlx(self) -> None:
        hw = HardwareInfo(
            accelerator=AcceleratorType.APPLE_SILICON,
            chip_name="Apple M1",
            mlx_available=False,
        )
        assert hw.label == "Apple M1 · CPU"

    def test_cuda(self) -> None:
        hw = HardwareInfo(
            accelerator=AcceleratorType.CUDA,
            chip_name="NVIDIA RTX 4090",
            cuda_available=True,
        )
        assert hw.label == "NVIDIA RTX 4090 · CUDA"

    def test_cpu_fallback(self) -> None:
        hw = HardwareInfo(accelerator=AcceleratorType.CPU)
        assert hw.label == "cpu · CPU"

    def test_cuda_no_chip_name(self) -> None:
        hw = HardwareInfo(
            accelerator=AcceleratorType.CUDA,
            cuda_available=True,
        )
        assert hw.label == "cuda · CUDA"

    def test_apple_silicon_no_chip_name(self) -> None:
        hw = HardwareInfo(
            accelerator=AcceleratorType.APPLE_SILICON,
            mlx_available=True,
        )
        assert hw.label == "apple_silicon · MLX"


# ---------------------------------------------------------------------------
# _install_hint (pip vs pipx detection)
# ---------------------------------------------------------------------------


class TestInstallHint:
    def test_pip_default(self) -> None:
        with patch("sys.prefix", "/usr/local"):
            assert _install_hint() == "pip install bristlenose[serve]"

    def test_pipx_detected(self) -> None:
        with patch("sys.prefix", "/home/user/.local/share/pipx/venvs/bristlenose"):
            assert _install_hint() == "pipx install bristlenose[serve]"

    def test_venv_without_pipx(self) -> None:
        with patch("sys.prefix", "/home/user/projects/bristlenose/.venv"):
            assert _install_hint() == "pip install bristlenose[serve]"


# ---------------------------------------------------------------------------
# _find_open_port
# ---------------------------------------------------------------------------


class TestFindOpenPort:
    def test_returns_first_available(self) -> None:
        """Should return a port in the expected range."""
        port = _find_open_port(start=18150, attempts=5)
        assert 18150 <= port <= 18154

    def test_skips_busy_port(self) -> None:
        """Should skip a port that's already bound."""
        # Bind a port to make it unavailable
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 18200))
            s.listen(1)
            port = _find_open_port(start=18200, attempts=5)
            assert port == 18201

    def test_raises_when_all_taken(self) -> None:
        """Should raise RuntimeError when all ports are taken."""
        sockets = []
        try:
            for p in range(18300, 18303):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(("127.0.0.1", p))
                s.listen(1)
                sockets.append(s)
            import pytest

            with pytest.raises(RuntimeError, match="No available port"):
                _find_open_port(start=18300, attempts=3)
        finally:
            for s in sockets:
                s.close()


# ---------------------------------------------------------------------------
# _print_pipeline_summary (serve_url, relative paths, doctor hint)
# ---------------------------------------------------------------------------


def _make_result(
    *,
    total_quotes: int = 10,
    llm_calls: int = 5,
    elapsed_seconds: float = 18.6,
    report_path: Path | None = None,
    pipeline_error: str = "",
    pipeline_error_link: str = "",
    pipeline_warning: str = "",
) -> SimpleNamespace:
    return SimpleNamespace(
        participants=["p1", "p2"],
        people=None,
        screen_clusters=["s1"],
        theme_groups=["t1"],
        total_quotes=total_quotes,
        llm_calls=llm_calls,
        llm_input_tokens=1000,
        llm_output_tokens=500,
        llm_model="test-model",
        llm_provider="anthropic",
        elapsed_seconds=elapsed_seconds,
        report_path=report_path,
        pipeline_error=pipeline_error,
        pipeline_error_link=pipeline_error_link,
        pipeline_warning=pipeline_warning,
    )


class TestPrintPipelineSummary:
    def test_serve_url_printed(self, capsys: object) -> None:
        """When serve_url is given, it appears in the output."""
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=120)
        with patch("bristlenose.cli.console", c):
            _print_pipeline_summary(
                _make_result(), serve_url="http://127.0.0.1:8150/report/"
            )
        output = buf.getvalue()
        assert "http://127.0.0.1:8150/report/" in output
        assert "Done" in output

    def test_no_serve_url_shows_file_path(self, tmp_path: Path) -> None:
        """Without serve_url, the file path is shown."""
        from io import StringIO

        from rich.console import Console

        report = tmp_path / "report.html"
        report.write_text("<html></html>")
        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=120)
        with patch("bristlenose.cli.console", c):
            _print_pipeline_summary(_make_result(report_path=report))
        output = buf.getvalue()
        assert "report.html" in output
        assert "http://" not in output

    def test_doctor_hint_on_zero_quotes(self) -> None:
        """0 quotes with LLM calls should suggest bristlenose doctor."""
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=120)
        with patch("bristlenose.cli.console", c):
            _print_pipeline_summary(_make_result(total_quotes=0))
        output = buf.getvalue()
        assert "bristlenose doctor" in output
        assert "Finished with errors" in output

    def test_no_doctor_hint_on_success(self) -> None:
        """Successful run should not mention doctor."""
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=120)
        with patch("bristlenose.cli.console", c):
            _print_pipeline_summary(_make_result(total_quotes=10))
        output = buf.getvalue()
        assert "doctor" not in output

    def test_pipeline_error_shows_root_cause(self) -> None:
        """When pipeline_error is set, the specific reason is shown."""
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=120)
        with patch("bristlenose.cli.console", c):
            _print_pipeline_summary(
                _make_result(
                    total_quotes=0,
                    pipeline_error="API credit balance too low",
                )
            )
        output = buf.getvalue()
        assert "API credit balance too low" in output
        assert "Finished with errors" in output
        # Should NOT show the generic fallback
        assert "check API credits or logs" not in output

    def test_pipeline_error_with_billing_link(self) -> None:
        """When pipeline_error_link is set, the billing URL is shown."""
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=120)
        with patch("bristlenose.cli.console", c):
            _print_pipeline_summary(
                _make_result(
                    total_quotes=0,
                    pipeline_error="API credit balance too low",
                    pipeline_error_link="https://platform.claude.com/settings/billing",
                )
            )
        output = buf.getvalue()
        assert "Billing" in output
        assert "platform.claude.com" in output

    def test_zero_quotes_no_error_shows_generic_message(self) -> None:
        """When 0 quotes but no pipeline_error, falls back to generic message."""
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=120)
        with patch("bristlenose.cli.console", c):
            _print_pipeline_summary(_make_result(total_quotes=0))
        output = buf.getvalue()
        assert "check API credits or logs" in output


# ---------------------------------------------------------------------------
# _print_error_step (red ✗ on failed stages)
# ---------------------------------------------------------------------------


class TestPrintErrorStep:
    def test_error_step_has_red_cross(self) -> None:
        """Error steps should show red ✗, not green ✓."""
        from io import StringIO

        from rich.console import Console

        from bristlenose.pipeline import _print_error_step

        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=80)
        with patch("bristlenose.pipeline.console", c):
            _print_error_step("Extracted 0 quotes", 8.1)
        output = buf.getvalue()
        assert "✗" in output
        assert "✓" not in output


# ---------------------------------------------------------------------------
# Doctor table FAIL icon
# ---------------------------------------------------------------------------


class TestDoctorTableIcons:
    def test_fail_uses_red_cross(self) -> None:
        """FAIL status should use red ✗, not yellow ⚠."""
        from io import StringIO

        from rich.console import Console

        from bristlenose.cli import _format_doctor_table
        from bristlenose.doctor import CheckResult, CheckStatus, DoctorReport

        report = DoctorReport(
            results=[CheckResult(status=CheckStatus.FAIL, label="API Key", detail="missing")]
        )
        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=80)
        with patch("bristlenose.cli.console", c):
            _format_doctor_table(report)
        output = buf.getvalue()
        assert "✗" in output
        # Should NOT use ⚠ for failures
        assert "⚠" not in output

    def test_warn_uses_yellow_triangle(self) -> None:
        """WARN status should use yellow ⚠."""
        from io import StringIO

        from rich.console import Console

        from bristlenose.cli import _format_doctor_table
        from bristlenose.doctor import CheckResult, CheckStatus, DoctorReport

        report = DoctorReport(
            results=[CheckResult(status=CheckStatus.WARN, label="FFmpeg", detail="old version")]
        )
        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=80)
        with patch("bristlenose.cli.console", c):
            _format_doctor_table(report)
        output = buf.getvalue()
        assert "⚠" in output


# ---------------------------------------------------------------------------
# _print_warn_step (yellow ⚠ on partially-succeeded stages)
# ---------------------------------------------------------------------------


class TestPrintWarnStep:
    def test_warn_step_has_yellow_triangle(self) -> None:
        """Partially-succeeded steps should show yellow ⚠, not ✓ or ✗."""
        from io import StringIO

        from rich.console import Console

        from bristlenose.pipeline import _print_warn_step

        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=80)
        with patch("bristlenose.pipeline.console", c):
            _print_warn_step("Extracted 5 quotes", 4.2)
        output = buf.getvalue()
        assert "⚠" in output
        assert "✓" not in output
        assert "✗" not in output
        assert "4." in output and "2s" in output


# ---------------------------------------------------------------------------
# "Done with warnings" summary state
# ---------------------------------------------------------------------------


class TestDoneWithWarnings:
    def test_partial_errors_show_done_with_warnings(self) -> None:
        """Partial success (quotes > 0 + warning) → 'Done with warnings'."""
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=120)
        with patch("bristlenose.cli.console", c):
            _print_pipeline_summary(
                _make_result(
                    total_quotes=5,
                    pipeline_warning="API credit balance too low",
                )
            )
        output = buf.getvalue()
        assert "Done with warnings" in output
        assert "API credit balance too low" in output
        # Should NOT show error state or doctor hint
        assert "Finished with errors" not in output
        assert "doctor" not in output

    def test_no_warning_shows_green_done(self) -> None:
        """Clean run (no warning, no error) → green 'Done'."""
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=120)
        with patch("bristlenose.cli.console", c):
            _print_pipeline_summary(_make_result(total_quotes=10))
        output = buf.getvalue()
        assert "Done" in output
        assert "warnings" not in output
        assert "errors" not in output
