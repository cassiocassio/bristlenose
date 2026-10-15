"""A project's life, engineered to fail: storage and serve across every moment.

Each scenario builds the state that broke (or could break) a real project and
drives the real code through it: ``create_app`` with no ``db_url`` (so the
server chooses where its database lives, which is where the 12 Oct 2026 bug
was), the real ``output_backup`` stash, restore, discard and reclaim, and real
events in the real events log, read by the real watcher. No LLM, and no mocks
of the code under test.

Every scenario ends on the same four checks (``assert_healthy``):

1. the database is under ``bristlenose-output/.bristlenose/``;
2. nothing was written to ``<project>/.bristlenose/`` (the interview folder);
3. the database holds exactly one project row;
4. project 1, the only row the report reads, holds the sessions.

The 12 Oct incident failed 1, 2, 3 and 4 at once while every other signal was
green, which is why the checks are uniform rather than per-scenario.

Scenarios marked ``xfail(strict=True)`` are failure modes that are understood
and **not** designed out yet; the reason names what would fix them. ``strict``
means a fix flips them to an unexpected pass, which fails the run, so the
table cannot go stale in the flattering direction.

The register of every lifecycle failure mode, with the test that proves each
one (here, or elsewhere for the pipeline and the Mac app), is
``docs/design-lifecycle-failure-modes.md``. Pipeline-side modes (a move
re-transcribing, a removed interview returning, same-named recordings
merging, one report per name) are engineered through the real
``Pipeline.run`` in ``tests/test_pipeline_lifecycle_paths.py``.
"""

from __future__ import annotations

import logging
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from bristlenose.utils import output_backup
from tests.test_serve_condition import _completed, _failed, _started
from tests.test_serve_project_root import (
    _app,
    _client,
    _project,
    _rows,
    _run_writes_its_output,
    _sessions,
    _wait,
)
from tests.test_serve_project_root import fast_watcher as fast_watcher  # noqa: F401

STAR = "q-p1-10"  # a quote the smoke fixture carries


def _db(proj: Path) -> Path:
    return proj / "bristlenose-output" / ".bristlenose" / "bristlenose.db"


def assert_healthy(proj: Path, client) -> None:
    """The four checks. Sessions first, with a wait: an import may be in flight."""
    problems: list[str] = []
    if not _wait(lambda: _sessions(client)):
        problems.append("project 1 — the row the report reads — has no sessions")
    if not _db(proj).exists():
        problems.append("the database is not under bristlenose-output/.bristlenose/")
    if (proj / ".bristlenose").exists():
        problems.append("litter in the interview folder: <project>/.bristlenose/")
    rows = _rows(_db(proj)) if _db(proj).exists() else []
    if len(rows) != 1:
        problems.append(f"{len(rows)} project rows (want 1): {rows}")
    assert not problems, "; ".join(problems)


def _star(client) -> None:
    assert _wait(lambda: _sessions(client))
    resp = client.put("/api/projects/1/starred", json={STAR: True})
    assert resp.status_code == 200, resp.text


def _starred(client) -> bool:
    resp = client.get("/api/projects/1/starred")
    return resp.status_code == 200 and resp.json().get(STAR) is True


def _rebuild_from(stash: Path, out: Path) -> None:
    """What a re-run writes: the analysis files, then a fresh events log."""
    shutil.copytree(
        stash, out, dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("bristlenose.db*", "bristlenose.log*", "pipeline-events.jsonl"),
    )


class _Warnings(logging.Handler):
    """Collect WARNINGs from one logger. Not caplog: ``create_app`` calls
    ``setup_logging``, which reconfigures the root logger and drops caplog's
    handler."""

    def __init__(self, name: str) -> None:
        super().__init__(level=logging.WARNING)
        self.seen: list[str] = []
        self._logger = logging.getLogger(name)

    def emit(self, record: logging.LogRecord) -> None:
        self.seen.append(record.getMessage())

    def __enter__(self) -> _Warnings:
        self._logger.addHandler(self)
        return self

    def __exit__(self, *exc: object) -> None:
        self._logger.removeHandler(self)


