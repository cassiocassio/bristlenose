---
status: current
last-trued: 2026-10-17
trued-against: HEAD@main (6e7a8a9b) on 2026-10-17
---

## Changelog

- _2026-10-17_ — rows 49–50 designed out: two races between a failed run's restore and the serve, both seen on CI as intermittent reds of tests that pass locally (`test_serve_while_the_output_is_stashed_then_restored`, scenario `reanalyse-fails-curation-survives`). Each now has a test that injects the restore into the window, so it is red every time without its fix. Score recomputed. Anchors: `_reattach_if_moved` and `_REATTACH_ROUNDS` in `server/app.py`, `completed_run_ids` and `run_event_watcher(imported=…)` in `server/event_watcher.py`.
- _2026-10-14, evening_ — four defects from one `--clean` Re-analyse in the Mac app: rows 45–47 designed out (the shoal lifted on the previous run's count; the serve's log lost with the set-aside folder; a mid-run pick refused as a recode), rows 44 and 48 open (a pick in the second before the serve reattaches; a 74 s status page the lost log could not explain). Row 8 recounted. Score recomputed. Anchors: `PipelineRunnerProgressTests`, `logging.reopen_log_file`, `refusal.analysis_running`, commit "review fixes: tests that could not fail, a log reopen that could lose the log, a silent paragraph move".
- _2026-10-14_ — trued up against progressive lenses (12–13 Oct): a proof-scope caveat (no scenario delivers a session mid-run, and every Mac Re-analyse now does); row 41 indexes the progressive lifecycle fixes by pointer; rows 42–43 open (curation made during a failed progressive Re-analyse; the progressive doc's known gaps); score recomputed. Anchors: `tests/test_progressive_lenses.py`, `tests/test_progressive_quotes.py`, `utils/output_backup.py`, commit "progressive lenses review: nothing unredacted is readable mid-run, and a run that ends without a report keeps what it delivered".
- _2026-10-13_ — trued up: rows 19–25 anchored to the tests and commits that closed them; rows 28–29 reworded for the live-rename fork measured 13 Oct; six Open rows (35–40) from the Mac-half review; score recomputed. Anchors: `eb8509e1`, TODO.md 13 Oct entry, `desktop/CLAUDE.md` renamed-folder entry.

# Lifecycle failure modes: what is designed out, what is proven, what is left

A project lives through first analysis, re-analysis, crashes, server restarts,
renames, moves and copies, and the Mac app, the CLI, the report server and the
pipeline each touch its folder at different moments. On 12 Oct 2026 one of those
moments — the report server starting while a re-analysis had moved
`bristlenose-output/` aside — produced a report with every lens at zero while
every signal was green. An audit of the whole lifecycle followed, the same day,
and three workstreams fixed what it found. This document is the register of
those failure modes: one row each, with the test that proves it is gone or the
reason it is not.

**Read it as a contract.** A row marked *designed out* names a test that was
red before the fix (measured, not assumed) and is green now. A row marked
*open* is understood, and either has a strict-xfail scenario that will flip
loudly when someone fixes it, or says why it has none.

## How the proof is built

- **`tests/test_lifecycle_scenarios.py`** — the storage and serve half, as one
  table. Each scenario builds the folder state that broke, then drives the real
  `create_app` (without `db_url`, so the server chooses where its database
  lives), the real `output_backup` stash, restore, discard and reclaim, and real
  events through the real watcher. No LLM; nothing under test is mocked. Every
  row ends on the same four checks: the database is under
  `bristlenose-output/.bristlenose/`, nothing was written to
  `<project>/.bristlenose/`, one project row, and project 1 — the only row the
  report reads — holds the sessions.
- **The pipeline half** — `tests/test_pipeline_lifecycle_paths.py` (a move, through
  the real `Pipeline.run` with Whisper and the LLM stubbed),
  `test_pipeline_removed_interview.py`, `test_pipeline_report_name.py`,
  `test_pipeline_stage2_cache.py`, and additions to `test_ingest.py`,
  `test_extract_audio.py` and `test_video_thumbnails.py`.
- **`tests/test_serve_project_root.py`, `tests/test_serve_lifecycle_robustness.py`,
  `tests/test_cli_project_paths.py`** — the individual serve and CLI fixes.
- **Swift** — `ProjectDBReadersTests`, `ProjectSubtitleForkTests`,
  `ServeFleetLifecycleTests`, `PipelineRunnerOrphanTests`,
  `ProjectFolderWatcherMoveTests`, `ProjectIndexPathChangedTests`,
  `ProjectIndexDamagedFileTests`.

**Evidence that the table bites.** Run against `41237cae` (the tree before any
fix, in a scratch `git archive` export with the current test files copied in):
6 of the 8 passing scenarios fail. The other two (a re-analysis that succeeds,
and one that fails without losing a star) already held, and are regression
guards rather than proof. Separately, each fix was reverted on its own against
the full set of lifecycle tests; four guards survived that pass and each now has
a test proved red on its mutant (`a4140b48`, `75a56841`).

**Proof scope since 13 Oct 2026.** No scenario in the table writes a manifest, so
none delivers a session mid-run. Since progressive lenses every Mac **Re-analyse…**
is a first analysis that does ([design-progressive-lenses.md](design-progressive-lenses.md) §7 item 18). Rows 2, 3 and 26 are therefore
proven for a re-analysis that delivers nothing before it ends; the delivering case
is covered by the progressive tests row 41 names, and the gap between the two is
row 42.

## The register

### Designed out and proven

| # | Failure mode (what the researcher saw) | Proof | Red before |
|---|---|---|---|
| 1 | First analysis in the Mac app: report empty, everything green | scenario `first-analysis-serve-before-output` | 41237cae |
| 2 | Report server (re)started during a re-analysis: report empty | scenario `server-restarted-mid-reanalyse` | 41237cae |
| 3 | …and the run then fails: report empty | scenario `server-restarted-mid-reanalyse-run-fails` | 41237cae |
| 4 | Crash, relaunch, next run reclaims the old report under a live server: report empty | scenario `crash-then-next-run-reclaims` | 41237cae |
| 5 | `serve <p>/bristlenose-output` then `serve <p>`: two projects; recordings 404 from the first | scenario `output-entry-then-root-entry`; `test_media_is_rooted_at_the_interview_folder_from_either_entry` | 41237cae |
| 6 | Folder renamed under a live server: nothing said, later runs never reach the report | scenario `rename-under-live-serve-is-said` (now a WARNING) | 41237cae |
| 7 | An import landing in a second project row reported as healthy | `test_a_forked_import_is_logged_and_published_under_its_own_row` | mutant |
| 8 | Speaker swaps, recodes, reassigns, pin withdrawals and the importer's pick carry written under a live run, then overwritten by it | `TestWritesRefusedWhileARunOwnsTheProject` (8 tests: six refusals, each now named `run_in_progress`, and the two writes that must still go through — a rename, and a pick whose `kind` is the slot's own role, row 47) | mutant |
| 9 | `run --clean` moved a live run's output out from under it | `test_stash_refuses_to_move_a_live_runs_output` | mutant |
| 10 | `status` reported litter instead of the report, and offered `rm -rf` for the only copy of it | `tests/test_cli_project_paths.py` | red-first |
| 11 | `serve` on an `-o` output folder re-ingested its parent, crashing on the home folder | `test_an_output_folder_elsewhere_is_not_rendered_from_its_parent` | red-first |
| 12 | A transcript-only session never gained its recording | `test_a_transcript_only_session_that_gains_a_recording` | red-first |
| 13 | Moving, renaming or copying the folder re-transcribed everything | `test_a_moved_project_is_not_re_transcribed` + migration test | red-first, mutant |
| 14 | A removed or renamed interview came back into the report | `tests/test_pipeline_removed_interview.py` | red-first |
| 15 | Same-named recordings in two folders merged; the second dropped silently | `tests/test_ingest.py`, `tests/test_extract_audio.py` | red-first |
| 16 | Renaming the folder left a report per name | `tests/test_pipeline_report_name.py` | red-first |
| 17 | Every run re-decoded every video (iCloud: re-downloaded); thumbnails never updated | `tests/test_pipeline_stage2_cache.py`, `tests/test_video_thumbnails.py` | red-first |
| 18 | `analyze` on a project's own transcripts named it `transcripts-raw` — and, with 16, would have deleted the real report | `TestAnalyzeProjectName` | red-first, mutant |
| 19 | Mac sidebar counted sessions across every project row, so it agreed with a forked database | `ProjectDBReadersTests`, `ProjectSubtitleForkTests`; measured live 13 Oct 2026 (row 29) | red-first — the `immutable=1` read lags the WAL, row 35 |
| 20 | Mac app kept a report server from before a sidecar rebuild all day | `ServeManagerFreshnessTests` (in `ServeFleetLifecycleTests.swift`) | mutation-proved |
| 21 | Relaunch mid-analysis: Analysing with an inert Stop, and Analyse could start a second run | `PipelineRunnerOrphanTests` (`ac1415fc`; closed in `eb8509e1` — the caller's sweep had undone the callee's keep) | red-first; `/bin/ps` refusal measured 12 Oct |
| 22 | Finder rename while open: the app served the old path | `ProjectFolderWatcherMoveTests`, `ProjectIndexPathChangedTests`; the window's restart (`pendingStart` when no window is key, `eb8509e1`) has no unit seam | red-first; the serve following measured 13 Oct on the Debug build — and following leads into row 29 |
| 23 | The server for a project left behind was never stopped on a selection change | `ContentView` change, `4ecf1437` | review |
| 24 | A folder moved to the Bin was followed and served from there | `ProjectIndexPathChangedTests` (`eb8509e1`) | review; mutation-proved |
| 25 | A `projects.json` that failed to decode was overwritten with an empty list | `ProjectIndexDamagedFileTests` | red-first — the set-aside is silent, row 36 |
| 26 | A failed re-analysis lost the researcher's curation under a live server | scenario `reanalyse-fails-curation-survives` | held before; regression guard |
| 41 | Progressive first analysis (13 Oct 2026): a serve started or restarted mid-run imported unredacted rows or forgot what it had; a run that ended without a report showed "processing" for ever; a restored stash left the report holding a partial delivery; the previous run's manifest read as this run's | `test_progressive_lenses.py`: `…serve_started_during_a_first_analysis_imports_nothing_at_startup`, `…serve_restarted_mid_run_shows_what_it_already_imported`, `…stopped_first_analysis_keeps_what_it_delivered_as_it_was`, `…whole_import_that_fails_ends_the_overlay_without_lifting_it`, `…report_put_back_under_the_partial_delivery_is_refetched`, `…event_timestamp_in_z_form_compares`; `test_progressive_quotes.py`: `…previous_runs_manifest_is_not_this_runs`, `…serve_restarted_mid_run_does_not_make_the_run_new_to_itself`. Detail: [design-progressive-lenses.md](design-progressive-lenses.md) §5.7 | review of 17259fcb; mutation-proved |
| 45 | A Re-analyse in the Mac app: the shoal gave way within seconds, to an "Analysing…" cover over the serve's status page. The runner read the **previous** run's last progress line ("8 sessions readable") before the new run wrote its start, and the run-id gate compared it with a `run_started` that was still the previous run's (14 Oct 2026) | `PipelineRunnerProgressTests` (the runner's capture at spawn, `beginSpawnedRun`); `RunProgressReaderTests.thePreviousRunsProgressIsNotTheNewRuns` (`EventLogReader.currentRunProgress`) | red-first; mutant (both halves) |
| 46 | `run --clean` under a live serve: the serve went on logging into the set-aside folder, which the run deletes when it succeeds — the serve's whole log for the run was lost | `test_the_serve_log_follows_the_output_folder`; `TestFollowTheLogFile` (`logging.reopen_log_file`: a failed reopen keeps the old handler and is retried; it never creates the folder) | red-first; mutant |
| 47 | "That's Me" on a moderator during a run failed as "check your connection": every SPA pick sends the slot's role as `kind`, and the run guard refused any `kind` as a recode. The toast blamed the connection for every failure | `test_naming_yourself_the_moderator_is_allowed`, `test_a_recode_is_still_refused`; `frontend/src/utils/api.test.ts` (the toast names a running analysis, a refusal, or the connection); `paragraphEdits.test.ts` (a refused paragraph move is no longer silent) | red-first; mutant |
| 49 | After a failed Re-analyse the report came back empty, and the researcher's stars looked lost. The restore landed while the serve was recreating the run's missing schema (`create_all` and every migration take a while), and the serve read the folder's identities after the heal. That recorded the restored folder as attached while its pool held the run's tree, which the restore had set aside, so nothing further was noticed and curation went into the set-aside copy (CI, 17 Oct 2026, macOS and Linux). The reattach now records the folder the heal looked at, and goes round again when that folder moved under it (`_reattach_if_moved`) | `test_a_restore_that_lands_during_the_reattach_is_followed` (the restore injected inside the heal); scenario `reanalyse-fails-curation-survives` was the intermittent witness | red-first; mutant (the second round, and what it records, each alone) |
| 50 | A restore landing while the serve started put back a `run_completed` the watcher counted as already imported, because the watcher read its baseline when its task first ran, after the startup import. With a backup carrying no database, the report stayed empty (CI, 17 Oct 2026). The baseline is now read before the startup import, and a completion in the log at the watcher's start that is not in it is imported then (`completed_run_ids`, `run_event_watcher(imported=…)`) | `test_a_restore_before_the_watcher_first_reads_the_log_is_imported` (the restore injected straight after the startup import); `test_serve_while_the_output_is_stashed_then_restored` was the intermittent witness | red-first; mutant (baseline read by the task, baseline read after the import, no dispatch at start, each alone) |
| 27 | After a crash, the previous report stayed hidden until the next run started. The server now puts it back on start, but only over a **stranded** run (started, no terminus, no live owner): an absent output folder or one holding only a log is also a run's own start-up, and reclaiming there would put the old report back under it (15 Oct 2026, `output_backup.reclaim_after_crash`) | scenarios `crash-report-visible-before-rerun`, `server-in-run-start-up-leaves-backup`, `server-under-live-run-leaves-backup`; `server-restarted-mid-reanalyse` is the absent-folder guard | red-first; mutant (each guard alone) |
| 34 | More than 50 projects: the 51st got no folder lease, so anything borrowing its folder got a bare path with no sandbox scope. The 50 watchers now go to the most recently opened projects, and opening a project or asking for its folder takes a lease on demand, the least recently opened giving way (15 Oct 2026, `ProjectIndex.ensureLease`). Masked in practice by row 39's leaked scope, which is why the cap never showed | `ProjectLeaseOnDemandTests` (4 tests, cap lowered to 1) | mutant (each of order, on-demand and eviction alone) |
| 29 | A folder moved or renamed forked the project, with the app closed or open; the report showed the stale first row. A study's own database now holds one study, found by its marker (`<output>/.bristlenose/study.json`, minted by the first run or serve, kept across Re-analyse), never matched by path; stored paths are healed; a fork left by an older release is removed at the next import unless curation hangs off it (15 Oct 2026, [design-project-identity.md](design-project-identity.md) §3–4, §10) | scenario `moved-while-closed`; `test_lifecycle_end_to_end.py` (`…moved_while_closed_keeps_its_curation`); `tests/test_study_identity.py` | strict xfail flipped; mutant (six changes, each alone) |
| 30 | A copied folder forked the same way. A copy now opens as the study it was copied from, with its curation, in its own database, so nothing written in one reaches the other; the app re-mints its id on arrival (phase 4) | scenario `copied-elsewhere`; `…a_copy_is_an_independent_duplicate` | strict xfail flipped |
| 31 | A renamed interview got a new session id, so its stars, tags and edits were deleted, and it was transcribed again. A session is now found by its recording's content first (`utils/fingerprint.py`, registry version 3), then by its last known place (a cloud placeholder), then by name; transcription is keyed by content, and the stored file path is healed. Filing interviews into a subfolder is the same case (15 Oct 2026, [design-project-identity.md](design-project-identity.md) §5–7) | `…renamed_interview_keeps_its_curation…`, `…filed_into_a_subfolder…` (`test_lifecycle_end_to_end.py`); `TestContentKeys`; `test_fingerprint.py`; the 12-Oct manifest migration test | strict xfail flipped; mutant (six of seven changes; the seventh was redundant and removed) |

