# Desktop App Security Audit — March 2026

> **Trued 30 Apr 2026** — Beat 3 + 3b first-run round of fixes: Finding #12 (Ollama URL accepts arbitrary HTTP) and Opportunity G closed by the desktop GUI hardwire (commit `dbd54ec`); new auth-check trust surface enumerated under "What's Already Strong" (verdict cache, TTL gate, privacy-marked logging); HTTP-only Ollama detection ✅ row added.

> **Trued 28 Apr 2026.** Multiple Distribution Blockers and Medium gaps shipped in Track C C0–C3 plus the SECURITY #5/#8 unblocker; rows below flipped to ✅ with commit anchors. Constraint #17 (Hardened Runtime entitlement) reframed: DLV is empirically required (Python.framework's nested `_CodeSignature/` seal is the binding reason), not "kept defensively". Distribution Prep row H ("Code signing + notarization CI pipeline") is half-done, half-rejected: code signing shipped, notarisation rejected for the App Store-only path. Canonical post-Track-C docs: `design-desktop-python-runtime.md` (sidecar mechanics, entitlements, signing), `design-modularity.md` (channels), `desktop/scripts/build-all.sh` (orchestrator).

Comprehensive security review of the macOS desktop app (`desktop/Bristlenose/`), combining:
- Internal security review agent (attacker/blocker/defender personas)
- Apple's official guidelines (Sandbox, Hardened Runtime, ATS, Keychain, Notarization)
- DASVS (Desktop Application Security Verification Standard, AFINE Nov 2025)
- Community patterns (WKWebView+localhost, PyInstaller sidecar, Tauri comparison)
- Third-party tooling (Semgrep, Objective-See, SwiftLint)

**Items from this audit are prioritised in `docs/private/100days.md`** — see §6 Risk, §11 Operations, §12 Legal/Compliance.

---

## What's Already Strong

| Area | Assessment | Evidence |
|------|------------|----------|
| Keychain credential storage | Excellent | Native Security.framework, `kSecAttrAccessibleWhenUnlocked`, no plaintext fallback. **C3 (Apr 2026)**: Swift reads Keychain at sidecar launch and injects `BRISTLENOSE_<PROVIDER>_API_KEY` env vars; the sandboxed sidecar never reaches `MacOSCredentialStore`. `credentials_macos.py` remains the CLI-Mac happy path. See `design-desktop-python-runtime.md` §"Credential flow" |
| Environment scrubbing | Excellent | Sidecar receives an allowlisted env dict. No DYLD, no cloud tokens. **API keys are now intentional, allowlisted entries** (`BRISTLENOSE_<PROVIDER>_API_KEY`) fetched by Swift from Keychain at spawn time — keys live in-process only; no disk write |
| Bearer token auth | Strong | 256-bit random token per instance, CORS blocks cross-origin, media route has path-traversal guard + extension allowlist |
| JS bridge design | Strong | All 5 `callAsyncJavaScript` sites use parameterised `arguments:` dicts. Zero `evaluateJavaScript` calls |
| Ephemeral WKWebView | Strong | `.nonPersistent()` data store per project — no cross-project leakage |
| SecurityChecklist.swift | Innovative | Compile-time `#error` blocks Release builds with known security gaps |
| Local-first privacy | Major differentiator | Zero telemetry, zero phone-home, zero crash reporting. Ollama escape hatch |
| Settings auth-check trust surface | Strong | Beat 3 round-trip key validation (`LLMValidator.swift`, `LLMSettingsView.swift`). Verdict cache stores 8-byte SHA256 hash + verdict only — no key material. 60s TTL gate caps outbound traffic (verified by `LLMValidatorTests.swift`). All `os.Logger` calls covering `error.localizedDescription` are `privacy: .private`. Provider-specific HTTP semantics (Anthropic 4xx-not-401-is-online forward-compat, Azure 404 → invalid, OpenAI standard codes). User-facing disclosure in `SECURITY.md` §"Data leaves your machine only when" item 2 |
| Ollama URL hardwired in desktop GUI | Strong | Trust-boundary closure (commit `dbd54ec`, 30 Apr 2026). Settings shows static read-only `localhost:11434`; no editable field. CLI/CI override path preserved via parent-process `BRISTLENOSE_LOCAL_URL` env var (`ServeManager.swift:351-357`, `BristlenoseShared.swift:122-127`). Replaces what would otherwise be a social-engineering footgun (paste an attacker URL → silent transcript exfil) |
| Ollama detection HTTP-only | Strong | First-run install/probe via `OllamaSetupSheet.swift` uses HTTP GET `127.0.0.1:11434/api/tags` exclusively. No `Process()` exec, no `/usr/sbin/lsof`, no `/Applications/Ollama.app` filesystem polling — sandbox-clean and Homebrew-friendly. `failureMessage(for:)` catalogues `URLError.notConnectedToInternet` / `.timedOut` / `.cannotConnectToHost` |

