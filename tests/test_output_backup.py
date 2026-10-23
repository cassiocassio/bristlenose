"""The previous report must survive a run that dies.

Pins `bristlenose/utils/output_backup.py`. The incident: on 30 Aug 2026 two runs
`rmtree`'d their output directory after preflight, then died inside transcription
seconds later, leaving neither the old report nor a new one. See
`docs/sidecar-transcription-crash.md`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from bristlenose.utils import output_backup
from bristlenose.utils.output_backup import RestoreOutcome

_MARKER = "bristlenose-report.html"


def _make_report(root: Path, *, marker: str, events: str) -> Path:
    """A plausible output directory: a deliverable plus the run-state dir."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "bristlenose-report.html").write_text(marker, encoding="utf-8")
    (root / "assets").mkdir(exist_ok=True)
    (root / "assets" / "theme.css").write_text("body{}", encoding="utf-8")
    state = root / ".bristlenose"
    state.mkdir(exist_ok=True)
    (state / "bristlenose.db").write_text(f"db:{marker}", encoding="utf-8")
    (state / "pipeline-events.jsonl").write_text(events, encoding="utf-8")
    return root


class TestStash:
    def test_moves_rather_than_deletes(self, tmp_path: Path) -> None:
        out = _make_report(tmp_path / "bristlenose-output", marker="good", events="old\n")

        backup = output_backup.stash(out)

        assert backup is not None
        assert not out.exists(), "the run needs a clean directory to write into"
        assert (backup / "bristlenose-report.html").read_text(encoding="utf-8") == "good"
        assert (backup / ".bristlenose" / "bristlenose.db").read_text(encoding="utf-8") == "db:good"

    def test_backup_is_hidden_so_ingest_cannot_re_scan_it(self, tmp_path: Path) -> None:
        """Load-bearing: `s01_ingest` skips every dot-prefixed entry.

        A visible backup would be walked by the next run's discovery and its
        contents offered as interview material.
        """
        out = tmp_path / "bristlenose-output"
        assert output_backup.backup_path_for(out).name.startswith(".")

    def test_backup_is_a_sibling_not_a_child(self, tmp_path: Path) -> None:
        """A child would be inside the tree the run is about to write into."""
        out = tmp_path / "bristlenose-output"
        backup = output_backup.backup_path_for(out)
        assert backup.parent == out.parent
        assert out not in backup.parents

    def test_nothing_to_stash_is_not_an_error(self, tmp_path: Path) -> None:
        assert output_backup.stash(tmp_path / "does-not-exist") is None

    def test_a_spent_backup_is_replaced(self, tmp_path: Path) -> None:
        """`reclaim_stale` runs first, so anything still here has had its chance."""
        out = _make_report(tmp_path / "bristlenose-output", marker="new", events="e\n")
        stale = output_backup.backup_path_for(out)
        _make_report(stale, marker="stale", events="e\n")

        backup = output_backup.stash(out, previous_backup_is_spent=True)

        assert backup is not None
        assert (backup / "bristlenose-report.html").read_text(encoding="utf-8") == "new"


class TestDiscard:
    def test_removes_the_backup(self, tmp_path: Path) -> None:
        out = _make_report(tmp_path / "bristlenose-output", marker="good", events="old\n")
        backup = output_backup.stash(out)

        output_backup.discard(backup)

        assert backup is not None and not backup.exists()

    def test_none_is_a_no_op(self, tmp_path: Path) -> None:
        output_backup.discard(None)  # must not raise


