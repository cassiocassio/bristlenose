# App Review Notes — Bristlenose

Drafted during C3 closeout (20 Apr 2026). Paste into the "App Review Information → Notes" field for the first TestFlight / App Store Connect submission. Edit as needed; the product-intent sentence is a FIXME and must be hand-written by Martin before submission.

---

## Product intent

**FIXME — hand-write before submission.** One-to-three sentences, in Martin's voice, saying what the app is and who it's for. Draft candidates rejected by reasoned preference; the reviewer needs product framing, not model-generated marketing copy.

---

## Native macOS application

Bristlenose is a native macOS application. Native elements include:

- Full macOS menu bar (File, Edit, View, Project, Sessions, Quotes, Codes, Video, Window, Help — ~89 items)
- SwiftUI sidebar for project and folder management: drag-and-drop reordering from Finder, context menus, multi-select, inline rename, folder disclosure
- NavigationSplitView workspace with a unified toolbar, segmented tab control, and native back/forward navigation
- Dedicated Settings window (Cmd+,) with three tabs (Appearance, LLM, Transcription)
- System integration: native keyboard shortcuts matching macOS conventions (Cmd+, Cmd+W, Cmd+Shift+[, Cmd+Opt+S), system appearance (dark mode, accent colour, dynamic text size), VoiceOver
- Secure storage via macOS Keychain (Security.framework, `SecItemAdd`/`SecItemCopyMatching`) for user API credentials
- App Sandbox + Hardened Runtime on Release builds

WKWebView is used to render the interactive research report, which is HTML/CSS/JavaScript by design (users export it as standalone HTML for sharing with colleagues). It is not used to wrap an external website.

---

## Network endpoints

Bristlenose makes network calls only to:

1. **The LLM provider the user selected in Settings** — Anthropic (Claude), OpenAI (ChatGPT), Azure OpenAI, Google (Gemini), or a locally-running Ollama instance — using the user's own API key, at the moment the user triggers an analysis.
2. **huggingface.co**, once per model, on first transcription, to download the Whisper transcription model to `~/Library/Application Support/Bristlenose/models/`.
3. **localhost (127.0.0.1)** between the SwiftUI host and its bundled Python analysis process.

There is no telemetry, no analytics, no crash reporting, and no usage tracking.

---

## Bundled code and downloaded data

**Bundled executables (not downloaded):**

- **FFmpeg + ffprobe** — bundled at `Contents/Resources/bin/`, signed with our Team ID (Z56GZVA2QB), Hardened Runtime enabled. Used for audio/video extraction. Pinned to a specific version with SHA-256 verification at build time.
- **Bristlenose analysis process** — bundled at `Contents/Resources/bristlenose-sidecar/`, signed with our Team ID, Hardened Runtime enabled. A PyInstaller-packaged Python runtime that serves a local HTTP API on 127.0.0.1 for the WKWebView front-end. Spawned as a subprocess on project open, terminated on app quit.

**Data downloaded on first use (not code):**

- **Whisper transcription model** — a PyTorch model file (~140 MB – 1.5 GB depending on the user's quality setting) downloaded from huggingface.co on first transcription. Cached to `~/Library/Application Support/Bristlenose/models/`. The model is **data consumed by the bundled `mlx_whisper` library** — no code is fetched at runtime and no executable content is downloaded. The library signed in the `.app` is what reads the model. Same pattern as other Whisper-using apps on the Mac App Store (MacWhisper, Aiko).

No other downloads occur.

---

## Reviewer demo access

To let you run the app end-to-end without needing your own LLM API key:

1. A throwaway Anthropic API key with a $5 hard spend cap is provided below. Please use only for App Review. It will be revoked after review completes.
2. A 2-minute demo video walking through a sample project is linked below. Reviewer can run the app themselves or watch the video if preferred.

**Throwaway API key:** `[INSERT AT SUBMISSION TIME — generate at console.anthropic.com with $5 cap, label 'app-store-review-<DATE>']`

**Demo video:** `[INSERT URL — upload to bristlenose.app/review/demo.mp4 or equivalent at submission time]`

---

## Metadata

- **Build number:** `[FILL IN AT SUBMISSION]`
- **Version:** `[FILL IN AT SUBMISSION]`
- **Minimum macOS:** 15.0 (Sequoia)
- **Reviewer contact:** martin@144a.org (monitored during review window)

## Known limitations in this build

Alpha build. Some post-alpha features are intentionally disabled or not yet shipped:

- AVFoundation-rendered highlight reels (post-100-days)
- Apple Background Assets pack downloads (public beta)

---

## Post-submission follow-ups

After submission, remember to:

- Revoke the throwaway API key at console.anthropic.com
- Remove the demo video URL from public hosting if rate-limited
- Update this file's metadata for the next build
