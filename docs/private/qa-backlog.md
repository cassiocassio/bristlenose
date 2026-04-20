# QA backlog — Track C C1 + C2 residual findings

Parked items from the usual-suspects reviews of sidecar-signing C1 (18 Apr 2026) and C2 (19 Apr 2026). Land when touching the relevant files; not blocking alpha.

## Parked: nice-to-haves

- [ ] **TOCTOU tightening on dev-sidecar path.** `SidecarMode.validateSidecarPath` checks exec bit / type, then `ServeManager` spawns later. Debug-only so severity bounded. Consider: `URL.resolvingSymlinksInPath()`, reject group/world-writable, log resolved absolute path at INFO.
- [ ] **Decide strip=True vs ship dSYM** for TestFlight sidecar. Strip saves ~40–60 MB in the bundle; shipping dSYM to App Store Connect gets symbolicated crash reports during alpha window. Currently `strip=True` in spec.
- [ ] **Read-loop cancellation on runaway sidecar.** `Task.detached` `availableData` loop leaks until pipe closes. Real risk only if sidecar ignores SIGINT. Consider `try handle.close()` in `stop()`.
- [ ] **`.private` on bundled path in Release logs.** `log.info("Mode: bundled, path=…")` currently `.public`. Leaks user's `/Applications` location into system logs on customer machines. Flip to `.private`.
- [ ] **Parameterise port-validation tests with `@Test(arguments:)` and `expectInvalidSidecarPath` helper.** Already applied in the refactor — double-check when `SidecarModeTests.swift` gets a test target wired in the Xcode project.
- [ ] **Wire up `BristlenoseTests` target in the Xcode project.** `SidecarModeTests.swift` + `I18nTests.swift` + `KeychainHelperTests.swift` + `ProjectIndexTests.swift` + `TabTests.swift` + `LLMProviderTests.swift` all currently orphan. `xcodebuild -list` shows only the `Bristlenose` target. ~20-60 min of pbxproj editing or a `PBXFileSystemSynchronizedRootGroup` entry for `BristlenoseTests/`.
- [ ] **Asymmetric cleanup guard for `.devSidecar` invalid path.** `ServeManager.init` only skips orphan cleanup when `userIntendedExternal` (BRISTLENOSE_DEV_EXTERNAL_PORT set). A user setting BRISTLENOSE_DEV_SIDECAR_PATH to a non-existent file still runs the kill-sweep. Current behaviour is arguably correct (dev-sidecar spawns a process we own, so zombies are ours); worth confirming intent with a comment already in place.
- [ ] **SBOM step in sidecar build** — `pip-licenses --format=json` alongside each build, archived to build output. Trust-centre material. Post-alpha.
- [ ] **Reproducible builds** for PyInstaller output. Timestamps + compile order pollute binaries. Post-alpha.
- [ ] **Replace `lsof` zombie-cleanup with in-proc TCP-connect sweep** once Track A sandbox lands — `/usr/sbin/lsof` exec is blocked under App Sandbox. Today the cleanup silently fails in a sandboxed build.

## Parked from final C1 review (18 Apr 2026)

- [ ] **Pick one canonical phrase** — "sidecar resolution" / "mode resolution" / "SidecarMode resolution" are all in use. Recommend "SidecarMode resolution" (matches the type name). Align `desktop/CLAUDE.md`, `ServeManager.swift` log strings, `design-desktop-python-runtime.md` §-heading, and any other callers.
- [ ] **Shorten `desktop/CLAUDE.md:283` parenthetical.** The typed-Optional architectural rationale belongs in the design doc, not the orientation CLAUDE.md line.
- [ ] **Flip `shouldAutocreateTestPlan = "NO"`** on all three schemes until `BristlenoseTests` target is actually wired in the Xcode project. Today it's `YES` in every scheme but the target doesn't exist.
- [ ] **Reserve `BRISTLENOSE_DEV_*` prefix in Python code.** Add a one-line comment in a stable Python file (e.g. `bristlenose/__init__.py` or `bristlenose/cli.py`) noting that the prefix is Swift-only and Python must not read env vars with that prefix — the post-archive gate in `desktop/scripts/check-release-binary.sh` skips the Python sidecar's Mach-Os and wouldn't catch a Python-side use.
- [ ] **Wire `desktop/scripts/check-release-binary.sh` into Xcode's archive pipeline.** Today it runs only if a human invokes it. Add a Run Script build phase that runs on Release-only archives, or wire into the C2 TestFlight-upload script as a precondition. Exits 1 on leak so CI can gate on it.
- [ ] **Quote `$TIMESTAMP_FLAG` (or use a bash array)** in `desktop/scripts/build-sidecar.sh:70-73`. Current unquoted `$TIMESTAMP_FLAG` expansion relies on exact default values; a hostile `TIMESTAMP_FLAG` caller-override could inject via word-splitting. Not an injection vector today (codesign rejects unknown args), but defensible.
- [ ] **Drop `head -30` on `codesign -dv` output** in `build-sidecar.sh`. On a signing failure you want the full output, not the truncated tail.
- [ ] **Add a one-line comment above `SIGN_IDENTITY="${SIGN_IDENTITY:--}"`** — the `:--` operator looks like a typo. `"-"` means ad-hoc signing identity. ✅ _folded into C2 `sign-sidecar.sh`_

