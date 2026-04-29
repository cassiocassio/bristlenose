# Design: About Panel (future)

## Changelog

- **2026-04-29** — Build Info diagnostic landed: standard About panel now carries a monospaced credits block (branch, short SHA + dirty flag, configuration, sandbox / Hardened-Runtime state, sidecar mode, build date), and a sibling **Build Info…** menu item opens a copyable sheet with the same content. Implementation: [BuildInfo.swift](../desktop/Bristlenose/Bristlenose/BuildInfo.swift), [BuildInfoSheet.swift](../desktop/Bristlenose/Bristlenose/BuildInfoSheet.swift), credits injection in [MenuCommands.swift](../desktop/Bristlenose/Bristlenose/MenuCommands.swift) `AppMenuContent`. Git values come from a generated Swift constants file refreshed each build by `desktop/scripts/generate-build-info.sh`.

## Current implementation

Standard macOS About panel via `NSApp.orderFrontStandardAboutPanel(options:)`. Shows:
- App icon
- "Bristlenose"
- Version from `/api/health` + Xcode build number in brackets (e.g. "0.14.0 (42)")
- Copyright
- **Credits block** (NSAttributedString, monospaced 10pt) with the same provenance line that the in-app footer / Build Info sheet shows — `v<X.Y.Z> · <branch> · <sha>[-dirty] · <Debug|Release> · sandbox=<on|off> HR=<on|off> · sidecar=<bundled|dev-sidecar|external:N>` plus build-number and build-date lines.

Adjacent **Build Info…** menu item (Bristlenose menu, immediately below About) opens a SwiftUI sheet with the same block plus a Copy button — this surface is always visible (no `#if DEBUG` gate) so a tester pasting "what build is this?" into a support thread doesn't depend on the in-app footer being legible in the screenshot. The footer overlay in `ContentView` is the in-app counterpart and is `#if DEBUG || BRISTLENOSE_SHOW_DIAGNOSTIC_OVERLAY`-gated so it never reaches App Store / TestFlight users.

## Future vision

A custom About window inspired by Nova (Panic) — richer than the standard macOS About, with:

- **App branding** — Bristlenose logo, version number prominently displayed, release date, build number
- **License status** — "Licensed to: Name" with Remove License button (when licensing is implemented)
- **Update status** — "Bristlenose is up to date" / "Update available" with Check for Updates button (Sparkle integration)
- **Links** — "Need help? Visit our support library", Acknowledgements, GitHub repo
- **System info** — Python version, installed LLM providers, Ollama status (ties into `bristlenose doctor`)

### Prior art

| App | What they show |
|-----|---------------|
| **Nova** (Panic) | License status, update expiry date, update check, support library link, acknowledgements |
| **Sketch** | Version, license, update check, system info |
| **Tower** (Git client) | Version, license, changelog link |
| **Dash** | Version, license, acknowledgements |

### Implementation notes

- Custom `NSWindow` or SwiftUI `Window` scene (not the standard About panel)
- Version still comes from `/api/health` (canonical source: `bristlenose/__init__.py`)
- Build number from `CFBundleVersion`
- Release date: could embed in Info.plist at build time or fetch from health endpoint
- Update checking: Sparkle framework (standard for non-App Store Mac apps)
- Acknowledgements: auto-generated from `NOTICE` or `ACKNOWLEDGEMENTS` file listing open-source dependencies

### Open questions

- Do we need licensing at all? (AGPL is free/open — but a commercial support tier might need it)
- Where does "Check for Updates" point? GitHub releases? Homebrew? Custom update server?
- Should system info (doctor output) be in About or in a separate "System Information" window?
