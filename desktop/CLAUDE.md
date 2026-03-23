# Desktop App — macOS Shell

SwiftUI macOS app wrapping the Bristlenose React SPA in a WKWebView. Native project sidebar, native toolbar, native Settings window, web content in embedded mode.

## Architecture

```
BristlenoseApp.swift          @main — WindowGroup + Settings scene
  ├─ @StateObject serveManager    Owns ServeManager (app-level, not view-level)
  ├─ @StateObject bridgeHandler   Owns BridgeHandler (app-level, not view-level)
  ├─ .commands { MenuCommands }   Full native menu bar (10 menus, ~89 items)
  ├─ .onReceive(willTerminate)    Calls serveManager.stop() on Cmd+Q
  └─ ContentView.swift            NavigationSplitView (sidebar + detail)
       ├─ @EnvironmentObject      Receives serveManager + bridgeHandler
       ├─ .toolbar {}             Back/forward + tabs + contextual trailing items
       ├─ ExportMenuButton        Per-tab export dropdown (toolbar)
       └─ WebView.swift           WKWebView wrapper (NSViewRepresentable)
            └─ Coordinator        WKScriptMessageHandler + WKNavigationDelegate + KVO

MenuCommands.swift            Commands struct + per-menu View structs
Tab.swift                     Tab enum — route mapping, path→tab derivation
BridgeHandler.swift           Inbound state + outbound actions + menuAction dispatch
ServeManager.swift            Process lifecycle + startup zombie cleanup + prefs overlay
WebView.swift                 WKWebView + security policy + KVO observations
KeychainHelper.swift          Credential storage via macOS Keychain
LLMProvider.swift             Provider enum + ProviderStatus enum + notification name
SettingsView.swift            TabView wrapper (3 icon tabs)
AppearanceSettingsView.swift  Theme radio + language dropdown
LLMSettingsView.swift         Mail Accounts pattern — provider list + detail pane
TranscriptionSettingsView.swift  Whisper backend + model pickers
```

### State ownership

`ServeManager` and `BridgeHandler` are `@StateObject` at the **App level** (not ContentView). This is required because:
- `.commands {}` needs `bridgeHandler` to dispatch tab switches
- `.onReceive(willTerminateNotification)` needs `serveManager` to kill zombies
- Both are passed to ContentView via `.environmentObject()`

ContentView uses `@EnvironmentObject` — it does not own these objects.

### Tab enum and route mapping

`Tab.swift` defines the 5 toolbar tabs: `project`, `sessions`, `quotes`, `codebook`, `analysis`. Raw values match `TAB_ROUTES` keys in `frontend/src/shims/navigation.ts`.

`Tab.from(path:)` derives the active tab from a URL path using prefix matching. Order matters — longest prefixes checked first so `/report/sessions/abc123` maps to `.sessions`, not `.project`. The project tab uses exact match (`== "/report/"`) to avoid swallowing all paths.

### Bridge communication

**Inbound** (web → native): `WKScriptMessageHandler` receives messages from `window.webkit.messageHandlers.navigation.postMessage(...)`. Types: `ready`, `route-change`, `editing-started`, `editing-ended`, `focus-change`, `undo-state`, `player-state`, `project-action`, `find-pasteboard-write`.

**Outbound** (native → web): `BridgeHandler` holds a `weak var webView: WKWebView?` (set in `WebView.makeNSView`). Four outbound methods:
- `goBack()` / `goForward()` — delegates to `webView?.goBack()` / `.goForward()`
- `switchToTab(_ tab: Tab)` — calls `callAsyncJavaScript("window.switchToTab(tab)", ...)`
- `menuAction(_ action: String, payload:)` — calls `callAsyncJavaScript("window.__bristlenose.menuAction(action, payload)", ...)`. Single dispatch point for all ~89 menu actions (security rule 3 — structured arguments, no string interpolation)

The `callAsyncJavaScript` parameter labels are `in: nil, in: .page` — not `contentWorld:`. Content world `.page` is required because `window.switchToTab` and `window.__bristlenose.menuAction` are installed by page-level JS, not a `WKUserScript`.

