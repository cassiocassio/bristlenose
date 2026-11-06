# Desktop App — macOS Shell

**Filesystem-location assertions:** Foundation can enumerate a temporary folder
through `/private/var` while a constructed URL spells it `/var`. In tests that
assert the same directory, compare `ScanSelection.realPath(url.path)` on both
sides; changing only the fixture root with `resolvingSymlinksInPath()` is not
sufficient. Keep payload-kind and count checks so canonical sets cannot hide
duplicate imports. See `SidebarFinderDropTests` and c92bba10a (30 Oct close-out).

SwiftUI macOS app wrapping the Bristlenose React SPA in a WKWebView. Native project sidebar, native toolbar, native Settings window, web content in embedded mode. **Alpha ships a bundled, signed PyInstaller sidecar** that runs `bristlenose serve` inside the `.app`, distributed via internal TestFlight. The current code uses **launcher-style scaffolding** (the Swift app searches the user's `$PATH` and venv directories for an installed `bristlenose` CLI rather than carrying its own) so v0.2 native-shell work could iterate without paying the bundle-sign-distribute tax on every change. Track C in Sprint 2 replaces it with the bundled sidecar.

## SwiftUI authoring + review help

`.claude/skills/swiftui-pro/` is a vendored SwiftUI review skill (Paul Hudson's
`swiftui-pro`, MIT — see its `VENDORED.md`). It auto-triggers when you read,
write, or review SwiftUI in the main conversation, and its `references/*.md`
(deprecated API, view composition, data flow, navigation, design/HIG,
accessibility, performance, modern Swift, hygiene) are read by the review agents
during `/usual-suspects` on `.swift` changes, for API facts, **after** their own
correctness pass. They aren't walked as the review itself: used that way, they
found fewer real bugs than a plain reading in the 11 Oct 2026 benchmark
(`.claude/skills/usual-suspects/SKILL.md`, "Why after").

It's a **knowledge source for generic SwiftUI craft**, not a Mac-taste
authority — it's iOS-first. On any conflict, project hard rules (`MEMORY.md`,
this file) win, then macOS idiom (`what-would-gruber-say` / `app-store-police`),
then swiftui-pro. It beats an agent's untrained SwiftUI hunch; it never overrides
a documented Mac decision. Details in the skill's `VENDORED.md`.

## Two axes: the language moves fast, the frameworks need judgement

Two separate rules; don't merge them into "use the latest". **Language** (Swift concurrency): latest is genuinely better, follow `swift-concurrency-pro` (the app still builds in Swift 5 language mode with default actor isolation `nonisolated`). **Frameworks** (SwiftUI on macOS): latest is a hypothesis, not a default. Try the SwiftUI affordance, and on a wall retreat to AppKit; the sidebar is migrating from `List` to `NSOutlineView` (`docs/design-desktop-sidebar-appkit.md`). On Mac, name the AppKit primitive that already does the job before the SwiftUI one; this overrides the vendored swiftui-pro's avoid-UIKit line. Check any SwiftUI fix against the deployment floor (`MACOSX_DEPLOYMENT_TARGET = 15.0` on all four schemes, pinned by `desktop/scripts/check-deployment-floors.sh`; most celebrated improvements landed in macOS 26; read the floor with `xcodebuild -showBuildSettings` and name the scheme). None of this is a native-pivot commitment: the web SPA stays the primary surface.

