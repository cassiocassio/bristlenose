# Desktop App — macOS Shell

SwiftUI macOS app wrapping the Bristlenose React SPA in a WKWebView. Native project sidebar, native toolbar, native Settings window, web content in embedded mode. **Alpha ships a bundled, signed PyInstaller sidecar** that runs `bristlenose serve` inside the `.app`, distributed via internal TestFlight. The current code uses **launcher-style scaffolding** (the Swift app searches the user's `$PATH` and venv directories for an installed `bristlenose` CLI rather than carrying its own) so v0.2 native-shell work could iterate without paying the bundle-sign-distribute tax on every change. Track C in Sprint 2 replaces it with the bundled sidecar.

## Shipping architecture (alpha and beyond)

See `docs/design-desktop-python-runtime.md` (to be written as part of Track C C0) for the canonical design. Summary:

- **Bundled, signed PyInstaller sidecar.** The Python `bristlenose serve` runtime ships inside `Bristlenose.app/Contents/Resources/bristlenose-sidecar/`. Every `.dylib`, `.so`, and framework inside is individually codesigned with Hardened Runtime. FFmpeg + ffprobe bundled alongside (trimmed codec set, ~25 MB). Whisper transcription model downloaded on first run to `~/Library/Application Support/Bristlenose/models/` — keeps the `.app` under ~200 MB, matches Aiko/MacWhisper/Audio Hijack UX.
- **Why sidecar, not embedded interpreter.** Long-running pipeline operations (transcription, LLM calls) must be independently killable from Activity Monitor. An embedded Python interpreter takes the SwiftUI chrome down if Python hangs — beach ball on the toolbar, force-quit the whole app. Separate process keeps that failure mode contained.
- **Single Python artefact.** Same `bristlenose serve` code path ships via Homebrew/Snap/pip for CLI users and via the `.app` for desktop users. No fork.
- **Apple-supported pattern.** Apple Developer Support recognises three App-Store-supported Python architectures (pure-Python wrapper via Briefcase, sidecar via IPC, embedded interpreter via PythonKit). Sidecar is documented and shippable.
- **App Sandbox on, Hardened Runtime on** for Release / TestFlight. Debug builds may relax either to speed iteration.

**Development history:** v0.1 (Feb 2026, in `desktop/v0.1-archive/`) proved the bundling pipeline end-to-end with a one-shot `bristlenose run` wizard. v0.2 (Mar 2026 onwards, this codebase) rebuilt the native shell — NavigationSplitView workspace, WKWebView, native sidebar/menu/settings — using the simpler launcher pattern so the native work could iterate without the bundle-sign-distribute tax on every change. Alpha recombines them: v0.2's native shell + v0.1's bundling pipeline, adapted to the long-lived `bristlenose serve` lifecycle.

## Current state vs target state

| | Current (v0.2, dev only) | Target (alpha, TestFlight) |
|---|---|---|
| Python runtime | Mode resolved once at `ServeManager.init` via `SidecarMode.resolve`; three Xcode schemes wrap Debug-only env vars (`BRISTLENOSE_DEV_SIDECAR_PATH`, `BRISTLENOSE_DEV_EXTERNAL_PORT`). Default scheme uses bundled path but expects the bundle to be present. | Bundled: `SidecarMode.resolve` returns `.bundled(path:)` pointing at `Bundle.main.resourceURL/bristlenose-sidecar/bristlenose-sidecar`. Release builds physically exclude the dev env-var reads. |
| Sandbox | `ENABLE_APP_SANDBOX = NO` (dev convenience) | On, with a minimal entitlement set enumerated by the C0 spike |
| Hardened Runtime | Off | `--options=runtime` at codesign time |
| Signing | Xcode automatic (ad-hoc / dev identity) | Apple Distribution cert + per-binary signing of every dylib/so/framework inside the PyInstaller bundle |
| FFmpeg | User-installed, found via `$PATH` | Bundled at `Contents/Resources/bin/ffmpeg`, trimmed codecs |
| Whisper model | User-installed or downloaded by the CLI | First-run download to Application Support |
| Keychain access (Python side) | `/usr/bin/security` CLI via subprocess (works fine under non-sandboxed CLI Mac distros; blocked under App Sandbox) | **Not reached** — Swift host fetches keys via Security.framework at sidecar launch and injects as `BRISTLENOSE_*_API_KEY` env vars (C3, Apr 2026). `credentials_macos.py` stays as-is for CLI Mac users; sandboxed sidecar never reaches it because env vars satisfy the fallback chain earlier. |
| Ollama integration | Shells out to `ollama` binary | HTTP-only detection against user-configured `localURL` |
| Distribution | Cmd+R in Xcode on Martin's Mac | Internal TestFlight (up to 100 invited testers) |

## Architecture (SwiftUI layer)

```
BristlenoseApp.swift          @main — WindowGroup + Settings scene
  ├─ @StateObject serveManager    Owns ServeManager (app-level, not view-level)
  ├─ @StateObject bridgeHandler   Owns BridgeHandler (app-level, not view-level)
  ├─ @StateObject projectIndex    Owns ProjectIndex (app-level, not view-level)
  ├─ .commands { MenuCommands }   Full native menu bar (10 menus, ~89 items)
  ├─ .onReceive(willTerminate)    Calls serveManager.stop() on Cmd+Q
  └─ ContentView.swift            NavigationSplitView (sidebar + detail)
       ├─ @EnvironmentObject      Receives serveManager + bridgeHandler + projectIndex
       ├─ .toolbar {}             Back/forward + tabs + contextual trailing items
       ├─ ExportMenuButton        Per-tab export dropdown (toolbar)
       └─ WebView.swift           WKWebView wrapper (NSViewRepresentable)
            └─ Coordinator        WKScriptMessageHandler + WKNavigationDelegate + WKUIDelegate + KVO
                 └─ popoutWindow  NSWindow with WKWebView for video player (created by WKUIDelegate)

MenuCommands.swift            Commands struct + per-menu View structs
ProjectIndex.swift            Project + Folder models, projects.json persistence, SidebarItem/SidebarSelection enums
ProjectRow.swift              Sidebar row — doc.text icon, inline rename
FolderRow.swift               Sidebar folder row — folder.fill icon, inline rename (Phase 3)
Tab.swift                     Tab enum — route mapping, path→tab derivation
BridgeHandler.swift           Inbound state + outbound actions + menuAction dispatch
ServeManager.swift            Sidecar lifecycle + startup zombie cleanup + prefs overlay
WebView.swift                 WKWebView + security policy + KVO observations
KeychainHelper.swift          Credential storage via native Security.framework (SecItem* APIs)
LLMProvider.swift             Provider enum + ProviderStatus enum + notification names
AIConsentView.swift           First-run AI data disclosure (Apple 5.1.2(i)) + audit log
SettingsView.swift            TabView wrapper (3 icon tabs)
AppearanceSettingsView.swift  Theme radio + language dropdown
LLMSettingsView.swift         Mail Accounts pattern — provider list + detail pane
TranscriptionSettingsView.swift  Whisper backend + model pickers
ToastView.swift               ToastStore (@Published message) + ToastOverlay (bottom fade, 3s auto-dismiss)
IconPickerPopover.swift       SF Symbol icon picker for project rows
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

Two layers, **both serve-only** — `bristlenose run` subprocesses (the pipeline) have their own PID-file scan/attach lifecycle managed by `PipelineRunner`. See `docs/design-subprocess-lifecycle.md` for the run-side mechanics; the `lsof` cleanup below is port-scoped to serve and does not cascade to run.

1. **Clean quit**: `.onReceive(NSApplication.willTerminateNotification)` on the root View calls `serveManager.stop()` (SIGINT).
2. **Crash recovery**: `ServeManager.init()` runs `killOrphanedServeProcesses()` — a nonisolated static method that calls `lsof -ti :8150-9149` to find PIDs, then `kill(pid, SIGINT)` each one. Runs synchronously (~10ms), safe at startup.

Gap: Xcode's stop button sends SIGKILL which bypasses `willTerminate`. The startup cleanup catches these on next launch.

**Cancelling a `bristlenose run` subprocess needs signal escalation, not just SIGINT.** Whisper / torch / ctranslate2 hold the GIL during long C calls (model load can take 30–60s). Python signal handlers only run between bytecodes — SIGINT and SIGTERM both sit queued during the wedge, so a Stop click sees no effect for tens of seconds. `PipelineRunner.scheduleOrphanCancelEscalation` does SIGINT → SIGTERM at +5s → SIGKILL at +8s; bails at any step if the PID is dead or `attachedOrphanPIDs[id]` no longer matches. SIGKILL bypasses Python entirely so it always wins. Owned-process cancel still uses `proc.interrupt()` (SIGINT only) — same wedge risk, escalation TODO.

**`applyScanResult` won't overwrite `.running`.** Passive sidebar manifest scans must not clobber active runs, so the function returns early on `.running`/`.queued`/`.failed`. `handleOrphanExit` IS the "run is over" signal — it must explicitly transition `state[projectID] = .idle` itself before scheduling the manifest re-read, or the pill stays "Running" forever after the subprocess dies.

**`PipelineProgress.isStopping` is the immediate-ack contract.** Set unconditionally at the top of `cancel()` for both owned and orphan paths so the toolbar pill, popover, and sidebar row all flip to "Stopping…" before the kill propagates. Without this, the user mashes Stop while signals play out (1–8s).

**Sandbox implication for alpha:** `/usr/sbin/lsof` exec is blocked by App Sandbox. In the shipped build this cleanup path will silently fail. The user-visible consequence is a "port in use" error on the next launch after a crash, which should be handled with a clear restart prompt. Alternatively replace with a Swift-native TCP connect sweep across the port range. Decision deferred to C1.

## Settings window (Cmd+,)

Apple canonical `Settings` scene with 3 icon tabs (Appearance, LLM, Transcription). Constant width 660pt, height animates to fit content. Settings sync to the serve process via env vars (`ServeManager.overlayPreferences()` reads `UserDefaults` and injects before launching). API keys bypass env vars today — Python's `MacOSCredentialStore` reads Keychain directly. LLM tab uses Mail Accounts pattern (sidebar list + detail pane). One provider must always be active; activation guarded by status.

See `docs/design-desktop-settings.md` for the three tab specs, the UserDefaults→env var mapping table, and the `ProviderStatus` model.

**Alpha change:** sandboxed Python can't exec `/usr/bin/security`, so Track C C3 replaces the CLI-based credential store with either `pyobjc-framework-Security` or a Swift-fetches-then-injects-via-env pattern (preferred). The env-var pattern is symmetric with `overlayPreferences()` and keeps Python out of the Keychain entirely.

## Security rules

1. **Navigation restriction** — `decidePolicyFor` allows only `127.0.0.1` and `about:`. External URLs open in system browser via `NSWorkspace.shared.open()`.
2. **Bridge origin validation** — every `WKScriptMessageHandler` callback checks `message.frameInfo.request.url?.host == "127.0.0.1"`.
3. **No string interpolation into JavaScript** — use `callAsyncJavaScript(_:arguments:in:in:)` for native→web calls. Never concatenate user data into `evaluateJavaScript` strings. A project named `'; alert(1); '` must not become code execution.
4. **Ephemeral storage** — each project gets `WKWebsiteDataStore.nonPersistent()` to prevent cross-project cookie/sessionStorage leakage.
5. **Settings interception** — `project-action: open-settings` opens the native Settings scene, not the web modal.

## WKWebView cross-view messaging

Multiple WKWebViews can communicate via **BroadcastChannel** if they share the same `WKWebsiteDataStore` instance. Validated in spike (28 Mar 2026, macOS 26.1). Full design: `docs/design-wkwebview-messaging.md`.

**Critical rule:** `.nonPersistent()` creates a new ephemeral partition on every call. Two views that each call `.nonPersistent()` independently are fully isolated. To enable BroadcastChannel between views, both must use the **same instance** via a singleton:

```swift
class SharedConfigStore {
    static let shared = SharedConfigStore()
    let dataStore: WKWebsiteDataStore = .nonPersistent()
    let processPool: WKProcessPool = WKProcessPool()
}

// In both WebView configs:
config.websiteDataStore = SharedConfigStore.shared.dataStore
```

Process pool sharing is optional — separate pools do not break BroadcastChannel. Only the data store instance matters.

**Channel naming:** `bristlenose-{purpose}-{projectId}` (e.g. `bristlenose-tags-1`). First consumer: Tag Inspector panel (`docs/design-native-inspector.md`).

**Each WKWebView needs its own `WKWebViewConfiguration`** — don't share a config object between views (each has its own `userContentController` for message handlers). Share the data store and pool *via* the config, not the config itself.

## Port allocation

`8150 + djb2(projectPath) % 1000` — deterministic per project path, range 8150–9149. If the computed port is busy, tries up to 10 consecutive ports. Swift's `String.hashValue` is randomized per process (since Swift 4.2), so we use a stable djb2 hash instead.

## Patterns inherited from v0.1 (battle-tested)

These are the parts of v0.1 that survived the v0.2 rewrite because they work. Alpha leans on them too.

- `KeychainHelper.swift` — originally wrapped the `security` CLI, now uses Security.framework (`SecItemAdd`/`SecItemCopyMatching`/`SecItemDelete`). Same service names and account as Python's `MacOSCredentialStore` so either side can read keys written by the other.
- `Assets.xcassets/` — app icon and accent colour.
- Pipe reading pattern in `ServeManager` — `Task.detached` + `fileHandle.availableData` loop, originally from v0.1's `ProcessRunner.swift`.
- ANSI escape stripping regex.
- PyInstaller `--onedir` + Xcode "Copy Sidecar Resources" Build Phase pattern — preserved in `desktop/v0.1-archive/` as the reference for Track C C1.
- FFmpeg + ffprobe sibling-binary layout in `Contents/Resources/` — the path convention the sidecar's `bundled_binary_path()` helper will use.

## Key conventions

- **Bundle ID: `app.bristlenose`** — reverse-DNS of `bristlenose.app`. Irrevocable after first App Store submission. Changed from `CassioCassio.Bristlenose` (25 Mar 2026), then `research.bristlenose.app` (which referenced a non-existent `.research` TLD). v0.1-archive retains original ID (frozen snapshot). Full infrastructure plan: `docs/private/infrastructure-and-identity.md`
- **macOS 15.0** (Sequoia) deployment target
- **Swift 6 concurrency** — `SWIFT_DEFAULT_ACTOR_ISOLATION = nonisolated` in build settings. Mark classes `@MainActor` explicitly
- **`@StateObject`** at App level for ServeManager/BridgeHandler, `@EnvironmentObject` in views
- **SIGINT** (not SIGTERM) for graceful serve shutdown — lets Uvicorn release the port
- **App Sandbox: currently off, on for alpha.** Today's Debug/Release builds run unsandboxed so the launcher-style CLI discovery works. Track C C0 spike determines the minimum entitlement set; C1 flips sandbox on and switches to bundled-sidecar discovery.
- **Hardened Runtime: currently off, on for alpha.** Track C C2 wires `--options=runtime` at codesign time.
- **`callAsyncJavaScript` param labels**: `in: nil, in: .page` — the two `in` parameters are frame and content world respectively
- **Dev escape hatch: two explicit env vars, three Xcode schemes.** `BRISTLENOSE_DEV_EXTERNAL_PORT` connects to an externally-running `bristlenose serve`; `BRISTLENOSE_DEV_SIDECAR_PATH` spawns a specific binary; neither set → bundled sidecar. Both set → startup error. Release builds ignore both (`#if DEBUG` guard, verified by `desktop/scripts/check-release-binary.sh` post-archive). See "Dev workflow" section.
- **Logging: `os.Logger`, not `print`.** `Logger(subsystem: "app.bristlenose", category: "<area>")`. Use `print` only for scripts, never in shipped Swift code.

## Build

### Dev build (today)

```bash
# CLI build (uses xcodebuild)
cd desktop/Bristlenose
xcodebuild build -scheme Bristlenose -configuration Debug -destination "platform=macOS"

# Or open in Xcode and Cmd+R
open desktop/Bristlenose/Bristlenose.xcodeproj
```

The Xcode project uses `PBXFileSystemSynchronizedRootGroup` — Swift files added to `desktop/Bristlenose/Bristlenose/` are auto-discovered. No need to manually add them to the project.

### Alpha build (Track C C1 and beyond)

End-to-end orchestration lives in `desktop/scripts/build-all.sh`:

1. `scripts/fetch-ffmpeg.sh` — downloads pinned SHA256 FFmpeg/ffprobe
2. `scripts/build-sidecar.sh` — PyInstaller `--onedir` of `bristlenose serve`
3. `scripts/sign-sidecar.sh` — parallel (`xargs -P8`) per-binary codesign loop
4. `xcodebuild archive` — including the Copy Sidecar Resources Build Phase
5. `xcodebuild -exportArchive` — using `desktop/Bristlenose/ExportOptions.plist`

The signing identity comes from `SIGN_IDENTITY` env var (`-` for ad-hoc local iteration; `Apple Distribution: …` for TestFlight uploads once Track A delivers the cert).

## Frontend build requirement

`bristlenose serve` needs the React bundle built into `bristlenose/server/static/`. If you see "React bundle not found" warnings:

```bash
cd frontend && npm run build
```

## Dev workflow: three modes via Xcode scheme variants

After Track C C1 lands, three shared Xcode schemes map to three sidecar resolution modes. Pick the scheme in the Run-button dropdown next to Cmd+R. Each scheme pre-sets the appropriate env vars; Debug-only `#if DEBUG` guards mean Release builds physically exclude these reads and always use the bundled path.

| Scheme | Env vars it sets | Mode | Purpose | Failure mode |
|---|---|---|---|---|
| **Bristlenose** (default) | _(none)_ | `bundled` | What TestFlight ships. Spawns the sidecar at `Bundle.main.resourceURL/bristlenose-sidecar/bristlenose-sidecar`. Exercises the full shipping flow end-to-end. | Debug + bundle missing → `.failed` state + SwiftUI error card with "set `BRISTLENOSE_DEV_SIDECAR_PATH` or run `desktop/scripts/build-sidecar.sh`". Release + bundle missing → `.failed` + "installation corrupted" + Reveal in Finder. |
| **Bristlenose (External Server)** | `BRISTLENOSE_DEV_EXTERNAL_PORT=8150` | `external` | Fast CSS/React iteration. Start `bristlenose serve --dev trial-runs/project-ikea` in a terminal, then Cmd+R. App connects to the external server — no subprocess. Live CSS endpoint re-reads on every request; Vite HMR pushes React changes. | App can't reach `127.0.0.1:<port>` → standard connection error + retry. Terminal server missing → same. |
| **Bristlenose (Dev Sidecar)** | `BRISTLENOSE_DEV_SIDECAR_PATH=/Users/cassio/Code/bristlenose/.venv/bin/bristlenose` | `devSidecar` | Swift spawns the exact binary you point at — usually your dev venv. Iterate on Python + test the full ServeManager subprocess flow without a PyInstaller rebuild. `Logger.warning` fires on mode resolution so a poisoned env var is visible. | Path invalid (non-existent, directory, non-executable) → `fatalError` with the resolved path (Debug only; never in Release because the env-var read is `#if DEBUG`-guarded). |

**Both env vars set simultaneously** → `ServeManager.init()` fails with "Both dev env vars set — pick one." Catches configuration mistakes at launch rather than on first project click.

**Mode logging.** `ServeManager` uses `Logger(subsystem: "app.bristlenose", category: "serve")` and emits one line at startup: `Mode: external-server, port=8150` / `Mode: dev-sidecar, path=/Users/.../bristlenose` / `Mode: bundled, path=/Applications/.../bristlenose-sidecar`. Shows up in Xcode console, Console.app, and `log stream --predicate 'subsystem == "app.bristlenose"'` in Terminal. Release builds get automatic privacy redaction.

**Swap schemes via the dropdown** next to the Run button in Xcode. To set your own env-var value inside a scheme: Product → Scheme → Edit Scheme → Run → Arguments → Environment Variables. For personal paths (e.g. a non-default venv location), edit the scheme's env-var value directly — the schemes are checked into `xcshareddata/xcschemes/` so the default values are shared, but personal overrides stay local until you commit them.

**Linux / Windows contributors** never touch this — these env vars are read by Swift, not Python. If you're working on the Python sidecar or React frontend, run `bristlenose serve` directly from your terminal and use any browser; the macOS shell is out of scope.

See `docs/design-modularity.md` "External dev server" glossary entry and `docs/private/sprint2-tracks.md` Track C C1 for the implementation spec. Underlying resolver is `SidecarMode.resolve(externalPortRaw:sidecarPathRaw:bundleResourceURL:fileManager:)` — a pure function (takes the two env-var raw strings as typed `Optional<String>` rather than an env dictionary, so the string literals live only inside the caller's `#if DEBUG` block and are absent from the Release Mach-O). Unit-tested in `BristlenoseTests/SidecarModeTests.swift` (orphan target today — see test-target note in this file).

## Gotchas

- **`.nonPersistent()` creates a new partition every call** — the most common mistake with multi-WKWebView setups. Two views that each call `.nonPersistent()` are fully isolated (no BroadcastChannel, no shared localStorage, no shared cookies). Store the instance in a singleton (`SharedConfigStore.shared.dataStore`) and pass it to both configs. See `docs/design-wkwebview-messaging.md`
- **Custom URL schemes + `.nonPersistent()` crash WebKit on macOS 26** — `WKURLSchemeHandler` with a custom scheme (e.g. `spike://`) and `.nonPersistent()` data store crashes the WebKit network process. Use HTTP (localhost) instead. Bug is specific to custom schemes, not a general `.nonPersistent()` regression
- **Don't share `WKWebViewConfiguration` between WKWebViews** — each view needs its own config (they have separate `userContentController` for message handlers/scripts). Sharing a config and then calling `userContentController.add(_, name: "X")` on both views adds duplicate handlers to the same controller, which crashes. Share the data store and pool *via* the config
- **`import Security` does NOT re-export Foundation on macOS 15 SDK** — `KeychainHelper.swift` needs both `import Foundation` and `import Security`. Without Foundation, `Data` and `ProcessInfo` are undefined. The code review suggested `import Security` alone would suffice — it doesn't
- **WKWebView `createWebViewWith` requires the provided configuration** — you MUST use the `configuration` parameter passed to `webView(_:createWebViewWith:for:windowFeatures:)`. Creating a fresh `WKWebViewConfiguration` and returning a WKWebView built with it crashes with `NSInternalInconsistencyException: "Returned WKWebView was not created with the given configuration."`. This means the popout inherits the parent's `userContentController` (including the bridge message handler). The bridge is accessible but player.html never calls it
- **WKWebView `window.open()` is blocked without `WKUIDelegate`** — `window.open()` silently returns `null` unless the Coordinator implements `WKUIDelegate` and `webView(_:createWebViewWith:for:windowFeatures:)`. No error in the console — the call just fails. This is why the video player didn't work in the desktop app before the WKUIDelegate was added
- **Zombie cleanup kills the dev server** — `ServeManager.killOrphanedServeProcesses()` runs on `init()` and kills everything on ports 8150–9149. When `BRISTLENOSE_DEV_EXTERNAL_PORT` is set (external-server scheme), cleanup is skipped — we don't own that process. When `BRISTLENOSE_DEV_SIDECAR_PATH` is set (dev-sidecar scheme), cleanup still runs because we own the spawned subprocess. Always start the terminal server **after** Xcode launches if using the external-server scheme.
- **`window.blur`/`window.focus` don't fire in WKWebView** — the web view's `window` is always considered focused from the web content's perspective. macOS window activation must be pushed from the native side via `NSWindow.didBecomeKeyNotification`/`didResignKeyNotification` → `BridgeHandler.setWindowActive()`. The browser `blur`/`focus` listener in `AppLayout.tsx` only works in browser-based serve mode
- **Safari Web Inspector for WKWebView debugging** — enable `webView.isInspectable = true` (already set in `#if DEBUG`). Open Safari → Develop → Bristlenose → pick the localhost page. The inspector opens in a Safari window, so the Bristlenose app window stays inactive — perfect for debugging inactive-window behaviour
- **Xcode stale indexer** — sometimes shows "no member" errors that `xcodebuild` doesn't. Fix: `Cmd+Shift+K` (Clean Build Folder) then `Cmd+R`
- **Zombie serve processes** — if the app crashes without calling `stop()`, the Python serve process keeps running on the port. Check with `lsof -i :8150-9150 -P -n | grep LISTEN` from a terminal. Next app launch cleans these up automatically via libproc-based startup sweep in `ServeManager.init`
- **App Sandbox blocks `Process()` exec of system binaries — use libproc syscalls instead.** `Process` exec of `/bin/ps`, `/usr/sbin/lsof`, `/usr/bin/security` etc. is blocked at sandbox-launch regardless of the binary's own permissions. The "ps is allowed" intuition is wrong — sandbox enforces at the *exec* boundary, not the destination binary. Mac-canonical replacements (all in `<libproc.h>`, one-line `import Darwin` from Swift): `proc_pidpath(pid, &buf, MAXPATHLEN)` (PID → executable path, what Activity Monitor uses), `proc_listpids(PROC_ALL_PIDS, ...)` (process enumeration), `proc_pidfdinfo(pid, fd, PROC_PIDFDSOCKETINFO, ...)` (listening sockets, replaces lsof). The full zombie-cleanup path is now libproc-only on `sidecar-signing` (SECURITY #5 swap of `/bin/ps`, then 27 Apr 2026 swap of `lsof`) — survives sandbox flip with no further changes
- **`Report:` readiness signal** — `bristlenose serve` prints this BEFORE Uvicorn accepts connections. The port-polling step in ServeManager handles the race. The sidecar will keep this log line and parser — it's the alpha readiness contract
- **Bridge code on main vs feature branch** — the `macos-app` branch has the bridge shims in `frontend/src/shims/bridge.ts`. The main branch build served by `bristlenose serve` won't post `ready` messages. The `didFinish` fallback in WebView handles this (shows content after 2s timeout)
- **Segmented Picker requires non-optional selection** — `Binding<Tab?>` doesn't work with `.pickerStyle(.segmented)`. The `tabBinding` in ContentView maps nil to `.project`
- **Tab.from(path:) prefix order** — check longest prefixes first (`/report/analysis` before `/report/`). The project tab uses exact match to avoid matching all paths
- **`.onReceive` is a View modifier, not Scene** — attach it to the root View inside WindowGroup, not to the WindowGroup itself. The publisher is `NotificationCenter.default.publisher(for: NSApplication.willTerminateNotification)`
- **`@ObservedObject` in `Commands` struct is unreliable** — use `let` (plain property) on the `Commands` struct, then use `@ObservedObject` inside `View` structs that are the content of `CommandMenu`/`CommandGroup`. See `MenuCommands.swift` for the pattern
- **Don't replace `.pasteboard` in Commands** — `CommandGroup(replacing: .pasteboard)` removes Cut/Copy/Paste. WKWebView handles these via the responder chain. Only replace `.undoRedo` (for app-level undo) and `.help`
- **Undo/Redo editing guard** — when `isEditing`, the Undo/Redo menu items are hidden (not disabled) so Cmd+Z falls through to WKWebView's character-level text undo. When not editing, they intercept and route to the bridge. **Known HIG deviation:** this violates the "dim, never hide" menu principle. Hiding is necessary here because a disabled Cmd+Z menu item would still intercept the shortcut before it reaches WKWebView's responder chain — dimming prevents the key from falling through. Acceptable trade-off: character-level undo during text editing is more important than menu discoverability
- **`@AppStorage` not `@SceneStorage` for project selection** — `selectedProjectPath` uses `@AppStorage` so the last-opened project persists across app launches. `@SceneStorage` doesn't survive relaunch for unsigned/debug-signed apps (macOS state restoration requires proper code signing). Xcode debug runs also reset scene storage between launches. Use `@AppStorage` for anything that must persist across relaunches
- **Web Inspector** — enabled via `webView.isInspectable = true` in `#if DEBUG` builds only. Right-click → Inspect Element works in debug builds for diagnosing bridge/CSS issues
- **Navigation shims use module-level refs (not closures)** — `installNavigationShims()` in `frontend/src/shims/navigation.ts` stores `navigate` and `scrollToAnchor` in module-level variables. The `window.switchToTab` etc. functions read from these refs instead of closing over the parameters directly. This prevents a stale-closure bug where the initial `navigate` captured at mount doesn't work until the router is fully ready. The `useEffect` in `AppLayout.tsx` calls `installNavigationShims` on every `navigate`/`scrollToAnchor` change — the window functions are installed once (idempotent guard) but the refs always update
- **`callAsyncJavaScript` error handling** — `BridgeHandler.switchToTab()` and `menuAction()` use `do/catch` (not `try?`) so JavaScript errors are logged to Xcode console. If a bridge call silently fails, check the console for `[BridgeHandler] ... FAILED:` messages
- **`NSWindow.accessibilityLanguage` doesn't exist** — VoiceOver language for web content is set via `syncLocale()` (bridge → HTML `lang` attribute). Native SwiftUI elements inherit the system language. Don't try to set accessibility language on NSWindow directly
- **Consent version bumping** — when AI disclosure content materially changes (new cloud provider, new data category sent to LLMs), bump `AIConsentView.currentVersion`. The dialog re-shows for users who acknowledged a lower version. Bump for: adding a new cloud provider, sending a new data type. Don't bump for: copy tweaks, layout changes, adding Ollama features
- **Serve process gated on consent** — `serveManager.start()` is only called after `aiConsentVersion >= AIConsentView.currentVersion` (checked in `.onChange(of: selectedProject)`). When consent is granted (version updated), `.onChange(of: consentVersion)` starts serve for the already-selected project. This prevents any data leaving the machine before the user has seen the AI data disclosure (Apple Guideline 5.1.2(i))
- **List selection must bind to `UUID?`, not a value-type model** — `List(selection: $selectedProject)` where `selectedProject` is `Project?` (a struct) breaks when any field on the selected project mutates (e.g. `updateLastOpened` changes `lastOpened`). SwiftUI compares the selection value against the list items by hash — if the hash changed, selection drops (flashes blue then deselects). Fix: bind to `$selectedID` (`UUID?`) and derive `selectedProject` as a computed property. UUIDs are stable across field mutations
- **ALL tap gestures on List rows break selection on macOS 26** — both `.onTapGesture` and `.simultaneousGesture(TapGesture())` on views inside `List` rows interfere with the List's built-in selection binding. `.onTapGesture` swallows the click entirely (row flashes but selection never commits). `.simultaneousGesture` works intermittently (selection sticks after 1 click then stops responding). This was confirmed with macOS 26.1 + Xcode 26.3. **Do not put any SwiftUI gesture recognisers on List row content.** Slow-double-click rename (Finder-style) is parked — needs NSEvent local monitor or AppKit subclass approach instead
- **`.onDrop` on individual List rows breaks selection** — per-row `.onDrop(of:)` causes the same selection interference as tap gestures. Use `.onDrop` on the List itself for sidebar-level drops. **Workaround shipped:** `SidebarDropDelegate` uses `DropInfo.location` + `GeometryReader` preferences (`RowFramePreferenceKey`/`FolderFramePreferenceKey`) to hit-test which row the drop targets. Handles both Finder file drops (onto project rows) and internal project drags (onto folders via `.draggable`). No per-row `.onDrop` needed
- **`List(selection: Set<SidebarSelection>)` for multi-select** — Cmd+click and Shift+click work natively with `Set` binding. `soleSelection` helper derives single-item state for serve/persist. Bulk delete via menu notifications filters by type (projects only, folders only)
- **`Project.position` / `Folder.position` for sidebar ordering** — `Int` field, auto-assigned on creation (new items get 0, existing pushed +1). `.onMove` on `ForEach` handles drag-to-reorder. Backward compat: old `projects.json` without `position` defaults to 0; first load backfills positions from `createdAt` order
- **`.contextMenu` on List rows does NOT break selection** — unlike gestures and drop targets, `.contextMenu` on rows works correctly. Right-click shows the menu, left-click selects. Context menu can live on the row (after `.tag()`) or inside the row View
- **Project menu actions use `Notification.Name` not bridge** — Show in Finder, Rename, Delete, New Project, New Folder, and Move To are native-side operations. They post notifications (`createNewProject`, `createNewFolder`, `renameSelectedProject`, `renameSelectedFolder`, `deleteSelectedProject`, `deleteSelectedFolder`, `moveSelectedProject`) which ContentView receives via `.onReceive`. This is different from all other menu actions which dispatch through `bridgeHandler.menuAction()` to the web layer
- **`SidebarSelection` enum for mixed-type selection** — `List(selection:)` binds to `SidebarSelection?` (`.project(UUID)` or `.folder(UUID)`) instead of `UUID?`. This lets projects and folders share the selection space while remaining type-safe. `@AppStorage("selectedProjectID")` only persists project selections (folders don't open a report). `DisclosureGroup` label `.tag()` propagates correctly — folder rows are selectable
- **`DisclosureGroup` inside `List` works for one-level folders** — `DisclosureGroup(isExpanded:)` binding reads from `Folder.collapsed` (inverted). The expand/collapse state is persisted in `projects.json` via `setFolderCollapsed()`. If nested folders were ever needed, `OutlineGroup` would be required instead
- **`Folder.collapsed`/`createdAt` backward compat** — old `projects.json` files have `FolderStub` shapes (just `id` and `name`). `Folder.init(from:)` uses `decodeIfPresent` with defaults (`collapsed = false`, `createdAt = Date()`) so old files parse correctly
- **Drag-and-drop uses async URL loading** — `NSItemProvider.loadItem` callbacks run on background threads. Use `withTaskGroup` + `withCheckedContinuation` to collect all URLs, then `await MainActor.run` to process. Never mutate `@State` or `@Published` from the callback directly
- **`.navigationTitle()` on the detail view adds a visible toolbar title item** — in `NavigationSplitView`, calling `.navigationTitle("Project Name")` on the detail view both sets `NSWindow.title` AND injects a SwiftUI toolbar title item. With a custom icon+name `ToolbarItem(placement: .navigation)` this creates a duplicate. Fix: omit `.navigationTitle` on the detail view entirely; set `NSWindow.title` via a `WindowTitleManager: NSViewRepresentable` that calls `window.title = title` in `updateNSView`. `titleVisibility = .hidden` alone does NOT suppress the SwiftUI toolbar item
- **Debug builds: main executable is a stub; code lives in `Bristlenose.debug.dylib`.** Xcode's incremental-linking optimisation. Release builds link directly into the main executable with no debug dylib. When writing post-archive gates that scan for string literals (`desktop/scripts/check-release-binary.sh`), scan every Mach-O in `Contents/MacOS` + `Contents/Frameworks`, not just the main executable — or Debug smoke-tests of the gate will show false negatives (main stub has no literals). The gate itself should only run against Release archives; Debug is expected to contain the `#if DEBUG` branch by design.
- **Xcode expands `$(SRCROOT)` reliably in scheme env-var values; `$(HOME)` is debated.** Use `$(SRCROOT)/../../.venv/bin/bristlenose` in shared schemes that need a repo-root-relative path — it expands to the project parent regardless of where the contributor cloned the repo. Avoid `$(HOME)` (may or may not expand depending on Xcode version / context) and avoid hardcoded `/Users/you/...` paths (personal, brittle).
- **`codesign --force --entitlements <file>` without `--remove-signature` first is unreliable when probing minimum entitlement sets** — if the outer binary already has a signature that grants, say, `disable-library-validation`, re-signing with `--force` and a trimmed entitlements file will appear to succeed (`codesign -dv` shows the new entitlements), but the process still runs because the inner `.dylib`/`.so`/`Python.framework` files retain their own signatures with the old entitlements. To genuinely test a minimum set: `codesign --remove-signature <binary>` first, then `codesign --force --options=runtime --entitlements … --sign - <binary>`. Confirmed during Track C C0 (18 Apr 2026). See `docs/design-desktop-python-runtime.md` §"How this was determined"
- **Empty-space deselection in `List(selection: Set<>)` on macOS 26** — `List(selection: $selection)` with a `Set` binding no longer auto-deselects when clicking empty space on macOS 26. SwiftUI gesture workarounds (`DragGesture(minimumDistance: 0)` as `.simultaneousGesture`) don't fire reliably. Fix: `SidebarDeselectMonitor: NSViewRepresentable` with `NSEvent.addLocalMonitorForEvents(matching: .leftMouseDown)`. In the handler, find the sidebar `NSTableView` (first table view in the window — WKWebView detail has none), convert the click to table coordinates, call `row(at:)`. If it returns -1 (click below all rows and within the table bounds), clear `selection = []`. Always `return event` to pass through

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

See `docs/design-desktop-menu-actions.md` for the full catalogue (65+ actions across AppLayout, useKeyboardShortcuts, project ops, codebook stubs, edit ops), payload conventions, `getState()` stubs, and recommended implementation order.

**Quick pointers:**
- AppLayout (`bn:menu-action` handler) owns panel toggles, find actions, modals, exports, zoom, dark-mode toggle, codebook dispatches
- `useKeyboardShortcuts.ts` (`handleMenuAction` switch) owns quote/player actions that need FocusContext/QuotesContext/PlayerContext closures
- Payloads only for data the native side has that the web side doesn't (e.g. `findNext` text from `NSPasteboard.find`)

## Testing

### Framework choice

- **Swift Testing** (`@Test`, `#expect`) for all unit and integration tests
- **XCTest** (`XCTestCase`, `XCUIApplication`) reserved for UI tests only — it's the only framework with UI automation
- Both can coexist in the same test target, but **never mix assertions** — `#expect` inside an `XCTestCase` is silently ignored, and `XCTFail` inside a `@Test` doesn't register ([interop proposal ST-0021](https://forums.swift.org/t/st-0021-targeted-interoperability-between-swift-testing-and-xctest/84965) is in progress)

### Conventions

- Test file naming: `{ClassName}Tests.swift` in `BristlenoseTests/`
- **Suite-level `@MainActor` for tests that touch `@MainActor` types** — annotate the `@Suite struct`, not each `@Test func`. The per-method approach (`@MainActor @Test func ...`) is noisier and tends to miss tests that call static methods on actor-isolated types. Two existing files (`I18nTests`, `ProjectIndexTests`) had header comments saying *"X is @MainActor — all tests must be @MainActor too"* but were missing the suite-level annotation; adding it cleared all the actor-isolation errors at once. Swift Testing runs `@Test` on arbitrary executors by default
- KeychainHelper tests always use `InMemoryKeychain`, never real SecItem — avoids overwriting real API keys (SIGKILL bypasses teardown, so cleanup is not crash-safe)
- ProjectIndex tests always use `ProjectIndex(fileURL: tempURL)`, never the default Application Support path
- I18n tests use `configure(localesDirectory:)` with fixtures in `BristlenoseTests/Fixtures/`, never `findLocalesDirectory()` (which hardcodes dev paths)

### Test target setup

**⚠️ `BristlenoseTests` is not wired into the Xcode project yet** (as of Track C C1, 19 Apr 2026). The directory exists with Swift Testing files (`I18nTests.swift`, `KeychainHelperTests.swift`, `ProjectIndexTests.swift`, `TabTests.swift`, `LLMProviderTests.swift`, `SidecarModeTests.swift`), but `xcodebuild -list` shows only the `Bristlenose` target. All test files compile standalone as reference, but `xcodebuild test` fails with "Scheme Bristlenose is not currently configured for the test action." Wiring up the target is a parked qa-backlog item — 20-60 min of pbxproj editing or adding a `PBXFileSystemSynchronizedRootGroup` entry. Until then, treat `BristlenoseTests/` as aspirational reference code.

The target, when wired, should use `PBXFileSystemSynchronizedRootGroup` so new `.swift` files added to `BristlenoseTests/` are auto-discovered.

**Auto-sync flattens flat-resource folders into `Resources/` and collides** — e.g. `Fixtures/{en,es}/*.json` (locale-style folders that aren't `.lproj`) all copy to `Resources/<name>.json` with no per-locale subdir, causing `Multiple commands produce '...common.json'` build errors. Fix in `Bristlenose.xcodeproj/project.pbxproj`: add a `PBXFileSystemSynchronizedBuildFileExceptionSet` referencing the synced root with `membershipExceptions = (Fixtures/en/common.json, ...)` listing each colliding file. Folder paths (`Fixtures` or `Fixtures/en`) don't work as exceptions — must list each file explicitly. The proper Xcode-side fix (folder reference instead of group) preserves the subdir structure but requires the GUI; pbxproj exceptions are the CLI-friendly workaround. Same exception set can also exclude pre-existing test files that don't yet compile under Swift 6 strict mode

Build settings must match the app target:
- `SWIFT_VERSION` — same as app (currently 5.0)
- `SWIFT_DEFAULT_ACTOR_ISOLATION = nonisolated`
- `ENABLE_APP_SANDBOX = NO` (today; matches app target; flips to YES for alpha)

### Running tests

```bash
xcodebuild test -project desktop/Bristlenose/Bristlenose.xcodeproj -scheme Bristlenose -destination 'platform=macOS'
```

Or in Xcode: Cmd+U.

### Testability refactors

Two injection points exist for safe testing:

1. **`ProjectIndex(fileURL:)`** — pass a temp directory URL to avoid touching `~/Library/Application Support/Bristlenose/projects.json`
2. **`KeychainStore` protocol** — `KeychainHelper.liveStore` for production, `InMemoryKeychain()` for tests. The static `KeychainHelper.get/set/delete` methods remain unchanged for existing call sites

## See also

- `docs/design-modularity.md` — canonical reference for what ships where (Python deps, extras, Background Assets, no-fork principle across CLI + macOS)
- `docs/design-desktop-python-runtime.md` — canonical shipping architecture for the Mac sidecar specifically (write-up due as part of Track C C0)
- `docs/private/road-to-alpha.md` — 14 checkpoints to TestFlight
- `docs/private/sprint2-tracks.md` — Track A (sandbox plumbing), Track B (MVP UX flow), Track C (sidecar bundling + signing)
- `desktop/v0.1-archive/README.md` — v0.1 bundling pipeline reference
