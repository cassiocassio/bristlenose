"""The serve survives the stash cycle, and nothing writes under a live run.

``run --clean`` moves the output folder aside and the run writes a new one; a
failed run's ``restore`` and the next run's ``reclaim_stale`` move it back. A
serve straddling any of those used to keep its pooled connections on the
moved file and write the session registry under a run that would overwrite
it. Each test here was measured red before its fix (12 Oct 2026; the
diagnosis is the private lifecycle handoff, findings S5, S7, S8, S11, P1).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from bristlenose.events import events_path
from bristlenose.run_lifecycle import _ps_start_time, _write_pid_file, pid_file_path
from bristlenose.server.event_watcher import run_event_watcher
from bristlenose.server.importer import import_project
from bristlenose.server.models import Session as SessionModel
from bristlenose.server.models import SourceFile
from bristlenose.utils import output_backup
from tests.conftest import AuthTestClient
from tests.test_serve_condition import _failed, _started
from tests.test_serve_event_watcher import _completed
from tests.test_serve_importer import _make_quote, _write_pipeline_output, _write_transcript
from tests.test_serve_importer import db as db  # noqa: F401 — the in-memory DB fixture
from tests.test_serve_moderator_identities import _client, _reimport, _slots
from tests.test_serve_participant_recode import _registry, _with_quotes
from tests.test_serve_project_root import _app, _project, _rows, _sessions, _wait
from tests.test_serve_project_root import _client as _polling_client
from tests.test_serve_project_root import fast_watcher as fast_watcher  # noqa: F401


def _lock(out: Path) -> None:
    """This process stands in for a live run: the real PID file, so
    ``run_in_progress`` says yes without any stub."""
    _write_pid_file(out, "live-run", _ps_start_time(os.getpid()) or "")


def _unlock(out: Path) -> None:
    pid_file_path(out).unlink()


# ---------------------------------------------------------------------------
# WS2.1 — the serve reattaches when the output folder is swapped under it
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="Windows will not move a folder whose database serve holds open, so neither the stash nor the restore can happen there")
class TestTheStashCycle:
    """A serve that straddles ``--clean``'s stash and a failed run's restore
    ends up reading the report that is on disk, in one project row."""

    def test_serve_while_the_output_is_stashed_then_restored(self, tmp_path: Path, fast_watcher) -> None:
        """``run --clean`` moves the report aside; the Mac app (re)starts the serve in
        that window on every Re-analyse; the run fails and ``restore`` puts the old
        report back. The serve must end up reading it — one row, under the output
        folder — not a second row beside an empty first."""
        from bristlenose.utils import output_backup

        proj = _project(tmp_path)
        out = proj / "bristlenose-output"
        backup = output_backup.stash(out)
        assert backup is not None and not out.exists()

        app = _app(proj, tmp_path)
        with _polling_client(app) as client:  # this module's _client builds an app
            db = out / ".bristlenose" / "bristlenose.db"
            assert db.exists(), "the database belongs under the output folder, created eagerly"
            assert not (proj / ".bristlenose").exists(), "litter at the project root"

            # The run dies; its handler puts the previous report back (the serve's
            # own eagerly-created tree is set aside as the failed run's).
            assert output_backup.restore(backup, out).report_is_back
            assert _wait(lambda: _sessions(client)), (
                "the report the SPA reads (project 1) stayed empty after the restore"
            )

        rows = _rows(db)
        assert len(rows) == 1, f"the restore's import forked a second project row: {rows}"
        assert Path(rows[0][2]).resolve() == out.resolve()
        assert not (proj / ".bristlenose").exists()

    def test_a_restore_under_a_serve_started_after_the_stash_is_read(
        self, tmp_path: Path, fast_watcher,
    ) -> None:
        """Serve A analysed the project; ``--clean`` stashed it; serve B started in
        that window; the run failed and ``restore`` put A's report back. B's pool
        is pinned to its own (now set-aside) database, and A's events log carries
        nothing B could re-import — so only an inode-change heal lets B read the
        report that is on disk."""
        proj = _project(tmp_path)
        out = proj / "bristlenose-output"
        with AuthTestClient(_app(proj, tmp_path)) as client:
            assert client.get("/api/projects/1/sessions").json()["sessions"]
        # A's history: a run that started and failed. Nothing to re-import.
        events_path(out).unlink()
        _started(out, "X")
        _failed(out, "X")
        backup = output_backup.stash(out)
        assert backup is not None

        with _polling_client(_app(proj, tmp_path)) as client:
            assert _sessions(client) == []
            assert output_backup.restore(backup, out).report_is_back
            assert _wait(lambda: _sessions(client)), (
                "the serve kept answering from the database the restore set aside"
            )
        assert len(_rows(out / ".bristlenose" / "bristlenose.db")) == 1

    def test_the_serve_log_follows_the_output_folder(self, tmp_path: Path, fast_watcher) -> None:
        """``run --clean`` under a live serve: the serve's log went on into the
        set-aside copy, which a successful run deletes, so its whole log for the
        run — a refused speaker pick included — was gone (14 Oct 2026)."""
        proj = _project(tmp_path)
        out = proj / "bristlenose-output"
        with _polling_client(_app(proj, tmp_path)) as client:
            assert _sessions(client)
            backup = output_backup.stash(out)
            assert backup is not None
            # The new run's tree: its own log (the run opens it straight after the
            # stash), its events log, no database yet.
            log = out / ".bristlenose" / "bristlenose.log"
            log.parent.mkdir(parents=True)
            log.write_text("the run's first line\n")
            _started(out, "NEW")
            assert _wait(lambda: log.exists() and "reattaching" in log.read_text()), (
                "the serve's reattach was not written to the output folder now on disk"
            )
            logging.getLogger("bristlenose.server.app").warning("a line after the stash")
            for handler in logging.getLogger().handlers:
                handler.flush()
            assert "a line after the stash" in log.read_text()
            assert "a line after the stash" not in (
                backup / ".bristlenose" / "bristlenose.log"
            ).read_text()


# ---------------------------------------------------------------------------
# WS2.2 — a project folder that goes away is said once, not silently
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_watcher_warns_once_when_the_project_folder_goes(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    root = tmp_path / "proj"
    out = root / "bristlenose-output"
    out.mkdir(parents=True)
    calls: list[str] = []

    async def cb(ev) -> None:
        calls.append(ev.run_id)

    log = logging.getLogger("bristlenose.server.event_watcher")
    log.addHandler(caplog.handler)
    task = asyncio.create_task(run_event_watcher(
        lambda: events_path(root / "bristlenose-output"), cb, poll_interval=0.05, root=root,
    ))
    try:
        await asyncio.sleep(0.2)
        root.rename(tmp_path / "renamed")
        await asyncio.sleep(0.4)
        # The same record reaches caplog twice when the logger propagates (its
        # handler was added for the case where setup_logging has stopped it).
        gone = {id(r) for r in caplog.records
                if r.levelno == logging.WARNING and "proj" in r.getMessage()}
        assert len(gone) == 1, [r.getMessage() for r in caplog.records]
        # Renamed back: the watcher is still listening.
        (tmp_path / "renamed").rename(root)
        from bristlenose.events import append_event
        append_event(events_path(out), _completed("after"))
        for _ in range(40):
            if calls:
                break
            await asyncio.sleep(0.05)
        assert calls == ["after"]
    finally:
        log.removeHandler(caplog.handler)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


# ---------------------------------------------------------------------------
# WS2.3 — the session registry is not written under a live run
# ---------------------------------------------------------------------------


class TestWritesRefusedWhileARunOwnsTheProject:
    def test_reassigning_to_a_new_moderator_is_refused(self, tmp_path: Path) -> None:
        project = _with_quotes(tmp_path)
        client = _client(project)
        _lock(project / "bristlenose-output")
        resp = client.post(
            "/api/projects/1/transcripts/s1/reassign",
            json={"position": 1, "verify": "Thanks for having me, it is", "new": "moderator"},
        )
        assert resp.status_code == 409, resp.text
        assert resp.json() == {"detail": "An analysis is running", "reason": "run_in_progress"}
        assert not (project / "bristlenose-output" / ".bristlenose" / "sessions.json").exists()

    def test_a_swap_is_refused(self, tmp_path: Path) -> None:
        project = _with_quotes(tmp_path)
        client = _client(project)
        _lock(project / "bristlenose-output")
        resp = client.put("/api/projects/1/sessions/s1/speakers/p1", json={"swap_with": "m1"})
        assert resp.status_code == 409, resp.text
        # The reason is what the SPA localises from; the English stays for logs.
        assert resp.json() == {"detail": "An analysis is running", "reason": "run_in_progress"}
        assert _slots(client)[("s1", "p1")]["speaker_code"] == "p1"

    def test_a_reanalyse_is_refused_by_name(self, tmp_path: Path) -> None:
        """Its pins are registry writes the run would save over."""
        project = _with_quotes(tmp_path)
        client = _client(project)
        _lock(project / "bristlenose-output")
        resp = client.post("/api/projects/1/sessions/s1/reanalyse")
        assert resp.status_code == 409, resp.text
        assert resp.json() == {"detail": "An analysis is running", "reason": "run_in_progress"}

    def test_a_rename_is_still_allowed(self, tmp_path: Path) -> None:
        """Only the writes a run would overwrite are refused; a name lives in
        the database, which the run never touches."""
        project = _with_quotes(tmp_path)
        client = _client(project)
        _lock(project / "bristlenose-output")
        resp = client.put("/api/projects/1/sessions/s1/speakers/m1", json={"full_name": "Martin S"})
        assert resp.status_code == 200, resp.text

    def test_naming_yourself_the_moderator_is_allowed(self, tmp_path: Path) -> None:
        """"That's Me" on a moderator, as the SPA sends it: someone new, with the
        slot's role as ``kind`` even though the role is unchanged. It is the first
        thing a researcher does while a first analysis runs, and it was refused
        as a recode (14 Oct 2026)."""
        project = _with_quotes(tmp_path)
        client = _client(project)
        _lock(project / "bristlenose-output")
        resp = client.put(
            "/api/projects/1/sessions/s1/speakers/m1",
            json={"person": "8f0c2a1e-0000-4000-8000-000000000001", "create": True,
                  "kind": "moderator", "full_name": "Martin", "short_name": "Martin",
                  "confirmed": True},
        )
        assert resp.status_code == 200, resp.text
        assert _slots(client)[("s1", "m1")]["name"] == "Martin"

    def test_a_recode_is_still_refused(self, tmp_path: Path) -> None:
        """The ``kind`` that changes the role is the write a run would overwrite."""
        project = _with_quotes(tmp_path)
        client = _client(project)
        _lock(project / "bristlenose-output")
        resp = client.put(
            "/api/projects/1/sessions/s1/speakers/m1",
            json={"person": "8f0c2a1e-0000-4000-8000-000000000002", "create": True,
                  "kind": "observer", "full_name": "Kim", "short_name": "Kim",
                  "confirmed": True},
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["reason"] == "run_in_progress"

    def test_the_importer_does_not_carry_picks_under_a_live_run(self, tmp_path: Path) -> None:
        """The run loaded the registry at its start and saves over it at its
        end, so a carry written now is lost — and a half-carried registry is
        what a run then reads. The next import carries them."""
        project = _with_quotes(tmp_path)
        reg = _registry(project, {"s1": {"Me": "m1", "Wylie": "p1"}, "s2": {"Kerri": "m1", "Ann": "p2"}})
        client = _client(project)
        client.put("/api/projects/1/sessions/s1/speakers/p1", json={"swap_with": "m1"})
        assert client.post("/api/projects/1/sessions/s1/reanalyse").status_code == 200
        # What the run does: honours the pins; Wylie is p3 now and Me is m1.
        data = json.loads(reg.read_text())
        data["speakers"]["s1"] = {"Wylie": "m1", "Me": "p3"}
        reg.write_text(json.dumps(data))
        out = project / "bristlenose-output"
        (out / "transcripts-raw" / "s1.txt").write_text(
            "# Transcript: s1\n# Date: 2026-09-20\n# Duration: 00:01:00\n\n"
            "[00:02] [p3] Welcome, thanks for coming in today.\n"
            "[00:10] [m1] Thanks for having me, it is good to be here.\n"
            "[00:20] [p3] Shall we start?\n"
        )
        before = reg.read_text()

        _lock(out)
        _reimport(client, project)
        assert reg.read_text() == before, "the registry was written under a live run"

        _unlock(out)
        _reimport(client, project)
        assert json.loads(reg.read_text())["pins"]["s1"]["Wylie"]["from_code"] == "m1", (
            "the carry happens once the run has let go"
        )

    def test_a_withdrawn_pin_is_not_dropped_under_a_live_run(self, tmp_path: Path) -> None:
        """``drop_withdrawn_pins`` saves the registry, so it too must wait for
        the run to let go. A person pick reaches it under a live run (only
        recodes and swaps are refused), so the guard inside it is the only
        thing stopping that write. A re-check mutation found it untested on
        12 Oct 2026: removing it left every test green.

        The setup builds a pin that WOULD be dropped — the recode undone in the
        database, the pin still in the registry — so the unlocked call at the
        end proves the test is not degenerate."""
        from bristlenose.server.routes.data import drop_withdrawn_pins

        project = _with_quotes(tmp_path)
        out = project / "bristlenose-output"
        reg = _registry(project, {"s1": {"Me": "m1", "Wylie": "p1"}, "s2": {"Kerri": "m1", "Ann": "p2"}})
        client = _client(project)
        client.put("/api/projects/1/sessions/s1/speakers/p1", json={"swap_with": "m1"})
        assert client.post("/api/projects/1/sessions/s1/reanalyse").status_code == 200
        pinned = reg.read_text()
        assert json.loads(pinned)["pins"]["s1"]
        # Undo the recode (which drops the pin), then put the pin back by hand:
        # a withdrawn pin waiting to be dropped.
        client.put("/api/projects/1/sessions/s1/speakers/p1", json={"swap_with": "m1"})
        reg.write_text(pinned)

        def drop() -> None:
            db = client.app.state.db_factory()
            try:
                drop_withdrawn_pins(db, 1, "s1")
            finally:
                db.close()

        _lock(out)
        drop()
        assert reg.read_text() == pinned, "the registry was written under a live run"

        _unlock(out)
        drop()
        assert "s1" not in json.loads(reg.read_text())["pins"], (
            "with no run, the withdrawn pin is dropped — so the locked call above was a real refusal"
        )


# ---------------------------------------------------------------------------
# WS2.4 — stash refuses a live run's output
# ---------------------------------------------------------------------------


def test_stash_refuses_to_move_a_live_runs_output(tmp_path: Path) -> None:
    """``run --clean`` while another run is live used to rename that run's
    output — PID file and all — out from under it; the second run then entered
    the lifecycle without ``ConcurrentRunError``."""
    out = tmp_path / "bristlenose-output"
    (out / ".bristlenose").mkdir(parents=True)
    (out / "report.html").write_text("live", encoding="utf-8")
    _lock(out)
    assert output_backup.stash(out) is None
    assert (out / "report.html").read_text(encoding="utf-8") == "live"
    assert not output_backup.backup_path_for(out).exists()


# ---------------------------------------------------------------------------
# WS2.5 — source files are re-verified on every import
# ---------------------------------------------------------------------------


class TestSourceFilesAreReVerified:
    def _transcript(self, out: Path, source: str) -> None:
        _write_transcript(out, "s1", (
            f"# Transcript: s1\n# Source: {source}\n# Date: 2026-01-20\n# Duration: 00:01:00\n\n"
            "[00:10] [p1] Login was easy\n"
        ))

    def _project(self, tmp_path: Path, source: str) -> Path:
        clusters = [{
            "screen_label": "Login", "description": "", "display_order": 1,
            "quotes": [_make_quote("s1", "p1", 10.0, "Login was easy")],
        }]
        proj = _write_pipeline_output(tmp_path, clusters, [])
        self._transcript(proj / "bristlenose-output", source)
        return proj

    def test_a_transcript_only_session_that_gains_a_recording(
        self, db: Session, tmp_path: Path,
    ) -> None:
        proj = self._project(tmp_path, "s1.vtt")
        (proj / "s1.vtt").write_text("WEBVTT\n", encoding="utf-8")
        import_project(db, proj)
        sess = db.query(SessionModel).one()
        assert sess.has_media is False

        # The recording turns up; the next run names it as the source.
        (proj / "s1.mp4").write_bytes(b"\x00" * 10)
        self._transcript(proj / "bristlenose-output", "s1.mp4")
        import_project(db, proj)
        sess = db.query(SessionModel).one()
        assert sess.has_media is True and sess.has_video is True
        paths = {Path(f.path).name for f in db.query(SourceFile).filter_by(session_id=sess.id)}
        assert "s1.mp4" in paths

    def test_a_recording_that_went_away_is_no_longer_verified(
        self, db: Session, tmp_path: Path,
    ) -> None:
        proj = self._project(tmp_path, "s1.mp4")
        (proj / "s1.mp4").write_bytes(b"\x00" * 10)
        import_project(db, proj)
        sf = db.query(SourceFile).one()
        assert sf.verified_at is not None and sf.size_bytes == 10

        (proj / "s1.mp4").unlink()
        import_project(db, proj)
        sf = db.query(SourceFile).one()
        assert sf.verified_at is None, "a path nothing re-verifies is a stale path"
