"""Keep the previous report until the new one exists.

WHY THIS EXISTS
---------------
`bristlenose run` used to `shutil.rmtree(output_dir)` after preflight and before
the pipeline. That is irreversible, and it happened *before* the run had
demonstrated it could do anything at all. On 30 Aug 2026 two runs cleaned their
output directory and then died seconds later inside transcription — a corrupt
bundled dylib, `docs/sidecar-transcription-crash.md`. Both projects were left
with neither their old report nor a new one. One of them has not been recovered:
rebuilding it needs a real run with real LLM spend.

The fix is not "clean later" — every stage writes into the output directory, so
there is no late moment. It is "clean by moving aside, and only destroy once the
run has produced a replacement".

WHAT A RESTORE HAS TO PRESERVE
------------------------------
Restoring the old directory wholesale would be wrong, and subtly so: the app
reads `.bristlenose/pipeline-events.jsonl` to decide what a project's state is.
Put the old file back and the tail says `run_completed` — so a run that just
failed would render as fine, and the failure would vanish from the UI.

So a restore is: **the old tree, plus the failed run's append-only history.**
`pipeline-events.jsonl` and `bristlenose.log` are both append-only by
construction, so old-then-new concatenation is exactly right.

**That concatenation is load-bearing, so it reports.** An earlier version caught
`OSError` inside the append, logged a warning, and let the restore return success
anyway — which put the old `run_completed` tail back and told the caller all was
well. That is the module's own headline failure, reintroduced through its error
handler. `RestoreOutcome` exists so the caller can tell the four cases apart.

CRASH SAFETY
------------
A SIGILL or SIGKILL runs no handler, so the in-process restore cannot fire. The
backup stays on disk and `reclaim_stale()` — called at the top of the next run —
puts it back. That is the safety net, not the main path.

**Nothing here ever deletes a backup it cannot prove is spent.** `stash()` used
to clear any pre-existing backup on the reasoning that `reclaim_stale` had
already had its chance — true only when the reclaim *succeeded*. When it failed,
the next `--clean` destroyed the sole surviving copy of the report.

WHERE THE STASH LIVES, AND WHAT THAT COSTS
------------------------------------------
A dot-prefixed sibling of the output directory. Two consequences, both real:

- **It cannot be re-ingested.** `s01_ingest.py` skips every dot-prefixed entry,
  and the desktop watcher sets `.skipsHiddenFiles`. A stashed report can never
  be offered back to the researcher as interview material.
- **It is invisible to the researcher, and it holds re-identification keys.**
  A full move carries `.bristlenose/` with it, so the stash contains
  `pii_summary.txt` (every original PII value with timecodes) and
  `llm-calls.jsonl`. `SECURITY.md` says `rm -rf bristlenose-output` deletes
  every per-project byte; while a stash exists, that is false. It is documented
  there now, and `bristlenose status` reports a stash it finds — but the honest
  summary is that this trades a little erasure clarity for not destroying the
  researcher's deliverable, and the trade is only defensible because the stash
  is short-lived: the next successful run discards it.

A sibling is not an arbitrary choice. The stash has to be on the same
filesystem, because the whole design rests on `rename(2)` being atomic and free;
an Application Support location would be a cross-device copy of a directory that
can hold gigabytes of extracted audio, on the failure path, at the moment the
disk is most likely to be full.

A FRESH START REPLACES THE REPORT ONCE IT HAS A SESSION
------------------------------------------------------
Re-analyse is a deliberate fresh start (owner, 23 Oct 2026). Its analysis
replaces the report as soon as it holds one analysed session, a session whose
quotes are on disk (`holds_an_analysed_session`), even if other sessions
failed: the rest is finished by an ordinary Analyse, like any partial run. Only
a run that produced nothing puts the report back. Nothing of the old analysis
is kept but what the researcher exported: `clips/` and `screens/` move into the
new output under the old analysis's date (`carry_exports`). One rule, one
place (`settle`), whether the run ended, raised, was stopped, stuck past the
hosted backstop, or crashed and is settled by the next run.

A 22 Oct design held the report back when any session failed, kept the attempt
beside it, and let the next plain run swap the attempt in. That plain run then
discarded the report, curation made on it since included, with no question
asked. It is gone: no run without --clean replaces a report.
"""

