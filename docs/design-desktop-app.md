# Bristlenose Desktop App

_Design document — Feb 2026_

## Vision

Bristlenose is powerful but invisible to its target audience. Researchers see "open your terminal" in the README and bounce. The desktop app removes that barrier entirely: a `.dmg` they drag to Applications, a folder picker, one button, and a report in their browser.

This is the "five friends in the pub" version — the minimum wrapper that gets bristlenose into researchers' hands for UX feedback before the untested design surface grows any larger.

UX debt is as expensive as tech debt. Test early, test often.

### Success scenario

A researcher who has never used a terminal:

1. Downloads `.dmg` from Google Drive (or receives it via AirDrop)
2. Drags Bristlenose to Applications
3. Opens it (System Settings > Privacy & Security > Open Anyway on first launch)
4. Drags a folder of interview recordings onto the window
5. Clicks "Analyse"
6. Waits ~8 minutes
7. Report opens in their browser
8. They poke at it, form opinions, give feedback

No terminal. No `brew install`. No API key signup. No Python.

---

## PRD

### Must have (v0.1)

| # | Requirement | Notes |
|---|-------------|-------|
| 1 | macOS `.dmg` with drag-to-Applications | Ad-hoc signed, Apple Silicon only |
| 2 | Launcher screen with folder picker + drag target | Native NSOpenPanel + SwiftUI drag-and-drop |
| 3 | Folder validation | Count processable files, warn if none found |
| 4 | "Analyse" button (primary) | Runs `bristlenose run <folder>` via bundled sidecar |
| 5 | "Re-render" button (secondary) | Runs `bristlenose render`, only if existing output found |
| 6 | Pipeline progress display | Stream stdout checkmark lines into styled log area |
| 7 | "View Report" button when done | Opens report HTML in default browser |
| 8 | "Start over" to return to launcher | Reset state, pick new folder |
| 9 | Bundled Python runtime | PyInstaller sidecar — zero Python prerequisite |
| 10 | Bundled FFmpeg | Static binary — zero Homebrew prerequisite |
| 11 | Bundled Whisper model | `base.en` (~142 MB) — zero download on first run |
| 12 | Bundled API key (capped account) | Fallback only — Keychain takes priority |
| 13 | Keychain API key support | Already implemented in `credentials_macos.py` — auto-detected |
| 14 | Supported file types displayed | `.mp4 .mov .avi .mkv .webm .wav .mp3 .m4a .flac .ogg .aac .vtt .srt .docx` |

### Stretch goals

| # | Requirement | Notes |
|---|-------------|-------|
| 15 | Estimated cost + time before running | Needs ingest pre-scan to count files/duration |
| 16 | Cancel button during pipeline run | Kill sidecar process |
| 17 | Settings panel for API key entry | Write to macOS Keychain via sidecar |

### Not in v0.1

| # | Requirement | Notes |
|---|-------------|-------|
| 18 | In-app report viewing (WKWebView) | v0.1 uses default browser |
| 19 | Intel x86_64 / universal binary | arm64 only for pub testing |
| 20 | Onboarding wizard (doctor checks as UI) | Doctor module's `CheckResult` is ready for this |
| 21 | In-app serve mode | Pipeline → serve → WKWebView, all in one window |
| 22 | Auto-update | Not needed for 5-friend distribution |
| 23 | App Store submission | Requires sandbox, notarization, Developer ID |

---

## Stack

### Why Swift/SwiftUI + Xcode (not Tauri)

Tauri would be faster to scaffold (3 hours vs 1-2 days), but it hides Xcode, Interface Builder, SwiftUI — the entire native Mac toolchain. Our goals:

1. **Learn first-class Mac development** — Xcode, SwiftUI, process management, code signing. Every session builds real skills
2. **Everything carries forward to App Store** — no throwaway shell to rewrite
3. **Claude in Xcode** — Xcode 26.3 (Feb 2026) integrates Claude Agent SDK natively. Claude can see SwiftUI Previews, understand project structure, build/iterate autonomously. Perfect for learning Swift while building
4. **Xcode visual tools** — Interface Builder, SwiftUI previews, and the Xcode debugger give real-time feedback on the UX. This is how you make it "Mac-like"

