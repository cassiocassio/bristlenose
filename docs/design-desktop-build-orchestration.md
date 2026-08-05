---
status: current
last-trued: 2026-08-05
trued-against: HEAD@main on 2026-08-05 (scripts + pbxproj + 353 logged ensure runs)
---

> **Truing status:** Partial — trued 2026-08-05. §Per-layer fingerprinting, §Script changes,
> §Xcode wiring, §Local vs TestFlight and §Risks are now as-built. **§Instrumentation is
> aspirational, not shipped** — it carries its own banner. §Phased implementation is retired as
> history. Everything else was verified against the scripts and left alone.

## Changelog

- _2026-08-05_ — trued up: corrected three output-side checks the doc claimed and the code never had (binary-mtime comparison, in-bundle `index.html` assertion); fixed the false "child keeps its own shebang" claim that the bare-`bash` invocation contradicts; marked §Instrumentation aspirational (none of its three claims are built); recorded the Release-config carve-out on the Ensure phase; retired §Phased implementation; absorbed the Phase-3 human-QA outcomes; added front-matter. Anchors: `desktop/scripts/build-sidecar.sh`, `ensure-sidecar.sh:138`, `check-sidecar-freshness.sh`, `build-all.sh:84,223,240,287`, pbxproj `499FD919EA7B4611AE10AE6A`, commits "desktop: skip Ensure Sidecar Fresh phase during Release archive", "reuse pip cache for incremental sidecar builds", "make sidecar build-phase PATH fallback respect a configured toolchain".
- _2026-08-05_ — added §The third staleness class + the V `--exclude-editable` sub-bullets. Anchors: commits "build-sidecar: fail loudly when the tree moves under the build", "build-sidecar: stop the venv gate rebuilding on every commit".
- _2026-06-29_ — initial draft (v2, post-plan-review).

# Desktop build orchestration — Cmd+R self-heals the sidecar

_Status: v2 — **Phases 1–5 implemented** (Phase 3 Xcode wiring landed 29 Jun 2026, option (b) — no per-scheme skip, **and since amended: the phase `exit 0`s for `CONFIGURATION = Release`**). Revised after a multi-agent plan-review; review log kept locally. Goal: hitting Cmd+R in Xcode auto-rebuilds+signs whatever bundle inputs are stale, **incrementally**, so the developer never hand-runs `build-sidecar.sh` + `sign-sidecar.sh` + clean-build again — while fast-iteration schemes stay instant and the loud staleness gate is preserved as an independent backstop. TestFlight artifacts still come only from `build-all.sh`._

## Implementation status (2026-06-29)

| Phase | What | State |
|---|---|---|
| 1 | `build-sidecar.sh` per-layer incremental (F/V/P, `--force`/`--dry-run`, output-side checks, unconditional preconditions, empty-hash guard) + `frontend_source_hash` sliced from the single recipe | **Done.** Decision logic verified via `--dry-run`; live bundle stamp unchanged (no spurious rebuild). |
| 2 | `ensure-sidecar.sh` orchestrator (escape hatches, Distribution guard, identity-transition→force-P, signs ffmpeg **and** sidecar, deep-verify, atomic `.sign-stamp` outside the bundle, run-log) | **Done.** Verified: cascade, Distribution guard aborts, skip-flags short-circuit. |
| 4 | `build-all.sh` collapse — steps 2–4 → one `ensure-sidecar.sh --force` under `_BRISTLENOSE_RELEASE=1`; preflight/self-test/inventory/archive/notarise kept | **Done** (syntax + sequence verified; full release run needs the Distribution identity → human). |
| 5 | `test-ensure-sidecar.sh` — committed decision-logic test | **Done.** Cases 1–8; two of them (recipe-vs-live-stamp, P-skip isolation) are **conditional** on a healthy `.venv-sidecar` and a tree matching the bundle stamp, so the pass *count* is environment-dependent — cite cases, not a number. Extended 4–5 Aug 2026 with case 8's two assertions (race gate present; fingerprint ignores the generated `_build_info.py`). |
| 3 | Xcode: `Ensure Sidecar Fresh` build phase before Copy; gate keeps `exit 1` + output assertion; skip mechanism; SIGN_IDENTITY mapping; `desktop/CLAUDE.md` update | **Done** (29 Jun 2026). `PBXShellScriptBuildPhase` (UUID `499FD919EA7B4611AE10AE6A`, `alwaysOutOfDate=1`) inserted into the `Bristlenose` target's `buildPhases` immediately before `Copy Sidecar Resources`; runs `ensure-sidecar.sh`. Shipped **option (b)** — no per-scheme skip (ensure runs on every scheme, ~instant when fresh; `BRISTLENOSE_SKIP_SIDECAR_ENSURE=1` opt-out honoured). Copy's `check-sidecar-freshness.sh` gate kept as-is (independent backstop). No SIGN_IDENTITY plumbing (ad-hoc default + Distribution guard). `pbxproj` validated via `plutil -lint` + `xcodebuild -list`. **Human QA: done** (was "three passes remaining"; the plan actually listed four). Evidence: fresh-bundle all-skip and stale→rebuild are exercised continuously — `desktop/build/ensure-sidecar.log` holds 353 runs from 2026-06-29T12:38:59Z onward; the Python-edit→P-rebuild pass was recorded live 29 Jun 15:19Z; the Distribution-archive pass is evidenced by the shipped TestFlight builds (commits "desktop: fix 3 App Store Connect upload rejections (nested-binary MAS signing)", "desktop: flip Release to sandbox + hardened runtime for App Store upload"). **Since amended:** the phase now `exit 0`s for `CONFIGURATION = Release` — see §Xcode wiring. |