---

## Challenges Found

### Distribution Blockers

| # | Challenge | Status | 100days |
|---|-----------|--------|---------|
| 1 | ~~No code signing or notarization~~ ✅ **CODE SIGNING DONE — C2 (`cd04ee9`, `0db0b28`); NOTARISATION REJECTED for App Store path (`1ee30eb`)** — Per-Mach-O Apple Distribution signing on every binary in the bundle. ExportOptions declares both `signingCertificate` (Apple Distribution) and `installerSigningCertificate` (Mac Installer Distribution). `notarytool` only accepts Developer ID, not Apple Distribution; App Store flow validates server-side after upload via App Store Connect. Developer ID notarytool flow preserved as deferred future-state in `design-desktop-python-runtime.md` §"Deferred — Developer ID flow" | §11 Must |
| 2 | App Sandbox disabled (`ENABLE_APP_SANDBOX = NO`) | Track A — sandbox flip is the next major piece. Track C done 28 Apr 2026 (C0–C5); Track A unstarted. Empty-ents-style empirical entitlement reduction will run on the host app once sandbox is on | §12 Must |
| 3 | ~~No Privacy Manifest (`PrivacyInfo.xcprivacy`)~~ ✅ **DONE — C4 (`765b111`..`f6c3170`, 28 Apr 2026)**. Host manifest at `Contents/Resources/` covers SwiftUI shell + FFmpeg; sidecar manifest at `Contents/Resources/bristlenose-sidecar/` covers embedded Python + 222 `.so` files. Single sidecar bundle-root manifest (per-package sub-manifests rejected as gold-plating after symbol-sweep triage). Build pipeline rejects archives missing either file or failing `plutil -lint`. See `docs/design-desktop-python-runtime.md` §"Privacy manifest coverage (C4)" | §12 Must |
| 4 | No AI data disclosure dialog | ✅ Done — `AIConsentView.swift` shipped C3, gates serve start until version acknowledged | §6 Must |
| 5 | ~~PyInstaller sidecar unsigned nested binaries~~ ✅ **DONE — C2 (`sign-sidecar.sh`)** — parallel per-binary loop signs all 240 inner `.dylib`/`.so`/framework binaries plus the outer Mach-O under one Apple Distribution identity. Note (28 Apr retest, `8cfd2ee`): per-Mach-O resigning is **necessary but not sufficient** to drop `cs.disable-library-validation` — Python.framework's internal `_CodeSignature/` seal is read by AMFI at dlopen and presents an identifier that doesn't match our Team ID. DLV stays. The empirical comment in `desktop/bristlenose-sidecar.entitlements` is the procurement-relevant record | §11 Must |

### Security Gaps — Medium

