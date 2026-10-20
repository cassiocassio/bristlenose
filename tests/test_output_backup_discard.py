"""A cleanup cut short never brings the old report back over the new one (R110).

Once a Re-analyse has produced its report, the stashed previous one is spent
and `discard` deletes it. The delete is a long rmtree (the stash can hold
gigabytes), and a stop or crash in the middle of it left a part of the old tree
at the backup path. The next run's `reclaim_stale` read that as a crashed run's
report and put it back over the new one. And `discard` logged "discarded"
whatever had happened. Now the backup is renamed out of the reclaim path first,
atomically, and the log says what the delete achieved.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pytest

from bristlenose.utils import output_backup


def _report(out: Path, text: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.html").write_text(text, encoding="utf-8")
    (out / "sessions").mkdir(exist_ok=True)
    (out / "sessions" / "s1.html").write_text(text, encoding="utf-8")


def _rerun(tmp_path: Path) -> tuple[Path, Path]:
    """A Re-analyse: the old report stashed, the new one written in its place."""
    out = tmp_path / "bristlenose-output"
    _report(out, "old")
    backup = output_backup.stash(out)
    assert backup is not None
    _report(out, "new")
    return out, backup


def test_a_discard_cut_short_is_not_reclaimed_over_the_new_report(
    tmp_path: Path, monkeypatch,
) -> None:
    out, backup = _rerun(tmp_path)
    real_rmtree = shutil.rmtree

    def _cut_short(path, *a, **k):
        if not Path(path).exists():
            return
        # Part of the tree goes, then the process is stopped.
        (Path(path) / "report.html").unlink(missing_ok=True)
        raise KeyboardInterrupt

    monkeypatch.setattr(output_backup.shutil, "rmtree", _cut_short)
    with pytest.raises(KeyboardInterrupt):
        output_backup.discard(backup)
    monkeypatch.setattr(output_backup.shutil, "rmtree", real_rmtree)

    assert output_backup.reclaim_stale(out) is output_backup.RestoreOutcome.NOTHING_TO_DO
    assert (out / "report.html").read_text(encoding="utf-8") == "new"


def test_a_delete_that_leaves_files_is_not_logged_as_discarded(
    tmp_path: Path, monkeypatch, caplog: pytest.LogCaptureFixture,
) -> None:
    _out, backup = _rerun(tmp_path)
    monkeypatch.setattr(output_backup.shutil, "rmtree", lambda *a, **k: None)
    with caplog.at_level(logging.INFO, logger="bristlenose.utils.output_backup"):
        output_backup.discard(backup)
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "discarded" not in said
    assert "could not fully delete" in said


def test_a_leftover_from_a_cut_short_discard_is_cleared_by_the_next_stash(
    tmp_path: Path, monkeypatch,
) -> None:
    out, backup = _rerun(tmp_path)
    monkeypatch.setattr(output_backup.shutil, "rmtree", lambda *a, **k: None)
    output_backup.discard(backup)
    monkeypatch.undo()
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".") and p != backup]
    assert leftovers, "the partly deleted tree is somewhere"
    assert output_backup.stash(out) is not None
    assert not any(p.exists() for p in leftovers)


def test_a_clean_discard_says_so(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _out, backup = _rerun(tmp_path)
    with caplog.at_level(logging.INFO, logger="bristlenose.utils.output_backup"):
        output_backup.discard(backup)
    assert not backup.exists()
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".")]
    assert any("discarded" in r.getMessage() for r in caplog.records)