from __future__ import annotations

import contextlib
import enum
import glob
import json
import logging
import os
import re
import shutil
from collections.abc import Iterator
from pathlib import Path

from bristlenose.utils.fs import open_private

logger = logging.getLogger(__name__)

#: Files that are append-only across runs, so a restore concatenates rather
#: than choosing. Relative to the output directory.
_APPEND_ONLY = (
    Path(".bristlenose") / "pipeline-events.jsonl",
    Path(".bristlenose") / "bristlenose.log",
)

#: Pipeline scratch, not part of the report. Dropped rather than stashed — see
#: `stash()`.
_SCRATCH = Path(".bristlenose") / "temp"

class RestoreOutcome(enum.Enum):
    """What a restore actually achieved. Four states, not two.

    Collapsing these to a bool is how the module told a caller "your report is
    back" in cases where it was not, or was back without the failure history
    that keeps the UI honest.
    """

    #: No backup existed. Nothing to do, nothing wrong.
    NOTHING_TO_DO = "nothing"
    #: The report is back and the failed run's history came with it.
    RESTORED = "restored"
    #: The report is back, but the failed run's history could NOT be appended —
    #: so the events tail is the OLD `run_completed` and the project will read
    #: as having succeeded. The caller must say so.
    RESTORED_WITHOUT_HISTORY = "restored_without_history"
    #: The restore failed partway. `output_dir` may not exist at all, and both
    #: copies are in dot-directories Finder will not show. Loud, always.
    FAILED = "failed"
    #: Not a restore: the run's analysis held a session, so it is the report
    #: now, and the one set aside was discarded (`settle`).
    REPLACED = "replaced"
    #: As REPLACED, but an export folder would not move, so the report set aside
    #: is kept, unspent, until the next run's `reclaim_stale` carries the rest.
    CARRY_INCOMPLETE = "carry_incomplete"

    @property
    def report_is_back(self) -> bool:
        return self in (RestoreOutcome.RESTORED, RestoreOutcome.RESTORED_WITHOUT_HISTORY)


#: This process's hold on each study folder's settle lock: path -> [fd, depth].
_settle_holds: dict[str, list[int]] = {}


@contextlib.contextmanager
def _settling(output_dir: Path) -> Iterator[None]:
    """Hold the study folder's settle lock: one settle, reclaim or stash at a time.

    After a crash the report server's `reclaim_after_crash` (at app launch) and
    a queue-restored run's `reclaim_stale` can both find the backup, both before
    any PID file exists, and one put-back renaming under the other loses the
    report's place. An `flock` on the study folder itself, so no file is added
    to it; released when the descriptor closes, death included. Re-entrant in
    this process (`reclaim_stale` calls `settle`). The CLI and the hosted
    backstop never settle together: both hold the exit hold first. Where flock
    does not exist (Windows), or the folder will not open, it runs unlocked,
    as before.
    """
    try:
        import fcntl
    except ImportError:
        yield
        return
    key = str(output_dir.parent.absolute())
    held = _settle_holds.get(key)
    if held is not None:
        held[1] += 1
        try:
            yield
        finally:
            held[1] -= 1
        return
    try:
        fd = os.open(key, os.O_RDONLY)
    except OSError:
        yield
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
    except OSError:
        os.close(fd)
        yield
        return
    _settle_holds[key] = [fd, 1]
    try:
        yield
    finally:
        del _settle_holds[key]
        os.close(fd)


def backup_path_for(output_dir: Path) -> Path:
    """Where `output_dir` is stashed. A hidden sibling, never a child."""
    return output_dir.parent / f".{output_dir.name}-previous"