### Toolbar

Four zones in the unified title bar:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ ● ● ●  ⊞  ◀ ▶  │  Project · Sessions · Quotes · Codebook · Analysis  │  🔍 ↑ [ctx]  │
│ leading         │  centre (segmented control)                          │  trailing     │
└──────────────────────────────────────────────────────────────────────────────────┘
```

- **Leading** (`.navigation`): back/forward buttons with KVO-driven enable/disable
- **Centre** (`.principal`): segmented `Picker` bound to `bridgeHandler.activeTab` via a two-way `Binding<Tab>` (nil mapped to `.project` — segmented Picker requires non-optional)
- **Trailing** (`.primaryAction`): contextual items that morph per tab — see "Toolbar morphing" below
- **Title**: `.navigationTitle(selectedProject?.name ?? "Bristlenose")`

Keyboard shortcuts: Cmd+1-5 (tabs) and Cmd+Opt+S (sidebar) live in the View menu (via `MenuCommands`). Cmd+[/] (back/forward) live as `.keyboardShortcut` on toolbar buttons.

### Toolbar morphing

**Principle: menus dim, toolbars morph.** The menu bar greys out unavailable items (HIG — discoverability). The toolbar shows/hides items per tab (Photos/Notes pattern — no greyed-out button graveyard).

**Universal items** (always present):
- **Search** (magnifying glass) — active on Quotes tab, dimmed elsewhere as "coming soon"
- **Export** (share icon) — dropdown `Menu` whose contents change per tab. Always has "Export Report..." first. Quotes tab adds "Export Quotes as CSV"

**Per-tab contextual items** (appear/disappear):
- **Quotes/Codebook/Analysis**: `ControlGroup` pill with two buttons — left (`sidebar.left`) toggles native project sidebar via `NSSplitViewController.toggleSidebar`, right (`list.bullet`) toggles web navigation sidebar (sections/themes, codebooks, signals) via `bridgeHandler.menuAction("toggleLeftPanel")`
- **Quotes**: Tag sidebar toggle (`sidebar.right` icon)
- **Analysis**: Heatmap inspector toggle (`square.grid.2x2` icon)
- **Project/Sessions**: no extra items

`ExportMenuButton` is a `View` struct in `ContentView.swift` that observes `bridgeHandler.activeTab` to render the correct menu items.

### Menu bar

`MenuCommands.swift` — full native menu bar with 10 menus and ~89 items.

**`View`-inside-`Commands` pattern:** `@ObservedObject` is unreliable directly in `Commands.body` (observation doesn't trigger re-evaluation). `MenuCommands` holds a plain `let bridgeHandler`. Each menu section is a `View` struct (`QuotesMenuContent`, `VideoMenuContent`, etc.) that owns `@ObservedObject var bridgeHandler` — views inside `CommandMenu`/`CommandGroup` follow normal SwiftUI view lifecycle.

**Contextual dimming** — menus dim unavailable items (never hide):
- Quotes menu: all items dim when not on Quotes tab. Star/Hide/Tag additionally require `focusedQuoteId != nil`
- Video menu: all items dim when `!hasPlayer`. Play/Pause label swaps
- Codes menu: group/code operations dim when not on codebook/quotes tab. Browse/Import always enabled
- Edit > Undo/Redo: hidden when `isEditing` (lets WKWebView handle character-level undo)
- View > panels: dim based on active tab

**Responder chain rules:**
- Do NOT touch `.pasteboard` — Cut/Copy/Paste handled by WKWebView responder chain
- Undo/Redo hidden during `isEditing` to let Cmd+Z fall through to WKWebView
- Cmd+F routes to web search bar (not native WKWebView find bar)
- Settings Cmd+, comes from the `Settings {}` scene automatically — no custom menu item

**No bare-key menu shortcuts** — `s`, `h`, `[`, `]`, `m`, `?`, arrows work only in WKWebView focus. Menu items for these actions have no keyboard shortcut shown. Help menu points to `?` for the full shortcut reference.

### KVO for back/forward

`WebView.Coordinator` stores two `NSKeyValueObservation` properties observing `webView.canGoBack` and `webView.canGoForward`. KVO callbacks dispatch to `bridgeHandler.canGoBack`/`.canGoForward` via `Task { @MainActor in }`. Observations are auto-invalidated when the Coordinator deallocates (triggered by `.id(project.id)` on project switch).

### Zombie process cleanup

Two layers:

1. **Clean quit**: `.onReceive(NSApplication.willTerminateNotification)` on the root View calls `serveManager.stop()` (SIGINT).
2. **Crash recovery**: `ServeManager.init()` runs `killOrphanedServeProcesses()` — a nonisolated static method that calls `lsof -ti :8150-9149` to find PIDs, then `kill(pid, SIGINT)` each one. Runs synchronously (~10ms), safe at startup.

Gap: Xcode's stop button sends SIGKILL which bypasses `willTerminate`. The startup cleanup catches these on next launch.

## Settings window (Cmd+,)

Apple canonical `Settings` scene with 3 icon tabs. Constant width (660pt) across all tabs, height animates to fit content.

### Tab 1: Appearance (paintbrush)

Theme radio group (auto/light/dark) + language dropdown (6 locales). `@AppStorage("appearance")` drives `.preferredColorScheme` on both the main window and Settings window. Appearance is also synced to the web layer via `BridgeHandler.syncAppearance()` on `ready` — native wins, web Settings modal hides its appearance picker in embedded mode.

### Tab 2: LLM (brain) — Mail Accounts pattern

Left sidebar list of 5 pre-populated providers (Claude, ChatGPT, Gemini, Azure, Ollama) with two orthogonal indicators per row:
- **Radio/checkmark** — which provider is active (user choice, `@AppStorage("activeProvider")`)
- **Status dot** — whether the provider is configured (green "Online" / grey "Not set up" / red "Invalid" / orange "Unavailable")

Right detail pane shows the selected provider's settings: API key (`SecureField` → Keychain via `KeychainHelper`), model picker (per-provider known models + "Custom…"), temperature slider, concurrency slider. Azure adds endpoint/deployment/version fields. Ollama shows URL instead of API key.

**Activation guard**: a provider cannot be activated (radio or toggle) unless its status is `.online`. You can select a provider in the sidebar to set it up, but the radio stays greyed out until a valid key is entered. One provider must always be active.

**Per-provider model storage**: `UserDefaults` key `llmModel_{provider}` stores each provider's selected model. When a provider becomes active, its model is written to the global `llmModel` key for ServeManager.

### Tab 3: Transcription (waveform)

Whisper backend picker (Auto/MLX/faster-whisper) + model picker (large-v3-turbo through tiny). `@AppStorage` for both.

### Preferences → serve process

`ServeManager.overlayPreferences()` reads `UserDefaults` and injects values as environment variables into the `Process.environment` dictionary before launching `bristlenose serve`. API keys don't need env var pass-through — Python's `MacOSCredentialStore` reads Keychain directly.

`ServeManager` subscribes to `Notification.Name.bristlenosePrefsChanged`. When any settings view posts this notification and a serve process is running, `restartIfRunning()` stops and re-starts with the new environment.

| Setting | UserDefaults key | Env var |
|---------|-----------------|---------|
| Active provider | `activeProvider` | `BRISTLENOSE_LLM_PROVIDER` |
| Model | `llmModel` | `BRISTLENOSE_LLM_MODEL` |
| Temperature | `llmTemperature` | `BRISTLENOSE_LLM_TEMPERATURE` |
| Concurrency | `llmConcurrency` | `BRISTLENOSE_LLM_CONCURRENCY` |
| Whisper backend | `whisperBackend` | `BRISTLENOSE_WHISPER_BACKEND` |
| Whisper model | `whisperModel` | `BRISTLENOSE_WHISPER_MODEL` |
| Language | `language` | `BRISTLENOSE_WHISPER_LANGUAGE` |
| Azure endpoint | `azureEndpoint` | `BRISTLENOSE_AZURE_ENDPOINT` |
| Azure deployment | `azureDeployment` | `BRISTLENOSE_AZURE_DEPLOYMENT` |
| Azure API version | `azureAPIVersion` | `BRISTLENOSE_AZURE_API_VERSION` |
| Ollama URL | `localURL` | `BRISTLENOSE_LOCAL_URL` |
| Appearance | `appearance` | *(bridge, not env)* |
| API keys | **Keychain** | *(Python reads directly)* |

### Provider status model

`ProviderStatus` in `LLMProvider.swift` — normalised account status:

| Status | Dot | Detection |
|--------|-----|-----------|
| `.online` | Green | Key valid (2xx test call) or Ollama reachable |
| `.notSetUp` | Grey | No key in Keychain |
| `.invalid` | Red | 401/403 from test call |
| `.unavailable` | Orange | 402/429/network error |
| `.checking` | Grey | Validation in progress |

Status is orthogonal to active selection. Providers don't expose balance, free-tier, or trial status via API — we report only what we can detect.

## Security rules

1. **Navigation restriction** — `decidePolicyFor` allows only `127.0.0.1` and `about:`. External URLs open in system browser via `NSWorkspace.shared.open()`.
2. **Bridge origin validation** — every `WKScriptMessageHandler` callback checks `message.frameInfo.request.url?.host == "127.0.0.1"`.
3. **No string interpolation into JavaScript** — use `callAsyncJavaScript(_:arguments:in:in:)` for native→web calls. Never concatenate user data into `evaluateJavaScript` strings. A project named `'; alert(1); '` must not become code execution.
4. **Ephemeral storage** — each project gets `WKWebsiteDataStore.nonPersistent()` to prevent cross-project cookie/sessionStorage leakage.
5. **Settings interception** — `project-action: open-settings` opens the native Settings scene, not the web modal.

## Port allocation

`8150 + djb2(projectPath) % 1000` — deterministic per project path, range 8150–9149. If the computed port is busy, tries up to 10 consecutive ports. Swift's `String.hashValue` is randomized per process (since Swift 4.2), so we use a stable djb2 hash instead.

## Key conventions

- **macOS 15.0** (Sequoia) deployment target
- **Swift 6 concurrency** — `SWIFT_DEFAULT_ACTOR_ISOLATION = nonisolated` in build settings. Mark classes `@MainActor` explicitly
- **`@StateObject`** at App level for ServeManager/BridgeHandler, `@EnvironmentObject` in views
- **SIGINT** (not SIGTERM) for graceful serve shutdown — lets Uvicorn release the port
- **Sandbox disabled** (`ENABLE_APP_SANDBOX = NO`) — needed for subprocess spawning and localhost network access
- **`callAsyncJavaScript` param labels**: `in: nil, in: .page` — the two `in` parameters are frame and content world respectively

## Files scavenged from v0.1

- `KeychainHelper.swift` — verbatim copy, `security` CLI wrapper matching Python's `MacOSCredentialStore`
- `Assets.xcassets/` — app icon and accent colour
- Pipe reading pattern from `ProcessRunner.swift` — `Task.detached` + `fileHandle.availableData` loop
- ANSI escape stripping regex

## Build

```bash
# CLI build (uses xcodebuild)
cd desktop/Bristlenose
xcodebuild build -scheme Bristlenose -configuration Debug -destination "platform=macOS"

