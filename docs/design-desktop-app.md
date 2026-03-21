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

## Compatibility target

**macOS 15 Sequoia + Apple Silicon (M1+).** Decided Feb 2026 based on market data.

**Rationale:** Professional Mac users (UX researchers in agencies/consultancies) upgrade aggressively — managed fleets hit 80-90% adoption within months of a new macOS release. By late 2026 launch, Tahoe will be current and Sequoia will be n-1, covering ~90% of our audience. Intel Macs are ~5-10% of the professional installed base and falling. Targeting Sequoia+ avoids SwiftUI contortion for older APIs.

**Chip floor evolution:** M1+ for v1 launch. Bump to M2+ when local model inference features arrive (Neural Engine improvements, unified memory bandwidth). M1 is still ~28% of Apple Silicon base — don't gate v1 on it.

| Choice | Coverage (professional Mac users) | Left behind |
|--------|-----------------------------------|-------------|
| macOS 15 Sequoia + M1+ (chosen) | ~90% | ~10% (Sonoma or older, Intel) |
| macOS 14 Sonoma + M1+ | ~95-97% | ~3-5% |
| macOS 26 Tahoe only | ~55% | Too aggressive for 2026 |

---

## PRD

### Must have (v0.1)

| # | Requirement | Notes |
|---|-------------|-------|
| 1 | macOS `.dmg` with drag-to-Applications | Ad-hoc signed, Apple Silicon (M1+), macOS 15 Sequoia+ |
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
| 19 | Intel x86_64 / universal binary | Not planned — Intel is ~5-10% of professional base and falling. Revisit only if demand appears |
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
| arm64 only — Intel Mac users excluded | Low | ~5-10% of professional Mac users. All five friends have Apple Silicon. Not planned for v1 |

### Unresolved questions

| Question | Impact | Current thinking |
|----------|--------|-----------------|
| Where to get a signed static FFmpeg for arm64? | Blocks .dmg build | Try Martin Riedl's build server. Fall back to source build |
| Does PyInstaller + faster-whisper + ctranslate2 bundle correctly on arm64? | Blocks sidecar build | ctranslate2 uses Accelerate framework (no torch). Needs testing |
| How to extract report path from pipeline output? | Affects "View Report" | Parse last stdout line (prints `file://` URL), or scan output dir for `bristlenose-*-report.html` |
| Sandbox + `Process()` compatibility for App Store? | Future (not v0.1) | Sandboxed apps can spawn bundled binaries. NSOpenPanel grants folder access via security-scoped bookmarks |
| Custom URL scheme (`bristlenose://`) for deep linking? | Future | Would enable serve-mode UI to open folders/files natively via `NSWorkspace.shared.open()` instead of clipboard-copy workaround. Register `bristlenose://open-folder?path=...` and `bristlenose://open-file?path=...` handlers in `Info.plist`. The React sessions table currently copies `file://` URIs to clipboard because browsers block `file://` navigation from `http://` pages — a custom URL scheme solves this cleanly |
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

---

## Navigation & multi-project shell (v1+)

_Design exploration — Mar 2026_

v0.1 is a single-project launcher that opens reports in the browser. The next evolution wraps the existing React SPA inside a native macOS window with a project sidebar, toolbar tabs, and browser-style history. Multi-project is **desktop-only** — the CLI stays single-project, one-off, ad-hoc for Linux/Windows researchers.

### Reference apps

Studied: Slack (sidebar pattern), Claude macOS (back/forward, sidebar-top `+ New session`), Things 3 (spring animations, relaxed spacing), Bear (tag-based sidebar, TagCons), Apple Notes (3-column, double-click-to-pop-out), Apple Mail (right-click context menus, Favourites), Finder (drag-to-add, `Cmd+Opt+S` sidebar toggle, Show in Finder), Safari (tab groups, sidebar sections), Arc Browser (spaces, pinned tabs), 1Password (search-first, vault sidebar), Reeder (no unread counts), Tower/Fork (branch badges).

### Architecture: two-column NavigationSplitView

```
┌──────────────────────────────────────────────────────────────┐
│ ● ● ●  ◀ ▶  Project · Sessions · Quotes · Codebook · Analysis   ⊞ │
├──────────┬───────────────────────────────────────────────────┤
│ + Add    │                                                   │
│ ──────── │                                                   │
│ Study1   │              WKWebView (React SPA)                │
│ Pilot    │                                                   │
│ ──────── │              — renders /report/quotes/            │
│ ACME     │              — own web sidebars on Quotes tab     │
│  Study1  │              — NavBar/Footer suppressed            │
│  Study2  │                                                   │
│ INTERNAL │                                                   │
│  Dogfood │                                                   │
│ ──────── │                                                   │
│ ARCHIVE  │                                                   │
│          │                                                   │
│ ⚙ Settings                                                   │
└──────────┴───────────────────────────────────────────────────┘
```

- **Left column:** Native SwiftUI sidebar — project list with one-level folders, `+ Add Project` at top (Claude pattern), settings gear pinned at bottom-left (Slack/Claude/Apple Music pattern)
- **Right column:** WKWebView detail — the React SPA in embedded mode
- **Toolbar:** Unified with title bar, three zones per HIG (Mario Guzman toolbar guidelines):

