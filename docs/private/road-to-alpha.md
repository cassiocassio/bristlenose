# Road to Alpha

Single source of truth for getting Bristlenose into friends' hands via **internal TestFlight**. Covers the full path: Apple Developer Program → sandbox → signing → Privacy Manifest → App Store Connect upload → TestFlight rollout. Gathers facts that are otherwise scattered across `docs/design-desktop-distribution.md`, `docs/design-desktop-security-audit.md`, `docs/design-homebrew-packaging.md`, `docs/private/launch-docs/`, `docs/private/infrastructure-and-identity.md`, and `docs/private/testflight-alpha-path.md`.

Alpha = sharing a signed sandboxed build with ~5 UXR friends via TestFlight internal testers (no Beta App Review). This doc doesn't cover external TestFlight or full App Store submission — those are S6+ and captured in `100days.md`.

_Written 17 Apr 2026 as part of Sprint 2 planning. Last updated 29 Apr 2026 (truing pass — Track C C2–C5 closed 28 Apr; Tracks A + B in flight on `sandbox-debug` and `first-run` worktrees from 29 Apr; Sprint 2 homework items 2/4/5/6/8/9 are ✅, only #3 sandbox + #11 CI remain S2; domain typo `bristlenose.research/privacy` → `bristlenose.app/privacy`). Earlier: 18 Apr 2026 (evening) — C0 spike completed, §5 reduced to one load-bearing entitlement. Update when facts change._

## Status (18 Apr 2026)

**v0.2 currently uses a launcher pattern, not a bundled sidecar.** The desktop app (`ServeManager.findBristlenoseBinary()`) finds an installed CLI on the user's machine — deliberate dev scaffolding so v0.2's native shell could iterate cheaply on Martin's laptop. Alpha resurrects the v0.1 bundling pipeline (now in `desktop/v0.1-archive/`), scoped to `bristlenose serve` rather than `bristlenose run`. Track C in `docs/private/sprint2-tracks.md` carries the work (C0 entitlement spike → C5 supply-chain pinning).

The 14 checkpoints below are correct as written. Cross-channel component decisions (what's bundled, what's downloaded via Background Assets, what's CLI-only) live in [`docs/design-modularity.md`](../design-modularity.md). Mac-specific sidecar mechanics will land in `docs/design-desktop-python-runtime.md` once C0 produces the entitlement table.

## Decision: TestFlight is the alpha path (17 Apr 2026)

**Choice:** ship the alpha to ~5 friends via **internal TestFlight**, not via `.dmg`.

**Reasoning:**
1. **Sandbox is unavoidable.** StoreKit subscriptions + in-app purchases for LLM tokens are required for v1.0 revenue. StoreKit requires App Store distribution, which requires sandbox. Skipping sandbox for an interim `.dmg` path just delays the work and creates throwaway code.
2. **Building our own store is worse.** If we skip App Store and run subscriptions ourselves, we inherit payment processing, tax compliance (UK VAT, EU VAT MOSS, US sales tax per state), receipt validation, refund handling, chargebacks, and the trust problem of "why would I give my credit card to a small indie dev?" Apple's 15% cut buys us all of that plus discoverability.
3. **Modern codebase from the start.** Sandbox-aware code paths (security-scoped bookmarks, sandbox-respecting temp files, child-process entitlement inheritance, Keychain via Security framework) are the correct architecture regardless of distribution channel. Doing them now means no legacy cleanup pass later.
4. **Interleave A/B cadence.** Sandbox step → UI step → sandbox step. Mixing keeps momentum and surfaces integration issues early — e.g. a folder-picker bookmark regression would otherwise be invisible until weeks later.

**Consequence:** the `.dmg` / Developer ID path is **deferred, not rejected** (decision sharpened 28 Apr 2026). Trigger to revisit: ~10k paying users where the App Store cut becomes material relative to the cost of running a parallel direct-distribution channel, OR first enterprise MDM ask. Items tagged S6 in `100days.md` that reference `.dmg` should be reframed as deferred-not-rejected. `docs/design-desktop-distribution.md` is now archived (`docs/archive/design-desktop-distribution.md`); the active sidecar-signing flow lives in `docs/design-desktop-python-runtime.md`.

## Why this path exists

The Mac app has two possible distribution channels:

| Channel | Where | Signing | Review | Audience |
|---|---|---|---|---|
| `.dmg` outside the store | GitHub Releases, bristlenose.app | **Developer ID** + notarisation | None | Anyone who can click a link |
| App Store Connect (TestFlight + App Store) | Apple servers | **Apple Distribution** + provisioning profile | TestFlight internal: none<br>TestFlight external: Beta App Review<br>App Store: full review | Apple ID users with the invite/link |

Different certificates. Different entitlements. Different review paths. Not interchangeable.

**The road described here is App Store Connect only.** For the `.dmg` path, see `design-desktop-distribution.md`.

## The 14 checkpoints, in order

### 1. Apple Developer Program membership ✅ DONE

- Individual enrollment, Martin Storey, Team ID `Z56GZVA2QB`
- Bundle ID: `app.bristlenose`
- Activated 16 Apr 2026, expires 16 Apr 2027
- Renewal reminder in `docs/private/succession-plan.md`

### 2. Apple Distribution + Mac Installer Distribution certs + provisioning profile ✅ DONE

- **Apple Distribution** cert installed under Team ID `Z56GZVA2QB` — signs every Mach-O in the `.app` bundle
- **Mac Installer Distribution** cert (Apple displays this as "3rd Party Mac Developer Installer" in `security find-identity` output — same cert family) installed 28 Apr 2026 — signs the `.pkg` wrapper that App Store Connect requires for Mac apps
- **Bristlenose Mac App Store** provisioning profile linked to bundle ID `app.bristlenose`
- Different from Developer ID. All three coexist in login Keychain
- `ExportOptions.plist` declares both certs (`signingCertificate` + `installerSigningCertificate`); see `desktop/Bristlenose/ExportOptions.plist` for the canonical config
- Both certs need `.p12` USB backup per cert-rotation reminder

### 3. App sandbox + entitlements 🟡 IN PROGRESS

Required for App Store Connect upload (TestFlight or App Store). Not required for `.dmg`.

**C0 spike completed 18 Apr 2026 (`7d121fa`, `8bd6883`).** The minimum entitlement set for **Hardened Runtime** was empirically determined — one key only (`com.apple.security.cs.disable-library-validation`). The pre-spike guess below was mostly wrong: `allow-unsigned-executable-memory` and `allow-jit` are not required. See `design-desktop-python-runtime.md` §"Entitlement table" for the empirical truth and §"How this was determined" for the test rig.

**Track A progress (1 May 2026):** Debug-only sandbox-on landed empirically across three narrow branches —
- **A1** (29 Apr, `cd4a5c6` on `sandbox-debug`): `app-sandbox` + `network.client` + `files.user-selected.read-write` (host); `inherit` (sidecar). SSB bookmark XPC deny cleared.
- **A1c** (30 Apr, `3f82ede`): bundled-sidecar spawn under inherited sandbox verified. `network-bind 9131` deny surfaced as next blocker.
- **A2** (1 May, `49cb600` on `track-a-a2-network-server`): `network.server` granted via `ENABLE_INCOMING_NETWORK_CONNECTIONS = YES`. Bind succeeds; app reaches welcome view.
- **Helper:** `desktop/scripts/reset-sandbox-state.sh` (`ff96766` / `ff57801` / `730367d`) — wipes Container + UserDefaults between iterations to recover from `EXC_BREAKPOINT` in `_libsecinit_appsandbox`. Documented in `desktop/CLAUDE.md` "Sandbox iteration".

**Empirical entitlement set (post-A2):**
- Host (Debug only, build-setting-driven in `Bristlenose.xcodeproj/project.pbxproj` — no separate `.entitlements` file):
  - `com.apple.security.app-sandbox` (`ENABLE_APP_SANDBOX = YES`)
  - `com.apple.security.network.client` (`ENABLE_OUTGOING_NETWORK_CONNECTIONS = YES`)
  - `com.apple.security.network.server` (`ENABLE_INCOMING_NETWORK_CONNECTIONS = YES`)
  - `com.apple.security.files.user-selected.read-write` (`ENABLE_USER_SELECTED_FILES = readwrite`)
- Sidecar (always, in `desktop/bristlenose-sidecar.entitlements`):
  - `com.apple.security.cs.disable-library-validation`
  - `com.apple.security.inherit`
- **Not needed** (pre-spike guess overruled): `files.bookmarks.app-scope` — `files.user-selected.read-write` alone covers the SSB XPC bootstrap.

**Still pending under sandbox-on:**
- A4/A6 — beats 6+ (pipeline run, FFmpeg subprocess, Whisper download, doctor probes). Beat 6 is also blocked by an unrelated stale code path: `PipelineRunner.findBristlenoseBinary()` was not migrated to `SidecarMode.resolve()` when C1 landed (TODO comment in source).
- Release config sandbox flip (`ENABLE_APP_SANDBOX = NO` in Release).
- `proc_listpids` returns EPERM under sandbox — zombie-cleanup-on-launch is silently a no-op. Fine for normal flow, breaks crash recovery. Defer until post-alpha.

**Pre-spike entitlement guess (preserved as historical baseline — DO NOT treat as current):**
- ~~`com.apple.security.app-sandbox` (true)~~ → ✅ confirmed required (above)
- ~~`com.apple.security.files.user-selected.read-write`~~ → ✅ confirmed required
- ~~`com.apple.security.files.bookmarks.app-scope`~~ → ❌ not needed (subsumed by user-selected.read-write)
- ~~`com.apple.security.network.client`~~ → ✅ confirmed required
- ~~`com.apple.security.network.server`~~ → ✅ confirmed required (A2 verified bind on 9131; comment said `:8150` but actual port is computed per project, default range `8150-9149`)
- ~~`com.apple.security.inherit` on the Python sidecar~~ → ✅ confirmed required (sidecar-side entitlement file)

**Hard parts for this app specifically:**
- **Python sidecar subprocess** must inherit sandbox. `ServeManager.swift` is the current spawn point (old `ProcessRunner.swift` lives in `desktop/v0.1-archive/`). Breakdown:
  - **Swift → Python spawn** — Swift parent has `com.apple.security.app-sandbox`. The Python sidecar binary needs its own `.entitlements` file at signing time declaring `com.apple.security.inherit = true` (and nothing else). That tells macOS "this child inherits the parent's sandbox; do not evaluate my entitlements separately." Without it the child either runs unsandboxed (rejected at review) or is denied resources the parent granted
  - **Posix_spawn, not fork** — sandbox inheritance works cleanly with `posix_spawn` and `execve`. `Process` (NSTask) uses `posix_spawn` under the hood, so standard Swift code is fine. Watch for any Python code using `os.fork()` directly (grep'd: none currently)
  - **Python → third-party binary spawns** — 14 files in `bristlenose/` call `subprocess.*`. Every binary spawned needs to either be (a) bundled + signed + have its own `inherit` entitlement, or (b) a system binary the sandbox lets us reach. Audit targets:
    - `bristlenose/stages/s02_extract_audio.py` — FFmpeg (bundled)
    - `bristlenose/utils/video.py` — FFmpeg frame extraction (bundled)
    - `bristlenose/utils/audio.py` — ffprobe (bundled)
    - `bristlenose/server/clip_backend.py` + `server/clip_manifest.py` + `server/routes/clips_export.py` — FFmpeg stream-copy for clip export (bundled)
    - `bristlenose/ollama.py` — spawns `ollama` binary (NOT bundled; user-installed). Sandbox will block reaching `/usr/local/bin/ollama` or `~/bin/ollama`. Options: document Ollama-unavailable in sandboxed builds, or use `ollama serve`'s HTTP API instead of CLI (cleaner, already supported by Ollama)
    - `bristlenose/credentials_macos.py` — `/usr/bin/security` CLI. Sandbox blocks this. **Must migrate to Security framework** via Swift bridge or a Python binding (separate S2 item). Same migration already done Swift-side
    - `bristlenose/doctor.py` + `doctor_fixes.py` — runtime health checks spawn `which`, maybe `ffprobe --version`. Audit whether doctor is even meaningful in a sandboxed context; may need a desktop-specific code path
    - `bristlenose/utils/hardware.py` — reads hardware info (probably `sysctl` or similar). Some paths allowed, some not
    - `bristlenose/cli.py` — CLI entry point, may fork for pipeline stages. Audit
  - **Bundled binary paths** — current code may use `shutil.which("ffmpeg")` which resolves against `$PATH`. In the `.app`, FFmpeg lives at `Contents/Resources/bin/ffmpeg` (or similar). Sidecar needs a `bundled_binary_path()` helper that prefers bundle-relative paths when running inside the `.app`, falls back to `shutil.which()` for CLI users. One source of truth, not sprinkled
  - **Grandchild entitlements** — FFmpeg launched by Python launched by Swift is a grandchild. Each hop needs `inherit` set at its own signing time. Signing script must cover: Python binary, FFmpeg, ffprobe, any other bundled executables
  - **File descriptor passing** — if Swift pre-opens a file and hands its fd to the sidecar, the sidecar can read it even without direct filesystem access. Useful for user-picked folders where we'd rather hand over access than ask the sidecar to consume a bookmark. Worth considering for drag-and-drop flow
  - **Stdio piping** — `Process.standardOutput` / `standardError` use pipes, work fine across sandbox boundary. Existing CLI output streaming via FastAPI SSE should survive unchanged
  - **Kill / signal handling** — parent sends `SIGTERM` to sidecar on app quit. Sandbox allows signalling own children. No change needed, but zombie cleanup (the port-scan orphan killer) may need adjustment — `kill(pid, 0)` to check process existence may fail for processes started by a previous (crashed) instance of our app, since those aren't our children
- **FFmpeg + ffprobe** inside the sidecar bundle need the same treatment for alpha — individually codesigned with `--options=runtime`, their own minimal `inherit` entitlement. **Post-100-days direction: use AVFoundation to build Mac-native video features competitors can't match.** Skate to where the puck is going — frame-accurate clip in/out, hardware-decoded scrubbing, colour-accurate thumbnails, ProRes, GPU transforms. Bristlenose is text-first and video is supporting, so this is bounded in scope, but the framing is forward-leaning product vision, not defensive bug fixes. CLI feature-parity is an explicit anti-goal — being Mac-first-class is the point. `ClipBackend` Protocol is scaffolded for this. Alpha plan unchanged: sign FFmpeg, ship it
- **Keychain access** — solved differently than originally planned. Swift host fetches keys via Security.framework and injects them as `BRISTLENOSE_*_API_KEY` env vars at sidecar launch (Track C C3, Apr 2026). Python's `credentials_macos.py` is unchanged for CLI Mac users; the sandboxed sidecar never reaches it because env vars satisfy the credential lookup chain earlier. No Python-side Keychain migration needed.
- **Temp files** — sandbox redirects `$TMPDIR` to a container-specific path. PyInstaller, ffmpeg temp usage, whisper caches all need to respect it
- **User-picked folders** — sandboxed app cannot traverse arbitrary paths. Need security-scoped bookmarks for every user-chosen folder persisted across launches

**Test first without uploading:** enable sandbox in Xcode, run locally, exercise every pipeline stage, watch Console for sandbox violations (`deny(1) file-read-data /some/path`).

Related: `docs/design-desktop-security-audit.md`, `bristlenose/credentials_macos.py`.

### 4. PyInstaller sidecar signing ⬜ BIG SCRIPT

Every `.dylib`, `.so`, and framework inside the PyInstaller bundle must be **individually** codesigned before notarisation. PyInstaller bundles routinely contain 100+ such files. Trimmed per `docs/design-modularity.md` — MLX-only (no ctranslate2), presidio excluded from the sidecar bundle for public beta (bundled inline for alpha), FFmpeg trimmed codecs. Target bundle size ≤ 200 MB before Whisper.

- Build script (`desktop/scripts/sign-sidecar.sh`, Track C C2, shipped `fc95b99..cd04ee9`): `find` every signable binary → `codesign --force --timestamp --options=runtime --sign …` each one → then sign the outer `.app`. Split from `build-sidecar.sh` so build and sign can parallelise independently.
- **Parallelise via bash `wait -n` job pool** (not `xargs -P`, which drops child exit codes on BSD — a failed codesign would be masked in interleaved stderr). Default `SIGN_JOBS=$(sysctl -n hw.ncpu)`. Per-binary `--timestamp` contacts Apple's TSA server; sequential = 8–20 min in CI, parallel = 1–3 min. Requires bash 4.3+ (Apple's default `/bin/bash` is 3.2; Homebrew bash in `$PATH`).
- Identity parameterised via `SIGN_IDENTITY` env var (`-` for ad-hoc local iteration; "Apple Distribution: …" for TestFlight).
- `--options=runtime` enables Hardened Runtime (required for notarisation and App Store)
- Entitlements file passed via `--entitlements` during final app sign
- Ordering matters: sign innermost first, outermost last
- **CI trigger (decided 18 Apr 2026):** tag push only (`on: push: tags: ['v*']`). Tag cadence is ~1 every 2.7 days — regression detection lag under 3 days, CI cost bounded. **End-to-end `build-all.sh` working locally as of 28 Apr 2026 (`1ee30eb`):** Mac Installer Distribution cert added (`installerSigningCertificate` in ExportOptions.plist signs the `.pkg` wrapper); `xcodebuild -exportArchive` falls back to the `.app` from xcarchive when `method=app-store` exports only a `.pkg`; notarisation + stapling + `spctl` are method-conditional skips because notarytool only accepts Developer ID, not Apple Distribution — App Store Connect validates server-side after upload, replaced locally by `pkgutil --check-signature` on the `.pkg`. CI wiring still pending. Empty-ents retest ran 28 Apr — RED (`8cfd2ee`): Python.framework's nested `_CodeSignature/` seal is the binding reason DLV stays. Lsof zombie-cleanup also libproc-only now (`5471b35`).

Reference: `docs/design-homebrew-packaging.md` uses `post_install` pip to avoid dylib relinking. Different problem but related context.

### 5. Hardened Runtime + associated entitlements ⬜ C0 SPIKE DONE (18 Apr 2026)

Enabled via `--options=runtime` at signing time. **Actual set determined empirically in Track C C0** (see [`docs/design-desktop-python-runtime.md`](../design-desktop-python-runtime.md)):

- ✅ `com.apple.security.cs.disable-library-validation` — **required**. PyInstaller ships Python.framework + 100+ `.so` files with a different (or absent) Team ID from the outer binary; library validation blocks dlopen without this key.
- ❌ `com.apple.security.cs.allow-unsigned-executable-memory` — **NOT required**. CPython 3.12 doesn't use W+X memory for normal bytecode execution. Confirmed by running the trimmed sidecar with only `disable-library-validation` set; server started and served HTTP normally. v0.1's inclusion was defensive, not load-bearing.
- ❌ `com.apple.security.cs.allow-jit` — **NOT required**. ctranslate2 is excluded from the sidecar per `design-modularity.md`; MLX runs on Metal GPU kernels, not CPU JIT.

**One entitlement total.** Each absent key is one fewer App Review justification. Full rationale and test methodology in `design-desktop-python-runtime.md` §"Entitlement table".

**Open:** mlx-whisper wasn't exercised in C0 (spike was `bristlenose serve` bring-up only). If actual inference needs an extra runtime-allow key at model-load time, it'll surface in C1 when the integration test harness runs a real clip through. Revisit this checkmark if so.

### 6. Privacy Manifest audit ✅ DONE

Host-app manifest shipped 19 Apr 2026: `desktop/Bristlenose/Bristlenose/PrivacyInfo.xcprivacy`. Sidecar-bundle manifest shipped 28 Apr 2026 as Track C C4 (`765b111`..`f6c3170`).

Coverage:
- Host (`Contents/Resources/PrivacyInfo.xcprivacy`): CA92.1 (UserDefaults — `@AppStorage`), C617.1 + DDA9.1 (FileTimestamp — sidebar "last opened" + FFmpeg source-mtime reads), E174.1 (DiskSpace — FFmpeg statfs), 35F9.1 (SystemBootTime — FFmpeg `mach_absolute_time`).
- Sidecar (`Contents/Resources/bristlenose-sidecar/PrivacyInfo.xcprivacy`): DDA9.1, E174.1, 35F9.1 covering bundled CPython + 222 `.so` files. Single bundle-root manifest because Apple's bar is API-category coverage, not per-vendored-library, and none of Bristlenose's deps are on Apple's named hard-rejection SDK list.
- `NSPrivacyTracking = false`, `NSPrivacyCollectedDataTypes` empty in both.

Reviewed by app-store-police + security-review at Checkpoint #2; code-review + what-would-gruber-say at Checkpoint #3. Build-all end-to-end exit 0 on 28 Apr 2026 with both manifests present and `plutil -lint` clean. Pre-flight `build-all.sh` step [f] enforces presence + lint on every release archive.

**Re-audit triggers:**
- Sandbox flip (Track A) may bring new file-access entitlements into scope.
- Dependency upgrades that introduce new required-reason API uses (worth a periodic `nm` regression sweep — parked).

Required since 1 May 2024. App Store Connect parses this at upload and rejects on invalid reason codes.

### 7. Privacy Nutrition Labels ⬜ NOT DONE

Self-serve form in App Store Connect. Less strict than Privacy Manifest — describes data collection at a product level rather than code level.

**Draft answers for Bristlenose:**
- Data collected: audio/video recordings, transcripts, user-generated content (quotes, tags, codebook)
- Purpose: app functionality only (no advertising, no analytics, no tracking)
- Linked to user: no (local-first)
- Used for tracking: no
- Third parties: LLM providers (Claude, ChatGPT, Azure OpenAI, Gemini) receive transcripts and metadata when user opts in; Ollama path sends nothing

### 8. AI data disclosure dialog ✅ DONE

Apple Guideline 5.1.2(i). Shipped as `desktop/Bristlenose/Bristlenose/AIConsentView.swift`. First-run sheet, consent version bump policy, re-accessible via menu.

### 9. Export compliance ✅ DONE IN PROJECT (19 Apr 2026)

`INFOPLIST_KEY_ITSAppUsesNonExemptEncryption = NO` set in both Debug and Release configs of `project.pbxproj`. Stops the per-build questionnaire from firing on every TestFlight upload. Bristlenose uses standard HTTPS to LLM providers only; no custom cryptography, no receipt-validation crypto yet. If that ever changes (E2E encryption, custom crypto library for a non-standard purpose), flip to `YES` and submit year-end self-classification reports.

### 10. App Store Connect app record ⬜ NOT DONE

One-time setup:
- Create app record with bundle ID `app.bristlenose`
- Assign primary language, category (Developer Tools? Productivity?)
- App icon set (1024×1024 marketing + sized variants — check existing assets)
- Set up internal TestFlight group, add friends as App Store Connect Users (Developer or Customer Support role is enough)

Pricing, screenshots, marketing description are required only for full App Store submission, not internal TestFlight.

### 11. CI desktop-build job ⬜ NOT DONE (informational version only)

`xcodebuild build` + `xcodebuild test` on macOS runner with `CODE_SIGNING_ALLOWED=NO`. Catches Swift compilation + Swift Testing regressions on every push. Does not upload. Prerequisite for automated TestFlight uploads later.

Plan: `docs/design-ci.md` §Coverage gaps.

### 12. First manual upload ⬜ NOT DONE

Once 1–10 are green:

```sh
# Archive
xcodebuild -project desktop/Bristlenose/Bristlenose.xcodeproj \
  -scheme Bristlenose \
  -configuration Release \
  -archivePath build/Bristlenose.xcarchive \
  archive

# Export for App Store Connect
xcodebuild -exportArchive \
  -archivePath build/Bristlenose.xcarchive \
  -exportPath build/export \
  -exportOptionsPlist ExportOptions.plist

# Upload
xcrun altool --upload-app \
  --type macos \
  --file build/export/Bristlenose.pkg \
  --username "$APPLE_ID" \
  --password "$APP_SPECIFIC_PASSWORD"
# Or the newer notarytool path — altool is deprecated
```

After upload, Apple runs automated checks (malware scan, entitlement validation, Privacy Manifest parse) — usually 15–60 minutes. Build appears in App Store Connect → TestFlight.

### 13. Internal TestFlight rollout ⬜ NOT DONE

- Internal testers: up to 100, must be in App Store Connect Users
- No Beta App Review, no hosted privacy policy URL, no ToS, no EULA
- Builds expire 90 days; need fresh upload to keep testing active
- Testers install via TestFlight app, get update notifications automatically
- Feedback channel: in-app screenshot + comment, surfaces in App Store Connect

Detail: `docs/private/testflight-alpha-path.md`.

### 14. External TestFlight → full App Store submission (S6 and beyond)

Not part of the alpha path. Requires:
- Hosted privacy policy URL (`bristlenose.app/privacy`)
- Terms of service
- EULA (standard Apple or custom)
- Age rating questionnaire
- Beta App Review on first build (external testers)
- Full App Store Review on submission (human review, days to weeks)
- Solicitor sign-off on legal docs (May 2026)
- Screenshots, marketing copy, keywords, pricing
- DPAs with LLM providers if using relay mode
- Rate-limiting on any server endpoint that touches paying-user state

Captured across `100days.md` S6 items.

## Current status summary

| # | Checkpoint | Status |
|---|---|---|
| 1 | Apple Developer Program | ✅ Done |
| 2 | Apple Distribution + Mac Installer Distribution certs + profile | ✅ Done (Apple Distribution + Mac Installer Distribution both 28 Apr 2026) |
| 3 | App sandbox + entitlements | ⬜ S2 (hardest part) |
| 4 | PyInstaller sidecar signing script | ✅ End-to-end (`fc95b99..cd04ee9`, `1ee30eb`) — Mac Installer cert added 28 Apr; notarytool skipped on App-Store path |
| 5 | Hardened Runtime entitlements | ✅ One key only (`cs.disable-library-validation`); empirically required (28 Apr retest, `8cfd2ee`) — Python.framework nested seal is the binding reason |
| 6 | Privacy Manifest audit | ✅ Host (19 Apr 2026) + sidecar (28 Apr 2026, C4 — `765b111`..`f6c3170`) |
| 7 | Privacy Nutrition Labels | ⬜ S6 (with upload) |
| 8 | AI data disclosure dialog | ✅ Done (AIConsentView.swift) |
| 9 | Export compliance | ✅ Done (19 Apr 2026, `ITSAppUsesNonExemptEncryption = NO`) |
| 10 | App Store Connect app record | ⬜ S6 |
| 11 | CI desktop-build job | ⬜ S2 (informational) |
| 12 | First manual upload | ⬜ S6 |
| 13 | Internal TestFlight rollout | ⬜ S6 |
| 14 | External / full submission | ⬜ Post-100-days |

**Sprint 2 status (29 Apr 2026):** items 2 (App Store Connect record), 4 (signing), 5 (sandbox plumbing in CI), 6 (Privacy Manifest), 8 (sidecar codesigning), 9 (supply chain) are ✅ shipped. Only #3 (sandbox runtime triage — Track A on `sandbox-debug`) + #11 (CI upload job) remain in S2. The upload itself (12–13) waits until first-run polish is share-ready — no point uploading an embarrassing build.

## What to do first when S2 signing time arrives

1. Turn on sandbox in Xcode for the Debug scheme only. Run the app. Watch Console for every sandbox violation as you exercise the MVP flow
2. For each violation, add the minimum entitlement to fix it. Keep the list tight
3. Only after sandbox works in Debug, try a Release build with Apple Distribution signing
4. Only after that, write the PyInstaller sidecar signing script
5. Only after that, run the Privacy Manifest reason-code audit against the actual code paths (host done 19 Apr 2026, sidecar done 28 Apr 2026 as Track C C4)

Resist the urge to do these in a different order. The sandbox work will surface issues that change what entitlements the manifest needs to declare; the C4 manifests will need a re-sweep when sandbox lands (Track A) since file-access entitlements may bring new required-reason API categories into scope.

## Cross-references

- **`docs/design-modularity.md`** — cross-channel component decisions (CLI + macOS), Background Assets strategy, no-fork principle, trickle-to-full-capability. Ground truth for what's bundled vs downloaded.
- **`docs/design-desktop-python-runtime.md`** — Mac sidecar mechanics (written 18 Apr 2026 as Track C C0 output, trued through 28 Apr 2026 with empty-ents retest result + App-Store-flow build pipeline). Ground truth for ServeManager, entitlements, codesign chain.
- **`docs/private/sprint2-tracks.md`** — Track A/B/C breakdown, Track C C0–C5 sub-scopes, convergence checklist.
- `docs/archive/design-desktop-distribution.md` — `.dmg` path Feb 2026 evaluation (archived 28 Apr 2026; Developer ID flow deferred until ~10k paying users, not rejected). Stub at `docs/design-desktop-distribution.md` redirects to canonical successors.
- `docs/design-desktop-security-audit.md` — full security audit findings
- `docs/design-homebrew-packaging.md` — sidecar signing prior art
- `docs/design-desktop-python-runtime.md` §"Privacy manifest coverage (C4)" — shipped manifests, triage method, build-time enforcement, re-audit triggers
- `docs/private/testflight-alpha-path.md` — TestFlight tester model
- `docs/private/infrastructure-and-identity.md` — Developer Program, domains
- `docs/private/succession-plan.md` — renewal dates
- `docs/private/100days.md` §6, §11, §12 — sprint-tagged items
