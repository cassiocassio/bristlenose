"""Regression tests: a run that exits before the pipeline starts must not
wall off the next run with "Output directory already exists".

The zero-config first-run trap (two-run sequence): `bristlenose run
interviews/` used to create `<input>/bristlenose-output/.bristlenose/` for
the log file *before* the provider gate fired, so the gated exit left
detritus and the post-configure second run failed with "Output directory
already exists ... Use --clean". Two defences, both pinned here:

- the provider gate runs before setup_logging, so a gated exit creates
  nothing on disk;
- the exists-check tolerates a log-only leftover (from a failed preflight
  or api-key abort, or from a bristlenose version that predates the
  reorder) instead of demanding --clean.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from bristlenose.cli import _is_leftover_log_only_output, app


@pytest.fixture()
def hermetic_cli(monkeypatch):
    """Make full-CLI invokes deterministic: no keychain reads, gate always fires.

    The real gate fires only when no provider resolves — an environment fact
    (env vars, config file, keychain) that differs between dev machines and
    CI. Stubbing the gate at its call site keeps the sequence under test
    (what exists on disk when the gate exits) without that dependence.
    """
    monkeypatch.setattr(
        "bristlenose.config._populate_keys_from_keychain", lambda s: s
    )

    def _gate_fires(settings: object) -> None:
        raise typer.Exit(0)

    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", _gate_fires)
    return CliRunner()


class TestZeroConfigTwoRunSequence:
    def test_gated_first_run_creates_nothing(self, hermetic_cli, tmp_path: Path) -> None:
        input_dir = tmp_path / "interviews"
        input_dir.mkdir()

        result = hermetic_cli.invoke(app, ["run", str(input_dir)])

        assert result.exit_code == 0
        assert not (input_dir / "bristlenose-output").exists()

    def test_second_run_is_not_blocked_by_the_first(self, hermetic_cli, tmp_path: Path) -> None:
        input_dir = tmp_path / "interviews"
        input_dir.mkdir()

        first = hermetic_cli.invoke(app, ["run", str(input_dir)])
        second = hermetic_cli.invoke(app, ["run", str(input_dir)])

        assert first.exit_code == 0
        assert second.exit_code == 0
        assert "already exists" not in second.output

    def test_leftover_log_only_output_does_not_block(self, hermetic_cli, tmp_path: Path) -> None:
        """A failed preflight / api-key abort leaves only .bristlenose/bristlenose.log."""
        input_dir = tmp_path / "interviews"
        state_dir = input_dir / "bristlenose-output" / ".bristlenose"
        state_dir.mkdir(parents=True)
        (state_dir / "bristlenose.log").write_text("log line\n")

        result = hermetic_cli.invoke(app, ["run", str(input_dir)])

        # Reaches the (stubbed) provider gate instead of the exists-check wall
        assert result.exit_code == 0
        assert "already exists" not in result.output

    def test_real_stale_output_still_demands_clean(self, hermetic_cli, tmp_path: Path) -> None:
        input_dir = tmp_path / "interviews"
        out_dir = input_dir / "bristlenose-output"
        out_dir.mkdir(parents=True)
        (out_dir / "themes.json").write_text("{}")

        result = hermetic_cli.invoke(app, ["run", str(input_dir)])

        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_analyze_gated_run_creates_nothing(self, hermetic_cli, tmp_path: Path) -> None:
        transcripts = tmp_path / "transcripts"
        transcripts.mkdir()

        result = hermetic_cli.invoke(app, ["analyze", str(transcripts)])

        assert result.exit_code == 0
        assert not (tmp_path / "bristlenose-output").exists()


class TestIsLeftoverLogOnlyOutput:
    def _output_with_state_dir(self, tmp_path: Path) -> Path:
        out = tmp_path / "bristlenose-output"
        (out / ".bristlenose").mkdir(parents=True)
        return out

    def test_log_and_rotations_are_tolerated(self, tmp_path: Path) -> None:
        out = self._output_with_state_dir(tmp_path)
        (out / ".bristlenose" / "bristlenose.log").write_text("x")
        (out / ".bristlenose" / "bristlenose.log.1").write_text("x")
        assert _is_leftover_log_only_output(out)

    def test_os_metadata_is_ignored(self, tmp_path: Path) -> None:
        out = self._output_with_state_dir(tmp_path)
        (out / ".DS_Store").write_bytes(b"\x00")
        (out / ".bristlenose" / "bristlenose.log").write_text("x")
        assert _is_leftover_log_only_output(out)

    def test_pipeline_state_blocks(self, tmp_path: Path) -> None:
        out = self._output_with_state_dir(tmp_path)
        (out / ".bristlenose" / "pipeline-events.jsonl").write_text("{}\n")
        assert not _is_leftover_log_only_output(out)

    def test_user_visible_content_blocks(self, tmp_path: Path) -> None:
        out = self._output_with_state_dir(tmp_path)
        (out / "themes.json").write_text("{}")
        assert not _is_leftover_log_only_output(out)
