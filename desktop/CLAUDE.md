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
ServeManager.swift            Process lifecycle + startup zombie cleanup
WebView.swift                 WKWebView + security policy + KVO observations
KeychainHelper.swift          Credential storage via macOS Keychain
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

**Inbound** (web → native): `WKScriptMessageHandler` receives messages from `window.webkit.messageHandlers.navigation.postMessage(...)`. Types: `ready`, `route-change`, `editing-started`, `editing-ended`, `focus-change`, `undo-state`, `player-state`, `project-action`.

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
- **Codebook**: Tags panel toggle (`tag` icon)
- **Analysis**: Inspector panel toggle (`rectangle.bottomhalf.inset.filled`)
- **Other tabs**: no extra items

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
- **Undo/Redo editing guard** — when `isEditing`, the Undo/Redo menu items are hidden (not disabled) so Cmd+Z falls through to WKWebView's character-level text undo. When not editing, they intercept and route to the bridge
