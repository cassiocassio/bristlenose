"""``serve`` and ``status`` find a project's output folder by one rule.

``serve`` and ``status`` must agree about a project's output folder.  In
particular, a stray ``<project>/.bristlenose`` directory must not win over the
actual report, and ``status`` must still name a stashed report when the output
folder is absent.
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

    def test_a_backup_marked_replaced_says_so_without_a_session_on_disk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys,
    ) -> None:
        """A run with no intermediates replaced it, then an export would not
        move: the marker, not the disk, is what says it (`backup_is_replaced`)."""
        monkeypatch.setattr(output_backup, "project_is_locked", lambda _p: False)
        out = tmp_path / "bristlenose-output"
        backup = output_backup.backup_path_for(out)
        backup.mkdir()
        (backup / ".bristlenose-backup-replaced").touch()
        out.mkdir()
        cli._report_stashed_output(out)
        text = " ".join(capsys.readouterr().out.split())
        assert "replaced by a fresh analysis" in text

    def test_a_delete_cut_short_is_named(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys,
    ) -> None:
        monkeypatch.setattr(output_backup, "project_is_locked", lambda _p: False)
        out = tmp_path / "bristlenose-output"
        (tmp_path / ".bristlenose-output-previous-discarding-42").mkdir()
        cli._report_stashed_output(out)
        text = " ".join(capsys.readouterr().out.split())
        assert ".bristlenose-output-previous-discarding-42 — a replaced report" in text
        assert "rm -rf" in text


    def test_the_delete_hint_survives_a_paste_whatever_the_folder_is_called(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys,
    ) -> None:
        """N139: the path was interpolated bare, so a folder called "Acme onboarding"
        pasted as ``rm -rf Acme onboarding/...`` and deleted an existing sibling
        called "Acme". Rich also folded the line at the space once the path passed
        the console width, so even a careful one-line copy ran a truncated delete.
        The hint is one line, shell-quoted, with a bracketed word left alone."""
        import shlex

        monkeypatch.setattr(output_backup, "project_is_locked", lambda _p: False)
        study = tmp_path / "Acme onboarding [draft] study with a long descriptive name"
        study.mkdir()
        out = study / "bristlenose-output"
        failed = output_backup.failed_path_for(out)
        failed.mkdir()
        assert len(str(failed)) > 80, "the fixture must pass the console width"
        cli._report_stashed_output(out)
        lines = [ln for ln in capsys.readouterr().out.splitlines() if "rm -rf" in ln]
        assert len(lines) == 1, "the command folded across lines or vanished"
        command = lines[0].split("Delete with:", 1)[1].strip()
        assert shlex.split(command) == ["rm", "-rf", str(failed)]


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