_(Written 29 Jun 2026, when the expensive end-to-end runs — a real full `build-sidecar.sh`, a Cmd+R with the phase wired, a `build-all.sh --force` Distribution archive — were still outstanding, having been deliberately not run autonomously mid-glyph-QA. All three have since happened many times over; see the Phase 3 row.)_

## Problem

The desktop app runs a **bundled** PyInstaller sidecar (`desktop/Bristlenose/Resources/bristlenose-sidecar/`) plus the React SPA baked into it — not live source. Today the only safety net is **detection**: the `Copy Sidecar Resources` build phase runs `check-sidecar-freshness.sh`, which **fails the build** when `bristlenose/**/*.py`, `bristlenose/locales/**`, or `frontend/` source has moved past the bundle's `.source-stamp`. Remediation is manual and three-step (`build-sidecar.sh && sign-sidecar.sh` + sometimes a clean build). Two things are wrong: the gate detects but doesn't remediate, and `build-sidecar.sh` recreates `.venv-sidecar` from scratch every run (multi-minute), so it can't naively fire on every Cmd+R.

## Goals / non-goals

**Goals**: Cmd+R auto-brings the bundle up to date before the bundle is consumed, no manual scripts; **per-layer incremental** (only the changed layer rebuilds; the big win is reusing `.venv-sidecar` when deps are unchanged); fast-iteration schemes stay instant; one `ensure-sidecar.sh` callable standalone and from Xcode; **lots of instrumentation**.

**Non-goals**: not changing what gets bundled, the spec, entitlements, or the notarise/export tail; **not making IDE-Archive a shipping path** (TestFlight = `build-all.sh` only); **not introducing a Python lockfile** (separate, larger project — release `--force` + an installed-manifest fingerprint is the bounded mitigation).

## Core principle (the keystone, from review)

**Stamps attest _inputs_; the design must also check _outputs_.** The existing `check-sidecar-freshness.sh` compares a recomputed source hash against `.source-stamp`. Every incremental skip path *writes a matching stamp by construction*, so the source-vs-stamp gate **cannot** catch the orchestrator's own skip bugs — it validates consistency, never correctness. Therefore:

1. The freshness gate stays **loud (`exit 1`), before the rsync**, exactly as today — demotion means "expected to pass," never "allowed to warn."
2. Each layer's skip predicate includes an **output-side check** the input-stamp cannot fake. Two independent computations agreeing is the only thing that makes "did nothing" safe.

**As built (5 Aug 2026), point 2 is weaker than this section claims** — stated here rather than quietly corrected, because the gap is the interesting part. What shipped: F asserts `bristlenose/server/static/index.html` exists and is non-empty (**source-side**, `build-sidecar.sh`); V requires the `.deps-ok` sentinel; P asserts the outer bundle binary exists and is executable. What did **not** ship: the *binary mtime ≥ newest source mtime* comparison and the *in-bundle* `index.html` assertion — grep the three scripts for `mtime` or `-nt` and there is nothing. So P's output check confirms the bundle exists, not that it contains a current SPA; the in-bundle side is unguarded. Treat the mtime/in-bundle wording below (§Per-layer fingerprinting, §Xcode wiring) as design intent, not as a safety net you can rely on today.

