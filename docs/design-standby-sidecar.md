# Standby sidecar: pay the generic part of a study open before the click

Status: plan, 5 Nov 2026. Numbers come from `docs/design-perf-ledger.md` and are labelled there. Today opening a study from a cold launch is 3.1 s (measured), of which the sidecar's boot is about 2.1 s, and about 0.85 s of that happens before `create_app` and does not depend on which study is chosen (estimate, from the app's own stage stamps; the in-app interleaved A/B that would confirm it was still running when this was written).

## What is built, what is not

**Built (phase 1): one generic standby.** `bristlenose serve --standby` boots, imports everything, then waits on stdin for a claim naming the study. The app keeps at most one standby; opening a study claims it when it can and cold-spawns exactly as today when it cannot.

**Not built (phase 2): pre-binding the last-opened study.** Two reasons, both found reading the code:
1. The app deliberately has no last-used fallback at launch (`ContentView.onAppear`): it would "spawn a sidecar on a study the researcher had not chosen". Phase 2 is that, on purpose.
2. `create_app(project_dir)` is welded to the study: database, watchers, media mount, importer, and the lifespan jobs (Screens, scene strips, Signals snapshot, which can make a paid call). A quiet bind would mean splitting it. That is a refactor of the server's core, not a performance patch.
Recorded in the ledger as declined with these reasons.

## Python

- Hidden flag `serve --standby` (no `project_dir`). In `serve()`, before any study-dependent work:
  1. install the exit logger and, when `_BRISTLENOSE_HOSTED_BY_DESKTOP=1`, the parent-death watcher, as `_start_server` does, so an orphan standby dies with the app;
  2. warm: import `uvicorn` and `bristlenose.server.app`, plus whatever `create_app` imports inside its body (measure whether a throwaway `create_app()` with no study and an in-memory database buys more than the imports alone, and take it only if it has no side effects: no log file, no files written);
  3. print `[bristlenose] standby-ready` on stdout;
  4. read one line from stdin: `{"v":1,"project":"<path>","mcp_token":"<token or empty>"}`. EOF before a claim: exit 0 quietly. A malformed or wrong-version claim: one line on stderr, exit 2;
  5. set `_BRISTLENOSE_MCP_TOKEN` from the claim (`app.py:281` reads it at `create_app`), set `project_dir`, and **fall through to the existing `serve` body unchanged**: `_refuse_unsafe_study`, settings, preflight, `_start_server`, `Report:` and `auth-token` lines. Same exit codes, same refusal behaviour, same stdout protocol.
- The standby generates no auth token and opens no database before the claim. A test pins that the standby, before a claim, has bound no port, written no file in any study and printed no `Report:` or `auth-token` line.
- The non-standby path is not touched. `--standby` with a `project_dir` argument is a usage error.

## Swift

- `StandbySidecar` (new file) wraps one `Process` with stdin, stdout and stderr pipes, spawned with `BristlenoseShared.childEnvironment(for: mode)` (project-independent) and the same arguments plus `--standby`. It records the environment fingerprint (`ServeEnvStaleness.fingerprint`) and the `SidecarBinaryStamp` it was spawned with, and goes `booting` then `ready` on the `standby-ready` line, or `dead`.
- `ServeFleet` owns at most one `StandbySidecar`:
  - **start:** about 1.5 s after launch, only in bundled mode (not `.external`, not a dev sidecar), only when at least one project exists, once the app is not under memory pressure;
  - **claim:** `ServeManager.start` asks the fleet for a standby; it is taken only if `ready`, alive, the fingerprint equals the one `start` would spawn with, and the binary stamp is unchanged. Otherwise cold spawn, exactly as today;
  - **replace:** after a claim, start a new one after a short delay, same rules;
  - **recycle:** on `applyEnvChange` (a fingerprint mismatch), a sidecar-binary change, or a memory-pressure event: terminate, then replace;
  - **quit:** closing stdin and `terminate()` on app exit; the parent-death watcher is the backstop.
- Adoption: `ServeManager.start` today builds a `Process`, wires the pipes and `handleLine`, then runs the watchdog. The claim path must reuse that wiring with an existing `Process`, writing the claim line to its stdin instead of passing the path as an argument. The `generation` token, `.starting` state, `ServeStartPolicy` watchdog (90 s ceiling, measured from the claim), `handleTermination` and `dropHandshake` behave as for a cold spawn. A failed stdin write or a dead standby falls back to a cold spawn in the same call, never a hang.
- Untouched: Agent Access and the handshake (they follow `.running` and `instance_id` as now), the MCP token store (the per-project token is read as now and sent in the claim), `ServeEnvStaleness` policy, the reaping sweep (a claimed process is an ordinary one).
- Kill switch: a defaults key and an environment variable turn the standby off entirely; default on.

## Tests (each mutation-proved)

Python: a subprocess test for each of: ready line printed and nothing else before a claim; claim then `Report:` and `auth-token` appear and the port serves `/api/health`; EOF before a claim exits 0 without binding; malformed claim exits 2; `--standby` with a path is a usage error; an unsafe study is refused with today's exit code after a claim; a fall-through equivalence check that the `serve` body is the same function for both paths.

Swift: a pure policy function (`StandbyPolicy`) decides start, claim, recycle and drop from a plain state value, tested exhaustively; the claim message encoding; adoption using a `/bin/sh` script as a stand-in standby (the pattern `ServeManagerRestartTests` already uses) that prints the ready line, reads the claim and prints a `Report:` line; fallbacks for a dead standby, a stale fingerprint, a stale binary, a failed stdin write.

## Measurement and risks

- **In dev** (Python only, same bundle): spawn to first `/api/health` with the standby claimed against a cold spawn, interleaved, repeated, Screens on and off. This measures the Python half only.
- **In the app:** the interleaved A/B (`desktop/scripts/perf/README.md`), run on a quiet Mac by the session that owns it. Until then the app gain is **unmeasured**, and the ledger says so.
- **Risks to review:** (1) adoption touching the most race-prone code in the app (`generation`, termination routing); (2) an idle process holding the active provider's API key in its environment, as a cold-spawned sidecar already does; (3) a stale environment: a setting changed between standby spawn and claim must never reach a study; (4) a claim racing a recycle; (5) an unbounded standby respawn loop if the binary is broken; (6) the first-run user, who must get no standby; (7) memory on 8 GB machines.
