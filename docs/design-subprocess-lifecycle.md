---
status: partial
last-trued: 2026-04-24
trued-against: HEAD@port-v01-ingestion on 2026-04-24 (post Stop fixes)
---

> **Truing status:** Partial — Stop-is-a-lie alpha blocker now fully closed (4 commits, 24 Apr 2026); attached-orphan visibility gap closed (log tail in popover); Stop click acknowledged instantly across pill / popover / sidebar (`isStopping` flag). Sandbox-clean probes (`proc_pidinfo`/`proc_pidpath`), `stopAll()`, and unified serve-side reconcile remain design-intent only.

## Changelog

- _2026-04-24 (evening)_ — Stop-is-a-lie + stale-pill alpha blockers fixed and documented. Bug banners replaced with "Fixed" content citing commits `896c074` (kill fix), `c0eb709` (escalation), `2b5475f` (`.running` transition), `da5cc45` (log tail + `isStopping`). Inline body updated with new flags (`attachedFromOrphan`, `isStopping`) and helpers (`logFileURL`, `readLogTail`, `scheduleOrphanCancelEscalation`, `orphanLogOffsets`).
- _2026-04-24 (afternoon)_ — Tier 2 truing follow-up: cite commit `49930e4` for the owned-process cancel-flag fix (was "this branch, working-tree"); add corner-case notes for the `projectIndex`-lookup PID-file leak (`PipelineRunner.swift:776-778`) and the spawn-vs-`writePIDFile` race (`:737-742`).
- _2026-04-23_ — trued up during port-v01-ingestion QA: PID file naming correction (shipped is `<uuid>.pid` without `<role>-` prefix); `atexit` ownership correction (Swift side removes, not Python); sandbox-compat scoped (`/bin/ps` exec in `aliveOwnedRunPID` is also incompatible, not just `lsof`); ServeManager port range corrected (`:5173,8150-9149`); Stop-is-a-lie bug called out in §Cancellation; attached-orphan visibility gap (stale "Starting up" pill) called out in §The design; `stopAll()` marked as planned. Anchors: `PipelineRunner.swift:341-358, 626-660, 690`, `ServeManager.swift:305-334`. Commits: 6d08f3f, 5e254cd.
- _20 Apr 2026_ — initial draft surfaced during port-v01-ingestion QA.

# Subprocess lifecycle — orphan management

**Status:** design, partly shipped. Surfaced during port-v01-ingestion QA, 20 Apr 2026; trued 23 Apr 2026.
**Related:** `desktop/CLAUDE.md` "Zombie process cleanup", `docs/design-pipeline-resilience.md`, `docs/private/sprint2-tracks.md` Track C C0 (sandbox spike).

## The principle

**Two categories of work, two visibility rules.**

| Category | Examples | Visibility |
|---|---|---|
| **User-initiated tasks** | "Analyse this folder" (`bristlenose run`), "Apply this codebook" (autocode), "Export clips for these quotes", "Add interviews to this project" | **Visible.** Per-task progress, where the user is already looking. Pill, ActivityChipStack, sidebar subtitle. The user asked for this, they want to see it happen. |
| **Infrastructure** | `bristlenose serve` lifecycle, port allocation, Cmd+R cleanup, reconciling across launches, deciding whether to attach an orphan or spawn fresh | **Invisible.** No surface, no menu, no list. The user doesn't know these processes exist. If they have to think about them, the design has failed. |

