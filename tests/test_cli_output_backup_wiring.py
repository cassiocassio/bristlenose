"""The `run` command must not destroy a report it cannot replace.

`tests/test_output_backup.py` proves `stash`/`restore`/`discard` are individually
correct. This file proves `cli.py` *calls them in the right order*, which is a
separate claim and the one with teeth: the decision lives in a `finally` block
with four exit paths, and a flipped boolean there does not merely fail to
restore on a crash — it restores the OLD report over a freshly-succeeded new
one. That is the same data loss as the incident
(`docs/sidecar-transcription-crash.md`), pointing the other way.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bristlenose.cli import app
from bristlenose.utils import output_backup

_MARKER = "bristlenose-report.html"


class _Result:
    """The minimum `run` reads off a pipeline result after a clean run."""

    llm_model = "claude-sonnet-4-6"
    llm_input_tokens = 0
    llm_output_tokens = 0
    llm_calls = 1
    total_quotes = 3
    summary: dict = {}


def _seed_report(out_dir: Path, marker: str) -> None:
    """A prior run's output: a deliverable, a database, and a terminus event."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / _MARKER).write_text(marker, encoding="utf-8")
    state = out_dir / ".bristlenose"
    state.mkdir(exist_ok=True)
    (state / "bristlenose.db").write_text(f"db:{marker}", encoding="utf-8")
    (state / "pipeline-events.jsonl").write_text(
        json.dumps({"event": "run_completed", "run_id": "old"}) + "\n", encoding="utf-8"
    )


@pytest.fixture
def cli_to_pipeline(monkeypatch):
    """Reach the pipeline: no keychain, no preflight, no api-key call.

    Deliberately does NOT stub the provider gate the way `hermetic_cli` does —
    that fixture exits before the pipeline, which is exactly the region under
    test here.
    """
    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", lambda s: None)
    # True means "doctor handled it" — skips _run_preflight.
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    monkeypatch.setattr(
        "bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None
    )
    return CliRunner()


def _run(runner: CliRunner, input_dir: Path):
    # --no-serve: the pipeline runs, the summary prints, and nothing binds a port.
    return runner.invoke(app, ["run", str(input_dir), "--clean", "--no-serve"])


class TestTheReportSurvivesAFailedRun:
    def test_a_crashing_pipeline_leaves_the_previous_report_intact(
        self, cli_to_pipeline, tmp_path: Path, monkeypatch
    ) -> None:
        """The incident, reproduced at the wiring level.

        Two runs on 30 Aug 2026 cleaned their output directory and died seconds
        later inside transcription. Before this wiring the report was simply
        gone.
        """
        input_dir = tmp_path / "interviews"
        out_dir = input_dir / "bristlenose-output"
        _seed_report(out_dir, "good")

        async def _boom(*a, **k):
            raise RuntimeError("transcription died")

        monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _boom)

        _run(cli_to_pipeline, input_dir)

        assert (out_dir / _MARKER).read_text() == "good"
        assert (out_dir / ".bristlenose" / "bristlenose.db").read_text() == "db:good"

    def test_the_failure_is_still_visible_after_the_restore(
        self, cli_to_pipeline, tmp_path: Path, monkeypatch
    ) -> None:
        """Restoring the old events file would make a failed run read as fine.

        The app decides project state from this file's tail. The restore
        concatenates instead, so the report comes back AND the run still failed.
        """
        input_dir = tmp_path / "interviews"
        out_dir = input_dir / "bristlenose-output"
        _seed_report(out_dir, "good")

        async def _boom(*a, **k):
            raise RuntimeError("transcription died")

        monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _boom)

        _run(cli_to_pipeline, input_dir)

        events = (out_dir / ".bristlenose" / "pipeline-events.jsonl").read_text()
        lines = [json.loads(ln) for ln in events.splitlines() if ln.strip()]
        assert lines[0]["run_id"] == "old", "the old history should survive"
        assert lines[-1]["event"] != "run_completed", (
            "the tail must not say the run completed — the run failed"
        )

    def test_an_interrupt_is_not_a_reason_to_lose_the_report(
        self, cli_to_pipeline, tmp_path: Path, monkeypatch
    ) -> None:
        """Ctrl-C is the likeliest early end, and it is not an `Exception`."""
        input_dir = tmp_path / "interviews"
        out_dir = input_dir / "bristlenose-output"
        _seed_report(out_dir, "good")

        async def _interrupt(*a, **k):
            raise KeyboardInterrupt

        monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _interrupt)

        _run(cli_to_pipeline, input_dir)

        assert (out_dir / _MARKER).read_text() == "good"


