# Desktop App Distribution

_Summary of distribution options for the macOS desktop app, Feb 2026._

## Distribution paths

| Path | Human review? | Robot scan? | Wait time | Who it's for |
|------|:---:|:---:|---:|---|
| **Sign only** (v0.1 plan) | No | No | 0 min | 5 friends who can click "Open Anyway" |
| **Sign + Notarize** | No | Yes | 5-15 min | Public downloads, strangers |
| **App Store** | Yes | Yes | Days/weeks | Mass distribution (not planned) |

## Apple Developer Program

- **Cost**: £79/year ($99 USD)
- **No free tier** for distributing outside the App Store
- **What it gets you**: Developer ID signing certificate, notarization access
- **When to pay**: Only when the app is self-contained (PyInstaller sidecar bundled). No point paying while the app still requires `pip install bristlenose`
- **Not needed for development**: "Sign to Run Locally" works fine on your own Mac

## Notarization vs App Store Review

These are completely different processes:

- **Notarization**: Automated robot scan. Upload `.dmg` to Apple's servers, they scan for malware signatures, 5-15 minutes, done. No human ever looks at it. For apps distributed outside the App Store (`.dmg` from website, GitHub Releases). Launched 2019. Fast, predictable, scriptable
- **App Store Review**: Human review process. Humans check app against guidelines, can reject for arbitrary reasons, takes days or weeks. The horror stories. **We are not doing this**

## Signing without notarization (friends milestone)

For ~5 friends, skip notarization entirely:

1. First launch: macOS shows "Bristlenose can't be opened because Apple cannot check it for malicious software"
2. Friend goes to **System Settings → Privacy & Security** → scrolls down → clicks **"Open Anyway"**
3. One time only, then it runs forever

Put a one-line instruction in the `.dmg` README.

## What goes in the bundle

| Component | Size | Purpose |
|-----------|------|---------|
| SwiftUI shell (.app) | ~1 MB | The native macOS wrapper |
| Python sidecar (PyInstaller `--onedir`) | ~200-400 MB | Python runtime + bristlenose + all deps |
| FFmpeg + ffprobe (static arm64) | ~80 MB | Audio extraction from video |
| Whisper model (`small.en`) | ~461 MB | On-device transcription |
| **Total .dmg (compressed)** | **~400-600 MB** | |

Without transcription (render + serve + analyze only): ~200 MB.

**Target platform**: macOS 15 Sequoia + Apple Silicon (M1+) only.

## Build sequence (before paying £79)

1. **PyInstaller sidecar** — freeze Python + bristlenose + deps into a single binary (days of work)
2. **Bundle FFmpeg** — static arm64 binary in .app Resources (hours)
3. **Bundle Whisper model** — pre-cache `small.en` so no download on first run (hours)
4. **Sign & package** — Developer ID + `.dmg` ← pay £79 here
5. **Ship to friends**

Steps 1-3 are testable entirely on your own Mac with "Sign to Run Locally". Only need the paid membership at step 4.

## Update workflow (after initial release)

1. Change pipeline code
2. Re-run PyInstaller → new sidecar binary
3. Re-run `codesign` → re-create `.dmg` (scriptable, 30 seconds)
4. Upload to GitHub Releases
5. Friends download new `.dmg`

Steps 2-4 will be scripted into `./scripts/build-desktop.sh` — one command, no manual steps, no waiting on Apple (unless notarizing, which adds 5-15 min).

## Minimum viable sidecar options

### Option A: Full pipeline (recommended for "give it a whirl" friends)

Bundle everything — friends throw a folder of recordings at it, it just works.

- Includes: faster-whisper, ctranslate2, all LLM providers, FFmpeg, Whisper model
- `.dmg` size: ~280 MB compressed
- Commands: `run`, `render`, `serve`, `analyze`

### Option B: Lightweight (no transcription)

Skip transcription deps. Friends need existing transcripts (VTT/SRT/DOCX).

- Excludes: faster-whisper, ctranslate2, FFmpeg, Whisper model
- `.dmg` size: ~100 MB compressed
- Commands: `render`, `serve`, `analyze`

Option A is the right choice — "give it a whirl" means throwing recordings at it, not preparing transcripts first.

## API key strategy (future)

Priority chain for LLM access:

1. macOS Keychain (user's own Claude/ChatGPT API key)
2. Environment variable (`ANTHROPIC_API_KEY` etc.)
3. Bundled fallback key (capped account, injected by Swift wrapper) — future, not v0.1
