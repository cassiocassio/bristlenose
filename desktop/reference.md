# Desktop CLAUDE.md — reference sections

Moved verbatim from `desktop/CLAUDE.md` on 5 Nov 2026 to keep that file short enough to load every session. Read the section before working in that area. Comments in code that cite `desktop/CLAUDE.md` for these topics mean this file.

## Two axes: the language moves fast, the frameworks need judgement

**Don't collapse these into one "use the latest" rule — they behave oppositely.**

**Axis 1 — the language** (Swift 5.5 → 6 → 6.2: async/await, actors, strict
concurrency, approachable concurrency). Here latest genuinely is better and the
direction is one-way. `swift-concurrency-pro` is the source; take its advice.
Caveat that the app still builds in **Swift 5 language mode** with default actor
isolation `nonisolated`, so a lot of Swift 6 advice is aspirational here — see
that skill's `VENDORED.md`.

**Axis 2 — the frameworks** (SwiftUI, especially on macOS; anything new in a
current macOS release). Here **latest is a hypothesis, not a default.** The
realistic pattern is: try the SwiftUI affordance, hit a wall, retreat to AppKit.
That is not failure, it's the normal cost of SwiftUI's Mac coverage still being
behind AppKit's.

**The worked example is our own sidebar.** It was built on SwiftUI `List` and is
migrating to AppKit `NSOutlineView` — `List` could not do source-list selection
semantics, type-to-select, keyboard navigation, or native drop insertion lines,
and the drag-and-drop failures were structural. Apple keeps Notes, Photos and
Finder sidebars in `NSOutlineView` for the same reasons. See
`docs/design-desktop-sidebar-appkit.md`.

**This directly contradicts vendored swiftui-pro**, whose Core Instructions say
the user will want to avoid UIKit unless requested — reasonable on iOS, wrong
here. Read that as axis-1 reasoning applied to an axis-2 problem: **on Mac, name
the AppKit primitive that already does the job before reaching for the SwiftUI
one**, and treat "SwiftUI can do this now" as a claim to verify on the actual
control, not a default to adopt.

None of this is a native-pivot commitment — the web SPA remains the durable
primary surface, and one AppKit surface is not evidence of a whole-app
direction.

**Independent corroboration**, so this reads as evidence rather than taste:
NetNewsWire builds at `SWIFT_VERSION = 6.2` with `NonisolatedNonsendingByDefault`
and `InferIsolatedConformances` — genuinely ahead on the language — while its Mac
UI is essentially pure AppKit. Brent Simmons committed a *new* technote on 6 Jun
2026 whose macOS section says to use AppKit and .xib files and avoid SwiftUI,
while the iOS section of the same file says the opposite. Same author, same day,
opposite advice per platform: that asymmetry is the two axes.

A dated register of what SwiftUI still cannot do on macOS — each entry with a
radar number, plus a separate list of complaints Apple has since *fixed* — is
kept in the maintainer's private notes (`/artifacts` → **Swift Corpus
Register**).

**But check the fix against our deployment floor before acting on it.**
The app ships `MACOSX_DEPLOYMENT_TARGET = 15.0` (Sequoia — the n-1 rule in
`docs/design-platform-policy.md` §"Pillar 3") on **all four schemes**, both
configurations, and `BristlenoseTests` is at 15.0 too (it was an incidental 26.1
until 25 Sep 2026, when the suite was proven on a macOS 15 guest). Pinned by
`desktop/scripts/check-deployment-floors.sh`.

Most of the celebrated SwiftUI-on-Mac improvements landed in **macOS 26** —
`List` performance, `TextEditor` rich text, native `WebView`,
`\.appearsActive` / `\.backgroundProminence`. At a 15.0 production floor those
are unreachable without an `if #available` gate, so "SwiftUI can do that now"
is usually true of the *platform* and false of *this app's shipping scheme*.
The AppKit fallback stays correct here for longer than the general commentary
suggests.

Read the floor with `xcodebuild -showBuildSettings -target … -configuration …`
and name the scheme. Hand-parsing the pbxproj gives the wrong answer, because
it cannot tell you which of the two floors a given scheme resolves to.

## Appearance (light / dark) — one seam, nothing per-surface

**Adding a window, panel, sheet, alert, menu, or popover? Do nothing. It already
themes correctly.** `AppAppearance.beginApplying()` runs once from
`AppDelegate.applicationDidFinishLaunching` and sets **`NSApp.appearance`** from
the Settings ▸ Appearance preference (`@AppStorage("appearance")` — `auto` /
`light` / `dark`), then keeps it applied via a KVO observation on UserDefaults.
Every AppKit surface the app creates inherits it. There is no per-surface step,
and adding one is the bug, not the fix.

**Never re-derive the mapping.** `"light"/"dark"/"auto"` → appearance lives in
exactly one place, `AppAppearance.swift`. Use `AppAppearance.current`
(`NSAppearance?`) or `AppAppearance.colorScheme(for:)` (SwiftUI `ColorScheme?`)
— never a fresh `switch` over the string, and never a fresh
`UserDefaults.standard.string(forKey: "appearance")`. `nil` means "follow the
system" in all three spellings, which is why `apply()` needs no `auto` case.

**This is not the seam-alignment "hammer".** `NSApp.appearance` (light/dark) is a
different property from `NSColor.controlAccentColor`, which the palette work
rules out overriding app-wide (`docs/private/100days.md` §Edo, and the `.tint()`
traps in `gotchas.md`). Appearance is the OS's own light/dark axis and every
Mac app sets it from its own preference; the accent override is a hammer because
it repaints controls the system owns. Don't let the accent rule talk you out of
the appearance seam.

**Why app-level and not per-window.** The preference can disagree with the
system's. Applied per-window — `.preferredColorScheme` on a SwiftUI scene,
`window.appearance` on an AppKit one — it reaches *only* windows that opted in,
leaving every non-window surface on the system theme and obliging each new
surface to remember. That is precisely what happened: the mapping was written
out three times, five auxiliary `Window` scenes (System Health, Type Parity,
Run Inspector, Shoal Screensaver, Shoal Tuner) had never had it applied at all,
and the export save panel plus both Locate panels shipped light-over-dark.
Fixed 2 Aug 2026 by moving to the single `NSApp.appearance` seam. Shimmer Tuner,
Keycap Gallery and Review Gallery are **not** in that list — they set their own
`.preferredColorScheme` from a local toggle because they're design tools that
preview both schemes on demand. That's a third legitimate exception, and it's
why the seam gate deliberately doesn't police `.preferredColorScheme` sites. **The tell for this whole class: a surface that is correct in Automatic
and wrong the moment the user forces Light or Dark.** QA it with the app
preference set *opposite* to System Settings — matching them hides every bug
here.

**Enforcement is mechanical, not just this document.**
`desktop/scripts/check-appearance-seam.sh` (build-all step 1a-bis, <1s) fails the
build if the mapping is re-derived outside `AppAppearance.swift`, if the raw
default is read outside it, if a save/open panel skips `adoptHostAppearance()`,
or if `AppDelegate` stops calling `beginApplying()` — the one deletion that would
leave every other assertion passing while nothing is themed. Each assertion is
proven to fail on its own violation. `AppAppearanceTests` pins the mapping, the
two spellings agreeing, unknown values falling back to *follow-system* rather
than to a forced light, and — the silent one — that the UserDefaults KVO actually
fires, since a rename of that property would apply the preference at launch and
then never again with no error anywhere.

**The two deliberate exceptions**, both belt-and-braces rather than load-bearing,
both already written — don't add a third without a reason in a comment:
- `ContentView`'s `.preferredColorScheme` — makes SwiftUI's `\.colorScheme`
  environment explicit for descendants that read it (the web-bridge appearance
  sync among them).
- `SettingsWindow.applyAppearance()` — that window is built by an AppKit
  controller, so the panes' `.preferredColorScheme` can't reach its chrome.

**Save/open panels are the one real caveat — call `panel.adoptHostAppearance()`
before presenting.** Under App Sandbox an `NSSavePanel`/`NSOpenPanel` is hosted
out-of-process by the powerbox, the single place where appearance inheritance
crosses a process boundary, so it is stated explicitly rather than trusted.
`PanelHost.window` is also the canonical host-window resolution
(`keyWindow ?? mainWindow ?? first visible canBecomeMain`) — use it for
`beginSheetModal(for:)` (and for the parked `PrintActions.print(window:)`, if
printing comes back). Bare
`NSApp.keyWindow` is wrong: a panel presented just as a drag's modal event loop
unwinds finds it `nil`, which silently downgrades a sheet to a free-floating,
system-themed panel. **Tell: the panel has its own traffic-light buttons instead
of sliding from the title bar.**

**The web report rides the same seam — do not add a bridge channel for it.** The
WKWebView inherits its window's effective appearance and the report CSS follows
`prefers-color-scheme`; no env var, no message. A `set-appearance` bridge call
did exist, was consumed by nothing (it routed via `menuAction` and AppLayout had
no `case` for it), and was removed 30 Jul 2026 — see the note at
`BridgeHandler.swift:234`. The platform already carries this fact.

## Current state vs target state

