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
1. `sandbox-debug` — flip sandbox in Debug scheme, exercise MVP flow, produce violation log. No fixes.
2. Per-Python-migration narrow branches as the violation log dictates (`credentials-security-framework`, `ollama-http`, `bundled-binary-helper`, etc.).

**Won't touch:** PyInstaller signing script, frontend, server route handlers (other than subprocess audit).

**A1 first move:** sandbox on in Debug, walk §1a, log every `deny(1) …`. Output: a ranked violation list in this directory (e.g. `sandbox-violations-A1.md`).

### Track B — MVP UX flow

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

(Beats 2, 11, 12 already shipped — see §1a in `100days.md`.)

**B1 first move:** clean-profile walkthrough on the current build to identify the first broken beat. Clean profile = wipe `~/Library/Application Support/Bristlenose` + Keychain entries, no Claude key set.

### Track C — Sidecar bundling + signing (re-scoped 18 Apr 2026)

**Re-scoped.** Original Track C assumed the desktop app already bundled a Python sidecar that just needed codesigning. It doesn't — v0.2 is a launcher-style dev shell (`ServeManager.findBristlenoseBinary()`) that was never intended to ship. Real Track C covers resurrecting the bundling pipeline from v0.1, signing it, and wiring in all the Mac App Store prerequisites. See the implementation plan in `~/.claude/plans/when-you-have-done-encapsulated-conway.md`.

**Canonical design references:**
- [`docs/design-modularity.md`](../design-modularity.md) — **what** goes where (Python deps, extras, Background Assets, cross-channel decisions). The no-fork principle lives here.
- `docs/design-desktop-python-runtime.md` (to be written in C0) — **how** the Mac sidecar specifically works (ServeManager, entitlements, Privacy Manifest, codesign chain).

**Sub-scopes (own branch each or narrow sequence):**