# Or open in Xcode and Cmd+R
open desktop/Bristlenose/Bristlenose.xcodeproj
```

The Xcode project uses `PBXFileSystemSynchronizedRootGroup` — Swift files added to `desktop/Bristlenose/Bristlenose/` are auto-discovered. No need to manually add them to the project.

## Frontend build requirement

`bristlenose serve` needs the React bundle built into `bristlenose/server/static/`. If you see "React bundle not found" warnings:

```bash
cd frontend && npm run build
```

## Gotchas

- **Xcode stale indexer** — sometimes shows "no member" errors that `xcodebuild` doesn't. Fix: `Cmd+Shift+K` (Clean Build Folder) then `Cmd+R`
- **Zombie serve processes** — if the app crashes without calling `stop()`, the Python serve process keeps running on the port. Check with `lsof -i :8150-9150 -P -n | grep LISTEN`. Next app launch cleans these up automatically (startup zombie cleanup in ServeManager.init)
- **`Report:` readiness signal** — `bristlenose serve` prints this BEFORE Uvicorn accepts connections. The port-polling step in ServeManager handles the race
- **Bridge code on main vs feature branch** — the `macos-app` branch has the bridge shims in `frontend/src/shims/bridge.ts`. The main branch build served by `bristlenose serve` won't post `ready` messages. The `didFinish` fallback in WebView handles this (shows content after 2s timeout)
- **Segmented Picker requires non-optional selection** — `Binding<Tab?>` doesn't work with `.pickerStyle(.segmented)`. The `tabBinding` in ContentView maps nil to `.project`
- **Tab.from(path:) prefix order** — check longest prefixes first (`/report/analysis` before `/report/`). The project tab uses exact match to avoid matching all paths
- **`.onReceive` is a View modifier, not Scene** — attach it to the root View inside WindowGroup, not to the WindowGroup itself. The publisher is `NotificationCenter.default.publisher(for: NSApplication.willTerminateNotification)`
- **`@ObservedObject` in `Commands` struct is unreliable** — use `let` (plain property) on the `Commands` struct, then use `@ObservedObject` inside `View` structs that are the content of `CommandMenu`/`CommandGroup`. See `MenuCommands.swift` for the pattern
- **Don't replace `.pasteboard` in Commands** — `CommandGroup(replacing: .pasteboard)` removes Cut/Copy/Paste. WKWebView handles these via the responder chain. Only replace `.undoRedo` (for app-level undo) and `.help`
- **Undo/Redo editing guard** — when `isEditing`, the Undo/Redo menu items are hidden (not disabled) so Cmd+Z falls through to WKWebView's character-level text undo. When not editing, they intercept and route to the bridge. **Known HIG deviation:** this violates the "dim, never hide" menu principle (line 99). Hiding is necessary here because a disabled Cmd+Z menu item would still intercept the shortcut before it reaches WKWebView's responder chain — dimming prevents the key from falling through. Acceptable trade-off: character-level undo during text editing is more important than menu discoverability
- **`@AppStorage` not `@SceneStorage` for project selection** — `selectedProjectPath` uses `@AppStorage` so the last-opened project persists across app launches. `@SceneStorage` doesn't survive relaunch for unsigned/debug-signed apps (macOS state restoration requires proper code signing). Xcode debug runs also reset scene storage between launches. Use `@AppStorage` for anything that must persist across relaunches
- **Web Inspector** — enabled via `webView.isInspectable = true` in `#if DEBUG` builds only. Right-click → Inspect Element works in debug builds for diagnosing bridge/CSS issues

