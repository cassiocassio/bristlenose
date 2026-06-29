# Desktop build orchestration — Cmd+R self-heals the sidecar

_Status: v2 — **Phases 1/2/4/5 implemented**; **Phase 3 (Xcode wiring) specced + deferred** (see Implementation status). Revised after a multi-agent plan-review; review log kept locally. Goal: hitting Cmd+R in Xcode auto-rebuilds+signs whatever bundle inputs are stale, **incrementally**, so the developer never hand-runs `build-sidecar.sh` + `sign-sidecar.sh` + clean-build again — while fast-iteration schemes stay instant and the loud staleness gate is preserved as an independent backstop. TestFlight artifacts still come only from `build-all.sh`._

## Implementation status (2026-06-29)

| Phase | What | State |
|---|---|---|
| 1 | `build-sidecar.sh` per-layer incremental (F/V/P, `--force`/`--dry-run`, output-side checks, unconditional preconditions, empty-hash guard) + `frontend_source_hash` sliced from the single recipe | **Done.** Decision logic verified via `--dry-run`; live bundle stamp unchanged (no spurious rebuild). |
| 2 | `ensure-sidecar.sh` orchestrator (escape hatches, Distribution guard, identity-transition→force-P, signs ffmpeg **and** sidecar, deep-verify, atomic `.sign-stamp` outside the bundle, run-log) | **Done.** Verified: cascade, Distribution guard aborts, skip-flags short-circuit. |
| 4 | `build-all.sh` collapse — steps 2–4 → one `ensure-sidecar.sh --force` under `_BRISTLENOSE_RELEASE=1`; preflight/self-test/inventory/archive/notarise kept | **Done** (syntax + sequence verified; full release run needs the Distribution identity → human). |
| 5 | `test-ensure-sidecar.sh` — committed decision-logic test | **Done** (7 pass / 0 fail; P-skip-isolation needs a real venv → human QA). |
| 3 | Xcode: `Ensure Sidecar Fresh` build phase before Copy; gate keeps `exit 1` + output assertion; skip mechanism; SIGN_IDENTITY mapping; `desktop/CLAUDE.md` update | **Specced, deferred** — see the refined §Xcode wiring (a real subtlety + pbxproj-surgery risk make this a do-with-human-in-Xcode step). |

The expensive end-to-end runs (a real `build-sidecar.sh` full build; a Cmd+R with the phase wired; a `build-all.sh --force` Distribution archive) are the human-QA step — none were run autonomously to avoid churning the machine mid-glyph-QA.

## Problem

The desktop app runs a **bundled** PyInstaller sidecar (`desktop/Bristlenose/Resources/bristlenose-sidecar/`) plus the React SPA baked into it — not live source. Today the only safety net is **detection**: the `Copy Sidecar Resources` build phase runs `check-sidecar-freshness.sh`, which **fails the build** when `bristlenose/**/*.py`, `bristlenose/locales/**`, or `frontend/` source has moved past the bundle's `.source-stamp`. Remediation is manual and three-step (`build-sidecar.sh && sign-sidecar.sh` + sometimes a clean build). Two things are wrong: the gate detects but doesn't remediate, and `build-sidecar.sh` recreates `.venv-sidecar` from scratch every run (multi-minute), so it can't naively fire on every Cmd+R.

## Goals / non-goals

**Goals**: Cmd+R auto-brings the bundle up to date before the bundle is consumed, no manual scripts; **per-layer incremental** (only the changed layer rebuilds; the big win is reusing `.venv-sidecar` when deps are unchanged); fast-iteration schemes stay instant; one `ensure-sidecar.sh` callable standalone and from Xcode; **lots of instrumentation**.

**Non-goals**: not changing what gets bundled, the spec, entitlements, or the notarise/export tail; **not making IDE-Archive a shipping path** (TestFlight = `build-all.sh` only); **not introducing a Python lockfile** (separate, larger project — release `--force` + an installed-manifest fingerprint is the bounded mitigation).

## Core principle (the keystone, from review)

**Stamps attest _inputs_; the design must also check _outputs_.** The existing `check-sidecar-freshness.sh` compares a recomputed source hash against `.source-stamp`. Every incremental skip path *writes a matching stamp by construction*, so the source-vs-stamp gate **cannot** catch the orchestrator's own skip bugs — it validates consistency, never correctness. Therefore:

1. The freshness gate stays **loud (`exit 1`), before the rsync**, exactly as today — demotion means "expected to pass," never "allowed to warn."
2. Each layer's skip predicate includes an **output-side check** the input-stamp cannot fake (artefact present + non-empty in the bundle, binary mtime ≥ newest source mtime). Two independent computations agreeing is the only thing that makes "did nothing" safe.