class TestTheNewReportSurvivesASuccessfulRun:
    def test_a_successful_run_is_not_overwritten_by_the_backup(
        self, cli_to_pipeline, tmp_path: Path, monkeypatch
    ) -> None:
        """THE MIRROR-IMAGE BUG.

        A flipped boolean in the `finally` restores the stash over a run that
        just succeeded — losing the new report instead of the old one. Unit
        tests of `output_backup` cannot see this; only the wiring can.
        """
        input_dir = tmp_path / "interviews"
        out_dir = input_dir / "bristlenose-output"
        _seed_report(out_dir, "old")

        async def _succeed(_self, _in, out, *a, **k):
            _seed_report(Path(out), "new")
            return _Result()

        monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _succeed)

        _run(cli_to_pipeline, input_dir)

        assert (out_dir / _MARKER).read_text() == "new", (
            "the successful run's report must be the one on disk"
        )

    def test_a_successful_run_leaves_no_backup_behind(
        self, cli_to_pipeline, tmp_path: Path, monkeypatch
    ) -> None:
        """A backup that outlives its run is a stale report the next run
        would 'recover' over a good one."""
        input_dir = tmp_path / "interviews"
        out_dir = input_dir / "bristlenose-output"
        _seed_report(out_dir, "old")

        async def _succeed(_self, _in, out, *a, **k):
            _seed_report(Path(out), "new")
            return _Result()

        monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _succeed)

        _run(cli_to_pipeline, input_dir)

        assert not output_backup.backup_path_for(out_dir).exists()


class TestCrashRecovery:
    def test_a_backup_left_by_a_hard_crash_is_reclaimed_on_the_next_run(
        self, cli_to_pipeline, tmp_path: Path, monkeypatch
    ) -> None:
        """A SIGILL runs no handler, so the in-process restore never fires.

        `reclaim_stale` at the top of the next run is the only thing between a
        signalled death and a lost report — which is precisely how the report
        was lost, since the crash that started all this was a SIGILL.
        """
        input_dir = tmp_path / "interviews"
        out_dir = input_dir / "bristlenose-output"
        # What the dead run left: a stash holding the good report, and a
        # half-written output directory.
        _seed_report(output_backup.backup_path_for(out_dir), "good")
        _seed_report(out_dir, "half-written")

        async def _boom(*a, **k):
            raise RuntimeError("and it died again")

        monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _boom)

        _run(cli_to_pipeline, input_dir)

        assert (out_dir / _MARKER).read_text() == "good"

    def test_recovery_happens_before_the_directory_is_inspected(
        self, cli_to_pipeline, tmp_path: Path, monkeypatch
    ) -> None:
        """Ordering, not behaviour.

        `output_exists` is computed once, early, and drives whether the run
        cleans at all. Recovering a backup after that probe leaves the restored
        report in place UNCLEANED, so the new run writes over a mix of both.
        """
        input_dir = tmp_path / "interviews"
        out_dir = input_dir / "bristlenose-output"
        _seed_report(output_backup.backup_path_for(out_dir), "good")
        # No output directory at all — the dead run's was never recreated.

        seen: dict[str, bool] = {}

        async def _record(_self, _in, out, *a, **k):
            # By the time the pipeline runs, the recovered report must have been
            # stashed away like any other — not still sitting in the output dir.
            seen["stale_marker_present"] = (Path(out) / _MARKER).exists()
            _seed_report(Path(out), "new")
            return _Result()

        monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _record)

        _run(cli_to_pipeline, input_dir)

        assert seen.get("stale_marker_present") is False, (
            "the recovered report was not cleaned before the run — reclaim_stale "
            "must precede the output_exists probe"
        )
        assert (out_dir / _MARKER).read_text() == "new"