## The third staleness class — the tree moving under the build (4 Aug 2026)

`sidecar_source_hash` is snapshotted **once at entry** to `build-sidecar.sh` and written into `.source-stamp` **after** the build, but Vite and PyInstaller read the tree somewhere in between. So a hashed file saved *during* the build yields a bundle that genuinely lacks that edit while the stamp attests a tree that no longer exists. The window is the build's own duration — seconds on a skip path, minutes on a full P rebuild.

The freshness gate already catches this, correctly, on the very next build phase. What it can't do is *explain* it: it reports a bundle-vs-source mismatch, which reads as "the rebuild didn't work" when the truth is "the rebuild worked and then you saved a file."

**Observed 4 Aug 2026.** `ensure-sidecar` ran 18:30:17Z→18:31:15Z, logged `Stamped .source-stamp: 8c89d089e4c4…`, and `Copy Sidecar Resources` failed one second later reading `1d2897c4698f`. Both lines were true; a frontend save had landed inside the 58-second window. The screenshot looked like the check chain contradicting itself.

So `build-sidecar.sh` now **recomputes the fingerprint at the end of a real run and fails if it moved**, naming the window width and both hashes. Three properties are deliberate:

- **The bundle keeps the entry-hash stamp.** Moving the stamp to a post-build hash would close the window by making the stamp *lie* — it would claim the bundle contains an edit PyInstaller never read, converting a loud correct failure into a silently stale bundle. The mismatch left behind is also what makes the next run rebuild P instead of skipping.
- **It fires on skip paths too**, not just rebuilds. If the tree moves during even a fast all-skip run, the bundle is genuinely stale and the freshness gate would fail anyway — better to say why.
- **It rests on `sidecar-source-hash.sh` excluding `bristlenose/_build_info.py`.** That file is *generated* by the P layer (git SHA + build date) and sits on disk until the script's EXIT trap removes it, so it is present at recompute time. Counted, it would move the hash on **every** build (measured: `476c2224` → `612bddee`) and the gate would cry wolf permanently. The exclusion is a no-op in the steady state — the file is absent — so it moved nobody's fingerprint. Pinned behaviourally by `test-ensure-sidecar.sh` case 8.

This does **not** make staleness impossible; nothing can, short of freezing the working tree. It makes the one unavoidable case legible. The escape for anyone iterating fast enough to keep hitting it is unchanged: the **Dev Sidecar** / **External Server** schemes serve live source and skip the bundle loop entirely.

## The two cadences

| Loop | Changes | Scheme | Pre-step cost |
|---|---|---|---|
| **Inner** (seconds) | Swift / React / CSS | Dev Sidecar · External Server | none — skipped |
| **Bundle** (seconds→minutes) | Python / frontend in the bundle | Bristlenose (bundled) | only the changed layer |

Automation lives on the bundle loop. **Release lives only in `build-all.sh`** (the irreversible boundary stays thorough — ETTO).

## Per-layer fingerprinting