## The two cadences

| Loop | Changes | Scheme | Pre-step cost |
|---|---|---|---|
| **Inner** (seconds) | Swift / React / CSS | Dev Sidecar · External Server | none — skipped |
| **Bundle** (seconds→minutes) | Python / frontend in the bundle | Bristlenose (bundled) | only the changed layer |

Automation lives on the bundle loop. **Release lives only in `build-all.sh`** (the irreversible boundary stays thorough — ETTO).

## Per-layer fingerprinting

| Layer | Rebuild trigger | Output-side check on skip | Cost when triggered | When not |
|---|---|---|---|---|
| **ffmpeg/model** | binary/dir *presence* | n/a | one-time download | stat |
| **F · frontend** | frontend slice of `sidecar_source_hash` ≠ `.frontend-stamp` | `server/static/index.html` present + non-empty | `npm run build`, ~10–30s | skip |
| **V · venv** | `pyproject.toml` hash + `.venv-sidecar` **installed-manifest** (`pip freeze` / `.dist-info` set) ≠ `.deps-stamp`, OR `.deps-ok` sentinel absent | `.deps-ok` sentinel exists (written only after install **and** `PyInstaller --version` pass) | recreate venv + pip, minutes | skip (reuse) |
| **P · PyInstaller** | full `sidecar_source_hash` ≠ `.source-stamp`, OR V rebuilt, OR F output missing | sidecar binary present; `server/static/index.html` present in bundle | PyInstaller **`--clean`**, ~tens of sec | skip |
| **S · codesign (sidecar + ffmpeg)** | P rebuilt, OR `.sign-stamp` identity ≠ requested, OR `codesign --verify --deep --strict` fails | `--verify --deep --strict` passes | sign loop, seconds | skip |

**Decisions baked in from review:**

