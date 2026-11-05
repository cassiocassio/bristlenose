# Standby sidecar: pay the generic part of a study open before the click

Status: phase 1 built 5 Nov 2026 (`fcf1ae9f8` Python, `e373db000` and `83395564f` Swift), after a plan review and a code review. **Not yet run in the sandboxed app**: it needs a rebuilt sidecar (an older bundle has no `--standby`, so the pool gives up after three quiet deaths and every open cold-spawns as before) and the app A/B. Numbers come from `docs/design-perf-ledger.md` and are labelled there. Today opening a study from a cold launch is 3.1 s (measured), of which the sidecar's boot is about 2.1 s, and about 0.85 s of that happens before `create_app` and does not depend on which study is chosen (estimate, from the app's own stage stamps; the in-app interleaved A/B that would confirm it was still running when this was written).

## What is built, what is not

**Built (phase 1): one generic standby.** `bristlenose serve --standby` boots, imports everything, then waits on stdin for a claim naming the study. The app keeps at most one standby; opening a study claims it when it can and cold-spawns exactly as today when it cannot.

**Not built (phase 2): pre-binding the last-opened study.** Two reasons, both found reading the code:
1. The app deliberately has no last-used fallback at launch (`ContentView.onAppear`): it would "spawn a sidecar on a study the researcher had not chosen". Phase 2 is that, on purpose.
2. `create_app(project_dir)` is welded to the study: database, watchers, media mount, importer, and the lifespan jobs (Screens, scene strips, Signals snapshot, which can make a paid call). A quiet bind would mean splitting it. That is a refactor of the server's core, not a performance patch.
Recorded in the ledger as declined with these reasons.

## Python

- Hidden flag `serve --standby` (no `project_dir`). In `serve()`, before any study-dependent work:
  1. **do not** install the exit logger or the parent-death watcher yet. Review found that `install_exit_logger` chains to the previous SIGTERM handler only `if callable(...)`, which is false for the default `SIG_DFL`, so a process with it installed *survives* SIGTERM (probed), and the watcher's own `os.kill(SIGTERM)` would not stop it either. The standby instead keeps default signal handling, exits on SIGTERM and SIGINT, and exits on stdin EOF (the app closing the pipe); `_start_server` installs the logger and watcher after the claim, as now;
  2. warm by importing `uvicorn` and `bristlenose.server.app` only. **No throwaway `create_app()`**: review showed it prints the auth token, writes `_BRISTLENOSE_AUTH_TOKEN` into the environment (which the real `create_app` then recovers), registers an atexit hook and assigns the lifespan;
  3. print `[bristlenose] standby-ready` on stdout;
  4. read one line from stdin: `{"v":1,"project":"<path>","mcp_token":"<token or empty>"}`. EOF before a claim: exit 0 quietly. A malformed or wrong-version claim: one fixed line on stderr that never echoes the claim (it holds a token), exit 2. Mark `claim-received` with `startup_trace` so the A/B can separate boot from bind;
  5. set `_BRISTLENOSE_MCP_TOKEN` from the claim (`app.py:281` reads it at `create_app`), set `project_dir`, and **fall through to the existing `serve` body, with the claim inserted before the `_refuse_unsafe_study` call**: `_refuse_unsafe_study`, settings, preflight, `_start_server`, `Report:` and `auth-token` lines. Same exit codes, same refusal behaviour, same stdout protocol.
- The standby generates no auth token and opens no database before the claim. A test pins that the standby, before a claim, has bound no port, written no file in any study and printed no `Report:` or `auth-token` line.
- The non-standby path is not touched. `--standby` with a `project_dir` argument is a usage error.

## Swift

