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

### Track C — Codesigning infrastructure

Road-to-alpha checkpoints **#4** (PyInstaller sidecar signing) and **#5** (Hardened Runtime entitlements — "comes with 4" per the doc).

Mechanical. Binary pass/fail success criterion. Claude can drive end-to-end with ad-hoc signing locally; human validates when it produces a runnable bundle.

**Scope cut:** one branch, `sidecar-signing`. Covers:
- `scripts/sign-sidecar.sh` (or `.py`) — `find` → per-binary `codesign --force --timestamp --options=runtime --sign …` loop, innermost first, then outer `.app` sign
- `desktop/Bristlenose/ExportOptions.plist` — for `xcodebuild -exportArchive`
- Hardened Runtime flag plumbing (`com.apple.security.cs.allow-unsigned-executable-memory`, `disable-library-validation`, `allow-jit` as required)
- Ad-hoc signing fallback (`--sign -`) for local dev before A delivers Apple Distribution cert
- Signing identity parameterised via env var (`SIGN_IDENTITY="Apple Distribution: …"` or `-`)
- Possibly `desktop/build-sidecar.sh` if one exists

**Won't put in this branch:**
- Contents of the entitlements file (A's output — C just references the path)
- CI upload job (#11 / S6)
- Actual TestFlight upload (#12 — needs real cert + finalised entitlements)

**Won't touch:** any Python source, any frontend, any server route.

**C1 first move:** inventory the current PyInstaller bundle (count signable binaries, list dylib/so/framework patterns), write the loop, iterate locally with ad-hoc signing until the bundle launches and runs.

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
