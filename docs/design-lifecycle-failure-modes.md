---
status: current
last-trued: 2026-10-12
---

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
| 8 | Speaker swaps, recodes, reassigns, pin withdrawals and the importer's pick carry written under a live run, then overwritten by it | `TestWritesRefusedWhileARunOwnsTheProject` (5 tests) | mutant |
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
| 19 | Mac sidebar counted sessions across every project row, so it agreed with a forked database | `ProjectDBReadersTests`, `ProjectSubtitleForkTests` | red-first |
| 20 | Mac app kept a report server from before a sidecar rebuild all day | `ServeFleetLifecycleTests` | red-first |
| 21 | Relaunch mid-analysis: Analysing with an inert Stop, and Analyse could start a second run | `PipelineRunnerOrphanTests` | red-first (sandbox measured) |
| 22 | Finder rename while open: the app served the old path | `ProjectFolderWatcherMoveTests`, `ProjectIndexPathChangedTests` | red-first |
| 23 | The server for a project left behind was never stopped on a selection change | `ContentView` change, `4ecf1437` | review |
| 24 | A folder moved to the Bin was followed and served from there | `ProjectFolderWatcherMoveTests` (`eb8509e1`) | review |
| 25 | A `projects.json` that failed to decode was overwritten with an empty list | `ProjectIndexDamagedFileTests` | red-first |
| 26 | A failed re-analysis lost the researcher's curation under a live server | scenario `reanalyse-fails-curation-survives` | held before; regression guard |

### Open, engineered (strict xfail in the scenario table)

| # | Failure mode | Why it is open | What fixes it |
|---|---|---|---|
| 27 | After a crash, the previous report stays hidden until the next run starts | the server never reclaims a stash itself | serve calls `output_backup.reclaim_stale` when no run owns the project |
| 28 | A CLI `serve` does not follow its folder to a new name | by design; it says so (row 6), and the Mac app restarts it | restart the server; or re-derive the root from the open database's path |
| 29 | A folder moved with the app closed forks the project; the report shows the stale first row | project identity is the absolute path | the study marker, [design-project-identity.md](design-project-identity.md) §3–4 and §10; decided 13 Oct 2026, phase 2 |
| 30 | A copied folder forks the same way, and the copy's writes reach the original | same | same; a copy is an independent duplicate, re-minted on arrival ([design-project-identity.md](design-project-identity.md) §9) |

### Open, not engineered

| # | Failure mode | Why there is no scenario yet |
|---|---|---|
| 31 | A renamed interview gets a new session id, so its stars, tags and edits are deleted | the session key is the file stem by design; a stable key needs content identity — the recording fingerprint and registry v3 in [design-project-identity.md](design-project-identity.md) §5–6 (decided 13 Oct 2026, phase 2) |
| 32 | Two servers, or two app windows on two machines, on one folder at once | no lock exists to test; SQLite serialises writes but imports can still race |
| 33 | Network shares, ExFAT, iCloud-evicted databases | WAL is unsupported on network filesystems; needs real volumes, not a temp dir |
| 34 | More than 50 projects: the 51st gets no folder lease, so no sandbox scope | rare; a Swift-side cap |

**Checked and not a failure mode:** only the two **Re-analyse…** call sites pass
`clean: true` (`ContentView.swift`, the confirmation sheet and the no-curation
path); every other start, Retry included, resumes.

**Accepted consequence, not a defect.** Selecting a project that has never been
analysed now creates an empty `bristlenose-output/` beside the interviews
straight away (the database is created eagerly so the first run and the server
share it). It used to leave a hidden `.bristlenose/` folder in the interview
folder instead.

## The score

**By count:** of 34 failure modes, 26 are designed out and proven (25 fixed on
12 Oct 2026, one that already held and is now guarded) — **76%**. Eight are
open: four engineered, four not.

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
   Debug build against a copy of the smoke fixture would close most of this.
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