class TestRestore:
    def test_puts_the_old_report_back(self, tmp_path: Path) -> None:
        out = tmp_path / "bristlenose-output"
        _make_report(out, marker="good", events='{"event":"run_completed"}\n')
        backup = output_backup.stash(out)
        # The failed run writes its own partial tree.
        _make_report(out, marker="partial", events='{"event":"run_failed"}\n')

        assert output_backup.restore(backup, out) is RestoreOutcome.RESTORED
        assert (out / "bristlenose-report.html").read_text(encoding="utf-8") == "good"
        assert (out / ".bristlenose" / "bristlenose.db").read_text(encoding="utf-8") == "db:good"
        assert (out / "assets" / "theme.css").is_file()

    def test_the_failure_stays_visible(self, tmp_path: Path) -> None:
        """THE subtle one.

        The app decides a project's state from the tail of
        `pipeline-events.jsonl`. Restore the old file wholesale and the tail
        reads `run_completed` — so a run that just failed would render as fine.
        The events log is append-only, so old-then-new concatenation is both
        correct and what keeps the failure on screen.
        """
        out = tmp_path / "bristlenose-output"
        _make_report(out, marker="good", events='{"event":"run_completed"}\n')
        backup = output_backup.stash(out)
        _make_report(out, marker="partial", events='{"event":"run_failed"}\n')

        output_backup.restore(backup, out)

        events = (out / ".bristlenose" / "pipeline-events.jsonl").read_text(encoding="utf-8")
        lines = [ln for ln in events.splitlines() if ln.strip()]
        assert "run_completed" in lines[0], "history should survive"
        assert "run_failed" in lines[-1], "the tail must still say the run failed"

    def test_restores_when_the_failed_run_wrote_nothing(self, tmp_path: Path) -> None:
        """A crash before the output dir was recreated. Plain rename back."""
        out = tmp_path / "bristlenose-output"
        _make_report(out, marker="good", events="old\n")
        backup = output_backup.stash(out)

        assert output_backup.restore(backup, out) is RestoreOutcome.RESTORED
        assert (out / "bristlenose-report.html").read_text(encoding="utf-8") == "good"

    def test_none_is_a_no_op(self, tmp_path: Path) -> None:
        assert output_backup.restore(None, tmp_path / "out") is RestoreOutcome.NOTHING_TO_DO

    def test_missing_backup_is_a_no_op(self, tmp_path: Path) -> None:
        assert output_backup.restore(tmp_path / "gone", tmp_path / "out") is RestoreOutcome.NOTHING_TO_DO


class TestReclaimStale:
    def test_recovers_the_report_a_hard_crash_left_behind(self, tmp_path: Path) -> None:
        """The SIGILL case: no handler ran, so the backup is still on disk.

        This is the only thing standing between a signalled death and a lost
        report, because the in-process restore never got to run.
        """
        out = tmp_path / "bristlenose-output"
        _make_report(out, marker="good", events='{"event":"run_completed"}\n')
        output_backup.stash(out)
        # Simulate the dead run's leftovers, then a fresh process starting up.
        _make_report(out, marker="half-written", events='{"event":"run_started"}\n')

        assert output_backup.reclaim_stale(out) is RestoreOutcome.RESTORED
        assert (out / "bristlenose-report.html").read_text(encoding="utf-8") == "good"
        assert not output_backup.backup_path_for(out).exists()

    def test_no_backup_is_a_no_op(self, tmp_path: Path) -> None:
        out = _make_report(tmp_path / "bristlenose-output", marker="x", events="e\n")
        assert output_backup.reclaim_stale(out) is RestoreOutcome.NOTHING_TO_DO
        assert (out / "bristlenose-report.html").read_text(encoding="utf-8") == "x"


class TestFullCycle:
    def test_success_leaves_exactly_one_report_and_no_litter(self, tmp_path: Path) -> None:
        out = tmp_path / "bristlenose-output"
        _make_report(out, marker="v1", events="a\n")

        backup = output_backup.stash(out)
        _make_report(out, marker="v2", events="b\n")  # the new run succeeds
        output_backup.discard(backup)

        assert (out / "bristlenose-report.html").read_text(encoding="utf-8") == "v2"
        assert not output_backup.backup_path_for(out).exists()
        assert sorted(p.name for p in tmp_path.iterdir()) == ["bristlenose-output"]

    def test_failure_drops_the_runs_tree_once_its_history_is_across(
        self, tmp_path: Path
    ) -> None:
        """A run put back produced nothing to keep (`settle`), so nothing finishes
        from its tree: it goes once its history is on the report's log. Kept, it
        was what a later plain run swapped in over the report (22 Oct 2026)."""
        out = tmp_path / "bristlenose-output"
        _make_report(out, marker="v1", events="a\n")

        backup = output_backup.stash(out)
        _make_report(out, marker="partial", events="b\n")
        output_backup.restore(backup, out)

        assert (out / _MARKER).read_text(encoding="utf-8") == "v1", "the report is back"
        assert (out / ".bristlenose" / "pipeline-events.jsonl").read_text() == "a\nb\n"
        assert not output_backup.failed_path_for(out).exists()
        assert not output_backup.backup_path_for(out).exists()

    def test_a_stranded_scratch_tree_does_not_break_the_next_restore(
        self, tmp_path: Path
    ) -> None:
        """`rename` onto a non-empty directory is ENOTEMPTY.

        Swallowed, that leaves the researcher's report hidden in the backup with
        no message — a silent failure of the module whose job is to not lose it.
        """
        out = tmp_path / "bristlenose-output"
        _make_report(output_backup.failed_path_for(out), marker="stranded", events="x\n")
        _make_report(out, marker="v1", events="a\n")

        backup = output_backup.stash(out)
        _make_report(out, marker="partial", events="b\n")

        assert output_backup.restore(backup, out) is RestoreOutcome.RESTORED
        assert (out / _MARKER).read_text(encoding="utf-8") == "v1"