### Open, engineered (strict xfail in the scenario table)

| # | Failure mode | Why it is open | What fixes it |
|---|---|---|---|
| 28 | A CLI `serve` does not follow its folder to a new name | by design; it says so (row 6), and the Mac app restarts it at the new path — which is what forks row 29 | restart the server; or re-derive the root from the open database's path |

### Open, not engineered

| # | Failure mode | Why there is no scenario yet |
|---|---|---|
| 32 | Two servers, or two app windows on two machines, on one folder at once | no lock exists to test; SQLite serialises writes but imports can still race |
| 33 | Network shares, ExFAT, iCloud-evicted databases | WAL is unsupported on network filesystems; needs real volumes, not a temp dir |
| 35 | The Mac readers open the database with `?immutable=1`, which ignores the WAL: after a fork is repaired the *Report out of date* row stays until a checkpoint, and curation made this session can count as zero, so **Re-analyse…** skips its confirmation | a committed-but-uncheckpointed row is invisible to that open (measured against sqlite 3.53); needs a read without `immutable` falling back on `CANTOPEN`, or a Python-side checkpoint after curation writes — review finding, parked 12 Oct 2026 |
| 36 | A damaged `projects.json` is set aside (row 25) and the next launch is an empty Welcome with nothing on screen; valid JSON from a newer build is treated as damage | no surfacing yet; an older `.dmg` opening a TestFlight-written file strands the sidebar in every build — parked 12 Oct 2026 |
| 37 | A rename during a live run: Python holds the old path while the app follows and restarts the serve at the new one | product call: follow at once (report honest) or defer until no run (run honest) — open question 12 Oct 2026 |
| 38 | A serve restart on a path change while the researcher is mid-edit in the report | rare and correct until shown otherwise — open question 12 Oct 2026 |
| 39 | `ProjectIndex.resolveBookmark` starts a security scope it never stops, at launch and on volume mount | pre-existing; the per-activation multiplier was removed in `eb8509e1`; a leaked extension per project per event, bounded by relaunch |
| 40 | A cross-volume rename or move: whether the security-scoped extension follows | a same-volume rename is measured to follow (13 Oct 2026); cross-volume is not, and Finder does it as copy + delete |
| 42 | Curation made **during** a progressive Re-analyse that then fails is lost: the restore sets the failed tree, its database included, aside to `.bristlenose-output-failed`, and the next run's stash clears it (`utils/output_backup.py`) | inferred from code, not measured; and a product call before a fix — carry it into the restored report, or accept the loss (open question 14 Oct 2026). Row 26 covers curation made *before* the run only |
| 43 | The progressive doc's known gaps: `data_version` restarts at 0 with the server (one refetch skipped); a resumed run imports at stage 6 while the Mac's shoal covers it; the chain can count a session the server refused, and the shoal then drops to an empty status page; a failed Re-analyse's restore reaches the server but not the Mac | indexed by pointer, not copied: [design-progressive-lenses.md](design-progressive-lenses.md) §5.7 "Known, not fixed" and §7 items 16 and 18 |
| 44 | A pick or rename made in the second after `run --clean` moves the output folder, before the serve's next poll reattaches, returns 200 and lands in the set-aside database, which a successful run deletes | inferred from code (review of `4f6f71d0`), not measured; a run-owned window of about one poll. Fix would be to refuse every curation write until the reattach, or to reattach on the stash itself |
| 48 | A report mounted while the serve is importing the first sessions showed the "in progress" status page for 74 s, not the ≤3 s its own poll allows (14 Oct 2026, 22:09:22 → 22:10:36). The serve's log for that window was lost (row 46), so the cause is unexplained | not reproduced; re-measure with the log now following the folder |