The line between the two: did the user explicitly ask for this thing to happen? `run` yes (they dropped a folder), `serve` no (it's how the report gets to the WebView). Autocode yes (they clicked Apply), the SQLite WAL writer no.

This design is about the **infrastructure** half. User-task progress surfaces (`PipelineActivityItem`, `ActivityChipStack`) are already in place and stay as they are. What changes here is the part the user shouldn't see — orphan reconciliation, port cleanup, sandbox-compat probes.

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
2. **`bristlenose run` auto-served and waited for Ctrl-C** — subprocess never reached exit, `terminationHandler` never fired, state machine stuck. Also fixed in port-v01-ingestion by passing `--static`.
3. **Multiple Bristlenose.app instances** — Cmd+R sometimes failed to kill the previous .app, leaving 3 instances running, each fighting for keychain prompts and ports.
4. **Today's cleanup mechanism doesn't survive sandbox.** `ServeManager.killOrphanedServeProcesses()` uses `lsof -ti :5173,8150-9149` + `kill`. Both `lsof` exec and arbitrary-PID `kill` are blocked under App Sandbox. `PipelineRunner.aliveOwnedRunPID()` additionally execs `/bin/ps -p <pid> -o uid=` and `-o args=` twice per scan — also sandbox-incompatible. TestFlight build will silently fail to clean up until both sites move to `libproc.h` probes.

## The design

### CLI side: every long-running subprocess writes a PID file

On startup, both `bristlenose serve` and `bristlenose run` write `<App Support>/Bristlenose/pids/<role>-<id>.pid` (e.g. `serve-<projectID>.pid`, `run-<projectID>.pid`). PID file contains the subprocess PID + start timestamp + project path.

On clean exit, subprocess removes its own PID file via `atexit` handler.

Force-quit / SIGKILL leaves the file behind — that's the signal the orphan-recovery path uses.

(Already implemented for `run` in port-v01-ingestion Slice 7. Extend to `serve` in this design's first slice.)

> **Superseded 2026-04-23 — naming and ownership corrections:**
> - Shipped file name is `<project.id.uuidString>.pid` (no `<role>-` prefix). Swift-side writer is `PipelineRunner.writePIDFile` at `PipelineRunner.swift:442`. When `serve` gets a PID file too (planned), the flat directory needs either a `<role>-` prefix (reviving the original spec) or two subdirectories (`pids/run/`, `pids/serve/`) to avoid collision.
> - **PID file is Swift-owned**, not Python-owned. Swift writes after `proc.run()` in `spawn`, and removes in `handleTermination` / `handleOrphanExit`. Python has no `atexit` handler touching these files — the App Support directory is in Swift's sandbox, not Python's. The "subprocess removes its own PID file" claim above is inverted; correct behaviour is "Mac side removes the PID file when the termination handler or orphan poller confirms exit."
> - File contains **PID only** (`String(pid)`), not start timestamp or project path. Verification of ownership goes via `/bin/ps -o uid=` and `-o args=` (shipped), or `proc_pidinfo`/`proc_pidpath` (planned, sandbox-clean).

### Mac side: scan-and-reconcile at app init, sandbox-clean

`PipelineRunner.init()` and `ServeManager.init()` both walk `<App Support>/Bristlenose/pids/` at startup:

For each PID file:
- **Dead PID** (`kill(pid, 0) != 0`): silently sweep the file. Manifest is the source of truth for state.
- **Alive, owned by us** (uid match via `proc_pidinfo` + argv contains `bristlenose run|serve` via `proc_pidpath`): **attach**, don't kill. The subprocess is still doing useful work and (per `docs/design-pipeline-resilience.md`) writes atomically to disk. Display it in the project's existing UI surface (sidebar row, toolbar pill) as if we'd just spawned it.
- **Alive, foreign uid or wrong argv**: leave alone, sweep the stale file. PID was reused by something we don't own.

This replaces the `lsof`/`kill` approach. All probes (`kill(pid, 0)`, `proc_pidinfo`, `proc_pidpath`) are sandbox-clean — they work entirely through the kernel via `libproc.h`. No subprocess exec required.

> **Superseded 2026-04-23.** The bullet above is **design-intent**. Shipped `aliveOwnedRunPID` (`PipelineRunner.swift:326-358`) uses `kill(pid, 0)` + TWO `/bin/ps` execs (`-o uid=`, then `-o args=`). Same outcome as the libproc path, but not sandbox-clean today — migrating is a separate slice before TestFlight. The target state ("all probes through `libproc.h`") is the planned endpoint, not a shipped capability.

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

**Owned-process cancel (non-orphan)** was fixed in commit `49930e4`. Pre-fix: `cancel()` called `proc.interrupt()` and relied on the termination handler to route `.failed`. Any non-zero exit landed in `.failed` including user-initiated cancels — "Transcription failed" appeared after a Stop click. Post-fix: a `cancellationRequested` flag (`PipelineRunner.swift:206`) is set before `proc.interrupt()` (`:629-630`); `handleTermination` checks it (`:790-795`) and routes to `.idle` with log line "run cancelled". Flag cleared at each spawn (`:677`). Both paths now also flip `progress.isStopping = true` at the top of `cancel()` so the UI acknowledges the click instantly.

**Open corner cases (not yet shipped, surfaced 24 Apr 2026):**
- **PID-file leak via `projectIndex` lookup.** `handleTermination` at `PipelineRunner.swift:776-778` removes the PID file by looking the project up from `projectIndex`. If `projectIndex` is unwired (logged at `:826`) or the project was deleted between spawn and termination, the PID file is leaked. Next launch's orphan-attach scan will find a dead PID and the `kill(pid, 0)` sweep removes it harmlessly — but worth being explicit so a future refactor doesn't assume the cleanup path is bulletproof.
- **Spawn-vs-`writePIDFile` race.** `PipelineRunner.swift:737-742` carries an in-source comment acknowledging a window where an app crash between `proc.run()` and `writePIDFile` leaves an unattachable orphan (subprocess running, no PID file). Accepted trade-off; documenting it here so the design intent survives.

### Quit propagation: kill children when the .app exits

Today's `.onReceive(NSApplication.willTerminateNotification)` calls `serveManager.stop()`. Extend to:
- `serveManager.stop()` — already does SIGINT to the active serve subprocess, kept.
- `pipelineRunner.stopAll()` — **planned, not shipped.** New method that SIGINTs every active spawn AND every attached orphan. Ensures Cmd+Q leaves no orphans behind. PID files get cleaned by the Swift-side termination handler; if SIGKILL was needed, the next launch's reconcile pass sweeps the stale file.

For Cmd+R / Xcode's stop button, `willTerminate` may not fire (SIGKILL bypasses it). The reconcile pass at next launch is the safety net.

### Sandbox compatibility

All probes (`kill(pid, 0)`, `proc_pidinfo`, `proc_pidpath`) work under App Sandbox without entitlements. PID file write to `<App Support>` works under sandbox by default (the App Support container is always granted).

The only sandbox-incompatible piece in today's code is `ServeManager.killOrphanedServeProcesses()`'s `lsof` exec. This design replaces it; that method goes away.

> **Superseded 2026-04-23 — sandbox-incompatibility surface is larger than stated.** Two shipped sites exec subprocesses that won't survive App Sandbox:
> 1. `ServeManager.killOrphanedServeProcesses()` — `lsof -ti :5173,8150-9149` (plus the Vite dev port, not just 8150-9149 as originally written).
> 2. `PipelineRunner.aliveOwnedRunPID(for:)` — `/bin/ps -p <pid> -o uid=` and `-o args=`, once per orphan scan, per project at app startup.
>
> Migrating (1) to port-range TCP-connect sweep OR PID-file-scan-and-reconcile, and (2) to `proc_pidinfo` + `proc_pidpath`, are both prerequisite to flipping `ENABLE_APP_SANDBOX = YES`.
>
> **Also worth documenting**: ServeManager's `lsof` cleanup, despite being aggressive, is port-scoped — it does NOT cascade to `bristlenose run` subprocesses (which run with `--static` and bind no port). Initial QA suspicion (23 Apr 2026) that ServeManager was killing run-orphans was wrong; the two lifecycles are properly independent today.

### What we explicitly don't build

- **No "running tasks" menu, sidebar item, or modal.** If the user has to see this list, the design has failed.
- **No global "Stop all" affordance.** Per-project Stop in the existing pill surface is enough. App-quit is the global "stop everything" path.
- **No CPU/memory monitoring per subprocess.** Activity Monitor exists.
- **No per-subprocess logs panel.** The technical-details disclosure on the failure popover is enough; full logs go to `<project>/.bristlenose/bristlenose.log` per existing convention.

## Implementation plan (one slice)

1. CLI: add PID file write + atexit cleanup to `bristlenose serve` (mirror what `bristlenose run` already does in this branch). Path: `<App Support>/Bristlenose/pids/serve-<projectID>.pid`.
2. Swift: rewrite `ServeManager.killOrphanedServeProcesses()` to use the PID-file-scan-and-reconcile pattern instead of `lsof`. Method renames to `reconcileServeProcesses()`. Same interface from caller's perspective.
3. Swift: rename `PipelineRunner.aliveOwnedRunPID()`'s `/bin/ps` exec to use `proc_pidinfo` / `proc_pidpath`. Sandbox-clean. Existing logic unchanged.
4. Swift: extend `.onReceive(willTerminateNotification)` to call `pipelineRunner.stopAll()` in addition to `serveManager.stop()`.
5. Tests: same as port-v01-ingestion alpha — manual matrix only, no automated. Force-quit + relaunch + observe attachment is the gate.

Estimated scope: ~2 days. Smaller than port-v01-ingestion. Can land any time before TestFlight; required before sandbox flips on.

## Open questions

- **Should we surface "we attached an orphan" in the UI as a brief one-time message?** The design says no (invisible-to-user is the principle). But the first time it happens to a real user it might feel like magic-good or magic-confusing. Consider a debug log entry only.
- **PID file location: project-relative or App-Support-relative?** Slice 7 chose App Support for sandbox simplicity. This design keeps that. Re-evaluate if multi-machine / cloud sync becomes a thing (then per-project might be better).
- **What if two Bristlenose instances launch simultaneously?** (e.g. user double-clicks the dock icon.) Today: undefined, both reconcile in parallel. Probably fine — same PID files, idempotent operations. Worth a quick test.