- **V (venv) — keep the reuse, make it honest.** Reusing `.venv-sidecar` when deps are unchanged is ~95% of the speed win. But `>=`-floor deps + no lockfile mean "`pyproject.toml` unchanged" ≠ "closure unchanged," and an interrupted `pip install` can leave a half-venv. So the V fingerprint hashes `pyproject.toml` **plus the actually-installed manifest** (`pip freeze` of `.venv-sidecar`), and a `.deps-ok` sentinel is written **only after** a clean `pip install` *and* the `PyInstaller --version` check. V skips only if hash matches **and** `.deps-ok` exists. Residual (a transitive republish within the same floor) is covered by **release always `--force`** — which recreates from scratch and is now the *only* trigger of the typeguard/`pyz+py` fresh-install audit (called out in Risks).
- **P — always `--clean` + `robust_rmrf $BUNDLE`** on any rebuild. Warm-workpath PyInstaller saves only tens of seconds and reintroduces the documented "appended stale Mach-Os / failed verification without a clear cause" class on file add/delete. The venv-reuse win stands alone; warm-P is dropped (Knuth's 97%).
- **S — signs BOTH sidecar and ffmpeg**, gates on `--verify --deep --strict` (shallow verify passes on stale inner CDHashes), and writes `.sign-stamp` atomically only after deep-verify passes.
- **Identity transitions are never incremental.** If `.sign-stamp` identity ≠ requested `SIGN_IDENTITY`, force a clean **P** rebuild (not just an S re-sign) so every inner Mach-O is signed under one identity — avoids mixed-identity bundles (ad-hoc→Distribution) and the `ALLOW_RESIGN=0` red-screen (Distribution→ad-hoc).

## Script changes

Two scripts. Layering lives **inside** the bundle builder, gated by fingerprints.

### 1. `build-sidecar.sh` → per-layer incremental (behaviour-preserving)

- **Preconditions run unconditionally, first** (npm, `node_modules`, `python3.12`) — never gated behind a skip decision. An empty/malformed `sidecar_source_hash` (not 64 hex) is a hard `exit 1`, never "all-skip."
- **F**: `npm run build` only if frontend slice moved **or** `server/static/index.html` missing; rewrite `.frontend-stamp`.
- **V**: recreate `.venv-sidecar` only if `.deps-stamp` ≠ (pyproject + installed-manifest) **or** `.deps-ok` missing; write `.deps-ok` last; set `venv_rebuilt`.
- **P**: PyInstaller `--clean` only if source hash moved **or** `venv_rebuilt` **or** bundle/output missing; `robust_rmrf $BUNDLE` first; rewrite privacy manifest + `.source-stamp` (after a good build). Provenance `git rev-parse` keeps its `|| echo unknown` guard **and logs a warning** when it resolves to `unknown` (stripped-env detector).
- **`--force` / `FORCE=1`** bypasses all gates → today's exact full clean rebuild. Release passes `--force`.
- Each step prints `REBUILD <layer> — <reason>` / `skip <layer> (<hash12> matches; output present)` + elapsed.

### 2. `ensure-sidecar.sh` → idempotent orchestrator (new)

```
ensure-sidecar.sh [--force] [--dry-run]
  preconditions (unconditional): npm, node_modules, python3.12, non-empty 64-hex hash
  0. BRISTLENOSE_ALLOW_STALE_SIDECAR=1 → log + exit 0   (escape hatch)
  0. BRISTLENOSE_SKIP_SIDECAR_ENSURE=1 → log + exit 0   (fast schemes; see wiring)
  1. ffmpeg/ffprobe/model presence → fetch-ffmpeg.sh if missing
  2. build-sidecar.sh [--force]        # F + V + P, each gated + output-checked
  3. sign IF (P rebuilt OR .sign-stamp identity != SIGN_IDENTITY OR deep-verify fails):
        sign-ffmpeg.sh   &&   sign-sidecar.sh     # BOTH — ffmpeg is a bundled Mach-O too
        -> codesign --verify --deep --strict; write .sign-stamp atomically
  -> per-layer decision+timing to desktop/build/ensure-sidecar.log + one stdout summary line
```

- **Shell**: `ensure-sidecar.sh` stays **bash-3.2-safe** (it runs as an Xcode build phase under `/bin/bash`); it shells out to `sign-sidecar.sh` as a child, which keeps its own `#!/usr/bin/env bash` (4.3+) shebang.
- **Distribution guard**: if `SIGN_IDENTITY != "-"` (a real identity) ensure refuses to proceed unless invoked via `build-all.sh` (an env flag `_BRISTLENOSE_RELEASE=1`) — Distribution signing is never auto-invoked from the IDE inner loop. The Release-config Cmd+R/Archive path therefore ad-hoc-signs for *local validation only*; the shipping artifact comes from `build-all.sh`.
- **ffmpeg sign-state**: a `.sign-stamp` covering ffmpeg/ffprobe, re-signed on identity change / fetch / verify-fail — independent of the sidecar P gate (ffmpeg never changes when Python does).

## Xcode wiring

- **Add `Ensure Sidecar Fresh` as the phase immediately BEFORE `Copy Sidecar Resources`** (not first). Swift compilation reads nothing from the bundle — only `Copy Sidecar Resources` consumes it — so placing ensure first would make a Swift-only iteration with stale Python WIP block on a Python rebuild it doesn't need, *worsening the motivating pain*. Before-Copy lets Swift compile in parallel, nothing lost, and the bundle is fresh exactly when it's consumed. `alwaysOutOfDate = 1` (internal fingerprints decide).
- **Skip mechanism — refined during implementation (the per-scheme problem).** The plan said "user-defined build setting per scheme." But build settings vary by **configuration**, not by scheme, and the three schemes (bundled, Dev Sidecar, External Server) **all build the Debug config** — so a per-config build setting cannot tell them apart. A scheme `<LaunchAction>` env var is invisible to build phases (the original bug). The two real options:
  - **(a) Per-scheme build _configurations_** — duplicate Debug into `Debug` (bundled, ensure runs) and `Debug (No Sidecar)` (sets `BRISTLENOSE_SKIP_SIDECAR_ENSURE = 1` as a build setting the phase reads), and point the Dev Sidecar + External schemes at the latter. Correct and clean, but it's new build-configs + scheme repointing — fiddly pbxproj surgery best done in Xcode's UI.
  - **(b) Accept ensure runs on all schemes** — it is **near-instant when the bundle is fresh** (all fingerprints skip in ~1s), so the only cost is on a fast scheme *with a stale bundle*, recoverable via the `BRISTLENOSE_ALLOW_STALE_SIDECAR=1` escape hatch. Cheapest; ships the goal for the common case.
  - Recommendation: ship **(b)** first (zero pbxproj risk), add **(a)** if fast-scheme-with-stale-bundle proves annoying. Either way the `ensure-sidecar.sh` skip-flag (`BRISTLENOSE_SKIP_SIDECAR_ENSURE`) is honoured; only *how it's set per scheme* differs.
  - Audit (both options): never set the flag in the default `Bristlenose.xcscheme` (the `isEnabled=YES`-leak scar in `desktop/CLAUDE.md`).
- **`SIGN_IDENTITY` via build setting too** — user-defined per config (Debug `-`, Release `Apple Distribution: …`), read by the phase. Fail-closed: Release config resolving to `-` is a hard error.
- **Gate stays loud + gains an output check.** `Copy Sidecar Resources` keeps `check-sidecar-freshness.sh || exit 1` **before the rsync**; the gate additionally asserts the built artefact is present in the bundle (`server/static/index.html` non-empty, sidecar binary mtime ≥ newest source) — the output-side truth the source-hash comparison structurally lacks. This gate runs on the bundled scheme **even when ensure is skipped**, so a leaked skip-flag can't silently ship stale.
- **Escape hatch unchanged**: `BRISTLENOSE_ALLOW_STALE_SIDECAR=1` skips ensure *and* the gate.

**Build-phase env caveat**: ensure prepends the Homebrew Node keg to PATH, logs to `desktop/build/ensure-sidecar.log`, and on failure prints a "run this in a terminal" pointer.

## Local vs TestFlight

One orchestration *script*, but **two non-equivalent doors** — and the plan is honest about it:

- **Cmd+R / IDE Archive (Debug or Release)** → `ensure-sidecar.sh` ad-hoc-signs (`-`) for **local validation only**. IDE-Archive is explicitly a **non-shipping** path.
- **`build-all.sh --force` (the only shipping path)** → runs every preflight (identity/profile/notary preflight, logging-hygiene, bundle-manifest), self-test, inventory-staleness, then `ensure-sidecar.sh --force` (with `_BRISTLENOSE_RELEASE=1` + Distribution `SIGN_IDENTITY`), then archive/export/notarise/verify. The collapse replaces only build-all's steps 2–4 (parallel fetch+build+sign) with `ensure-sidecar.sh --force`; steps 1/1a/1b/2a/2b and 5–10 stay verbatim. ensure preserves the fetch-ffmpeg ‖ build-sidecar concurrency internally (background the fetch) so no release wall-clock regression.

## Instrumentation (explicit goal)

- `desktop/build/ensure-sidecar.log`: per run — timestamp, scheme/identity, per-layer `decision=rebuild|skip reason=<moved|forced|missing-output|verify-failed|precondition> elapsed_ms=<n>`, total, and the `sign-manifest.json` sha/signed_at (audit tie). On an S skip, the prior sign timestamp is **not** rewritten (a skip must not imply a re-sign).
- Stdout one-liner in Xcode's build log: `ensure-sidecar: F skip · V skip · P rebuild(source moved) · S rebuild · 41s`.
- `--dry-run` prints what *would* rebuild and why, no work — for "why is my Cmd+R slow?".

## Risks

1. **Cmd+R can take minutes when `pyproject.toml` (or the installed manifest) changed** — by design; fast schemes + rare dep changes mitigate; surfaced in the log.
2. **`--force` is now the ONLY trigger of the typeguard/`pyz+py` fresh-install audit** (previously every build). Release uses `--force`, so the shipping path keeps it; a local incremental run that hits a transitive-dep landmine is recoverable via `ensure-sidecar.sh --force`. Stated loudly so it isn't a surprise.
3. **Three new stamp writer/checker pairs (F/V/S)** add drift surface (the one existing recipe already drifted once on locale-`sort`). Mitigated by the committed **build-twice assertion** (below) and by each stamp pairing with an output-side check, not just a hash.
4. **pbxproj + signing edits are hard to verify headlessly** — `xcodebuild` exercises the phase; full Archive needs the Distribution identity. Phase the rollout; QA each.

## Phased implementation

1. **`build-sidecar.sh` per-layer incremental** (+ `--force`, output-side checks, unconditional preconditions, per-layer + git-unknown logging). Standalone-testable.
2. **`ensure-sidecar.sh`** — orchestrator (sign sidecar **and** ffmpeg, deep-verify gate, identity-transition→force-P, Distribution guard, `--dry-run`, instrumentation).
3. **Xcode**: add the before-Copy phase; build settings for skip-flag + SIGN_IDENTITY; gate keeps `exit 1` + gains the output assertion; **update `desktop/CLAUDE.md`** (the "Cmd+R doesn't rebuild the sidecar" entries invert) in the same commit.
4. **Collapse `build-all.sh`** steps 2–4 onto `ensure-sidecar.sh --force` (concurrency preserved), keep 1/1a/1b/2a/2b/5–10 verbatim.
5. **Committed test** — `desktop/scripts/test-ensure-sidecar.sh` (or a pytest/Swift-test seam): run ensure twice → second run all-skip + outputs present; touch one `.py` → only P+S rebuild; wipe `server/static/` → F rebuilds. Catches the stamp-drift class.

QA (human, after): Swift-only Cmd+R instant; one-line `.py` edit rebuilds only P+S; `pyproject` edit recreates V; wiped `static/` is caught; Dev Sidecar scheme untouched; `build-all.sh --force` still produces a valid Distribution-signed, notarised build.