The Swift path is an investment, not overhead. Every line carries forward.

### Technology choices

| Layer | Technology | Why |
|-------|-----------|-----|
| IDE | Xcode 26.3 | Native Mac dev, Claude integration, SwiftUI previews |
| UI framework | SwiftUI | Declarative, native macOS look-and-feel |
| Folder picker | NSOpenPanel | Native macOS dialog, 5 lines of Swift |
| Drag and drop | `.onDrop(of: [.fileURL])` | SwiftUI modifier, native |
| Process management | Foundation `Process()` | Spawn sidecar, stream stdout line-by-line |
| Open in browser | `NSWorkspace.shared.open()` | One line |
| Python runtime | PyInstaller `--onefile` | Bundled in `.app/Contents/Resources/` |
| FFmpeg | Static arm64 binary | Bundled in `.app/Contents/Resources/` |
| Whisper model | `base.en` CTranslate2 format | Bundled in `.app/Contents/Resources/` |
| API key storage | macOS Keychain | Already implemented in `credentials_macos.py` |
| Signing | "Sign to Run Locally" (ad-hoc) | No Apple Developer account needed |
| .dmg creation | `create-dmg` or `hdiutil` | Standard macOS approach |

### Alternatives considered

| Option | App size | Verdict |
|--------|----------|---------|
| **Tauri v2** (Rust + WebView) | 3-8 MB shell | Hides Xcode, hides SwiftUI. Fast scaffold but nothing learned carries forward. "Mac dev for people who don't want to learn Mac dev" |
| **Electron** | 150-250 MB | Bundles Chromium to display a WebKit page. Overkill |
| **pywebview** | 80-150 MB | Pure Python, fast. But notarization is painful, and no path to App Store |
| **Swift/SwiftUI** (chosen) | 1-3 MB shell | Native, carries to App Store, teaches real Mac dev, Claude helps in Xcode |

---

## Project structure

```
desktop/
  Bristlenose.xcodeproj/              # Xcode project (generated by Xcode)
  Bristlenose/
    BristlenoseApp.swift              # @main entry point
    ContentView.swift                 # State machine (4 phases)
    Views/
      ReadyView.swift                 # Drop zone + folder picker + supported formats
      SelectedView.swift              # Folder info + action buttons
      RunningView.swift               # Pipeline log
      DoneView.swift                  # View Report + Start Over
    Model/
      AppPhase.swift                  # State enum with associated values
      ProcessRunner.swift             # ObservableObject: spawn, stream, cancel
      FolderValidator.swift           # Check extensions, count files, detect output
    Assets.xcassets/                   # App icon, colours
    Bristlenose.entitlements           # Sandbox disabled for v0.1
    Resources/                         # gitignored — built by scripts
      bristlenose-cli                 # PyInstaller binary
      ffmpeg                          # Static FFmpeg
      models/base.en/                 # Whisper model
  scripts/
    build-sidecar.sh                  # PyInstaller → Resources/bristlenose-cli
    fetch-ffmpeg.sh                   # Download static FFmpeg → Resources/ffmpeg
    build-dmg.sh                      # xcodebuild + create-dmg → .dmg
```

Existing `frontend/` and `bristlenose/` are **untouched**.

---

## User flow

### State 1: Ready (launch)

```
┌─────────────────────────────────────────────┐
│                                             │
│              🐟 Bristlenose                 │
│       User Research Analysis Tool           │
│                                             │
│  ┌───────────────────────────────────┐      │
│  │                                   │      │
│  │  Choose a folder or drag it here  │      │
│  │                                   │      │
│  │         [ Choose folder ]         │      │
│  │                                   │      │
│  └───────────────────────────────────┘      │
│                                             │
│  .mp4 .mov .wav .mp3 .m4a .vtt .srt .docx  │
│  Zoom, Teams & Google Meet recordings       │
│                                             │
│  ┌────────────┐   ┌─────────────┐           │
│  │  Analyse   │   │  Re-render  │           │
│  │ (disabled) │   │  (disabled) │           │
│  └────────────┘   └─────────────┘           │
│                                             │
└─────────────────────────────────────────────┘
```

