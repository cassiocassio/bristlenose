# Sprint 2 — Three parallel tracks

_Written 18 Apr 2026. The plan that A, B, and C branches all share. Update when the tracks' scope changes._

S2 work runs on three concurrent tracks. Each lives on its own branch (or family of branches), can progress independently, and only converges at the first TestFlight upload.

This doc is the shared map. Branches in any of the three tracks should read this first, and reference it in their commit messages / PR descriptions when scope is unclear.

## Sources of truth

- **`docs/private/100days.md`** §1a — MVP 1-hour flow (the B-track checklist)
- **`docs/private/road-to-alpha.md`** — 14 checkpoints to TestFlight (A and C are subsets)
- **`docs/private/100days.md`** §"Sprint 2 cadence" — A/B interleave rationale

This doc does not duplicate those — it cuts them into branch-shaped pieces.

## The three tracks

### Track A — Sandbox plumbing

Road-to-alpha checkpoints **#2** (Apple Distribution cert + provisioning profile) and **#3** (App sandbox + entitlements).

Code-archaeology and Swift/Python wiring. Driven by sandbox violation logs from running the MVP flow with sandbox enabled in the Debug scheme. Mostly mechanical, but needs human sign-off on architectural calls (e.g. ollama HTTP vs CLI; doctor.py sandbox-aware path).

**Scope cut:** stop before #4. Specifically, this branch family covers:
- `desktop/Bristlenose/Bristlenose.xcodeproj` — Apple Distribution signing config
- `.entitlements` files (new)
- `desktop/Bristlenose/Bristlenose/ServeManager.swift` — sandbox-aware sidecar spawn
- Security-scoped bookmark plumbing for user-picked folders
- `bristlenose/credentials_macos.py` — migrate off `/usr/bin/security` to Security framework
- `bristlenose/ollama.py` — switch CLI spawn to HTTP API
- `bristlenose/stages/s02_extract_audio.py`, `bristlenose/utils/video.py`, `bristlenose/utils/audio.py` — bundled-binary path helper
- `bristlenose/server/clip_backend.py`, `server/clip_manifest.py`, `server/routes/clips_export.py`
- `bristlenose/doctor.py`, `bristlenose/doctor_fixes.py` — sandbox-aware code path
- `bristlenose/utils/hardware.py`

**Suggested branch structure:**
1. `sandbox-debug` — flip sandbox in Debug scheme, exercise MVP flow, produce violation log. No fixes. **Started 29 Apr 2026** on `bristlenose_branch sandbox-debug/` worktree.
2. Per-Python-migration narrow branches as the violation log dictates (`credentials-security-framework`, `ollama-http`, `bundled-binary-helper`, etc.).

**Won't touch:** PyInstaller signing script, frontend, server route handlers (other than subprocess audit).

**A1 first move:** sandbox on in Debug, walk §1a, log every `deny(1) …`. Output: a ranked violation list in this directory (e.g. `sandbox-violations-A1.md`).

**Iteration helper:** `desktop/scripts/reset-sandbox-state.sh` (added 1 May 2026 during A2 verification). Stale Container/UserDefaults state across re-launches manifests as `EXC_BREAKPOINT` in `_libsecinit_appsandbox.cold.*` even when the entitlements themselves are correct — the script wipes the stale-state path so each Cmd+R starts clean. Verbose by default, has `--dry-run`. Run between every Xcode launch when chasing sandbox issues. See `desktop/CLAUDE.md` "Sandbox iteration" gotcha for the full diagnostic context.

### Track B — MVP UX flow

> **Status (29 Apr 2026):** Track B happy path **shipped 26 Apr** via `port-v01-ingestion` (commit `e781ebe` → v0.15.0) — broader scope than predicted: ingestion + multi-project core + lifecycle. End-to-end new project → drop folder → ingestion → processing → display works. Branch 1 = `first-run` worktree (started 29 Apr) for the remaining first-run polish (beat 3 API-key validation, beat 3b Ollama wiring in `AIConsentView`, cold-start splash, empty-state narrative). Polish backlog at `desktop-ux-iteration.md`. The "narrow branch per broken beat" framing below is preserved as the original 18 Apr planning context.

The `100days.md` §1a beats 1–13. The long pole. Judgment-heavy. Quality bar: "Martin can run this on a laptop with no API keys pre-configured and no cached state, from new, in under an hour, and produce a report he'd send to a UXR friend without apologising."

