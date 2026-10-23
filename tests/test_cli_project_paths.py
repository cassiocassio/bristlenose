"""``serve`` and ``status`` find a project's output folder by one rule.

``cli._resolve_output_dir`` (``status``) used to try ``<p>/.bristlenose`` first,
so a project littered by a serve that had rooted itself at the interview folder
reported the litter and not the report. ``_auto_render`` (run by ``serve`` at
startup) set ``input_dir = output_dir.parent`` on both branches, so ``serve
<out>`` with an ``-o`` outside the interview folder re-ingested the parent — and
crashed with ``UnsuitableInputDirError`` when that was ``$HOME``. And ``status``
said nothing about a stashed report while the output folder was absent, which
is exactly when the stash is the only copy. All measured 12 Oct 2026
(docs/private handoff, findings S3, S12, P2).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from bristlenose import cli
from bristlenose.utils import output_backup


def _intermediate(out: Path) -> None:
    (out / ".bristlenose" / "intermediate").mkdir(parents=True)
    (out / ".bristlenose" / "pipeline-events.jsonl").write_text("", encoding="utf-8")


class _Recorder:
    """Stands in for ``Pipeline``: records the input dir a render was asked for."""

    calls: list[tuple[Path, Path]] = []

    def __init__(self, settings, verbose=False):
        pass

    def run_render_only(self, output_dir: Path, input_dir: Path):
        _Recorder.calls.append((output_dir, input_dir))

        class _R:
            total_quotes = 0

        return _R()


@pytest.fixture()
def recorder(monkeypatch: pytest.MonkeyPatch) -> type[_Recorder]:
    _Recorder.calls = []
    monkeypatch.setattr("bristlenose.pipeline.Pipeline", _Recorder)
    return _Recorder


class TestAutoRender:
    def test_default_layout_renders_with_the_interview_folder(
        self, tmp_path: Path, recorder: type[_Recorder],
    ) -> None:
        proj = tmp_path / "proj"
        out = proj / "bristlenose-output"
        _intermediate(out)
        cli._auto_render(proj)
        assert recorder.calls == [(out, proj.resolve())]

    def test_an_output_folder_elsewhere_is_not_rendered_from_its_parent(
        self, tmp_path: Path, recorder: type[_Recorder],
    ) -> None:
        """``run -o ~/reports/study`` then ``serve ~/reports/study``: the parent
        is not the interview folder, and ingesting it is a crash at best."""
        out = tmp_path / "reports" / "study"
        _intermediate(out)
        cli._auto_render(out)
        assert recorder.calls == [], (
            f"rendered from a folder that holds no interviews: {recorder.calls}"
        )


class TestServeRootAfterRun:
    def test_default_output_serves_the_interview_folder(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        assert cli._serve_root_for(proj, proj / "bristlenose-output") == proj

    def test_output_elsewhere_serves_the_output_folder(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        out = tmp_path / "elsewhere"
        assert cli._serve_root_for(proj, out) == out


class TestResolveOutputDir:
    def test_standard_layout(self, tmp_path: Path) -> None:
        out = tmp_path / "bristlenose-output"
        _intermediate(out)
        assert cli._resolve_output_dir(tmp_path) == out

    def test_the_output_folder_itself(self, tmp_path: Path) -> None:
        out = tmp_path / "bristlenose-output"
        _intermediate(out)
        assert cli._resolve_output_dir(out) == out

    def test_an_output_folder_elsewhere(self, tmp_path: Path) -> None:
        out = tmp_path / "study"
        _intermediate(out)
        assert cli._resolve_output_dir(out) == out

    def test_legacy_output_folder(self, tmp_path: Path) -> None:
        legacy = tmp_path / "output"
        (legacy / ".bristlenose").mkdir(parents=True)
        assert cli._resolve_output_dir(tmp_path) == legacy

    def test_nothing(self, tmp_path: Path) -> None:
        assert cli._resolve_output_dir(tmp_path) is None

    def test_litter_at_the_project_root_does_not_win(self, tmp_path: Path) -> None:
        """A serve that rooted itself at the interview folder left
        ``<p>/.bristlenose/``; the report is still under ``bristlenose-output/``."""
        (tmp_path / ".bristlenose").mkdir()
        out = tmp_path / "bristlenose-output"
        _intermediate(out)
        assert cli._resolve_output_dir(tmp_path) == out


class TestStatusReportsTheStash:
    def test_a_stash_is_named_even_when_the_output_is_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """After a hard crash the stash is the only copy of the report and the
        output folder may not exist at all; ``status`` must still say so."""
        monkeypatch.setattr(output_backup, "project_is_locked", lambda _p: False)
        out = tmp_path / "bristlenose-output"
        stash = output_backup.backup_path_for(out)
        (stash / ".bristlenose").mkdir(parents=True)
        result = CliRunner().invoke(cli.app, ["status", str(tmp_path)])
        assert result.exit_code == 1
        assert stash.name in result.output

    def test_an_unlocked_stash_is_not_called_in_flight_and_gets_no_rm(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys,
    ) -> None:
        monkeypatch.setattr(output_backup, "project_is_locked", lambda _p: False)
        out = tmp_path / "bristlenose-output"
        output_backup.backup_path_for(out).mkdir()
        cli._report_stashed_output(out)
        text = " ".join(capsys.readouterr().out.split())
        assert "in flight" not in text
        assert "rm -rf" not in text, "that is the only copy of a report"
        assert "next run" in text

    def test_a_locked_stash_is_in_flight(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys,
    ) -> None:
        monkeypatch.setattr(output_backup, "project_is_locked", lambda _p: True)
        out = tmp_path / "bristlenose-output"
        output_backup.backup_path_for(out).mkdir()
        cli._report_stashed_output(out)
        text = " ".join(capsys.readouterr().out.split())
        assert "in flight" in text
        assert "rm -rf" not in text

    def test_a_failed_tree_says_the_next_run_deletes_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys,
    ) -> None:
        """``.bristlenose-output-failed/`` is a failed run's tree nothing reads
        (left by a cut put-back, or a build with the 22 Oct hold-back)."""
        monkeypatch.setattr(output_backup, "project_is_locked", lambda _p: False)
        out = tmp_path / "bristlenose-output"
        output_backup.failed_path_for(out).mkdir()
        cli._report_stashed_output(out)
        text = " ".join(capsys.readouterr().out.split())
        assert "the next run deletes it" in text
        assert "rm -rf" in text

    def test_a_backup_replaced_by_a_fresh_analysis_says_so(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys,
    ) -> None:
        """A Re-analyse cut short after a session landed: the next run deletes
        the backup rather than putting it back (`output_backup.settle`)."""
        from tests.test_output_backup import _land_a_session

        monkeypatch.setattr(output_backup, "project_is_locked", lambda _p: False)
        out = tmp_path / "bristlenose-output"
        output_backup.backup_path_for(out).mkdir()
        out.mkdir()
        _land_a_session(out)
        cli._report_stashed_output(out)
        text = " ".join(capsys.readouterr().out.split())
        assert "replaced by a fresh analysis" in text
        assert "puts it back" not in text


class TestAnalyzeProjectName:
    """``bristlenose analyze <p>/bristlenose-output/transcripts-raw`` named the
    project ``transcripts-raw`` (handoff P8). Since ``remove_superseded_reports``
    (fe0bc8a4) prunes every report whose name is not the current one, that run
    would also have deleted ``bristlenose-<project>-report.html``. The name now
    comes from the project the output belongs to."""

    def _names_with(self, monkeypatch: pytest.MonkeyPatch, transcripts: Path) -> str:
        seen: dict[str, object] = {}

        class _StopError(Exception):
            pass

        def _capture(**kwargs):
            seen.update(kwargs)
            raise _StopError

        monkeypatch.setattr(cli, "load_settings", _capture)
        result = CliRunner().invoke(cli.app, ["analyze", str(transcripts)])
        assert isinstance(result.exception, _StopError), result.output
        return str(seen["project_name"])

    def test_the_project_keeps_its_recorded_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        proj = tmp_path / "Talismanic"
        raw = proj / "bristlenose-output" / "transcripts-raw"
        raw.mkdir(parents=True)
        inter = proj / "bristlenose-output" / ".bristlenose" / "intermediate"
        inter.mkdir(parents=True)
        (inter / "metadata.json").write_text('{"project_name": "Talismanic study"}', encoding="utf-8")
        assert self._names_with(monkeypatch, raw) == "Talismanic study"

    def test_with_no_record_the_project_folder_names_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        proj = tmp_path / "Talismanic"
        raw = proj / "bristlenose-output" / "transcripts-raw"
        raw.mkdir(parents=True)
        assert self._names_with(monkeypatch, raw) == "Talismanic"

    def test_a_standalone_transcripts_folder_still_names_itself(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        raw = tmp_path / "zoom exports"
        raw.mkdir()
        assert self._names_with(monkeypatch, raw) == "zoom exports"