#: Written into a backup before `discard` moves it: a backup carrying it is
#: spent, and `reclaim_stale` deletes it rather than restoring it.
_SPENT_MARKER = ".bristlenose-backup-spent"

#: Written into a backup once a run has replaced it, before its exports are
#: carried: a backup carrying it is never put back, even when the run's
#: session cannot be read from disk (`settle`'s *produced*), only finished.
_REPLACED_MARKER = ".bristlenose-backup-replaced"


def _discarding_path(backup: Path) -> Path:
    """Where a spent backup goes to be deleted: never a path `reclaim_stale` reads.

    Per process, so the rename never lands on a leftover it could not clear.
    """
    return backup.with_name(f"{backup.name}-discarding-{os.getpid()}")


def _clear_discarding(backup: Path) -> None:
    """Delete what earlier cut-short discards left. Said when something stays."""
    for leftover in backup.parent.glob(f"{glob.escape(backup.name)}-discarding*"):
        shutil.rmtree(leftover, ignore_errors=True)
        if leftover.exists():
            logger.warning("output_backup: could not clear %s, a spent backup", leftover)


def leftovers_for(output_dir: Path) -> list[Path]:
    """Trees beside the output that a cut-short delete or put-back left.

    A spent backup's `-discarding-<pid>` and a run's `-failed` (or
    `-failed-<pid>`, when a kept one held the name). Nothing reads them, and
    they hold participants' data, so `status` names them and the next run
    deletes them.
    """
    parent, name = output_dir.parent, glob.escape(output_dir.name)
    return sorted(
        set(parent.glob(f".{name}-previous-discarding*")) | set(parent.glob(f".{name}-failed*"))
    )


def failed_path_for(output_dir: Path) -> Path:
    """Where a restore steps the run's tree while it copies the history across.

    Deleted as soon as the history is across. A tree here was left by a restore
    cut short, or by a build that kept failed attempts (22 Oct 2026): nothing
    reads it, and `stash` and `reclaim_stale` clear it.
    """
    return output_dir.parent / f".{output_dir.name}-failed"


def stash(output_dir: Path, *, previous_backup_is_spent: bool = False) -> Path | None:
    """Move `output_dir` aside instead of deleting it. Returns the backup path.

    Returns None when there was nothing to stash, or when the move failed — in
    which case the old output is left exactly where it was. It never falls back
    to deleting; that is the behaviour this module exists to remove. **A caller
    that gets None must not tell the user the directory was cleaned**, because
    the pipeline will now resume off the old manifest.

    `previous_backup_is_spent` must be True before an existing backup will be
    destroyed. Only the caller knows: it is true when `reclaim_stale` already
    put that backup back. Defaulting to False means the dangerous act needs a
    word, and a backup that could not be reclaimed survives rather than being
    swept by the next `--clean` — which is how the sole surviving copy of a
    report would have been lost.

    `.bristlenose/temp/` is dropped rather than carried. It holds the extracted
    WAV cache, which nothing cleans up (measured at 944 MB after a ten-interview
    run, `docs/design-performance.md`), so stashing it would put a second copy
    beside the new run's own. It is scratch: no restore needs it, and the old
    upfront `rmtree` deleted it too.
    """
    with _settling(output_dir):
        return _stash(output_dir, previous_backup_is_spent=previous_backup_is_spent)