## Parked from C2 review + session (19 Apr 2026)

### Blocks full end-to-end (own track, not C2)
- [ ] **SECURITY #5** in `desktop/Bristlenose/Bristlenose/SecurityChecklist.swift:23` — `ServeManager.killOrphanedServeProcesses` SIGINTs any PID on 8150–9149 without checking it's actually a bristlenose process. Multi-user Mac could terminate unrelated processes. Fix: match process name before kill. Blocks every Release archive.
- [ ] **SECURITY #8** in `SecurityChecklist.swift:24` — WKWebView navigation policy allows any `127.0.0.1:*`. Fix: restrict to the specific serve port assigned to the project. Blocks every Release archive.

### Signing hardening (procurement / CI polish)
- [ ] **Empty-entitlements re-test.** Confirm `cs.disable-library-validation` is still load-bearing now that the whole bundle is signed by one Apple Distribution identity. If it passes empty, drop DLV and update the entitlement table. Recipe: `docs/private/c2-session-notes.md` Goal 2.
- [ ] **App Store Connect API key** — replace the app-specific password in the `bristlenose-notary` profile with an ASC API key (`.p8` + key ID + issuer ID). Scoped, rotatable, revocable without touching Apple ID. One-line swap in `xcrun notarytool store-credentials`.
- [ ] **Dedicated `build.keychain`** — login keychain should not be the signing keychain for CI or shared machines. Create `build.keychain` with empty password, import P12 with `-T /usr/bin/codesign`, `security set-key-partition-list -S apple-tool:,apple: -k "" build.keychain`, list-keychains addition. Post-alpha.
- [ ] **Pre-archive cert expiry warn** — `build-all.sh` pre-flight could also report days until cert/profile expiry and warn at ≤30 days. Cheap; useful before first TestFlight push.

### Infra + script ergonomics
- [ ] **`xcodebuild archive | tee`** in an operator's shell drops the archive's non-zero exit unless they've set `pipefail`. Add a hint to the script's help text, or make `build-all.sh` detect and warn when invoked via tee-without-pipefail.
- [ ] **"Copy Sidecar Resources" build phase** has no declared outputs, so Xcode runs it on every build ("Run script build phase 'Copy Sidecar Resources' will be run during every build…"). Add outputs or flip "Based on dependency analysis" off. Nit.
- [ ] **Reserve `BRISTLENOSE_DEV_*` prefix in Python** — add a pytest that greps the Python tree and fails if any file references the prefix. Replaces the cargo-cult comment-in-`__init__.py` idea.
- [ ] **`SIGN_JOBS` benchmark per host** — document the observed wall-clock at different `SIGN_JOBS` values on M-series. TSA is I/O bound, so oversubscription may help. Run once, pick a default, note.
- [ ] **`notarytool log` JSON status parsing** — today we read `.status` via `python3 -c json.load`; could swap to `jq` if we're willing to add a brew dep, or keep Python for zero-dep.

### Documentation
- [ ] **Cross-reference `docs/private/c2-session-notes.md` into `bristlenose-docs-private/infrastructure-and-identity.md`** next time the private repo is updated (keychain partition list, app-specific password regen flow, App Store Connect record prerequisites for C3).

## Parked from app-store-police first run (19 Apr 2026)

First run of the new `app-store-police` agent against the sidecar-signing branch. Two BLOCKERs fixed in-branch (`PrivacyInfo.xcprivacy`, `INFOPLIST_KEY_ITSAppUsesNonExemptEncryption = NO`, non-empty copyright). The rest are deferred to the right track — Track A for sandbox, Track C C4/C5 for post-build verification.

