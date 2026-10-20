"""A Re-analyse that comes back degraded discards the previous report (R108, open).

`run --clean` with 9 of 10 sessions failed and 4 quotes back (353 before)
discards the previous report, its database and curation included, because
`cli.py` counts any quote as a replacement. The reproduction below is a strict
xfail: it turns red, and must be un-marked, when a fix lands.

It is not fixed because keeping the backup forces a choice about the NEXT run
that is a product decision: the next run's `reclaim_stale` would put the kept
report back automatically, `stash` would refuse and turn the next `--clean`
into a resume, or a kept backup must be swept or carried a generation. And
`run_condition.summary_is_degraded` counts a declined file (a stray PDF in the
folder) as degraded, so a keep keyed on it fires on ordinary Re-analyses.

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


def _summary(*, failed_sessions: int) -> PipelineSummary:
    failed = [
        StageFailure(
            session_id=f"s{i}",
            cause=Cause(category=CauseCategoryEnum.NETWORK, message="quotes failed"),
        )
        for i in range(2, 2 + failed_sessions)
    ]
    return PipelineSummary(
        quotes=StageOutcome(attempted=1 + failed_sessions, succeeded=1, failed=failed)
    )


class _Result:
    llm_model = "claude-sonnet-4-6"
    llm_input_tokens = 0
    llm_output_tokens = 0
    llm_calls = 10

    def __init__(self, *, total_quotes: int, summary: PipelineSummary) -> None:
        self.total_quotes = total_quotes
        self.summary = summary


def _seed_report(out_dir: Path, marker: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / _MARKER).write_text(marker, encoding="utf-8")
    state = out_dir / ".bristlenose"
    state.mkdir(exist_ok=True)
    (state / "bristlenose.db").write_text(f"db:{marker}", encoding="utf-8")
    (state / "pipeline-events.jsonl").write_text(
        json.dumps({"event": "run_completed", "run_id": marker}) + "\n", encoding="utf-8"
    )


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", lambda s: None)
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None)
    return CliRunner()


def _pipeline_returns(
    monkeypatch, marker: str, *, quotes: int, failed_sessions: int
) -> dict[str, bool]:
    """Stub the run. Records whether the old report was still in the output
    folder when it started, which is false only if `--clean` set it aside."""
    seen: dict[str, bool] = {}

    async def _run(_self, _in, out, *a, **k):
        seen["old_marker_present"] = (Path(out) / _MARKER).exists()
        _seed_report(Path(out), marker)
        return _Result(total_quotes=quotes, summary=_summary(failed_sessions=failed_sessions))

    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _run)
    return seen


def _reanalyse(runner: CliRunner, input_dir: Path, seen: dict[str, bool]) -> None:
    """Run `--clean` and assert it really set the old report aside, so a
    verdict below is about the outcome and never about a refused stash."""
    result = runner.invoke(app, ["run", str(input_dir), "--clean", "--no-serve"])
    # `pytest.fail`, not `assert`: the xfail below is met only by an
    # AssertionError, so a broken precondition must fail the test outright.
    if result.exit_code != 0 or "Could not set" in result.output:
        pytest.fail(f"the run did not complete cleanly:\n{result.output}")
    if seen.get("old_marker_present") is not False:
        pytest.fail("the old report was not set aside before the run")


class TestTheDegradedRunKeepsThePreviousReport:
    @pytest.mark.xfail(
        strict=True,
        raises=AssertionError,
        reason="R108 open, needs a decision: what becomes of a kept backup at the "
        "next run (docs/design-lifecycle-failure-modes.md, row 54)",
    )
    def test_the_previous_report_and_its_database_survive(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        """The reproduction: 9 of 10 sessions failed, 4 quotes back."""
        input_dir = tmp_path / "interviews"
        out_dir = input_dir / "bristlenose-output"
        _seed_report(out_dir, "good")
        seen = _pipeline_returns(monkeypatch, "degraded", quotes=4, failed_sessions=9)

        _reanalyse(runner, input_dir, seen)

        # Not restored either way (R109). The new report is what is on show.
        assert (out_dir / _MARKER).read_text(encoding="utf-8") == "degraded"
        kept = output_backup.backup_path_for(out_dir)
        assert kept.is_dir(), "the degraded run discarded the previous report"
        assert (kept / _MARKER).read_text(encoding="utf-8") == "good"
        assert (kept / ".bristlenose" / "bristlenose.db").read_text(encoding="utf-8") == "db:good"

    def test_a_clean_success_still_discards_it(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        input_dir = tmp_path / "interviews"
        out_dir = input_dir / "bristlenose-output"
        _seed_report(out_dir, "good")
        seen = _pipeline_returns(monkeypatch, "new", quotes=353, failed_sessions=0)

        _reanalyse(runner, input_dir, seen)

        assert not output_backup.backup_path_for(out_dir).exists()
        assert (out_dir / _MARKER).read_text(encoding="utf-8") == "new"