def _stash(output_dir: Path, *, previous_backup_is_spent: bool) -> Path | None:
    if not output_dir.exists():
        return None

    # A live run's output is not ours to move. `run --clean` used to rename a
    # running run's tree — PID file and all — so the second run entered the
    # lifecycle without ConcurrentRunError and the first wrote into a folder
    # nothing would ever read. `reclaim_stale` declines the same way.
    if project_is_locked(output_dir):
        logger.warning(
            "output_backup: a live run owns %s — refusing to move it aside", output_dir,
        )
        return None

    backup = backup_path_for(output_dir)
    # Spent backups whose delete was cut short (`discard`): already proven
    # spent, never restorable, so cleared here.
    _clear_discarding(backup)
    if backup.exists():
        if not previous_backup_is_spent:
            logger.warning(
                "output_backup: %s exists and was not reclaimed — refusing to stash "
                "over it. The previous report would be the thing destroyed.",
                backup,
            )
            return None
        shutil.rmtree(backup, ignore_errors=True)
        if backup.exists():
            # A partially-suppressed rmtree leaves a non-empty directory, and
            # `rename` onto one is ENOTEMPTY — which would surface below as a
            # bare "could not stash". Name the real reason here.
            logger.warning(
                "output_backup: could not clear %s — leaving output in place", backup
            )
            return None

    # A tree a cut-short restore left: nothing reads it. Its exports join the
    # report about to be set aside, and settle with it.
    if failed_path_for(output_dir).exists():
        _drop_tree(failed_path_for(output_dir), exports_to=output_dir)

    scratch = output_dir / _SCRATCH
    if scratch.exists():
        shutil.rmtree(scratch, ignore_errors=True)

    try:
        output_dir.rename(backup)
    except OSError as exc:
        logger.warning(
            "output_backup: could not stash %s (%s); leaving it in place", output_dir, exc
        )
        return None

    logger.info("output_backup: stashed %s -> %s", output_dir, backup)
    return backup


def discard(backup: Path | None) -> None:
    """Delete a stashed backup. Called once the run has produced a replacement.

    Renamed out of the backup path first, atomically, then deleted. The delete
    is long (a stash can hold gigabytes), and one cut short used to leave part
    of the old tree at the backup path, which the next run's `reclaim_stale`
    put back over the new report (R110). A delete that leaves files says so;
    the next `stash` clears what is left.
    """
    if backup is None or not backup.exists():
        return
    try:
        (backup / _SPENT_MARKER).touch()
    except OSError as exc:
        logger.warning("output_backup: could not mark %s spent (%s)", backup, exc)
    doomed = _discarding_path(backup)
    try:
        backup.rename(doomed)
    except OSError as exc:
        logger.warning(
            "output_backup: could not set %s aside to delete it (%s); it is left in "
            "place, marked spent, for the next run to delete", backup, exc,
        )
        return
    shutil.rmtree(doomed, ignore_errors=True)
    if doomed.exists():
        logger.warning(
            "output_backup: could not fully delete %s; the next run removes it", doomed,
        )
        return
    logger.info("output_backup: discarded %s", backup)


def restore(backup: Path | None, output_dir: Path) -> RestoreOutcome:
    """Put the stashed report back, keeping the failed run's history.

    Holds the exit (``run_lifecycle.holding_exit``) throughout: a hosted run's
    backstop that exited between the two renames would leave the report set
    aside until the next run.
    """
    if backup is None or not backup.exists():
        return RestoreOutcome.NOTHING_TO_DO
    from bristlenose.run_lifecycle import holding_exit

    with holding_exit():
        return _restore(backup, output_dir)


def _restore(backup: Path, output_dir: Path) -> RestoreOutcome:

    failed = failed_path_for(output_dir)
    moved_failed = False
    try:
        # Step the run's tree aside rather than reading it into memory — the
        # log can be large, and a rename costs nothing.
        if output_dir.exists():
            # A tree already here (a restore cut short, a `stash` that kept one
            # whose export would not move, a build with the 22 Oct hold-back)
            # is cleared first, its exports into the report coming back. One
            # that is kept leaves its name, and this run's tree takes its own.
            if failed.exists():
                _drop_tree(failed, exports_to=backup)
            if failed.exists():
                failed = failed.with_name(f"{failed.name}-{os.getpid()}")
                shutil.rmtree(failed, ignore_errors=True)
            output_dir.rename(failed)
            moved_failed = True

        backup.rename(output_dir)
    except OSError as exc:
        logger.error(
            "output_backup: restore of %s FAILED (%s). The report is at %s%s",
            output_dir,
            exc,
            backup if backup.exists() else output_dir,
            f"; this run's tree is at {failed}" if moved_failed else "",
        )
        return RestoreOutcome.FAILED

    history_ok = True
    if failed.is_dir():
        # The run's tree: stepped aside above, or by a restore cut short
        # between its renames, which left no output and this.
        for rel in _APPEND_ONLY:
            history_ok = _append_onto(failed / rel, output_dir / rel) and history_ok
        # The run produced nothing to keep (`settle`), so once its history is
        # across its tree goes: there is no attempt to finish from.
        _drop_tree(failed, exports_to=output_dir)

    logger.info("output_backup: restored %s from %s", output_dir, backup)
    return RestoreOutcome.RESTORED if history_ok else RestoreOutcome.RESTORED_WITHOUT_HISTORY