- **C0 — Entitlement spike** ✅ done 18 Apr 2026 (commit `7d121fa`). Minimum set empirically reduced to one key (`cs.disable-library-validation`); v0.1's `allow-unsigned-executable-memory` and `allow-jit` both proved unnecessary. Bundle landed at 644 MB (target ≤ 200 MB) — torch/llvmlite/onnxruntime/scipy transitive pulls flagged for C1 excludes pass. See `docs/design-desktop-python-runtime.md`.
- **C1 — Resurrect bundling pipeline, scoped to `serve`** ✅ done 18 Apr 2026. Ported `desktop/v0.1-archive/` forward: PyInstaller spec at `desktop/bristlenose-sidecar.spec`, build script at `desktop/scripts/build-sidecar.sh` (parameterised `SIGN_IDENTITY`, auto-picked `TIMESTAMP_FLAG`, post-sign strict verify + outer `--verify --deep --strict`), output lands at `desktop/Bristlenose/Resources/bristlenose-sidecar/` for Xcode's Copy Sidecar Resources phase. **Dev escape hatch consolidation done:** `findBristlenoseBinary()`'s silent 5-path search replaced with pure `SidecarMode.resolve(externalPortRaw:sidecarPathRaw:bundleResourceURL:fileManager:)`; two explicit Debug-only env vars (`BRISTLENOSE_DEV_EXTERNAL_PORT`, `BRISTLENOSE_DEV_SIDECAR_PATH`); three shared Xcode schemes wrap them; `os.Logger(subsystem: "app.bristlenose", category: "serve")` replaces `print()`. Post-archive `desktop/scripts/check-release-binary.sh` asserts dev env-var literals are absent from Release Mach-Os (defence-in-depth moved forward from C2; script scans every Swift-shell Mach-O in the bundle, skips the Python sidecar). **Size trim + lazy-import work deferred** per `design-modularity.md` §"trickle to full capability" — Background Assets is the post-install story, not build-time trimming.
- **C2 — Sign every binary + notarise + Apple Distribution** ✅ code done 19 Apr 2026 (commits `fc95b99..cd04ee9` on `sidecar-signing`). `build-sidecar.sh` split into build-only + new `sign-sidecar.sh` (parallel `wait -n` bash job pool, `SIGN_JOBS=$(sysctl -n hw.ncpu)` default — not `xargs -P` which drops child exit codes on BSD). SHA256 sign-manifest emitted. `fetch-ffmpeg.sh` ported with FFmpeg 8.1 pin; new `sign-ffmpeg.sh` signs the two sibling binaries. `ExportOptions.plist` + pbxproj Release flipped to Manual signing against Apple Distribution cert + Bristlenose Mac App Store profile. Full `build-all.sh` orchestrator: pre-flight → parallel fetch+build → sign → archive → export → strings/`get-task-allow` gate → embedded profile sanity check → `notarytool submit --wait` + stapler → final verification battery. `check-release-binary.sh` extended to scan for `get-task-allow=TRUE`. Notarytool credentials stored as `bristlenose-notary` keychain profile. Canonical keychain partition-list incantation documented. **End-to-end run parked** — `xcodebuild archive` fails on pre-existing `#error` directives in `SecurityChecklist.swift` (SECURITY #5 + #8 — unrelated to signing). Those now unblock both C2 verification and C3. Full session notes + resume-cold guide: `docs/private/c2-session-notes.md`.
- **C3 — Keychain in sandbox** ✅ code done 20 Apr 2026 (commits `a8dc3cb..ab1b2a1` on `sidecar-signing`). `ServeManager.overlayAPIKeys()` fetches LLM API keys from Keychain via `Security.framework` and injects `BRISTLENOSE_<PROVIDER>_API_KEY` env vars at subprocess launch. Python's `credentials_macos.py` unchanged behaviourally for CLI Mac distros (happy path still `/usr/bin/security` subprocess); exception handling broadened with `FileNotFoundError`/`PermissionError`/`OSError` + `logger.debug` so sandboxed-sidecar regressions surface as "No API key configured" rather than unhandled tracebacks. Runtime log redactor added (Anthropic / OpenAI / Google key shapes — Azure skipped; pre-beta re-audit tracked in 100days.md). Source-level CI gate `check-logging-hygiene.sh` wired into `build-all.sh` pre-flight. `KeychainHelper.hasAnyAPIKey()` fixed to iterate all providers (was Anthropic-only). Docs updated across `desktop/CLAUDE.md`, `SECURITY.md`, `design-desktop-python-runtime.md` + siblings. No-fork principle preserved. **Smoke test deferred to human** (Step 6 — Xcode GUI + throwaway Anthropic key). **Empty-ents retest split into its own plan** (`~/.claude/plans/c3-empty-ents-retest.md`), prerequisite SECURITY #5+#8.
- **C4 — Privacy Manifest** (~1–2 days — revised up from ~½ day after C3 scoping). Host manifest drafted at `desktop/Bristlenose/Bristlenose/PrivacyInfo.xcprivacy` (tracked as of C3). Sidecar + Python.framework + 222 `.so` files need triage + sub-manifests. FFmpeg manifest too. Full plan at `~/.claude/plans/c4-privacy-manifests.md`.
- **C5 — Supply-chain provenance** (~½ day). SHA256-pin FFmpeg/Whisper URLs, `THIRD-PARTY-BINARIES.md`, CVE-monitoring note.

**Branch:** `sidecar-signing` (current worktree — scope extended from original three-sentence version)

**Won't do in Track C:** Developer ID / `.dmg` pipeline (rejected per road-to-alpha); CI upload job (#11); actual TestFlight upload (#12); App Store Connect app record (#10). These belong to Track B and land whenever the schedule allows — S6 was a provisional bucket, not a commitment.

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
- Developer ID cert + `.dmg` pipeline (rejected — see road-to-alpha §"Decision")

## Branch hygiene

- Each branch lives in its own worktree (`/Users/cassio/Code/bristlenose_branch <name>`). Use `/new-feature <name>`.
- Each branch keeps changes minimal — don't refactor adjacent code.
- Reference this doc in commit messages when scope is non-obvious: "track A: sandbox-aware ServeManager spawn (see sprint2-tracks.md)".
- When a track's branch lands, update its row in the convergence checklist below.

## Convergence checklist

- [ ] Track A: sandbox enabled in Debug, MVP flow runs without violations, entitlements file finalised
- [ ] Track A: Apple Distribution cert + provisioning profile in place (#2)
- [ ] Track C: `sign-sidecar.sh` produces a runnable ad-hoc-signed bundle
- [ ] Track C: same script swapped to Apple Distribution, produces uploadable `.pkg`
- [ ] Track B: §1a clean-profile walkthrough completes end-to-end without apology
- [ ] Promote to S6 work (#10, #12) → first upload