# ── Scenarios ───────────────────────────────────────────────────────────────
# Each takes the project folder (a fresh copy of the smoke fixture) and the
# test's tmp_path, and ends on assert_healthy or a stated invariant.


def first_analysis_serve_before_output(proj: Path, tmp: Path) -> None:
    """The Mac app starts the report server on the next pass after it spawns a
    first run, so the server usually comes up before ``bristlenose-output/``
    exists. Before 12 Oct this rooted the database in the interview folder
    and the run imported into a second row: an empty report, every signal green."""
    out = proj / "bristlenose-output"
    held = tmp / "held"
    shutil.move(str(out), str(held))
    with _client(_app(proj, tmp)) as client:
        _run_writes_its_output(held, out)
        assert_healthy(proj, client)


def reanalyse_succeeds_under_a_live_serve(proj: Path, tmp: Path) -> None:
    """Re-analyse moves the output aside, writes a new one, and discards the old
    on success, all while the report server holds the old database open."""
    out = proj / "bristlenose-output"
    app = _app(proj, tmp)
    with _client(app) as client:
        assert _wait(lambda: _sessions(client))
        stash = output_backup.stash(out)
        assert stash is not None
        _rebuild_from(stash, out)
        _started(out, "RERUN")
        _completed(out, "RERUN")
        output_backup.discard(stash)
        assert _wait(lambda: (app.state.last_run.get(1) or {}).get("run_id") == "RERUN"), (
            "the server never imported the re-analysis"
        )
        assert_healthy(proj, client)


def reanalyse_fails_and_curation_survives(proj: Path, tmp: Path) -> None:
    """A re-analysis that fails puts the previous report back. The server used to
    keep answering from the copy that had been set aside, so curation made
    before the run looked lost and curation made after it went nowhere."""
    out = proj / "bristlenose-output"
    with _client(_app(proj, tmp)) as client:
        _star(client)
        stash = output_backup.stash(out)
        assert stash is not None
        (out / ".bristlenose").mkdir(parents=True, exist_ok=True)  # the run's first act
        _started(out, "BAD")
        _failed(out, "BAD")
        assert output_backup.restore(stash, out).report_is_back
        assert_healthy(proj, client)
        assert _wait(lambda: _starred(client)), "a failed re-analyse lost the researcher's star"


def server_restarted_mid_reanalyse(proj: Path, tmp: Path) -> None:
    """The incident itself: the server is (re)started while the output is moved
    aside, then the run finishes."""
    out = proj / "bristlenose-output"
    stash = output_backup.stash(out)
    assert stash is not None
    with _client(_app(proj, tmp)) as client:
        _rebuild_from(stash, out)
        _started(out, "RERUN")
        _completed(out, "RERUN")
        output_backup.discard(stash)
        assert_healthy(proj, client)


def server_restarted_mid_reanalyse_then_the_run_fails(proj: Path, tmp: Path) -> None:
    """As above, but the run fails and the previous report is put back under a
    server that has never seen it."""
    out = proj / "bristlenose-output"
    stash = output_backup.stash(out)
    assert stash is not None
    with _client(_app(proj, tmp)) as client:
        _started(out, "BAD")
        _failed(out, "BAD")
        assert output_backup.restore(stash, out).report_is_back
        assert_healthy(proj, client)


def crash_leaves_a_stash_and_the_next_run_reclaims_it(proj: Path, tmp: Path) -> None:
    """A hard crash runs no restore, so the previous report sits in the stash.
    The app relaunches and starts the server; the next run reclaims the stash
    under it before doing anything else."""
    out = proj / "bristlenose-output"
    assert output_backup.stash(out) is not None  # and then the process died
    with _client(_app(proj, tmp)) as client:
        assert output_backup.reclaim_stale(out).report_is_back
        assert_healthy(proj, client)


