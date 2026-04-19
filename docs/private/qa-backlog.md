# QA backlog — Track C C1 residual findings

Parked items from the usual-suspects review of sidecar-signing C1 (18 Apr 2026). Land when touching the relevant files; not blocking alpha.

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
- [ ] **Add a one-line comment above `SIGN_IDENTITY="${SIGN_IDENTITY:--}"`** — the `:--` operator looks like a typo. `"-"` means ad-hoc signing identity.