**Scope cut:** one narrow branch per broken beat. No `mvp-flow` umbrella branch — beats 4–6 are mostly Swift, beats 7–10 are mostly React, they don't need to ship together.

**Files touched, by beat:**

| Beat | Likely files |
|---|---|
| 1. First-time empty state | `desktop/Bristlenose/Bristlenose/ContentView.swift`, project sidebar views, possibly `frontend/src/pages/` for empty-state |
| 3. Claude API key in Settings | `frontend/src/components/SettingsModal.tsx`, `bristlenose/server/routes/settings.py` (validation), `desktop/Bristlenose/Bristlenose/Keychain*.swift` |
| 4. New project | `desktop/Bristlenose/Bristlenose/` project sidebar (NSEvent monitor work), `bristlenose/server/routes/projects.py` |
| 5. Drop interview folder | `desktop/Bristlenose/Bristlenose/` drop handlers (`DropDelegate`, UTType validation), `Project.inputFiles` model |
| 6. Process / run from GUI | `desktop/Bristlenose/Bristlenose/ServeManager.swift`, `bristlenose/server/routes/pipeline.py`, progress streaming |
| 7. Display | `frontend/src/` dashboard / quotes / transcripts |
| 8. Codebook | `frontend/src/islands/CodebookPanel.tsx`, `bristlenose/server/routes/codebook.py` |
| 9. Signal cards | `frontend/src/islands/Dashboard*.tsx` |
| 10. Stars / filtering | `frontend/src/contexts/QuotesStore.ts`, related components |
| 13. CSV export | `frontend/src/components/ExportMenu.tsx`, `bristlenose/server/routes/quotes_export.py` |