## Wiring menu actions (bridge handler cookbook)

### The 3-file chain

Every menu action follows the same path:

```
MenuCommands.swift                    → bridgeHandler.menuAction("find")
  ↓ callAsyncJavaScript
bridge.ts                             → window.dispatchEvent(CustomEvent("bn:menu-action"))
  ↓ event listener
AppLayout.tsx (or useKeyboardShortcuts) → React store call / DOM action
```

**Swift side is complete** — all ~65 menu actions call `bridgeHandler.menuAction(...)`. Two frontend listeners handle them:
- **`AppLayout.tsx`** — panel toggles, find actions, and modal/export actions (things that need AppLayout state)
- **`useKeyboardShortcuts.ts`** — quote/player actions (things that need FocusContext/QuotesContext closures)

### Adding a new handler

1. **No Swift changes needed** — the menu item already dispatches via `bridgeHandler.menuAction("actionName")`
2. **Choose the right listener** — if the handler needs FocusContext/QuotesContext/PlayerContext, add it to `useKeyboardShortcuts.ts`'s `handleMenuAction` switch. Otherwise add it to `AppLayout.tsx`'s `bn:menu-action` handler
3. **Delegate to existing logic** — most actions already have implementations in `useKeyboardShortcuts.ts` or React stores

### Action catalogue

