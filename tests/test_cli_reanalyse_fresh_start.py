"""A Re-analyse is a fresh start: it replaces the report once it has a session.

Ruled 23 Oct 2026 (owner, decision 1b). `run --clean` replaces the previous
analysis once it has produced at least one analysed session, even if other
sessions failed. If it produced nothing (refused before the pipeline, or
failed, stopped or crashed before any session landed), the previous report
comes back as it was. Nothing of the old analysis is archived, except the
clips and screens the researcher exported, which carry into the new output
under the old analysis's date.

This replaces 22 Oct's hold-back (f3aebc07): a Re-analyse with failed sessions
put the old report back and kept its attempt, and the next plain run swapped
the attempt in and discarded the report, with whatever curation had been done
on it since (the release hold). No plain run replaces a report now.

Drives the real CLI with a stubbed `Pipeline.run`, as
`tests/test_cli_output_backup_wiring.py` does.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
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


def _summary(failed_sessions: int) -> PipelineSummary:
    failures = [
        StageFailure(session_id=f"s{i}", cause=Cause(
            category=CauseCategoryEnum.NETWORK, message="failed"))
        for i in range(2, 2 + failed_sessions)
    ]
    return PipelineSummary(quotes=StageOutcome(
        attempted=1 + failed_sessions, succeeded=1, failed=failures,
    ))


class _Result:
    llm_model = "claude-sonnet-4-6"
    llm_input_tokens = 0
    llm_output_tokens = 0
    llm_calls = 10

    def __init__(self, *, total_quotes: int, summary: PipelineSummary) -> None:
        self.total_quotes = total_quotes
        self.summary = summary


def _seed_report(out_dir: Path, marker: str, *, created: str | None = None) -> None:
    """A run's output: a deliverable, a database, a manifest and a terminus."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / _MARKER).write_text(marker, encoding="utf-8")
    state = out_dir / ".bristlenose"
    state.mkdir(exist_ok=True)
    (state / "bristlenose.db").write_text(f"db:{marker}", encoding="utf-8")
    (state / "pipeline-manifest.json").write_text("{}", encoding="utf-8")
    with (state / "pipeline-events.jsonl").open("a", encoding="utf-8") as fh:
        if created is not None:
            # The run that made this analysis: its start dates the analysis.
            fh.write(json.dumps({"event": "run_started", "run_id": marker,
                                 "started_at": created}) + "\n")
        fh.write(json.dumps({"event": "run_completed", "run_id": marker}) + "\n")


def _land_sessions(out_dir: Path, sids: list[str], *, quotes_each: int = 2) -> None:
    """What a session leaves on disk when its quotes are in: the quotes file,
    then the manifest record that says they are there (pipeline `_deliver_quotes`)."""
    from bristlenose.manifest import (
        STAGE_QUOTE_EXTRACTION,
        create_manifest,
        mark_session_complete,
        write_manifest,
    )

    intermediate = out_dir / ".bristlenose" / "intermediate"
    intermediate.mkdir(parents=True, exist_ok=True)
    quotes = [
        {"session_id": sid, "participant_id": "p1", "text": f"q{n}"}
        for sid in sids for n in range(quotes_each)
    ]
    (intermediate / "extracted_quotes.json").write_text(json.dumps(quotes), encoding="utf-8")
    manifest = create_manifest("t", "0")
    for sid in sids:
        mark_session_complete(manifest, STAGE_QUOTE_EXTRACTION, sid)
    write_manifest(manifest, out_dir)


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", lambda s: None)
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None)
    return CliRunner()


def _pipeline_returns(monkeypatch, marker: str, *, quotes: int, failed_sessions: int = 0):
    seen: dict[str, object] = {}

    async def _run(_self, _in, out, *a, **k):
        found = Path(out) / _MARKER
        seen["started_on"] = found.read_text(encoding="utf-8") if found.exists() else None
        _seed_report(Path(out), marker)
        return _Result(total_quotes=quotes, summary=_summary(failed_sessions))

    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _run)
    return seen


