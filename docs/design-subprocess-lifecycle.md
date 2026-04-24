---
status: partial
last-trued: 2026-04-24
trued-against: HEAD@port-v01-ingestion on 2026-04-24
---

> **Truing status:** Partial — orphan-attach and per-project cancel have shipped in this branch; sandbox-clean probes (`proc_pidinfo`/`proc_pidpath`), `stopAll()`, and unified serve-side reconcile are design-intent, not shipped. Stop-is-a-lie bug (orphan-path cancel) is the headline alpha blocker — owned-process cancel is fixed (`49930e4`), orphan path is not. Stale-pill visibility gap also still open. See changelog below.

## Changelog

- _2026-04-24_ — Tier 2 truing follow-up: cite commit `49930e4` for the owned-process cancel-flag fix (was "this branch, working-tree"); add corner-case notes for the `projectIndex`-lookup PID-file leak (`PipelineRunner.swift:776-778`) and the spawn-vs-`writePIDFile` race (`:737-742`).
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

> **Superseded 2026-04-23 — attached-orphan visibility gap.** Empirically (23 Apr 2026 QA), attached-orphan pill shows stale "Starting up — loading models and validating credentials" for minutes while the subprocess is actually mid-transcribe. Root cause: attach path polls `.bristlenose/manifest.json` for stage updates (`attachOrphan` poll task at `PipelineRunner.swift:377-406`), but doctor preflight and early stages don't write manifest checkpoints. Separately, the orphan's real stdout went to the dead parent's pipe — it's gone. Without a freshness signal the pill lies about progress. **User-impact:** users conclude analysis is stuck and click Stop, losing hours of transcription work. Fix direction (not yet scheduled): tail `.bristlenose/bristlenose.log` on the attach path and surface last N lines as `progress.lastLine`. Swift-side change only. See plan file for full finding.

### Cancellation: SIGINT via the existing surfaces

The user cancels via the toolbar pill's Stop button (per-project surface). Implementation: `kill(pid, SIGINT)` after re-verifying ownership. Matches today's behaviour.

There is no global "kill all" surface. If the user wants to nuke everything, they Quit Bristlenose — and a separate part of this design (below) handles propagating that decision to the children.

> **Superseded 2026-04-23 — Stop-is-a-lie bug (alpha blocker).** The shipped attached-orphan cancel path (`PipelineRunner.swift:626-660`) does `aliveOwnedRunPID(for: project) == pid` and only calls `kill(pid, SIGINT)` if the re-verify returns true. If it returns false (PID file missing or ps exec hiccup), SIGINT is **silently skipped** — but the code still executes `state[project.id] = .idle`, removes the PID file, and clears `attachedOrphanPIDs[project.id]`. The UI shows Stop-succeeded while the subprocess continues running. Observed 23 Apr 2026 — clicked Stop, pill cleared, `pgrep` showed subprocess still alive; needed manual `kill -INT <pid>` to actually stop it.
>
> **Compounds with the stale-pill gap above.** User sees "Starting up" for minutes, clicks Stop expecting to cancel, UI confirms, but subprocess keeps burning CPU and API. User drops folder again → duplicate project → two orphans running in parallel. Trust-eroding.
>
> **Fix direction.** Remove re-verification at cancel time. We attached to a PID; send SIGINT to that PID. `kill(pid, SIGINT)` return value is the only signal needed: ESRCH = already dead (treat as success), EPERM = not ours (surface toast). Never unconditionally clear state — clear only when we confirm the kill.

**Owned-process cancel (non-orphan) was also broken and fixed inline in port-v01-ingestion (commit `49930e4`).** Pre-fix: `cancel()` called `proc.interrupt()` and relied on the termination handler to route `.failed`. Any non-zero exit landed in `.failed` including user-initiated cancels — "Transcription failed" appeared after a Stop click. Post-fix: a `cancellationRequested` flag (`PipelineRunner.swift:206`) is set before `proc.interrupt()` (`:629-630`); `handleTermination` checks it (`:790-795`) and routes to `.idle` with log line "run cancelled". Flag cleared at each spawn (`:677`). Clean cancel UX — matches what Stop semantically means. Orphan-path `cancel()` is unchanged and still carries the Stop-is-a-lie bug above.

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