def crash_report_visible_before_any_rerun(proj: Path, tmp: Path) -> None:
    """After a crash, the previous report is readable as soon as the app reopens,
    without the researcher starting another run. The crash is a re-analysis
    that stashed the report, began its own output, and was killed: the server
    reopens on a stranded run (a start, no terminus, no live owner)."""
    out = proj / "bristlenose-output"
    assert output_backup.stash(out) is not None
    _started(out, "KILLED")  # the run's first event, then SIGKILL
    with _client(_app(proj, tmp)) as client:
        assert_healthy(proj, client)
    assert not output_backup.backup_path_for(out).exists(), "the backup was not reclaimed"
    log = (out / ".bristlenose" / "bristlenose.log").read_text(encoding="utf-8")
    assert "put back the report a crashed run had set aside" in log, (
        "the reclaim was said only on stderr, not in the project's log"
    )


def server_starting_inside_a_runs_start_up_is_left_alone(proj: Path, tmp: Path) -> None:
    """``run --clean`` stashes, opens its log, and only then writes its first
    event and PID file. A server started in that window must not mistake the
    backup for a crash and put the old report back under the run."""
    out = proj / "bristlenose-output"
    assert output_backup.stash(out) is not None
    (out / ".bristlenose").mkdir(parents=True)
    (out / ".bristlenose" / "bristlenose.log").write_text("run starting\n")
    with _client(_app(proj, tmp)):
        pass
    assert output_backup.backup_path_for(out).exists(), (
        "the server reclaimed a backup during a run's start-up"
    )


def server_starting_under_a_live_run_is_left_alone(proj: Path, tmp: Path) -> None:
    """A run that owns the folder (its PID file names a live process) is never
    second-guessed, whatever the events log says."""
    from bristlenose.run_lifecycle import _ps_start_time, _write_pid_file

    out = proj / "bristlenose-output"
    assert output_backup.stash(out) is not None
    _started(out, "LIVE")
    start = _ps_start_time(__import__("os").getpid())
    assert start is not None
    _write_pid_file(out, "LIVE", start)
    with _client(_app(proj, tmp)):
        pass
    assert output_backup.backup_path_for(out).exists(), (
        "the server reclaimed a backup from under a live run"
    )


def served_from_the_output_folder_then_the_project(proj: Path, tmp: Path) -> None:
    """``serve <p>/bristlenose-output`` and ``serve <p>`` used to store different
    input folders, so alternating them forked the project."""
    with _client(_app(proj / "bristlenose-output", tmp)):
        pass
    with _client(_app(proj, tmp)) as client:
        assert_healthy(proj, client)


def renamed_under_a_live_serve_is_said(proj: Path, tmp: Path) -> None:
    """A Finder rename under a live server leaves its open files working while it
    watches a path that no longer exists. That used to be silent."""
    moved = proj.with_name(proj.name + " renamed")
    with _Warnings("bristlenose.server.event_watcher") as warned:
        with _client(_app(proj, tmp)) as client:
            assert _wait(lambda: _sessions(client))
            shutil.move(str(proj), str(moved))
            assert _wait(lambda: any("is gone" in m for m in warned.seen)), (
                "a rename under a live server went unsaid"
            )
            assert _sessions(client), "the server stopped answering after a rename"


def renamed_under_a_live_serve_is_followed(proj: Path, tmp: Path) -> None:
    """The server itself following its folder to a new name."""
    moved = proj.with_name(proj.name + " renamed")
    app = _app(proj, tmp)
    with _client(app) as client:
        assert _wait(lambda: _sessions(client))
        shutil.move(str(proj), str(moved))
        _completed(moved / "bristlenose-output", "AFTER-RENAME")
        assert _wait(lambda: (app.state.last_run.get(1) or {}).get("run_id") == "AFTER-RENAME"), (
            "a run finished at the new path was never imported"
        )


def moved_while_closed_keeps_its_curation(proj: Path, tmp: Path) -> None:
    """The folder is moved with the app closed, then opened at its new place."""
    with _client(_app(proj, tmp)) as client:
        _star(client)
    moved = tmp / "Archive" / proj.name
    moved.parent.mkdir()
    shutil.move(str(proj), str(moved))
    with _client(_app(moved, tmp)) as client:
        assert_healthy(moved, client)
        assert _starred(client), "the move orphaned the researcher's curation"


