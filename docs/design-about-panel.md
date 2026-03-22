# Design: About Panel (future)

## Current implementation

Standard macOS About panel via `NSApp.orderFrontStandardAboutPanel(options:)`. Shows:
- App icon
- "Bristlenose"
- Version from `/api/health` + Xcode build number in brackets (e.g. "0.14.0 (42)")
- Copyright

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