- `StandbySidecar` (new file) wraps one `Process` with a stdin pipe and **one merged stdout+stderr pipe, as `ServeManager.start` builds it today** (the startup stamps, signposts and tracebacks all ride stderr), spawned with `BristlenoseShared.childEnvironment(for: mode)` (project-independent) and the same arguments plus `--standby`. It records the environment fingerprint (`ServeEnvStaleness.fingerprint`) and the `SidecarBinaryStamp` it was spawned with, and goes `booting` then `ready` on the `standby-ready` line, or `dead`.
- `ServeFleet` owns at most one `StandbySidecar`:
  - **start:** about 1.5 s after launch **and after `ProjectIndex.syncWatchers` has taken its leases**, only in bundled mode (not `.external`, not a dev sidecar), only when at least one ready project exists. There is no memory-pressure signal in the app today (`ServeReaping` takes a parameter nothing sets), so the plan does not claim one: the cost is bounded by "one standby", and wiring a real pressure source is a separate change;
  - **claim:** `ServeManager.start` asks the fleet for a standby, **synchronously on the main actor with no `await` between the checks and the adoption**. It is taken only if `ready`, alive, the fingerprint equals the one `start` would spawn with, the binary stamp is unchanged, **and the study's `ProjectBookmarkLease` existed when the standby was spawned** (a child inherits sandbox extensions held at spawn; a project added, located or relocated afterwards has none in an already-running standby). The standby records the set of leased project ids at spawn; a study outside it cold-spawns. Otherwise cold spawn, exactly as today;
  - **replace:** after a claim, start a new one after a short delay, same rules;
  - **recycle:** on a fingerprint mismatch, a sidecar-binary change, or a lease set that no longer covers the projects: stop, then replace. `applyEnvChange` iterates managers only, so the fleet gives the standby its own `.bristlenosePrefsChanged` hook;
  - **replace loop is bounded:** at most one respawn per 30 s and a stop after three consecutive standbys that die before `ready`, so a broken binary cannot spin;
  - **quit and stop:** close stdin and send SIGINT (`interrupt()`, the house convention), never SIGTERM alone.
- Adoption: `ServeManager.start` today builds a `Process`, wires the pipes and `handleLine`, then runs the watchdog. The claim path must reuse that wiring with an existing `Process`, writing the claim line to its stdin instead of passing the path as an argument. Three specifics from review: (1) **one reader on the pipe**: the standby's reader is the only reader, with a swappable sink that becomes `handleLine(_, fromProcessID:)` at adoption and is assigned to the manager's read task so `stop()` cancels it (two readers on one file handle split bytes); (2) **handler before liveness check**: install the manager's termination handler first, then re-check `isRunning`, so a standby that dies in the handover is routed to `handleTermination` and not left for the 90 s watchdog; (3) **copy the spawn records** (`spawnedEnvFingerprint`, `spawnedReadsScreens`, `spawnedSidecarStamp`) from the standby so `applyEnvChange` judges an adopted, still-starting serve correctly, and keep `authToken = nil` until the token line arrives through the manager. The `generation` token, `.starting` state, `ServeStartPolicy` watchdog (90 s ceiling, measured from the claim), `handleTermination` and `dropHandshake` behave as for a cold spawn. A failed stdin write or a dead standby falls back to a cold spawn in the same call, never a hang.
- Untouched: Agent Access and the handshake (they follow `.running` and `instance_id` as now), the MCP token store (the per-project token is read as now and sent in the claim), `ServeEnvStaleness` policy, the reaping sweep (a claimed process is an ordinary one).
- Kill switch: a defaults key and an environment variable turn the standby off entirely; default on.

## Tests (each mutation-proved)

Python: a subprocess test for each of: ready line printed and nothing else before a claim; claim then `Report:` and `auth-token` appear and the port serves `/api/health`; EOF before a claim exits 0 without binding; **SIGTERM and SIGINT to a waiting standby exit it**; malformed claim exits 2 and the stderr line does not contain the claim; `--standby` with a path is a usage error; an unsafe study is refused with today's exit code after a claim. (The earlier "same function" equivalence test is dropped: it was tautological.)

Swift: a pure policy function (`StandbyPolicy`) decides start, claim, recycle and drop from a plain state value, tested exhaustively; the claim message encoding; adoption using a `/bin/sh` script as a stand-in standby (the pattern `ServeManagerRestartTests` already uses) that prints the ready line, reads the claim and prints a `Report:` line; fallbacks for a dead standby, a stale fingerprint, a stale binary, a failed stdin write, a study outside the leased set, a standby that dies during the handover (resolves in well under the 90 s watchdog), an adopted serve whose token line arrives through the manager, and `applyEnvChange` on an adopted `.starting` serve. **Only the real sandboxed app can show** that a leased study is readable by a standby spawned before the click, and that a study added afterwards is not; that is part of the app A/B, not a unit test.

