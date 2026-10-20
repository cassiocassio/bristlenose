---
status: partial
last-trued: 2026-10-20
trued-against: HEAD@main (fa686f9a, 2407fedc, 4702f48f) on 2026-10-20
---

> **Truing status:** Partial — Stop-is-a-lie alpha blocker now fully closed (4 commits, 24 Apr 2026); attached-orphan visibility gap closed (log tail in popover); Stop click acknowledged instantly across pill / popover / sidebar (`isStopping` flag). Sandbox-clean probes (`proc_pidinfo`/`proc_pidpath`) — **run side shipped 12 Oct 2026 on libproc with a start-time token (`ac1415fc`, `eb8509e1`); see the PID-file note** — and unified serve-side reconcile remain design-intent only. **Quit propagation shipped 20 Oct 2026 (R19)** as `PipelineRunner.stopAllForQuit()` plus a self-stopping hosted run; see §Quit propagation. The orphan-attach premise ("attach, don't kill") now holds only in a sub-second window.
>
> **Serve-side reconcile superseded (May 2026, A6 redesign):** the §"sandbox-incompatible" lsof exec in `ServeManager.killOrphanedServeProcesses()` was deleted, not migrated to libproc. Sidecar self-terminates on parent-death via `bristlenose/server/lifecycle.py`; host uses `bind(0)`. The PID-file-scan-and-reconcile design described later in this doc still applies to the **run** subprocess (`PipelineRunner`), but no longer to **serve**. References to `ServeManager.killOrphanedServeProcesses()` below are historical.

## Changelog

- _2026-10-20_ — trued after R19 (quit mid-run): Quit propagation as shipped (`stopAllForQuit`, `fa686f9a`); a hosted run stops itself when the app goes (`2407fedc`) and records `run_cancelled`, not `run_failed`, if it ends after the app has gone (`4702f48f`); "attach, don't kill" marked superseded; the two PID files distinguished; line refs replaced by symbol names; implementation plan, sandbox section and open questions brought up to date.
- _2026-10-13_ — trued up: run-side orphan attach as shipped: the PID-file format, the three-valued verdict, the 14 Jul → 12 Oct window in which it was unreachable; implementation-plan steps 3–5 annotated. Anchors: `PipelineRunner.ownedRunVerdict`, `PipelineRunnerOrphanTests`, register row 21.
- _2026-06-21_ — repointed the "user-task progress surfaces" reference off the deleted `PipelineActivityItem` onto the shipped sidebar-row surfaces (`ProjectRowActivityIndicator` / `ProjectRow`); per-project progress now lives on the row.
- _2026-04-24 (evening)_ — Stop-is-a-lie + stale-pill alpha blockers fixed and documented. Bug banners replaced with "Fixed" content citing commits `896c074` (kill fix), `c0eb709` (escalation), `2b5475f` (`.running` transition), `da5cc45` (log tail + `isStopping`). Inline body updated with new flags (`attachedFromOrphan`, `isStopping`) and helpers (`logFileURL`, `readLogTail`, `scheduleOrphanCancelEscalation`, `orphanLogOffsets`).
- _2026-04-24 (afternoon)_ — Tier 2 truing follow-up: cite commit `49930e4` for the owned-process cancel-flag fix (was "this branch, working-tree"); add corner-case notes for the `projectIndex`-lookup PID-file leak (`PipelineRunner.swift:776-778`) and the spawn-vs-`writePIDFile` race (`:737-742`).
- _2026-04-23_ — trued up during port-v01-ingestion QA: PID file naming correction (shipped is `<uuid>.pid` without `<role>-` prefix); `atexit` ownership correction (Swift side removes, not Python); sandbox-compat scoped (`/bin/ps` exec in `aliveOwnedRunPID` is also incompatible, not just `lsof`); ServeManager port range corrected (`:5173,8150-9149`); Stop-is-a-lie bug called out in §Cancellation; attached-orphan visibility gap (stale "Starting up" pill) called out in §The design; `stopAll()` marked as planned. Anchors: `PipelineRunner.swift:341-358, 626-660, 690`, `ServeManager.swift:305-334`. Commits: 6d08f3f, 5e254cd.
- _20 Apr 2026_ — initial draft surfaced during port-v01-ingestion QA.

# Subprocess lifecycle — orphan management

