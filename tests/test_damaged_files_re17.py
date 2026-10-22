"""A damaged file is never written over, and the researcher is told (RE#17).

Owner rulings, 22 Oct 2026 (decisions #17 and #18). A file the researcher edits
(``people.yaml``) is left exactly as it is, the run carries on without the names
in it, and the terminal names the line to fix. A record Bristlenose keeps for
itself (the pipeline manifest) is set aside as ``<name>.damaged-<stamp>`` and
the run says what that costs. Until then a typo in ``people.yaml`` stopped
``run`` with a traceback after every paid stage, and a truncated manifest was
written over while the terminal said "Resuming from previous run...".

Driven through the real ``Pipeline`` methods (``test_pipeline_command_caches``'
harness: real manifest, real people file, Whisper and every LLM call stubbed).
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest

from bristlenose.manifest import (
    MANIFEST_FILENAME,
    create_manifest,
    hold_for_resume,
    load_manifest,
)
from bristlenose.people import (
    PEOPLE_FILENAME,
    load_people_file,
    read_people_file,
    write_people_file,
)
from tests.test_pipeline_command_caches import _drive

_TYPO = (
    "participants:\n"
    "  p1:\n"
    "    editable:\n"
    '      full_name: "Sarah\n'
    "      short_name: Sarah\n"
)
_WRONG_SHAPE = "participants: 5\n"
_TRUNCATED = '{"schema_version": 1, "project_name": "x", "stag'


def _people(tmp_path: Path) -> Path:
    return tmp_path / "output" / PEOPLE_FILENAME


def _manifest(tmp_path: Path) -> Path:
    return tmp_path / "output" / ".bristlenose" / MANIFEST_FILENAME


def _one_line(out: str) -> str:
    """Rich wraps at 80 columns; the sentence is what is asserted."""
    return re.sub(r"\s+", " ", out)


class TestPeopleFile:
    @pytest.mark.parametrize("mode", ["run", "transcribe", "analyze"])
    def test_a_typo_is_left_as_it_is_and_the_run_finishes(
        self, tmp_path: Path, mode: str, capsys: pytest.CaptureFixture[str],
    ) -> None:
        _drive(tmp_path, "run", 2, {})
        _people(tmp_path).write_text(_TYPO, encoding="utf-8")
        capsys.readouterr()

        _drive(tmp_path, mode, 2, {})

        assert _people(tmp_path).read_text(encoding="utf-8") == _TYPO, (
            f"{mode} wrote over the researcher's file"
        )
        said = _one_line(capsys.readouterr().out)
        assert (
            "people.yaml couldn't be read (line 4, column 18), so it was left as it "
            "is, and names you added aren't in this report. Fix that line, then run "
            "again." in said
        ), said

    @pytest.mark.parametrize("text", [
        _WRONG_SHAPE,
        # A date that does not exist raises ValueError from the YAML
        # constructor, outside YAMLError (silent-failure review).
        "participants:\n  p1:\n    editable:\n      notes: 2026-02-30\n",
    ])
    def test_a_file_of_the_wrong_shape_is_left_too_with_no_line_to_name(
        self, tmp_path: Path, text: str, capsys: pytest.CaptureFixture[str],
    ) -> None:
        _drive(tmp_path, "run", 2, {})
        _people(tmp_path).write_text(text, encoding="utf-8")
        capsys.readouterr()

        _drive(tmp_path, "run", 2, {})

        assert _people(tmp_path).read_text(encoding="utf-8") == text
        assert "people.yaml couldn't be read, so it was left as it is" in _one_line(
            capsys.readouterr().out
        )

    @pytest.mark.parametrize("mode", ["run", "transcribe"])
    def test_no_names_are_filled_in_for_a_file_that_will_not_read(
        self, tmp_path: Path, mode: str,
    ) -> None:
        """A detected name may be the real one the researcher pseudonymised.

        With the file unreadable, the run shows codes, never a name of its own
        finding (silent-failure review of RE#17).
        """
        _drive(tmp_path, "run", 2, {})
        _people(tmp_path).write_text(_TYPO, encoding="utf-8")
        filled: list[str] = []

        def _spy(people, *_a, **_kw):
            filled.append(mode)

        with patch("bristlenose.people.auto_populate_names", new=_spy):
            result = _drive(tmp_path, mode, 2, {})

        assert filled == [], "names were filled in for an unreadable people.yaml"
        if result is not None:
            assert result.people is not None
            assert all(
                not e.editable.full_name and not e.editable.short_name
                for e in result.people.participants.values()
            )

    def test_render_only_leaves_it_and_says_so(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        """serve's static re-render reads people.yaml too (`run_render_only`)."""
        from bristlenose.config import BristlenoseSettings
        from bristlenose.pipeline import Pipeline

        _drive(tmp_path, "run", 2, {})
        _people(tmp_path).write_text(_TYPO, encoding="utf-8")
        capsys.readouterr()

        Pipeline(BristlenoseSettings(project_name="caches", output_dir=tmp_path / "output"),
                 verbose=False).run_render_only(tmp_path / "output", tmp_path / "input")

        assert _people(tmp_path).read_text(encoding="utf-8") == _TYPO
        assert "people.yaml couldn't be read (line 4, column 18)" in _one_line(
            capsys.readouterr().out
        )

    def test_a_readable_file_is_still_rewritten(self, tmp_path: Path) -> None:
        """The skip is for a file that will not read, not for every run."""
        _drive(tmp_path, "run", 2, {})
        people = load_people_file(tmp_path / "output")
        assert people is not None
        _people(tmp_path).write_text("# hand-trimmed\n" + _people(tmp_path).read_text())

        _drive(tmp_path, "run", 2, {})

        assert not _people(tmp_path).read_text().startswith("# hand-trimmed")

    @pytest.mark.parametrize(("text", "where"), [
        # An unclosed quote is noticed at the end of the file; the line to fix
        # is where it opened.
        (_TYPO, (4, 18)),
        # A mid-file mistake is named where YAML noticed it.
        ("participants:\n  p1:\n    editable: x\n     role: y\n", (4, 10)),
    ])
    def test_the_tolerant_reader_names_the_line(
        self, tmp_path: Path, text: str, where: tuple[int, int],
    ) -> None:
        (tmp_path / PEOPLE_FILENAME).write_text(text, encoding="utf-8")
        people, problem = read_people_file(tmp_path)
        assert people is None
        assert problem is not None and (problem.line, problem.column) == where

    def test_a_write_that_dies_before_the_rename_leaves_the_old_file_whole(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A crash or a full disk mid-write used to truncate the file in place."""
        _drive(tmp_path, "run", 1, {})
        out = tmp_path / "output"
        before = _people(tmp_path).read_text(encoding="utf-8")
        people = load_people_file(out)
        assert people is not None
        people.participants["p1"].editable.full_name = "Changed"

        def _die(*_a, **_kw):
            raise OSError("disk full")

        monkeypatch.setattr("bristlenose.people.replace_retrying", _die)
        with pytest.raises(OSError):
            write_people_file(people, out)

        assert _people(tmp_path).read_text(encoding="utf-8") == before
        assert [p.name for p in out.iterdir() if p.name.endswith(".tmp")] == []


class TestManifest:
    def test_a_damaged_manifest_is_set_aside_and_the_cost_is_said(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        log: dict = {}
        _drive(tmp_path, "run", 2, log)
        _manifest(tmp_path).write_text(_TRUNCATED, encoding="utf-8")
        capsys.readouterr()

        _drive(tmp_path, "run", 2, log)

        aside = sorted(_manifest(tmp_path).parent.glob(f"{MANIFEST_FILENAME}.damaged-*"))
        assert len(aside) == 1, "the damaged manifest was written over"
        assert aside[0].read_text(encoding="utf-8") == _TRUNCATED
        assert re.fullmatch(
            rf"{re.escape(MANIFEST_FILENAME)}\.damaged-\d{{4}}-\d\d-\d\dT\d\d-\d\d-\d\d",
            aside[0].name,
        )
        said = _one_line(capsys.readouterr().out)
        assert (
            f"The pipeline manifest couldn't be read, so it was set aside as "
            f"{aside[0].name}. Every stage runs again, including the LLM stages." in said
        ), said
        # It did: the second run transcribed again (the cost the line names).
        assert log["transcribed"] == [["s1", "s2"], ["s1", "s2"]]

    def test_with_a_held_copy_it_does_not_claim_every_stage_runs_again(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        log: dict = {}
        _drive(tmp_path, "run", 2, log)
        out = tmp_path / "output"
        # As an unfinished run leaves it: the previous run's records, held.
        hold_for_resume(load_manifest(out), out)
        _manifest(tmp_path).write_text(_TRUNCATED, encoding="utf-8")
        capsys.readouterr()

        _drive(tmp_path, "run", 2, log)

        said = _one_line(capsys.readouterr().out)
        assert "The pipeline manifest couldn't be read, so it was set aside" in said
        assert "Every stage runs again" not in said
        # And it did not: the held records were reused.
        assert log["transcribed"] == [["s1", "s2"]]

    def test_a_held_copy_with_nothing_finished_still_says_every_stage(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A held copy that vouches for no stage saves nothing (review #2)."""
        log: dict = {}
        _drive(tmp_path, "run", 2, log)
        out = tmp_path / "output"
        hold_for_resume(create_manifest("caches", "1.0"), out)
        _manifest(tmp_path).write_text(_TRUNCATED, encoding="utf-8")
        capsys.readouterr()

        _drive(tmp_path, "run", 2, log)

        assert "Every stage runs again" in _one_line(capsys.readouterr().out)
        assert log["transcribed"] == [["s1", "s2"], ["s1", "s2"]]

    def test_a_run_that_ends_before_its_first_write_leaves_a_manifest(
        self, tmp_path: Path,
    ) -> None:
        """A copy is kept, not a move: an empty folder or a Stop during ingest
        must not leave the next `run` refusing the folder (code review of RE#17;
        R111's guard asks whether the file exists)."""
        from bristlenose.manifest import has_manifest

        _drive(tmp_path, "run", 2, {})
        _manifest(tmp_path).write_text(_TRUNCATED, encoding="utf-8")

        try:
            _drive(tmp_path, "run", 0, {})  # nothing found: ends before the write
        except Exception:  # noqa: BLE001 — how it ends is not the point here
            pass

        assert has_manifest(tmp_path / "output")
        assert len(list(_manifest(tmp_path).parent.glob(f"{MANIFEST_FILENAME}.damaged-*"))) == 1

    def test_a_readable_manifest_is_not_set_aside(self, tmp_path: Path) -> None:
        _drive(tmp_path, "run", 2, {})
        _drive(tmp_path, "run", 2, {})
        assert not list(_manifest(tmp_path).parent.glob("*.damaged-*"))
