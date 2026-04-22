# Subprocess lifecycle — orphan management

**Status:** design, not yet scheduled. Surfaced during port-v01-ingestion QA, 20 Apr 2026.
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
4. **Today's cleanup mechanism doesn't survive sandbox.** `ServeManager.killOrphanedServeProcesses()` uses `lsof -ti :8150-9149` + `kill`. Both `lsof` exec and arbitrary-PID `kill` are blocked under App Sandbox. TestFlight build will silently fail to clean up.

## The design

### CLI side: every long-running subprocess writes a PID file

On startup, both `bristlenose serve` and `bristlenose run` write `<App Support>/Bristlenose/pids/<role>-<id>.pid` (e.g. `serve-<projectID>.pid`, `run-<projectID>.pid`). PID file contains the subprocess PID + start timestamp + project path.

On clean exit, subprocess removes its own PID file via `atexit` handler.

Force-quit / SIGKILL leaves the file behind — that's the signal the orphan-recovery path uses.

(Already implemented for `run` in port-v01-ingestion Slice 7. Extend to `serve` in this design's first slice.)

### Mac side: scan-and-reconcile at app init, sandbox-clean

`PipelineRunner.init()` and `ServeManager.init()` both walk `<App Support>/Bristlenose/pids/` at startup:

For each PID file:
- **Dead PID** (`kill(pid, 0) != 0`): silently sweep the file. Manifest is the source of truth for state.
- **Alive, owned by us** (uid match via `proc_pidinfo` + argv contains `bristlenose run|serve` via `proc_pidpath`): **attach**, don't kill. The subprocess is still doing useful work and (per `docs/design-pipeline-resilience.md`) writes atomically to disk. Display it in the project's existing UI surface (sidebar row, toolbar pill) as if we'd just spawned it.
- **Alive, foreign uid or wrong argv**: leave alone, sweep the stale file. PID was reused by something we don't own.

This replaces the `lsof`/`kill` approach. All probes (`kill(pid, 0)`, `proc_pidinfo`, `proc_pidpath`) are sandbox-clean — they work entirely through the kernel via `libproc.h`. No subprocess exec required.

The orphan-attach UX surface is **the project's normal status indicators** — the sidebar row says "Analysing…", the toolbar pill shows the stage. The user has no way to tell whether the subprocess was just spawned by this Bristlenose instance or attached from a previous instance. That's the design's whole point.

### Cancellation: SIGINT via the existing surfaces

The user cancels via the toolbar pill's Stop button (per-project surface). Implementation: `kill(pid, SIGINT)` after re-verifying ownership. Matches today's behaviour.

There is no global "kill all" surface. If the user wants to nuke everything, they Quit Bristlenose — and a separate part of this design (below) handles propagating that decision to the children.

### Quit propagation: kill children when the .app exits

Today's `.onReceive(NSApplication.willTerminateNotification)` calls `serveManager.stop()`. Extend to:
- `serveManager.stop()` — already does SIGINT to the active serve subprocess, kept.
- `pipelineRunner.stopAll()` — new. SIGINT to every active spawn AND every attached orphan. Ensures Cmd+Q leaves no orphans behind. PID files get cleaned via the subprocess's own atexit; if SIGKILL was needed, the next launch's reconcile pass sweeps the stale file.

For Cmd+R / Xcode's stop button, `willTerminate` may not fire (SIGKILL bypasses it). The reconcile pass at next launch is the safety net.

### Sandbox compatibility

All probes (`kill(pid, 0)`, `proc_pidinfo`, `proc_pidpath`) work under App Sandbox without entitlements. PID file write to `<App Support>` works under sandbox by default (the App Support container is always granted).

The only sandbox-incompatible piece in today's code is `ServeManager.killOrphanedServeProcesses()`'s `lsof` exec. This design replaces it; that method goes away.

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