(Original 18 Apr framing said "Beats 2, 11, 12 already shipped". Updated 29 Apr: beats 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13 reachable end-to-end as of 26 Apr via `port-v01-ingestion`. **Still gaps:** beat 3 — Settings + Keychain shipped (`LLMSettingsView.swift`, `KeychainHelper.swift`) but no live API roundtrip validation; beat 3b implicit — Ollama detection rich on Python side (`bristlenose/ollama.py`) but Swift UI doesn't surface install method / auto-start / model picker.)

**B1 first move (18 Apr framing):** clean-profile walkthrough on the current build to identify the first broken beat. **B1 actual outcome (29 Apr):** the walkthrough effectively happened across `port-v01-ingestion` QA (20–25 Apr) and produced `desktop-ux-iteration.md` (10-section deferred polish backlog). The narrow "per broken beat" branches predicted here did not materialise; what shipped instead was one larger ingestion + multi-project + lifecycle branch. The remaining first-run polish lives on the `first-run` worktree (started 29 Apr).

### Track C — Sidecar bundling + signing (re-scoped 18 Apr 2026)

**Re-scoped.** Original Track C assumed the desktop app already bundled a Python sidecar that just needed codesigning. It doesn't — v0.2 is a launcher-style dev shell (`ServeManager.findBristlenoseBinary()`) that was never intended to ship. Real Track C covers resurrecting the bundling pipeline from v0.1, signing it, and wiring in all the Mac App Store prerequisites. See the implementation plan in `~/.claude/plans/when-you-have-done-encapsulated-conway.md`.

**Canonical design references:**
- [`docs/design-modularity.md`](../design-modularity.md) — **what** goes where (Python deps, extras, Background Assets, cross-channel decisions). The no-fork principle lives here.
- `docs/design-desktop-python-runtime.md` (written 18 Apr 2026 as C0 output; updated through C3) — **how** the Mac sidecar specifically works (ServeManager, entitlements, bundle-data requirements, validation gates, fail-loud contracts, credential flow, codesign chain).

**Sub-scopes (own branch each or narrow sequence):**

- **C0 — Entitlement spike** ✅ done 18 Apr 2026 (commit `7d121fa`). Minimum set empirically reduced to one key (`cs.disable-library-validation`); v0.1's `allow-unsigned-executable-memory` and `allow-jit` both proved unnecessary. Bundle landed at 644 MB (target ≤ 200 MB) — torch/llvmlite/onnxruntime/scipy transitive pulls flagged for C1 excludes pass. See `docs/design-desktop-python-runtime.md`.
- **C1 — Resurrect bundling pipeline, scoped to `serve`** ✅ done 18 Apr 2026. Ported `desktop/v0.1-archive/` forward: PyInstaller spec at `desktop/bristlenose-sidecar.spec`, build script at `desktop/scripts/build-sidecar.sh` (parameterised `SIGN_IDENTITY`, auto-picked `TIMESTAMP_FLAG`, post-sign strict verify + outer `--verify --deep --strict`), output lands at `desktop/Bristlenose/Resources/bristlenose-sidecar/` for Xcode's Copy Sidecar Resources phase. **Dev escape hatch consolidation done:** `findBristlenoseBinary()`'s silent 5-path search replaced with pure `SidecarMode.resolve(externalPortRaw:sidecarPathRaw:bundleResourceURL:fileManager:)`; two explicit Debug-only env vars (`BRISTLENOSE_DEV_EXTERNAL_PORT`, `BRISTLENOSE_DEV_SIDECAR_PATH`); three shared Xcode schemes wrap them; `os.Logger(subsystem: "app.bristlenose", category: "serve")` replaces `print()`. Post-archive `desktop/scripts/check-release-binary.sh` asserts dev env-var literals are absent from Release Mach-Os (defence-in-depth moved forward from C2; script scans every Swift-shell Mach-O in the bundle, skips the Python sidecar). **Size trim + lazy-import work deferred** per `design-modularity.md` §"trickle to full capability" — Background Assets is the post-install story, not build-time trimming.
  - **Fresh-worktree retest 29 Apr 2026** (branch `track-c-c1-bundled-sidecar`, after `sidecar-signing` merged to main on 28 Apr). Goal: confirm C1 deliverables still work post-merge from a clean `/new-feature` setup, with no prior PyInstaller install. Result: green end-to-end. Phase 1 — `build-sidecar.sh` produced a working onedir at `desktop/Bristlenose/Resources/bristlenose-sidecar/`. Phase 2 — bundled binary served `trial-runs/project-ikea` via `serve`, `/api/health` returned 200 with the expected payload, clean SIGINT shutdown. `bristlenose doctor --self-test` green (React SPA + codebooks + LLM prompts + locales + theme + alembic migrations all bundled). Phase 3 — `xcodebuild archive` Release succeeded; `Bristlenose.app/Contents/Resources/bristlenose-sidecar/bristlenose-sidecar` present and `+x`. Phase 4 — `Mode: bundled, path=…/Bristlenose.app/Contents/Resources/bristlenose-sidecar/bristlenose-sidecar` confirmed via `/usr/bin/log show` from a default-scheme launch (sandbox off, hardened runtime off). Two real ergonomic gaps closed in `track-c-c1-bundled-sidecar`: (a) PyInstaller wasn't a declared dep — added new `[desktop]` extra to `pyproject.toml` (pinned `>=6.10`, matches the project's >= cadence), updated `build-sidecar.sh` error message to point at `.[dev,serve,desktop]`. Each extra now has a header comment explaining WHEN/WHERE it's used (`apple`/`dev`/`serve`/`release`/`desktop`). (b) Xcode's "Run script build phase 'Copy Sidecar Resources' will be run during every build because it does not specify any outputs" warning fixed — declared the sidecar main binary as the dependency anchor; `ffmpeg`/`ffprobe`/`models` stay as conditional script side-effects. Bundle size 646 MB (vs. 644 MB on 18 Apr) — recorded for reference in `docs/private/qa-backlog.md`. The C0 "≤ 200 MB target" was a pre-scope guess; 646 MB is fine for an app that ships its own Python + LLM clients + transcription. Real slimming path is Background Assets / AVFoundation in the alpha→GA window, not now. Commits: `d886938` (extras + script docs), `d29c2c4` (pbxproj input/output paths). Bundled-mode UI launch screenshotted by user; foo's pre-existing "Transcription failed" surfaced cleanly via `PipelineRunner` (whisper-model deferred-download issue, not C1). C1 unblock for Track A1c stands — `sandbox-debug` can now rebase + re-walk against the bundled `.app`.