| | Current (v0.2, dev only) | Target (alpha, TestFlight) |
|---|---|---|
| Python runtime | Mode resolved once at `ServeManager.init` via `SidecarMode.resolve`; three Xcode schemes wrap Debug-only env vars (`BRISTLENOSE_DEV_SIDECAR_PATH`, `BRISTLENOSE_DEV_EXTERNAL_PORT`). Default scheme uses bundled path but expects the bundle to be present. | Bundled: `SidecarMode.resolve` returns `.bundled(path:)` pointing at `Bundle.main.resourceURL/bristlenose-sidecar/bristlenose-sidecar`. Release builds physically exclude the dev env-var reads. |
| Sandbox | Debug: `ENABLE_APP_SANDBOX = YES` (so Export/WKWebView sandbox behaviour is real in dev builds); Release: `NO` | On, with a minimal entitlement set enumerated by the C0 spike |
| Hardened Runtime | Off | `--options=runtime` at codesign time |
| Signing | Xcode automatic (ad-hoc / dev identity) | Apple Distribution cert + per-binary signing of every dylib/so/framework inside the PyInstaller bundle |
| FFmpeg | User-installed, found via `$PATH` | Bundled at `Contents/Resources/bin/ffmpeg`, trimmed codecs |
| Whisper model | User-installed or downloaded by the CLI | Background download from launch into the container's Hugging Face cache (see above) |
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
AppearanceSettingsView.swift  Appearance (auto/light/dark) + Typography (SF Pro/Inter) + Language (12 locales + Weblate link) pickers + random-project-icons toggle
LLMSettingsView.swift         Mail Accounts pattern — provider list + detail pane
TranscriptionSettingsView.swift  Whisper backend + model pickers
ToastView.swift               ToastStore (@Published message) + ToastOverlay (bottom fade, 3s auto-dismiss); one store per window, owned by ContentView (R90)
IconPickerPopover.swift       SF Symbol icon picker for project rows
```

### Bridge communication

**Inbound** (web → native): `WKScriptMessageHandler` receives messages from `window.webkit.messageHandlers.navigation.postMessage(...)`. Types: `ready`, `route-change`, `editing-started`, `editing-ended`, `focus-change`, `undo-state`, `export-counts`, `quote-action-state`, `player-state`, `lens-subtitle`, `quotes-filter`, `panel-state`, `project-action`, `find-pasteboard-write`, `store-miro-token`, `llm-failure`, `report-error`, `report-pref`. **`project-action: open-feedback` may carry `data: {kind: "problem", message}`** — the report's crash pane asking for this window's sheet as a problem report (`FeedbackSheetMode.fromBridge`; no data, as the status page sends, is feedback). **`report-pref` carries one report preference** (zoom, quote grouping, a panel's open state or width; R89, 23 Oct 2026): `BridgeHandler.storeReportPref` saves it in UserDefaults against an allowlist pinned by `tests/fixtures/report-prefs-contract.json`, and `reportPrefsSeedScript()` puts the saved values into each new web view's `.nonPersistent()` storage at document start (wiring pinned by `tests/test_desktop_report_prefs_seed.py`). App-wide and not live across windows. **`report-error` is the whole report failing to render** (decision #2, 21 Oct 2026): `ReportCrash.fromBridge` parses and bounds it, `BridgeHandler.reportCrash` keeps it for this window, `ContentView` pairs it with the sole-selected study for the sidebar, and `ProjectSubtitle.resolve` ranks it with `ReportCrash.outranks` plus its place in `resolveIdle`: it yields to failed, running, unreachable and a partial completion (causes, and their popovers stay reachable), takes the line from a queued, stopped or partial run, and in the idle tier sits below the activities (adding, batch, copy) and the error-kind forked-database delta, above screen reading and the missing/unanalysed deltas. It clears on `route-change` (the fresh layout posts it on mount after Retry's reload), `status-page` and `reset()` — never on `ready`, which `WebView.didFinish` fabricates and which can belong to the crashed document — so it never outlives the document. Receiving one lifts the boot veil (`isReady`); a queued lens intent is kept, logged once, and replayed by the `ready` a successful Retry mounts, so a click before the crash and one after behave alike. `documentState` is untouched: `.spa` after a post-mount crash, where the still-installed shims are the recovery path, so the command gates do not key on `reportCrash`. A new `PipelineState` case must be placed in `outranks` (exhaustive, no `default`), and a new `SubtitleVariant` case still has to be classified in every switch the glyph contract names.

**`panel-state` is how native sees the report's own panels** — `{leftOpen, rightOpen, inspectorOpen}`, posted from an effect in `AppLayout.tsx` whenever the SPA's `SidebarStore`/`InspectorStore` open flags change, and the only writer of `BridgeHandler.leftPanelOpen`/`rightPanelOpen`/`inspectorOpen`. Without it the View menu's panel rows can't swap Hide↔Show (the state is web-owned end to end, so there's nothing for Swift to derive). Consumed by `PanelToggle.labelKey` — see `SidebarVisibilityFocus.swift`.

**Outbound** (native → web): `BridgeHandler` holds a `weak var webView: WKWebView?`. **It is written by the view alone** — registered in `WebView.makeNSView`, cleared in `WebView.dismantleNSView` under an identity guard, and deliberately **not** by `reset()`: two writers with no defined order wiped a live registration (see the two-writers gotcha). Its `didSet` drives the published `hasChannel`, which is what lets a menu gate restate the `guard let webView` it stands in for. Some of the outbound methods (the list below is illustrative, not a census — `grep '^    func ' BridgeHandler.swift`):
- `goBack()` / `goForward()` — delegates to `webView?.goBack()` / `.goForward()`
- `switchToTab(_ tab: Tab)` — calls `callAsyncJavaScript("window.switchToTab(tab)", ...)`
- `menuAction(_ action: String, payload:)` — calls `callAsyncJavaScript("window.__bristlenose.menuAction(action, payload)", ...)`. Single dispatch point for all ~89 menu actions (security rule 3 — structured arguments, no string interpolation)
- `reloadWebView() -> Bool` — `webView?.reloadFromOrigin()`; returns false when the webView is momentarily nil mid project-switch so the caller can retry. Swaps the stale status page for the freshly-served report after a run finishes — see the report-auto-reload gotcha below

**`callAsyncJavaScript` has two overloads — choose by whether you read the result.** The async form is `(_:arguments:in:contentWorld:) async throws -> Any?` (second label `contentWorld:`); the completion-handler form is `(_:arguments:in:in:completionHandler:) -> Void` (both frame and world use `in:`). A `try await` call that **binds** the return value MUST use `contentWorld:` — writing `in: nil, in: .page` there silently resolves to the *completion* overload, whose `Void` result then won't bind (`conditional binding must have Optional type` — the TypeParity `__typeParityCollect` build break fixed in `991635c3`). Content world `.page` is required either way because `window.switchToTab` / `window.__bristlenose.menuAction` are installed by page-level JS, not a `WKUserScript`.

**Two spellings live in this file on purpose.** `switchToTab` and `menuAction` use the **real async overload** (`in: nil, contentWorld: .page`) and their `catch` blocks are live. Five `sync*`/`set*` pushers use `try? await … in: nil, in: .page`, where the `await`/`try` are inert because that spelling resolves to the *completion* overload; two more (`:447`, `:477`) call it plainly, which is the honest form. The rule that survives, stated at `BridgeHandler.swift:437`: **never write `try await … in: nil, in: .page`** — use `contentWorld:` if you want to catch, or drop the `try/await` if you don't.

_Corrected 12 Sep 2026._ This paragraph used to say `switchToTab` / `setLeftPanel` / `setLocale` / `menuAction` all wrote the inert spelling and that two `catch` blocks were dead, citing `BridgeHandler.swift:155/164/184/208/237/238`. Every clause was false: the first and last moved to the real overload (`891823da`), **`setLeftPanel` does not exist**, the method is `syncLocale` not `setLocale`, and all six anchors point at unrelated `@Published` declarations. Measure the split with the two greps above rather than trusting a remembered count.

**A Swift test that configures `I18n` and never pins a locale asserts against YOUR app's language.**
`I18n.configure(localesDirectory:)` reads `UserDefaults.standard.string(forKey: "language") ?? "en"`,
and in a test host that is the app's own domain — so a test asserting English output
passes until somebody switches the app's language, then fails with no code change.
Eight tests had this shape; they went red the moment the Welcome pane was QA'd in
German and Russian (21 Sep 2026), and the failure reads as a regression in whatever
you last touched. The tell is exact: **only the assertions that go through `i18n`
fail, while a sibling asserting the raw fallback passes** — in
`PipelineSummaryTests` the two `localisedOverflowText_*` plural tests failed and
`localisedOverflowText_fallsBackToRawWhenRegexFails` passed, because that one never
resolves a key. The stored value lives in the sandboxed container plist, which TCC
blocks you from reading, so do not try to confirm it by reading the preference —
confirm it by the failure *pattern*, and fix it the way `I18nTests`'
`localisedOverflowText_czech_selectsFewForm` always did: call `i18n.setLocale("en")`
straight after `configure`. This is the Swift instance of root `CLAUDE.md`'s
"tests must not depend on local environment", and CI never caught it because CI has
no stored preference — only a developer who changed the app's language does.
The audit is one grep: a test body containing `configure(localesDirectory` and no
`setLocale(`.

**Report auto-reload after a run finishes — don't reach for `.id`.** When a run completes and the user *stays* on the project, the detail WebView is still on the serve's status page ("Nothing to see here, yet."). The serve re-imports the report on the `run_completed` terminus within ~1s and sets `last_run`, but the WebView never reloads itself. Three traps, all hit on the determinate-progress branch (`ContentView.scheduleReportReloadOnCompletion`):
- **`.id(project.id)`-bump recreation does not reliably reload.** SwiftUI may *reuse* the `NSViewRepresentable` rather than recreate it, running `updateNSView` — whose `guard url != lastLoadedURL` short-circuits because the serve URL never changes. The bump silently no-ops. Reload directly via `bridgeHandler.reloadWebView()` (`reloadFromOrigin`, bypasses cache) instead.
- **Three signals, three questions — pick by what your gate actually guards** (added 12 Sep 2026, after a menu item spent months lit over a dead channel). `hasChannel` = is there a web view at all (a published mirror of the `weak var webView`, driven by its `didSet`); `documentState == .spa` = is this document one that carries `window.__bristlenose`; `canDispatch` = both, and the gate for anything routed through `menuAction`. **`isReady` is none of them** — see the next bullet. The rule that settles it: a menu gate should be a literal restatement of the `guard` in the thing it enables, so File ▸ Print gated on `hasChannel` (it handed the view to AppKit and dispatched no JS) while zoom and Export gate on `canDispatch`. _Print was withdrawn 23 Oct 2026 (printing is post-v1); View ▸ Reload Report (⌘R) is now `hasChannel`'s menu consumer, for the same reason — it hands the view to WebKit and dispatches no JS._ The trap when adding a signal like this is the siblings: `isReady` goes false only in `reset()` (a *selection* change) while `webView` clears at `dismantleNSView`, so a sidecar dying mid-session left ⌘P enabled and inert — the old gate's own comment still justified itself with "`webView` can't drive SwiftUI", which the change adding `hasChannel` had just falsified.
- **`bridgeHandler.isReady` is NOT "the report is showing."** The status page never posts `ready`, and `WebView.didFinish` force-sets `isReady = true` 2s after *any* load — so it stays true on stale content and never resets without a project switch. Don't gate render-state logic on it.
- **Gate the trigger on `analysing → ready`, not `!ready → ready`.** The launch-time `nil → ready` disk read of an already-finished project otherwise fires a spurious reload (and bails because the serve is still booting). Project *switches* don't need this path at all — the WebView is recreated fresh, and a serve-port change reloads via `updateNSView`; only the no-switch completion does.

### Toolbar

Four zones in the unified title bar:

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ● ● ●  ⊞  [ctx] ◀ ▶  │  Project title · subtitle  │  🔍 ↑ [ctx]           │
│ leading               │  (window title, native)    │  trailing            │
└──────────────────────────────────────────────────────────────────────────┘
```

- **Leading** (`.navigation`): lens-contextual left button (see "Toolbar morphing"), then back/forward with KVO-driven enable/disable
- **Lens switching lives in the SIDEBAR, not the toolbar** — the former centre segmented `Picker` was relocated into the project sidebar (`LensRail.swift` + the AppKit outline's lens rows); `ContentView` has no `.principal` toolbar item. `switchToTab` callers are the lens rows, the `LensRail` fallback, and **View ▸ ⌘1–5** — all routed through `bridgeHandler.activateLens` (Sessions restores the last-viewed route via `SessionsRouteMemory`; `switchToTab` itself stays "go to the tab root")
- **Trailing** (`.primaryAction`): contextual items that morph per tab — see "Toolbar morphing" below
- **Title + subtitle**: `.navigationTitle(selectedProject?.name ?? "Bristlenose")` + `.navigationSubtitle(navigationSubtitle)` on the **detail** view (native Mail/Notes pattern — title = scope/project, subtitle = "16 Sessions · 18h 23m" from the DB session count + summed `duration_seconds`). NOT a custom `.navigation` `ToolbarItem` — see the gotcha below.

Keyboard shortcuts: Cmd+1-5 (tabs) and Cmd+Opt+S (sidebar) live in the View menu (via `MenuCommands`). Cmd+[/] (back/forward) live as `.keyboardShortcut` on toolbar buttons.

### Toolbar morphing

**Principle: menus dim, toolbars morph.** The menu bar greys out unavailable items (HIG — discoverability). The toolbar shows/hides items per tab (Photos/Notes pattern — no greyed-out button graveyard).

**Universal items** (always present):
- **Search** — its own trailing item after the actions capsule, folding last (`ToolbarItemPriority`). A live field on Quotes; on Sessions, Codebook and Signals the same field shows but does nothing yet (multi-lens search is coming); absent on Project. `QuotesToolbarControls.swift`, `docs/design-desktop-nav-toolbar-rearrangement.md` §4.4 (3 Oct 2026)
- **Export** (share icon) — dropdown `Menu` whose contents change per tab. Always has "Export Report..." first. Quotes tab adds "Export Quotes as CSV"

**Per-tab contextual items** (appear/disappear):
- **Sessions**: `list.bullet` button presenting the **native session-switcher popover** (`SessionsSwitcherButton` → `SessionsPopoverContent`; label `desktop.toolbar.switchSession`) — NOT a panel toggle. The Sessions lens has no web left panel in embedded mode; the popover replaced it (`docs/design-sessions-popover-navigation.md`). ⌘⌥L on this lens posts `.showSessionsSwitcher` to present the same popover. Same glyph as the toggles below, different *kind* (momentary chooser vs stateful toggle) — accepted, and the menu twin is what keeps it honest.
- **Quotes/Codebook/Analysis**: `list.bullet` button toggling the web left panel via `bridgeHandler.menuAction("toggleLeftPanel")` — sections/themes on Quotes, codebooks on Codebook, signals on Signals. (The native project-sidebar toggle is provided by `NavigationSplitView` automatically, Mail-style.) Labels use `desktop.toolbar.{contents,codes,signals}`. ⌘⌥L in **View ▸ Show/Hide …** is the menu twin (`leftPanelKey` in `MenuCommands.swift`; the verb follows the panel's real state via `panel-state`).
- **Quotes**: Tag sidebar toggle (`sidebar.right` icon)
- **Signals**: Heatmap inspector toggle (`square.grid.2x2` icon)
- **Project**: no extra items

**The toolbar is the *only* surface for the web nav/tag sidebars in embedded mode** (Quotes/Codebook/Signals — the Sessions lens no longer *has* a web left panel; its switcher popover replaced it, and `AppLayout` gates `showSidebar`, the `[` key, and `panel-state` off the embedded sessions route). The SPA hides its own icon rails + close-× when `isEmbedded()` (`.layout.embedded` in `bristlenose/theme/organisms/sidebar.css`) — that web chrome is a non-Mac idiom and the two 36px rails wasted width the WKWebView (zero-inset, fills the detail pane) gives back to content. So the `toggleLeftPanel` / `toggleRightPanel` ControlGroup buttons + `[`/`]` keys are the user's only way to open/close them; there's no in-pane affordance to fall back on. Overlay/hover-peek mode is also gone in embedded (it was rail-triggered) — the web TOC is closed↔push only. If you ever remove these toolbar toggles, those web sidebars become unreachable in the app. See `docs/design-sidebar.md` § Desktop embedded mode.

`ExportMenuButton` is a `View` struct in `ContentView.swift` that observes `bridgeHandler.activeTab` to render the correct menu items.

### Menu bar

`MenuCommands.swift` — full native menu bar with 10 menus and ~89 items.

**`View`-inside-`Commands` pattern:** `@ObservedObject` is unreliable directly in `Commands.body` (observation doesn't reliably trigger re-evaluation) — and it is worse than useless, because the wrapper still subscribes to the whole object and every publish rewrites the entire menu bar. An open Window menu then drops the items AppKit appends at open time (the tiling group, Move to <display>, the tab items) until it is next opened; the 1.5 s agent pulse made that a collapse under a second after opening (20 Sep 2026 — the pulse also published on unchanged readings, fixed the same day in `ServeInstance.noteAgentCallCount`). `MenuCommands` holds every store as a plain `let`. Each menu section is a `View` struct (`QuotesMenuContent`, `VideoMenuContent`, etc.) that owns `@ObservedObject var bridgeHandler` — views inside `CommandMenu`/`CommandGroup` follow normal SwiftUI view lifecycle.

**Contextual dimming** — menus dim unavailable items (never hide):
- **A lens gate on a `menuAction` command reads `commandTab`, not `activeTab`** (`canDispatch ? activeTab : nil`). The report's mirrors (`activeTab`, `focusedQuoteId`, `hasPlayer`, `canUndo`, `timelineAvailable`) keep their last value when the sidecar dies, so a gate on the mirror alone stayed lit over a dead channel and the press was dropped at `menuAction`'s guard (R70, 20 Oct 2026). A mirror with no lens is gated `canDispatch && mirror`
- Quotes menu: all items dim when not on a card lens (`commandTab`). Star/Hide/Tag additionally require a focused or selected quote
- Video menu: player commands dim when `!(canDispatch && hasPlayer)`; Subtitles is a preference and gates on `canDispatch` instead. Play/Pause label swaps
- Codes menu: group/code operations dim when not on the codebook lens with a live channel. Browse/Import always enabled
- Edit > Undo/Redo: hidden when `isEditing` (lets WKWebView handle character-level undo). The report's undo dims without a live channel; a pending sidebar removal is native and does not. **While a native text field has the keyboard (the Quotes search box, a rename, a field in Settings or a sheet) they stay lit, read plain "Undo" / "Redo", and act on the field** (`TextEditingFocus`, N140)
- File > Export Report: `canExportReport` — dims while any lens is withheld (a first analysis, or a stopped one), because the SPA refuses a partial report (R61)
- File > Add Files…: dims without a selected study, and while the study can't take files (its folder missing, or failed, unreachable, or a folder `run` refuses by name — the home folder or a system root, RE#20 #110 follow-up, 24 Oct 2026 — a running or queued study takes them since decision #100, 22 Oct 2026: `selectedProjectTakesFiles`, the rule a sidebar drop asks via `StudyFinderDrop`, R47; an ejected drive keeps `.ready`, so the folder is asked too)
- View > panels: dim based on `commandTab`

**Responder chain rules:**
- Do NOT touch `.pasteboard` — Cut/Copy/Paste handled by WKWebView responder chain
- Undo/Redo hidden during `isEditing` to let Cmd+Z fall through to WKWebView. For a **native** field the menu cannot hide its way out, because AppKit's text undo is itself a menu action (`undo:`) with no key binding of its own: our item stays, asks the first responder *when pressed* and calls its `undoManager`. ⌘⌫ on Project ▸ Remove from Sidebar and Folder ▸ Delete does the same for the key (delete to the start of the line), but not for a mouse click on the item
- Cmd+F focuses the **native** Quotes search capsule and never crosses the bridge — `bridgeHandler.requestSearchFocus()` bumps a published counter `QuotesSearchToolbarControl` observes (12 Sep 2026; it previously dispatched `menuAction("find")` into a handler that queried an element embedded mode never renders, and so did nothing since it shipped). Lens-gated on `canSearch`. ⌘G/⇧⌘G were withdrawn in the same sweep — search here filters the grid, so there is no "next" to go to
- Settings Cmd+, comes from the `Settings {}` scene automatically — no custom menu item

**No bare-key menu shortcuts while a report is in front** — `s`, `h`, `[`, `]`, `m`, `?`, arrows work only in WKWebView focus. A bare key on a menu item is taken before any view sees it, so it would steal the report's own keys and stop Space typing in an editor. Menu items for these actions have no keyboard shortcut shown; Help points to `?`. **The one exception is the popout player** (29 Sep 2026): `VideoMenuContent` attaches Space, ← →, ⌥← ⌥→, ⇧, ⇧., C and fn-F *only while the player window is key* (`key(_:)` returns nil otherwise), because the player has nothing to type into. See `docs/design-desktop-menu-actions.md` §"Video menu — the popout player in front".

**An AppKit window is invisible to the menus' `@FocusedValue`.** The popout player is a plain `NSWindow`, so with it key `@FocusedValue(\.bridge)` is nil and every bridge-dependent item fell back to `.unattached` and dimmed — the whole Video menu, exactly when the viewer reached for it. `PopoutOwners` (`WebView.swift`) maps each popout to the report bridge that opened it, and `MenuCommands` falls back to it. And a key window change there does **not** reliably rebuild the SwiftUI menu bar, so anything that must follow it needs its own trigger: `KeyWindowWatcher` publishes on `NSWindow.didBecomeKey`/`didResignKey`, observed by the one section that needs it — never by `MenuCommands`, per the whole-menu-bar rule above. Any future AppKit window that should drive the menus needs both.

**An `NSWindow` made in code must set `isReleasedWhenClosed = false`.** The AppKit default releases the window on close, one release too many under ARC: after the viewer closed the popout player with its red button, the Coordinator's `popoutWindow` pointed at freed memory, and the next timecode click sent `close` to whatever lived there — `-[NSButtonImageView close]: unrecognized selector`, crashing the app (29 Sep 2026; latent since the player shipped in March). Also clear your reference on `NSWindow.willCloseNotification`, since a close can come from the red button, ⌘W or the page's `window.close()`.

### Zombie process cleanup

**The host doesn't enumerate orphans — it can't, by sandbox design.** App Sandbox blocks `proc_listpids`, `lsof`, `ps`, and friends. Instead, the orphan cleans itself: the sidecar (Python) installs a parent-death watcher that polls `os.getppid()` every 2s; on detecting reparenting (PID changes — typically to launchd/PID 1), it SIGTERMs itself for uvicorn's graceful-shutdown path. See `bristlenose/server/lifecycle.py`.

**Read process metadata via libproc, never via subprocess.** Four swaps now in the family — Swift `proc_pidpath` (zombie-cleanup PID verification, commit `38808fe`), Swift `proc_listpids`+`proc_pidfdinfo` (TCP-LISTEN socket walk, commit `5471b35`), Python `proc_pidinfo(PROC_PIDTBSDINFO)` for process start time in `bristlenose/run_lifecycle.py:_ps_start_time` (May 2026), and Swift `proc_pidinfo(PROC_PIDTBSDINFO)` for the PID-liveness check in `EventLogReader.procStartTime` (Jun 2026). All `/bin/ps` and `/usr/sbin/lsof` execs are sandbox-blocked at startup, not at first call — adding a fifth subprocess-shaped helper will crash the bundled sidecar before it serves a byte. If a fifth need arises, that's the trigger to extract `bristlenose/utils/libproc.py` (Rule of Three, long met).

**The Swift/Python `start_time` token is a cross-language equality contract — keep both sides byte-identical.** Python writes `run.pid`'s `start_time` and Swift (`EventLogReader.pythonOwnedRunIsAlive`) reads it back to confirm a run is still live; they compare for *equality*, never parse. On macOS both must emit `proc_pidinfo(PROC_PIDTBSDINFO)`'s `"<pbi_start_tvsec>.<pbi_start_tvusec>"`. The original Swift side read `/bin/ps -o lstart=` (human date string) — which both mismatched Python's libproc format on every real run *and* was sandbox-blocked — so `.running` detection silently never fired in the sandboxed build. A self-consistent test (Swift writes ps-format, Swift reads ps-format) masked it for months. If you touch either `_ps_start_time` (Python) or `procStartTime` (Swift), change both, and make the test build its PID file via the production query rather than hand-rolling the format.

The host signals "I am the parent that owns this lifecycle" by setting the `_BRISTLENOSE_HOSTED_BY_DESKTOP=1` env var when spawning the sidecar. CLI users don't get the watcher — they may legitimately `nohup` and outlive their starting shell.

**Subprocess environment — build it with `BristlenoseShared.childEnvironment(for: mode)`, never hand-roll.** Every desktop-spawned `bristlenose` subprocess needs a handful of env concerns, and assembling them by hand at each call site is exactly how they drift. `childEnvironment` is the single source of truth, folding in: (1) the minimal var allowlist + UserDefaults preferences (`buildChildEnvironment` → `overlayPreferences`); (2) `_BRISTLENOSE_HOSTED_BY_DESKTOP=1` (parent-death handshake); (3) TLS cert paths (`sslEnvironment` — PyInstaller's bundled OpenSSL points at Homebrew paths blocked by App Sandbox, so the 4 SSL vars redirect Python to the certifi `cacert.pem` inside the `.app`); (4) bundled FFmpeg/ffprobe paths (`bundledBinaryEnvironment`); (5) the active provider's API key (`overlayAPIKeys` — read from Keychain by the Swift host, since Python can't touch Keychain under sandbox); (6) for the bundled sidecar under a sandboxed host, `CFFIXED_USER_HOME` = the container (`foundationHomeEnvironment` — see the inherited-home gotcha below). The language, platform, palette and PII settings are set inline there too. Used in `PipelineRunner.start()` and `ServeManager.start()`. **Any new spawn site calls `childEnvironment`, full stop — don't re-derive the env block.** History: the run path used to hand-roll the block and silently dropped the API-key overlay, which broke `bristlenose run` the moment sandbox was enabled (Python got no key). The factory exists so that class of bug can't recur. The SSL/ffmpeg/key sinks are also why subprocess stdout is redacted with `BristlenoseShared.redactKeys(in:)` before it reaches the diagnostic-popover buffer at both spawn sites — a Python-side key echo must not ride "Copy error details" out to a pasted bug report.

**Desktop type system — activated here (this was the "critical gap").** `childEnvironment` now sets `env["BRISTLENOSE_PLATFORM"] = "desktop"`, so the server emits `data-platform="desktop"` and the SF Pro + Apple-HIG type scale in `tokens-desktop.css` renders (it shipped dark before — the cascade was unplugged at this env seam). It also pins `env["BRISTLENOSE_COLOR_THEME"] = "default"` so app.py doesn't default desktop → the Edo palette (deferred, not for TestFlight — flip to `"edo"` or make it a preference when those colours land). **Since the Phase-3 `Ensure Sidecar Fresh` build phase landed (29 Jun 2026), a plain Cmd+R self-heals this** — `ensure-sidecar.sh` rebuilds+signs the stale bundle (per-layer incremental, ~instant when fresh) *before* Copy Sidecar Resources embeds it, so no hand-run `build-sidecar.sh` + clean build is needed to see a backend/frontend change; the Dev Sidecar scheme still sidesteps the rebuild entirely. The **Appearance ▸ Typography** picker (`AppearanceSettingsView`, `@AppStorage("typography")`, default `"sf"`) lets the user opt back to Inter: `overlayPreferences` injects `BRISTLENOSE_TYPOGRAPHY="inter"` → app.py emits `data-typography="inter"` → `tokens-desktop.css`'s `:not([data-typography="inter"])` gate falls back to `:root` (Inter). The change lands on the next serve start (the picker posts `.bristlenosePrefsChanged` → restart, same mechanism as the language picker). **Appearance is NOT in that company** — it produces no env var, the WKWebView inherits light/dark from `NSApp.appearance`, and its `.onChange` post was deleted 4 Aug 2026: the restart took a fresh `bind(0)` port, which changed the detail WebView's `.id` and cold-remounted the SPA on every light↔dark switch, to serve byte-identical HTML. See `docs/design-native-typography-grid.md`.

Two layers in total:

1. **Clean quit**: `.onReceive(NSApplication.willTerminateNotification)` on the root View calls `serveManager.stop()` (SIGINT). Sidecar shuts down within milliseconds.
2. **Crash recovery (host SIGKILLed by Xcode stop button, force-quit, OOM)**: sidecar's parent-death watcher detects reparenting within 2s and SIGTERMs itself. The next host launch uses `bind(0)`, so even if the orphan is mid-shutdown, the new sidecar gets a different kernel-assigned port. Result: silent recovery, no UI surface.

**Why bind(0) instead of a deterministic per-project port:** the desktop host doesn't need port stability across launches (WKWebView gets injected with whatever URL the sidecar reports, every time). CLI users keep the deterministic 8484 default for bookmark-and-reload. Decoupling the two contracts removed ~150 lines of djb2-port-walker + libproc-cleanup scaffolding (Apr 2026, A6 redesign).

**Side effects of the redesign:**
- Sidecar prints `Report: http://127.0.0.1:NNNN/report/` *after* socket bind (kernel-assigned port). `ServeManager.handleLine(_:)` parses the port from this URL via `reportPortRegex`.
- Every sidecar exit emits one structured INFO line: `sidecar_exit reason=<r> uptime_sec=<u> original_ppid=<o> current_ppid=<c> [exc=<e>]`. Reasons: `parent_death`, `sigterm`, `sigint`, `uncaught_exception`, `normal_shutdown`. Greppable from `<output_dir>/.bristlenose/bristlenose.log` — first stop when investigating "why did the sidecar die?".
- The sidecar's watcher works on **its own state only** (own getppid, own SIGTERM). No process enumeration. Sandbox-clean.

`bristlenose run` subprocesses (the pipeline) have a separate PID-file scan/attach lifecycle managed by `PipelineRunner`; see `docs/design-subprocess-lifecycle.md`. The serve sidecar's watcher does not cascade to run subprocesses — **a hosted run installs its own** (0.5 s, `cli.py` top of `run`), and ⌘Q SIGTERMs it from `PipelineRunner.stopAllForQuit()` (since 24 Oct 2026, `quitSignal`; Stop stays SIGINT, and the run records the first signal it took, so `EventLogReader.endedByLeaving` tells a Quit from a Stop). **Leaving the app stops the run; Analyse resumes from the cache** (R19, 20 Oct 2026). Don't make a hosted run outlive the app: its stdout is a pipe to us, so it dies at its next print with EPIPE and records `run_failed` — which is what a relaunch's "Resuming…" used to end in. A run that ends after its app has gone records `run_cancelled` whatever it ended with (`run_lifecycle._failure_terminus`), and one already stopping ignores further signals, because Quit delivers two. **The queue is kept across Quit and a crash** (owner's decision, 20 Oct 2026): `RunQueueJournal` writes it to the app's defaults on every change, the run in flight first, and the next launch's `restoreQueue(from:index:)` starts it again in order. `QueueRestorePolicy` honours an entry for 92 hours from when it was asked for (Friday 4 pm to Tuesday noon) and only while its study is in the sidebar, its folder is found (an evicted iCloud folder is found: it runs as any Analyse does, no special case), carries the same study id and still holds something to analyse; anything else is dropped with a log line and no UI. A relaunch that shows the AI disclosure again waits for it and then runs the queue; one with no API key fails each study as Analyse would. Stop and Remove from queue take an entry out at once; Quit freezes the journal, so the run it stops stays the head, and the restore waits (up to two minutes) for that run to finish taking its SIGTERM before starting it again, since `start` turns away a study whose earlier run is still live. Only the copy of the app holding `run-queue.lock` (a `flock` in Application Support) reads or writes it, and a test host never does.

**Cancelling a `bristlenose run` subprocess needs signal escalation, not just SIGINT.** Whisper / torch / ctranslate2 hold the GIL during long C calls (model load can take 30–60s). Python signal handlers only run between bytecodes — SIGINT and SIGTERM both sit queued during the wedge, so a Stop click sees no effect for tens of seconds. Both Stop paths share one ladder, `PipelineRunner.cancelLadder` via `escalateCancel`: SIGINT → SIGTERM at +5s → SIGKILL at +30s, bailing at any step once the run is gone. Both signal the run's **process group** (`signalTarget` → `ownedSignalTarget`, what `Process.interrupt()` reached; never the app's own group), and so does Quit (`stopAllForQuit`). A step goes ahead while anything in that group is alive — so a worker the run left behind still gets SIGKILL, even once the next run has started — and, for an owned run signalled by bare pid, while `generation` is unchanged (owned path since 20 Oct 2026, R20; before it, owned Stop was SIGINT only and sat on "Stopping…" for minutes mid-transcription). A desktop-hosted run already stopping ignores SIGTERM (R19); its own backstop (`run_lifecycle._HOSTED_STOP_GRACE_S`, 20 s after the first signal) writes `run_cancelled` and exits. SIGKILL writes no terminus, so it waits until after the backstop could have written (grace + its 5 s lock wait + 5 s; mirrored as `PipelineRunner.pythonHostedStopGrace` / `pythonBackstopLockWait`, pinned from both sides by `tests/test_swift_python_contract.py` and `StopLadderTests`). Until 20 Oct 2026 it fired at +8 s, and a run still unwinding read "Analysis stopped unexpectedly" and was recorded as a failure. **Don't shorten the SIGKILL step below the backstop.** SIGKILL still always ends the run, and it still writes nothing for a run whose main thread cannot reach a bytecode for 30 s (the GIL held by any thread, or one native call on the main thread), because the backstop is armed by the Python-level handler, nor for one whose handler runs more than ~10 s late and whose unwind then blocks (the grace starts at the handler, not at SIGINT); and the group-wide SIGKILL also reaches workers a stopped run left behind after the next run has started; measured 20 Oct 2026, while mlx-whisper decode and model load, faster-whisper and ffmpeg all took SIGINT in under 0.4 s.

**`applyScanResult` won't overwrite `.running`.** Passive sidebar manifest scans must not clobber active runs, so the function returns early on `.running`/`.queued`/`.failed`. Three exceptions, each a read of disk replacing a read of disk: a `.running` the app doesn't own (a CLI run, R22) is disk's to end; a live run on disk replaces the ending a row shows; and "Analysis stopped unexpectedly" (`isStranded`) is replaced by any later read (decisions #40, #41, 22 Oct 2026). The app reads every study at rest again when it comes forward (`rescanOnActivation`). `handleOrphanExit` IS the "run is over" signal — it must explicitly transition `state[projectID] = .idle` itself before scheduling the manifest re-read, or the pill stays "Running" forever after the subprocess dies.

**`PipelineProgress.isStopping` is the immediate-ack contract.** Set unconditionally at the top of `cancel()` for both owned and orphan paths so the toolbar pill, popover, and sidebar row all flip to "Stopping…" before the kill propagates. Without this, the user mashes Stop while signals play out (up to 30 s).

**Sandbox implication for alpha:** `/usr/sbin/lsof` exec is blocked by App Sandbox. In the shipped build this cleanup path will silently fail. The user-visible consequence is a "port in use" error on the next launch after a crash, which should be handled with a clear restart prompt. Alternatively replace with a Swift-native TCP connect sweep across the port range. Decision deferred to C1.

## MCP / Agent Access (31 Jul 2026 — supersedes the Connect Agent sheet)

The sidecar ships the `mcp` extra, so every desktop serve mounts the
read-only `/mcp/` endpoint. Native surface since the extension shipped
(design: `docs/design-mcp-extension.md`; the sheet-era as-built record in
`docs/design-mcp-server.md` §6a is history, not current):

- **Settings ▸ MCP Agents** (`MCPAgentsSettingsView.swift`, 4th pane,
  antenna icon; the `LLM` tab renamed to **LLM Provider** in the same
  pass). Header always ("Agents read whichever project is selected"),
  Now-showing sub-line only while a serve is up (absence is the
  information), the GLOBAL Anonymise toggle (`@AppStorage "mcpAnonymise"`,
  off by default — rides `BRISTLENOSE_MCP_ANONYMISE` via
  `overlayPreferences`; when that env var is present the server's
  `grounding._mcp_anonymise_active` ignores the per-project DB flag
  entirely, so desktop behaviour is purely global; applies via the
  prefs-changed serve restart like every other Settings pref), machine-wide
  install row (`MCPExtensionInstaller` — since 29 Sep 2026 it zips the
  native helper from `Contents/Helpers` into a `type: binary` `.mcpb` at
  click time (`NativeExtensionPackage`), writes it to the container and
  `NSWorkspace.open`s THAT; a build without the helper falls back to the
  bundled Node `.mcpb`; no Claude → claude.ai download link; Install is the
  pane's ONE `.borderedProminent`), and four client tabs (Claude Desktop =
  that row; ChatGPT & Codex = **Install Plugin…** (`ChatGPTPluginInstaller`,
  the `codex://plugins/bristlenose?marketplacePath=` link into the bundled
  `chatgpt-marketplace/`) with the pasted TOML under "Or connect by hand";
  Claude Code / Generic MCP = copyable dialects, pinned by
  `MCPAgentsSettingsViewTests`). Design and measurements:
  `docs/design-mcp-native-proxy.md` §6.9–§6.11. Pane width is 660 — identical
  to the other three panes; the Settings package animates height only.
  **A per-project register sits under the divider** (21 Aug 2026,
  `docs/mockups/mcp-agents-pane.html`): which studies an agent can read,
  which could be, sessions, and when each was last asked. It was cut on
  1 Aug as over-build — *"the sidebar's menu is the act and the antenna is
  the audit"* — and that argument stopped holding when the handshake went
  plural on 20 Aug: an antenna per row cannot answer "what have I shared"
  for N projects at once. **Scope: only projects with Agent Access ON.**
  An off project is out of scope by definition, not missing — this is a
  risk register, not a control surface, and granting still happens in the
  sidebar. The rows are derived by `AgentProjectRegister` and the headline
  count prints `ServeFleet.readableProjects` — `syncHandshake`'s own gate
  set — so the audit surface and the gate cannot disagree.
- **Turn On/Off Agent Access** — verb swap, not a checkmark (§3.6a).
  Context menu (`buildProjectMenu`): its own group below housekeeping,
  HIDDEN unless `AgentAccessPolicy.canShare` (locatable AND analysed —
  session count or `lastPipelineRunAt`) and `mcpMounted`. Menu-bar twin
  (`ProjectMenuContent`): same strings, DIMS instead (opposite rule),
  antenna icon, no shortcut. `Bristlenose ▸ Connect an Agent…` opens the
  pane. "No agent installed" is never a gate — unknowable, and access is
  a permission, not a connection.
- **"Close windows when quitting an application" decides whether a relaunch restores
  windows, and the factory default is to RESTORE.** System Settings ▸ Desktop &
  Dock. While the switch is on, the system discards window state at quit for
  *every* app, and no amount of correct `WindowGroup(for:)` / scene-value code
  restores anything. Confirmed 20 Aug 2026 as the cause of an "always opens on
  Welcome" report on a Mac where the switch had been turned on; restoration worked
  immediately once it was turned off. _Corrected 5 Nov 2026:_ this entry used to
  say the switch is on by default and that restoration is therefore a minority
  path. Fresh macOS 15.7 and 27.0 guests carry no such key, which is the restore
  default; a Mac that has the switch on got it from its owner (or an old
  migration). Restoration is the common case, so the restore path (the window
  returns on its study and its lens, `WindowSeed.projectToOpen`, `LensMemory`)
  has to be right, and was not until 5 Nov (`dbf18b01f`, `4298ef0a1`).

  **Do NOT add a Bristlenose preference for this** (decided 20 Aug 2026, after a
  review floated a Settings ▸ General row for the "it forgot where I was" case).
  macOS already owns the decision globally, and duplicating a system preference
  inside an app reads as not trusting the platform. The behaviour follows the
  setting either way: off gives the old Mac thing, on gives Welcome — and
  Welcome is a decent landing rather than a consolation prize, which is what
  makes honouring the setting cheap. Safari does invent its own ("Safari opens
  with:"); treat that as the odd one out, not the model.

- **Cmd-R from Xcode cannot test window restoration — and it fails by giving a
  confident wrong answer.** macOS writes window state on a **graceful** quit
  (`applicationShouldTerminate` → `NSQuitAlwaysKeepsWindows`). Xcode's Stop
  button sends **SIGKILL**, so nothing is saved, and every Cmd-R launch looks
  exactly like "nothing to restore". You get that result whether restoration
  works perfectly or is entirely broken. Wider than restoration: SIGKILL also
  skips `applicationWillTerminate`, serve teardown, and the handshake's
  delete-on-stop, so none of those run in a Cmd-R session either. To test any
  of it: `open -n <built>.app`, arrange windows, **⌘Q the app itself**, then
  `open` again. Same family as the stale-server-on-8484 trap in the root
  `CLAUDE.md` — a check that reports confidently while measuring something else.

- **The antenna badge means exposure, not activity** (§5a-bis).
  `cellRightSlot` `.agent(exposedNow:)`: no badge when access is off;
  tertiary (pale) when on-but-not-open; secondary (solid) when the serve
  is up — driven by `Project.agentAccess` + `servingProjectPath`, NOT
  `mcp.active` (that poll still feeds `agentActiveNow` for the install
  row's status line). Precedence unchanged: ring > copy > agent (the cloud glyph that sat last was removed with `.inCloud`, 22 Oct 2026) —
  during a run the ring hides the antenna, accepted deliberately.
  **But `servingProjectPath` is NOT the spec** (verified 19 Aug 2026):
  §5a-bis says solid means *handshake live*, and `syncHandshake()` also
  requires `mcpInstanceID` + `mcpToken`. `mcpInstanceID` is nilled on every
  start/park/re-point and refilled only by an `/api/health` read, while
  `state` hits `.running` at the stdout port parse — so the antenna goes
  solid with no handshake on every start and every switch, and *stays* that
  way if the health read keeps failing (`pollAgentActivity` calls
  `syncHandshake()` only inside its successful-fetch branch). Over-claims in
  the mild direction, so it's a correctness bug, not a security one. Fix is
  to publish `handshakeProjectPath` from `syncHandshake`'s two exits and read
  that — don't re-derive a predicate its owner already computes.

- **Token: `MCPTokenStore.swift`** — durable per-project bearer, minted
  host-side, data-protection Keychain (account = SHA-256 of the
  standardized project path, non-synchronizable). Injected as
  `_BRISTLENOSE_MCP_TOKEN`; the server validates `/mcp` against it ALONE
  (scoped — it opens nothing else; `middleware.py`). **Keychain refusal
  mints an ephemeral process-lifetime scoped token instead**
  (`MCPTokenStore.mintEphemeral`, injected the same way) — since 31 Jul
  2026 there is NO fallback to the rotating server token: the handshake
  writer publishes `mcpToken` into a file another vendor's process reads,
  and the unscoped token opens `/api/*` (design-mcp-extension §3.1,
  Finding 3). NB ad-hoc-signed builds (`SIGN_IDENTITY="-"`) hit `-34018`
  on every write, so local QA builds always run the ephemeral path —
  expected; the only loss is token durability across restarts. The
  parked-sidecar re-point restores `entry.mcpToken` (spawn-time capture),
  never a fresh Keychain read — a re-mint would 401 against the parked
  process's baked env.
- **Handshake file: `MCPHandshake.swift`** — `mcp-handshake.json` in
  Application Support/Bristlenose (`{schema, port, token, instance_id,
  updated_at}`; NO project field — accountKey hashes paths for a reason).
  `ServeManager.syncHandshake()` writes it when the fronted project is
  `.running` with `Project.agentAccess` on (flag lives in `projects.json`,
  policy injected via `serveManager.agentAccessResolver` in
  `BristlenoseApp.onAppear`) and the serve's `mcp.instance_id` has been
  read off `/api/health`; deletes it on stop/shutdown/park/unshare/
  fronted-death + an unconditional sweep at host launch. Write path is
  credential-class: `O_EXCL|O_NOFOLLOW` 0600 temp + `rename(2)`,
  backup-excluded — never `Data.write(.atomic)` (umask 0644, follows
  symlinks). The sidecar deletes its own on graceful exit
  (`lifecycle.install_handshake_cleanup`, instance_id-matched, desktop-
  hosted only). Consumer: the `.mcpb` proxy in `desktop/mcpb/`
  (built by `build-mcpb.sh`, gated by `check-mcpb.sh`, build-all step 2d;
  `desktop/mcpb/**` is in `sidecar-source-hash.sh`, so proxy edits trip
  the freshness gate — expect one sidecar rebuild after pulling this).
- **`serveManager.mcpMounted` + `agentActiveNow`** come from `/api/health`
  (`mcp: {mounted, active}`, parsed by `AgentActivity.swift` — the Swift
  end of the contract `TestHealthAdvertisesMount` pins in Python). One
  long-lived 20s poll (no per-start tasks — same one-owner discipline as
  `generation`); the poll re-reads `mounted` every cycle, so do NOT gate
  it on `mcpMounted` — that was the bug where one raced startup fetch
  pinned the sheet on "unavailable" for a whole session.
- **Pane branch order is load-bearing** (`payloadPane`, inherited from the
  retired sheet): not-running speaks before any build-capability claim (a
  cold-launched app must never say "not available in this build"), and a
  running no-mcp build must never show a payload.
- **Anonymise is GLOBAL on desktop (v1)** — same `menu.quotes.anonymise`
  strings as Export, off by default (= names accompany codes in the
  agent's overview). The desktop no longer reads or writes
  `/api/projects/1/agent-settings`; that endpoint and the per-project
  `projects.mcp_anonymise` flag remain server-side (the CLI/API
  semantics, and the env-absent fallback in
  `grounding._mcp_anonymise_active`).
- **Pane i18n keys are `desktop.mcpAgents.*` / `desktop.connectAgent.*`**
  (the surviving dialect strings kept their keys) — the first dotted
  segment is the namespace FILE. Bare `mcpAgents.*` resolves to nothing
  and renders raw keys (bit once, caught in review).
- **The Claude Desktop tab pre-announces the one-time macOS prompt**
  (`mcpAgents.claudeDesktopPromptNote`, under the install row, 3 Aug
  2026). *Scope since 29 Sep 2026:* macOS ≤ 26 and the Node `.mcpb` only —
  on 27 the Node path shows the Files & Folders note instead, and a build
  carrying the native helper shows neither — unless its last Install fell
  back to the Node `.mcpb` (the native package failed), when the Node note
  shows for the rest of that visit (`MCPExtensionInstaller.nodeNotesApply`,
  R42, 24 Oct 2026). Two things about it are load-bearing rather than stylistic.
  **(1) It sits BELOW the row** because the proxy reads the handshake
  only inside tool calls — so `"Claude" would like to access data from
  other apps` fires on the first *question*, not on install; a note
  placed above the button would mis-set the very expectation it exists
  to set. **(2) Every locale quotes macOS's OWN dialog wording and
  Allow-button label**, lifted from `TCC.framework`'s
  `Localizable.loctable` (`REQUEST_ACCESS_SERVICE_kTCCServiceSystem`
  `PolicyAppData` + `REQUEST_ACCESS_ALLOW`), not translated
  independently — recognition is the whole mechanism, and a
  well-translated-but-different sentence would defeat it. **Reuse that
  loctable trick for any future pre-announcement of a system prompt**;
  `plutil -convert json -o - <loctable>` reads it, and it carries 42
  locales. **It covers stock control _labels_ too, which is the commoner
  case** — AppKit's own `Common.loctable` carries `Choose`, the
  `NSOpenPanel` button, so a panel we present reads the exact word the
  researcher already sees in every other open panel on their Mac
  (`Auswählen`, `Choisir`, `選択`, `Выбрать`). Used for Settings ▸ General
  in `38b76bfa`. **Check the loctables before hand-translating any string
  that names a system control** — and note Apple's locale codes differ from
  ours, so several need an alias to find their row. **Do not take that map
  from prose: read `scripts/apple-locale-map.json`**, which
  `scripts/apple-locale-map.py` derives by probing the corpus. This line used
  to carry the map itself and said `pt-BR`→`pt`, which is wrong — bare `pt`
  is Apple's *legacy* Brazilian spelling (454 tables to `pt_BR`'s 2,589, and
  no file carries both), so the lookup resolved, returned nothing, and read as
  "Apple ships no translation here". It hid 91 of the 264 strings Apple
  answers in Brazilian Portuguese. `nb`, `zh-Hant` and `pt-PT` are the same
  trap in waiting: all three exist verbatim as Apple codes carrying ~75 keys
  against ~211,000, so existence proves nothing and only coverage does.
  Corrected 22 Sep 2026; `.claude/agents/i18n-review.md` §6c has the record.
- **Known gaps, deliberate:** the handshake follows the *fronted* serve
  only (a parked warm sidecar's live `/mcp` is not advertised — v1 scope);
  there is no token revocation in the app (Turn Off Agent Access deletes the
  handshake, which is the operative revocation; `MCPTokenStore.revoke()`
  was never wired and was removed 15 Oct 2026, once tokens were keyed by
  study and it would have deleted the wrong account). _(The third entry here — "no
  consent-version bump yet for the agent recipient class" — was stale and
  is removed: it shipped 1 Aug 2026, `09b348b1` + `6df94d4f`, and
  `AIConsentView.currentVersion` is 2.)_
- **The native MCP helper is built in the Copy Sidecar Resources phase, and its
  identifier follows the signer kind.** `desktop/mcp-helper/build-helper.sh`
  compiles `bristlenose-mcp` for the app's floor and signs it with the identity
  the app is being signed with: Developer ID → `app.bristlenose.mcp.devid`, Apple
  Distribution → `app.bristlenose.mcp`, Apple Development (Debug) →
  `app.bristlenose.mcp.dev`; ad-hoc builds skip it. The `.dev` name is not
  cosmetic: a sandboxed helper's container remembers the *kind* of signer that
  first ran it, and a Debug build claiming the store name would make the
  TestFlight helper hang on this Mac (`docs/design-mcp-native-proxy.md` §6.7).
  The `.dmg` lane pins `BRISTLENOSE_HELPER_CHANNEL=devid` at archive because it
  archives Apple Development and re-signs at export. **Two ChatGPT facts that
  cost a test cycle each:** a plugin is used only when the question mentions
  @Bristlenose (without it ChatGPT may call its own built-in `list_projects`),
  and ChatGPT never updates a plugin in place — ⋯ ▸ Uninstall, then Install
  plugin. Claude does update in place, but only for a higher manifest version.
- **macOS 27 silently blocks the shipped Node `.mcpb` for any agent app
  that has never been granted, and how Claude launches a server decides
  it.** Measured 29 Sep 2026 in a clean, SIP-on 27.0 guest
  (`docs/design-mcp-files-and-folders.md` §1). Claude Desktop runs a
  **Node** server *inside its own* `Claude Helper (Plugin)` utility process
  (`node.mojom.NodeService`; "Using built-in Node.js" in the log), so Claude
  is the responsible process. The container read is then cross-team:
  `EPERM`, and tccd records a denial for `com.anthropic.claudefordesktop`
  with no dialog. A **`type: binary`** server is spawned through
  `Claude.app/Contents/Helpers/disclaimer --pgroup` ("Using basic execution"
  in the log), so the binary is its own responsible process, and a
  Z56GZVA2QB-signed binary reads our container with no grant. Two
  debugging traps from the same run: the Node proxy's stderr lands in
  `~/Library/Logs/Claude/main.log` as `[UtilityProcess stderr] [bn-proxy]`,
  **not** in `mcp-server-Bristlenose.log`, which carries only the protocol
  frames; and installing a same-named `.mcpb` over an existing one only
  **previews** it (the dialog offers Uninstall), so a proxy swap is
  uninstall-then-install.

## Apple speech helper (built 18 Oct 2026, on by default since 22 Oct)

`desktop/speech-helper/` builds `bristlenose-speech`, which the **sidecar** launches to transcribe a first run with Apple's `SpeechTranscriber` while Whisper downloads (`docs/design-apple-first-transcription.md`). Three things to know before touching it:

- **Signed like ffmpeg, not like the MCP helper.** The sidecar launches it, so it carries app-sandbox + inherit and nothing else, and ad-hoc signing is allowed; `bristlenose-mcp` is launched by a foreign app and is the opposite. `desktop/scripts/check-speech-helper.sh` gates it, and each of its checks has been shown to fail on its own violation. Run standalone, the signed binary traps with exit 133 (inherit needs a sandboxed parent): to try it by hand, re-sign a copy with `codesign --force --sign - --identifier app.bristlenose.speech <copy>`.
- **Embedded in every build since 22 Oct 2026** (the Copy Sidecar Resources phase), as the fifth nested executable. `check-pkg-shippable.sh` and `check-dmg-shippable.sh` require it and run `check-speech-helper.sh` on each copy, `check-release-binary.sh` scans `Contents/Helpers`, and `tests/test_entitlements_split.py` (`TestTheSpeechHelperShipsAndIsGated`) pins all of that. (`check-bundle-integrity.py` walks only the sidecar bundle, for PyInstaller's strip damage, so it does not cover the helper and need not.) `BristlenoseFlags.appleSpeech` is now a kill switch, on unless `defaults write app.bristlenose BristlenoseAppleSpeech -bool NO`; Python's `experimental_apple_speech` likewise defaults on.
- **The sidecar only gets its path when the bundled sidecar runs** (`BristlenoseShared.appleSpeechEnvironment`): a dev sidecar is unsandboxed, and would launch the helper straight into exit 133. Under the Dev Sidecar scheme the Apple path therefore never engages, and Python falls back to Whisper.

The one Whisper download is `WhisperDownloadModel.shared` (a singleton, so the lazily built Settings window needs no injection). It runs the sidecar's `doctor --fetch --progress-lines` and asks `doctor --whisper-status` whether Whisper is on disk, so it never computes the Hugging Face cache path itself.

## Settings window (Cmd+,)

Canonical macOS Settings window with 6 icon-toolbar panes (General, Appearance, LLM Provider, Transcription, Accounts, MCP Agents), built on **Sindre Sorhus's `Settings` package** (AppKit `SettingsWindowController` swapping `NSViewController` panes), **NOT** a SwiftUI `Settings {}` + `TabView`. `SettingsWindow` (`SettingsView.swift`) owns the controller; each pane wraps the existing SwiftUI view. The package sizes each pane to `fittingSize` and animates `setFrame` both ways, so short panes shrink — but **only on tab activation**: `setWindowFrame`'s two callers are both tab switches, and the pane view is pinned by required constraints that beat `NSHostingView`'s 750-priority intrinsic height, so a pane whose height depends on its own state compresses or clips rather than resizing, silently. Such a pane calls `SettingsWindow.refitToContent()` (measured 21 Aug 2026; the consequences for pane authors are in `docs/design-desktop-settings.md`). **A master-detail pane passes `shrinkThreshold:`** — the re-fit is asymmetric: it grows past layout noise always (a pane wanting more room is *compressed*, not scrolled), and shrinks only when the saving beats the threshold, so picking rows in a list doesn't resize the window on every click. Reduce Motion is honoured inside `refitToContent`, not at the call sites. **Do NOT reintroduce a `TabView`** (it high-water-marks: grows to the tallest tab, never shrinks, because a greedy `.formStyle(.grouped)` Form gives the window no natural-height signal). A hand-rolled `NSWindow.setFrame` shim was tried and deleted; the package is the canonical fix (see `docs/design-desktop-settings.md`). `AppDelegate.showSettingsWindow(_:)` answers the one remaining responder-chain caller, the web bridge — everything with a pane in mind deep-links via `SettingsWindow.shared.show(pane:)`, the provider-problem pill included; `CommandGroup(replacing: .appSettings)` supplies Cmd+,. Help text in Appearance/Transcription is an in-cell subtitle (title + secondary `Text` in the control's label — no row keyline). Settings sync to the serve process via env vars (`BristlenoseShared.overlayPreferences()` reads `UserDefaults` and injects before launching — `BristlenoseShared`, not `ServeManager`). **Adding a pref? Post `.bristlenosePrefsChanged` ONLY if the pref actually becomes an env var.** That notification means "the sidecar's baked env is stale", and `ServeFleet.applyEnvChange()` answers it — `BristlenoseApp` owns the observer, and the fleet fans out per serve on `ServeEnvStaleness.action` (`.restartNow` for the fronted serve, *for any serve exposed to agents*, and for a serve still booting whose spawn env (`ServeEnvStaleness.fingerprint`) differs from the current one, since nothing re-checks it on reaching running (R35, 20 Oct 2026); `.restartOnNextFront`; or `.nothing`). A restart drains the warm slot and respawns, which takes a fresh `bind(0)` port, changes the detail WebView's `.id` (keyed on `ServeSession.viewID` in `ContentView.swift`), and **cold-remounts the SPA**: route, scroll position, open panels and focus all lost, plus the boot wait. Copying the neighbouring `.onChange` is the trap — the appearance pref did exactly this until 4 Aug 2026, restarting the serve on every light↔dark switch to deliver byte-identical HTML. Three shapes, pick by what the pref actually drives: **env var → post it** (typography, language); **web-visible but live-swappable → its own notification + a bridge call** (palette → `.bristlenosePaletteChanged` → `setColorPalette()`); **carried by the platform → post nothing** (appearance — the WKWebView inherits `NSApp.appearance`). The tell you got it wrong: the report flashes and loses its place when the pref changes. **And post at a gesture's end, only when the value changed:** a slider on release, a text field on Return or focus loss, plus the pane's own exits (row change, `onDisappear`, the Settings window resigning key or closing), all through one `CommitGate` so the duplicate exits are no-ops. Quit is not one of those exits: no window closes on terminate. So `applicationShouldTerminate` saves a pending API key through `APIKeyQuitSave`, which writes off the main thread behind `.terminateLater` and posts nothing, and `commitsAllowed` stands the pane's own commits down for the rest of the quit. A per-step `.onChange` post restarted the serve once per slider notch and per Azure keystroke until 20 Oct 2026 (R34); `LLMSettingsView.commitPending` is the worked example. API keys ride `BRISTLENOSE_<PROVIDER>_API_KEY` from `overlayAPIKeys` (the sidecar never reads Keychain; this line said the opposite until 4 Sep 2026 — the CLI on the same Mac reads the login-keychain copy the app keeps, see the two-keychains bullet under Run / sidecar / signing gotchas). LLM tab uses Mail Accounts pattern (sidebar list + detail pane). One provider must always be active; activation guarded by status.

See `docs/design-desktop-settings.md` for the three tab specs, the UserDefaults→env var mapping table, and the `ProviderStatus` model.

**Alpha change:** sandboxed Python can't exec `/usr/bin/security`, so Track C C3 replaces the CLI-based credential store with either `pyobjc-framework-Security` or a Swift-fetches-then-injects-via-env pattern (preferred). The env-var pattern is symmetric with `overlayPreferences()` and keeps Python out of the Keychain entirely.

## Key conventions

- **Logging: `os.Logger`, not `print`.** `Logger(subsystem: "app.bristlenose", category: "<area>")`. Use `print` only for scripts, never in shipped Swift code. **`log stream` hides `.debug`-level lines by default** — a `.debug(...)` call shows in Xcode's console but NOT in `log stream --predicate '…'` unless you add `--level debug` (or `--debug`); `.info`/`.notice`/`.error` show without the flag (Console.app: Action → Include Debug Messages). Cost several round-trips during the sidebar lens-selection debug — the instrumentation looked like it "printed nothing" when it was only level-filtered. For a live-QA trace you want the user to read back, prefer `.notice` (visible in their default `log stream`) or tell them to pass `--level debug`.
- **Debug signing uses Apple Development + `DEVELOPMENT_TEAM = Z56GZVA2QB`** (Martin's personal team). A **stable team identity** keeps Keychain access prompt-free across rebuilds — but the *mechanism* changed with the 2 Jun data-protection-keychain migration (`8b2ef51`), which **supersedes** the old "Always Allow ACL bound to the binary hash" framing. `KeychainHelper` now uses the **data-protection keychain** (`kSecUseDataProtectionKeychain`) with a team-scoped `keychain-access-groups` entitlement (`$(AppIdentifierPrefix)app.bristlenose`); the DP keychain validates by **Team ID, not binary hash** (Apple TN3137; cf. steipete/CodexBar #585), so any team-signed build reads its own provider keys **silently and across rebuilds — no per-key "Always Allow" prompt at all**. The one path that still re-prompts is **ad-hoc** signing (`None` + `Sign to Run Locally`): empty `$(AppIdentifierPrefix)` → access group breaks → fallback to the *legacy* file-based keychain, which binds grants to the binary hash and re-prompts every build. So the stable `Z56GZVA2QB` team matters for keeping the **access-group entitlement valid**, not for "ACL persistence." Contributors without that team configured will see "No signing certificate found for team Z56GZVA2QB" on Debug build — fallback is Xcode → Bristlenose target → Signing & Capabilities → Debug → set Team to your own (or None + Sign to Run Locally). **Do not commit that local change.** Release config is independent (Apple Distribution + Mac App Store provisioning profile, unaffected by Debug signing choice). **First Cmd+R after switching identity fires two one-time non-Keychain prompts** — (1) `codesign wants to access key "Apple Development: …"` (signing-key Always Allow — that's the *signing* private key in the login keychain, accessed by the build tool, unrelated to our provider keys), (2) `"Bristlenose" differs from previously opened versions` (LaunchServices, Open Anyway). _Superseded (pre-2-Jun, file-based keychain): a third "Keychain ACL-extension prompt per stored provider key" used to fire here (Verified 16 May 2026: macOS extended the existing item's ACL rather than orphaning it). The data-protection-keychain migration removed it for team-signed builds — own-access-group reads no longer prompt._ Second Cmd+R is silent — that's the test. **One deliberate exception since 4 Sep 2026:** the login-keychain *copy* of each CLI-shared key (`SharedKeychainItem`) lives on the legacy keychain, so an item `bristlenose configure` created prompts the app once (Always Allow) when it is first adopted — bounded by a ledger, never per build; see the two-keychains bullet under Run / sidecar / signing gotchas.

## Build

### Dev build (today)

**The FIRST `xcodebuild` in a fresh worktree fails with `cannot find 'GeneratedBuildInfo' in scope` — re-run, it succeeds.** `GeneratedBuildInfo.swift` is gitignored (doesn't follow worktrees) and is written by the pre-compile "Run Script" build phase (`scripts/generate-build-info.sh`). On the very first build of a fresh worktree the file doesn't exist yet, and the `PBXFileSystemSynchronizedRootGroup` snapshots the Compile-Sources list *before* the script creates it — so that build can't see the just-generated file and errors. The file is now on disk, so the **second** build discovers it and compiles clean. Not a real error; don't chase it. (Same class as the gitignored-binaries-don't-follow-worktrees gotcha, but for a generated source file rather than ffmpeg/models.)

**Auto-sync only covers files inside `desktop/Bristlenose/Bristlenose/`.** Shared data dirs at the repo root (e.g. `bristlenose/locales/`) won't ship in the bundle unless an explicit Copy Bundle Resources phase or shell-script copy puts them there. Without that, `Bundle.main` lookups return nil at runtime — symptom is chrome strings rendering as raw i18n keys (e.g. `desktop.settingsTabs.llm` instead of "LLM"). The "Copy Sidecar Resources" shell-script phase in `Bristlenose.xcodeproj/project.pbxproj` is the established pattern for this — it `rsync`s the sidecar, ffmpeg, models, and locales (added Apr 2026 after locales were missing from the bundle on `main`). Add new shared dirs to that phase rather than inventing new ones.

**Swift i18n sweeps: grep helper-function `return "…"` + `Button("…")` / `.help("…")`, not just `Text("…")`.** _(Authoring a string rather than sweeping for one? See §"A user-facing string needs a key" above — this is the audit recipe, not the rule.)_ **Start with the six `LocalizedError` conformers** — `grep -rn ": LocalizedError" desktop/Bristlenose/Bristlenose` — which held 6 of 6 gaps on 21 Sep 2026, then widen. Hardcoded user-facing strings hide in computed vars and static funcs that `return "…"` (e.g. `PipelineActivityItem.headlineStatus`, `pillHelp`, `humanCategoryLabel`) and in `Button("…")` / `.help("…")` / `.accessibilityLabel("…")`. A `Text("…")`-only grep undercounts and ships a half-localised view (popover header English, body translated). Grep `return "[A-Z]`, `Button("`, `.help("`, `.accessibilityLabel("` too. **Watch static funcs shared with English-only surfaces** — but check the sharing is still real. This line named `humanCategoryLabel` as the single source for the UI label *and* the English-only "Copy error details" payload, and called the fix a UI-vs-plaintext split, deferred (cz-branch i18n review Finding 13). **It had not been shared since `11435ddd`**: the payload prints `category.rawValue` — the wire name, `out_of_credit`, which is what a bug report wants — so the function had exactly one caller and the deferral was guarding nothing. Localised on 21 Sep 2026 as `PipelineFailureCategory.labelKey`; the function is gone. The class of finding is real, the instance was stale, and the tell was cheap: `grep -rn '<funcName>' desktop/ --include='*.swift'` and count the *production* callers before believing a doc about them.

## Dev workflow: three modes via Xcode scheme variants

After Track C C1 lands, three shared Xcode schemes map to three sidecar resolution modes. Pick the scheme in the Run-button dropdown next to Cmd+R. Each scheme pre-sets the appropriate env vars; Debug-only `#if DEBUG` guards mean Release builds physically exclude these reads and always use the bundled path.

| Scheme | Env vars it sets | Mode | Purpose | Failure mode |
|---|---|---|---|---|
| **Bristlenose** (default) | _(none)_ | `bundled` | What TestFlight ships. Spawns the sidecar at `Bundle.main.resourceURL/bristlenose-sidecar/bristlenose-sidecar`. Exercises the full shipping flow end-to-end. | Debug + bundle missing → `.failed` state + SwiftUI error card with "set `BRISTLENOSE_DEV_SIDECAR_PATH` or run `desktop/scripts/build-sidecar.sh`". Release + bundle missing → `.failed` + "installation corrupted" + Reveal in Finder. |
| **Bristlenose (External Server)** | `BRISTLENOSE_DEV_EXTERNAL_PORT=8484` | `external` | Fast CSS/React iteration. Start `bristlenose serve --dev trial-runs/project-ikea` in a terminal, then Cmd+R. App connects to the external server — no subprocess. Live CSS endpoint re-reads on every request; Vite HMR pushes React changes. | App can't reach `127.0.0.1:<port>` → standard connection error + retry. Terminal server missing → same. |
| **Bristlenose (Dev Sidecar)** | `BRISTLENOSE_DEV_SIDECAR_PATH=/Users/cassio/Code/bristlenose/.venv/bin/bristlenose` | `devSidecar` | Swift spawns the exact binary you point at — usually your dev venv. Iterate on Python + test the full ServeManager subprocess flow without a PyInstaller rebuild. `Logger.warning` fires on mode resolution so a poisoned env var is visible. | Path invalid (non-existent, directory, non-executable) → `fatalError` with the resolved path (Debug only; never in Release because the env-var read is `#if DEBUG`-guarded). |

**Both env vars set simultaneously** → `ServeManager.init()` fails with "Both dev env vars set — pick one." Catches configuration mistakes at launch rather than on first project click.

**Mode logging.** `ServeManager` uses `Logger(subsystem: "app.bristlenose", category: "serve")` and emits one line at startup: `Mode: external-server, port=8484` / `Mode: dev-sidecar, path=/Users/.../bristlenose` / `Mode: bundled, path=/Applications/.../bristlenose-sidecar`. Shows up in Xcode console, Console.app, and `log stream --predicate 'subsystem == "app.bristlenose"'` in Terminal. Release builds get automatic privacy redaction.

**Swap schemes via the dropdown** next to the Run button in Xcode. To set your own env-var value inside a scheme: Product → Scheme → Edit Scheme → Run → Arguments → Environment Variables. For personal paths (e.g. a non-default venv location), edit the scheme's env-var value directly — the schemes are checked into `xcshareddata/xcschemes/` so the default values are shared, but personal overrides stay local until you commit them.

**Linux / Windows contributors** never touch this — these env vars are read by Swift, not Python. If you're working on the Python sidecar or React frontend, run `bristlenose serve` directly from your terminal and use any browser; the macOS shell is out of scope.

See `docs/design-modularity.md` "External dev server" glossary entry for the implementation spec. Underlying resolver is `SidecarMode.resolve(externalPortRaw:sidecarPathRaw:bundleResourceURL:fileManager:)` — a pure function (takes the two env-var raw strings as typed `Optional<String>` rather than an env dictionary, so the string literals live only inside the caller's `#if DEBUG` block and are absent from the Release Mach-O). Unit-tested in `BristlenoseTests/SidecarModeTests.swift` (orphan target today — see test-target note in this file).

## Wiring menu actions (bridge handler cookbook)

### The 3-file chain

Every menu action follows the same path:

```
MenuCommands.swift                    → bridgeHandler.menuAction("exportReport")
  ↓ callAsyncJavaScript
bridge.ts                             → window.dispatchEvent(CustomEvent("bn:menu-action"))
  ↓ event listener
AppLayout.tsx (or useKeyboardShortcuts) → React store call / DOM action
```

**But not every menu command is a `menuAction` — there are four routes.** The bridge (above); a `Notification.Name` to `ContentView` (project ops); straight to AppKit (`PrintActions`, parked since printing went post-v1 on 23 Oct 2026); and **native to native**, where the target is a native control and nothing crosses the bridge. ⌘F is the first of those: `requestSearchFocus()` bumps a published counter the Quotes search capsule observes. Reach for it whenever the thing the command operates on already lives in Swift — routing through the SPA and back is how ⌘F spent its whole life dispatching cleanly into nothing.

_The worked example above was `menuAction("find")` until 12 Sep 2026, which by then was the one action that had just been deleted from both ends._

Most menu actions do take the bridge route. Two frontend listeners handle them:
- **`AppLayout.tsx`** — panel toggles, find actions, and modal/export actions (things that need AppLayout state)
- **`useKeyboardShortcuts.ts`** — quote/player actions (things that need FocusContext/QuotesContext closures)

### Adding a new handler

1. **Usually no Swift changes needed** — most menu items already dispatch via `bridgeHandler.menuAction("actionName")`. The exception is a command whose target is a *native* control: that needs a `@Published` counter on `BridgeHandler` plus an `.onChange` in the control, and no bridge hop at all (see the four routes above)
2. **Choose the right listener** — if the handler needs FocusContext/QuotesContext/PlayerContext, add it to `useKeyboardShortcuts.ts`'s `handleMenuAction` switch. Otherwise add it to `AppLayout.tsx`'s `bn:menu-action` handler
3. **Delegate to existing logic** — most actions already have implementations in `useKeyboardShortcuts.ts` or React stores

### Action catalogue

See `docs/design-desktop-menu-actions.md` for the full catalogue (65+ actions across AppLayout, useKeyboardShortcuts, project ops, codebook stubs, edit ops), payload conventions, `getState()` stubs, and recommended implementation order.

**Quick pointers:**
- AppLayout (`bn:menu-action` handler) owns panel toggles, modals, exports, zoom, dark-mode toggle, codebook dispatches. **Not the Find family any more** — ⌘F is native, ⌘G/⇧⌘G are withdrawn, and ⌘E's `focusSearchInput()` half is inert in embedded mode (correct in the browser, where the SPA renders its own SearchBox)
- `useKeyboardShortcuts.ts` (`handleMenuAction` switch) owns quote/player actions that need FocusContext/QuotesContext/PlayerContext closures
- Payloads only for data the native side has that the web side doesn't (e.g. `findNext` text from `NSPasteboard.find`)

## Run / sidecar / signing gotchas (8 Jun 2026 — full desktop-run debug)

These are the layered blockers that broke desktop ChatGPT runs end-to-end. Each hid the next; the resolution ledger (`llm_resolve` lines, below) is what finally surfaced the root.

- **`run --llm` default beats the desktop-injected provider env var.** The `run`/`analyze` CLI option `--llm` previously defaulted to `"claude"` and was *always* passed into `settings_kwargs`, so `load_settings` saw it as a CLI override — which outranks `BRISTLENOSE_LLM_PROVIDER` (the env var the Swift host injects from `activeProvider`). Net: GUI says ChatGPT, run goes to the Anthropic endpoint, the model env var (`gpt-4o`) rides along → 404 `model: gpt-4o`. Fixed by defaulting `--llm` to `None` and only passing it when explicitly set (`bristlenose/cli.py`). **When adding a CLI flag whose value the desktop also injects via env, default it to None** — a non-None CLI default silently wins over the host injection. Pinned by `tests/test_desktop_config_resolution.py::TestRunCommandDefaultDoesNotOverrideEnv`.
- **Ollama model choice rides a DIFFERENT env axis than cloud — `BRISTLENOSE_LOCAL_MODEL`, not `BRISTLENOSE_LLM_MODEL`.** `BristlenoseSettings` has two model fields: `llm_model` (cloud, ← `BRISTLENOSE_LLM_MODEL`) and `local_model` (Ollama, ← `BRISTLENOSE_LOCAL_MODEL`, default `llama3.2:3b`). For the `local` provider, `llm_model` is *cosmetic* — execution reads `local_model` (`config.py` `_fill_provider_default_model` docstring; `LLMClient` `model = self.settings.local_model`). `overlayPreferences` originally injected the resolved model into `BRISTLENOSE_LLM_MODEL` for *all* providers, so a desktop Ollama run silently dropped the user's pick (`gemma4:31b`) and fell back to the `llama3.2:3b` default — which is too small for structured output and 100%-fails topic segmentation ("All topic segmentation calls failed", schema echoed back as the response `input_value={'$defs': …}`). The manifest records the cosmetic `llm_model` (`gemma4:31b`) while `llm-calls.jsonl` telemetry shows the real `gen_ai.request.model=llama3.2:3b` — that split is the diagnostic tell. Fixed (29 Jun 2026): `overlayPreferences` routes by provider — `provider == "local"` → `BRISTLENOSE_LOCAL_MODEL`, else `BRISTLENOSE_LLM_MODEL` (`BristlenoseShared.swift`). Pinned by `ServeManagerEnvTests/overlayPreferences_local_provider_routes_model_to_local_axis`. **When adding any provider whose Python execution reads a non-`llm_model` field, route its env injection to the matching axis — don't assume `BRISTLENOSE_LLM_MODEL` is universal.**
- **Bundled sidecar transcription SIGKILLs without JIT entitlements.** The run path transcribes via `mlx-whisper → numba → llvmlite`, which JIT-compiles word-timestamp kernels and `mprotect`s pages executable. Under Hardened Runtime that's killed with `EXC_BAD_ACCESS / SIGKILL (Code Signature Invalid)` / `CODESIGNING Invalid Page` — surfaces in the desktop as "Run failed (no terminus event) / unknown" with **no output dir created** (crash before any stage writes). Fix: `com.apple.security.cs.allow-jit` + `com.apple.security.cs.allow-unsigned-executable-memory` in `desktop/bristlenose-sidecar.entitlements` (re-sign after). Diagnose via `~/Library/Logs/DiagnosticReports/bristlenose-sidecar-*.ips`. **App-Store-review-sensitive** — route through app-store-police before submit. The serve-only entitlement comment ("JIT not needed") was scoped to serve; run needs it.
- **PyInstaller sidecar needs `multiprocessing.freeze_support()`.** A dep (mlx-whisper/tokenizers/onnxruntime) spawns mp children by re-executing the frozen binary with interpreter bootstrap args (`-B -S -c …`); without `freeze_support()` in `desktop/sidecar_entry.py:main()` those children fall through the argv rewrite, become `serve -B`, and Typer kills them ("No such option '-B'" / `resource_tracker: process died unexpectedly`). Main pipeline survives but child workers crash-loop. `freeze_support()` runs the worker and exits; no-op for a normal invocation. Must run before any argv manipulation.
- **The app keeps every CLI-readable key in TWO keychains — its own data-protection copy AND a login-keychain copy — because `security` cannot see the first.** Keys saved in the sandboxed app live in access group `app.bristlenose` on the data-protection keychain, invisible to `security find-generic-password` (measured 4 Sep 2026: an unentitled Security.framework caller gets `-25300` there, and the tool has no flag that could reach it). That was the split found in live provider testing — a key configured in the CLI invisible to the app and vice versa, two same-named items in Keychain Access. Since 4 Sep 2026 `KeychainHelper` mirrors the five `sharedWithCLI` keys into the login keychain at the service/account the CLI writes, and `SharedKeychainItem` reconciles on read: the copy that moved wins, a UserDefaults ledger says what moved, and the prompt budget is one macOS *"wants to use your confidential information"* dialog per foreign-created item, Always Allow once — **spent only by Settings ▸ LLM Provider.** Every other read is `quiet` (`KeychainInteraction`, the default): the login decrypt runs under `SecKeychainSetUserInteractionAllowed(false)`, a foreign item reads as `wouldPrompt`, and the app's own copy serves. That default exists because the first suite run without it hung the test host on the dialog at launch — see the gotcha below. **And the test host never reaches the real keychain at all:** `KeychainHelper.isUnderTestHost` (the XCTest harness env) resolves both raw keychains to `InMemoryRawKeychain` and the ledger to a throwaway suite, because `SettingsRefitTests` renders the real `LLMSettingsView` and its key field's focus handler wrote a developer's Gemini key back from inside the suite on 4 Sep 2026. Pinned by type in `KeychainHelperTests`; a test that wants a keychain still injects `InMemoryKeychain`. So `bristlenose configure` and the app see each other's keys, and for a CLI repro of a desktop run `security find-generic-password -s "Bristlenose OpenAI API Key" -w` now works (expect that dialog once); passing `BRISTLENOSE_<PROVIDER>_API_KEY` explicitly still does too. **Remove in Settings reaches the app's copies only:** a login item `bristlenose configure` created cannot be deleted by the app (`-25244`, no dialog), so `SharedKeychainItem.remove` leaves it for the CLI and keeps its stamp withheld in the ledger — until 21 Oct 2026 it wiped the ledger and the next read adopted the lone copy straight back (R37); `InMemoryRawKeychain.delete` now refuses foreign items too, so a test of `remove` can see the refusal. Design, the measured table and the on-device walk: `docs/design-keychain.md` § "One keyspace, two keychains". (Under the sandbox the Swift host still reads the key and injects it; Python never touches Keychain.)
- **Sidecar build provenance — the banner SHA carries `-dirty`/`@buildtime`.** `bristlenose/_build.py` resolves a build SHA: generated `_build_info.py` baked by `build-sidecar.sh` (bundle) → live `git rev-parse` (dev, with `-dirty`) → `"unknown"`. The banner (`_print_header`, also captured into `last-run-failure.log`) shows e.g. `e93e079 @06-08T02:46Z` or `e93e079-dirty`. Use it to confirm a rebuild actually took — a bare SHA with no `@time`/`-dirty` distinction was the flaw that made "did my rebuild land?" unanswerable.
- **A stale bundled sidecar silently no-ops any new *Python-emit* feature on desktop — QA of such features starts with a sidecar rebuild.** The bundled sidecar is built from a point-in-time `.venv-sidecar` and is NOT rebuilt by Xcode (see the build-sidecar note above). So a feature whose Python side emits new data — e.g. the Phase 0b `run_progress` events that feed the determinate ring *and* the sidebar progress text (`RunProgressSubtitle`) — looks completely dead on desktop (ring stuck as a spinner, subtitle stuck at "Analysing…") while the *same* `bristlenose run` from a current venv works. The events file is the tell: it carries only the older lifecycle events (`run_started` / `run_completed`) and **zero `run_progress`**. **Diagnose by comparing the run's `run_started.process.bristlenose_version` (in `<output>/.bristlenose/pipeline-events.jsonl`) against the tree `__version__`** — a mismatch means the bundled sidecar predates the emit code. Fix: `desktop/scripts/build-sidecar.sh` then `SIGN_IDENTITY=- desktop/scripts/sign-sidecar.sh`, then Cmd+R (Copy Sidecar Resources re-bundles it). The whole 0b ring shipped *latent* on desktop for ~1 day this way — the Swift rendered correctly but the bundled sidecar (v0.15.14) predated `RunProgressEvent`; nobody saw the ring or text until the 18 Jun 2026 rebuild. (Also under sandbox=on, projects.json + events live in `~/Library/Containers/app.bristlenose/Data/…`, not `~/Library/Application Support/` — look in the container when inspecting a sandboxed run's state.)
- **Resolution ledger for "why this provider/model?".** `load_settings` builds a step-by-step `llm_resolve` ledger (inputs → alias → pydantic-winner+source → orphan-guard → final), replayed from `LLMClient.__init__` and the early-logging hook in `run()` (config + preflight run *before* `pipeline._configure_logging`, so live emission is otherwise lost). `llm_preflight_validate` logs the exact wire pair where a mismatch 404 fires. Grep the run log (`<output>/.bristlenose/bristlenose.log`) for `llm_resolve` / `llm_preflight_validate` / `llm_client_target` / `llm_call_failed` before theorising about provider bugs.
- **A process reading our container on macOS 27: who it is doesn't decide it, who is *responsible* for it does. And a team-prefixed app group is the one public door.** Measured 29 Sep 2026 with the Agent Access proxy (`docs/design-mcp-native-proxy.md` §3 and §6). Another team's app data container or group container is denied by default on 27, and tccd judges by the **responsible** process: a Z56GZVA2QB-signed reader launched by Claude, ChatGPT or Terminal is denied as that host.
  - **Ways through:** (1) be your own responsible process — LaunchServices-launched `.app`s are; Claude Desktop starts every `type: binary` `.mcpb` server through its own `Helpers/disclaimer`; `responsibility_spawnattrs_setdisclaim` is private SPI, and App Review has rejected apps for it under §2.5.1. Or (2) be **sandboxed and carry a Team-ID-prefixed app group** (`Z56GZVA2QB.…`), which opens that group container whoever is responsible, with no tccd request. Unsandboxed + group, under a foreign host, was denied.
  - **A sandboxed bare Mach-O needs an embedded Info.plist** (`-Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker info.plist`). Without one it traps with **exit 133** ("Info.plist … has no value for kCFBundleIdentifierKey"). This is a different cause from the `inherit`-launched-standalone exit 133: read ReportCrash's line in `/usr/bin/log show` before assuming which one you hit.
  - **Two measurement traps.** sandboxd caches a denial per responsible *process*, so test the case you care about first, or in `open -n -a Terminal x.command`, which is a fresh instance. And a TCC result from a Cirrus tart `-base`/`-xcode` guest is void, because those images ship with SIP off: record `csrutil status` beside every result.

## Testing

### Conventions

- **If a SwiftUI view is making a decision, the decision belongs in a testable helper, not in the view.** Drop hit-testing, menu enable state, error categorisation, availability mapping — pull each into a plain `struct` or free function that takes inputs and returns an outcome (e.g. `DropDecision.evaluate(items:target:) -> DropOutcome`, `RevealAvailability.from(project:) -> Bool`, `LocateValidation.classify(folder:) -> LocateResult`, `ProjectSubtitle.resolve(...) -> SubtitleVariant` — the sidebar subtitle precedence chain, lifted out of `ProjectRow`'s body). The view becomes a thin caller; the helper gets a unit test in `BristlenoseTests/`. This is the minimum-step convention before reaching for an XCUITest target — covers the bulk of Swift-layer testability without new infrastructure. See `docs/design-test-philosophy.md` for the philosophy
- Test file naming: `{ClassName}Tests.swift` in `BristlenoseTests/`
- **To SEE a SwiftUI view from a test, host it in an `NSHostingView` inside a window, force an appearance, and give it a background, or the PNG is blank.** `host.bitmapImageRepForCachingDisplay(in:)` + `cacheDisplay`, then `Attachment.record(png, named:)` and `xcrun xcresulttool export attachments --path <xcresult> --output-path <dir>` (run with `-resultBundlePath`). Left alone, the test host draws in the developer's appearance onto a transparent bitmap: light text on a white PNG, so only filled shapes (an accent disc, a slider thumb) appear and it looks like the view is broken. Set `host.appearance`, `window.appearance`, `.environment(\.colorScheme, …)` and `.background(Color(nsColor: .windowBackgroundColor))`. Put the bridge in the live state first (`ready`, a `route-change` with the key **`url`**, not `path`, and keep a strong reference to the `WKWebView`, since `BridgeHandler.webView` is weak) or `commandTab` is nil and every row is dimmed. An off-screen `NSSwitch` never shows its knob on, and an inactive window shows the accent as grey: neither is a bug. Used for the Display popover, 3 Nov 2026.
- **A test that something did NOT happen must wait as long as the test that it did.** `ServeFleet.applyEnvChange` restarts through a `Task` (shutdown, then start), so asserting `state == .starting` straight after the call passes whether or not a restart was scheduled. A mutation that always restarted survived exactly that test (20 Oct 2026, R35); `aStartingServeAlreadyOnTheCurrentEnvIsLeftAlone` now runs the same `settle` the restart tests use before asserting the absence. Prove a negative test with the mutant that does the thing. **Two ways a test with a real child process passes without testing anything** (20 Oct 2026, `ServeManagerRestartTests`): a child given no time to install its `trap` is killed by the first SIGINT, because the restart's Task runs within milliseconds of `p.run()`, so the teardown window the test exists for never opens. And under the full suite the main actor is shared, so "after 300 ms" is not "after the Task ran". Give the child ~200 ms, then wait on *state* (`waitUntil { m.instance.process == nil }`) with a precondition `#expect` that the window is open. Both passed green with the fix reverted until the preconditions went in.
- **Suite-level `@MainActor` for tests that touch `@MainActor` types** — annotate the `@Suite struct`, not each `@Test func`. The per-method approach (`@MainActor @Test func ...`) is noisier and tends to miss tests that call static methods on actor-isolated types. Two existing files (`I18nTests`, `ProjectIndexTests`) had header comments saying *"X is @MainActor — all tests must be @MainActor too"* but were missing the suite-level annotation; adding it cleared all the actor-isolation errors at once. Swift Testing runs `@Test` on arbitrary executors by default
- KeychainHelper tests always use `InMemoryKeychain`, never real SecItem — avoids overwriting real API keys (SIGKILL bypasses teardown, so cleanup is not crash-safe)
- ProjectIndex tests always use `ProjectIndex(fileURL: tempURL)`, never the default Application Support path
- I18n tests use `configure(localesDirectory:)` with fixtures in `BristlenoseTests/Fixtures/`, never `findLocalesDirectory()` (which hardcodes dev paths)
- **A bare `I18n()` in a test returns the raw key, so any assertion on rendered text is silently an assertion about the key name.** `t()` falls back to returning the key on a miss, and an unconfigured instance misses everything. So `#expect(!label.lowercased().contains("failure"))` passes when `label` is `desktop.chrome.notAnalysedCount` — not because the copy is right, but because the *identifier* happens not to contain the word. Two tests passed this way on 20 Aug 2026 and a third failed, which is the only reason it was noticed. **Assert on the decision, not the translation:** extract the key choice into a pure function (`bucketCountKey`) and test that; leave whether the key resolves to good copy to `check-locales.py` and a native reviewer

### Running tests

```bash
desktop/scripts/test-swift.sh
```

Use this entry point for the full gate. It runs the general suite, then
`PoolStarvationTimeoutTests` in a separate process: those tests deliberately
block the shared executor, and `.serialized` does not isolate them from other
suites. Both invocations must pass and report tests before a green receipt is
written. Assertions, deadlines and the known saturation issue are unchanged.
Individual tests can still run in Xcode; a single-process Cmd+U full run can
reproduce the executor-contention false failure. See
`docs/design-study-recovery-guard.md` for the 29 October comparison receipts.

**A green `test-swift.sh` deletes its logs, so it cannot show you that a NEW test ran.** With `BN_LOG_DIR` unset it logs to a `mktemp -d` directory and `rm -rf`s it on success, leaving only the `N passed` total. Don't go looking for that directory afterwards: on 30 Sep 2026 the newest `$TMPDIR/tmp.*` holding a `test.log` belonged to *another session's* earlier run, without the tests in question, and read as "my suite never ran". To see your tests by name, pass `BN_LOG_DIR=<dir>` and grep `<dir>/test.log` for `Test case '<Suite>/<name>' passed`. Better still, run it once against a mutant that restores the old behaviour. Exactly your tests going red is proof that they ran *and* that they bite.

**`test-swift.sh`'s pass count can read one short on a green run.** It counts verdict lines, and xcodebuild sometimes writes its own `… Testing started completed.` line into the middle of the last verdict (`… passed on 'My Mac…` became `… pass2026-10-11 17:50:55…`), so that test is not counted. Measured 11 Oct 2026: the suite reported 1813 with 1814 tests run. The script's second check, xcodebuild's own exit status, still catches a real failure. **Tell:** a total that does not move when you add a test. Diff the per-test verdict lines of two runs (`grep -oE "Test case '[^']*' (passed|failed) on"`) before suspecting your test did not run.

**Concurrent `xcodebuild test` runs across worktrees hang in teardown — read the per-test "passed" lines, not the exit code.** When two worktrees run `xcodebuild test-without-building` for the same `Bristlenose` scheme at the same time (e.g. two Claude sessions, this branch + a sibling like `warm-sidecar-pool`), they contend on the shared macOS test host and **wedge in post-execution teardown** — the tests themselves run and pass, but `xcodebuild` never returns. A `timeout`-wrapped run then exits 124, and a manual `kill` of the wedged process shows up as exit 144 (128+SIGTERM) — **both look like test failures but aren't.** Diagnose by reading the log — but **not with the two greps this line used to recommend, because both lie in opposite directions** (18 Aug 2026). `grep -cE "✘|recorded an issue"` returned **0 on a genuinely red run**: with `xcodebuild`'s default reporter, a Swift Testing failure is written as `Test case 'Suite/name()' failed on 'My Mac …'` and carries no `✘` and no "recorded an issue" at all. The obvious repair, `grep -c "Test case.*failed"`, then fails the *other* way — it matches every test whose **name** contains the word (`failedDeclines()`, `failedRowsAreNotAnnounced()`, `failedWithDiagnosticMapsToHeaderCase()`), all of which go on to say `passed`, so a clean suite reports six failures. Both mistakes were made in one sitting, five minutes apart, and the first was reported to the user as green.

**Anchor on the verdict token, never on the line:**

```bash
grep -oE "' (passed|failed) on" run.log | grep -c failed   # 0 = green
```

Same family as the piped-`pytest`-exit-code gotcha in the root `CLAUDE.md`: the number that looks like a test result is produced by something that never examined a test. It clears on its own once the sibling run finishes (then a clean run returns exit 0). Hit 19 Jun 2026 on `project-status-line` while `warm-sidecar-pool` was testing concurrently.

**`build-for-testing` could sign the app BEFORE the test bundle inside it was signed — a scheduling race, deterministic only at release time.** Xcode derives a hosted macOS test target's `TARGET_BUILD_DIR` as the host's `Contents/PlugIns`, so `BristlenoseTests.xctest` was linked *into* `Bristlenose.app`, and the app's `CodeSign` task then had to seal it. Nothing orders the xctest's own `CodeSign` before the app's: the two are independent ready tasks, and the scheduler picks. Measured 22 Sep 2026 in three build logs of the same tree: two runs `Ld xctest → CodeSign app` (fails: `code object is not signed at all · In subcomponent: …/BristlenoseTests.xctest`, and the xctest's sign never runs), one run `Ld xctest → CodeSign xctest → CodeSign app` (passes). `parallelizeBuildables = NO` on the scheme changed nothing — measured, reverted. Ordinary work rarely hits it because the app's re-sign is usually up to date; a release dirties both targets in one build (the bump changes the app's Info.plist and the build-info phase rewrites a source for the new commit; the day's test edits relink the bundle), so it bit **0.30.0 and 0.31.0 in a row**, and 0.30.0's log recorded the symptom ("DerivedData held an unsigned xctest") and the workaround (`xcodebuild clean`) without the cause. **Fix: the test target sets `TARGET_BUILD_DIR = $(BUILT_PRODUCTS_DIR)`** (both configurations, `project.pbxproj`), so the bundle is built beside the app and the app's signature never covers it; `BUNDLE_LOADER`/`TEST_HOST` are unchanged and the xctestrun records the new location. `test-swift.sh` names the residue an older build may have left inside the app and the one `rm -rf` that clears it. **Tell:** a `BUILD FAILED` from the Swift gate with no `error:` line under it.

### Testability refactors

Four injection points exist for safe testing:

1. **`ProjectIndex(fileURL:)`** — pass a temp directory URL to avoid touching `~/Library/Application Support/Bristlenose/projects.json`
2. **`KeychainStore` protocol** — `KeychainHelper.liveStore` for production, `InMemoryKeychain()` for tests. The static `KeychainHelper.get/set/delete` methods remain unchanged for existing call sites
3. **`ServeManager(resolvedMode:)`** — any test that calls `start()` passes `.success(.external(port:))`. A bare `ServeManager()` resolves the sidecar from the **app bundle**, and the bundle has three shapes that give three different `start()`s: the main repo embeds the real sidecar (a unit test spawns a real process), CI's `mac-build.yml` stubs a **0-byte** executable (`proc.run()` throws, state becomes `.failed(launchFailed)`), and a fresh checkout has none (`start()` returns at its `mode` guard and changes nothing). `aFailedServeCanBeRestartedOnTheSameProject` asserted only "not the old failure", so it passed locally by spawning, passed on CI **because the launch failed**, and failed in a fresh checkout — which read as a guard bug for a day (29 Sep 2026, `55628d90`). External mode runs `start()` to completion with no process, so assert the state you expect (`.running(port:)`), never the absence of the old one
4. **`PipelineRunner(launcher:escalationSleep:signalTarget:…)`** — any test that calls `start()` passes a `launcher`, or it resolves the sidecar from the app bundle and runs a real `bristlenose run` (or fails on CI's 0-byte stub, or does nothing in a fresh checkout: the same three shapes as `ServeManager`). The launcher records the request and hands back a `LaunchedRun` whose exit the test fires by hand, so the queue, the slot, Stop's ladder and the exit path run for real with no process. `escalationSleep: { _ in }` collapses the ladder, and `signalTarget` lets a test see group signalling without a second process; every signal, probes (signal 0) included, goes through `sendSignal`, so a recorder sees them all and nothing reaches the test host. A test's `LaunchedRun` can carry an `output` stream, whose `finish()` is the pipe closing (a failed run's verdict waits for it, at most `outputDrainLimit`), and `sidecarLookup:` beside a launcher makes `spawn` look the sidecar up, so a failed lookup is reachable (R28); `foreignRunPollInterval:` and `foreignRunPatience:` pace the watch on a run another process owns (R22). Worked example: `PipelineRunnerQueueTests`. To land a start inside `handleTermination`'s end-state await, wait for the run's PID file to vanish (removed just before the await, and the test holds the main actor from there), and assert the file existed first.

