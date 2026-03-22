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

**Inbound** (web → native): `WKScriptMessageHandler` receives messages from `window.webkit.messageHandlers.navigation.postMessage(...)`. Types: `ready`, `route-change`, `editing-started`, `editing-ended`, `project-action`.

**Outbound** (native → web): `BridgeHandler` holds a `weak var webView: WKWebView?` (set in `WebView.makeNSView`). Three outbound methods:
- `goBack()` / `goForward()` — delegates to `webView?.goBack()` / `.goForward()`
- `switchToTab(_ tab: Tab)` — calls `callAsyncJavaScript("window.switchToTab(tab)", arguments: ["tab": tab.rawValue], in: nil, in: .page)`

The `callAsyncJavaScript` parameter labels are `in: nil, in: .page` — not `contentWorld:`. Content world `.page` is required because `window.switchToTab` is installed by page-level JS (the navigation shim), not a `WKUserScript`.

### Toolbar

Three zones in the unified title bar:

```
┌─────────────────────────────────────────────────────────────────────┐
│ ● ● ●  ⊞  ◀ ▶  │  Project · Sessions · Quotes · Codebook · Analysis  │  Q1 Study  │
│ leading         │  centre (segmented control)                          │  trailing  │
└─────────────────────────────────────────────────────────────────────┘
```

- **Leading** (`.navigation`): back/forward buttons with KVO-driven enable/disable
- **Centre** (`.principal`): segmented `Picker` bound to `bridgeHandler.activeTab` via a two-way `Binding<Tab>` (nil mapped to `.project` — segmented Picker requires non-optional)
- **Trailing**: `.navigationTitle(selectedProject?.name ?? "Bristlenose")`

Keyboard shortcuts: Cmd+1-5 (tabs) and Cmd+Opt+S (sidebar) live in `.commands {}` on the Scene (creates proper menu items, VoiceOver-discoverable). Cmd+[/] (back/forward) live as `.keyboardShortcut` on toolbar buttons.

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
