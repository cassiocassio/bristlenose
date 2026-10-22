"""A Re-analyse replaces the report only when it finishes (R108, R109).

`run --clean` with 9 of 10 sessions failed and 4 quotes back (353 before) used
to discard the previous report, its database and curation included, because
`cli.py` counted any quote as a replacement (R108). And a Re-analyse that did
not finish kept its paid work in `.bristlenose-output-failed`, which nothing
read back: the only real retry was another `--clean`, which swept it and paid
for every session again (R109).

Ruled 22 Oct 2026: when any session failed in transcripts, topics, quotes or
themes, the previous report comes back as it does for a failed run, and the
attempt is kept aside. The next run without `--clean` picks the attempt up and
pays only for what is missing; once it completes, it replaces the report. Files
declined at ingest (a stray PDF) are not an unfinished analysis.

Drives the real CLI with a stubbed `Pipeline.run`, as
`tests/test_cli_output_backup_wiring.py` does.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bristlenose.cli import app
from bristlenose.events import (
    Cause,
    CauseCategoryEnum,
    PipelineSummary,
    StageFailure,
    StageOutcome,
)
from bristlenose.utils import output_backup

_MARKER = "bristlenose-report.html"
_KEPT_LINE = "Your previous report is still here, because some sessions failed."


def _failures(n: int, category=CauseCategoryEnum.NETWORK) -> list[StageFailure]:
    return [
        StageFailure(session_id=f"s{i}", cause=Cause(category=category, message="failed"))
        for i in range(2, 2 + n)
    ]


def _summary(*, failed_sessions: int, bucket: str = "quotes",
             category=CauseCategoryEnum.NETWORK) -> PipelineSummary:
    outcome = StageOutcome(
        attempted=1 + failed_sessions, succeeded=1,
        failed=_failures(failed_sessions, category),
    )
    return PipelineSummary(**{bucket: outcome})


class _Result:
    llm_model = "claude-sonnet-4-6"
    llm_input_tokens = 0
    llm_output_tokens = 0
    llm_calls = 10

    def __init__(self, *, total_quotes: int, summary: PipelineSummary) -> None:
        self.total_quotes = total_quotes
        self.summary = summary


def _seed_report(out_dir: Path, marker: str) -> None:
    """A run's output: a deliverable, a database, a manifest and a terminus."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / _MARKER).write_text(marker, encoding="utf-8")
    state = out_dir / ".bristlenose"
    state.mkdir(exist_ok=True)
    (state / "bristlenose.db").write_text(f"db:{marker}", encoding="utf-8")
    (state / "pipeline-manifest.json").write_text("{}", encoding="utf-8")
    with (state / "pipeline-events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event": "run_completed", "run_id": marker}) + "\n")


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", lambda s: None)
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None)
    return CliRunner()


def _pipeline_returns(
    monkeypatch, marker: str, *, quotes: int, failed_sessions: int, **summary_kw
) -> dict[str, object]:
    """Stub the run. Records which tree the run started on: the marker of the
    report in the output folder, or None when `--clean` set it aside."""
    seen: dict[str, object] = {}

    async def _run(_self, _in, out, *a, **k):
        found = Path(out) / _MARKER
        seen["started_on"] = found.read_text(encoding="utf-8") if found.exists() else None
        _seed_report(Path(out), marker)
        return _Result(
            total_quotes=quotes,
            summary=_summary(failed_sessions=failed_sessions, **summary_kw),
        )

    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _run)
    return seen


def _pipeline_raises(monkeypatch, marker: str) -> None:
    async def _run(_self, _in, out, *a, **k):
        _seed_report(Path(out), marker)
        raise RuntimeError("provider went away")

    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _run)


def _invoke(runner: CliRunner, input_dir: Path, *, clean: bool):
    args = ["run", str(input_dir), "--no-serve"] + (["--clean"] if clean else [])
    return runner.invoke(app, args)


