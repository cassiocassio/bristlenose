# Desktop App Security Audit — March 2026

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
| Keychain credential storage | Excellent | Native Security.framework, `kSecAttrAccessibleWhenUnlocked`, no plaintext fallback, cross-compatible with Python `MacOSCredentialStore` |
| Environment scrubbing | Excellent | Sidecar receives exactly 9 allowlisted env vars. No API keys, no DYLD, no cloud tokens |
| Bearer token auth | Strong | 256-bit random token per instance, CORS blocks cross-origin, media route has path-traversal guard + extension allowlist |
| JS bridge design | Strong | All 5 `callAsyncJavaScript` sites use parameterised `arguments:` dicts. Zero `evaluateJavaScript` calls |
| Ephemeral WKWebView | Strong | `.nonPersistent()` data store per project — no cross-project leakage |
| SecurityChecklist.swift | Innovative | Compile-time `#error` blocks Release builds with known security gaps |
| Local-first privacy | Major differentiator | Zero telemetry, zero phone-home, zero crash reporting. Ollama escape hatch |

---

## Challenges Found

### Distribution Blockers

| # | Challenge | Status | 100days |
|---|-----------|--------|---------|
| 1 | No code signing or notarization | `CODE_SIGN_STYLE = Automatic`, dev-signed only | §11 Must |
| 2 | App Sandbox disabled (`ENABLE_APP_SANDBOX = NO`) | Required for App Store | §12 Must |
| 3 | No Privacy Manifest (`PrivacyInfo.xcprivacy`) | Required since mid-2024 | §12 Must (new) |
| 4 | No AI data disclosure dialog | Apple Guideline 5.1.2(i), Nov 2025 | §6 Must (new) |
| 5 | PyInstaller sidecar unsigned nested binaries | Every `.dylib`/`.so` must be individually signed | §11 Must |

### Security Gaps — Medium

| # | Challenge | File | 100days |
|---|-----------|------|---------|
| 6 | Navigation allows any localhost port (bridge hijack risk) | `WebView.swift:170` | §6 Must — SECURITY #8 |
| 7 | Zombie cleanup kills arbitrary PIDs without process name verification | `ServeManager.swift:377-406` | §6 Must — SECURITY #5 |
| 8 | No Content Security Policy on WKWebView | WebView config | §6 Should (new) |
| 9 | SecurityChecklist.swift stale (items #1, #3, #7 resolved but listed) | `SecurityChecklist.swift` | §6 Should (new) |

### Security Gaps — Low

| # | Challenge | 100days |
|---|-----------|---------|
| 10 | Auth token prefix (8 chars) logged to stdout | §6 Could |
| 11 | Hardcoded dev paths in release binary (`~/Code/bristlenose/...`) | §6 Should (new) |
| 12 | Ollama URL accepts arbitrary HTTP without warning | §6 Should |
| 13 | CFBundleVersion = 1 (blocks Sparkle/App Store updates) | §11 Should |
| 14 | PyInstaller malware association → AV false positives | §11 Should |
| 15 | Bundled fallback API key extractable from binary | §6 Should |

### Architectural Constraints

| # | Constraint | Why It's Hard |
|---|-----------|---------------|
| 16 | Sandbox vs subprocess spawning | Python sidecar, arbitrary directory access, dynamic localhost ports. Requires security-scoped bookmarks + XPC |
| 17 | Hardened Runtime vs Python JIT | `com.apple.security.cs.allow-unsigned-executable-memory` required. Known PyInstaller issue |
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
| G | Warn on non-localhost Ollama URL | Small SwiftUI | Prevents unencrypted transcript transmission |

## Opportunities — Distribution Prep

| # | Opportunity | Effort | Impact |
|---|-------------|--------|--------|
| H | Code signing + notarization CI pipeline | 1-2 days | Prerequisite for any distribution |
| I | First-run AI data consent dialog | 1 day | Apple Guideline 5.1.2(i) compliance |
| J | Privacy Manifest (`PrivacyInfo.xcprivacy`) | Half day | App Store requirement |
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