- Dashed-border drop zone accepts folder drag-and-drop
- "Choose folder" button triggers native NSOpenPanel
- Supported file types listed below the drop zone
- Both buttons disabled until a folder is selected

### State 2: Folder selected

```
┌─────────────────────────────────────────────┐
│                                             │
│  📁 ~/Desktop/Q1 Interviews                │
│  Found 6 processable files                  │
│                                             │
│  ┌────────────┐   ┌─────────────┐           │
│  │ ▶ Analyse  │   │  Re-render  │           │
│  │ (primary)  │   │ (secondary) │           │
│  └────────────┘   └─────────────┘           │
│                                             │
└─────────────────────────────────────────────┘
```

- Folder icon + path displayed (truncated with middle-ellipsis for long paths)
- File count shown, or "No processable files found" warning
- **Analyse** — primary button (`.borderedProminent`), enabled when fileCount > 0
- **Re-render** — secondary button (`.bordered`), only visible if `bristlenose-output/` exists
- Stretch goal: estimated cost + time

### State 3: Running

```
┌─────────────────────────────────────────────┐
│                                             │
│  📁 Q1 Interviews — Analysing...           │
│                                             │
│  ┌───────────────────────────────────┐      │
│  │ ✓ Ingested 6 files               │      │
│  │ ✓ Extracted audio (12s)           │      │
│  │ ✓ Transcribed 4 sessions (3m 22s) │      │
│  │ ● Extracting quotes...            │      │
│  └───────────────────────────────────┘      │
│                                             │
└─────────────────────────────────────────────┘
```

- Streams sidecar stdout line-by-line
- Monospace font, auto-scrolls to bottom
- Shows the pipeline's existing checkmark output (no parsing needed)

### State 4: Done

```
┌─────────────────────────────────────────────┐
│                                             │
│  📁 Q1 Interviews — Done ✓                 │
│                                             │
│  ┌───────────────────────────────────┐      │
│  │ ✓ Ingested 6 files               │      │
│  │ ✓ Extracted audio (12s)           │      │
│  │ ✓ Transcribed 4 sessions (3m 22s) │      │
│  │ ✓ Extracted 47 quotes (1m 8s)     │      │
│  │ ✓ Report ready                    │      │
│  └───────────────────────────────────┘      │
│                                             │
│  ┌──────────────────┐                       │
│  │  View Report  ▶  │  ...report.html       │
│  └──────────────────┘                       │
│                                             │
│  ← Start over                               │
│                                             │
└─────────────────────────────────────────────┘
```

- "View Report" opens HTML in default browser via `NSWorkspace.shared.open()`
- Report path shown alongside
- Launcher window persists behind the browser
- "Start over" returns to State 1

---

## API key strategy

Priority chain (no code changes needed — `load_settings()` + `_populate_keys_from_keychain()` already does this):

1. **Keychain** (highest): existing `"Bristlenose Anthropic API Key"` service, `"bristlenose"` account. Friends who have Claude and want to use their own key add it here (via Keychain Access.app or `bristlenose configure`)
2. **Environment variable**: `ANTHROPIC_API_KEY` if set
3. **Bundled fallback**: capped-account key, injected as env var when spawning sidecar

---

## What carries forward to App Store?

| Component | Baby app | App Store | Status |
|-----------|----------|-----------|--------|
| Xcode project structure | ✓ | ✓ | **Permanent** |
| SwiftUI views (all 4 states) | ✓ | ✓ | **Permanent** — this IS the app |
| ProcessRunner (sidecar management) | ✓ | ✓ | **Permanent** |
| FolderValidator | ✓ | ✓ | **Permanent** |
| NSOpenPanel + drag-and-drop | ✓ | ✓ | **Permanent** |
| App icon, window config | Basic | Polished | **Evolves** |
| Code signing | Ad-hoc | Developer ID → App Store | **Config change** |
| Sandbox entitlements | Disabled | Enabled (user-selected files) | **Future work** |
| PyInstaller sidecar | ✓ | Replace (native Python or Rust) | **Disposable** |
| Bundled FFmpeg | ✓ | Replace (signed build or AVFoundation) | **Disposable** |
| Hardcoded API key | ✓ | Remove | **Disposable** |