- **C2 — Sign every binary + notarise + Apple Distribution** ✅ code done 19 Apr 2026 (commits `fc95b99..cd04ee9` on `sidecar-signing`); end-to-end working 28 Apr 2026 (`1ee30eb`). `build-sidecar.sh` split into build-only + new `sign-sidecar.sh` (parallel `wait -n` bash job pool, `SIGN_JOBS=$(sysctl -n hw.ncpu)` default — not `xargs -P` which drops child exit codes on BSD). SHA256 sign-manifest emitted. `fetch-ffmpeg.sh` ported with FFmpeg 8.1 pin; new `sign-ffmpeg.sh` signs the two sibling binaries. `ExportOptions.plist` + pbxproj Release flipped to Manual signing against Apple Distribution cert + Bristlenose Mac App Store profile. **28 Apr structural fixes (`1ee30eb`):** `ExportOptions.plist` now declares both `signingCertificate` (Apple Distribution) AND `installerSigningCertificate` (`3rd Party Mac Developer Installer` = Mac Installer Distribution) — the latter signs the `.pkg` wrapper App Store Connect requires. `build-all.sh` falls back to the `.app` from xcarchive when `method=app-store` exports only a `.pkg`. Notarisation + stapling + spctl steps **skipped on the App-Store path** because `notarytool` only accepts Developer ID-signed binaries; App Store Connect validates server-side post-upload. `pkgutil --check-signature` replaces `spctl` for App Store flow. Distribution decision (28 Apr 2026): App Store only, Developer ID flow deferred until ~10k paying users — see private memory `project_developer_id_revisit.md`. `check-release-binary.sh` extended to scan for `get-task-allow=TRUE`. Notarytool credentials stored as `bristlenose-notary` keychain profile (preserved for the eventual Developer ID revisit, not used today). Canonical keychain partition-list incantation documented. Full session notes + resume-cold guide: `docs/private/c2-session-notes.md`.
- **C3 — Keychain in sandbox** ✅ code done 20 Apr 2026 (commits `a8dc3cb..ab1b2a1` on `sidecar-signing`). `ServeManager.overlayAPIKeys()` fetches LLM API keys from Keychain via `Security.framework` and injects `BRISTLENOSE_<PROVIDER>_API_KEY` env vars at subprocess launch. Python's `credentials_macos.py` unchanged behaviourally for CLI Mac distros (happy path still `/usr/bin/security` subprocess); exception handling broadened with `FileNotFoundError`/`PermissionError`/`OSError` + `logger.debug` so sandboxed-sidecar regressions surface as "No API key configured" rather than unhandled tracebacks. Runtime log redactor added (Anthropic / OpenAI / Google key shapes — Azure skipped; pre-beta re-audit tracked in 100days.md). Source-level CI gate `check-logging-hygiene.sh` wired into `build-all.sh` pre-flight. `KeychainHelper.hasAnyAPIKey()` fixed to iterate all providers (was Anthropic-only). Docs updated across `desktop/CLAUDE.md`, `SECURITY.md`, `design-desktop-python-runtime.md` + siblings. No-fork principle preserved. **Smoke test deferred to human** (Step 6 — Xcode GUI + throwaway Anthropic key). **Empty-ents retest split into its own plan** (`~/.claude/plans/c3-empty-ents-retest.md`), prerequisite SECURITY #5+#8.
  - **Post-hand-off smoke test (21 Apr 2026) uncovered three data-bundling bugs**, all fixed before this doc was trued up:
    - **BUG-3** (`5aae47c`) — React SPA `bristlenose/server/static/` missing from PyInstaller `datas`; sidecar silently served the deprecated static-render HTML. Fixed + fail-loud contract added: `_mount_prod_report` returns HTTP 500 with a clear error page when the React bundle is missing (`3a9bc6a`). Static render formally reframed as vestigial scaffolding (`66f4050`).
    - **BUG-4** + **BUG-5** (`08a0664`) — codebook YAMLs and llm/prompts missing from `datas`; Browse Codebooks empty + every LLM call raised `FileNotFoundError` before reaching the provider.
    - **BUG-6** (`673ddee`) — regression gate `check-bundle-manifest.sh` added as `build-all.sh` pre-flight step 2a. AST-parses the spec, walks `bristlenose/` for runtime-data dirs, fails closed on missing coverage.
    - Runtime self-check `bristlenose doctor --self-test` added (`52024f8`) so the sidecar can verify its own bundle integrity at deployment time.
  - **End-to-end archive UNBLOCKED 26 Apr 2026** — SECURITY #5 (`823f9be`, `38808fe`) and SECURITY #8 (`fdf90dc`, `92a1d36`) shipped, both `SecurityChecklist.swift` `#error` directives gone, Release archives compile. End-to-end build pipeline ran clean 28 Apr (`1ee30eb`). Empty-ents retest ran 28 Apr — **RED** (`8cfd2ee`): Python.framework's nested `_CodeSignature/` seal is the binding reason DLV stays; per-Mach-O resigning is necessary but not sufficient. DLV restored with empirical justification. Path forward (parked): treat Python.framework as a unit with `codesign --force` on the directory itself. Zombie cleanup also swapped to libproc (`5471b35`, `proc_listpids` + `proc_pidfdinfo`); whole supervisor path is now sandbox-friendly. Plan archived: `~/.claude/plans/next-track-security-5-and-8-unblocker.md`.