#### Already handled — AppLayout (8 actions)

| Action | Handler |
|--------|---------|
| `toggleLeftPanel` | `sidebarAnimations.toggleToc()` |
| `toggleRightPanel` | `sidebarAnimations.toggleTags()` |
| `toggleInspectorPanel` | `toggleInspector()` |
| `find` | Focus search input (expand + focus + select) |
| `useSelectionForFind` | Selection → search query + find pasteboard write |
| `findNext` | Find pasteboard text (from payload) → search query |
| `findPrevious` | Find pasteboard text (from payload) → search query |
| `jumpToSelection` | No-op (WKWebView native) |

#### Already handled — useKeyboardShortcuts (12 actions)

These are in the `handleMenuAction` switch inside `useKeyboardShortcuts.ts`, sharing closures with the keyboard handlers.

| Action | Handler |
|--------|---------|
| `star` | `handleStar()` — bulk-aware (uses focused/selected) |
| `hide` | `handleHide()` — bulk-aware, moves focus after |
| `addTag` | `handleTagOpen()` — opens TagInput on focused quote |
| `applyLastTag` | `handleQuickApply()` — quick-apply last-used tag |
| `playPause` | `handlePlay()` — seekTo via PlayerContext |
| `nextQuote` | `moveFocus(1)` |
| `previousQuote` | `moveFocus(-1)` |
| `extendSelectionDown` | `handleShiftMove(1)` |
| `extendSelectionUp` | `handleShiftMove(-1)` |
| `toggleSelection` | `toggleSelection(focusedId)` + anchor |
| `clearSelection` | `clearSelection()` |
| `revealInTranscript` | `navigate(/report/sessions/:pid#anchor)` |

