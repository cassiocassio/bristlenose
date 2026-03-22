# Desktop App — macOS Shell

SwiftUI macOS app wrapping the Bristlenose React SPA in a WKWebView. Native project sidebar, native Settings window, web content in embedded mode.

## Architecture

```
BristlenoseApp.swift          @main — WindowGroup + Settings scene
  └─ ContentView.swift        NavigationSplitView (sidebar + detail)
       ├─ ServeManager        Spawns bristlenose serve, monitors stdout
       ├─ BridgeHandler        Receives bridge messages from React SPA
       └─ WebView.swift        WKWebView wrapper (NSViewRepresentable)
            └─ Coordinator     WKScriptMessageHandler + WKNavigationDelegate
```

- **ServeManager** starts `bristlenose serve --no-open --port N <path>` as a Foundation `Process`. Detects readiness from `"Report: http://..."` in stdout, then polls the TCP port until it accepts connections before transitioning to `.running`.
- **BridgeHandler** receives messages posted by the React SPA via `window.webkit.messageHandlers.navigation.postMessage(...)`. Five message types: `ready`, `route-change`, `editing-started`, `editing-ended`, `project-action`.
- **WebView** injects `window.__BRISTLENOSE_EMBEDDED__ = true` via `WKUserScript` at `.atDocumentStart`. The React SPA checks this flag to suppress NavBar/Footer/Header.

## Security rules

1. **Navigation restriction** — `decidePolicyFor` allows only `127.0.0.1` and `about:`. External URLs open in system browser via `NSWorkspace.shared.open()`.
2. **Bridge origin validation** — every `WKScriptMessageHandler` callback checks `message.frameInfo.request.url?.host == "127.0.0.1"`.
3. **No string interpolation into JavaScript** — use `callAsyncJavaScript(_:arguments:)` for native→web calls. Never concatenate user data into `evaluateJavaScript` strings. A project named `'; alert(1); '` must not become code execution.
4. **Ephemeral storage** — each project gets `WKWebsiteDataStore.nonPersistent()` to prevent cross-project cookie/sessionStorage leakage.
5. **Settings interception** — `project-action: open-settings` opens the native Settings scene, not the web modal.

## Port allocation

`8150 + djb2(projectPath) % 1000` — deterministic per project path, range 8150–9149. If the computed port is busy, tries up to 10 consecutive ports. Swift's `String.hashValue` is randomized per process (since Swift 4.2), so we use a stable djb2 hash instead.

## Key conventions

- **macOS 15.0** (Sequoia) deployment target
- **Swift 6 concurrency** — `SWIFT_DEFAULT_ACTOR_ISOLATION = nonisolated` in build settings. Mark classes `@MainActor` explicitly.
- **`@StateObject`** for ObservableObject classes in SwiftUI views (not `@State`)
- **SIGINT** (not SIGTERM) for graceful serve shutdown — lets Uvicorn release the port
- **Sandbox disabled** (`ENABLE_APP_SANDBOX = NO`) — needed for subprocess spawning and localhost network access

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
- **Zombie serve processes** — if the app crashes without calling `stop()`, the Python serve process keeps running on the port. Check with `lsof -i :8150-9150 -P -n | grep LISTEN`
- **`Report:` readiness signal** — `bristlenose serve` prints this BEFORE Uvicorn accepts connections. The port-polling step in ServeManager handles the race
- **Bridge code on main vs feature branch** — the `macos-app` branch has the bridge shims in `frontend/src/shims/bridge.ts`. The main branch build served by `bristlenose serve` won't post `ready` messages. The `didFinish` fallback in WebView handles this (shows content after 2s timeout)