def _reanalyse(runner: CliRunner, input_dir: Path, seen: dict[str, object]):
    """Run `--clean` and assert it really set the old report aside, so a
    verdict below is about the outcome and never about a refused stash."""
    result = _invoke(runner, input_dir, clean=True)
    if result.exit_code != 0 or "Could not set" in result.output:
        pytest.fail(f"the run did not complete cleanly:\n{result.output}")
    if seen.get("started_on") is not None:
        pytest.fail("the old report was not set aside before the run")
    return result


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    input_dir = tmp_path / "interviews"
    out_dir = input_dir / "bristlenose-output"
    return input_dir, out_dir, output_backup.failed_path_for(out_dir)


class TestAnUnfinishedReanalyseKeepsThePreviousReport:
    def test_the_previous_report_and_its_database_come_back(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        """The reproduction: 9 of 10 sessions failed, 4 quotes back."""
        input_dir, out_dir, failed = _paths(tmp_path)
        _seed_report(out_dir, "good")
        seen = _pipeline_returns(monkeypatch, "degraded", quotes=4, failed_sessions=9)

        result = _reanalyse(runner, input_dir, seen)

        assert _read(out_dir / _MARKER) == "good"
        assert _read(out_dir / ".bristlenose" / "bristlenose.db") == "db:good"
        assert not output_backup.backup_path_for(out_dir).exists()
        # The attempt is kept, to be finished.
        assert _read(failed / _MARKER) == "degraded"
        assert _KEPT_LINE in result.output
        # The run's history rides on the restored report, so the row reads partial.
        events = _read(out_dir / ".bristlenose" / "pipeline-events.jsonl")
        tail = json.loads(events.strip().splitlines()[-1])
        assert tail["event"] == "run_completed"
        assert len(tail["summary"]["quotes"]["failed"]) == 9

    def test_a_transcription_failure_counts_too(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        input_dir, out_dir, failed = _paths(tmp_path)
        _seed_report(out_dir, "good")
        seen = _pipeline_returns(
            monkeypatch, "degraded", quotes=300, failed_sessions=1,
            bucket="transcripts", category=CauseCategoryEnum.CLOUD_FETCH,
        )

        _reanalyse(runner, input_dir, seen)

        assert _read(out_dir / _MARKER) == "good"
        assert _read(failed / _MARKER) == "degraded"

    def test_a_file_declined_at_ingest_does_not_hold_the_report_back(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        """A stray PDF is in `ingest.failed`; the analysis itself finished."""
        input_dir, out_dir, failed = _paths(tmp_path)
        _seed_report(out_dir, "good")
        seen = _pipeline_returns(
            monkeypatch, "new", quotes=353, failed_sessions=1,
            bucket="ingest", category=CauseCategoryEnum.UNUSABLE_INPUT,
        )

        result = _reanalyse(runner, input_dir, seen)

        assert _read(out_dir / _MARKER) == "new"
        assert not output_backup.backup_path_for(out_dir).exists()
        assert not failed.exists()
        assert _KEPT_LINE not in result.output

    def test_a_clean_success_still_replaces_it(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        input_dir, out_dir, failed = _paths(tmp_path)
        _seed_report(out_dir, "good")
        seen = _pipeline_returns(monkeypatch, "new", quotes=353, failed_sessions=0)

        _reanalyse(runner, input_dir, seen)

        assert not output_backup.backup_path_for(out_dir).exists()
        assert not failed.exists()
        assert _read(out_dir / _MARKER) == "new"

    def test_a_first_analysis_that_comes_back_degraded_is_kept(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        """With no previous report there is nothing to hold back for."""
        input_dir, out_dir, failed = _paths(tmp_path)
        input_dir.mkdir()
        _pipeline_returns(monkeypatch, "degraded", quotes=4, failed_sessions=9)

        result = _invoke(runner, input_dir, clean=False)

        assert result.exit_code == 0, result.output
        assert _read(out_dir / _MARKER) == "degraded"
        assert not failed.exists()


class TestTheNextRunFinishesTheAttempt:
    def _degraded_reanalyse(self, runner, monkeypatch, input_dir, out_dir) -> None:
        _seed_report(out_dir, "good")
        seen = _pipeline_returns(monkeypatch, "attempt", quotes=4, failed_sessions=9)
        _reanalyse(runner, input_dir, seen)

    def test_a_retry_resumes_the_attempt_and_replaces_the_report(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        input_dir, out_dir, failed = _paths(tmp_path)
        self._degraded_reanalyse(runner, monkeypatch, input_dir, out_dir)
        seen = _pipeline_returns(monkeypatch, "finished", quotes=353, failed_sessions=0)

        result = _invoke(runner, input_dir, clean=False)

        assert result.exit_code == 0, result.output
        # The run picked up the attempt, not the old report (R109).
        assert seen["started_on"] == "attempt"
        assert _read(out_dir / _MARKER) == "finished"
        assert not failed.exists()
        assert not output_backup.backup_path_for(out_dir).exists()

    def test_a_retry_that_still_fails_keeps_the_report_and_the_attempt(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        input_dir, out_dir, failed = _paths(tmp_path)
        self._degraded_reanalyse(runner, monkeypatch, input_dir, out_dir)
        seen = _pipeline_returns(monkeypatch, "attempt2", quotes=40, failed_sessions=5)

        result = _invoke(runner, input_dir, clean=False)

        assert result.exit_code == 0, result.output
        assert seen["started_on"] == "attempt"
        assert _read(out_dir / _MARKER) == "good"
        assert _read(failed / _MARKER) == "attempt2"
        # The attempt's first run is on the report's log once, not twice.
        events = _read(out_dir / ".bristlenose" / "pipeline-events.jsonl")
        assert events.count('"run_id": "attempt"}') == 1, events

    def test_a_failed_reanalyse_is_finished_by_the_next_run(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        """R109: the failed run's paid work is resumed, not swept and paid again."""
        input_dir, out_dir, failed = _paths(tmp_path)
        _seed_report(out_dir, "good")
        _pipeline_raises(monkeypatch, "attempt")
        _invoke(runner, input_dir, clean=True)
        assert _read(out_dir / _MARKER) == "good"
        assert failed.is_dir()
        seen = _pipeline_returns(monkeypatch, "finished", quotes=353, failed_sessions=0)

        result = _invoke(runner, input_dir, clean=False)

        assert result.exit_code == 0, result.output
        assert seen["started_on"] == "attempt"
        assert _read(out_dir / _MARKER) == "finished"

    def test_a_retry_refused_before_the_pipeline_leaves_both_where_they_were(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        """A key that fails preflight must not leave the attempt on show."""
        from bristlenose.preflight.api_key import ApiKeyPreflightAbortedError

        input_dir, out_dir, failed = _paths(tmp_path)
        self._degraded_reanalyse(runner, monkeypatch, input_dir, out_dir)

        def _refuse(**kw):
            raise ApiKeyPreflightAbortedError("out of credit")

        monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", _refuse)
        result = _invoke(runner, input_dir, clean=False)

        assert result.exit_code == 2, result.output
        assert _read(out_dir / _MARKER) == "good"
        assert _read(failed / _MARKER) == "attempt"
        assert not output_backup.backup_path_for(out_dir).exists()

    def test_another_clean_starts_from_scratch(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        input_dir, out_dir, failed = _paths(tmp_path)
        self._degraded_reanalyse(runner, monkeypatch, input_dir, out_dir)
        seen = _pipeline_returns(monkeypatch, "fresh", quotes=353, failed_sessions=0)

        _reanalyse(runner, input_dir, seen)

        assert _read(out_dir / _MARKER) == "fresh"
        assert not failed.exists()

    def test_an_attempt_with_a_report_and_no_manifest_is_left_alone(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        """Promoting it would meet "Output directory already exists" with the
        report set aside."""
        input_dir, out_dir, failed = _paths(tmp_path)
        self._degraded_reanalyse(runner, monkeypatch, input_dir, out_dir)
        (failed / ".bristlenose" / "pipeline-manifest.json").unlink()
        seen = _pipeline_returns(monkeypatch, "resumed", quotes=353, failed_sessions=0)

        result = _invoke(runner, input_dir, clean=False)

        assert result.exit_code == 0, result.output
        assert seen["started_on"] == "good"
        assert _read(failed / _MARKER) == "attempt"