#### Need new frontend implementation (14)

| Action | Implementation needed |
|--------|----------------------|
| `exportReport` | Open `ExportDialog` (`setExportOpen(true)`) |
| `exportAnonymised` | Open `ExportDialog` with anonymise pre-selected |
| `exportQuotesCSV` | Trigger CSV download (quotes API → blob) |
| `copyAsCSV` | Copy focused/selected quotes as CSV to clipboard |
| `allQuotes` | Clear search + tag filter (reset to default view) |
| `starredQuotesOnly` | Set starred-only filter |
| `filterByTag` | Focus the tag filter dropdown |
| `showHelp` | `setHelpSection("help"); setHelpOpen(true)` |
| `showKeyboardShortcuts` | `setHelpSection("shortcuts"); setHelpOpen(true)` |
| `showReleaseNotes` | `setHelpSection("release-notes"); setHelpOpen(true)` |
| `sendFeedback` | `setFeedbackOpen(true)` |
| `zoomIn` / `zoomOut` / `actualSize` | CSS `font-size` scaling or `document.body.style.zoom` |
| `toggleDarkMode` | Toggle `prefers-color-scheme` override |

#### Video player actions — need PlayerContext wiring (12)

These require the popout player bridge (currently stub: `hasPlayer: false` in `getState()`).

| Action | Player method needed |
|--------|---------------------|
| `skipForward5` / `skipBack5` | `player.currentTime ± 5` |
| `skipForward30` / `skipBack30` | `player.currentTime ± 30` |
| `speedUp` / `slowDown` / `normalSpeed` | `player.playbackRate` |
| `volumeUp` / `volumeDown` / `mute` | `player.volume` / `player.muted` |
| `pictureInPicture` | `player.requestPictureInPicture()` |
| `fullscreen` | `player.requestFullscreen()` |