def _pipeline_raises(monkeypatch, marker: str, *, landed: list[str] | None = None,
                     exc: BaseException | None = None) -> None:
    async def _run(_self, _in, out, *a, **k):
        _seed_report(Path(out), marker)
        if landed:
            _land_sessions(Path(out), landed)
        raise exc if exc is not None else RuntimeError("provider went away")

    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _run)


def _invoke(runner: CliRunner, input_dir: Path, *, clean: bool):
    args = ["run", str(input_dir), "--no-serve"] + (["--clean", "--yes"] if clean else [])
    return runner.invoke(app, args)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    input_dir = tmp_path / "interviews"
    return input_dir, input_dir / "bristlenose-output"


def _no_litter(out_dir: Path) -> None:
    assert not output_backup.backup_path_for(out_dir).exists()
    assert not (out_dir.parent / f".{out_dir.name}-failed").exists()


class TestAFreshStartReplacesTheReport:
    def test_one_analysed_session_is_enough(self, runner, tmp_path: Path, monkeypatch) -> None:
        """R108's shape: 9 of 10 sessions failed, 4 quotes back. Ruled 23 Oct:
        the fresh analysis replaces the old one."""
        input_dir, out_dir = _paths(tmp_path)
        _seed_report(out_dir, "old")
        seen = _pipeline_returns(monkeypatch, "new", quotes=4, failed_sessions=9)

        result = _invoke(runner, input_dir, clean=True)

        assert result.exit_code == 0, result.output
        assert seen["started_on"] is None
        assert _read(out_dir / _MARKER) == "new"
        assert _read(out_dir / ".bristlenose" / "bristlenose.db") == "db:new"
        _no_litter(out_dir)

    @pytest.mark.xfail(strict=True, reason=(
        "Open judgement call (RE#13, 23 Oct 2026): a run whose only failures are "
        "recordings that did not transcribe still ends on \"✓ Done\"; quote and "
        "topic failures already end on \"Done with warnings — no quotes from …\". "
        "No existing words say it; the options wait on the owner."))
    def test_a_partial_run_does_not_say_done(self, runner, tmp_path: Path, monkeypatch) -> None:
        """Over a partly analysed report the summary is not a bare "✓ Done"."""
        input_dir, out_dir = _paths(tmp_path)
        _seed_report(out_dir, "old")
        failures = [StageFailure(session_id="s2", cause=Cause(
            category=CauseCategoryEnum.CLOUD_FETCH, message="failed"))]
        summary = PipelineSummary(transcripts=StageOutcome(
            attempted=2, succeeded=1, failed=failures))

        async def _run(_self, _in, out, *a, **k):
            _seed_report(Path(out), "new")
            return _Result(total_quotes=40, summary=summary)

        monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _run)

        result = _invoke(runner, input_dir, clean=True)

        assert _read(out_dir / _MARKER) == "new"
        assert "✓ Done" not in result.output, result.output

    def test_a_run_that_fails_after_a_session_landed_replaces_it(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        input_dir, out_dir = _paths(tmp_path)
        _seed_report(out_dir, "old")
        _pipeline_raises(monkeypatch, "new", landed=["s1"])

        _invoke(runner, input_dir, clean=True)

        assert _read(out_dir / _MARKER) == "new"
        _no_litter(out_dir)

    def test_a_run_stopped_after_a_session_landed_replaces_it(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        input_dir, out_dir = _paths(tmp_path)
        _seed_report(out_dir, "old")
        _pipeline_raises(monkeypatch, "new", landed=["s1"], exc=KeyboardInterrupt())

        _invoke(runner, input_dir, clean=True)

        assert _read(out_dir / _MARKER) == "new"
        _no_litter(out_dir)


class TestAFreshStartThatProducedNothing:
    def test_a_failure_before_any_session_puts_the_report_back(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        input_dir, out_dir = _paths(tmp_path)
        _seed_report(out_dir, "old")
        _pipeline_raises(monkeypatch, "attempt")

        _invoke(runner, input_dir, clean=True)

        assert _read(out_dir / _MARKER) == "old"
        assert _read(out_dir / ".bristlenose" / "bristlenose.db") == "db:old"
        # The attempt is not kept: there is nothing to finish it from.
        _no_litter(out_dir)
        # And the failure stays on the record (30 Aug design).
        events = _read(out_dir / ".bristlenose" / "pipeline-events.jsonl")
        assert '"run_id": "attempt"' in events

    def test_a_session_with_no_quotes_is_not_an_analysis(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        """A silent recording is recorded complete with no quotes; an emptied or
        silent folder must not replace a report (R116)."""
        input_dir, out_dir = _paths(tmp_path)
        _seed_report(out_dir, "old")

        async def _run(_self, _in, out, *a, **k):
            _seed_report(Path(out), "attempt")
            _land_sessions(Path(out), ["s1"], quotes_each=0)
            raise RuntimeError("stopped")

        monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _run)

        _invoke(runner, input_dir, clean=True)

        assert _read(out_dir / _MARKER) == "old"

    def test_a_refusal_before_the_pipeline_moves_nothing(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        from bristlenose.preflight.api_key import ApiKeyPreflightAbortedError

        input_dir, out_dir = _paths(tmp_path)
        _seed_report(out_dir, "old")

        def _refuse(**kw):
            raise ApiKeyPreflightAbortedError("out of credit")

        monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", _refuse)
        result = _invoke(runner, input_dir, clean=True)

        assert result.exit_code == 2, result.output
        assert _read(out_dir / _MARKER) == "old"
        _no_litter(out_dir)


class TestNoPlainRunReplacesAReport:
    def test_the_run_after_a_failed_reanalyse_works_on_the_report(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        """The release hold: a plain run after a Re-analyse that came back with
        nothing used to swap the attempt in and discard the report, curation made
        on it since included. It now resumes the report it finds."""
        input_dir, out_dir = _paths(tmp_path)
        _seed_report(out_dir, "old")
        _pipeline_raises(monkeypatch, "attempt")
        _invoke(runner, input_dir, clean=True)
        # The researcher stars a quote on the restored report.
        (out_dir / ".bristlenose" / "bristlenose.db").write_text("db:old+star", encoding="utf-8")
        seen: dict[str, object] = {}

        async def _resume(_self, _in, out, *a, **k):
            # A resume touches neither the report nor its database here.
            seen["started_on"] = _read(Path(out) / _MARKER)
            return _Result(total_quotes=353, summary=PipelineSummary())

        monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _resume)

        result = _invoke(runner, input_dir, clean=False)

        assert result.exit_code == 0, result.output
        assert seen["started_on"] == "old"
        assert _read(out_dir / ".bristlenose" / "bristlenose.db") == "db:old+star"
        _no_litter(out_dir)

    def test_a_leftover_attempt_is_never_swapped_in(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        """A `.bristlenose-output-failed` from a build with the hold-back."""
        input_dir, out_dir = _paths(tmp_path)
        _seed_report(out_dir, "old")
        _seed_report(out_dir.parent / f".{out_dir.name}-failed", "attempt")
        seen = _pipeline_returns(monkeypatch, "old", quotes=353)

        result = _invoke(runner, input_dir, clean=False)

        assert result.exit_code == 0, result.output
        assert seen["started_on"] == "old"
        _no_litter(out_dir)


class TestExportsCarryAcross:
    def _exports(self, out_dir: Path) -> None:
        (out_dir / "clips").mkdir()
        (out_dir / "clips" / "p1 0-12.mp4").write_text("clip", encoding="utf-8")
        (out_dir / "screens").mkdir()
        (out_dir / "screens" / "s1 01.png").write_text("still", encoding="utf-8")

    def test_clips_and_screens_carry_under_the_old_analysis_date(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        input_dir, out_dir = _paths(tmp_path)
        _seed_report(out_dir, "old", created="2026-10-03T09:00:00Z")
        self._exports(out_dir)
        _pipeline_returns(monkeypatch, "new", quotes=4, failed_sessions=1)

        _invoke(runner, input_dir, clean=True)

        assert _read(out_dir / _MARKER) == "new"
        clips = out_dir / "clips (from the analysis of 3 Oct 2026)"
        screens = out_dir / "screens (from the analysis of 3 Oct 2026)"
        assert _read(clips / "p1 0-12.mp4") == "clip"
        assert _read(screens / "s1 01.png") == "still"
        assert not (out_dir / "clips").exists()
        _no_litter(out_dir)

    def test_earlier_dated_folders_carry_along_and_none_is_overwritten(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        input_dir, out_dir = _paths(tmp_path)
        _seed_report(out_dir, "old", created="2026-10-03T09:00:00Z")
        self._exports(out_dir)
        earlier = out_dir / "clips (from the analysis of 1 Sep 2026)"
        earlier.mkdir()
        (earlier / "a.mp4").write_text("older", encoding="utf-8")
        # Same day as the old analysis: a second fresh start that day.
        same_day = out_dir / "clips (from the analysis of 3 Oct 2026)"
        same_day.mkdir()
        (same_day / "b.mp4").write_text("same day", encoding="utf-8")
        _pipeline_returns(monkeypatch, "new", quotes=4)

        _invoke(runner, input_dir, clean=True)

        assert _read(out_dir / "clips (from the analysis of 1 Sep 2026)" / "a.mp4") == "older"
        assert _read(same_day / "b.mp4") == "same day"
        assert _read(out_dir / "clips (from the analysis of 3 Oct 2026) 2" / "p1 0-12.mp4") == "clip"

    def test_nothing_produced_leaves_the_exports_where_they_were(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        input_dir, out_dir = _paths(tmp_path)
        _seed_report(out_dir, "old", created="2026-10-03T09:00:00Z")
        self._exports(out_dir)
        _pipeline_raises(monkeypatch, "attempt")

        _invoke(runner, input_dir, clean=True)

        assert _read(out_dir / "clips" / "p1 0-12.mp4") == "clip"
        assert not any(p.name.startswith("clips (") for p in out_dir.iterdir())


class TestAnExportIsNeverDeleted:
    def test_exports_made_into_a_run_that_produced_nothing_are_kept(
        self, runner, tmp_path: Path, monkeypatch
    ) -> None:
        """Clips exported from the fresh analysis while it ran sit in its tree;
        a put-back that drops the tree moves them out first."""
        input_dir, out_dir = _paths(tmp_path)
        _seed_report(out_dir, "old")

        async def _run(_self, _in, out, *a, **k):
            _seed_report(Path(out), "attempt", created="2026-10-23T20:00:00Z")
            (Path(out) / "clips").mkdir()
            (Path(out) / "clips" / "new.mp4").write_text("mid-run clip", encoding="utf-8")
            raise RuntimeError("provider went away")

        monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _run)

        _invoke(runner, input_dir, clean=True)

        assert _read(out_dir / _MARKER) == "old"
        # The folder is dated by the attempt's own start, which this run writes
        # now, so the test finds the one carried folder rather than predicting
        # today's date (it failed the first time it ran after midnight).
        carried = [p for p in out_dir.iterdir() if p.name.startswith("clips (from the analysis of ")]
        assert len(carried) == 1, [p.name for p in out_dir.iterdir()]
        assert _read(carried[0] / "new.mp4") == "mid-run clip"
        _no_litter(out_dir)

    def test_a_carry_that_cannot_list_the_report_does_not_raise(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """It runs inside the CLI's `finally`: an escape would replace the run's
        own failure with a traceback."""
        report = tmp_path / "report"
        report.mkdir()
        real = Path.iterdir

        def _refuse(self):
            if self == report:
                raise PermissionError("denied")
            return real(self)

        monkeypatch.setattr(Path, "iterdir", _refuse)
        assert output_backup.carry_exports(report, tmp_path / "out") is False

    def test_an_incomplete_carry_is_said(self, runner, tmp_path: Path, monkeypatch) -> None:
        input_dir, out_dir = _paths(tmp_path)
        _seed_report(out_dir, "old")
        _pipeline_returns(monkeypatch, "new", quotes=4)
        monkeypatch.setattr(output_backup, "carry_exports", lambda *_a: False)

        result = _invoke(runner, input_dir, clean=True)

        assert _read(out_dir / _MARKER) == "new"
        assert output_backup.backup_path_for(out_dir).exists()
        assert "previous report is kept" in " ".join(result.output.split())


class TestACrashIsSettledByTheSameRule:
    def _crashed(self, out_dir: Path, *, landed: list[str]) -> None:
        """What a SIGKILL mid --clean leaves: the report set aside, the attempt
        in place, no terminus, no live PID."""
        _seed_report(out_dir, "old", created="2026-10-03T09:00:00Z")
        (out_dir / "clips").mkdir()
        (out_dir / "clips" / "c.mp4").write_text("clip", encoding="utf-8")
        assert output_backup.stash(out_dir) is not None
        _seed_report(out_dir, "attempt")
        if landed:
            _land_sessions(out_dir, landed)

    def test_a_crash_before_any_session_landed_puts_the_report_back(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "bristlenose-output"
        self._crashed(out_dir, landed=[])

        outcome = output_backup.reclaim_stale(out_dir)

        assert outcome.report_is_back
        assert _read(out_dir / _MARKER) == "old"
        _no_litter(out_dir)

    def test_a_crash_after_a_session_landed_keeps_the_fresh_analysis(
        self, tmp_path: Path
    ) -> None:
        out_dir = tmp_path / "bristlenose-output"
        self._crashed(out_dir, landed=["s1"])

        output_backup.reclaim_stale(out_dir)

        assert _read(out_dir / _MARKER) == "attempt"
        assert _read(out_dir / "clips (from the analysis of 3 Oct 2026)" / "c.mp4") == "clip"
        _no_litter(out_dir)


def test_the_folder_date_is_the_old_analysis_day_on_this_machine() -> None:
    from bristlenose.utils.markdown import format_finder_day

    assert format_finder_day(datetime(2026, 10, 3, 9, 0)) == "3 Oct 2026"
    assert format_finder_day(datetime(2026, 1, 9, 23, 0, tzinfo=timezone.utc)) in (
        "9 Jan 2026", "10 Jan 2026",  # local zone
    )


@pytest.mark.skipif(
    __import__("sys").platform == "win32" or __import__("os").geteuid() == 0,
    reason="needs a folder this user cannot write",
)
def test_a_clean_refuses_while_an_export_is_still_to_carry(
    runner, tmp_path: Path, monkeypatch
) -> None:
    """Finding 2, unstubbed: a crashed fresh run that analysed a session, and an
    old `clips/` that will not move. `--clean` used to find the backup unspent,
    fail to stash, print "this run will write over it" and resume the fresh
    analysis: a fresh start that quietly wasn't one."""
    input_dir, out_dir = _paths(tmp_path)
    _seed_report(out_dir, "old", created="2026-10-03T09:00:00Z")
    (out_dir / "clips").mkdir()
    (out_dir / "clips" / "c.mp4").write_text("clip", encoding="utf-8")
    backup = output_backup.stash(out_dir)
    _seed_report(out_dir, "fresh")
    _land_sessions(out_dir, ["s1"])
    seen = _pipeline_returns(monkeypatch, "again", quotes=353)
    backup.chmod(0o500)
    try:
        result = _invoke(runner, input_dir, clean=True)
    finally:
        backup.chmod(0o700)

    assert result.exit_code == 1, result.output
    assert "seen" not in seen and "started_on" not in seen, "the pipeline ran"
    assert "previous report is kept" in " ".join(result.output.split())
    assert _read(out_dir / _MARKER) == "fresh"
    assert _read(backup / "clips" / "c.mp4") == "clip"