**Checked and not a failure mode:** only the two **Re-analyse…** call sites pass
`clean: true` (`ContentView.swift`, the confirmation sheet and the no-curation
path); every other start, Retry included, resumes. Since 13 Oct 2026 those two
sites start a progressive first analysis (row 42's context).

**Proven on macOS and Linux only: rows 3, 4, 6 and 26, and the scenario
`reanalyse-succeeds-live-serve`.** Each scenario moves
`bristlenose-output/`, or the project around it, while a server holds
`.bristlenose/bristlenose.db` and its log open, and Windows refuses to move a
folder with an open file in it (WinError 5 / 32). The scenarios skip there
(`_MOVES_AN_OPEN_DATABASE`, 13 Oct 2026, after they turned the Windows CI cell
red). What a Windows CLI user gets instead is a refusal, not a loss: `run
--clean` under a live `serve` cannot set the report aside, says *"this run will
write over it"*, and resumes in place; a restore or reclaim under one leaves the
previous report in `.bristlenose-output-previous` and logs where. Listed as an
open item in `docs/design-windows-port.md`.

**Accepted consequence, not a defect.** Selecting a project that has never been
analysed now creates an empty `bristlenose-output/` beside the interviews
straight away (the database is created eagerly so the first run and the server
share it). It used to leave a hidden `.bristlenose/` folder in the interview
folder instead.

## The score

**By count:** of 50 failure modes, 37 are designed out and proven (25 fixed on
12 Oct 2026, one that already held and is now guarded, row 41's progressive
fixes of 13 Oct counted as one, rows 45–47 of 14 Oct, rows 27, 29, 30, 31 and 34 of 15 Oct, and rows 49–50 of 17 Oct) — **74%**. Thirteen are
open: one engineered, twelve not. _(13 Oct 2026: rows 35–40 added from the review
of the Mac half; 14 Oct: rows 41–43 from the progressive-lenses truing, then 44–48
from a `--clean` Re-analyse in the app; 17 Oct: rows 49–50 from two CI flakes. The denominator moved each time.)_

**By how often a researcher would meet them**, which is the number that
matters, it is higher. Rows 1–4 sat on the path every Mac user takes: a first
analysis and every re-analysis. Rows 13–17 hit anyone who adds, removes or
renames interviews, or moves a study folder. Those two groups are where nearly
all real failures would have come from, and both are closed. Of what is left,
only 29–30 (moving or copying a study) is something researchers do routinely;
27, 28, 32 and 34 need an unusual sequence; 31 is a design limit with a
visible cause; 33 depends on where the study lives. My estimate — a judgement,
not a measurement — is that the fixes remove **85–90% of the lifecycle failures
a researcher would actually hit**. The single largest remaining item is 29–30,
and it is one design change (WS4), not a list.

## What can still trip us up

In order of likely cost:

1. **Moving or copying a study (29–30).** Researchers archive finished studies,
   move them between client drives, and copy them to colleagues. Today that
   gives a report showing the last state before the move, and new analysis
   landing where the report cannot see it. The sidebar now names the fork
   (row 19), so it is loud rather than silent, which is the main reason it is
   not worse. [design-project-identity.md](design-project-identity.md) is the fix,
   decided 13 Oct 2026.
2. **The Mac app has no end-to-end lifecycle test.** Rows 19–25 are proven by
   unit tests of each piece; nothing drives the built app through
   add → analyse → re-analyse → quit mid-run → relaunch → rename. The 12 Oct
   incident was exactly an interaction between pieces. One scripted pass with the
   Debug build against a copy of the smoke fixture would close most of this. A
   partial pass was done by hand on 13 Oct 2026 (sandboxed Debug build, a real
   drop, a Finder rename, a cold relaunch): it found row 29 live. Still not
   scripted.
3. **Storage we do not control (33).** A study on SMB, or a database iCloud has
   evicted, has not been run. The likely failures are slow or locked rather than
   lost, but that is a prediction.
4. **The scenario table checks storage, not the screen.** It proves that project
   1 holds the sessions; it does not render the report. The SPA reading project
   1 is pinned elsewhere (`app.py` injects `data-project-id="1"`), but a future
   change to how the SPA picks its project would bypass these checks.

## Keeping it true

- A new lifecycle defect gets a row here **and** a scenario (or a reason it has
  none) before its fix lands.
- When WS4 or the stash reclaim lands, the matching xfail flips and fails the
  run; move the row to *designed out* in the same commit.
- The pipeline-side and Swift-side proofs live with their code; this register is
  the index, not a copy.