### Blocks first MAS submission (Track A territory)
- [ ] **Flip `ENABLE_APP_SANDBOX = YES` for Release** in `desktop/Bristlenose/Bristlenose.xcodeproj/project.pbxproj`. Automated App Store Connect gate — unsandboxed archive bounces at upload (§2.4.5(i)). Owner: Track A. Today's `ENABLE_APP_SANDBOX = NO` is deliberate dev convenience per `desktop/CLAUDE.md`.
- [ ] **Create host-app entitlements file** (`desktop/Bristlenose/Bristlenose.entitlements`) with `com.apple.security.app-sandbox = true` + the minimal set determined by Track A's sandbox spike (likely `network.server` for loopback serve, `user-selected.read-write` + security-scoped bookmarks for interview folders). Owner: Track A. Do the empirical reduction the same way the sidecar's entitlements were reduced in C0 (18 Apr) — start with maximal, subtract until something breaks, document the load-bearing set.
- [ ] **Add `com.apple.security.inherit` to the bundled sidecar** (`desktop/bristlenose-sidecar.entitlements`) once host sandbox is on, so the sidecar runs under the parent's sandbox. Owner: Track A. Pre-documented in the sidecar entitlements comment block.

### Post-build verification (Track C C4/C5 — needs a built `.app`)
- [ ] **Verify `Python.framework` is signed as a framework bundle**, not just its inner Mach-Os. Run `codesign -dv <app>/Contents/Resources/bristlenose-sidecar/_internal/Python.framework/Versions/3.12` — output must show a bundle `CodeDirectory`, not just a plain Mach-O signature. Notarisation + MAS validation reject loose-Mach-O-only framework signatures. Ref: TN3127. If `sign-sidecar.sh` doesn't already sign the framework bundle path, add it before the inner-dylib loop.
- [ ] **Add `xcrun stapler validate -v` to `build-all.sh`** post-notarisation. Confirm the staple ticket covers the sidecar tree, not just the outer `.app`. Belt-and-braces check — notarised-but-not-fully-stapled bundles give Gatekeeper dialogs to offline users.

### Privacy manifest follow-ups
- [ ] **Add `PrivacyInfo.xcprivacy` inside the bundled Python tree** (bundle root of `bristlenose-sidecar/` and inside `Python.framework`). Apple requires privacy manifests on every embedded framework since 1 May 2024. Host-app manifest shipped 19 Apr 2026; sidecar manifest is part of Track C C4 when the runtime doc lands. Document required-reason API usage for CPython + any `.so` that hits `file_timestamp` / `disk_space` / `system_boot_time` / `active_keyboards`.
- [ ] **Revisit host-app `PrivacyInfo.xcprivacy` when sandbox lands.** Adding file-access entitlements may bring new required-reason API categories into scope; re-audit the manifest then.

### LLM disclosure prep (§5.1.2)
- [ ] **Draft App Privacy disclosure in App Store Connect** before first TestFlight build. Every configured LLM provider (Claude, ChatGPT, Azure OpenAI, Gemini) needs disclosure under Data Used to Track You / Data Linked to You — specifically User Content / Audio Data / Search History categories, since interview recordings contain all of these. Pre-drafting avoids a same-week scramble the morning of the first submission.

### Copyright holder — resolved
Copyright holder is "Martin Storey" (sole trader). No change needed. See `memory/project_legal_entity.md`. Revisit only if Martin incorporates.

## Parked from C3 closeout (20 Apr 2026)

### LLMSettingsView polish (what-would-gruber-say flagged during C3 review)
- [ ] **Save-on-blur silently clobbers working API keys** (**alpha-blocker-class**). `LLMSettingsView.swift:193–196` writes the field contents to Keychain on focus-loss with no validation, no confirmation, no undo. A 2-char typo + tab-away destroys the working key — user then has to generate a new one at the provider console. Fix: explicit Save button with verify-on-save HEAD request, OR restore the previous value if first API call 401s. This WILL bite an alpha tester.
- [ ] **Status dot reflects presence, not validity.** `refreshStatuses()` checks "key exists in Keychain" not "key works." Paste rubbish → green dot → 401 ten minutes into pipeline. Wire `ProviderStatus.invalid` to a verify-on-save HEAD.
- [ ] **Double activation control** — sidebar radio button + detail-pane toggle both set "active provider." Pick one. Kill the radio; let the toggle carry activation.
- [ ] **Provider logos dimmed to 0.55 opacity** — sign the assets are the wrong weight. Ship tuned 16pt symbol-weight icons or fall back to SF Symbols.
- [ ] **Fixed window height** (`.frame(width: 660, height: 460)`) — Mail's accounts pane flexes. Allow height to animate to content.
- [ ] **Missing Section footer under API Key field** — Mail pattern shows "Unable to verify account name or password." inline. Wire `helperText` as footer for the API Key section.
- [ ] **"Clear" button for API key has no confirmation** — destructive on a live key. At least `.borderless` style + right-of-field glyph position (`xmark.circle.fill`) per 1Password pattern.
- [ ] **Reveal-eye state persists across provider switches** — revealing Anthropic key, switching to OpenAI, switching back reveals Anthropic again. Reset on switch.
- [ ] **Escape doesn't cancel in-flight API key edit** — Settings panes should revert field on Escape.