**9 permanent/evolving, 3 disposable.** All disposable parts are binaries in `Resources/` — no architectural debt.

---

## Estimated .dmg size

| Component | Size |
|-----------|------|
| Swift app binary | ~2 MB |
| Python sidecar (PyInstaller, CPU-only) | ~150-200 MB |
| FFmpeg static binary (arm64) | ~70-90 MB |
| Whisper base.en model | ~142 MB |
| **Total** | **~365-435 MB** |

---

## Repo & branch strategy

**Same repo, `desktop/` directory.** Not a new repo.

- Build scripts need the Python codebase to PyInstaller it
- File extensions, CLI interface, keychain conventions must stay in sync
- Separate repo = guaranteed drift. Monorepo = one source of truth
- `desktop/` is clean separation (like `frontend/` already is)
- Xcode project is self-contained — spawns a binary, doesn't import Python

**Branch sequence:**

1. **Merge `serve` → `main` first.** Serve is mature and desktop v0.2 needs it (in-app WKWebView report viewing). Don't let it drift further
2. **Create `desktop` worktree from `main`** (post-merge)
3. Desktop scaffolding in `desktop/` — zero conflict with Python/JS code
4. Merge `desktop` → `main` when launcher UI works
5. Sidecar builds, FFmpeg, Whisper model in a follow-up

---

## Open questions & technical doubts

### Confirmed risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| macOS Sequoia Gatekeeper friction — must use System Settings > Privacy & Security > Open Anyway | Medium | Send one-paragraph instructions with the .dmg. After first launch, works forever |
| PyInstaller `--onefile` startup time — 2-4s extraction | Low | Acceptable for v0.1. Move to `--onedir` later |
| Whisper `base.en` lower quality than `large-v3-turbo` | Low | Good enough for report UX feedback (the goal) |
| arm64 only — Intel Mac users excluded | Low | All five friends have Apple Silicon |

### Unresolved questions

| Question | Impact | Current thinking |
|----------|--------|-----------------|
| Where to get a signed static FFmpeg for arm64? | Blocks .dmg build | Try Martin Riedl's build server. Fall back to source build |
| Does PyInstaller + faster-whisper + ctranslate2 bundle correctly on arm64? | Blocks sidecar build | ctranslate2 uses Accelerate framework (no torch). Needs testing |
| How to extract report path from pipeline output? | Affects "View Report" | Parse last stdout line (prints `file://` URL), or scan output dir for `bristlenose-*-report.html` |
| Sandbox + `Process()` compatibility for App Store? | Future (not v0.1) | Sandboxed apps can spawn bundled binaries. NSOpenPanel grants folder access via security-scoped bookmarks |
| `.xcodeproj` generation via CLI? | Build automation | `project.pbxproj` is best generated by Xcode itself. Claude Code writes `.swift` files; Xcode project created manually then Swift files added |

### Confidence areas

- SwiftUI state machine pattern (enum + switch) is idiomatic and well-documented
- `Process()` + `Pipe()` + `readabilityHandler` for stdout streaming is standard Foundation
- NSOpenPanel folder picker is 5 lines of Swift
- `NSWorkspace.shared.open()` handles file URLs correctly
- Ad-hoc signing works for local distribution
- Existing `credentials_macos.py` Keychain integration works as-is (no changes needed)
- The CLI interface (`bristlenose run <folder>`) is stable

---

## Xcode + Claude workflow

Xcode 26.3 (released Feb 2026) integrates Claude Agent SDK natively:

- **Coding assistant**: Claude Sonnet 4 for inline Swift help
- **SwiftUI Previews**: Claude can capture previews to see what the interface looks like and iterate
- **Agentic coding**: give Claude a goal ("add drag-and-drop"), it breaks it down, implements, builds, sees compile errors, and iterates
- **Setup**: Xcode Settings → add Anthropic API key from console.anthropic.com

This makes SwiftUI the ideal choice — Claude helps inside the IDE as you learn.