| Layer | Rebuild trigger | Output-side check on skip | Cost when triggered | When not |
|---|---|---|---|---|
| **ffmpeg** | `ffmpeg` + `ffprobe` *presence* in `Resources/` (the **model is deliberately not checked** — it's first-run-downloaded, not built here) | n/a | one-time download | stat |
| **F · frontend** | frontend slice of `sidecar_source_hash` ≠ `.frontend-stamp` | `server/static/index.html` present + non-empty | `npm run build`, ~10–30s | skip |
| **V · venv** | venv missing (`! -x $PYTHON`), OR `pyproject.toml` hash + `.venv-sidecar` **installed-manifest** (`pip freeze --exclude-editable`) ≠ `.deps-stamp`, OR `.deps-ok` sentinel absent | `.deps-ok` sentinel exists (written only after install **and** `PyInstaller --version` pass) | recreate venv + pip, minutes | skip (reuse) |
| **P · PyInstaller** | full `sidecar_source_hash` ≠ `.source-stamp`, OR V rebuilt, OR **F rebuilt** (any F rebuild cascades — not merely "F output missing"), OR bundle missing | sidecar binary present + executable. _(The planned in-bundle `server/static/index.html` assertion was never implemented — see §Core principle.)_ | PyInstaller **`--clean`**, ~tens of sec | skip |
| **S · codesign (sidecar + ffmpeg)** | P rebuilt, OR `.sign-stamp` identity ≠ requested, OR `codesign --verify --deep --strict` fails | `--verify --deep --strict` passes | sign loop, seconds | skip |

**Decisions baked in from review:**

- **V (venv) — keep the reuse, make it honest.** Reusing `.venv-sidecar` when deps are unchanged is ~95% of the speed win. But `>=`-floor deps + no lockfile mean "`pyproject.toml` unchanged" ≠ "closure unchanged," and an interrupted `pip install` can leave a half-venv. So the V fingerprint hashes `pyproject.toml` **plus the actually-installed manifest** (`pip freeze` of `.venv-sidecar`), and a `.deps-ok` sentinel is written **only after** a clean `pip install` *and* the `PyInstaller --version` check. V skips only if hash matches **and** `.deps-ok` exists. Residual (a transitive republish within the same floor) is covered by **release always `--force`** — which recreates from scratch and is now the *only* trigger of the typeguard/`pyz+py` fresh-install audit (called out in Risks).
  - **Incremental recreates reuse pip's wheel cache; only `--force` passes `--no-cache-dir`.** So an incremental V rebuild re-installs from wheels already on disk (no network, much faster than the "minutes" figure implies) — and *cannot* pick up a transitive republish even though it recreated the venv. Only the release path re-resolves against live PyPI. This sharpens Risk 2 below: `--force` isn't merely the *preferred* trigger of the fresh-install audit, it's the **only** code path that can observe the drift at all.
  - **`pip freeze` must be `--exclude-editable` (5 Aug 2026).** In a git checkout pip renders the editable self-install as `-e git+…/bristlenose.git@<HEAD-sha>#egg=bristlenose`, so the fingerprint embedded the **current commit** and V recreated the venv after *every* commit — a docs-only one included — cascading a P rebuild each time. The run log had **130 V rebuilds against 131 skips**, for a gate meant to fire only on dependency movement; since commit-then-build is the normal rhythm, the incremental design only paid off when you built twice without committing in between. Excluding the self-reference costs the gate nothing it doesn't already hold (bristlenose's code → `sidecar_source_hash`; its declared deps + extras → the `pyproject.toml` hash in the same fingerprint; a hand-installed package → still among the other ~129 entries; an editable→wheel switch → reappears, since a non-editable install isn't excluded).
  - **This whole gate is a hand-rolled `uv sync --check`.** Both halves — the deps fingerprint *and* the `.deps-ok` half-install sentinel — are approximations of one command that `docs/design-dev-environment.md` §Phase 3 already plans to adopt with `uv.lock` (gated post-TestFlight; it also unlocks the wheel-hash pinning the verifiable-security track needs). The `--exclude-editable` fix is deliberately a patch to a mitigation with a scheduled replacement, not a better fingerprint — anything more ambitious builds something Phase 3 deletes.
- **P — always `--clean` + `robust_rmrf $BUNDLE`** on any rebuild. Warm-workpath PyInstaller saves only tens of seconds and reintroduces the documented "appended stale Mach-Os / failed verification without a clear cause" class on file add/delete. The venv-reuse win stands alone; warm-P is dropped (Knuth's 97%).
- **S — signs BOTH sidecar and ffmpeg**, gates on `--verify --deep --strict` (shallow verify passes on stale inner CDHashes), and writes `.sign-stamp` atomically only after deep-verify passes.
- **Identity transitions are never incremental.** If `.sign-stamp` identity ≠ requested `SIGN_IDENTITY`, force a clean **P** rebuild (not just an S re-sign) so every inner Mach-O is signed under one identity — avoids mixed-identity bundles (ad-hoc→Distribution) and the `ALLOW_RESIGN=0` red-screen (Distribution→ad-hoc).

## Script changes

Two scripts. Layering lives **inside** the bundle builder, gated by fingerprints.

### 1. `build-sidecar.sh` → per-layer incremental (behaviour-preserving)

- **Preconditions run unconditionally, first** (npm, `node_modules`, `python3.12`) — never gated behind a skip decision. An empty/malformed `sidecar_source_hash` (not 64 hex) is a hard `exit 1`, never "all-skip." **Each tool resolves against a stripped PATH**: Xcode build phases drop Homebrew, so both scripts fall back to the Homebrew prefix (and, separately, the keg-only `node@24` bin) — but **only when the tool isn't already resolvable**, so a contributor's mise/asdf/pyenv toolchain wins untouched and is never reordered. If it's still unreachable, error loudly rather than skip. Not a universal resolver by design.
- **F**: `npm run build` only if frontend slice moved **or** `server/static/index.html` missing; rewrite `.frontend-stamp`.
- **V**: recreate `.venv-sidecar` only if `.deps-stamp` ≠ (pyproject + installed-manifest) **or** `.deps-ok` missing; write `.deps-ok` last; set `venv_rebuilt`.
- **P**: PyInstaller `--clean` only if source hash moved **or** `venv_rebuilt` **or** `frontend_rebuilt` (the load-bearing cascade — the bundle's baked `static/` is a copy) **or** bundle/output missing; `robust_rmrf $BUNDLE` first; rewrite privacy manifest + `.source-stamp` (after a good build). Provenance `git rev-parse` keeps its `|| echo unknown` guard **and logs a warning** when it resolves to `unknown` (stripped-env detector).
- **`--force` / `FORCE=1`** bypasses all gates → today's exact full clean rebuild. Release passes `--force`.
- Each step prints `    [F] REBUILD — <reason>` / `    [F] skip (<hash12> matches; output present)`. **No per-layer timing is emitted** — the "+ elapsed" this line used to promise was never built; see §Instrumentation.
- **Race gate (tail, real runs only)**: recompute `sidecar_source_hash` and `exit 1` if it differs from the entry snapshot — the tree moved under the build, so the bundle lacks that edit. Reports the window width and both hash prefixes. Not a `--force` bypass: it reports a fact about the tree, not a skip decision. See §The third staleness class.

### 2. `ensure-sidecar.sh` → idempotent orchestrator (new)

```
ensure-sidecar.sh [--force] [--dry-run]
  PATH prepend: Homebrew prefix, only if absent (see Shell note below)
  0. BRISTLENOSE_ALLOW_STALE_SIDECAR=1 → log + exit 0   (escape hatch)
  0. BRISTLENOSE_SKIP_SIDECAR_ENSURE=1 → log + exit 0   (fast schemes; see wiring)
  0b. Distribution guard: real SIGN_IDENTITY without _BRISTLENOSE_RELEASE=1 → exit 1
  1. ffmpeg/ffprobe presence → fetch-ffmpeg.sh if missing   (model is NOT checked)
  2. identity transition (.sign-stamp identity != SIGN_IDENTITY) → force a clean P
  3. build-sidecar.sh [--force]        # F + V + P, each gated + output-checked
                                       # (preconditions live HERE, not in ensure)
  4. sign IF (P rebuilt OR identity changed OR ffmpeg fetched OR deep-verify fails):
        sign-ffmpeg.sh   ;   sign-sidecar.sh      # BOTH — ffmpeg is a bundled Mach-O too
        -> codesign --verify --deep --strict; write .sign-stamp atomically
  -> event-by-event lines to desktop/build/ensure-sidecar.log (NOT the structured
     per-layer decision+timing format described in §Instrumentation — unbuilt)
```

- **Shell**: `ensure-sidecar.sh` stays **bash-3.2-safe** (it runs as an Xcode build phase under `/bin/bash`); it shells out to `sign-sidecar.sh` as a child. **The child does NOT keep its own shebang** — an earlier revision of this line said it did, and that is exactly the trap. `ensure-sidecar.sh:138/159/160` invoke it as bare `bash "$SCRIPT_DIR/sign-sidecar.sh"`, which **overrides** `#!/usr/bin/env bash` and resolves to the first `bash` on PATH. Under Xcode's stripped PATH that is `/bin/bash` 3.2, and `sign-sidecar.sh` needs 4.3+. The requirement is met only by the Homebrew-prefix PATH prepend at the top of both scripts — remove the prepend, or "tidy" the invocation, and signing breaks in-phase while working fine from a login shell.
- **Distribution guard**: if `SIGN_IDENTITY != "-"` (a real identity) ensure refuses to proceed unless invoked via `build-all.sh` (an env flag `_BRISTLENOSE_RELEASE=1`) — Distribution signing is never auto-invoked from the IDE inner loop. The Release-config Cmd+R/Archive path therefore ad-hoc-signs for *local validation only*; the shipping artifact comes from `build-all.sh`.
- **ffmpeg sign-state**: a `.sign-stamp` covering ffmpeg/ffprobe, re-signed on identity change / fetch / verify-fail — independent of the sidecar P gate (ffmpeg never changes when Python does).

## Xcode wiring

- **Add `Ensure Sidecar Fresh` as the phase immediately BEFORE `Copy Sidecar Resources`** (not first). Swift compilation reads nothing from the bundle — only `Copy Sidecar Resources` consumes it — so placing ensure first would make a Swift-only iteration with stale Python WIP block on a Python rebuild it doesn't need, *worsening the motivating pain*. Before-Copy lets Swift compile in parallel, nothing lost, and the bundle is fresh exactly when it's consumed. `alwaysOutOfDate = 1` (internal fingerprints decide).
- **Skip mechanism — refined during implementation (the per-scheme problem).** The plan said "user-defined build setting per scheme." But build settings vary by **configuration**, not by scheme, and the schemes (bundled, Dev Sidecar, External Server — and since 29 Jun a fourth, `Bristlenose default`) **all build the Debug config** — so a per-config build setting cannot tell them apart. A scheme `<LaunchAction>` env var is invisible to build phases (the original bug). The two real options:
  - **(a) Per-scheme build _configurations_** — duplicate Debug into `Debug` (bundled, ensure runs) and `Debug (No Sidecar)` (sets `BRISTLENOSE_SKIP_SIDECAR_ENSURE = 1` as a build setting the phase reads), and point the Dev Sidecar + External schemes at the latter. Correct and clean, but it's new build-configs + scheme repointing — fiddly pbxproj surgery best done in Xcode's UI.
  - **(b) Accept ensure runs on all schemes** — it is **near-instant when the bundle is fresh** (all fingerprints skip in ~1s), so the only cost is on a fast scheme *with a stale bundle*, recoverable via the `BRISTLENOSE_ALLOW_STALE_SIDECAR=1` escape hatch. Cheapest; ships the goal for the common case.
  - **Shipped (b) on 29 Jun 2026** — no per-scheme skip wired; revisit (a) only if a fast scheme with a stale bundle becomes a recurring annoyance. _(The preceding two options are retained as the reasoning; (b) was chosen for zero pbxproj risk. Either way the `ensure-sidecar.sh` skip-flag `BRISTLENOSE_SKIP_SIDECAR_ENSURE` is honoured; only how it's set per scheme differs.)_
  - **Amended since: the phase `exit 0`s for `CONFIGURATION = Release`.** So the shipped state is option (b) *minus Release* — ensure runs on every **Debug** scheme and not at all during a Release archive (commit "desktop: skip Ensure Sidecar Fresh phase during Release archive"). Belt-and-braces, `build-all.sh` also exports `BRISTLENOSE_SKIP_SIDECAR_ENSURE=1` before archiving, so the in-archive phase is suppressed from both ends. This is deliberate — the shipping bundle is built by `build-all.sh`'s own `ensure-sidecar.sh --force` step, and re-running ensure inside the archive would be redundant at best and identity-confusing at worst.
  - Audit (both options): never set the flag in the default `Bristlenose.xcscheme` (the `isEnabled=YES`-leak scar in `desktop/CLAUDE.md`).
- **~~`SIGN_IDENTITY` via build setting~~ — dropped (Finding 11).** No per-config SIGN_IDENTITY plumbing was wired. `ensure-sidecar.sh` defaults to ad-hoc `-`, and its **Distribution guard** refuses a real identity unless `_BRISTLENOSE_RELEASE=1` (set only by `build-all.sh`). So Cmd+R / IDE-Archive ad-hoc-sign for local validation; TestFlight artifacts come only from `build-all.sh` (IDE-Archive is a non-shipping path — Finding 8). This removed the per-config build-setting work the v1 plan assumed.
- **Gate stays loud. The planned output check was never added.** `Copy Sidecar Resources` keeps `check-sidecar-freshness.sh || exit 1` **before the rsync** — that part shipped and holds. But the gate does *hash-vs-stamp only*; the additional in-bundle assertions this line used to promise (`server/static/index.html` non-empty, sidecar binary mtime ≥ newest source) do **not** exist in `check-sidecar-freshness.sh`. The output-side truth the source-hash comparison structurally lacks is therefore still missing — see §Core principle. The gate does still run on the bundled scheme **even when ensure is skipped**, so a leaked skip-flag can't silently ship stale; that much of the defence is real.
- **Escape hatch unchanged**: `BRISTLENOSE_ALLOW_STALE_SIDECAR=1` skips ensure *and* the gate.

**Build-phase env caveat**: ensure prepends the Homebrew Node keg to PATH, logs to `desktop/build/ensure-sidecar.log`, and on failure prints a "run this in a terminal" pointer.

## Local vs TestFlight

One orchestration *script*, but **two non-equivalent doors** — and the plan is honest about it:

- **Cmd+R (Debug)** → `ensure-sidecar.sh` ad-hoc-signs (`-`) for **local validation only**. **IDE Archive (Release) no longer runs ensure at all** — the phase `exit 0`s for `CONFIGURATION = Release` (see §Xcode wiring). IDE-Archive remains explicitly a **non-shipping** path.
- **`build-all.sh --force` (the only shipping path)** → runs every preflight (identity/profile/notary preflight, logging-hygiene, bundle-manifest), self-test, inventory-staleness, then `ensure-sidecar.sh --force` (with `_BRISTLENOSE_RELEASE=1` + Distribution `SIGN_IDENTITY`), then archive/export/notarise/verify. The collapse replaced only build-all's steps 2–4 (parallel fetch+build+sign) with `ensure-sidecar.sh --force`; the surrounding steps stayed verbatim — **though the step list has since grown**: 1a-bis (appearance-seam gate), 2c (App Store §2.5.2 string scan), 2d (`.mcpb` build + check). Don't treat the old "1/1a/1b/2a/2b and 5–10" enumeration as current; read `build-all.sh`.
  - **Concurrency was never implemented.** This line used to claim ensure "preserves the fetch-ffmpeg ‖ build-sidecar concurrency internally (background the fetch)". It doesn't — the fetch runs synchronously at step 1, the build at step 3, and there is no `&`/`wait` anywhere in `ensure-sidecar.sh`. In practice this costs nothing, because the fetch is a one-time download that no-ops on every subsequent run; but the parallelism the collapse was supposed to preserve is simply gone.

## Instrumentation (explicit goal)

> **Aspirational — not built as of 5 Aug 2026.** Of the three items below, only `--dry-run`
> shipped. Verified across 353 logged runs: **zero** occurrences of `decision=` or `elapsed_ms`,
> no summary line, no `sign-manifest.json` tie. Don't grep for them. The original goal is kept
> verbatim below because it's still the right target; what the log *actually* contains is
> recorded underneath.

- ~~`desktop/build/ensure-sidecar.log`: per run — timestamp, scheme/identity, per-layer `decision=rebuild|skip reason=<moved|forced|missing-output|verify-failed|precondition> elapsed_ms=<n>`, total, and the `sign-manifest.json` sha/signed_at (audit tie). On an S skip, the prior sign timestamp is **not** rewritten (a skip must not imply a re-sign).~~ **Unbuilt.**
- ~~Stdout one-liner in Xcode's build log: `ensure-sidecar: F skip · V skip · P rebuild(source moved) · S rebuild · 41s`.~~ **Unbuilt** — the per-layer `    [F] skip …` lines come from `build-sidecar.sh`; `ensure-sidecar.sh` prints event-by-event `_say` lines and no summary.
- `--dry-run` prints what *would* rebuild and why, no work — for "why is my Cmd+R slow?". **Shipped**, and the one piece of this section you can rely on.

**What the log actually contains**, per run: a `---- <ISO ts>  identity=<id> force=<0|1> dry=<0|1> release=<0|1>` header; an ffmpeg present/fetched line; the **entire raw stdout of `build-sidecar.sh`** (including full PyInstaller output); a sign done/skip line; and a `==== done <ISO ts>` terminus. Start and end timestamps are the only timing available — subtract them for total wall-clock, which is how the figures in this doc were measured.

**Consequence worth knowing:** because the whole PyInstaller stdout is appended, the log is **unrotated and ~15 MB after 353 runs**. That directly contradicts the compact-structured-log framing above. If this section ever gets built, rotation belongs in the same pass.

## Risks

1. **Cmd+R can take minutes when `pyproject.toml` (or the installed manifest) changed** — by design; fast schemes + rare dep changes mitigate; surfaced in the log.
2. **`--force` is now the ONLY trigger of the typeguard/`pyz+py` fresh-install audit** (previously every build). Release uses `--force`, so the shipping path keeps it; a local incremental run that hits a transitive-dep landmine is recoverable via `ensure-sidecar.sh --force`. Stated loudly so it isn't a surprise.
3. **Three new stamp writer/checker pairs (F/V/S)** add drift surface (the one existing recipe already drifted once on locale-`sort`, and the V pair drifted again on the git-SHA-in-`pip freeze` bug fixed 5 Aug 2026). **The planned mitigation did not ship as described:** there is no committed *build-twice assertion* — `test-ensure-sidecar.sh` drives decisions via `--dry-run` + controlled stamp state and two grep-for-guard-text checks; it never runs ensure twice, never touches a `.py`, never wipes `server/static/`. And the output-side pairing is partial (§Core principle). So this risk is **live**, not mitigated — which is precisely how the V drift survived from 29 Jun to 5 Aug.
4. **pbxproj + signing edits are hard to verify headlessly** — `xcodebuild` exercises the phase; full Archive needs the Distribution identity. _(Rollout complete: 353 logged ensure runs and shipped TestFlight archives. Retained as a standing caution for future edits to the phase.)_

## Phased implementation

> **Retired 2026-08-05 — this was the plan of record for work that shipped 29 Jun 2026.**
> Kept as history, not as instruction. Two of its five items had drifted into contradicting the
> body: item 3 still prescribed per-config build settings for the skip-flag and `SIGN_IDENTITY`
> (both **dropped** — see §Xcode wiring), and item 5 prescribed a run-twice / touch-a-`.py` /
> wipe-`static/` test shape that is **not** what `test-ensure-sidecar.sh` does (see Risk 3).
> For as-built state read §Implementation status and the sections above.

1. **`build-sidecar.sh` per-layer incremental** (+ `--force`, output-side checks, unconditional preconditions, per-layer + git-unknown logging). Standalone-testable.
2. **`ensure-sidecar.sh`** — orchestrator (sign sidecar **and** ffmpeg, deep-verify gate, identity-transition→force-P, Distribution guard, `--dry-run`, instrumentation).
3. **Xcode**: add the before-Copy phase; build settings for skip-flag + SIGN_IDENTITY; gate keeps `exit 1` + gains the output assertion; **update `desktop/CLAUDE.md`** (the "Cmd+R doesn't rebuild the sidecar" entries invert) in the same commit.
4. **Collapse `build-all.sh`** steps 2–4 onto `ensure-sidecar.sh --force` (concurrency preserved), keep 1/1a/1b/2a/2b/5–10 verbatim.
5. **Committed test** — `desktop/scripts/test-ensure-sidecar.sh` (or a pytest/Swift-test seam): run ensure twice → second run all-skip + outputs present; touch one `.py` → only P+S rebuild; wipe `server/static/` → F rebuilds. Catches the stamp-drift class.

QA (human, after): Swift-only Cmd+R instant; one-line `.py` edit rebuilds only P+S; `pyproject` edit recreates V; wiped `static/` is caught; Dev Sidecar scheme untouched; `build-all.sh --force` still produces a valid Distribution-signed, notarised build. _(All six evidenced — see §Implementation status.)_

## See also

- `desktop/CLAUDE.md` — the operational face of this doc. Its gotchas on the stripped-PATH / shebang-override trap, the `_build_info.py` race signature, and per-layer incremental behaviour are the day-to-day form of §Script changes and §The third staleness class. **Cross-reference, don't mirror** — where the two disagree on script mechanics, `desktop/CLAUDE.md` has historically been the more accurate of the pair.
- `docs/design-dev-environment.md` §Phase 3 — where the V gate retires into `uv sync --check` + `uv.lock`.