[full text](reference.md#two-axes-the-language-moves-fast-the-frameworks-need-judgement)

## New platform features are offered, not required

**Two moves look the same in a diff and are opposites.** Distinguish them before
writing the code, because only one of them costs users.

| | What it does | Cost |
|---|---|---|
| **Progressive enhancement** — adopt the new API behind `if #available`, keep the old path working | adds capability | none |
| **Floor bump** — raise `MACOSX_DEPLOYMENT_TARGET` so the new API can be called unconditionally | adds capability *and* removes everyone below the new floor | users |

The tempting argument runs: *"SwiftUI has caught up with AppKit here, so let's
rebuild this surface in SwiftUI and raise the minimum."* That is the second row.
It trades a population of users for an implementation convenience, and the
convenience is usually the smaller number.

**What we actually want: offer the latest and greatest native features to
everyone whose machine can run them, and still open fine on the oldest OS we
support.** That is the first row — feature detection and graceful degradation,
not a minimum-version gate. It is also what makes the planned model tiering
work: Apple and local models appear on machines modern enough to have them,
alongside bring-your-own-key for everyone else, and the app has to run well in
both cases (`docs/design-platform-policy.md` §"Pillar 3 — macOS").

So "this new API would be nice" is **never on its own an argument for moving the
floor.** It is an argument for an availability check. Moving the floor needs its
own justification, weighed against who it cuts off — and that decision lives in
Pillar 3, not in the diff where the temptation arises.

## Native primitives first — Swift isn't a blank web canvas

**The out-of-the-box system primitive with default settings is the starting
point, not a fallback.** Before drawing anything, name the stock control that
already does the job and default to it: `NSSavePanel`/`NSOpenPanel` for
location/save/create-folder (these are *also what grant sandbox access* — a
hand-drawn sheet grants nothing), `NSOutlineView` for hierarchical lists, a
standard sheet for a committed modal task, a popover for a transient
light-dismiss choice, `NSAlert` for a confirm, SF Symbols / real file icons for
glyphs. Composing your own is the exception that needs the written sentence "the
system primitive is X; we depart because Z" — if you can't write it, use X.
Treating Swift as an arbitrary canvas (any modal, any helper text, any emoji)
imports web habits into a platform with strong native answers, and produces
non-Mac-like UI that a `what-would-gruber-say` pass then has to drag back.

This is the level *above* the grid rule: stay-on-the-grid governs **values**
(fonts/colours/spacing/materials); this governs the whole **primitive** (control,
panel, sheet, interaction pattern). Brick, not paint.

**Process:** run `what-would-gruber-say` on novel native UI **before** proposing
a mockup, not after — it's a verification backstop, not a discovery tool. If
Gruber is dragging the design back to Mac reality, native-first got skipped. The
recurring panels/dialogs checklist and the origin post-mortem live in the
`feedback_native_primitives_first.md` memory.

## A user-facing string needs a key — the authoring rule

**macOS app UI is an i18n target** (`docs/design-i18n.md` §"Which surfaces are
targets"; 21 full locales). The exceptions are narrow and stated there: System
Health and the Diagnostics menu, which are hidden on the App Store build, and the
alpha-expiry chrome.

**The failure is a sentence filed as data.** Every one of the ~100 gaps the 21 Sep
2026 audit found was a `String` property on a type that models a *thing* rather than
a *screen* — `signInTitle` on a platform, `errorDescription` on an error,
`rowMessage` on a verdict, `humanSummary` on a category, `label` on an icon. Writing
a View makes you think about a reader; writing a model does not, and the string
renders just the same.

Three rules, in the order they bite:

1. **Errors carry a case, not a sentence.** `Cause.reason` travels on the wire and
   the pane resolves `desktop.pipeline.diagnostic.reason.*`; the SPA's
   `autocodeFailure.ts` maps `failure_kind` → `(key, fallback, kind)`. Both keep the
   forensic record English *and* give the reader their language. A `switch` returning
   a bare literal is that table missing its key column.
2. **`LocalizedError.errorDescription` is the highest-risk site in this codebase** —
   6 of 6 conformers held hardcoded English on 21 Sep 2026. The protocol's name is
   the promise; keep it.
3. **A non-View type takes `I18n` as a parameter.** There is no `I18n.shared` — one
   instance, injected. `CloudPlatform.windowTitle(_ i18n: I18n)` is the worked
   example, and `signInTitle` three lines below it in the same enum is what happens
   without this rule.

Sweeping rather than authoring? The grep recipe is "Swift i18n sweeps" in [reference.md § Build](reference.md#build).

## Appearance (light / dark) — one seam, nothing per-surface

Adding a window, panel, sheet, alert, menu or popover needs no appearance step: `AppAppearance.beginApplying()` (from `applicationDidFinishLaunching`) sets `NSApp.appearance` from the Settings ▸ Appearance preference, and every AppKit surface inherits it. A per-surface step is the bug. Never re-derive the mapping: use `AppAppearance.current` or `AppAppearance.colorScheme(for:)` (both in `AppAppearance.swift`), never a fresh `switch` or a raw `UserDefaults` read. Save/open panels must call `panel.adoptHostAppearance()` before presenting, and host windows resolve through `PanelHost.window`, not bare `NSApp.keyWindow`. The web report follows through `prefers-color-scheme`; do not add a bridge channel. `desktop/scripts/check-appearance-seam.sh` enforces this. Tell for the whole class: a surface correct in Automatic and wrong when the user forces Light or Dark; QA with the app preference set opposite to System Settings.

[full text](reference.md#appearance-light--dark--one-seam-nothing-per-surface)

## Shipping architecture (alpha and beyond)

See `docs/design-desktop-python-runtime.md` for the canonical design. Summary:

- **Bundled, signed PyInstaller sidecar.** The Python `bristlenose serve` runtime ships inside `Bristlenose.app/Contents/Resources/bristlenose-sidecar/`. Every `.dylib`, `.so`, and framework inside is individually codesigned with Hardened Runtime. FFmpeg + ffprobe bundled alongside (trimmed codec set, ~25 MB). Whisper transcription model downloaded in the background from launch (once the AI disclosure is acknowledged, with at least 10 GB free; `WhisperDownloadModel.checkAtLaunch`, 22 Oct 2026) into the Hugging Face cache inside the app's container (`~/Library/Containers/app.bristlenose/Data/.cache/huggingface/hub/`; the app sets no `HF_*` variable, so `preflight/whisper.py` `_hf_cache_root` falls back to `$HOME/.cache`, and `HOME` is the container) — keeps the `.app` small. _Corrected 18 Oct 2026: this said `~/Library/Application Support/Bristlenose/models/`, v0.1's `BRISTLENOSE_WHISPER_MODEL_DIR`, which nothing sets any more._
- **Why sidecar, not embedded interpreter.** Long-running pipeline operations (transcription, LLM calls) must be independently killable from Activity Monitor. An embedded Python interpreter takes the SwiftUI chrome down if Python hangs — beach ball on the toolbar, force-quit the whole app. Separate process keeps that failure mode contained.
- **Single Python artefact.** Same `bristlenose serve` code path ships via Homebrew/Snap/pip for CLI users and via the `.app` for desktop users. No fork.
- **Apple-supported pattern.** Apple Developer Support recognises three App-Store-supported Python architectures (pure-Python wrapper via Briefcase, sidecar via IPC, embedded interpreter via PythonKit). Sidecar is documented and shippable.
- **App Sandbox on, Hardened Runtime on** for Release / TestFlight. Debug builds may relax either to speed iteration.

**Development history:** v0.1 (Feb 2026, in `desktop/v0.1-archive/`) proved the bundling pipeline end-to-end with a one-shot `bristlenose run` wizard. v0.2 (Mar 2026 onwards, this codebase) rebuilt the native shell — NavigationSplitView workspace, WKWebView, native sidebar/menu/settings — using the simpler launcher pattern so the native work could iterate without the bundle-sign-distribute tax on every change. Alpha recombines them: v0.2's native shell + v0.1's bundling pipeline, adapted to the long-lived `bristlenose serve` lifecycle.

## Current state vs target state

A table of the dev-only v0.2 state against the alpha/TestFlight target (Python runtime, sandbox, Hardened Runtime, signing, FFmpeg, Whisper model, Keychain access, Ollama, distribution). Kept in full in the reference.

[full text](reference.md#current-state-vs-target-state)

## Architecture (SwiftUI layer)

`BristlenoseApp` (the `@main` entry; app-level objects, menu commands, quit hook) holds `ContentView` (a `NavigationSplitView`: sidebar + detail, toolbar), which holds `WebView` (the `WKWebView` wrapper and its Coordinator, with the popout player window). The annotated file tree is in the full text; the live list is `ls desktop/Bristlenose/Bristlenose`. Which objects are app-level and which per-window: see State ownership below.

[full text](reference.md#architecture-swiftui-layer)

### State ownership

**The two objects sit at different levels, and which is which is load-bearing.**

- **`ServeFleet` is app-level** — `@StateObject private var serveFleet` in `BristlenoseApp.swift:96`. Sidecars are a machine-wide resource, not a per-window one, and `.onReceive(willTerminateNotification)` needs it to kill zombies at quit.
- **`BridgeHandler` is PER-WINDOW** — `@StateObject private var bridgeHandler` in `ContentView.swift:178`. It mirrors one document: which lens is showing, whether the channel is live, what the selection is. Two windows on two projects need two of them.

_This section said both were app-level, with ContentView holding them via `@EnvironmentObject` and owning neither — true before the multi-window work (Stage 3b), false since, and corrected 12 Sep 2026._ It is worth getting right because the file's own multi-window gotchas depend on it: "a per-window callback hung off an app-wide channel is the multi-window bug you will actually ship" is only reasonable advice if you know which side of that line `bridgeHandler` falls on. A menu command reads the *focused* window's handler via `@FocusedValue`, not a shared one.

### Tab enum and route mapping

`Tab.swift` defines the 5 toolbar tabs: `project`, `sessions`, `quotes`, `codebook`, `signals`. Raw values match `TAB_ROUTES` keys in `frontend/src/shims/navigation.ts`.

`Tab.from(path:)` derives the active tab from a URL path using prefix matching. Order matters — longest prefixes checked first so `/report/sessions/abc123` maps to `.sessions`, not `.project`. The project tab uses exact match (`== "/report/"`) to avoid swallowing all paths.

### Bridge communication

Inbound (web → native) messages arrive through `WKScriptMessageHandler` on `window.webkit.messageHandlers.navigation`; the type list is in the full text. `report-pref` is checked against the allowlist in `tests/fixtures/report-prefs-contract.json`; `report-error` means the whole report failed to render (`ReportCrash`, ranked in `ProjectSubtitle.resolve`); `panel-state` is the only writer of the left/right/inspector open flags. Outbound: `BridgeHandler.webView` is weak and written by the view alone (never by `reset()`); `menuAction` is the single dispatch point (structured arguments, no string interpolation). `callAsyncJavaScript` has two overloads: a call that binds the result must use `contentWorld:`; never write `try await … in: nil, in: .page`. A Swift test that configures `I18n` must pin a locale (`i18n.setLocale("en")` after `configure`). After a run completes, reload with `bridgeHandler.reloadWebView()`, not an `.id` bump; `isReady` does not mean "the report is showing"; gate the trigger on analysing → ready. Pick a menu gate by what it guards: `hasChannel`, `documentState == .spa`, or `canDispatch` (both).

[full text](reference.md#bridge-communication)

### Toolbar

Four zones in the unified title bar: leading (lens-contextual button, back/forward driven by KVO), the native window title and subtitle on the detail view (`.navigationTitle` / `.navigationSubtitle`, not a custom `ToolbarItem`), and trailing contextual items. Lens switching lives in the sidebar (`LensRail.swift` and the outline's lens rows; View ▸ ⌘1–5), all routed through `bridgeHandler.activateLens`; `ContentView` has no `.principal` item.

[full text](reference.md#toolbar)

### Toolbar morphing

Menus dim, toolbars morph. Universal items are Search and Export; per-tab items are the Sessions switcher popover, the web left-panel toggle on Quotes/Codebook/Signals, the Tag sidebar toggle and the Heatmap inspector toggle. In embedded mode the toolbar is the only way to open the web nav/tag sidebars: removing these toggles makes those sidebars unreachable.

[full text](reference.md#toolbar-morphing)

### Menu bar

`MenuCommands.swift` holds the 10 menus (~89 items). It keeps every store as a plain `let`; each menu section is a `View` struct owning `@ObservedObject var bridgeHandler` (never observe directly in `Commands.body`, which rewrites the whole menu bar on every publish). Menus dim unavailable items and never hide them; a lens gate on a `menuAction` command reads `commandTab`, not `activeTab`. Do not touch `.pasteboard`. No bare-key menu shortcuts while a report is in front (the popout player is the one exception). An AppKit window is invisible to `@FocusedValue` (`PopoutOwners`, `KeyWindowWatcher`). An `NSWindow` made in code must set `isReleasedWhenClosed = false`.

[full text](reference.md#menu-bar)

### KVO for back/forward

`WebView.Coordinator` stores two `NSKeyValueObservation` properties observing `webView.canGoBack` and `webView.canGoForward`. KVO callbacks dispatch to `bridgeHandler.canGoBack`/`.canGoForward` via `Task { @MainActor in }`. Observations are auto-invalidated when the Coordinator deallocates (triggered by `.id(project.id)` on project switch).

### Zombie process cleanup

The host cannot enumerate orphans (sandbox): the sidecar polls `os.getppid()` every 2 s and SIGTERMs itself on reparenting, which needs `_BRISTLENOSE_HOSTED_BY_DESKTOP=1`. Read process metadata via libproc, never via subprocess (`ps`/`lsof` are sandbox-blocked at startup), and keep the Swift/Python `start_time` token byte-identical. Build every spawned subprocess's environment with `BristlenoseShared.childEnvironment(for:)`; never hand-roll it. Desktop ports come from `bind(0)`. Cancelling a run uses one escalation ladder (`PipelineRunner.cancelLadder`: SIGINT, SIGTERM at +5 s, SIGKILL at +30 s); don't shorten the SIGKILL step below the Python backstop. Leaving the app stops a hosted run and Analyse resumes from cache (don't make a hosted run outlive the app: its stdout pipe breaks and it records `run_failed`); the queue is kept across Quit and a crash. `applyScanResult` won't overwrite `.running`; `PipelineProgress.isStopping` is the immediate-ack contract.

[full text](reference.md#zombie-process-cleanup)

## MCP / Agent Access (31 Jul 2026 — supersedes the Connect Agent sheet)

Every desktop serve mounts the read-only `/mcp/` endpoint (design: `docs/design-mcp-extension.md`). **Settings ▸ MCP Agents** (`MCPAgentsSettingsView.swift`) holds the global Anonymise toggle, the install rows (a native-helper `.mcpb` for Claude Desktop; the Install Plugin route for ChatGPT and Codex; copyable dialects for Claude Code and Generic MCP) and a per-project register. **Turn On/Off Agent Access** is a verb swap (hidden in the project context menu unless the study is locatable and analysed, dimmed in the menu bar); access is a permission, not a connection, so "no agent installed" is never a gate. The antenna badge means exposure, not activity. Do not add a Bristlenose preference for window restoration (macOS owns it), and Cmd-R from Xcode cannot test restoration (Stop sends SIGKILL): ⌘Q a built app. The token is a per-project Keychain bearer (`MCPTokenStore`; an ephemeral scoped token on Keychain refusal, never the rotating server token); the handshake file (`MCPHandshake.swift`) is written credential-class and only for the fronted serve. Pane i18n keys are `desktop.mcpAgents.*` / `desktop.connectAgent.*`. Pre-announcements of system prompts and stock control labels quote macOS's own wording from the system loctables (read `scripts/apple-locale-map.json`, not prose). macOS 27 blocks the Node `.mcpb` for never-granted agent apps; a `type: binary` server is not blocked. The remaining detail (badge spec gap, known gaps, helper identifiers per signer, ChatGPT facts, measurements) is in the full text.

[full text](reference.md#mcp--agent-access-31-jul-2026--supersedes-the-connect-agent-sheet)

## Apple speech helper (built 18 Oct 2026, on by default since 22 Oct)

`desktop/speech-helper/` builds `bristlenose-speech`, which the sidecar launches to transcribe a first run with Apple's `SpeechTranscriber` while Whisper downloads. It is signed like ffmpeg (app-sandbox + inherit; gated by `desktop/scripts/check-speech-helper.sh`), embedded in every build, and killable with `defaults write app.bristlenose BristlenoseAppleSpeech -bool NO`. The sidecar only gets its path when the bundled sidecar runs. The one Whisper download is `WhisperDownloadModel.shared`.

[full text](reference.md#apple-speech-helper-built-18-oct-2026-on-by-default-since-22-oct)

## Code intelligence: sourcekit-lsp does NOT work on this project without a build server

Measured 11 Oct 2026 (`experiments/skills-research/lsp_probe.py`). `sourcekit-lsp`
started bare from the repo root, which is how Claude Code's `swift-lsp` plugin
runs it, has no build settings for an `.xcodeproj`, so it type-checks each file
alone. It returned no cross-file definition, zero references to a type four files
use, and **24 false compile errors** ("Cannot find type 'ServeManager' in
scope"). Pointing it at an existing Xcode index store changed nothing. It works
only behind a build server (`xcode-build-server` + `buildServer.json`). Until
someone sets one up, don't install the plugin. Its false errors would send an
agent chasing problems that do not exist. Grep across files instead.

## Settings window (Cmd+,)

Six-pane Settings window built on Sindre Sorhus's `Settings` package (an AppKit controller), not a SwiftUI `Settings {}` + `TabView`; do not reintroduce a `TabView`. Panes refit their height only on tab activation: a pane whose height depends on its own state calls `SettingsWindow.refitToContent()` (a master-detail pane passes `shrinkThreshold:`). Deep-link with `SettingsWindow.shared.show(pane:)`. Prefs reach the serve through `BristlenoseShared.overlayPreferences()`; post `.bristlenosePrefsChanged` ONLY if the pref becomes an env var (it restarts the serve and cold-remounts the SPA). A web-visible, live-swappable pref gets its own notification and bridge call; a platform-carried pref (appearance) posts nothing. Post at a gesture's end, once, through one `CommitGate`. API keys ride `BRISTLENOSE_<PROVIDER>_API_KEY` from `overlayAPIKeys`; the sidecar never reads Keychain. Spec: `docs/design-desktop-settings.md`.

[full text](reference.md#settings-window-cmd)

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

**Desktop:** the host passes `--port 0` to the sidecar; the kernel assigns a free port via `bind(0)`. `ServeManager.handleLine(_:)` parses the port from the sidecar's `Report: http://127.0.0.1:NNNN/report/` stdout line (printed *after* socket bind). Every host launch gets a fresh port — no contention with slow-dying orphans, no port-walking retry loop, no need for a deterministic-port table.

**CLI:** `bristlenose serve` defaults to port 8484, a fixed number so the link is stable (CLI users bookmark `http://127.0.0.1:8484/report/` and reload after re-running the pipeline). Pass `--port 0` to opt into kernel assignment if you need it.

The deterministic djb2-per-project allocation was removed in Apr 2026 (A6 redesign) — it only mattered for orphan-cleanup, which the sidecar now handles itself.

**WKWebView right-click → Copy Link** yields a single-session URL (the port changes next launch). Fine — Bristlenose is not a browser; users don't bookmark internal URLs.

## Patterns inherited from v0.1 (battle-tested)

These are the parts of v0.1 that survived the v0.2 rewrite because they work. Alpha leans on them too.

- `KeychainHelper.swift` — originally wrapped the `security` CLI, now uses Security.framework (`SecItemAdd`/`SecItemCopyMatching`/`SecItemDelete`). Same service names and account as Python's `MacOSCredentialStore` so either side can read keys written by the other.
- `Assets.xcassets/` — app icon and accent colour.
- Pipe reading pattern in `ServeManager` — `Task.detached` + `fileHandle.availableData` loop, originally from v0.1's `ProcessRunner.swift`.
- ANSI escape stripping regex.
- PyInstaller `--onedir` + Xcode "Copy Sidecar Resources" Build Phase pattern — preserved in `desktop/v0.1-archive/` as the reference for Track C C1.
- FFmpeg + ffprobe sibling-binary layout in `Contents/Resources/` — the path convention the sidecar's `bundled_binary_path()` helper will use.

## Key conventions

- **Bundle ID: `app.bristlenose`** — reverse-DNS of `bristlenose.app`. Irrevocable after first App Store submission. Changed from `CassioCassio.Bristlenose` (25 Mar 2026), then `research.bristlenose.app` (which referenced a non-existent `.research` TLD). v0.1-archive retains original ID (frozen snapshot). Full infrastructure plan: `docs/private/archive/infrastructure-and-identity.md`
- **macOS 15.0** (Sequoia) deployment target
- **Swift 6 concurrency** — `SWIFT_DEFAULT_ACTOR_ISOLATION = nonisolated` in build settings. Mark classes `@MainActor` explicitly
- **`@StateObject`** at App level for ServeManager/BridgeHandler, `@EnvironmentObject` in views
- **SIGINT** (not SIGTERM) for graceful serve shutdown — lets Uvicorn release the port
- **App Sandbox: currently off, on for alpha.** Today's Debug/Release builds run unsandboxed so the launcher-style CLI discovery works. Track C C0 spike determines the minimum entitlement set; C1 flips sandbox on and switches to bundled-sidecar discovery.
- **Hardened Runtime: currently off, on for alpha.** Track C C2 wires `--options=runtime` at codesign time.
- **`callAsyncJavaScript` param labels**: `in: nil, in: .page` — the two `in` parameters are frame and content world respectively
- **Dev escape hatch: two explicit env vars, three Xcode schemes.** `BRISTLENOSE_DEV_EXTERNAL_PORT` connects to an externally-running `bristlenose serve`; `BRISTLENOSE_DEV_SIDECAR_PATH` spawns a specific binary; neither set → bundled sidecar. Both set → startup error. Release builds ignore both (`#if DEBUG` guard, verified by `desktop/scripts/check-release-binary.sh` post-archive). See "Dev workflow" section.
- **Logging: `os.Logger`, not `print`**, and `log stream` hides `.debug` lines unless you pass `--level debug`. **Debug signing** uses Apple Development with `DEVELOPMENT_TEAM = Z56GZVA2QB`: the data-protection keychain validates by Team ID, so team-signed builds read provider keys silently across rebuilds, while ad-hoc signing re-prompts; don't commit a local team change. [full text](reference.md#key-conventions)

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

The first `xcodebuild` in a fresh worktree fails with `cannot find 'GeneratedBuildInfo' in scope`; re-run it. Auto-sync covers only files under `desktop/Bristlenose/Bristlenose/`: shared dirs (e.g. `bristlenose/locales/`) must be added to the Copy Sidecar Resources phase, or `Bundle.main` lookups return nil and chrome strings render as raw i18n keys. For Swift i18n sweeps start with `grep -rn ": LocalizedError"`, and grep helper-function `return "…"`, `Button("…")` and `.help("…")`, not just `Text("…")`. [full text](reference.md#dev-build-today)

### Alpha build (Track C C1 and beyond)

End-to-end orchestration lives in `desktop/scripts/build-all.sh`:

1. `scripts/fetch-ffmpeg.sh` — downloads pinned SHA256 FFmpeg/ffprobe
2. `scripts/build-sidecar.sh` — PyInstaller `--onedir` of `bristlenose serve`
3. `scripts/sign-sidecar.sh` — parallel (`xargs -P8`) per-binary codesign loop
4. `xcodebuild archive` — including the Copy Sidecar Resources Build Phase
5. `xcodebuild -exportArchive` — using `desktop/Bristlenose/ExportOptions.plist`

The signing identity comes from `SIGN_IDENTITY` env var (`-` for ad-hoc local iteration; `Apple Distribution: …` for TestFlight uploads once Track A delivers the cert).

**The Developer-ID `.dmg` is a SEPARATE build** — `desktop/scripts/build-dmg.sh` (not `build-all.sh`), a different signing path (Developer ID Application, not Apple Distribution). Full mechanics: `docs/design-dmg-build.md`. The one gotcha to pre-load before touching its signing: this app is sandboxed AND carries the Keychain-Sharing (`keychain-access-groups`) entitlement, which Xcode treats as **provisioning-profile-gated even for Developer ID** — so forcing Developer-ID signing at *archive* time fails "requires a provisioning profile." Don't re-try that dead end (nor hardcoding the team prefix, nor automatic signing which is development-only, nor dropping the entitlement which breaks the data-protection keychain → `-34018`; all verified dead 16 Jul 2026). The working flow is **archive with development signing → export as Developer ID with `xcodebuild -allowProvisioningUpdates`** (Xcode auto-mints the Developer-ID provisioning profile; no portal trip).

## Frontend build requirement

`bristlenose serve` needs the React bundle built into `bristlenose/server/static/`. If you see "React bundle not found" warnings:

```bash
cd frontend && npm run build
```

## Dev workflow: three modes via Xcode scheme variants

Three shared Xcode schemes: **Bristlenose** (default; the bundled sidecar, what TestFlight ships), **Bristlenose (External Server)** (`BRISTLENOSE_DEV_EXTERNAL_PORT=8484`; run `bristlenose serve --dev …` in a terminal, then Cmd+R) and **Bristlenose (Dev Sidecar)** (`BRISTLENOSE_DEV_SIDECAR_PATH` pointing at your venv binary). Both env vars set is a startup error; Release builds ignore both (`#if DEBUG`). The resolver is `SidecarMode.resolve`. The scheme table, failure modes and mode logging are in the full text.

[full text](reference.md#dev-workflow-three-modes-via-xcode-scheme-variants)

## Gotchas

**The full entries — the incident, the measurement, the fix — are in [`gotchas.md`](gotchas.md), by theme.** Read the theme's section before working in that area. This index is the rule and the tell, nothing more: one line per entry, same order as the file. Add a new gotcha to `gotchas.md` and its headline here.

**Serve lifecycle and the bridge** (28) — [full entries](gotchas.md#serve-lifecycle-and-the-bridge)

- A profile of the app needs a rendered report, and the dev-server flag leaves the bridge dead: a study with no report shows a native pane, and the external server gives the app no token, so `ready` never posts and signposts never end.
- "Picking up Signals…" is the idle tier's status for a first report being built, derived…
- "Is this progress line the current run's?" has a blind window: from spawn until the new…
- A popout from `WKUIDelegate.createWebViewWith` gets a live `window.opener` — the…
- A counter or token the page sends restarts with every document; state on the…
- A menu command can fail BELOW the gate — the bridge works perfectly and the operation…
- `serveManager.stop()` from `applySelectionChange` is an app-wide act on per-window state
- The detail-pane WebView must be keyed on `project.id` 
- Don't share `WKWebViewConfiguration` between WKWebViews
- WKWebView `createWebViewWith` requires the provided configuration
- WKWebView `window.open()` is blocked without `WKUIDelegate`
- `window.blur`/`window.focus` don't fire in WKWebView
- Zombie serve processes
- `Report:` readiness signal
- Bridge code on main vs feature branch
- Serve process gated on consent
- Project menu actions use `Notification.Name` not bridge
- A per-window callback hung off an app-wide channel is the multi-window bug you will…
- The desktop failure popover/classifier can mislabel — read the captured stderr, not the…
- `ServeManager` serve-lifecycle ownership is guarded by the `generation` counter — and…
- `callAsyncJavaScript` error handling
- "Bristlenose didn't finish starting within 15 seconds" was a false failure from…
- When adding a new `PipelineState` case, audit `applyScanResult` for the early-return…
- Idle-sleep is held off during a run via `RunSleepAssertion`…
- A reconnected (orphan-attached) run reads "Resuming…", not "Analysing…", in the row…
- Two writers on one reference, and the order between them decided by whether a sidecar…
- `ServeManager.start()` MUST reset `authToken` (and `serverVersion`) — `handleLine`'s…
- Zombie cleanup is delegated to the sidecar (Apr 2026, A6 redesign)

**Sidebar, toolbar and window layout** (29) — [full entries](gotchas.md#sidebar-toolbar-and-window-layout)

- A window drag is a per-frame load test: `@State` written per frame re-runs the whole `ContentView` body (use a reference box), and the outline reload per republish is held until the live resize ends; 10 → 58 window updates a second (`docs/design-client-performance.md`).
- `NavigationSplitView`'s `columnVisibility` binding is not only your writes — AppKit…
- Driving the Mac app from outside needs care, and the first-build window needs a recipe…
- A native popover anchored to web content must add the web view's top safe-area inset
- A hosted AppKit scroll view in the `NavigationSplitView` sidebar does NOT run under the…
- A `NavigationSplitView` column opens at its STORED width, not its `ideal` — and a…
- A plain `.focusable()` view in a window that opens KEY takes focus at once and draws…
- `NSSplitView` never clamps — a column minimum the window cannot hold is honoured by…
- `.searchable` on the detail column is a column minimum you never wrote — same overflow…
- An empty `@ToolbarContentBuilder` body does not compile — so a `#if DEBUG`-only item…
- A SwiftUI `ToolbarItem` cannot say "fold me last" — NSToolbar folds equal priorities…
- A sidebar toolbar item goes on the sidebar COLUMN (`sidebarWithFooter` in…
- New sidebar context-menu items go in the AppKit `buildProjectMenu`…
- A drop-initiated `NSSavePanel`/`NSOpenPanel` finds `NSApp.keyWindow == nil` and…
- `NSGridView` `.firstBaseline` row alignment silently edge-places any CUSTOM NSView
- `tableView(_:nextTypeSelectMatchFromRow:toRow:for:)`'s range is `[startRow, endRow)`…
- Translucent detail column (spike, `spike` branch, 3 Jul 2026 — Notes/Mail idiom on…
- `NSWindow.accessibilityLanguage` doesn't exist
- Native window title + subtitle live on the DETAIL view via `.navigationTitle` +…
- A titled `Window`/`WindowGroup` scene auto-populates the standard Window menu…
- Toolbar pill state indicators belong at `placement: .status`, not `.primaryAction`
- macOS 26 wraps EVERY toolbar item in its own glass capsule, so a pill that draws its…
- `.onAppear` is unreliable on toolbar items; use `.task(id:)` instead
- AppKit gives *rows* animation and *columns* none — and `NSTableColumn.isHidden` is…
- A column width set in code does not reach the layout until the table RE-FITS — and…
- `.contextMenu` on a toolbar-hosted view is swallowed by macOS's "Customize Toolbar"…
- Porting a mock illustration into a Swift webview string…
- A welcome illustration's left edge is set TWICE — the Swift frame is the settled owner…
- `fit()` clamps at `Math.min(0.9, …)`, so a bigger frame buys AIR, not content

**Lists, drag and drop, and navigation** (24) — [full entries](gotchas.md#lists-drag-and-drop-and-navigation)

- `List(selection: Set<SidebarSelection>)` for multi-select
- `Project.position` / `Folder.position` for sidebar ordering
- `SidebarSelection` enum for mixed-type selection
- View-based `NSOutlineView`/`NSTableView` inline rename: begin with…
- Segmented Picker requires non-optional selection
- Tab.from(path:) prefix order
- `.onReceive` is a View modifier, not Scene
- Don't replace `.pasteboard` in Commands
- `@AppStorage` not `@SceneStorage` for project selection
- Navigation shims use module-level refs (not closures)
- List selection must bind to `UUID?`, not a value-type model
- ALL tap gestures on List rows break selection on macOS 26
- `.onDrop` on individual List rows breaks selection
- Never stack two `.dropDestination(for: T.self)` modifiers on the same view — use one…
- `.draggable(String)` auto-coerces to URL on the macOS pasteboard — use a typed…
- `Label { ... } icon: { ... }` only takes content width — stretch to row width before…
- `.contextMenu` on List rows does NOT break selection
- `DisclosureGroup` inside `List` works for one-level folders
- `Folder.collapsed`/`createdAt` backward compat
- Drag-and-drop uses async URL loading
- Empty-space deselection in `List(selection: Set<>)` on macOS 26
- `NSOutlineView` variable row heights need `rowSizeStyle = .custom` — every other style…
- SwiftUI List inter-row gap steals drops from per-row `.dropDestination` modifiers
- AppKit `NSOutlineView` mode rows: fire click side-effects from…

**SwiftUI and AppKit mechanics** (21) — [full entries](gotchas.md#swiftui-and-appkit-mechanics)

- `@ObservedObject` in a `Commands` struct is unreliable AND expensive
- Porting a SwiftUI two-way binding to AppKit splits it into a read and a write — and the…
- `@Environment(\.dismiss)` is INERT inside an AppKit `NSPopover` — and it fails by…
- Many-item page dots → windowed indicator, not one dot per item
- `.opacity` on a SwiftUI container fades each LEAF, not the container — overlapping…
- An `@EnvironmentObject` injected into only *some* scenes is a launch crash, not a nil…
- Don't hang a lifetime on a third-party package's view-lifecycle callback
- `Logger` takes an interpolation literal, not a `String` expression
- The `Settings` package's namespace enum collides with SwiftUI's `Settings` scene…
- AppKit reveal/overlay animations must read the cell's icon frame AFTER layout
- `@MainActor` class static helpers need `nonisolated static` to be callable from…
- `.frame(width: 30, maxHeight: .infinity)` doesn't compile — "extra argument 'width' in…
- macOS has no paging `TabView` — build carousels by hand
- Hover-reveal chrome must key off hover ONLY — `@FocusState` persists after the pointer…
- A full-bleed `.overlay` hit-strip (`contentShape(Rectangle())` + `.onTapGesture`)…
- Progressive disclosure in a fixed-geometry cell = `ViewThatFits(in: .vertical)`, and it…
- SwiftUI view body too complex: extract into a `ViewModifier`, not more inline modifiers
- `isEditing` must learn that an edit ENDED from more than focus events — WebKit fires no…
- Undo/Redo editing guard (web editor only — a native field is `TextEditingFocus`, see…
- SwiftUI `CommandsBuilder` caps at 10 elements per `body`
- macOS SwiftUI `.tint()` — five traps around palette-aware theming

**Sandbox, files and cloud** (15) — [full entries](gotchas.md#sandbox-files-and-cloud)

- On macOS 27 another app's read of our container is decided by the RESPONSIBLE process…
- "The folder exists" is not "the app may read it" — under App Sandbox…
- SQLite `?immutable=1` URI parameter is load-bearing for sandboxed read-only opens of…
- The Mac counts a study's files with `run`'s own file selection, so change the two walks…
- AppleDouble `._*` files break Python scanners that read every file as UTF-8
- `FileManager.copyItem` blocks *indefinitely* on an iCloud-evicted (dataless) source…
- `-34018 errSecMissingEntitlement` on `SecItemAdd` under App Sandbox means the…
- Sandbox iteration: use `desktop/scripts/reset-sandbox-state.sh` between builds
- In the inherited-sandbox sidecar, `NSHomeDirectory()` is the REAL home, so a system…
- App Sandbox blocks `Process()` exec of system binaries — and also blocks…
- `BRISTLENOSE_DEV_SIDECAR_PATH` cannot point at a venv outside the bundle when sandbox…
- Xcode now uses build-setting-driven entitlements for App Sandbox
- Security-scoped bookmark creation needs `files.user-selected.read-write` granted before…
- A security-scoped extension follows a renamed folder, and nothing re-resolves bookmarks…
- A count that gates a destructive act returns nil for *unreadable*, never zero

**The sidecar: building, bundling and signing** (18) — [full entries](gotchas.md#the-sidecar-building-bundling-and-signing)

- Build-script pretty output goes through `report.sh` + `build_report.py` — see…
- mlx is bundled via `collect_all("mlx")`, not PyInstaller's default modulegraph walk
- `codesign --verify` a PyInstaller `--onedir` bundle by its OUTER EXECUTABLE, not the…
- `OSError: could not get source code` at sidecar import time → typeguard 4.x +…
- Sidecar bundle is built against `.venv-sidecar/`, NOT the contributor `.venv/`
- Sidecar fingerprint (`sidecar-source-hash.sh`) must EXCLUDE OS metadata
- …and it must INCLUDE every bundled data dir — the other half of the same rule, and the…
- `ensure-sidecar` says "Stamped &lt;hash&gt;…" and the very next phase fails "STALE"…
- The `Ensure Sidecar Fresh` build phase runs under Xcode's STRIPPED PATH — scripts must…
- The bundled sidecar can silently lag the repo — when desktop progress/telemetry looks…
- `mlx_whisper` also needs `collect_all`
- `sqladmin` also needs `collect_all` — and the failure is a construction-time…
- App Store §2.5.2 `itms-services` static-scan trap — the bundled CPython carries it, and…
- `Copy Sidecar Resources` script: `cp` and `rsync -a` disagree on symlink dereferencing
- For materialising a PyInstaller sidecar bundle (or any macOS bundle) from main into a…
- `excludes=` in the spec drops one named module, not its transitive deps
- `plutil -extract` splits the key path on dots, so it CANNOT read a reverse-DNS…
- `codesign --force --entitlements <file>` without `--remove-signature` first is…

**Xcode, build settings and debugging** (10) — [full entries](gotchas.md#xcode-build-settings-and-debugging)

- A custom Info.plist key cannot go in an `INFOPLIST_KEY_…` build setting — Xcode carries…
- Xcode stale indexer
- Debugging the desktop app's runtime: two traps
- Debug builds: main executable is a stub; code lives in `Bristlenose.debug.dylib`
- Xcode expands `$(SRCROOT)` reliably in scheme env-var values; `$(HOME)` is debated
- QA env vars in committed xcschemes must have `isEnabled = "NO"`
- Committing during an Xcode build fails the build — the sidecar's freshness guard sees…
- Xcode's "Validate Project Settings" nag wants to enable Hardened Runtime for Debug…
- Safari Web Inspector for WKWebView debugging
- Web Inspector

**Platform APIs, policy and sign-in** (13) — [full entries](gotchas.md#platform-apis-policy-and-sign-in)

- `import Security` does NOT re-export Foundation on macOS 15 SDK
- "This application does not support printing. Please contact the application's…
- `dlsym` a WebKit SPI identifier by its C name, which carries a leading underscore
- Two system APIs retain the object you hand them, so "drop my reference and `deinit`…
- Apple HIG pages are JavaScript-rendered — `curl` / `WebFetch` returns only the static…
- `URLResourceValues.volumeIdentifier` is typed as `Any?`/opaque, not `Hashable`
- `.nonPersistent()` creates a new partition every call
- Custom URL schemes + `.nonPersistent()` crash WebKit on macOS 26
- `kSecAttrAccessControl` and `kSecAttrAccessible` are mutually exclusive
- An HTTPS OAuth callback wants `webcredentials:`, NOT `applinks:` — and getting it wrong…
- An HTTPS OAuth callback on a developer Mac can fail because a DIFFERENT copy of the app…
- Printing is post-v1 (owner, 23 Oct 2026): no `com.apple.security.print`, no File ▸…
- Consent version bumping

**Tests, harnesses and verification** (12) — [full entries](gotchas.md#tests-harnesses-and-verification)

- A whole-suite red where every failure took 0.000s may be the test HOST exiting, and the…
- A Swift test that waits for an AppKit animation fails while the display is asleep or…
- The GitHub macOS runners give the test process a 1024×768 @1x screen, and `orderFront`…
- `-only-testing` needs the trailing `()` for a Swift Testing test
- Getting a measured VALUE out of a Swift test: only a file works, and the file must land…
- A Swift test that spins `RunLoop.main.run(until:)` freezes every SwiftUI animation at…
- A verification sweep run before all the edits have landed reports clean, because there…
- Verifying Swift while another session edits the same tree is not verification — isolate
- `StubURLProtocol` redirects arrive with NO headers, and the adapters' fetches never…
- A new Swift Testing suite that drives `StubURLProtocol` must be nested inside…
- "The test runner hung before establishing connection" is a modal dialog at launch — the…
- A shared working tree hides missing commits — and `main` not building is invisible from…

## Wiring menu actions (bridge handler cookbook)

Most menu actions run `MenuCommands.swift` → `bridgeHandler.menuAction("…")` → `bridge.ts` (a `bn:menu-action` CustomEvent) → `AppLayout.tsx` or `useKeyboardShortcuts.ts`. There are four routes in all: the bridge, a `Notification.Name` to `ContentView`, straight to AppKit, and native to native (⌘F bumps a counter the Quotes search capsule observes). Catalogue: `docs/design-desktop-menu-actions.md`.

[full text](reference.md#wiring-menu-actions-bridge-handler-cookbook)

## Run / sidecar / signing gotchas (8 Jun 2026 — full desktop-run debug)

Layered blockers from the 8 Jun 2026 desktop-run debug; each hid the next. The rules that survive: a CLI flag the desktop also injects via env must default to `None`; Ollama's model rides `BRISTLENOSE_LOCAL_MODEL`, not `BRISTLENOSE_LLM_MODEL` (route by provider in `overlayPreferences`); the sidecar needs the JIT entitlements for transcription (App-Store-review-sensitive: route through app-store-police); `sidecar_entry.py` needs `multiprocessing.freeze_support()`; CLI-shared keys live in two keychains (`KeychainHelper`/`SharedKeychainItem`; only Settings ▸ LLM Provider spends the one prompt); a stale bundled sidecar silently no-ops any new Python-emit feature (compare `run_started.process.bristlenose_version` with the tree's `__version__`, then `build-sidecar.sh` and `sign-sidecar.sh`); grep `llm_resolve` and `llm_call_failed` in the run log before theorising about provider bugs; on macOS 27 tccd judges by the responsible process, and a sandboxed helper carrying a Team-ID-prefixed app group is the public door.

[full text](reference.md#run--sidecar--signing-gotchas-8-jun-2026--full-desktop-run-debug)

## Testing

### Framework choice

- **Swift Testing** (`@Test`, `#expect`) for all unit and integration tests
- **XCTest** (`XCTestCase`, `XCUIApplication`) reserved for UI tests only — it's the only framework with UI automation
- Both can coexist in the same test target, but **never mix assertions** — `#expect` inside an `XCTestCase` is silently ignored, and `XCTFail` inside a `@Test` doesn't register ([interop proposal ST-0021](https://forums.swift.org/t/st-0021-targeted-interoperability-between-swift-testing-and-xctest/84965) is in progress)

### Conventions

A decision a SwiftUI view makes belongs in a testable helper (`DropDecision.evaluate`, `ProjectSubtitle.resolve`, …). Files are `{ClassName}Tests.swift`. Annotate the `@Suite`, not each `@Test`, with `@MainActor`. Keychain tests use `InMemoryKeychain`, `ProjectIndex` tests a temp `fileURL`, I18n tests `configure(localesDirectory:)` with fixtures. A bare `I18n()` returns the raw key, so assert on the decision, not the translation. A test that something did NOT happen must wait as long as one that it did. To see a view from a test, host it in an `NSHostingView` in a window with a forced appearance and a background.

[full text](reference.md#conventions)

### Test target setup

**`BristlenoseTests` is wired into the Xcode project** (`xcodebuild -list` shows both `Bristlenose` and `BristlenoseTests` targets). Run it with:

```sh
cd desktop/Bristlenose
xcodebuild build-for-testing -scheme Bristlenose -configuration Debug -destination 'platform=macOS,arch=arm64'
xcodebuild test-without-building -scheme Bristlenose -destination 'platform=macOS,arch=arm64' -only-testing:BristlenoseTests
```

Note `test-without-building` runs the **already-compiled** bundle — after editing a test file you must re-run `build-for-testing` first, or the stale bundle runs and your change appears to have no effect.

The target uses `PBXFileSystemSynchronizedRootGroup`, so new `.swift` files added to `BristlenoseTests/` are auto-discovered — no pbxproj edit needed per file.

**Auto-sync flattens flat-resource folders into `Resources/` and collides** — e.g. `Fixtures/{en,es}/*.json` (locale-style folders that aren't `.lproj`) all copy to `Resources/<name>.json` with no per-locale subdir, causing `Multiple commands produce '...common.json'` build errors. Fix in `Bristlenose.xcodeproj/project.pbxproj`: add a `PBXFileSystemSynchronizedBuildFileExceptionSet` referencing the synced root with `membershipExceptions = (Fixtures/en/common.json, ...)` listing each colliding file. Folder paths (`Fixtures` or `Fixtures/en`) don't work as exceptions — must list each file explicitly. The proper Xcode-side fix (folder reference instead of group) preserves the subdir structure but requires the GUI; pbxproj exceptions are the CLI-friendly workaround. Same exception set can also exclude pre-existing test files that don't yet compile under Swift 6 strict mode

Build settings must match the app target:
- `SWIFT_VERSION` — same as app (currently 5.0)
- `SWIFT_DEFAULT_ACTOR_ISOLATION = nonisolated`
- `ENABLE_APP_SANDBOX = NO` (today; matches app target; flips to YES for alpha)

### Running tests

`desktop/scripts/test-swift.sh` is the full gate (the general suite, then `PoolStarvationTimeoutTests` in a separate process). A green run deletes its logs: pass `BN_LOG_DIR=<dir>` to see your tests by name. Its pass count can read one short. Concurrent `xcodebuild test` runs hang in teardown, so read verdicts with `grep -oE "' (passed|failed) on" run.log | grep -c failed` (0 = green), not the exit code. The test target sets `TARGET_BUILD_DIR = $(BUILT_PRODUCTS_DIR)` to avoid an app-signing race.

[full text](reference.md#running-tests)

### Testability refactors

Injection points: `ProjectIndex(fileURL:)`, `KeychainStore` with `InMemoryKeychain`, `ServeManager(resolvedMode:)` (any test that calls `start()` passes `.success(.external(port:))`), and `PipelineRunner(launcher:escalationSleep:signalTarget:…)` (any test that calls `start()` passes a `launcher`).

[full text](reference.md#testability-refactors)

## See also

- `docs/design-modularity.md` — canonical reference for what ships where (Python deps, extras, Background Assets, no-fork principle across CLI + macOS)
- `docs/design-desktop-python-runtime.md` — canonical shipping architecture for the Mac sidecar specifically (write-up due as part of Track C C0)
- `docs/private/road-to-app-store.md` — current Apple-side gate sequence to TestFlight
- `desktop/v0.1-archive/README.md` — v0.1 bundling pipeline reference

### Settling a SwiftUI layout question without a build-and-click

A layout question — does this wrap or truncate, is that modifier doing
anything, how tall is this actually — is answerable in about two minutes
without launching the app, and reasoning about SwiftUI's layout rules instead
is how you get it wrong. Write a throwaway `main.swift` that reproduces the
*exact* modifier chain, run it through `ImageRenderer`, and read `nsImage.size`
/ dump the PNG:

```swift
let r = ImageRenderer(content: TheView()); r.scale = 2
print(r.nsImage!.size)                      // 420.0 x 330.5
```

`swiftc main.swift -o probe` — no project changes, no target membership, no
scheme. Set `NSApplication.shared.setActivationPolicy(.prohibited)` first so
nothing appears on screen.

**The strong form is differential.** Render the view twice, once with the
modifier under suspicion and once without, and compare the PNGs with `cmp`.
Byte-identical output proves the modifier is a no-op on that layout — which is
a much better answer than "it looked the same to me". Used 22 Aug 2026 to
settle whether `ReAnalyseConfirmSheet`'s title wraps (it does) and whether the
missing `.fixedSize` on it was a latent bug (it isn't).

**It also catches your CSS mockups lying.** The HTML stand-in for that sheet
measured ~7.5pt short of the real thing on every height — SF Symbol line boxes
and push-button metrics are the usual culprits. Quote SwiftUI's numbers in
docs, not the mockup's.