**Status:** design, partly shipped. Surfaced during port-v01-ingestion QA, 20 Apr 2026; trued 23 Apr 2026.
**Related:** `desktop/CLAUDE.md` "Zombie process cleanup", `docs/design-pipeline-resilience.md`, `docs/private/archive/sprint2-tracks.md` Track C C0 (sandbox spike).

## The principle

**Two categories of work, two visibility rules.**

| Category | Examples | Visibility |
|---|---|---|
| **User-initiated tasks** | "Analyse this folder" (`bristlenose run`), "Apply this codebook" (autocode), "Export clips for these quotes", "Add interviews to this project" | **Visible.** Per-task progress, where the user is already looking. Pill, ActivityChipStack, sidebar subtitle. The user asked for this, they want to see it happen. |
| **Infrastructure** | `bristlenose serve` lifecycle, port allocation, Cmd+R cleanup, reconciling across launches, deciding whether to attach an orphan or spawn fresh | **Invisible.** No surface, no menu, no list. The user doesn't know these processes exist. If they have to think about them, the design has failed. |

The line between the two: did the user explicitly ask for this thing to happen? `run` yes (they dropped a folder), `serve` no (it's how the report gets to the WebView). Autocode yes (they clicked Apply), the SQLite WAL writer no.

This design is about the **infrastructure** half. User-task progress surfaces (the sidebar row's progress ring + subtitle — `ProjectRowActivityIndicator`, `ProjectRow`; `ActivityChipStack` in the report SPA) are already in place and stay as they are. What changes here is the part the user shouldn't see — orphan reconciliation, port cleanup, sandbox-compat probes.

The question this design answers: when an attached orphan from a previous launch shows progress in the toolbar pill, the user should see exactly what they'd see if we'd just spawned it. Same surface. Same affordances. They should never know it was an orphan. That's the test.

## What's in scope

Long-running Bristlenose subprocesses spawned by the Mac app:
- `bristlenose run` (pipeline ingestion, minutes to hours)
- `bristlenose serve` (HTTP server for the React SPA, lifetime of project session)
- Any future `bristlenose <verb>` subcommand that runs longer than a Mac event loop tick

In-process tools (FFmpeg, Whisper) are children of the Bristlenose subprocess, not direct children of the .app — they die when their parent dies. Out of scope.

## The problem surfaced during QA

Two-day debug detour during port-v01-ingestion QA, all caused by orphan subprocesses:

1. **Cmd+R doesn't kill subprocess children.** macOS doesn't propagate parent death by default. Each Cmd+R cycle leaves `bristlenose run` and/or `bristlenose serve` alive. Next launch's Bristlenose can't bind ports, can't tell what the user's project state should be, and surfaces confusing errors ("address already in use" on a port the user never asked about).
2. **`bristlenose run` auto-served and waited for Ctrl-C** — subprocess never reached exit, `terminationHandler` never fired, state machine stuck. Originally worked around in port-v01-ingestion by passing `--static` to suppress auto-serve. (Post-A3 / 12 May 2026 the `--static` flag is gone; the spawn passes the hidden `--no-serve` instead — `PipelineRunner.spawn`.)
3. **Multiple Bristlenose.app instances** — Cmd+R sometimes failed to kill the previous .app, leaving 3 instances running, each fighting for keychain prompts and ports.
4. **Today's cleanup mechanism doesn't survive sandbox.** `ServeManager.killOrphanedServeProcesses()` uses `lsof -ti :5173,8150-9149` + `kill`. Both `lsof` exec and arbitrary-PID `kill` are blocked under App Sandbox. `PipelineRunner.aliveOwnedRunPID()` additionally execs `/bin/ps -p <pid> -o uid=` and `-o args=` twice per scan — also sandbox-incompatible. TestFlight build will silently fail to clean up until both sites move to `libproc.h` probes.

## The design

### CLI side: every long-running subprocess writes a PID file

On startup, both `bristlenose serve` and `bristlenose run` write `<App Support>/Bristlenose/pids/<role>-<id>.pid` (e.g. `serve-<projectID>.pid`, `run-<projectID>.pid`). PID file contains the subprocess PID + start timestamp + project path.

On clean exit, subprocess removes its own PID file via `atexit` handler.

Force-quit / SIGKILL leaves the file behind — that's the signal the orphan-recovery path uses.

> **Since 20 Oct 2026 the run rarely survives to be found** — a hosted run stops itself within 0.5 s of the app going (§Quit propagation), so a leftover file usually reads `.stale` at the next launch.
>
> **Two PID files, not one.** This section and the next are about the Swift-owned `<App Support>/Bristlenose/pids/<project-id>.pid`. Python separately writes and removes `<output>/.bristlenose/run.pid` (`run_lifecycle._write_pid_file`, Phase 1f), which the concurrent-run refusal and `EventLogReader.pythonOwnedRunIsAlive` read.

(Already implemented for `run` in port-v01-ingestion Slice 7. Extend to `serve` in this design's first slice.)

> **Superseded 2026-04-23 — naming and ownership corrections:**
> - Shipped file name is `<project.id.uuidString>.pid` (no `<role>-` prefix). Swift-side writer is `PipelineRunner.writePIDFile` at `PipelineRunner.swift:442`. When `serve` gets a PID file too (planned), the flat directory needs either a `<role>-` prefix (reviving the original spec) or two subdirectories (`pids/run/`, `pids/serve/`) to avoid collision.
> - **PID file is Swift-owned**, not Python-owned. Swift writes after `proc.run()` in `spawn`, and removes in `handleTermination` / `handleOrphanExit`. Python has no `atexit` handler touching these files — the App Support directory is in Swift's sandbox, not Python's. The "subprocess removes its own PID file" claim above is inverted; correct behaviour is "Mac side removes the PID file when the termination handler or orphan poller confirms exit."
> - File contains **PID only** (`String(pid)`), not start timestamp or project path. Verification of ownership goes via `/bin/ps -o uid=` and `-o args=` (shipped), or `proc_pidinfo`/`proc_pidpath` (planned, sandbox-clean).
>   **Since 12 Oct 2026 (`ac1415fc`, `eb8509e1`):** the file is `"<pid>\n<start-token>"`, the token being the libproc `"<tvsec>.<tvusec>"` string `EventLogReader.procStartTime` yields; a pid-only file is *stale*; a spawn whose libproc query failed writes the non-empty sentinel `PipelineRunner.noStartToken`, read as *indeterminate*. Ownership is `kill(pid, 0)` + `proc_pidinfo` uid + the token — no `proc_pidpath`, no argv.

### Mac side: scan-and-reconcile at app init, sandbox-clean

`PipelineRunner.init()` and `ServeManager.init()` both walk `<App Support>/Bristlenose/pids/` at startup:

For each PID file:
- **Dead PID** (`kill(pid, 0) != 0`): silently sweep the file. Manifest is the source of truth for state.
- **Alive, owned by us** (uid match via `proc_pidinfo` + argv contains `bristlenose run|serve` via `proc_pidpath`): **attach**, don't kill. The subprocess is still doing useful work and (per `docs/design-pipeline-resilience.md`) writes atomically to disk. Display it in the project's existing UI surface (sidebar row, toolbar pill) as if we'd just spawned it.

> **Superseded for hosted runs, 20 Oct 2026 (R19).** The premise "the subprocess is still doing useful work" was false in practice: a run's stdout is a pipe to the app, so a run that outlived it died at its next print (EPIPE → `run_failed`, "CLI exited with code 1"), after a relaunch had attached and shown "Resuming…". The rule now is **leaving the app stops the run; Analyse resumes from the cache** — ⌘Q SIGINTs it, a force-quit or crash makes it stop itself (§Quit propagation). Attach survives for the sub-second window before a stopping run exits, and for a run whose signal handler is deferred by a long C call (Whisper/torch — inferred from the GIL note below, not measured).
- **Alive, foreign uid or wrong argv**: leave alone, sweep the stale file. PID was reused by something we don't own.

This replaces the `lsof`/`kill` approach. All probes (`kill(pid, 0)`, `proc_pidinfo`, `proc_pidpath`) are sandbox-clean — they work entirely through the kernel via `libproc.h`. No subprocess exec required.

> **As shipped, 12 Oct 2026:** the verdict is three-valued — `alive` / `stale` / `indeterminate` (`PipelineRunner.ownedRunVerdict`, a pure table with every probe injected). Only `stale` removes the file; `indeterminate` keeps it, because a verifier that cannot verify must never upgrade a pid to *ours* and must never delete the evidence. The caller's unconditional sweep that undid that keep one frame up was the first finding of the 12 Oct review (`eb8509e1`). A scan also refuses to attach to this process's own live run (`applyScan`), since rescans now fire on rename and bookmark heal.

> _Historical — true 23 Apr to 12 Oct 2026, replaced by the libproc check above._ **Superseded 2026-04-23.** The bullet above is **design-intent**. Shipped `aliveOwnedRunPID` (`PipelineRunner.swift:326-358` at the time) uses `kill(pid, 0)` + TWO `/bin/ps` execs (`-o uid=`, then `-o args=`). Same outcome as the libproc path, but not sandbox-clean today — migrating is a separate slice before TestFlight. The target state ("all probes through `libproc.h`") is the planned endpoint, not a shipped capability.
>
> **14 Jul → 12 Oct 2026:** with the sandbox on in both configurations, those two execs failed on every launch (`Operation not permitted`, measured 12 Oct from the sandboxed Debug test host); the failure read as *not ours*, the file was deleted, and orphan attach was unreachable in every sandboxed build — a relaunch mid-run showed Analysing with an inert Stop while Analyse could start a second run (`design-lifecycle-failure-modes.md` row 21). Closed by `ac1415fc` + `eb8509e1`.

The orphan-attach UX surface is **the project's normal status indicators** — the sidebar row says "Analysing…", the toolbar pill shows the stage. The user has no way to tell whether the subprocess was just spawned by this Bristlenose instance or attached from a previous instance. That's the design's whole point.

> **Fixed 2026-04-24 — attached-orphan visibility gap.** Closed in commit `da5cc45`. The orphan poll task now tails `<output>/.bristlenose/bristlenose.log` off disk every 2s — `readLogTail(url:offset:)` seeks past previously-read bytes (capped at 64 KB per read), splits on newlines, appends into `liveData.outputLines` (same surface owned-process uses). Per-project byte offsets in `orphanLogOffsets` start at end-of-file at attach time so the popover doesn't dump the prior-run history. The popover headline switched from "Starting up — loading models" to "Resuming analysis (reconnected after app restart)" via a new `attachedFromOrphan: Bool` flag on `PipelineProgress`; the latest log line surfaces as a subtitle and "Show technical details" scrolls real progress lines.

### Cancellation: SIGINT via the existing surfaces

The user cancels via the toolbar pill's Stop button (per-project surface). Implementation: `kill(pid, SIGINT)` after re-verifying ownership. Matches today's behaviour.

There is no global "kill all" surface. If the user wants to nuke everything, they Quit Bristlenose — and a separate part of this design (below) handles propagating that decision to the children.

> **Fixed 2026-04-24 — Stop-is-a-lie bug (alpha blocker).** Closed across four commits:
>
> 1. **`896c074`** — drop the racy `aliveOwnedRunPID` re-verify in the orphan cancel path (`PipelineRunner.swift:626`). Trust the attach: `attachedOrphanPIDs[project.id]` already proves we owned this PID at attach time. Send `kill(pid, SIGINT)` directly and interpret errno: 0 → success, ESRCH → already gone (run `handleOrphanExit` immediately), EPERM/other → log error and **leave state intact**. Don't clear state on success either — let the existing 2s orphan poll task detect the death via `kill(pid, 0) != 0` and run `handleOrphanExit` for clean teardown + manifest re-read.
> 2. **`c0eb709`** — escalate when SIGINT alone won't cut through. Whisper / torch / ctranslate2 hold the GIL during long C calls, so a Python signal handler can be deferred 30–60s during model load. New `scheduleOrphanCancelEscalation(pid:projectID:)` Task: SIGINT at t=0, SIGTERM at +5s if PID still alive, SIGKILL at +8s. Bails at any step if the PID is already dead or `attachedOrphanPIDs[projectID]` no longer matches. The user's "Stop" must always succeed.
> 3. **`2b5475f`** — let `handleOrphanExit` transition out of `.running`. The fix above relied on the orphan poll task → `handleOrphanExit` → manifest re-read → `applyScanResult` chain to clear the pill, but `applyScanResult` guards against overwriting `.running` (passive sidebar scans must not clobber active runs). Set `state[projectID] = .idle` inside `handleOrphanExit` before scheduling the manifest re-read; the re-read can then upgrade to `.ready` if the manifest says all stages complete.
> 4. **`da5cc45`** — acknowledge the click instantly. New `isStopping: Bool` flag on `PipelineProgress`, set unconditionally at the top of `cancel()` for both owned and orphan paths. Toolbar pill, popover headline, popover Stop button (greyed + relabelled "Stopping…"), and sidebar row subtitle all flip on the same flag. No more user-mashing-Stop while signals propagate.
>
> Owned-process cancel was fixed earlier (`49930e4`); the wedge-in-C-land risk applies to the owned path too — escalation is currently orphan-only, tracked for the next slice.

**Owned-process cancel (non-orphan)** was fixed in commit `49930e4`. Pre-fix: `cancel()` called `proc.interrupt()` and relied on the termination handler to route `.failed`. Any non-zero exit landed in `.failed` including user-initiated cancels — "Transcription failed" appeared after a Stop click. Post-fix: a `cancellationRequested` flag (`PipelineRunner.cancellationRequested`) is set in `cancel()` before `proc.interrupt()`; `handleTermination` checks it and routes to `.idle` with log line "run cancelled". Flag cleared at each `spawn`. Both paths now also flip `progress.isStopping = true` at the top of `cancel()` so the UI acknowledges the click instantly.

**Open corner cases (not yet shipped, surfaced 24 Apr 2026):**
- **PID-file leak via `projectIndex` lookup.** `handleTermination` removes the PID file by looking the project up from `projectIndex`. If `projectIndex` is unwired (not logged there — the only such log is in `startNextQueued`) or the project was deleted between spawn and termination, the PID file is leaked. Next launch's orphan-attach scan will find a dead PID and the `kill(pid, 0)` sweep removes it harmlessly — but worth being explicit so a future refactor doesn't assume the cleanup path is bulletproof.
- **Spawn-vs-`writePIDFile` race.** `PipelineRunner.spawn` carries an in-source comment acknowledging a window where an app crash between `proc.run()` and `writePIDFile` leaves an unattachable orphan (subprocess running, no PID file). Accepted trade-off; documenting it here so the design intent survives. Since 20 Oct 2026 that orphan stops itself within 0.5 s (§Quit propagation), so the window no longer leaves a run going.

### Idle-sleep prevention during a run (Jun 2026)

A long unattended analysis on AC power used to freeze at the macOS idle-sleep timer — the run didn't fail, it *stalled* until the user woke the Mac. `PipelineRunner` now holds a `RunSleepAssertion` (`ProcessInfo.beginActivity(options: .userInitiated)`) whenever any project's `PipelineState` is `.running`, driven off `state.didSet` (single source of truth; `setHeld` is idempotent so coarse-transition churn can't thrash or leak). `.userInitiated` disables idle *system* sleep but leaves *display* sleep enabled (the screen still dims — no reason to burn the backlight for an unwatched job). It deliberately does **not** prevent *forced* sleep: lid-close on battery sleeps the Mac regardless (OS guarantee), and recovery from that is the orphan-attach/resume path above, not the assertion. `beginActivity` is sandbox-clean (process-local power hint, no entitlement). See `desktop/CLAUDE.md` for the design-choice rationale; edge machine unit-tested in `RunSleepAssertionTests.swift`.

### Quit propagation: kill children when the .app exits

Today's `.onReceive(NSApplication.willTerminateNotification)` calls `serveManager.stop()`. Extend to:
- `serveManager.stop()` — already does SIGINT to the active serve subprocess, kept.
- `pipelineRunner.stopAll()` — **planned, not shipped.** New method that SIGINTs every active spawn AND every attached orphan. Ensures Cmd+Q leaves no orphans behind. PID files get cleaned by the Swift-side termination handler; if SIGKILL was needed, the next launch's reconcile pass sweeps the stale file.

For Cmd+R / Xcode's stop button, `willTerminate` may not fire (SIGKILL bypasses it). The reconcile pass at next launch is the safety net.

> **As shipped, 20 Oct 2026 (R19).** The proposal above is kept as the baseline; what landed differs in shape.
>
> - **Serve** has registered its own `willTerminate` observer in `ServeManager` since 16 Aug 2026 ("the object that owns the process owns its shutdown"); there is no `.onReceive` on the root view.
> - **Runs:** `PipelineRunner` registers its own observer and calls `stopAllForQuit()`, which SIGINTs the run it spawned and every attached orphan, once each (`quitSignalTargets`). SIGINT then the pipe closing records `run_cancelled` — measured against the real CLI at every point tried, mid-transcription included — which the row shows as **Stopped**, resumable. No escalation: the app has exited before a timer could fire. The PID file is not removed on Quit (the async termination handler never runs); the next launch's scan finds a dead pid and sweeps it as `.stale`. (`fa686f9a`; tests `PipelineRunnerQuitTests`.)
> - **The queue is not kept.** Queued runs are dropped on Quit and only logged (`quit: N queued run(s) not kept across launches`). Persisting it — and whether a relaunch should resume what Quit stopped — is an open product decision: a relaunch must not spend money on stale intent.
> - **Force-quit, crash, Xcode stop:** see the next subsection; the reconcile pass is now mostly a dead-pid sweep.

### Hosted-run self-termination (CLI side, 20 Oct 2026)

Why: a run's stdout and stderr are a pipe to the app (`PipelineRunner.spawn`). A run that outlived the app carried on until its next print, hit EPIPE and recorded `run_failed`; a relaunch inside that window attached, showed "Resuming…", then "CLI exited with code 1". Three Python mechanisms, all gated on `_BRISTLENOSE_HOSTED_BY_DESKTOP=1`:

1. **Parent-death watcher in `run`** (`cli.py`, top of `run`, `install_parent_death_watcher(poll_interval_sec=0.5)`). The same watcher `serve` and `doctor --fetch` use; on reparenting it SIGTERMs itself, which `run_lifecycle` records as `run_cancelled`. 0.5 s rather than serve's 2 s because a run prints at every stage. A CLI run never installs it — a `nohup`'d run must carry on. (`2407fedc`; `tests/test_hosted_run_quit.py`.)
2. **A run already stopping ignores further signals** (`run_lifecycle._signal_handler`). ⌘Q now delivers two — the app's SIGINT, then the watcher's SIGTERM — and a second `KeyboardInterrupt` mid-unwind escaped the cancel write or was wrapped by pydantic as an ordinary error: 1 cancel in 5 recorded as a failure at a stage boundary. The CLI keeps a second Ctrl-C as the user's force. (`2407fedc`; `test_subprocess_hosted_second_signal_does_not_lose_the_cancel`.)
3. **A run that ends after its app has gone is cancelled, not failed** (`run_lifecycle._failure_terminus`). Closes the watcher's window — a print inside the 0.5 s after a force-quit still hit the dead pipe first. If the parent has changed since the run began (or was already launchd at entry), the terminus is `run_cancelled` whatever it ended with; the original cause stays in the message and the log, and resuming surfaces any real failure again. (`4702f48f`; `test_subprocess_hosted_run_whose_app_left_is_cancelled_not_failed` and its alive-app control.)

Measured through the real CLI with a stand-in host process: ⌘Q 7/7 and force-quit 8/8 (boundary and mid-stage) record `run_cancelled`, the run gone within 0.8 s.

### Sandbox compatibility

> **Post-flip, 20 Oct 2026.** This section was written as prerequisites for turning the sandbox on, which happened 14 Jul 2026. Both items below are closed: `killOrphanedServeProcesses` was deleted in A6, and `aliveOwnedRunPID` has been libproc since 12 Oct (`ac1415fc`, `eb8509e1`). `proc_pidpath` is not used (see the PID-file note above). Kept as the record.

All probes (`kill(pid, 0)`, `proc_pidinfo`, `proc_pidpath`) work under App Sandbox without entitlements. PID file write to `<App Support>` works under sandbox by default (the App Support container is always granted).

The only sandbox-incompatible piece in today's code is `ServeManager.killOrphanedServeProcesses()`'s `lsof` exec. This design replaces it; that method goes away.

> **Superseded 2026-04-23 — sandbox-incompatibility surface is larger than stated.** Two shipped sites exec subprocesses that won't survive App Sandbox:
> 1. `ServeManager.killOrphanedServeProcesses()` — `lsof -ti :5173,8150-9149` (plus the Vite dev port, not just 8150-9149 as originally written).
> 2. `PipelineRunner.aliveOwnedRunPID(for:)` — `/bin/ps -p <pid> -o uid=` and `-o args=`, once per orphan scan, per project at app startup.
>
> Migrating (1) to port-range TCP-connect sweep OR PID-file-scan-and-reconcile, and (2) to `proc_pidinfo` + `proc_pidpath`, are both prerequisite to flipping `ENABLE_APP_SANDBOX = YES`.
>
> **Also worth documenting**: ServeManager's `lsof` cleanup, despite being aggressive, is port-scoped — it does NOT cascade to `bristlenose run` subprocesses (which bind no port for the pipeline phase). Initial QA suspicion (23 Apr 2026) that ServeManager was killing run-orphans was wrong; the two lifecycles are properly independent today. (Pre-A3 the `run` subprocess explicitly passed `--static` to suppress auto-serve; A3 removed that flag — the no-port property is now an emergent property of the pipeline phase rather than an explicit flag, worth re-verifying.) _Resolved: the spawn passes an explicit `--no-serve`._

### What we explicitly don't build

- **No "running tasks" menu, sidebar item, or modal.** If the user has to see this list, the design has failed.
- **No global "Stop all" affordance.** Per-project Stop in the existing pill surface is enough. App-quit is the global "stop everything" path.
- **No CPU/memory monitoring per subprocess.** Activity Monitor exists.
- **No per-subprocess logs panel.** The technical-details disclosure on the failure popover is enough; full logs go to `<project>/.bristlenose/bristlenose.log` per existing convention.

## Implementation plan (one slice)

1. ~~CLI: add PID file write + atexit cleanup to `bristlenose serve`~~ _Superseded by A6 (May 2026): serve has no PID file; parent-death watcher + `bind(0)`._ CLI: add PID file write + atexit cleanup to `bristlenose serve` (mirror what `bristlenose run` already does in this branch). Path: `<App Support>/Bristlenose/pids/serve-<projectID>.pid`.
2. ~~Swift: rewrite `ServeManager.killOrphanedServeProcesses()`~~ _Superseded by A6: the method was deleted._ Swift: rewrite `ServeManager.killOrphanedServeProcesses()` to use the PID-file-scan-and-reconcile pattern instead of `lsof`. Method renames to `reconcileServeProcesses()`. Same interface from caller's perspective.
3. ~~Swift: rename `PipelineRunner.aliveOwnedRunPID()`'s `/bin/ps` exec to use `proc_pidinfo` / `proc_pidpath`. Sandbox-clean. Existing logic unchanged.~~ _Shipped 12 Oct 2026 — as a start-time token, not an argv match (see the PID-file note above)._
4. Swift: extend `.onReceive(willTerminateNotification)` to call `pipelineRunner.stopAll()` in addition to `serveManager.stop()`. _Shipped 20 Oct 2026 as `PipelineRunner.stopAllForQuit()` on its own `willTerminate` observer, plus the Python half the plan did not foresee (§Hosted-run self-termination)._
5. ~~Tests: same as port-v01-ingestion alpha — manual matrix only, no automated. Force-quit + relaunch + observe attachment is the gate.~~ _`PipelineRunnerOrphanTests` (12 Oct 2026) pins the verdict table and the keep-the-file rule; `PipelineRunnerQuitTests`, `tests/test_hosted_run_quit.py` and the hosted cases in `tests/test_run_lifecycle.py` (20 Oct) pin Quit; a real ⌘Q and force-quit are still hand tests._

~~Estimated scope: ~2 days. Smaller than port-v01-ingestion. Can land any time before TestFlight; required before sandbox flips on.~~ _The sandbox flipped on 14 Jul 2026; steps 3–5 are done, 1–2 superseded._

## Open questions

- ~~**Should we surface "we attached an orphan" in the UI as a brief one-time message?** The design says no (invisible-to-user is the principle). But the first time it happens to a real user it might feel like magic-good or magic-confusing. Consider a debug log entry only.~~ _Moot: the row's "Resuming…" headline (`attachedFromOrphan`) already says it, and since 20 Oct an attach lasts under a second._
- **PID file location: project-relative or App-Support-relative?** Slice 7 chose App Support for sandbox simplicity. This design keeps that. Re-evaluate if multi-machine / cloud sync becomes a thing (then per-project might be better).
- **What if two Bristlenose instances launch simultaneously?** (e.g. user double-clicks the dock icon.) Today: undefined, both reconcile in parallel. Probably fine — same PID files, idempotent operations. Worth a quick test. _20 Oct 2026, inferred from code, not measured: no longer fine. Nothing prevents a second instance, instance B's scan attaches A's live run (`applyScan` skips only its own), and B's Quit then SIGINTs it via `stopAllForQuit`. Fix shape: don't attach, or don't signal at Quit, a run whose parent is still alive._