## Measurement and risks

- **In dev** (Python only, same bundle): spawn to first `/api/health` with the standby claimed against a cold spawn, interleaved, repeated, Screens on and off. This measures the Python half only.
- **In the app:** the interleaved A/B (`desktop/scripts/perf/README.md`), run on a quiet Mac by the session that owns it. Until then the app gain is **unmeasured**, and the ledger says so.
- **Risks to review:** (1) adoption touching the most race-prone code in the app (`generation`, termination routing); (2) an idle process holding the active provider's API key in its environment, as a cold-spawned sidecar already does; (3) a stale environment: a setting changed between standby spawn and claim must never reach a study; (4) a claim racing a recycle; (5) an unbounded standby respawn loop if the binary is broken; (6) the first-run user, who must get no standby; (7) memory on 8 GB machines.

## As built (5 Nov 2026)

- **Python half, measured** (`experiments/perf/standby-ab.py`, dev, same bundle, real-size study copy, interleaved, 8 reps each): claim to `Report:` **0.74 s against 1.36 s cold** (Screens off) and **0.75 against 1.39 s** (Screens on), a saving of 0.62–0.65 s, spread under 50 ms. The standby's own boot, hidden behind the time spent choosing, is about 0.64 s. This is the Python half only: the sandboxed app, its code-signature cost and the Swift handover are not in it.
- **What the two reviews caught.** The plan review (Fable) found the SIGTERM trap (`install_exit_logger` before uvicorn swallows SIGTERM, so a waiting standby could not be stopped), that the throwaway `create_app()` has side effects, the lease-at-spawn condition, the two-readers-on-one-pipe problem and the missing memory-pressure source. The code review (Fable) found a **blocker the tests could not see**: the manager kept the adopted process and read task but nothing kept the `StandbySidecar` object, whose reader and exit handler hold it weakly, so after the first claim no line and no exit reached the manager and every claim would have ended as the 90 s start timeout. Every test had held the object in a local variable. The regression tests drop every local reference first (`theAdoptedStandbyStaysAliveAndItsLinesReachTheManager`), and removing the owner turns two of them red.
- **Tests:** 15 Python subprocess tests (`tests/test_standby.py`, four mutations killed); 43 Swift tests in `StandbySidecarTests.swift` (policy matrix, the process protocol against `/bin/sh` stand-ins, the pool, the manager's claim, `start()` itself), eight mutations killed; 190 Swift tests across the serve, fleet and project suites green, run in an isolated worktree because other sessions had uncommitted Swift in the tree.
- **Not covered, only the real app can show:** that a standby spawned before the click can read a leased study under the sandbox; that a study added after launch is refused the claim and cold-spawns; the actual saving in the app.
- **Kill switch:** `defaults write app.bristlenose BristlenoseStandbySidecar -bool NO`, or `BRISTLENOSE_STANDBY=0`.

## Restored launches: starting earlier, and claiming a spare that is still booting (proposal, 5 Nov 2026)

Under the platform default a restored window starts its study's sidecar within a fraction of a second of launch. The pool as built starts its spare 1.5 s after the first window appears, so a restored window never finds one. Two changes are proposed; this section stress-tests them and says what to build, what to measure first, and what to leave alone.

### What the spare saves when the study asks before it is ready (measured)

`experiments/perf/standby-early-claim.py`, dev, same bundle, real-size study, interleaved, 5 reps. The claim is written `d` seconds after the spare was spawned, without waiting for `standby-ready` (Python reads it when its imports finish):

| claim sent d s after spawn | spawn → `Report:` | the study waits | saved vs cold (1.375 s) |
|---|---|---|---|
| 0.00 | 1.396 | 1.396 | −0.02 |
| 0.15 | 1.410 | 1.260 | 0.12 |
| 0.30 | 1.398 | 1.098 | 0.28 |
| 0.45 | 1.394 | 0.944 | 0.43 |
| 0.60 | 1.407 | 0.807 | 0.57 |
| 0.90 | 1.650 | 0.750 | 0.62 |

**The law: the total is `max(boot 0.64, d) + bind 0.75`, so claiming early gives the study exactly the head start the spare had, no more.** Boot and bind stay in series; there is no overlap to win. A claim at d = 0 is a cold start with extra steps. The Python side needs no change to accept an early claim (the line waits in the pipe).

So the two changes depend on each other, and on a number nobody has: **t_w, the time from process launch to the restored window's `start()`**. The ledger has no launch-to-ready figure. Saving ≈ t_w − t_spare, capped at about 0.62 s.

### Change A: start the spare earlier

- Today: scheduled in the first window's `onAppear` plus 1.5 s. A restored window's `ContentView.onAppear` runs in the same pass, so the head start is ~0 even with the delay removed. **Removing the delay alone buys nothing.**
- To get a real head start the start must come before window creation: `ProjectIndex.init` already does `load()` then `syncWatchers()`, so leases exist as soon as the `@StateObject` is first read (during the App's first body pass); the earliest reachable hook after that and before the windows is the app delegate (`applicationWillFinishLaunching`/`DidFinishLaunching`), which would need references to the fleet and index.
- **Order constraint:** spawn only after the leases (a child inherits extensions held at spawn). Event-driven (a callback after `syncWatchers`), never a timer.
- **Consent (found while reviewing this, and true of the build as shipped):** `ServeManager.start` is gated on AI consent so nothing runs before the disclosure is acknowledged (Apple 5.1.2(i)). The pool is not. The spare makes no calls, but a launch-time process holding a provider key and importing third-party packages before consent breaks the stated rule, and a dependency's import-time telemetry would be a real event. **Gate the pool on the same condition, now.**
- Pros: the only way a restored launch gets any win; a Welcome launch loses nothing (thinking time is far longer than boot).
- Cons: contends with launch for CPU/disk (unmeasured; the first launch after an install also pays code-signature validation of the bundle's ~219 Mach-Os, which a cold start would pay anyway); holds ~140 MB for a session that never opens a study (more sessions, since it now starts every launch); needs an app-delegate hook and a second reference path; a first launch before consent starts nothing (correct).

### Change B: a restored window claims a spare that is still booting

- Mechanism: allow `claim` in `.booting`. Write the claim; Python reads it after imports. Drop the late `standby-ready` line from the manager's output (it would land in the boot log tail).
- Pros: turns a spare that is 0.3 s old into a 0.3 s saving instead of nothing; no Python change.
- **The stress finding: failure behaviour changes.** Today a claim happens only after `standby-ready`, so a spare that cannot boot (an old bundle without `--standby`, an import crash) never reaches a study. With B, a study can be handed to a process that then dies before it is ready, and `handleTermination` reports `exitedBeforeReady` for a study that a cold spawn would have opened. That is a new user-visible failure on the path that used to work. Two ways to close it:
  1. **Proven-binary rule (preferred):** claim a booting spare only if this sidecar binary's stamp has already booted a spare to ready, remembered across launches (a defaults key holding the proven stamp). The first launch after any rebuild or update pays one cold start; every later one is covered. No fallback machinery.
  2. Fallback re-spawn on early death: transparent but more code and a re-entrancy risk in the most race-prone part of the app.
- Other conditions, unchanged: fingerprint, stamp and lease checks are still done at claim time. A study that waits on a spare that then hangs in its imports waits the 90 s ceiling a cold start would have had.
- Cons: only one window gets the spare (two restored windows: the second cold-starts); the watchdog starts at claim, so it also covers boot.

### Verdict on the pair

| | alone | together |
|---|---|---|
| A without B | the restored window finds the spare unready and cold-spawns; the spare then idles | no |
| B without A | no spare exists yet at claim time | no |
| A + B | the window waits `1.375 − head start` | saves up to ~0.6 s, **size unmeasured until t_w is** |

### Recommendations (in order)

1. **Gate the pool on AI consent now.** A small defect in the shipped build.
2. **Settle the default** with `defaults read -g NSQuitAlwaysKeepsWindows` on a fresh guest. If restoring is the platform default, restored launches are the common case and A + B decide most of the feature's value; if not, the shipped build already serves the common case and A + B are an edge.
3. **Measure t_w** (and launch-to-ready with and without a launch-time spare) in the real app, with the existing signposts. Without it A + B are a guess.
4. If worthwhile: build A and B together, with the proven-binary rule, behind the same kill switch.