class TestTheErrorBranches:
    """Every defect a silent-failure review found here lived on these paths.

    The happy-path suite above was green throughout and could see none of them.
    """

    def test_a_failed_history_append_does_not_report_a_clean_restore(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """THE module's own headline failure, via its error handler.

        The concatenation is the only thing keeping the restore honest — without
        it the tail is the old `run_completed` and a run that just failed renders
        as fine. An earlier version caught the OSError, logged, and returned
        success anyway.
        """
        out = tmp_path / "bristlenose-output"
        _make_report(out, marker="good", events='{"event":"run_completed"}\n')
        backup = output_backup.stash(out)
        _make_report(out, marker="partial", events='{"event":"run_failed"}\n')

        monkeypatch.setattr(
            output_backup.os, "open", lambda *a, **k: (_ for _ in ()).throw(OSError("EACCES"))
        )

        outcome = output_backup.restore(backup, out)

        assert outcome is RestoreOutcome.RESTORED_WITHOUT_HISTORY
        assert outcome.report_is_back, "the report IS back — that part succeeded"
        assert outcome is not RestoreOutcome.RESTORED, (
            "but the caller must not be told the failure is still visible"
        )

    def test_a_partial_append_is_truncated_rather_than_left_half_written(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Half an event line is worse than none — `read_events` would choke."""
        out = tmp_path / "bristlenose-output"
        _make_report(out, marker="good", events='{"event":"run_completed"}\n')
        backup = output_backup.stash(out)
        _make_report(out, marker="partial", events='{"event":"run_failed"}\n')

        def _die_midway(src, dst, length=0):
            dst.write(b'{"event":"run_fai')
            raise OSError("ENOSPC")

        monkeypatch.setattr(output_backup.shutil, "copyfileobj", _die_midway)
        output_backup.restore(backup, out)

        events = (out / ".bristlenose" / "pipeline-events.jsonl").read_text(encoding="utf-8")
        assert events == '{"event":"run_completed"}\n', "truncated back to the boundary"

    def test_a_restore_that_fails_partway_says_so(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Returning a bare False left the output directory absent and silent.

        Both copies are then dot-directories Finder will not show, and the CLI
        printed nothing — the researcher sees an empty project.
        """
        out = tmp_path / "bristlenose-output"
        _make_report(out, marker="good", events="a\n")
        backup = output_backup.stash(out)
        _make_report(out, marker="partial", events="b\n")

        real_rename = Path.rename
        calls = {"n": 0}

        def _second_rename_fails(self, target):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("ENOSPC")
            return real_rename(self, target)

        monkeypatch.setattr(Path, "rename", _second_rename_fails)

        assert output_backup.restore(backup, out) is RestoreOutcome.FAILED

    def test_stash_refuses_to_destroy_a_backup_that_was_never_reclaimed(
        self, tmp_path: Path
    ) -> None:
        """The total-loss path.

        `stash` assumed any surviving backup was spent because `reclaim_stale`
        had run. True only when the reclaim SUCCEEDED — when it failed, the next
        `--clean` deleted the sole surviving copy of the report.
        """
        out = _make_report(tmp_path / "bristlenose-output", marker="new", events="e\n")
        stranded = output_backup.backup_path_for(out)
        _make_report(stranded, marker="IRREPLACEABLE", events="e\n")

        assert output_backup.stash(out) is None, "refuses rather than destroys"
        assert (stranded / _MARKER).read_text(encoding="utf-8") == "IRREPLACEABLE"

    @pytest.mark.skipif(os.name != "posix", reason="symlink refusal is O_NOFOLLOW, which Windows lacks")
    def test_the_history_append_does_not_follow_a_symlink(self, tmp_path: Path) -> None:
        """`open("ab")` follows symlinks — an append-to-arbitrary-file primitive.

        `dest` sits in a directory a co-worker on a shared study folder can
        write to. `run_lifecycle.append_event` opens the same file O_NOFOLLOW
        for exactly this reason; this is the second writer.
        """
        out = tmp_path / "bristlenose-output"
        _make_report(out, marker="good", events="old\n")
        backup = output_backup.stash(out)
        _make_report(out, marker="partial", events="new\n")

        victim = tmp_path / "victim.txt"
        victim.write_text("# untouched\n", encoding="utf-8")
        events = backup / ".bristlenose" / "pipeline-events.jsonl"
        events.unlink()
        events.symlink_to(victim)

        output_backup.restore(backup, out)

        assert victim.read_text(encoding="utf-8") == "# untouched\n", "the symlink target is not appended to"

    def test_reclaim_declines_while_a_live_run_owns_the_directory(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Otherwise a second `run` renames the FIRST run's live output away.

        That run then writes into an unlinked inode, its terminus lands nowhere,
        and the project reads as "no terminus, so no lens opens" — the symptom
        this module exists to prevent, caused by its own recovery path.
        """
        out = tmp_path / "bristlenose-output"
        _make_report(output_backup.backup_path_for(out), marker="old", events="a\n")
        _make_report(out, marker="LIVE RUN IS WRITING HERE", events="b\n")

        monkeypatch.setattr(output_backup, "project_is_locked", lambda _p: True)

        assert output_backup.reclaim_stale(out) is RestoreOutcome.NOTHING_TO_DO
        assert (out / _MARKER).read_text(encoding="utf-8") == "LIVE RUN IS WRITING HERE"


def _land_a_session(out: Path, *, quotes: int = 1) -> None:
    """A session whose quotes are in: the quotes file, then its manifest record."""
    import json

    from bristlenose.manifest import (
        STAGE_QUOTE_EXTRACTION,
        create_manifest,
        mark_session_complete,
        write_manifest,
    )

    intermediate = out / ".bristlenose" / "intermediate"
    intermediate.mkdir(parents=True, exist_ok=True)
    (intermediate / "extracted_quotes.json").write_text(json.dumps(
        [{"session_id": "s1", "participant_id": "p1"}] * quotes), encoding="utf-8")
    manifest = create_manifest("t", "0")
    mark_session_complete(manifest, STAGE_QUOTE_EXTRACTION, "s1")
    write_manifest(manifest, out)


class TestTheAnalysedSessionRule:
    """`holds_an_analysed_session`: what makes a fresh start the report."""

    def test_a_session_with_quotes_counts(self, tmp_path: Path) -> None:
        out = _make_report(tmp_path / "out", marker="a", events="x\n")
        _land_a_session(out)
        assert output_backup.holds_an_analysed_session(out)

    def test_a_session_with_no_quotes_does_not(self, tmp_path: Path) -> None:
        out = _make_report(tmp_path / "out", marker="a", events="x\n")
        _land_a_session(out, quotes=0)
        assert not output_backup.holds_an_analysed_session(out)

    def test_quotes_with_no_record_do_not(self, tmp_path: Path) -> None:
        """The record is written after the quotes: quotes alone may be half a write."""
        out = _make_report(tmp_path / "out", marker="a", events="x\n")
        _land_a_session(out)
        (out / ".bristlenose" / "pipeline-manifest.json").unlink()
        assert not output_backup.holds_an_analysed_session(out)

    def test_an_unreadable_quotes_file_does_not(self, tmp_path: Path) -> None:
        out = _make_report(tmp_path / "out", marker="a", events="x\n")
        _land_a_session(out)
        (out / ".bristlenose" / "intermediate" / "extracted_quotes.json").write_text("[{")
        assert not output_backup.holds_an_analysed_session(out)

    def test_no_output_does_not(self, tmp_path: Path) -> None:
        assert not output_backup.holds_an_analysed_session(tmp_path / "absent")


class TestSettle:
    def test_a_put_back_cut_between_its_renames_is_finished_by_the_next_run(
        self, tmp_path: Path
    ) -> None:
        """No output, the report set aside, the run's tree stepped aside: what a
        kill inside `_restore` leaves. The report comes back with the run's
        history, once, and the tree goes."""
        out = tmp_path / "bristlenose-output"
        _make_report(out, marker="report", events="r1\n")
        output_backup.stash(out)
        _make_report(output_backup.failed_path_for(out), marker="attempt", events="a1\n")

        assert output_backup.reclaim_stale(out) is RestoreOutcome.RESTORED

        assert (out / _MARKER).read_text(encoding="utf-8") == "report"
        assert (out / ".bristlenose" / "pipeline-events.jsonl").read_text() == "r1\na1\n"
        assert not output_backup.failed_path_for(out).exists()

    def test_an_export_that_will_not_move_keeps_the_report_until_it_does(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Never delete an export with the report it sat in."""
        out = tmp_path / "bristlenose-output"
        _make_report(out, marker="report", events="r1\n")
        (out / "clips").mkdir()
        (out / "clips" / "c.mp4").write_text("clip", encoding="utf-8")
        backup = output_backup.stash(out)
        _make_report(out, marker="fresh", events="f1\n")
        _land_a_session(out)
        real_rename = Path.rename

        def _refuse_clips(self, target):
            if self.name == "clips":
                raise OSError("busy")
            return real_rename(self, target)

        monkeypatch.setattr(Path, "rename", _refuse_clips)
        assert output_backup.settle(backup, out) is RestoreOutcome.CARRY_INCOMPLETE
        assert (backup / "clips" / "c.mp4").read_text(encoding="utf-8") == "clip"
        assert not (backup / ".bristlenose-backup-spent").exists()

        monkeypatch.setattr(Path, "rename", real_rename)
        assert output_backup.reclaim_stale(out) is RestoreOutcome.REPLACED

        assert (out / _MARKER).read_text(encoding="utf-8") == "fresh"
        carried = [p for p in out.iterdir() if p.name.startswith("clips (")]
        assert len(carried) == 1 and (carried[0] / "c.mp4").read_text() == "clip"
        assert not backup.exists()

    def test_a_leftover_tree_is_swept_by_the_next_run(self, tmp_path: Path) -> None:
        """A `-failed` tree from a build with the hold-back: nothing reads it."""
        out = _make_report(tmp_path / "bristlenose-output", marker="report", events="r\n")
        _make_report(output_backup.failed_path_for(out), marker="attempt", events="a\n")

        assert output_backup.reclaim_stale(out) is RestoreOutcome.NOTHING_TO_DO

        assert not output_backup.failed_path_for(out).exists()
        assert (out / _MARKER).read_text(encoding="utf-8") == "report"

    def test_not_while_a_live_run_owns_the_project(self, tmp_path: Path, monkeypatch) -> None:
        out = _make_report(tmp_path / "bristlenose-output", marker="report", events="r\n")
        _make_report(output_backup.failed_path_for(out), marker="attempt", events="a\n")
        monkeypatch.setattr(output_backup, "project_is_locked", lambda _p: True)

        output_backup.reclaim_stale(out)

        assert output_backup.failed_path_for(out).is_dir()


_CAN_CHMOD = sys.platform != "win32" and os.geteuid() != 0


class TestTheFreshEyesFindings:
    """The coordinator's Fable check of 33a6e01cb, 23 Oct 2026."""

    def test_a_put_back_carries_the_exports_of_a_tree_already_beside_it(
        self, tmp_path: Path
    ) -> None:
        """A `-failed` tree a `stash` kept (or a hold-back build left) is
        cleared by the next put-back: its export joins the report, never
        deleted with it (finding 1)."""
        out = tmp_path / "bristlenose-output"
        _make_report(out, marker="report", events="r1\n")
        backup = output_backup.stash(out)
        old = _make_report(output_backup.failed_path_for(out), marker="old run", events="o\n")
        (old / "clips").mkdir()
        (old / "clips" / "c.mp4").write_text("clip", encoding="utf-8")
        _make_report(out, marker="attempt", events="a1\n")  # produced nothing

        assert output_backup.settle(backup, out) is RestoreOutcome.RESTORED

        assert (out / _MARKER).read_text(encoding="utf-8") == "report"
        carried = [p for p in out.iterdir() if p.name.startswith("clips (")]
        assert len(carried) == 1 and (carried[0] / "c.mp4").read_text() == "clip"
        assert output_backup.leftovers_for(out) == []

    @pytest.mark.skipif(not _CAN_CHMOD, reason="needs a folder this user cannot write")
    def test_a_tree_whose_export_will_not_move_is_kept_by_a_put_back(
        self, tmp_path: Path
    ) -> None:
        out = tmp_path / "bristlenose-output"
        _make_report(out, marker="report", events="r1\n")
        backup = output_backup.stash(out)
        old = _make_report(output_backup.failed_path_for(out), marker="old run", events="o\n")
        (old / "clips").mkdir()
        (old / "clips" / "c.mp4").write_text("clip", encoding="utf-8")
        _make_report(out, marker="attempt", events="a1\n")
        old.chmod(0o500)
        try:
            assert output_backup.settle(backup, out).report_is_back
        finally:
            old.chmod(0o700)

        assert (out / _MARKER).read_text(encoding="utf-8") == "report"
        assert (old / "clips" / "c.mp4").read_text() == "clip"
        # This run's own tree took another name and went.
        assert output_backup.leftovers_for(out) == [old]

    def test_a_replaced_backup_is_never_put_back(self, tmp_path: Path, monkeypatch) -> None:
        """A run whose session is not on disk (no intermediates) replaced the
        report, then an export would not move: the next reclaim must finish the
        replacement, not restore the old report over it (finding 5)."""
        out = tmp_path / "bristlenose-output"
        _make_report(out, marker="report", events="r1\n")
        (out / "clips").mkdir()
        backup = output_backup.stash(out)
        _make_report(out, marker="fresh", events="f1\n")
        monkeypatch.setattr(output_backup, "carry_exports", lambda *_a: False)
        assert output_backup.settle(backup, out, produced=True) is (
            RestoreOutcome.CARRY_INCOMPLETE)
        monkeypatch.undo()

        assert output_backup.reclaim_stale(out) is RestoreOutcome.REPLACED

        assert (out / _MARKER).read_text(encoding="utf-8") == "fresh"
        assert not backup.exists()

    def test_the_next_run_sweeps_a_delete_cut_short(self, tmp_path: Path) -> None:
        """A `-discarding-<pid>` tree holds participants' data; a researcher who
        only ever runs plain runs must not keep it for ever (finding 4)."""
        out = _make_report(tmp_path / "bristlenose-output", marker="r", events="r\n")
        cut = output_backup.backup_path_for(out).with_name(".bristlenose-output-previous-discarding-1")
        _make_report(cut, marker="old", events="o\n")
        assert output_backup.leftovers_for(out) == [cut]

        output_backup.reclaim_stale(out)

        assert not cut.exists()

    @pytest.mark.skipif(sys.platform == "win32", reason="flock")
    def test_two_reclaims_take_turns(self, tmp_path: Path) -> None:
        """The serve's reclaim at launch and a queue-restored run's can both
        find a crash's backup before any PID file exists (finding 3)."""
        import fcntl
        import threading

        out = tmp_path / "bristlenose-output"
        _make_report(out, marker="report", events="r1\n")
        output_backup.stash(out)
        _make_report(out, marker="attempt", events="a1\n")
        fd = os.open(tmp_path, os.O_RDONLY)
        fcntl.flock(fd, fcntl.LOCK_EX)  # another process mid-settle
        results: list[RestoreOutcome] = []
        t = threading.Thread(target=lambda: results.append(output_backup.reclaim_stale(out)))
        t.start()
        t.join(0.5)
        try:
            assert t.is_alive() and not results, "the reclaim ran under another's settle"
            assert (out / _MARKER).read_text(encoding="utf-8") == "attempt"
        finally:
            os.close(fd)
        t.join(5)
        assert results == [RestoreOutcome.RESTORED]
        assert (out / _MARKER).read_text(encoding="utf-8") == "report"