### Logging hygiene phase 2 (post-C3)
- [ ] **Audit every `Logger` / `os_log` / `print` call in `desktop/Bristlenose/Bristlenose/**/*.swift`** — add explicit `privacy: .public` or `privacy: .private` annotations. Currently many interpolated strings have no marker, which defaults to `.private` in Release (correct-but-unreadable in unified logging). ~2 hrs.
- [ ] **Document the Swift logging convention in `desktop/CLAUDE.md`** — public vs private vs sensitive markers, when each applies, examples of each.
- [ ] **Extend `check-logging-hygiene.sh` to Python side** — symmetric gate for `logger.*` calls with user-content interpolation. ~1 hr.
- [ ] **Pre-beta: Azure key shape re-audit** — tracked in `100days.md` §6 Risk → Should; revisit when Azure's API-key format stabilises or a context-sensitive regex becomes tractable.

### Test target wiring (C1 + C3 have both added aspirational tests now)
- [ ] **Wire `BristlenoseTests` target into the Xcode project** — currently 7 aspirational Swift test files orphan: `I18nTests`, `KeychainHelperTests`, `ProjectIndexTests`, `TabTests`, `LLMProviderTests`, `SidecarModeTests`, `ServeManagerEnvTests`, `HandleLineRedactorTests`. `xcodebuild -list` shows only `Bristlenose`. 20–60 min of pbxproj editing or a `PBXFileSystemSynchronizedRootGroup` entry. Do this as a dedicated micro-track between desktop tracks to avoid pbxproj merge conflicts.

### Empty-ents retest (split from C3, prerequisite SECURITY #5+#8)
- [ ] **Run the 8-point empty-entitlements retest** per `~/.claude/plans/c3-empty-ents-retest.md`. Prerequisite: SECURITY #5+#8 unblocker. Outcome either drops `cs.disable-library-validation` entirely (strong procurement line) or rewrites the load-bearing justification.

## Parked from C3 smoke test (21 Apr 2026)

### Worktree hygiene
- [ ] **`/new-feature` skill should cover frontend deps when a worktree will touch desktop/sidecar work.** As discovered during C3 smoke test, the skill currently skips `cd frontend && npm install && npm run build`. Without those, `bristlenose/server/static/` is missing, so the bundled sidecar serves the deprecated static-render HTML instead of the React SPA. Either: (a) add a step 6b that always runs the frontend setup, or (b) make it conditional on a flag (e.g. `/new-feature my-branch --desktop`). Worth a `/new-feature` SKILL.md update before the next worktree is created.
- [x] ~~**Bundle-vs-source CI gate — source→spec part** (BUG-6a).~~ **Landed 21 Apr 2026** as `desktop/scripts/check-bundle-manifest.sh` (commit `673ddee`). Wired into `build-all.sh` step 1b. Python AST parser + extension-whitelist walker. ~60ms. Fail-closed on unparseable; allowlist at `desktop/scripts/bundle-manifest-allowlist.md` (`BMAN-<N>` markers).

- [ ] **Bundle-vs-source CI gate — spec→bundle runtime smoke test (BUG-6b).** Complementary to the landed source→spec gate. Catches "spec entry present, PyInstaller silently dropped files" class (different from BUG-3/4/5's source→spec class, which was the immediate fire). Shape:
  - Post-`build-sidecar.sh`, spawn bundled binary on ephemeral port, hit representative endpoints, assert no 5xx from `FileNotFoundError` / `ModuleNotFoundError`.
  - Endpoints to probe: `GET /api/health`, `GET /api/codebooks/` (or wherever `CODEBOOK_TEMPLATES` is exposed), plus one probe that forces `_load_prompt("autocode")` to execute — so BUG-5-class regressions are caught.
  - Security hardening (per /usual-suspects review): **must pin `--host 127.0.0.1`**, set `HOME=$(mktemp -d)` for the child, use a random high-entropy token (not a predictable sentinel), `trap` cleanup on exit/SIGINT, hard `timeout 60`, don't persist stdout with tokens into CI artefacts.
  - TCP-poll readiness detection (per perf-review): don't rely solely on `Report: http://...` log line — it fires before Uvicorn accepts connections. Add a `nc -z 127.0.0.1 <port>` poll with 50ms interval + 30s timeout after the log signal.
  - ~30s runtime. Lands in `build-all.sh` post-`build-sidecar.sh`, before `archive`.

- [ ] **`sidecar-signing` worktree's `trial-runs/` is irregular.** The skill says it should be a clean top-level symlink (`trial-runs → /Users/cassio/Code/bristlenose/trial-runs`). Instead, it's a real directory with `.DS_Store`, a real `fossda-opensource/` subdir, AND a nested `trial-runs/trial-runs → main` symlink inside. Cleanup: delete the directory's contents, replace with the proper symlink. Not blocking, just messy.
