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
