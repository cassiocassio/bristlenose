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
"""

from __future__ import annotations

import contextlib
import enum
import logging
import os
import shutil
from pathlib import Path

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

    @property
    def report_is_back(self) -> bool:
        return self in (RestoreOutcome.RESTORED, RestoreOutcome.RESTORED_WITHOUT_HISTORY)


def backup_path_for(output_dir: Path) -> Path:
    """Where `output_dir` is stashed. A hidden sibling, never a child."""
    return output_dir.parent / f".{output_dir.name}-previous"


def failed_path_for(output_dir: Path) -> Path:
    """Where a failed run's tree is kept, so a resume is a rename away."""
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
    if not output_dir.exists():
        return None

    backup = backup_path_for(output_dir)
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

    # Last run's kept-failed tree: one run's tenancy. It existed so THIS run
    # could have resumed from it, and this run has chosen not to.
    shutil.rmtree(failed_path_for(output_dir), ignore_errors=True)

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
    """Delete a stashed backup. Called once the run has produced a replacement."""
    if backup is None or not backup.exists():
        return
    shutil.rmtree(backup, ignore_errors=True)
    logger.info("output_backup: discarded %s", backup)


def restore(backup: Path | None, output_dir: Path) -> RestoreOutcome:
    """Put the stashed report back, keeping the failed run's history."""
    if backup is None or not backup.exists():
        return RestoreOutcome.NOTHING_TO_DO

    failed = failed_path_for(output_dir)
    moved_failed = False
    try:
        # A previous restore may have died between its rename and its cleanup,
        # leaving this path occupied. `rename` onto a non-empty directory is
        # ENOTEMPTY, which would otherwise surface as a bare FAILED.
        shutil.rmtree(failed, ignore_errors=True)

        # Step the failed tree aside rather than reading it into memory — the
        # log can be large, and a rename costs nothing.
        if output_dir.exists():
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
    if moved_failed:
        for rel in _APPEND_ONLY:
            history_ok = _append_onto(failed / rel, output_dir / rel) and history_ok

    # THE FAILED TREE IS KEPT, not deleted. It holds the manifest, the
    # `intermediate/` stage cache and any transcripts the run got as far as
    # writing — after an hour of Whisper that is the expensive thing on disk,
    # and the only thing that makes a retry cheaper than starting over.
    # `stash()` clears it next run, so it is a one-run tenancy, not litter.
    logger.info("output_backup: restored %s from %s", output_dir, backup)
    if moved_failed:
        logger.info("output_backup: failed run's tree kept at %s", failed)
    return RestoreOutcome.RESTORED if history_ok else RestoreOutcome.RESTORED_WITHOUT_HISTORY


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
        fd = os.open(
            dest, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600
        )
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
    write. Restoring here is what makes the crash case survivable at all.

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
    backup = backup_path_for(output_dir)
    if not backup.exists():
        return RestoreOutcome.NOTHING_TO_DO

    if project_is_locked(output_dir):
        logger.warning(
            "output_backup: a live run owns %s — leaving the backup at %s alone",
            output_dir,
            backup,
        )
        return RestoreOutcome.NOTHING_TO_DO

    logger.warning("output_backup: recovering a previous report from %s", backup)
    return restore(backup, output_dir)