def _drop_tree(tree: Path, *, exports_to: Path) -> None:
    """Delete a run's tree nothing will read. Said when something stays.

    Exports go first: a researcher can export clips or screens from a fresh
    analysis while it runs, into this tree, and an export is never deleted.
    They move into *exports_to* under the run's own date (`carry_exports`).
    If one will not move, the tree is kept for the next run to try again.
    """
    if not carry_exports(tree, exports_to):
        logger.warning("output_backup: kept %s, which holds an export that would not "
                       "move", tree)
        return
    shutil.rmtree(tree, ignore_errors=True)
    if tree.exists():
        logger.warning("output_backup: could not fully delete %s; the next run removes it",
                       tree)


def _append_onto(src: Path, dest: Path) -> bool:
    """Append `src`'s bytes to `dest`. False if the history was NOT preserved.

    `O_NOFOLLOW` + `0o600`, matching `run_lifecycle.append_event` and
    `llm/telemetry.py`, because this is the second writer to a file those two
    open carefully. A plain `open("ab")` follows a symlink at `dest` — and
    `dest` lives in a directory a co-worker on a shared study folder can write
    to — which makes this an append-to-arbitrary-file primitive fed by log
    bytes. It also creates at umask default, silently downgrading a 0600
    re-identification key to 0644.

    A partial write is truncated back: half an event line is worse than none,
    because `read_events` would then choke on the file rather than skip it.
    """
    if not src.is_file():
        return True  # Nothing to preserve is not a failure to preserve it.
    start = dest.stat().st_size if dest.exists() else 0
    fd = None
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd = open_private(dest, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
        with open(fd, "wb", closefd=True) as fh_dest:
            fd = None  # now owned by the file object
            with src.open("rb") as fh_src:
                shutil.copyfileobj(fh_src, fh_dest)
            fh_dest.flush()
            os.fsync(fh_dest.fileno())
    except OSError as exc:
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)
        logger.error(
            "output_backup: could not append %s onto %s (%s) — the restored log "
            "would read as a COMPLETED run. Truncating back to %d bytes.",
            src,
            dest,
            exc,
            start,
        )
        with contextlib.suppress(OSError):
            os.truncate(dest, start)
        return False
    return True