- **C4 — Privacy Manifest** ✅ **DONE 28 Apr 2026** (`765b111`, `f83faac`, `3a20f3a`, `f6c3170`).
  - Phase 1 triage: symbol sweep across 244 Mach-O files / 40,460 undefined symbols against Apple's four required-reason API families. Zero `NSUserDefaults`/`CFPreferences` hits in the sidecar (pure Python). FileTimestamp / DiskSpace / SystemBootTime found across 17 packages. Per-package sub-manifest approach abandoned in favour of one bundle-root manifest per signing scope — Apple's bar is API-category coverage, not per-vendored-library, and none of our deps are on Apple's named hard-rejection SDK list (Firebase/Adjust/Branch/etc.).
  - Phase 2 shipped: host manifest augmented (CA92.1, C617.1+DDA9.1, E174.1, 35F9.1) covering FFmpeg at `Contents/Resources/`. New sidecar manifest at `Contents/Resources/bristlenose-sidecar/PrivacyInfo.xcprivacy` (DDA9.1, E174.1, 35F9.1) covering bundled Python + 222 `.so` files. Build wired through `desktop/scripts/build-sidecar.sh` (cp post-PyInstaller) + `desktop/scripts/build-all.sh` step [f] (find + plutil -lint assertion).
  - Reviewed: app-store-police + security-review (Checkpoint #2, fixes in `f83faac` — split FileTimestamp reason codes, dropped onnxruntime callout, added not-for-fingerprinting note); code-review + what-would-gruber-say (Checkpoint #3, fixes in `3a20f3a`+`f6c3170` — comment-to-data ratio trimmed, positioning copy stripped from manifest comments).
  - Build-all end-to-end ran exit 0 on 28 Apr; `Bristlenose.pkg` ready for App Store Connect upload (Track B).
  - Bundle slimming (excluding orphan `onnxruntime`/`watchfiles`/`uvloop`) deferred — alpha-first, not a TestFlight blocker.
- **C5 — Supply-chain provenance** ✅ **DONE 28 Apr 2026**. `THIRD-PARTY-BINARIES.md` at repo root: hand-curated rows for FFmpeg/ffprobe (SHA256 from `fetch-ffmpeg.sh`) + Python.framework + PyInstaller bootloader; auto-generated Python-wheel section (105 rows, regenerated by `scripts/generate-third-party-binaries.py` from the venv minus spec excludes); first-run downloads (Whisper via HF Hub built-in SHA chain); CVE-monitoring cadence (Dependabot for Python, FFmpeg mailing list for native, quarterly manual review). Deferred + honestly-disclosed: wheel hash pinning (deferred until `uv` migration) + CycloneDX SBOM (will add if asked). `pip-licenses` added to a new `[release]` optional-dependency group. Cross-references in SECURITY.md "Code signing and runtime hardening" + design-desktop-python-runtime.md §"Supply-chain provenance (C5)".

**Branch:** `sidecar-signing` (current worktree — scope extended from original three-sentence version)

**Won't do in Track C:** Developer ID / `.dmg` pipeline (deferred per road-to-alpha — revisit at ~10k paying users or first enterprise MDM ask); CI upload job (#11); actual TestFlight upload (#12); App Store Connect app record (#10). These belong to Track B and land whenever the schedule allows — S6 was a provisional bucket, not a commitment.

**Deferred to public-beta polish pass (post-alpha, before 100-days):**
- Native SwiftUI splash window during sidecar boot (alpha can cope with 3–6 s blank WKWebView; paying users can't).
- "Manage downloaded content" Settings panel (storage view, per-asset delete) — needs Background Assets to be live first.
- Upgrade prompts when Apple-Hosted asset packs publish a new version (e.g. better Whisper model).
- Per-asset retry / cancel UI for failed Background Assets downloads.
- First-run "we'll trickle additional capability over the next hour" sheet.

The split is deliberate: alpha proves the architecture works with 5 friends; public beta polishes the UX for evaluators. Don't pull beta polish into Track C — it'll bloat alpha.

**C0 first move:** build v0.1 sidecar fresh, `codesign -o runtime`, run, record every entitlement violation. Populate entitlement table in `design-desktop-python-runtime.md`.

## Track interaction matrix

| | A touches | B touches | C touches |
|---|---|---|---|
| **A** | — | Low: `ServeManager.swift` overlap if both touch sidecar spawn | Low: `.entitlements` path — C consumes, A authors |
| **B** | (above) | — | Zero |
| **C** | (above) | Zero | — |

The only real conflict risk is `ServeManager.swift` if A's sandbox-aware spawn lands at the same time as a B beat that changes the pipeline trigger. Coordinate via PR sequencing if both are open simultaneously.

## Convergence point

The first TestFlight upload (road-to-alpha #12) needs all three tracks landed:

1. **A** lands → entitlements file exists, sandbox passes locally
2. **C** swaps ad-hoc signing for Apple Distribution → produces uploadable `.pkg`
3. **B** is "share-ready" → upload makes sense

Until that point, A, B, and C ship independently to `main`. None blocks the others.

## Out of scope for all three tracks

These belong to S6 (per `100days.md` and `road-to-alpha.md` §14):

- App Store Connect app record (#10)
- Privacy Nutrition Labels (#7)
- Export compliance form (#9)
- First manual upload (#12)
- Internal TestFlight rollout (#13)
- External TestFlight / full App Store review (#14)
- Hosted privacy policy URL, ToS, EULA, solicitor sign-off

Also out of scope and parked elsewhere:
- CI cleanup (separate session, not a track here)
- Developer ID cert + `.dmg` pipeline (deferred — see road-to-alpha §"Decision")

## Branch hygiene

- Each branch lives in its own worktree (`/Users/cassio/Code/bristlenose_branch <name>`). Use `/new-feature <name>`.
- Each branch keeps changes minimal — don't refactor adjacent code.
- Reference this doc in commit messages when scope is non-obvious: "track A: sandbox-aware ServeManager spawn (see sprint2-tracks.md)".
- When a track's branch lands, update its row in the convergence checklist below.

## Convergence checklist

- [ ] Track A: sandbox enabled in Debug, MVP flow runs without violations, entitlements file finalised
- [ ] Track A: Apple Distribution cert + provisioning profile in place (#2)
- [x] Track C: `sign-sidecar.sh` produces a runnable ad-hoc-signed bundle (C2 code done, `fc95b99..cd04ee9`)
- [x] Track C: same script swapped to Apple Distribution, produces uploadable `.pkg` (C2 code done; ~~end-to-end `xcodebuild archive` blocked by SECURITY #5+#8~~ — unblocked 26 Apr 2026; end-to-end run clean 28 Apr 2026 via `1ee30eb` — adds Mac Installer Distribution cert + `installerSigningCertificate` + skips notarytool/spctl on the App-Store path)
- [x] Track C: Keychain credential injection wired, sandbox-compatible (C3, `a8dc3cb..ab1b2a1`; smoke test Step 6 pending human)
- [x] Track C: bundle-data coverage enforced (C3, BUG-6 `673ddee`); fail-loud on missing React bundle (`3a9bc6a`); runtime self-check (`52024f8`)
- [x] ~~**PREREQUISITE**: fix SECURITY #5 + #8 in `SecurityChecklist.swift`~~ ✅ **Done 26 Apr 2026** on `sidecar-signing` (commits `823f9be..38808fe`). #5: `proc_pidpath` PID verification (libproc, sandbox-friendly). #8: port-restricted nav policy + `NSWorkspace.open` allowlist. Release archives now compile. ~~End-to-end `build-all.sh` run + empty-ents retest still pending~~ — both done 28 Apr 2026: end-to-end build clean (`1ee30eb`), empty-ents retest RED (`8cfd2ee`, DLV stays — Python.framework nested seal). Lsof zombie-cleanup also libproc-only now (`5471b35`).
- [ ] Track B: §1a clean-profile walkthrough completes end-to-end without apology
- [ ] Promote to S6 work (#10, #12) → first upload

## Post-alpha pickups

After the first internal-TestFlight cohort reports back, pick up work that was deferred from S2 to keep the TestFlight runway clear:

- **Alpha telemetry Phases 2–4** — Phase 1 plumbing landed 26 Apr 2026 (`alpha-telemetry` branch, merge `c5a7f61`). Remaining: Python event API + SQLite buffer + shipper + prompt-version sidecar, React emission hook, Swift opt-in sheet + Keychain UUID + Settings → Privacy. Full prompt: `docs/private/alpha-telemetry-next-session-prompt.md`. Tracked in `road-to-alpha.md` §13b and `100days.md` §1 Must.