| # | Challenge | File | 100days |
|---|-----------|------|---------|
| 6 | ~~Navigation allows any localhost port~~ ✅ **DONE — SECURITY #8 (`fdf90dc`, `92a1d36`)** — `WebView.swift` now restricts navigation to `127.0.0.1` on the assigned serve port only; external opens go to `NSWorkspace.shared.open()`; port-mismatch rejections logged | `WebView.swift` (was: `:170`; now `:163, :266`) |
| 7 | ~~Zombie cleanup kills arbitrary PIDs without process name verification~~ ✅ **OBVIATED — A6 redesign (May 2026)** — host no longer enumerates orphans (sandbox blocks `proc_listpids` anyway). Sidecar self-terminates on parent-death via `os.getppid()` polling in `bristlenose/server/lifecycle.py`; host uses `bind(0)` so a slow-dying orphan can't collide. Whole `killOrphanedServeProcesses` + libproc helpers deleted (~150 lines). Earlier SECURITY #5 / libproc swap is no longer in the tree | `ServeManager.swift`, `bristlenose/server/lifecycle.py` |
| 8 | No Content Security Policy on WKWebView | WebView config | §6 Should |
| 9 | SecurityChecklist.swift stale (items #1, #3, #7 resolved but listed) — `#error` directives for #5/#8 removed in `fdf90dc` and `823f9be`; verify remaining items still flag accurately | `SecurityChecklist.swift` | §6 Should |

### Security Gaps — Low

| # | Challenge | 100days |
|---|-----------|---------|
| 10 | ~~Auth token prefix (8 chars) logged to stdout~~ ✅ **FIXED — C3 (`8a41f60`, `c17954d`)** | Runtime log redactor in `ServeManager.handleLine` masks Anthropic/OpenAI/Google key shapes (Azure deferred, pre-beta re-audit); source-level `check-logging-hygiene.sh` CI gate prevents Swift-side regressions. Auth-token parse runs before redaction so base64url tokens can't collide |
| 11 | Hardcoded dev paths in release binary (`~/Code/bristlenose/...`) | §6 Should (new) |
| 12 | ~~Ollama URL accepts arbitrary HTTP without warning~~ ✅ **DONE — first-run branch (`dbd54ec`, 30 Apr 2026)** — chosen mitigation was hardwire-not-warn (stronger than the original ticket): the editable URL field was removed from the desktop GUI entirely, replaced with a static `localhost:11434` display. CLI/CI override via parent-process `BRISTLENOSE_LOCAL_URL` env var only. Closes the trust boundary that would otherwise allow a social-engineered user to paste an attacker URL and silently exfiltrate transcripts over plain HTTP. Anchor: `LLMSettingsView.swift:331-348`, `ServeManager.swift:351-357` |
| 13 | CFBundleVersion = 1 (blocks Sparkle/App Store updates) | §11 Should |
| 14 | PyInstaller malware association → AV false positives | §11 Should |
| 15 | Bundled fallback API key extractable from binary | §6 Should |

### Architectural Constraints

| # | Constraint | Why It's Hard |
|---|-----------|---------------|
| 16 | Sandbox vs subprocess spawning | Python sidecar, arbitrary directory access, dynamic localhost ports. Requires security-scoped bookmarks + XPC |
| 17 | ~~Hardened Runtime vs Python JIT: `com.apple.security.cs.allow-unsigned-executable-memory` required~~ ✅ **FIXED — C0 (`7d121fa`)**: empirically not required. Single entitlement `com.apple.security.cs.disable-library-validation` is sufficient. `allow-unsigned-executable-memory` and `allow-jit` both unnecessary (ctranslate2 excluded; MLX runs on Metal GPU kernels). **DLV is empirically required (28 Apr retest, `8cfd2ee`), not "kept defensively":** PyInstaller's bundled Python.framework carries an internal `_CodeSignature/` seal AMFI reads at dlopen, distinct from the per-binary signatures applied by `sign-sidecar.sh`. See `design-desktop-python-runtime.md` §"Why DLV survives unified-identity signing" — this is the procurement talking point: every Mach-O in the bundle is signed under our Apple Distribution identity (Z56GZVA2QB), DLV exists to defer to Apple's own framework seal layout, and the future-work to drop it is `codesign --force` on the framework directory as a unit |
| 18 | No DASVS audit done | The right standard for desktop apps (not MASVS/ASVS). 150+ requirements across 12 domains |

---

## Opportunities — Quick Wins (< 1 day each)

| # | Opportunity | Effort | Impact |
|---|-------------|--------|--------|
| A | Port-restrict navigation policy | ~10 lines | Closes SECURITY #8 |
| B | Verify PID before zombie kill (`ps -p <pid> -o comm=`) | ~5 lines | Closes SECURITY #5 |
| C | Clean up SecurityChecklist.swift (remove #1, #3, #7) | Trivial | Clearer release gate |
| D | Wrap dev paths in `#if DEBUG` | Trivial | No info disclosure |
| E | Strip token prefix from release logs | 1 line | No token fragment in Console.app |
| F | Add `NSAllowsLocalNetworking` to Info.plist | Config | Correct ATS (not implicit via sandbox-off) |
| G | ~~Warn on non-localhost Ollama URL~~ ✅ **DONE — first-run branch (`dbd54ec`)** — closed by Finding #12 hardwire. Stronger mitigation than warn (no editable field at all in the desktop GUI). |
| H1 | ~~Broaden `MacOSCredentialStore` subprocess exception handling for sandbox-denied cases~~ ✅ **DONE — C3 (`f44ac52`)** | 1 commit | `credentials_macos.py` `get`/`set`/`delete` now also catch `FileNotFoundError` / `PermissionError` / `OSError` alongside `CalledProcessError`, with DEBUG-level diagnostic logging. Sandbox regressions surface as "No API key configured" rather than unhandled tracebacks |
| H2 | ~~Source-level logging-hygiene CI gate~~ ✅ **DONE — C3 (`c17954d`)** | 1 script | `check-logging-hygiene.sh` scans Swift for credential-shaped interpolations without `privacy: .private` markers; wired as `build-all.sh` pre-flight step 1a |
| H3 | ~~Bundle-data coverage gate~~ ✅ **DONE — C3 (`673ddee`, BUG-6)** | 1 script | `check-bundle-manifest.sh` AST-parses the PyInstaller spec, walks the source tree, fails closed on any runtime-data directory missing from `datas`. Prevents the BUG-3/4/5 class (React SPA, codebook YAMLs, llm/prompts shipped missing because Analysis only discovers `.py` imports) |

## Opportunities — Distribution Prep

| # | Opportunity | Effort | Impact |
|---|-------------|--------|--------|
| H | ~~Code signing + notarization CI pipeline~~ ✅ **CODE SIGNING DONE** (C2 `cd04ee9` + 28 Apr `1ee30eb` end-to-end fixes); **notarisation rejected for App Store path** — server-side validation by App Store Connect after upload replaces it | done | Distribution unblocked via App Store flow |
| I | First-run AI data consent dialog | 1 day | Apple Guideline 5.1.2(i) compliance |
| J | ~~Privacy Manifest (`PrivacyInfo.xcprivacy`)~~ ✅ **DONE — C4 (28 Apr 2026)** | done | App Store requirement |
| K | Inject CSP via WKUserScript | Half day | Restrict script sources in WKWebView |
| L | DASVS Level 1 checklist audit | 2-3 days | Purpose-built standard for desktop apps |
| M | Build number auto-increment | CI | Unblocks Sparkle and App Store |

## Opportunities — Longer-Term

| # | Opportunity | Notes |
|---|-------------|-------|
| N | Custom URL scheme (`bristlenose://`) | Eliminates localhost attack surface entirely (Tauri pattern). Major refactor |
| O | App Sandbox migration | Security-scoped bookmarks, XPC sidecar. Major architecture work |
| P | Semgrep CI (Swift experimental + Python mature) | Catches injection, path traversal, insecure crypto |
| Q | Objective-See QA (KnockKnock + LuLu) | Verify system footprint pre-release |
| R | AV false-positive testing | PyInstaller bundles get flagged |
| S | `kSecAttrAccessibleWhenUnlockedThisDeviceOnly` | Prevent iCloud Keychain sync of API keys |

---

## Attack Surface — Confirmed Clean

1. All 12 Swift source files — zero `evaluateJavaScript`, `NSAppleScript`, `osascript`, `shell=True`
2. `callAsyncJavaScript` — 5 call sites, all use parameterised `arguments:`
3. Keychain — correct Security.framework, `kSecAttrAccessibleWhenUnlocked`, no plaintext fallback
4. Subprocess spawning — 2 `Process()` instances, neither uses shell mode
5. WKWebView — ephemeral data store, main-frame-only user scripts, navigation delegate with origin restriction
6. Bridge messages — typed dictionary lookups with safe casting (`as? String`, `as? Bool`)
7. I18n locale handling — allowlist prevents path traversal
8. Find pasteboard — validates non-empty string
9. UserDefaults — no sensitive data
10. Server middleware — bearer token, CORS, media extension allowlist, path traversal guard

---

## Relevant Standards & Tools

| Standard/Tool | Applicability | Link |
|---------------|---------------|------|
| **DASVS** (AFINE, Nov 2025) | Primary — purpose-built for desktop apps | [github.com/afine-com/DASVS](https://github.com/afine-com/DASVS) |
| **Apple App Review Guidelines** | Mandatory for App Store | [developer.apple.com](https://developer.apple.com/app-store/review/guidelines/) |
| **Semgrep** (Swift + Python) | Static analysis | [semgrep.dev](https://semgrep.dev) |
| **Objective-See** (LuLu, KnockKnock) | QA testing | [objective-see.org](https://objective-see.org/tools.html) |
| **OWASP MASVS** | Reference only (mobile, not desktop) | [mas.owasp.org](https://mas.owasp.org/MASVS/) |

### Key Sources

- [DASVS — Desktop Application Security Verification Standard](https://github.com/afine-com/DASVS)
- [DASVS Introduction (AFINE)](https://afine.com/desktop-application-security-standard-introducing-dasvs)
- [Apple Guideline 5.1.2(i) — AI Data Sharing (TechCrunch)](https://techcrunch.com/2025/11/13/apples-new-app-review-guidelines-clamp-down-on-apps-sharing-personal-data-with-third-party-ai/)
- [PyInstaller macOS Code Signing Recipe](https://github.com/pyinstaller/pyinstaller/wiki/Recipe-OSX-Code-Signing)
- [Signing and Notarizing a Python macOS App (haim.dev)](https://haim.dev/posts/2020-08-08-python-macos-app)
- [Tauri Security Architecture](https://medium.com/tauri-apps/we-want-smaller-faster-more-secure-native-apps-77222f590c64)
- [Secure WebView Implementation (Securing.pl)](https://www.securing.pl/en/secure-implementation-of-webview-in-ios-applications/)
- [App Sandbox](https://developer.apple.com/documentation/security/app-sandbox)
- [Hardened Runtime](https://developer.apple.com/documentation/security/hardened-runtime)

---

*Generated 24 Mar 2026 by security review agent (attacker/blocker/defender) + web research.*