```
┌─────────────────────────────────────────────────────────────────────┐
│ ● ● ●  ⊞  ◀ ▶  │  Project · Sessions · Quotes · Codebook · Analysis  │  Q1 Study  │
│ leading         │  centre (segmented control)                          │  trailing  │
└─────────────────────────────────────────────────────────────────────┘
```

  - **Leading** (anchored — doesn't move when sidebar opens/closes): sidebar toggle (`Cmd+Opt+S`), back/forward (`Cmd+[`/`Cmd+]` and `Cmd+←`/`Cmd+→`)
  - **Centre** (collapses to overflow on narrow windows): tab segmented control (`Cmd+1-5`)
  - **Trailing**: project name as window title (content-descriptive per HIG, not "Bristlenose"). Empty state shows "Bristlenose" when no project selected. Truncates with `...` for long names

### 17 design decisions

| # | Choice | Decision | Rationale |
|---|--------|----------|-----------|
| 1 | Columns | **2-column** (sidebar + WKWebView detail) | Web content IS the detail; a middle list would duplicate the SPA |
| 2 | Sidebar background | **Translucent vibrancy** (`.sidebar` material) | Platform default, strongest native-feel signal. Free with NavigationSplitView |
| 3 | Row height | **Follow system preference** (Small/Med/Large) | SwiftUI `List` in sidebar respects this automatically |
| 4 | Icons | **SF Symbols exclusively** for native shell | Auto-adapt to weight, size, accessibility, and accent colour |
| 5 | Selection highlight | **System accent pill** (default `List` selection) | Researchers set their accent colour; respect it |
| 6 | Collapse behaviour | **Disappear completely** (not icons-only rail) | Project names aren't icon-recognisable; 8 identical folder icons provide no information |
| 7 | Toggle animation | **Push** (content resizes) | NavigationSplitView default for permanent chrome |
| 8 | Auto-hide | **NavigationSplitView `.automaticColumnVisibility`** (~600pt) | Don't fight the framework; sidebar becomes overlay on narrow windows |
| 9 | Badges | **Grey pill** for status, **red circle** only for "needs attention" | Tower model — "Fully Merged" / "Stale" badges. Avoids notification fatigue |
| 10 | Section headers | **Uppercase small caps** (try mixed case too in implementation) | Finder/Mail standard, but Bear/Things use mixed — see what matches web content |
| 11 | Divider | **Platform default** | Thin line on Sequoia, Liquid Glass dynamic shadow on Tahoe |
| 12 | Search | **Sidebar type-to-filter** first, `Cmd+K` command palette deferred | Filter is trivial in SwiftUI; `Cmd+K` needs cross-project indexing (far future) |
| 13 | Add button | **Sidebar-top** (Claude `+ New session` pattern), `Cmd+N` when collapsed | Toolbar stays clean for navigation. Sidebar is where projects live |
| 14 | Context menu | **Right-click only** (Mail pattern), no `•••` hover affordance | Mac-only app, no iPad tax. Researchers know right-click from Dovetail/Figma/Miro |
| 15 | Drag-and-drop | **Yes** — reorder projects, drag between folders, drag media files onto sidebar to create new project, drag onto existing project to add sessions | See drop target matrix below |
| 16 | Empty state | **Drop zone + one sentence**, no tutorial | Researchers are professionals. `+ Add Project` plus main-area drop zone |
| 17 | Multi-window | **Notes pattern** — single-click loads in main window, double-click pops report into standalone window (no sidebar). Design-for now, ship later | Researchers must compare two reports side-by-side — otherwise CLI + two browser tabs wins |

### Communication bridge

```
SwiftUI ←→ WKWebView

SwiftUI → Web:
  evaluateJavaScript() for:
  - Tab navigation (window.location.href = '/report/quotes/')
  - Embedded flag injection (window.__BRISTLENOSE_EMBEDDED__ = true)
  - Theme sync (dark mode, accent colour)

Web → SwiftUI:
  WKScriptMessageHandler for:
  - route-change (keeps toolbar tab highlight in sync with React Router)
  - project-action (re-analyse, export triggered from web UI)
  - ready (web app mounted, safe to show — avoids white flash)

Native sidebar selection → spawns/switches serve instance → WKWebView loads new URL
```

### History model — delegate to WKWebView

Tab switches (`Cmd+1-5`) inject `window.location.href` changes into the WKWebView, creating real browser history entries. Native back/forward buttons call `webView.goBack()` / `webView.goForward()` (KVO-observable for enable/disable state).

React Router uses `pushState` for client-side navigation, which does NOT trigger `WKNavigationDelegate` callbacks. Instead, React posts every route change via `WKScriptMessageHandler`:

```swift
// Native → Web: tab switch
webView.evaluateJavaScript("window.location.href = '/report/quotes/'")
```

```typescript
// Web → Native: route change notification (in React router subscriber)
window.webkit?.messageHandlers?.navigation?.postMessage({
  type: 'route-change',
  url: window.location.pathname
});
```

SwiftUI receives this and updates the toolbar tab highlight. This gives correct behaviour for mixed sequences: `Cmd+3` (Quotes) → click session link → `Cmd+5` (Analysis) → Back → returns to session page, not Quotes.

### Embedded mode — the 4th rendering mode

`WKUserScript` injected at `.atDocumentStart` before the page loads:

```swift
let script = WKUserScript(
    source: "window.__BRISTLENOSE_EMBEDDED__ = true;",
    injectionTime: .atDocumentStart,
    forMainFrameOnly: true
)
```

When `window.__BRISTLENOSE_EMBEDDED__ === true`, `AppLayout.tsx` suppresses:

- **NavBar** — tabs are in the native toolbar
- **Footer** — feedback links move to native Help menu
- **Header** (logo + project title) — native toolbar shows project name

This is the 4th rendering mode for `main.tsx` (after SPA serve mode, legacy island mode, and export mode).

### Keyboard shortcut split

| Layer | Shortcuts | Mechanism |
|-------|-----------|-----------|
| **Native** (menu bar) | `Cmd+1-5` (tabs), `Cmd+Opt+S` (sidebar), `Cmd+,` (prefs), `Cmd+N` (new project), `Cmd+[` / `Cmd+]` (back/forward), `Cmd+←` / `Cmd+→` (back/forward alt) | NSMenuItem key equivalents — intercepted before WKWebView |
| **Web** (WKWebView focus) | `[` `]` `\` (web sidebars), `s` `h` (star/hide), `?` (help), arrows (quote navigation), `m` (inspector) | `useKeyboardShortcuts.ts` — bare keys, no Cmd modifier |

**Known conflict:** `Cmd+[` / `Cmd+]` (back/forward) vs bare `[` / `]` (web sidebar toggle). Users may develop muscle memory for `Cmd+[` as "go back" and be confused by bare `[` meaning "toggle TOC sidebar." The bare-key sidebar shortcuts are a future redesign candidate when the desktop shell ships. Noted, deferred.

### The two-sidebar problem

Bristlenose is 2-column native (projects | web content) but the web content has its OWN sidebars on the Quotes tab (6-column CSS grid: TOC rail | TOC sidebar | centre | minimap | tag sidebar | tag rail).

At 1440px (MacBook Pro 14") with native sidebar at 250px: the web content area is 1190px. If both web TOC (280px) and web tags (280px) are pushed open, centre content gets ~630px. Tight but workable.

**Mitigation:** When the native project sidebar is open, the web TOC sidebar defaults to **overlay mode** (hover-to-peek from the rail) instead of push. This prevents three simultaneous pushed sidebars. The user can still manually push the web TOC open, but the default is less aggressive.

### Sidebar content

#### Smart sections

```
+ Add Project              ← Claude pattern, Cmd+N when sidebar collapsed
──────────
Q1 Usability Study         ← unfiled projects (folder_id: null) — live at root
Onboarding Pilot
──────────
ACME CORP                  ← folder (one-level grouping, generic — not "client" or "workspace")
  Study 1                  5 sessions · Complete
  Q4 Card Sort             3 sessions · In progress
INTERNAL
  Dogfooding Nov           2 sessions · Draft
──────────
ARCHIVE                    ← archived projects and folders
```

Every project lives in exactly one place: either at root (unfiled) or inside a folder. No smart sections, no duplicates, no "recently opened" virtual group. Move a project to a folder via context menu → it leaves the root. Move it back to "No Folder" → it returns to the root.

ARCHIVE section uses a disclosure triangle, collapsed by default. A researcher who archives 20 old projects shouldn't have them dominating the sidebar.

**Row content:** project name (primary) + `"{n} sessions · {status}"` (secondary, muted). If project is on unmounted volume: greyed out + location hint (e.g. "External drive — Samsung T7").

**Folders:** Generic one-level grouping (not "clients" or "workspaces"). A folder is just a folder, like Finder. Users name them after clients, products, research programmes, or whatever makes sense for their work.

#### Project icon

Need a distinct SF Symbol for "project" (vs `folder.fill` for folders). Candidates:

- `doc.text.fill` — document with text
- `chart.bar.doc.horizontal.fill` — document with chart (research report)
- `rectangle.stack.fill` — stacked cards (multiple sessions)
- `waveform.and.person.filled` — audio + person (interview connotation)

#### Context menus (right-click only, no `•••` affordance)

**Project row:**
Open in New Window · --- · Show in Finder · Rename... · Move to → [folder submenu + No Folder + New Folder...] · Re-analyse · --- · Archive · Delete Project...

**Folder header:**
Rename Folder... · New Folder · --- · Archive Folder · Delete Folder...

Delete Folder confirmation: _"This will remove the folder grouping. Your projects will move to the top level. No project data will be affected."_ [Delete Folder] [Cancel]

**Archived project:**
Restore · Show in Finder · Delete Project...

**Archived folder header:**
Restore Folder

"Show in Finder" is the most important non-obvious item. Researchers constantly need to add new interview files to an existing project folder. The path from "I recorded a new interview" to "it's in my project folder" must be short.

#### Drop target matrix

| Drop target | What's dropped | Action |
|-------------|---------------|--------|
| Empty sidebar space | Media files (.mp4, .mov, .wav, .mp3, .m4a, .vtt, .srt, .docx) | "Create new project from these N files?" → name prompt → folder picker → create project folder, copy files, add to library |
| Empty sidebar space | A folder | Add existing folder as project (current v0.1 flow) |
| Folder section header | Media files | Same as above, auto-assign to that folder |
| Folder section header | A folder | Add as project, auto-assign to folder |
| Existing project row | Media files | "Add these files to [project name]?" — copies to project's input dir |
| Existing project row | A folder | Scan folder for processable files → modal: _"Found N new interviews in '[folder]'. Add to [project]?"_ with file list → on OK, copy files to project input dir, trigger re-analysis |
| Project row ↔ project row | Drag reorder | Reorder within folder, or drag onto folder header to move |

#### Archive & Delete semantics

**Key principle:** Bristlenose stores pointers to original source files + derived data (DB, tags, quotes, transcripts, analysis). Original recordings are never touched by any action.

| Action | What's removed | Original source files? |
|--------|---------------|------------------------|
| **Archive** | Nothing — sets `archived: true`, moves to ARCHIVE section | Untouched |
| **Delete Project** | `.bristlenose/` directory (DB, manifest, intermediates) + `bristlenose-output/` directory (report, transcripts, people.yaml) + `projects.json` entry | **Untouched** — recordings stay exactly where they are |
| **Unarchive** | Nothing — restores to original folder (uses preserved `previous_folder_id`) | Untouched |

Delete confirmation dialog: _"This will delete the analysis, transcripts, and tags. Your original recordings will not be affected."_ [Delete] [Cancel]

Archiving a folder archives all projects within it. The folder reappears as a section header in ARCHIVE. Unarchiving the folder restores everything.

### Multi-window: Notes "shoebox" pattern

**Single-click** a project row → loads report in the main window's WKWebView (replaces current content).

**Double-click** a project row → pops the report out into a standalone window. No sidebar, no project list — just a WKWebView with a minimal toolbar (back/forward, tabs, project name). Lightweight.

This enables side-by-side comparison without the complexity of dual-sidebar state:

```
┌─ Main Window (shoebox) ─────────┐  ┌─ Report Window (popped out) ─────┐
│ Sidebar │ Q1 Study — Quotes tab  │  │ Q4 Study — Quotes tab            │
│  Q1 ◀── │ (web content)          │  │ (web content, full width)        │
│  Q4     │                        │  │ No sidebar, no project list     │
│  Pilot  │                        │  │ Just the report                  │
└─────────┴────────────────────────┘  └──────────────────────────────────┘
```

Popped-out windows are just `Window` scenes with a `WKWebView` — no `NavigationSplitView`. Close the window → nothing lost, project is still in the sidebar.

**Scope:** Design-for now (avoid global singletons, per-window serve connection), ship in v2. v1 launches as single-window with sidebar switching.

**Why this matters:** If the desktop app can't show two reports side-by-side, researchers will just `bristlenose serve` twice in two terminals and use browser tabs. The native app must be at least as capable as the CLI + browser combo, or there's no point in the native shell.

### Visual consistency: native ↔ web

**Principle:** The native sidebar and web content should feel like they come from the same world, but the exact treatment is TBD until we see them side-by-side.

**Decided:**
- **Font family:** SF Pro in native shell. Web currently uses Inter (Google Fonts). Switching the web to SF Pro in embedded mode is a TODO — likely via a `mac-native` theme variant or suppressing the Inter `<link>` tag. Exact approach TBD when we see both side-by-side
- **Selection colour:** Derived from the Edo theme accent token (pale blue wash) — shared across native and web
- **Icon weight:** SF Symbols in native, cross-platform icon set TBD (Lucide / Phosphor) in web — matched visual weight

**Defer until side-by-side:**
- **Text sizes and row padding.** Web fonts may be too small next to native. May need a `mac-native` theme variant, or token tweaks, or accept honest divergence
- **Section headers.** Uppercase small caps vs mixed case — try both
- **Background tint.** Native vibrancy can't be replicated in WKWebView. May or may not approximate it

**Open possibility:** A dedicated macOS theme for the web content that's closer to native sizing and spacing, letting the browser version diverge. All undecided until we see what we have.

### Future project metadata

The `projects.json` index (see `docs/design-multi-project.md`) currently stores identity and location. Future fields to support smart sidebar sections and badges:

| Field | Why | Type |
|-------|-----|------|
| `client` / `organisation` | Freelancers juggle clients — often IS the folder grouping dimension | string, nullable |
| `study_type` | "usability test", "diary study", "card sort" — for smart filtering | string, nullable |
| `status` | "draft", "in progress", "complete", "shared" — for grey pill badges | enum |
| `date_range` | When interviews happened (not import date) — for chronological sorting | `{start, end}` |
| `participant_count` | Derived from pipeline — sidebar subtitle | int |
| `session_count` | Derived from pipeline — sidebar subtitle | int |
| `project_tags` | User-applied labels for cross-cutting organisation | string[] |
| `notes` | Researcher's project-level notes | text |

### App Store sandbox guardrails

v0.1 ships as a notarized `.dmg` with sandbox disabled — correct for user testing. The App Store is the endgame. These rules prevent us adding things now that have to be undone later. The full sandbox spec is in `docs/design-desktop-distribution.md` and `ROADMAP.md` (milestone 10). This section is just the "don't paint yourself into a corner" checklist for day-to-day development.

**File access — the #1 source of rework:**

| Do | Don't | Why |
|----|-------|-----|
| Store file references as security-scoped bookmark data | Store file references as path strings | Paths are dead in sandbox — the OS blocks access on next launch. Bookmarks survive moves and renames. Every indie dev who shipped non-sandboxed first says this was their biggest rework |
| Use `FileManager.default.containerURL(for:)` for app data | Hardcode `~/Library/Application Support/Bristlenose/` | `NSHomeDirectory()` lies in sandbox — returns the container path. Hardcoded `~/` paths silently point nowhere |
| Use `NSTemporaryDirectory()` for temp files | Hardcode `/tmp/` or `os.tmpdir()` | Redirects into the container in sandbox |
| Pass file URLs to the Python sidecar explicitly | Let the sidecar discover files by scanning the filesystem | Sidecar inherits sandbox — can only access URLs the parent resolved |

**Process spawning — the #2 source of rework:**

| Do | Don't | Why |
|----|-------|-----|
| Bundle all helper binaries inside the `.app` (ffmpeg, Python sidecar) | Shell out to `/usr/bin/open`, `/usr/bin/osascript`, `xcrun`, or any system tool | Sandbox blocks execution of anything outside your bundle. Cryptic error: "cannot be used within an App Sandbox" |
| Sign every `.so`, `.dylib`, helper binary with Team ID | Use `codesign --deep` on the app bundle | `--deep` overwrites individual signatures on XPC services and helpers. Sign inside-out: helpers first, then frameworks, then the app |
| Use `NSWorkspace.shared.open(url)` to open URLs in browser | Use `Process("/usr/bin/open", ...)` | `NSWorkspace` works in sandbox; `Process` with system binaries doesn't |

**Networking — easy to get right from the start:**

| Do | Don't | Why |
|----|-------|-----|
| Use `URLSession` / native networking for all HTTP | Use OpenSSL-based HTTP clients in the Python layer | Sandbox may block non-Apple SSL implementations. Python's `urllib3`/`requests` use OpenSSL — test early, may need to route API calls through the Swift layer |
| Use the Security framework (`SecItemAdd`) for API key storage | Store API keys in plaintext files or UserDefaults | Keychain works in sandbox with zero extra entitlements. Already implemented (`docs/design-keychain.md`) |

**Architecture — keep the door open:**

| Do | Don't | Why |
|----|-------|-----|
| Keep separate build targets (direct + App Store) from the start | Assume one build target with Sparkle baked in | Sparkle must be removed for App Store builds. Adding a second target later means re-testing everything |
| Use `NSOpenPanel` / drag-and-drop for all file selection | Add file browser features that scan arbitrary directories | User-selected access is the only access in sandbox |
| Treat `projects.json` as container-relative data | Put `projects.json` in a location the CLI also writes to | Desktop writes to container; CLI writes to `~/.config/`. If they share a location, the sandbox version breaks. Keep them separate, merge is a future problem |
| Design XPC service boundaries now, implement later | Make the Python sidecar deeply coupled to the Swift process | If App Store requires XPC (for privilege separation), the interface boundary is already clean |
| Use `Intl.DateTimeFormat()` in web layer | Hardcode date formats like `"DD MMM YYYY"` | Sandbox doesn't cause this, but regional format respect is an App Store review signal and a Mac-ness tell |

**Data migration — plan the one-shot:**

| Do | Don't | Why |
|----|-------|-----|
| Keep the non-sandboxed data layout simple and documented | Scatter state across `~/Library/Preferences/`, `~/Library/Caches/`, `~/Library/Application Support/` | Apple provides a one-shot migration (`com.apple.security.app-sandbox.migration` in Info.plist) that moves files from old locations into the container on first sandboxed launch. You get ONE chance. Miss a file → user loses data. Fewer locations = simpler migration |
| Use a single `Application Support/Bristlenose/` directory for all app state | Split state across multiple directories | One source directory → one migration rule |

**The practical "never do" list** (from indie devs who learned the hard way):
1. Never use `NSAppleScript` to control other apps (blocked in sandbox, needs entitlements Apple usually rejects)
2. Never depend on temporary exception entitlements — App Review rejects them retroactively
3. Never assume entitlement review is consistent — an entitlement that passed 15 times can be rejected on update 16
4. Never use `CFBundleVersion = 1` as a default — both Sparkle and App Store Connect require strictly incrementing build numbers
5. Never put critical actions at the bottom of the sidebar (HIG: users position windows low, bottom is clipped)
6. Never store anything without the quarantine xattr removed — App Store Connect rejects bundles with `com.apple.quarantine` on any file

### File tracking — NSURL bookmarks, not paths

macOS tracks files by inode/file ID, not path. Store **security-scoped bookmark data** (not path strings) in `projects.json` when the user adds a project folder. The system resolves the bookmark to the current location even after moves and renames — no "reconnect" dialog needed.

```swift
// On project creation — store bookmark
let bookmarkData = try url.bookmarkData(
    options: .withSecurityScope,  // required for App Store sandboxing
    includingResourceValuesForKeys: [.nameKey, .volumeNameKey],
    relativeTo: nil
)
// Store as base64 in projects.json alongside the path (path is a cache for display)

// On project load — resolve bookmark to current path
var isStale = false
let resolved = try URL(
    resolvingBookmarkData: bookmarkData,
    options: .withSecurityScope,
    relativeTo: nil,
    bookmarkDataIsStale: &isStale
)
if isStale {
    // File was moved or renamed — re-create bookmark, update cached path
    let fresh = try resolved.bookmarkData(options: .withSecurityScope, ...)
    // Update projects.json with fresh bookmark + new path
}
// Must call resolved.startAccessingSecurityScopedResource() before file I/O
```

**What this gives us:**

| Scenario | Behaviour |
|----------|-----------|
| User moves project folder to a new location | Bookmark resolves to new path. Cached path updates silently. No dialog |
| User renames the folder | Same — bookmark follows the inode |
| User moves folder to external drive | Bookmark resolves when drive is mounted. Greyed out when unmounted (volume name from bookmark metadata) |
| User moves folder to iCloud Drive | Bookmark resolves. May need to trigger download if evicted |
| App Store sandbox | Security-scoped bookmarks are the ONLY way to maintain access across launches. Required, not optional |

**`projects.json` schema change:** Each project entry stores both `bookmark` (base64-encoded `Data`) and `path` (string, cached for display and CLI fallback). The bookmark is authoritative; the path is a cache that updates on resolution. The CLI (non-sandboxed, Linux/Windows) uses `path` directly and ignores `bookmark`.

**Stale bookmark handling:** On app launch, resolve all bookmarks. If `isStale`, silently re-create. If resolution fails entirely (file deleted, volume permanently gone), mark the project as unavailable in the sidebar with the last-known path and volume name for the user's reference. Never silently delete a project entry — the user may reconnect the drive later.

**FSEvents for live monitoring (P2):** `DispatchSource.makeFileSystemObjectSource` or `FSEventStream` can monitor project folders for changes in real time — new files added, files renamed, files deleted. This enables: (a) "New interview files detected" badge on sidebar project row, (b) auto-refresh session list when user adds recordings via Finder. Separate from bookmark resolution, which handles the folder itself moving.

### Cross-project search (far future)

The search that really matters is: search across quotes within a folder of N projects, and search for tags-in-common across multi-project studies. This is a major feature beyond sidebar scope — it needs cross-project indexing, folder-scoped search boundaries, and a results UI. The near-term sidebar filter just narrows the project list by name.

### Apple HIG compliance

Cross-referenced against the [macOS Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/) (sidebars, toolbars, menus, keyboards, windows). Key constraints that shaped the menu bar and interaction design:

| HIG rule | Impact on our design |
|----------|---------------------|
| Every toolbar item must also exist in menu bar | Already compliant — toolbar has tabs + sidebar toggle, all in View menu |
| Dim unavailable menu items, never hide them | Menu bar items grey out contextually (e.g. Quotes menu items dim when not on Quotes tab). Exception: context menus (right-click) DO hide unavailable items per HIG |
| View menu must include Show/Hide Sidebar, Show/Hide Toolbar, Enter/Exit Full Screen | Added all three (were missing Toolbar and Full Screen) |
| Edit menu must include Select All, Use Selection for Find, Jump to Selection | Added all three |
| `Cmd+E` is reserved for "Use Selection for Find" | Moved Export to `Cmd+Shift+E` |
| `Cmd+T` is reserved for "Show Fonts" | Confirmed our TBD flag — Add Tag needs a different shortcut |
| Toolbar title should be content-descriptive, not the app name | Title shows project name (e.g. "Q1 Usability Study"), not "Bristlenose" |
| No critical info/actions at sidebar bottom | Settings gear at bottom-left is a convenience shortcut for `Cmd+,`, not the only path. Settings is also in the app menu. Low risk, but test with users who position windows low on screen |
| Window menu must list all open windows | Added, including popped-out report windows |
| Standard menu order: App · File · Edit · Format · View · [app-specific] · Window · Help | Our order: Bristlenose · File · Edit · View · Project · Codes · Quotes · Video · Window · Help. No Format menu (no rich text editing). App-specific menus between View and Window ✓ |
| Reserved system shortcuts must never be overridden | Verified: `Cmd+Space`, `Cmd+Tab`, `Cmd+H`, `Cmd+M`, `Cmd+Q`, `Cmd+F5` (VoiceOver), `Ctrl+F2` (menu focus), screenshots — none conflict with our assignments |
| Modifier key preference: Cmd > Shift > Option > Control | All custom shortcuts follow this. No Control-based shortcuts. Option used sparingly (`Cmd+Opt+S` for sidebar, following Finder convention) |
| Context menus: hide unavailable items, no keyboard shortcuts shown, max 1 level of submenu | Our context menus comply. "Move to →" is the only submenu |
| Append "..." when menu item requires additional input | Added ellipses to: Rename..., Export Report..., Browse Codebooks..., etc. |

### Native menu bar

Every command in the app must be reachable from the menu bar — this is macOS, not Slack. The menu bar is the primary discovery mechanism for keyboard shortcuts and features.

**Menu order:** Bristlenose · File · Edit · View · Project · Codes · Quotes · Video · Window · Help

**Bristlenose** (app menu — system provides Services, Hide, Show All, Quit automatically)
- About Bristlenose
- ---
- Settings... (`Cmd+,`)
- Check System Health... (runs `doctor`, output in a sheet)
- ---
- _[system: Services, Hide Bristlenose, Hide Others, Show All, Quit]_

**File** (creating, opening, closing, exporting — the "document" is a project)
- New Project... (`Cmd+N`)
- Open in New Window (`Cmd+Shift+O`)
- Close Window (`Cmd+W`) — becomes "Close All" with Option held
- ---
- Export Report... (`Cmd+Shift+E`)
- Export Anonymised...
- ---
- Page Setup... / Print... (`Cmd+P`) — prints from WKWebView

**Edit** (standard text editing + find — forwarded to WKWebView)
- Undo (`Cmd+Z`) — forwards to web layer's custom undo (quote edits, tag additions, star/hide)
- Redo (`Shift+Cmd+Z`)
- ---
- Cut (`Cmd+X`) / Copy (`Cmd+C`) / Paste (`Cmd+V`) / Paste and Match Style (`Opt+Shift+Cmd+V`)
- Delete
- Select All (`Cmd+A`)
- ---
- Find (`Cmd+F`) — routes to web search bar, NOT native WKWebView find bar
- Find Next (`Cmd+G`) / Find Previous (`Shift+Cmd+G`)
- Use Selection for Find (`Cmd+E`)
- Jump to Selection (`Cmd+J`)
- ---
- _[system: Spelling and Grammar, Substitutions, Transformations, Speech, Start Dictation, Emoji & Symbols]_

**View** (what you see, how you see it — tab titles toggle state-aware labels per HIG)
- Project (`Cmd+1`)
- Sessions (`Cmd+2`)
- Quotes (`Cmd+3`)
- Codebook (`Cmd+4`)
- Analysis (`Cmd+5`)
- ---
- Show/Hide Project Sidebar (`Cmd+Opt+S`) — label toggles with state
- Show/Hide Toolbar (`Opt+Cmd+T`)
- ---
- Toggle Left Panel — forwards `[` to web (Quotes tab only)
- Toggle Right Panel — forwards `]` to web (Quotes tab only)
- Toggle Inspector Panel — forwards `m` to web (Analysis tab only)
- ---
- All Quotes
- Starred Quotes Only
- Filter by Tag → [submenu]
- ---
- Zoom In (`Cmd+=`) / Zoom Out (`Cmd+-`) / Actual Size — WKWebView text zoom (no shortcut — `Cmd+0` is reserved for Window > Projects)
- ---
- Dark Mode / Light Mode
- Enter Full Screen (`Ctrl+Cmd+F`)

**Project** (actions on the current project — like Xcode's "Product" or ATLAS.ti's "Project")
- Show in Finder (`Cmd+Shift+R` — Reveal, following Xcode convention)
- Rename...
- Move to → [folder submenu + No Folder + New Folder...]
- ---
- Re-analyse
- ---
- Archive
- Delete Project...

**Codes** (codebook operations — QDA terminology, matches ATLAS.ti/NVivo)
- Create Code Group
- Create Code
- ---
- Rename Code Group...
- Rename Code...
- Delete Code Group
- Delete Code
- Merge Codes...
- ---
- Browse Codebooks...
- Import Framework...
- Remove Framework
- ---
- Show/Hide Code Group (eye toggle)

**Quotes** (items dim when not on Quotes tab — never hidden per HIG)
- Star
- Hide
- Add Tag... (shortcut TBD — `Cmd+T` reserved for Show Fonts, `Cmd+Shift+T` is a candidate)
- Apply Last Tag
- ---
- Reveal in Transcript — navigates to session transcript page, scrolls to timecode
- Play / Pause (Space) — forwards to Video player
- ---
- Next Quote (↓)
- Previous Quote (↑)
- Extend Selection Down (Shift+↓)
- Extend Selection Up (Shift+↑)
- Toggle Selection
- Clear Selection
- ---
- Copy as CSV

**Video** (always visible, items dim when no player is open — the Mac way)
- Play / Pause (Space)
- ---
- Skip Forward 5s (→)
- Skip Back 5s (←)
- Skip Forward 30s (Shift+→)
- Skip Back 30s (Shift+←)
- ---
- Speed Up (`Cmd+Shift+.`)
- Slow Down (`Cmd+Shift+,`)
- Normal Speed (`Cmd+Shift+0`)
- ---
- Volume Up (`Cmd+↑`)
- Volume Down (`Cmd+↓`)
- Mute / Unmute
- ---
- Picture in Picture — dims for audio-only sessions
- Fullscreen (`Cmd+Shift+F`) — dims for audio-only sessions

**Window** (standard macOS — system provides most of this)
- Minimise (`Cmd+M`) — Option held = Minimise All
- Zoom — Option held = Zoom All
- ---
- Projects (`Cmd+0`) — brings the main shoebox window to front (Notes pattern: Window > Notes)
- Bring All to Front — Option held = Arrange in Front
- ---
- _[open window list — main window + any popped-out report windows, alphabetically]_

**Help**
- Bristlenose Help (`Cmd+?`)
- Keyboard Shortcuts — _"Press ? in the report view to see all keyboard shortcuts"_
- ---
- Send Feedback
- ---
- Release Notes

**Menu bar implementation notes:**
- Bare-key web shortcuts (`s`, `h`, `[`, `]`, `m`, `?`, arrows) DON'T get Cmd+ menu equivalents — they only work when WKWebView has focus. The Help menu points users to `?` for the full shortcut reference.
- Menu items that forward to the web layer call `evaluateJavaScript("window.__bristlenose.menuAction('star')")` — a single dispatch function with string action names. See bridge protocol below.
- Tab-contextual menus (Quotes, Codes, Video) **dim** unavailable items based on active tab — the `route-change` bridge message tracks this. Items are never hidden from the menu bar (HIG rule).
- `Cmd+[` / `Cmd+]` back/forward are disabled when an EditableText field is active in the web layer. The bridge sends `editing-started` / `editing-ended` messages to manage this.
- `Cmd+F` routes to the web app's search bar, NOT the native `WKWebView.find()` bar. The web search is richer (searches quotes, tags, speaker names).
- Undo/Redo forwards to the web layer's custom undo stack, not browser-native `document.execCommand('undo')`. The web layer reports undo availability via `getState()` so the native menu items enable/disable correctly.
- Video menu title stays "Video" (99% case). Audio-only sessions still use the same menu — only Picture in Picture and Fullscreen dim (all other controls apply to audio). The menu is always visible with items dimmed when no player is open — researchers discover "oh, I can control speed from here" before they need it.
- System-registered **MPNowPlayingInfoCenter** + **MPRemoteCommandCenter** integration is a future enhancement — would make keyboard media keys (play/pause on Touch Bar / function row) and the Control Center Now Playing widget work automatically. Requires bridging the HTML5 Media Session API from WKWebView.

### Bridge protocol (expanded)

The initial bridge (3 message types) needs expansion to support the full menu bar. The mechanism is simple and extensible — just more message types and a dispatch function.

**Web → SwiftUI** (`WKScriptMessageHandler`):

| Message type | Payload | Purpose |
|-------------|---------|---------|
| `route-change` | `{ url: string }` | Tab highlight sync, contextual menu enable/disable |
| `ready` | `{}` | Web app mounted — safe to dismiss loading overlay |
| `project-action` | `{ action: string, data?: object }` | Re-analyse, export triggered from web UI |
| `focus-change` | `{ quoteId: string \| null, selectedIds: string[] }` | Enables Quotes menu items, provides target for Star/Hide/Tag |
| `editing-started` | `{ element: string }` | Disables `Cmd+[`/`Cmd+]` back/forward during text editing |
| `editing-ended` | `{}` | Re-enables back/forward |
| `undo-state` | `{ canUndo: bool, canRedo: bool, undoLabel?: string }` | Enables/disables Edit > Undo/Redo, optional label ("Undo Star") |
| `player-state` | `{ playing: bool, hasPlayer: bool, audioOnly: bool }` | Enables/disables Video menu items, toggles Play/Pause label |

**SwiftUI → Web** (`evaluateJavaScript`):

```typescript
// Single namespace, stable API surface
window.__bristlenose = {
  // Menu action dispatcher — native menu items call this
  menuAction(action: string, payload?: object): void,

  // State query — native polls this for menu enable/disable
  getState(): {
    activeTab: string,
    focusedQuoteId: string | null,
    selectedIds: string[],
    isEditing: boolean,
    canUndo: boolean,
    canRedo: boolean,
    hasPlayer: boolean,
    playerPlaying: boolean,
  },
};
```

The `menuAction` dispatcher is the single entry point for all 89+ menu actions. Each action is a string (`'star'`, `'hide'`, `'addTag'`, `'nextQuote'`, `'playPause'`, `'skipForward5'`, `'speedUp'`, etc.). The web layer routes to the appropriate handler — same handlers that keyboard shortcuts already use. No new logic, just a new entry point.

**Polling vs events:** The native side uses `getState()` as a fallback for menu validation (called before showing a menu), but prefers the event-driven messages (`focus-change`, `undo-state`, `player-state`) for real-time updates. This avoids polling overhead while ensuring menus are always correct even if an event was missed.

### Accessibility

**VoiceOver at the native/web boundary** — the hardest accessibility challenge. Must specify before writing code:

1. **Tab / Shift+Tab transition.** SwiftUI's `.focusSection()` modifier on the sidebar and the WKWebView container. When Tab reaches the end of the sidebar project list, focus enters the WKWebView. Shift+Tab from the first focusable web element returns to the sidebar.
2. **VoiceOver announcement.** The WKWebView container should have `accessibilityLabel = "Report content"` so VoiceOver announces the boundary when entering the web view.
3. **Rotor behaviour.** VoiceOver treats WKWebView as a web content group. The web app's existing ARIA roles (tabs, buttons, modals) continue to work inside it.
4. **Focus on project switch.** After selecting a project in the sidebar, call `webView.becomeFirstResponder()` to move focus into the web content. Same after `Cmd+1-5` tab switches.
5. **Toolbar accessibility labels.** Tab segmented control items must have accessibility labels matching the web tab names exactly ("Project", "Sessions", "Quotes", "Codebook", "Analysis").

**Reduced motion.** All native spring animations must check `@Environment(\.accessibilityReduceMotion)` and fall back to instant transitions. The web side already handles `prefers-reduced-motion` via CSS.

**Keyboard-only navigation.** Full keyboard path must work: Tab to sidebar → arrow keys to select project → Enter to open → Tab into web content → `Cmd+3` to Quotes → arrow keys to navigate quotes → `s` to star. The weakest link is the Tab transition from sidebar to WKWebView — test explicitly.

**Drag-and-drop keyboard alternative.** Context menu "Move to" covers folder reassignment. For reordering projects within a folder: consider `Cmd+Opt+↑` / `Cmd+Opt+↓` to move the selected project up/down in its list. `+ Add Project` with a file picker dialog covers all drag-and-drop creation scenarios for keyboard-only users.

**Dynamic Type / text scaling.** SwiftUI respects the system text size setting automatically for native sidebar elements. WKWebView does NOT — the web content stays the same size regardless of the Accessibility text size preference. This creates a mismatch: at "Extra Large" text, the sidebar rows grow but the web content doesn't. Mitigation: inject a CSS `font-size` override into WKWebView based on the system text size setting (`NSApplication.shared.preferredContentSizeCategory`). Exact scaling curve TBD during implementation.

**High contrast mode.** macOS "Increase contrast" accessibility setting. SwiftUI handles this for native elements. The web app's CSS tokens should respond to `prefers-contrast: more` — verify during integration testing.

**Drop target highlighting.** Drag-and-drop uses standard macOS drop-target highlighting: blue insertion line for reorder, background tint on valid "drop into" targets (folder headers, project rows, empty sidebar space). This is separate from the "no hover affordance" principle for context menus (decision 14) — drag feedback is expected and necessary for usability.

### Mac-ness audit checklist

The unwritten rules that separate "a Mac app" from "an app that runs on Mac." Sourced from the indie Mac developer community — John Gruber (Daring Fireball), Brent Simmons (NetNewsWire), Craig Hockenberry (Iconfactory), Panic (Nova/Transmit), the ATP podcast (Siracusa/Arment/Liss), Mario Guzman (Apple design engineer), and the 1Password-to-Electron backlash. The guiding philosophy: **"Caring is ultimately what makes true Mac apps Mac apps"** (Gruber, 2017). It's not about the tech stack — it's about whether the user can tell.

**Goal:** App Store version is completely Mac-like. The user never needs to know the detail pane is a web view. The things that break the illusion are listed here.

References:
- [Daring Fireball: Mac-Assed Mac Apps](https://daringfireball.net/linked/2020/03/20/mac-assed-mac-apps)
- [Daring Fireball: Sketch, and the Joy of Mac-App Mac Apps](https://daringfireball.net/2020/11/sketch_mac_app_mac_apps)
- [Audacious: Tuned for the Mac](https://audacious.blog/2020/tuned-for-the-mac/)
- [Mario Guzman: Sidebar Guidelines](https://marioaguzman.github.io/design/sidebarguidelines/)
- [Mario Guzman: Toolbar Guidelines](https://marioaguzman.github.io/design/toolbarguidelines/)
- [DEV.to: Making Electron Apps Feel Native on Mac](https://dev.to/vadimdemedes/making-electron-apps-feel-native-on-mac-52e8)
- [MacStories: Nova Review](https://www.macstories.net/reviews/nova-review-panics-code-editor-demonstrates-why-mac-like-design-matters/)
- [Michael Tsai: Is Electron Really That Bad?](https://mjtsai.com/blog/2025/04/25/is-electron-really-that-bad/)

#### Already covered in our design

| # | Check | Status | Where |
|---|-------|--------|-------|
| 1 | Every action in the menu bar with shortcuts | ✓ | Menu bar section above |
| 2 | `Cmd+,` opens Settings | ✓ (needs native window — see #18 below) | App menu |
| 3 | Show/Hide Sidebar in View menu | ✓ | View menu, `Cmd+Opt+S` |
| 4 | Window position/size memory between launches | ✓ | SwiftUI `NSWindow.setFrameAutosaveName` — automatic |
| 5 | Multi-window support | ✓ | Notes shoebox pattern, `Cmd+0` for Projects |
| 6 | `Cmd+W` closes window, `Cmd+Q` quits — app knows the difference | ✓ | Standard Window menu |
| 7 | Dark mode with proper `NSAppearance` integration | ✓ | Native vibrancy + web CSS tokens |
| 8 | Right-click context menus (not hamburger menus) | ✓ | Decision 14, Mail pattern |
| 9 | Drag and drop with full drop target matrix | ✓ | Decision 15 |
| 10 | Sidebar width constraints, Show/Hide, right-click menus | ✓ | Sidebar content section |
| 11 | No hamburger menus anywhere | ✓ | — |
| 12 | No white flash on launch | ✓ | `ready` bridge message + native loading overlay |

#### Easy wins — implement during P1/P2

| # | Check | What to do | Priority |
|---|-------|-----------|----------|
| 13 | **Shared find pasteboard** (`Cmd+E` copies selection to system find pasteboard, `Cmd+G` finds next in ANY app) | Bridge `NSPasteboard(name: .find)` — write from native on `Cmd+E`, read from native on `Cmd+G`, forward to WKWebView. Cross-app find is a beloved power-user feature that Electron apps break | P1 |
| 14 | **Cocoa text keybindings** (`Ctrl+A` beginning of line, `Ctrl+E` end of line, `Ctrl+K` kill to end, `Ctrl+F/B` forward/back, `Ctrl+P/N` prev/next line, `Ctrl+Y` yank) | WKWebView `<input>`/`<textarea>` get these for free. `contenteditable` quote editing may not — test and fix. Decades of muscle memory for long-time Mac users | P1 |
| 15 | **Selections dim to grey when window inactive** | SwiftUI sidebar: automatic. WKWebView: add `::selection` CSS with `:window-inactive` pseudo-class (WebKit-specific). Without this, the app immediately feels foreign | P2 |
| 16 | **Dates/numbers respect regional format** | Use `Intl.DateTimeFormat()` and `Intl.NumberFormat()` in web layer, not hardcoded formats. Native side: automatic. "The quickest way to tell an Electron app from a native one is whacky datetime formatting" (Michael Tsai) | P1 |
| 17 | **13pt system font in embedded mode** | macOS system font size is 13pt. Web defaults to 16px. In embedded mode, set `font-size: 13px` on `<html>` — this is the Inter→SF Pro TODO. The 16px web text next to 13pt native sidebar text is an immediate tell | P1 |
| 18 | **Option-drag copies** in sidebar | SwiftUI `onDrag` with `.copy` modifier when Option key held. Standard Mac drag-and-drop convention | P2 |
| 19 | **Cursor: arrow on non-link elements** | Web convention: `cursor: pointer` on buttons/cards. Mac convention: `cursor: default` on non-link interactive elements. In embedded mode, consider resetting `cursor: pointer` to `cursor: default` on buttons, toggles, sidebar items. Subtle but Mac users notice | P2 |

#### Harder questions — design decisions needed

| # | Check | Question | Notes |
|---|-------|----------|-------|
| 20 | **Native Preferences window** | Settings must be a SwiftUI `Settings` scene — proper window, `Cmd+,`, native controls, grid-of-icons layout (Panic Nova pattern). Changes apply immediately, no Save button. Which settings live in native vs web? All of them should be native — the web `SettingsModal` becomes dead code in embedded mode. Quote display preferences, codebook settings, provider credentials — all native controls | P1 — design the Settings window layout before implementing |
| 21 | **Services menu on right-click** | Right-click selected quote text should show Services submenu (Send via Mail, Create Sticky Note, system automation). WKWebView's `contenteditable` and `<textarea>` may or may not surface this — needs testing. If not, it's a "this developer doesn't get it" tell | P1 — test early, may need native intervention |
| 22 | **Quick Look extension** | Spacebar on a `.bristlenose` project folder in Finder → Quick Look preview showing project summary (session count, quote count, last analysed date). Requires shipping a Quick Look extension (`.appex`). Nice touch, not essential | Post-v1 |
| 23 | **AppleScript / Shortcuts integration** | "Run analysis on this folder" as a Shortcut action. "Export report for project X" via AppleScript. Power users expect automation. Design-for-now: use `@Observable` properly so Shortcuts `AppIntent` can query state later | Post-v1, but design-for now |
| 24 | **Scroll feel in WKWebView** | WKWebView inherits native scroll inertia and rubber-banding for free. But custom scroll handlers (smooth scroll polyfills, the `useScrollSpy` RAF-throttled listener) can fight the native feel. Test the Quotes page scroll carefully — any jank here is an immediate tell | P1 — test, don't assume |
| 25 | **Drag from inactive windows** | Should be able to drag a project from the sidebar of an inactive (background) main window without clicking to activate it first. SwiftUI may handle this automatically — needs testing. Gruber specifically criticised Photos for not supporting this | P2 — test |
| 26 | **Undo depth** | `Cmd+Z` must work with proper depth, not just one level. The web layer's custom undo stack (quote edits, tag additions, star/hide) needs to be deep enough. The bridge reports `canUndo`/`canRedo` + optional label ("Undo Star") | P1 — already in bridge spec |

#### The Gruber framework

> "You CAN deviate from standard Mac UI — but only if the deviation is genuinely better design. Custom chrome is forgiven when it's thoughtful. Custom chrome that's worse than the standard is unforgivable."

The WKWebView content IS custom chrome by definition — it's web, not AppKit. The art is making the native shell so good that users forget the detail pane is a web view. The native sidebar, toolbar, menu bar, Preferences window, find pasteboard, Services menu, window management, and keyboard shortcuts must all be flawless. Then the web content can be whatever it needs to be — and if it's good enough, nobody will care that it's rendered by WebKit.

**The 1Password cautionary tale:** 1Password 8 switched from native AppKit to Electron. The Mac community erupted. Jason Snell (Six Colors): "The very best Electron app isn't as good a Mac app as one written using Apple's AppKit frameworks." The lesson: it's not about whether you use Electron/WKWebView — it's about whether the app *cares* about being a Mac app. We care.

### Patterns to adopt vs avoid

**Adopt:**
- **Bear** — collapsible tag sections → our folder sections with disclosure triangles
- **Things 3** — spring animations (`.spring(response: 0.3, dampingFraction: 0.8)`), relaxed spacing
- **Finder** — "Show in Finder" context menu, `Cmd+Opt+S` sidebar toggle, drag-to-add
- **Claude macOS** — `+ New session` at sidebar top, back/forward in toolbar
- **Notes** — double-click to pop out into standalone window for comparison

**Avoid:**
- **Reeder** — "no unread counts" philosophy. Researchers NEED status badges
- **Craft** — deep nesting with breadcrumbs. Violates one-level folder constraint
- **Tower** — developer-density information design. Intimidating for non-technical users
- **Notes `•••`** — hover affordance for context menu. Un-Mac, iPad tax. Right-click only

### Serve instance lifecycle (P0)

One serve process per active project, managed by a `ServeManager` observable object.

**Port allocation:** `8150 + hash(project_id) % 1000`, fallback to next available port if occupied. Range 8150–9149. Each project gets a consistent port across sessions (predictable, debuggable). Consistent-port is best-effort — if the port is occupied by a non-Bristlenose process, the fallback port is used and logged.

**State machine:**

```
                    ┌─────────┐
                    │  Idle   │ ← no project selected
                    └────┬────┘
                         │ sidebar click
                    ┌────▼────┐
                    │Starting │ → spawn `bristlenose serve --port N project_path`
                    └────┬────┘
                         │ stdout: "Uvicorn running on..."
                    ┌────▼────┐
                    │Loading  │ → WKWebView navigates to localhost:N/report/
                    └────┬────┘
                         │ bridge: `ready` message
                    ┌────▼────┐
                    │ Active  │ → loading overlay dismissed, content visible
                    └────┬────┘
                         │ sidebar click (different project)
                    ┌────▼────┐
                    │Switching│ → new process starts, old stays alive
                    └────┬────┘
                         │ new process ready
                         │ old process gets SIGTERM (graceful, 5s timeout → SIGKILL)
                         └──→ Active (new project)
```

**Project switching:** The old serve process stays alive until the new one is ready. This keeps the old content visible during the transition — no blank screen. The WKWebView dims slightly (0.7 opacity) during the switch, then fades to full opacity on `ready`.

**Failure handling:** If the serve process doesn't output "Uvicorn running on..." within 10 seconds, or the `ready` bridge message doesn't arrive within 15 seconds of page load, transition to `Failed` state. Show error sheet: stderr log, [Retry] [Dismiss]. During `Switching`, do NOT navigate the WKWebView or SIGTERM the old process until the new one reaches `Active`. If the new process fails, cancel the switch — restore old WKWebView to full opacity with an error toast.

**Cleanup:** `applicationWillTerminate` sends `SIGTERM` to all managed processes. `atexit` handler catches crashes. `ServeManager` tracks PIDs and ports in an in-memory dictionary — no persistent state.

**Multi-window (future):** Each popped-out report window keeps its serve process alive independently. `ServeManager` reference-counts: process lives as long as at least one window references it. Last window closes → `SIGTERM`.

### Loading and transition states

| Transition | What the user sees | Duration |
|-----------|-------------------|----------|
| **App launch → first project** | Native sidebar renders immediately (< 100ms). WKWebView area shows a centered `ProgressView` (system spinner) on the window background. Dismisses on `ready` bridge message | ~1-3s (serve startup + React mount) |
| **Project switch** (sidebar click) | WKWebView dims to 0.7 opacity. Sidebar selection updates immediately. On `ready`, new content fades in (200ms `easeInOut`) | ~1-2s (new serve startup, old stays visible underneath) |
| **Tab switch** (`Cmd+1-5`) | Instant — `evaluateJavaScript` changes the URL, React Router handles client-side transition. No native loading state needed | < 100ms |
| **Pipeline running** | Sidebar project row shows a spinning activity indicator (replaces status badge). Main content stays on current report. Progress streams to a sheet or popover anchored to the sidebar row | Minutes |
| **Pipeline failed** | Activity indicator replaced by red exclamation badge. Clicking the badge opens a sheet: error message, stdout/stderr log, [Retry] [Copy Error] [Dismiss]. If partial output exists (transcription done, analysis failed): [View Partial Report] button | — |
| **No project selected** (empty state) | Sidebar shows `+ Add Project` and project list. Main area shows a drop zone with one sentence: _"Drag a folder of interviews here, or click + Add Project"_ | — |

### WKWebView configuration

**Process pool:** One shared `WKProcessPool` across all WKWebViews for v1 (saves memory, shares cookies/session storage). Per-project pools if multi-window ships and isolation matters.

**Bridge namespace injection:** `window.__bristlenose = { menuAction: ..., getState: ... }` injected via a second `WKUserScript` at `.atDocumentStart`, immediately after the embedded flag script. Order matters — embedded flag first, then bridge namespace, then the page loads.

**Web content crash recovery:** Implement `webViewWebContentProcessDidTerminate(_:)` in `WKNavigationDelegate`:
1. Show a native overlay: _"Report view stopped unexpectedly."_ [Reload]
2. Log the crash (timestamp, project, last URL)
3. On Reload: `webView.reload()` — serve process is still running, just the renderer crashed
4. If crash happens 3× in 60 seconds: show _"Something is wrong with this report."_ [Open in Browser] [Dismiss]

**`evaluateJavaScript` error handling:** Menu actions fail silently (user clicked Star but page wasn't ready — no harm, no alert). `getState()` failure returns a default "disabled" state (all contextual menu items dim). Log errors for debugging.

**`ready` message timing:** The web layer posts `ready` after first meaningful paint — React mounted AND initial route data loaded (quotes list, session list, dashboard stats). Posted from the route-level data loader, NOT from `main.tsx` mount. This prevents showing app chrome with empty content. If data loading takes > 5 seconds, post `ready` anyway with a loading skeleton — the native overlay shouldn't linger indefinitely.

### WKWebView security hardening

Required for v1. Small amount of code, large security payoff.

**1. Navigation restriction** — implement `WKNavigationDelegate.decidePolicyFor:navigationAction:` to allow only `http://127.0.0.1:*` and `about:blank`. All external URLs open in the default browser via `NSWorkspace.shared.open(url)`. This prevents: (a) clickable URLs in transcript content navigating the WKWebView to attacker-controlled pages, (b) redirect chains from LLM error pages reaching the bridge.

**2. Bridge origin validation** — every `WKScriptMessageHandler` callback must check `message.frameInfo.request.url` to verify the origin is `http://127.0.0.1`. Register all handlers with `forMainFrameOnly: true`. Without this, any page loaded in the WKWebView could call `window.webkit.messageHandlers.navigation.postMessage(...)` and trigger native actions.

**3. Never interpolate user strings into `evaluateJavaScript`** — use `WKWebView.callAsyncJavaScript(_:arguments:)` (macOS 11+) which passes arguments via structured serialisation, not string concatenation. A project named `'; alert(1); '` must not become code execution. Document this rule in `desktop/CLAUDE.md`.

**4. Per-project WKWebViewConfiguration** — each project gets its own `WKWebViewConfiguration` with `WKWebsiteDataStore.nonPersistent()` (ephemeral storage). Prevents cross-project cookie/sessionStorage leakage if two projects end up on the same port (sequential use, port reuse). Memory cost is negligible.

**5. Settings entry point interception** — in embedded mode, any in-app route to Settings (gear icon, `Cmd+,`, any "Settings" link) must be intercepted. The web layer posts `project-action: { action: 'open-settings' }` via the bridge, and the native `Settings` scene opens. Prevents two Settings surfaces (native window + web modal).

### Serve-side security hardening

These affect the Python `bristlenose serve` layer. Should be implemented regardless of desktop/CLI mode.

**1. Restrict `/media` mount** — currently `StaticFiles(directory=project_dir)` serves the ENTIRE project directory, including `.bristlenose/bristlenose.db`, `bristlenose-output/people.yaml`, and transcript files. Any localhost process can download the participant database. Fix: either (a) serve from a dedicated `media/` subdirectory, or (b) add middleware that filters by file extension (`.mp4`, `.mov`, `.wav`, `.mp3`, `.m4a`, `.webm`, `.mkv`, `.avi`, `.flac`, `.ogg`, `.aac`, `.vtt`, `.srt`), or (c) block access to `.bristlenose/` and `bristlenose-output/` paths explicitly.

**2. Add CORS middleware** — `CORSMiddleware(allow_origins=["http://127.0.0.1"])`. Defence-in-depth against the "Open in Browser" escape hatch. Without CORS, any browser tab can read API responses via simple GET requests. With CORS, the browser blocks cross-origin reads.

**3. Localhost auth token** (future consideration) — generate a random token at serve startup, pass it to WKWebView via `WKUserScript`, require it as a header on all API requests. Prevents other localhost processes from accessing the API. Not essential for v0.1 "five friends" but recommended before wider distribution.

### Resolved design decisions (from UX review)

These were flagged as open questions. Now answered:

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Serve instance lifecycle | One process per active project, `ServeManager` observable. See section above | Simplest model that works. Reference-counted for multi-window |
| 2 | Pipeline failure state | Red exclamation badge on sidebar row, click for error sheet with Retry/Copy Error/View Partial | Stays out of the way, doesn't block other projects |
| 3 | Concurrent pipeline runs | One at a time for v1. Sidebar badge shows which project is running. Starting a second queues it | Concurrent pipelines are complex (CPU/GPU contention, multiple LLM streams). Queue is simple, clear |
| 4 | `projects.json` location | Desktop: `~/Library/Application Support/Bristlenose/`. CLI: `~/.config/bristlenose/`. Separate files, no merge | Sandbox guardrails say keep them separate. Desktop users rarely use CLI. If they do, they manage two lists. Merge is a future problem |
| 5 | WKWebView state on project switch | Accept the loss for v1. State (scroll position, filters, selections) resets on switch | Simple, predictable. Save/restore via bridge is P2 polish if users complain |
| 6 | `Cmd+F` routing | Web search bar wins. Suppress native `WKWebView.find()` by not forwarding the key event to the web view's default handler — intercept in the menu item and call `evaluateJavaScript("window.__bristlenose.menuAction('find')")` | Web search is richer (quotes, tags, speakers). Native find bar only does text matching |
| 7 | Theme sync | WKWebView inherits system `prefers-color-scheme` automatically — no injection needed for system-level dark mode. The View menu "Dark Mode / Light Mode" toggle sets `NSApp.appearance` on the window, which WKWebView respects | Tested by other WKWebView apps. If it doesn't work in practice, fall back to `evaluateJavaScript` injection |
| 8 | Add Tag shortcut | `Cmd+Shift+T` — closest to `Cmd+T` without conflicting with Show Fonts. Not ideal, but functional. Revisit after user testing | `Cmd+D` conflicts with "Add Bookmark" muscle memory. `Ctrl+T` violates the "avoid Control" HIG guideline |

### v0.1 → v1 transition

Same app, same bundle ID. v1 replaces v0.1 as an update (`.dmg` swap or auto-update via Sparkle).

**What changes for existing v0.1 users:**
- Reports now open inside the app (WKWebView) instead of the system browser
- Multi-project sidebar replaces the single-project folder picker
- Existing project folders are auto-imported on first v1 launch (scan `~/Library/Application Support/Bristlenose/` for known project paths, create bookmarks)

**Escape hatch:** Project menu > "Open in Browser" launches `open http://localhost:N/report/` for users who prefer the browser workflow. This is a convenience, not a primary path.

**No data migration needed:** v0.1 writes `.bristlenose/` and `bristlenose-output/` inside the user's project folder. v1 reads the same files. The only new data is `projects.json` (project index), which v1 creates fresh.

### Native Settings window

SwiftUI `Settings` scene — proper window, `Cmd+,`, native controls. Changes apply immediately (no Save button). The web `SettingsModal` becomes dead code in embedded mode.

**Layout:** Grid of icons at top (Panic Nova pattern), sections drill down:

```
┌─ Settings ──────────────────────────────────────┐
│  🔧 General    🤖 Models    🔒 Privacy          │
├─────────────────────────────────────────────────┤
│                                                 │
│  General                                        │
│  ─────────                                      │
│  Default tab on project open    [Project ▾]     │
│  Quote density                  [Comfortable ▾] │
│  Theme                          [System ▾]      │
│  Animation speed                [━━━●━━━]       │
│                                                 │
│  Models                                         │
│  ─────────                                      │
│  Provider                       [Claude ▾]      │
│  API key                        [••••••••]  🔑  │
│  Model                          [Opus 4 ▾]      │
│  Local model URL                [localhost:11434]│
│                                                 │
│  Privacy                                        │
│  ─────────                                      │
│  PII redaction                  [On / Off]      │
│  Default anonymisation          [On / Off]      │
│  ☑ Remove PII from LLM prompts                 │
│                                                 │
└─────────────────────────────────────────────────┘
```

Settings stored via `@AppStorage` (UserDefaults) for native values, Keychain for API keys (already implemented — `docs/design-keychain.md`). The web layer reads settings via a bridge query (`window.__bristlenose.getSettings()`) or the serve API.

### Print behaviour

File menu > Print (`Cmd+P`) calls `webView.printOperation(with:)` — prints the current WKWebView content using the web layer's existing `@media print` CSS (already used by export). No custom print dialog for v1. The user gets whatever the current tab shows, formatted for print.

### Priority order

1. **P0 — Architectural** (before any code): Serve instance lifecycle, history model, embedded detection, keyboard shortcut split, 2-column layout, bridge protocol namespace, NSURL bookmark storage (required for App Store sandbox)
2. **P1 — Sidebar + native chrome**: Collapse behaviour, toggle animation, row content, section headers, empty state, add button, context menus, native Settings window (`Cmd+,`), shared find pasteboard, embedded font sizing (13pt)
3. **P2 — Polish**: Badges, row height, divider, search, drag-drop, Video menu, popped-out windows
4. **Post-v1**: `Cmd+K` command palette, cross-project search, Quick Look extension, AppleScript/Shortcuts integration, MPNowPlayingInfoCenter media key integration

### Files involved

**Modify:**
- `frontend/src/layouts/AppLayout.tsx` — conditional NavBar/Footer/Header suppression when `__BRISTLENOSE_EMBEDDED__`
- `frontend/src/main.tsx` — embedded mode detection (4th rendering mode)

**Create (future):**
- `desktop/Bristlenose/Views/ProjectSidebar.swift` — native sidebar with project list, folders, smart sections
- `desktop/Bristlenose/Views/WebContentView.swift` — WKWebView wrapper with script message handlers
- `desktop/Bristlenose/Model/ProjectStore.swift` — `projects.json` read/write, `ObservableObject`
- `frontend/src/shims/native-bridge.ts` — `WKScriptMessageHandler` posting for route changes