#### Project operations — native-side or future (8)

These are either native-only (Finder, print) or depend on features not yet built (project list, re-analysis).

| Action | Notes |
|--------|-------|
| `revealInFinder` | Native: `NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath:)`. Needs project path from ServeManager |
| `newProject` | Future: project creation flow |
| `openInNewWindow` | Future: multi-window |
| `renameProject` / `archive` / `deleteProject` | Future: project management |
| `reAnalyse` | Future: re-run pipeline |
| `checkSystemHealth` | Navigate to `/report/` and open doctor panel (or call `/api/health`) |
| `pageSetup` / `print` | `NSPrintOperation` on WKWebView snapshot |

#### Codebook operations — need CodebookPanel wiring (10)

These dispatch to the codebook UI (browse modal, group/code CRUD). Most need `CustomEvent` dispatch to `CodebookPanel`.

| Action | Target |
|--------|--------|
| `browseCodebooks` | Dispatch `bn:codebook-browse` CustomEvent |
| `importFramework` | Dispatch `bn:codebook-browse` with pre-selected template |
| `removeFramework` | Dispatch `bn:codebook-remove` (needs framework ID context) |
| `createCodeGroup` / `renameCodeGroup` / `deleteCodeGroup` / `toggleCodeGroup` | Dispatch to codebook group CRUD |
| `createCode` / `renameCode` / `deleteCode` / `mergeCode` | Dispatch to code CRUD |

#### Edit operations — partially handled (2)

| Action | Status |
|--------|--------|
| `undo` / `redo` | Stub (`canUndo: false` in `getState()`). Needs undo store |

#### Internal (not from menu)

| Action | Notes |
|--------|-------|
| `set-appearance` | Sent by `BridgeHandler.syncAppearance()` on `ready`. Frontend applies theme |

### Payload conventions

Most actions are **stateless** — the action string is sufficient because the frontend reads current state from FocusContext/QuotesContext (which quote is focused, which are selected).

Actions that need **payloads** (the optional second argument to `menuAction`):

| Action | Payload shape | Example |
|--------|--------------|---------|
| `set-appearance` | `{ value: "dark" \| "light" \| "auto" }` | Already wired |
| `exportAnonymised` | `{ anonymise: true }` | Proposed |
| `importFramework` | `{ templateId: string }` | Proposed |
| `removeFramework` | `{ frameworkId: string }` | Proposed — needs context from native sidebar |
| `findNext` / `findPrevious` | `{ text: string }` | Wired — reads from `NSPasteboard.find` |

**Rule:** if the frontend already knows the target (focused quote, active tab), don't pass it in the payload. Payloads are for data the native side has that the web side doesn't.

### getState() stubs

`bridge.ts` `getState()` has four hardcoded stubs:

| Property | Stub value | Wired when |
|----------|-----------|------------|
| `canUndo` | `false` | Undo store ships (tracks quote edits, tag changes) |
| `canRedo` | `false` | Same |
| `hasPlayer` | `false` | PlayerContext reports popout window state to bridge |
| `playerPlaying` | `false` | PlayerContext reports playback state to bridge |

These control menu item dimming in Swift. Until wired, the Undo/Redo and Video menus will dim correctly (items disabled when stubs are `false`).

### Recommended implementation order (remaining)

1. **New frontend handlers, no new infra** — `exportReport`, `showHelp`, `showKeyboardShortcuts`, `showReleaseNotes`, `sendFeedback`, `exportQuotesCSV`, `copyAsCSV`, `exportAnonymised`, `allQuotes`, `starredQuotesOnly`, `filterByTag`, `zoomIn`/`zoomOut`/`actualSize`, `toggleDarkMode`. Add to `AppLayout.tsx` handler
2. **Codebook** — `browseCodebooks` + CRUD actions (dispatch CustomEvents to CodebookPanel)
3. **Video** — requires PlayerContext bridge (popout window ↔ native state sync)
4. **Project operations** — requires project list feature
5. **Undo/Redo** — requires undo store design