def holds_an_analysed_session(output_dir: Path) -> bool:
    """Has this run produced a session worth replacing a report with?

    A session whose quote extraction is recorded done (the record the server
    imports a session's quotes by, ``lens_readiness.quoted_in_manifest``) and
    which has at least one quote on disk. A session recorded done with no
    quotes (a silent recording) is not an analysis: an emptied or silent folder
    used to replace a report with an empty one (R116). Read from disk, not from
    the run's result, so the same answer comes back after a run that raised,
    was stopped or was killed. Anything unreadable answers False, and the
    report set aside comes back.
    """
    from bristlenose.manifest import (
        STAGE_QUOTE_EXTRACTION,
        get_completed_session_ids,
        load_manifest,
    )

    if not output_dir.is_dir():
        return False
    sids = get_completed_session_ids(load_manifest(output_dir), STAGE_QUOTE_EXTRACTION)
    if not sids:
        return False
    quotes_file = output_dir / ".bristlenose" / "intermediate" / "extracted_quotes.json"
    try:
        quotes = json.loads(quotes_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(quotes, list):
        return False
    return any(isinstance(q, dict) and q.get("session_id") in sids for q in quotes)


#: Folders the researcher exported into the output, carried into a fresh
#: start's output rather than discarded with the old analysis (owner, 23 Oct
#: 2026). The clip export writes `clips/`, the screens export `screens/`.
_EXPORT_FOLDERS = ("clips", "screens")

#: A carried folder's name. DRAFT wording (copy-for-approval-2026-10-23.md,
#: RE#13), English whatever the UI language, like the files inside it.
_CARRIED_NAME = "{folder} (from the analysis of {day})"

#: A folder an earlier fresh start carried: carried along again, as it is.
_CARRIED = re.compile(
    r"(?:" + "|".join(_EXPORT_FOLDERS) + r") \(from the analysis of [^)]+\)(?: \d+)?"
)


def _analysis_day(report: Path) -> str | None:
    """The day the analysis in *report* was started: its first run's start.

    The events log of an output folder begins with the run that made it (a
    first analysis or a fresh start); later Analyse runs append. None when
    nothing says, and the caller dates each folder by its own time instead.
    The manifest's `created_at` is only the fallback: the pipeline makes a new
    manifest on every run, so it dates the last Analyse, not the analysis.
    """
    from datetime import datetime

    from bristlenose.utils.markdown import format_finder_day

    events = report / ".bristlenose" / "pipeline-events.jsonl"
    try:
        with events.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    started = json.loads(line).get("started_at")
                except (ValueError, AttributeError):
                    continue
                if isinstance(started, str):
                    # The events log writes "…Z", which `fromisoformat` reads
                    # only from Python 3.11.
                    return format_finder_day(
                        datetime.fromisoformat(started.replace("Z", "+00:00")))
    except (OSError, ValueError):
        pass
    from bristlenose.manifest import load_manifest

    manifest = load_manifest(report)
    if manifest is not None:
        try:
            return format_finder_day(
                datetime.fromisoformat(manifest.created_at.replace("Z", "+00:00")))
        except ValueError:
            pass
    return None


def _free_name(parent: Path, name: str) -> str:
    """*name*, or the first of "*name* 2", "*name* 3"… not taken in *parent*."""
    candidate, n = name, 1
    while (parent / candidate).exists():
        n += 1
        candidate = f"{name} {n}"
    return candidate


def carry_exports(report: Path, output_dir: Path) -> bool:
    """Move the exports out of a replaced *report* into *output_dir*.

    `clips/` and `screens/` take the old analysis's date; folders an earlier
    fresh start carried move as they are. A name already taken gets " 2", " 3",
    so nothing is written over. False when any folder could not be moved: the
    caller must then keep *report*, never delete an export with it.
    """
    from datetime import datetime

    from bristlenose.utils.markdown import format_finder_day

    # Never raises: it runs inside the CLI's `finally`, and an escape there
    # would replace the run's own failure with a traceback no log holds.
    try:
        entries = sorted(report.iterdir(), key=lambda e: (e.name in _EXPORT_FOLDERS, e.name))
    except OSError as exc:
        logger.warning("output_backup: could not list %s for exports (%s); it is kept "
                       "until it can be", report, exc)
        return False
    day = _analysis_day(report)
    moved_all = True
    # Folders already carried go first, so each keeps the name it was given.
    for entry in entries:
        try:
            if not entry.is_dir() or entry.is_symlink():
                continue
            if entry.name in _EXPORT_FOLDERS:
                when = day or format_finder_day(datetime.fromtimestamp(entry.stat().st_mtime))
                name = _CARRIED_NAME.format(folder=entry.name, day=when)
            elif _CARRIED.fullmatch(entry.name):
                name = entry.name
            else:
                continue
            target = output_dir / _free_name(output_dir, name)
            output_dir.mkdir(parents=True, exist_ok=True)
            entry.rename(target)
        except OSError as exc:
            logger.warning("output_backup: could not carry %s into %s (%s); the "
                           "previous report is kept until it can be", entry, output_dir, exc)
            moved_all = False
            continue
        logger.info("output_backup: carried %s to %s", entry, target)
    return moved_all


def settle(backup: Path | None, output_dir: Path, *, produced: bool = False) -> RestoreOutcome:
    """Decide between the report set aside and the run in its place.

    The run's analysis replaces the report once it holds a session
    (`holds_an_analysed_session`, or *produced*: the caller saw quotes in the
    run's result, which also covers a run that wrote no intermediates). The
    exports are carried across and the report is discarded. Otherwise the
    report is put back with the run's history (`restore`). Holds the exit
    throughout, as `restore` does, so a hosted backstop never exits between
    the carry and the discard.
    """
    from bristlenose.run_lifecycle import holding_exit

    with holding_exit(), _settling(output_dir):
        if backup is None or not backup.exists():
            return RestoreOutcome.NOTHING_TO_DO
        if not (produced or backup_is_replaced(output_dir)):
            return _restore(backup, output_dir)
        try:
            (backup / _REPLACED_MARKER).touch()
        except OSError as exc:
            logger.warning("output_backup: could not mark %s replaced (%s)", backup, exc)
        if not carry_exports(backup, output_dir):
            # Kept, unspent, marked replaced: the next run's `reclaim_stale`
            # carries what is left and discards it, and never puts it back. An
            # export is never deleted with it.
            return RestoreOutcome.CARRY_INCOMPLETE
        discard(backup)
    return RestoreOutcome.REPLACED


def backup_is_replaced(output_dir: Path) -> bool:
    """Has a fresh run replaced the report set aside beside *output_dir*?

    Its analysis holds a session on disk, or a settle already decided so and
    marked the backup (a run whose session is not on disk, cut short after).
    """
    return (
        (backup_path_for(output_dir) / _REPLACED_MARKER).exists()
        or holds_an_analysed_session(output_dir)
    )


def project_is_locked(output_dir: Path) -> bool:
    """Is a live run holding this output directory?

    Imported lazily: `run_lifecycle` pulls in a lot, and this module is small
    enough to be used by tooling that wants none of it.
    """
    from bristlenose.run_lifecycle import _is_alive_owned, _read_pid_file

    pid_file = _read_pid_file(output_dir)
    return pid_file is not None and _is_alive_owned(pid_file)


def reclaim_stale(output_dir: Path) -> RestoreOutcome:
    """Recover a backup left behind by a hard crash. Call before `stash()`.

    A signalled death runs no cleanup, so the backup from that run is still on
    disk while the output directory holds whatever the dead run managed to
    write. Settling it here is what makes the crash case survivable at all, and
    by the rule the run would have applied (`settle`): a run killed after a
    session landed is the report, one killed before is not.

    **It must decline while another run is live.** This runs well before
    `run_lifecycle` takes the concurrent-run lock, so nothing has yet checked
    whether someone else owns the directory. A second `bristlenose run` on a
    folder that already has one in flight would otherwise rename the LIVE output
    away and put the first run's backup in its place — the first run then writes
    into an unlinked inode, its terminus lands nowhere, and the project reads as
    "no terminus, so no lens opens". That is the symptom this module exists to
    prevent, caused by the fix for it.

    Logged at WARNING, not INFO. This runs before `setup_logging` has attached a
    file handler, so `logging.lastResort` is the only thing carrying it — and
    that emits WARNING and above. At INFO, the single most consequential silent
    act in the module was recorded nowhere at all.
    """
    with _settling(output_dir):
        return _reclaim_stale(output_dir)


def _reclaim_stale(output_dir: Path) -> RestoreOutcome:
    backup = backup_path_for(output_dir)
    # Spent backups whose delete was cut short: proven spent, never restorable.
    _clear_discarding(backup)
    if not backup.exists():
        _clear_leftover_attempt(output_dir)
        return RestoreOutcome.NOTHING_TO_DO

    if (backup / _SPENT_MARKER).exists():
        # A run produced its report and `discard` could not move this out of
        # the way: it is spent, and restoring it would put the old report over
        # the new one (R110).
        logger.warning("output_backup: deleting %s, a spent backup", backup)
        shutil.rmtree(backup, ignore_errors=True)
        if backup.exists():
            logger.warning("output_backup: could not delete %s", backup)
        return RestoreOutcome.NOTHING_TO_DO

    if project_is_locked(output_dir):
        logger.warning(
            "output_backup: a live run owns %s — leaving the backup at %s alone",
            output_dir,
            backup,
        )
        return RestoreOutcome.NOTHING_TO_DO

    outcome = settle(backup, output_dir)
    if outcome is RestoreOutcome.REPLACED:
        logger.warning("output_backup: %s holds a fresh analysis; deleted the previous "
                       "report set aside at %s", output_dir, backup)
    elif outcome is RestoreOutcome.CARRY_INCOMPLETE:
        logger.warning("output_backup: %s holds a fresh analysis; the previous report at "
                       "%s is kept until an export in it moves", output_dir, backup)
    else:
        logger.warning("output_backup: recovering a previous report from %s: %s",
                       backup, outcome.value)
    return outcome


def _clear_leftover_attempt(output_dir: Path) -> None:
    """Delete a tree at `failed_path_for` no run is using.

    Left by a restore cut short, or kept by a build with the 22 Oct hold-back.
    Nothing reads it, and it holds a copy of the participants' data.
    """
    if project_is_locked(output_dir):
        return
    for failed in output_dir.parent.glob(f".{glob.escape(output_dir.name)}-failed*"):
        logger.warning("output_backup: deleting %s, a run's tree nothing reads", failed)
        _drop_tree(failed, exports_to=output_dir)


def reclaim_after_crash(output_dir: Path) -> RestoreOutcome:
    """The report server's reclaim: put a crashed run's backup back on start.

    `reclaim_stale` runs at the top of the next `run`, so after a crash the
    previous report stayed hidden until the researcher analysed again. The
    server can do it sooner, but only when the evidence says *crash* and never
    when it might be a run's own start-up. `run --clean` stashes, then sets up
    its log, imports the pipeline and only then writes `run_started` and its
    PID file — a window of a second or more in which the backup exists and
    nothing yet owns the folder. A server started inside that window that
    reclaimed would put the old report back under a run that is about to
    write into it.

    So it reclaims in one shape only: the output folder's latest run is
    **stranded** — it started, wrote no terminus, and its PID file names no
    live process. That is what a SIGKILL mid-run leaves.

    An **absent** output folder is not that shape, though it looks like a
    crash: it is also a run's first instant, between its rename and its first
    write, and on 12 Oct 2026 the app started a run and a server within the
    same second (``tests/test_lifecycle_scenarios.py``,
    ``server-restarted-mid-reanalyse``). A folder holding a log and no
    `run_started` is the rest of the start-up window. A failed run's in-process
    restore already had its chance. All three are left for the next `run`.
    """
    backup = backup_path_for(output_dir)
    if not backup.exists() or project_is_locked(output_dir):
        return RestoreOutcome.NOTHING_TO_DO
    from bristlenose.run_condition import RunStateEnum, read_condition

    latest = read_condition(output_dir).latest if output_dir.exists() else None
    if latest is None or latest.state is not RunStateEnum.STRANDED:
        logger.info(
            "output_backup: %s has a backup but no crashed run — leaving it for the "
            "next run to reclaim", output_dir,
        )
        return RestoreOutcome.NOTHING_TO_DO
    return reclaim_stale(output_dir)