def copied_to_another_place_is_one_project(proj: Path, tmp: Path) -> None:
    """The folder is copied (another disk, a colleague's machine) and the copy is
    opened. Its database carries the original's paths."""
    with _client(_app(proj, tmp)) as client:
        _star(client)
    copy = tmp / "Copy" / proj.name
    shutil.copytree(proj, copy)
    with _client(_app(copy, tmp)) as client:
        assert_healthy(copy, client)
        assert _starred(client), "the copy lost the curation it carries"


# ── The table ───────────────────────────────────────────────────────────────

# Windows will not rename or move a folder while a file inside it is open, and a
# live server holds bristlenose-output/.bristlenose/bristlenose.db (and its log)
# open. Each scenario below moves that folder, or the project around it, under a
# live server, so on Windows the move itself is refused before the code under
# test runs. Same class as TestTheStashCycle (test_serve_lifecycle_robustness)
# and the test_serve_condition guards. What the refusal costs a Windows user is
# recorded as an open item in docs/design-windows-port.md, not hidden here.
_MOVES_AN_OPEN_DATABASE = pytest.mark.skipif(
    sys.platform == "win32",
    reason="moves a folder whose database a live server holds open; Windows refuses the move",
)

SCENARIOS = [
    pytest.param(first_analysis_serve_before_output, id="first-analysis-serve-before-output"),
    pytest.param(reanalyse_succeeds_under_a_live_serve, id="reanalyse-succeeds-live-serve",
                 marks=_MOVES_AN_OPEN_DATABASE),
    pytest.param(reanalyse_fails_and_curation_survives, id="reanalyse-fails-curation-survives",
                 marks=_MOVES_AN_OPEN_DATABASE),
    pytest.param(server_restarted_mid_reanalyse, id="server-restarted-mid-reanalyse"),
    pytest.param(server_restarted_mid_reanalyse_then_the_run_fails,
                 id="server-restarted-mid-reanalyse-run-fails",
                 marks=_MOVES_AN_OPEN_DATABASE),
    pytest.param(crash_leaves_a_stash_and_the_next_run_reclaims_it, id="crash-then-next-run-reclaims",
                 marks=_MOVES_AN_OPEN_DATABASE),
    pytest.param(served_from_the_output_folder_then_the_project, id="output-entry-then-root-entry"),
    pytest.param(renamed_under_a_live_serve_is_said, id="rename-under-live-serve-is-said",
                 marks=_MOVES_AN_OPEN_DATABASE),
    pytest.param(
        crash_report_visible_before_any_rerun, id="crash-report-visible-before-rerun",
        marks=_MOVES_AN_OPEN_DATABASE,
    ),
    pytest.param(server_starting_inside_a_runs_start_up_is_left_alone,
                 id="server-in-run-start-up-leaves-backup"),
    pytest.param(server_starting_under_a_live_run_is_left_alone,
                 id="server-under-live-run-leaves-backup"),
    pytest.param(
        renamed_under_a_live_serve_is_followed, id="rename-under-live-serve-is-followed",
        marks=pytest.mark.xfail(strict=True, reason=(
            "a CLI serve keeps watching the old path (it says so, previous scenario). The "
            "Mac app follows the folder and restarts the serve at the new path "
            "(988a60d8, eb8509e1); the CLI user restarts it by hand."
        )),
    ),
    pytest.param(moved_while_closed_keeps_its_curation, id="moved-while-closed",
                 marks=_MOVES_AN_OPEN_DATABASE),
    pytest.param(copied_to_another_place_is_one_project, id="copied-elsewhere"),
]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_lifecycle_scenario(
    scenario: Callable[[Path, Path], None], tmp_path: Path, fast_watcher,  # noqa: F811
) -> None:
    proj = _project(tmp_path)
    scenario(proj, tmp_path)
