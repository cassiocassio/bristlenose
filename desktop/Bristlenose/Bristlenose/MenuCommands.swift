import AppKit
import SwiftUI

// MARK: - Menu bar

/// Native menu bar — every command reachable, keyboard shortcuts discoverable.
///
/// Uses the `View`-inside-`Commands` pattern: `@ObservedObject` is unreliable
/// directly in `Commands.body`, so each menu section is a small `View` struct
/// that owns `@ObservedObject var bridgeHandler`. Views inside `CommandMenu` /
/// `CommandGroup` follow normal SwiftUI view lifecycle and observe correctly.
///
/// All actions dispatch through `bridgeHandler.menuAction(_:payload:)` which
/// calls `callAsyncJavaScript` with structured arguments (security rule 3).
///
/// Menu order: Bristlenose · File · Edit · View · Project · Codes · Quotes · Video · Window · Help
///
/// Menu item labels are translated via `I18n` (reads from shared JSON locale files).
/// `CommandMenu` titles stay in English — SwiftUI resolves `LocalizedStringKey`
/// from `.lproj` bundles, not runtime JSON. Matches ATLAS.ti/MAXQDA precedent.
struct MenuCommands: Commands {
    @ObservedObject var serveManager: ServeManager
    @ObservedObject var projectIndex: ProjectIndex
    @ObservedObject var removalStore: UndoableRemovalStore
    @ObservedObject var i18n: I18n
    /// Used only by the Diagnostics menu's DEBUG harness section (Ollama
    /// setup-pill state forcing).
    @ObservedObject var ollamaDownload: OllamaDownloadModel
    /// Read by File ▸ Import so a running batch can dim the other
    /// platforms. One store globally (§9), so switching platform
    /// mid-transfer would otherwise abandon it — see
    /// `CloudImportCoordinator.openLive`.
    @ObservedObject var cloudImport: CloudImportCoordinator
    /// Gates the Diagnostics menu's presence. `@AppStorage` is a
    /// DynamicProperty, so flipping the toggle in Appearance settings should
    /// re-evaluate menu presence live; if a macOS release regresses that, the
    /// documented fallback is applies-on-next-launch (Safari-acceptable).
    @AppStorage(DiagnosticsPreference.key)
    private var showDiagnosticsMenu: Bool = DiagnosticsPreference.defaultValue

    /// The key window's bridge. Read once here and handed down as a plain
    /// `@ObservedObject` to each section, so the sections keep observing
    /// correctly (the `View`-inside-`Commands` pattern the doc comment above
    /// describes) while the *choice of object* follows the front window.
    @FocusedValue(\.bridge) private var focusedBridge

    /// The bridge the menus read. Falls back to the never-attached stand-in
    /// when no project window is frontmost — see `BridgeHandler.unattached`,
    /// whose default state dims exactly the items that need a window.
    private var bridgeHandler: BridgeHandler { focusedBridge ?? .unattached }

    var body: some Commands {
        CommandGroup(replacing: .appInfo) {
            AppMenuContent(serveManager: serveManager, i18n: i18n)
        }

        CommandGroup(replacing: .newItem) {
            FileMenuContent(bridgeHandler: bridgeHandler, projectIndex: projectIndex,
                            i18n: i18n, cloudImport: cloudImport, serveManager: serveManager)
        }

        CommandGroup(replacing: .undoRedo) {
            UndoRedoMenuContent(bridgeHandler: bridgeHandler, removalStore: removalStore, i18n: i18n)
        }

        CommandGroup(after: .textEditing) {
            FindMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }

        CommandGroup(replacing: .toolbar) {
            ViewMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }

        // CommandMenu titles stay in English (see doc comment above).
        // Grouped into a child Commands struct to stay under CommandsBuilder's
        // 10-element limit.
        CustomMenus(
            bridgeHandler: bridgeHandler,
            projectIndex: projectIndex,
            i18n: i18n
        )

        // (`Window ▸ Bristlenose` lived here until 16 Aug 2026. It is
        // `File ▸ New Window` now — see FileMenuContent for why the Window menu
        // was the wrong home.)

        CommandGroup(replacing: .help) {
            HelpMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }

        // Diagnostics menu — gated by the `showDiagnosticsMenu` preference
        // (Appearance settings; off by default, on in local DEBUG builds), so
        // a keen tester on ANY channel can opt into the poke-around tools.
        // Contents compound by build inside the one menu: Section 1 (user
        // diagnostics) ships everywhere; Section 2 (devtools — the SQLAdmin
        // browser) only where `exposesDebugTools` (local DEBUG + Developer-ID
        // .dmg beta, never App Store/TestFlight); Section 3 (fake-state
        // harness) is `#if DEBUG` only. See docs/design-diagnostics-menu.md.
        if showDiagnosticsMenu {
            CommandMenu("Diagnostics") {
                DiagnosticsMenuContent(
                    ollamaDownload: ollamaDownload,
                    serveManager: serveManager,
                    bridgeHandler: bridgeHandler
                )
            }
        }
    }
}

/// The single Diagnostics menu — three sections, gates compounding inside it
/// (the pref gates the menu; the channel + build-config gates pick sections).
/// Labels are commands only, no ellipsis on open-window items (HIG — opening a
/// window that IS the thing takes no further input). English-only for now,
/// matching the menu's tester-facing register.
private struct DiagnosticsMenuContent: View {
    @ObservedObject var ollamaDownload: OllamaDownloadModel
    @ObservedObject var serveManager: ServeManager
    /// Used by the DEBUG harness section's "Grid Specimen" (navigates the SPA).
    @ObservedObject var bridgeHandler: BridgeHandler
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        // Section 1 — user diagnostics, every channel. Reveal-existing-data
        // actions for the served project + the Shoal animation at defaults.
        // (Web Inspector is a side-effect of the preference toggle, not a menu
        // item — there's no public API to open a hosted WKWebView's inspector.)

        // Check Health — opens the native Health window (`DoctorReportView`),
        // which runs the doctor-style local system checks via `GET /api/doctor`
        // and renders them as a native list. No ellipsis: opening a window that
        // IS the thing takes no further input (HIG). Replaced the dead
        // `menuAction("checkSystemHealth")` bridge dispatch (28 Jul 2026).
        Button("Check Health") {
            openWindow(id: "health")
        }

        Divider()

        Button("Reveal .bristlenose/ in Finder") {
            DiagnosticsActions.revealInternalDir(serveManager: serveManager)
        }
        Button("Open Log in Console") {
            DiagnosticsActions.openLog(serveManager: serveManager)
        }
        Button("Copy Build Provenance") {
            DiagnosticsActions.copyBuildProvenance(serveManager: serveManager)
        }
        Button("Shoal Screensaver") { openWindow(id: "shoal-view") }

        if DistributionChannel.current.exposesDebugTools {
            Divider()
            // Section 2 — developer tools (.dmg beta + local DEBUG only).
            // No ellipsis — opens the panel directly in the browser.
            Button("Open Admin Panel") {
                AdminPanelAction.open(serveManager: serveManager)
            }
            .disabled(serveManager.runningPort == nil)

            // The cloud-import window, driven by fixtures instead of Google.
            //
            // This is not a convenience. Every failure state the design turns
            // on — a capped paginator, a declined scope, a personal account
            // with a full calendar and no recordings, a half-failed batch — is
            // unreachable from a healthy live account, and most are unreachable
            // without a paid Workspace tenant, a recorded meeting and a
            // verified OAuth client, none of which exist yet. Without this
            // menu the states could be written but never *seen*, which is how
            // an empty-state's copy stays wrong for two releases.
            Menu("Cloud Import") {
                ForEach(CloudPlatform.allCases) { platform in
                    Menu(platform.displayName) {
                        ForEach(CloudImportScenario.allCases) { scenario in
                            Button(scenario.menuTitle) {
                                NotificationCenter.default.post(
                                    name: .openCloudImportFixture,
                                    object: FixtureRequest(platform: platform,
                                                           scenario: scenario)
                                )
                            }
                        }
                    }
                }

                Divider()

                // A stored Zoom sign-in, without a Zoom account.
                //
                // The fixtures above drive the import *window*; they cannot
                // reach Settings ▸ Accounts or the restore path, because both
                // read the Keychain and a fixture session deliberately holds no
                // credentials. For Teams and Meet that gap is closed by having
                // a real tenant. Zoom has no account at all — so without this,
                // the row states, Disconnect, and "does a sign-in survive a
                // relaunch" are writable but never *seeable*, which is the
                // argument this whole menu already makes one level up.
                //
                // The token is deliberately junk: listing with it fails, which
                // is itself the refusal path worth watching. The address uses
                // `.invalid` (RFC 2606) so it can never collide with a real
                // account, and Forget is offered beside it so the item can
                // always be undone from here — including with
                // `BristlenoseCloudImportZoom` off, where Settings ▸ Accounts
                // shows no Zoom row and would otherwise leave this
                // unremovable.
                Button("Store a Test Zoom Sign-In") {
                    CloudGrantStore.saveZoom(
                        ZoomGrant(
                            tokens: ZoomTokens(accessToken: "fixture-access",
                                               refreshToken: "fixture-refresh",
                                               expiresAt: Date().addingTimeInterval(3600),
                                               scopes: ZoomScopes.requested),
                            identity: "zoom-test@example.invalid"),
                        previousKey: CloudAccountKey.unidentified)
                }
                Button("Forget the Test Zoom Sign-In") {
                    if let key = CloudGrantStore.firstAccountKey(for: .zoom) {
                        CloudGrantStore.disconnect(.zoom, accountKey: key)
                    }
                }
            }
        }

        #if DEBUG
        Divider()
        // Section 3 — full-fat harness, dev machines only.
        DebugMenuContent(
            ollamaDownload: ollamaDownload,
            serveManager: serveManager,
            bridgeHandler: bridgeHandler
        )
        #endif
    }
}

#if DEBUG
/// DEBUG-only menu driving the Ollama setup pill through every state for live
/// UX QA — no daemon or network needed. Forcing any scene also resurrects the
/// pill from idle (the `BRISTLENOSE_DEBUG_OLLAMA_PHASE` bootstrap only fires at
/// launch). View struct per the `@ObservedObject`-in-Commands pattern.
private struct DebugMenuContent: View {
    @ObservedObject var ollamaDownload: OllamaDownloadModel
    @ObservedObject var serveManager: ServeManager
    /// "Grid Specimen" navigates the report SPA (no native window scene).
    @ObservedObject var bridgeHandler: BridgeHandler
    @Environment(\.openWindow) private var openWindow
    @FocusedValue(\.windowCommands) private var windowCommands

    var body: some View {
        // Diagnostics windows take NO keyboard shortcut — except Run Inspector,
        // the one tool slated to ship to users (Tier U per design-diagnostics-menu.md),
        // which keeps ⌃⌘R. Rationale + canonical rule: docs/design-keyboard-shortcuts.md
        // § "Diagnostics windows".
        // No ellipsis: opening a window that IS the thing takes no further input
        // (HIG — ellipsis means "needs more input before it completes").
        Button("Type Parity Inspector") { openWindow(id: "type-parity") }

        Button("Run Inspector") { openWindow(id: "run-inspector") }
            .keyboardShortcut("r", modifiers: [.command, .control])

        // The tuning harness (sliders/presets/FPS probe) — distinct from the
        // Section-1 "Shoal Screensaver" (the animation at defaults).
        Button("Shoal Tuner") { openWindow(id: "shoal") }

        Button("Shimmer Tuner") { openWindow(id: "shimmer-tuner") }

        Button("Keycap Gallery") { openWindow(id: "keycap-gallery") }

        // Stress rig for content degradation in the fixed welcome geometry —
        // scale vs ellipsis vs clause-split vs authored ladder, over a corpus
        // of clause shapes, meaning traps and head-final scripts.
        Button("Degradation Lab") { openWindow(id: "degradation-lab") }

        // Where the AppKit sidebar meets the WKWebView. Cycles the candidate
        // background treatments against the real report and reports the live
        // seam geometry — Tahoe draws an inset plateau, macOS 27 reverts to
        // edge-anchored, so the numbers are measured rather than assumed.
        Button("Seam Lab") { openWindow(id: "seam-lab") }

        // Debug lens — test content on a visible grid, inside the report
        // webview itself (measures the production CSS in situ). Routes the
        // SPA to /report/specimen; needs a served project.
        Button("Grid Specimen") { bridgeHandler.menuAction("openSpecimen") }
            .disabled(serveManager.runningPort == nil)

        // (Reveal / Open Log / Copy Provenance moved to Section 1 — they ship
        // to every channel now. See DiagnosticsActions.)

        // Inject a synthesized diagnostic state into the SELECTED project's
        // sidebar row — flip popover/indicator scenes live, no relaunch. Posts
        // to ContentView, which owns the selection. (Previously env-var-only.)
        Menu("Diagnostic fixtures ▸ selected project") {
            ForEach(DiagnosticFixture.summaryScenarioNames, id: \.self) { name in
                Button(name) { postFixture(name) }
            }
            Divider()
            ForEach(DiagnosticFixture.simpleStateNames, id: \.self) { name in
                Button(name) { postFixture(name) }
            }
            Divider()
            Button(DiagnosticFixture.noSummaryScenarioName) {
                postFixture(DiagnosticFixture.noSummaryScenarioName)
            }
        }

        Divider()

        // Flyout submenu — the pill state harness is a deep but rarely-needed
        // list; keep the top-level Debug menu to the inspectors + a Cycle
        // shortcut, and tuck the per-scene buttons behind one hover.
        Button("Cycle Ollama pill ▸ next state") { ollamaDownload.debugCycleNext() }
            .keyboardShortcut("o", modifiers: [.command, .control])
        Menu("Ollama setup pill") {
            ForEach(OllamaDownloadModel.DebugScene.allCases, id: \.self) { scene in
                Button(scene.label) { ollamaDownload.debugApply(scene) }
            }
            Divider()
            Button("Hide pill (idle)") { ollamaDownload.cancel() }
        }
    }

    /// Ask the key window (which owns the sidebar selection) to inject `name`
    /// into its selected project.
    private func postFixture(_ name: String) {
        windowCommands?.perform(.applyDebugFixture(scenario: name))
    }
}
#endif

// MARK: - Custom CommandMenus grouped

private struct CustomMenus: Commands {
    let bridgeHandler: BridgeHandler
    let projectIndex: ProjectIndex
    let i18n: I18n

    var body: some Commands {
        CommandMenu("Project") {
            ProjectMenuContent(bridgeHandler: bridgeHandler, projectIndex: projectIndex, i18n: i18n)
        }
        CommandMenu("Codes") {
            CodesMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }
        CommandMenu("Quotes") {
            QuotesMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }
        CommandMenu("Video") {
            VideoMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }
    }
}

// MARK: - App menu (Bristlenose)

private struct AppMenuContent: View {
    @ObservedObject var serveManager: ServeManager
    @ObservedObject var i18n: I18n
    @FocusedValue(\.windowCommands) private var windowCommands

    var body: some View {
        Button(i18n.t("desktop.menu.app.about")) {
            let buildNumber = Bundle.main.infoDictionary?["CFBundleVersion"] as? String
            var options: [NSApplication.AboutPanelOptionKey: Any] = [:]

            if let version = serveManager.serverVersion {
                var versionString = version
                if let build = buildNumber {
                    versionString += " (\(build))"
                }
                options[.applicationVersion] = versionString
            }

            // Stash the BuildInfo block in the standard panel's Credits area
            // so users posting an "About" screenshot already include enough
            // provenance to disambiguate the build.
            let credits = BuildInfo.current.detailed(
                sidecar: serveManager.mode?.shortSummary ?? "?"
            )
            options[.credits] = NSAttributedString(
                string: credits,
                attributes: [
                    .font: NSFont.monospacedSystemFont(ofSize: 10, weight: .regular),
                    .foregroundColor: NSColor.secondaryLabelColor,
                ]
            )

            options[.version] = ""
            NSApp.orderFrontStandardAboutPanel(options: options)
        }

        Divider()

        Button(i18n.t("desktop.menu.app.aiPrivacy"), systemImage: "hand.raised") {
            windowCommands?.perform(.showAIConsent)
        }
        .disabled(!WindowCommand.showAIConsent.isEnabled(hasKeyWindow: windowCommands != nil))

        Divider()

        // Connect an Agent… — the plain word where discovery happens; the
        // pane it opens says MCP everywhere (the precise word where the
        // work happens). Honest that it only opens Settings — the same
        // shape as Mail's Add Account…, which also opens a pane. Setup is
        // a once-ever, app-level act, so it lives in the app menu, not the
        // project menu (that one gets the per-project verb swap).
        Button(i18n.t("desktop.menu.app.connectAgent"),
               systemImage: "antenna.radiowaves.left.and.right") {
            SettingsWindow.shared.show(pane: .mcpAgents)
        }
    }
}

// MARK: - File menu

private struct FileMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var projectIndex: ProjectIndex
    @ObservedObject var i18n: I18n
    @ObservedObject var cloudImport: CloudImportCoordinator
    /// Only for ⌥⌘N's gate — see the button. The File menu asks one question of
    /// it: is any study currently being served.
    @ObservedObject var serveManager: ServeManager
    @FocusedValue(\.windowCommands) private var windowCommands
    @Environment(\.openWindow) private var openWindow

    /// The study the front window is on, if any.
    ///
    /// Via the bridge's path rather than an id because that is what the front
    /// window publishes; `samePath` because bookmark healing can respell
    /// `Project.path` while the bridge holds the spelling it was given.
    private var frontProjectID: UUID? {
        guard !bridgeHandler.selectedProjectPath.isEmpty else { return nil }
        return projectIndex.projects.first {
            AgentActivity.samePath($0.path, bridgeHandler.selectedProjectPath)
        }?.id
    }

    var body: some View {
        Button(i18n.t("desktop.menu.file.newProject"), systemImage: "plus") {
            newItem(.newProject) {
                NewItemFallback.createProject(
                    in: projectIndex, named: i18n.t("desktop.chrome.newProject"))
            }
        }
        .keyboardShortcut("n", modifiers: .command)

        Button(i18n.t("desktop.menu.file.newFolder"), systemImage: "folder.badge.plus") {
            newItem(.newFolder) {
                NewItemFallback.createFolder(
                    in: projectIndex, named: i18n.t("desktop.chrome.newFolder"))
            }
        }
        .keyboardShortcut("n", modifiers: [.command, .shift])

        // File ▸ New Window (⌥⌘N) — was `Window ▸ Bristlenose`, which was wrong
        // twice over. Wrong menu: Apple's standard Window-menu command list
        // contains no new-window command at all, while `File ▸ New <Item>` is
        // defined as "Creates a new document, file, or window." And wrong
        // label: it called `openWindow(id:)` against a `WindowGroup`, which
        // *spawns* a window rather than reopening one — a New Window command
        // wearing a reopen label, and the way a second window got opened by
        // accident. Sits with New Project / New Folder because it is the third
        // New item, and ⌥⌘N keeps that family's shape.
        //
        // **Passes no value, deliberately — measured 20 Aug 2026.** SwiftUI keeps
        // at most one window per unique scene value, so `openWindow(id:value:)`
        // for a study that already has a window *brings that window forward*
        // instead of opening another. Observed on screen: ⌥⌘N with two windows
        // open re-activated one of them rather than making a third.
        //
        // That is fatal for this command specifically. New Window's whole job is
        // "another view of what I'm looking at" — the case that wants two windows
        // on one study — and it is what the `WindowRoster` ordinals exist to
        // number. Deduping makes both unreachable.
        //
        // Passing NO value was the first repair and it did not work either:
        // `nil` is itself a unique value, so exactly one no-value window can
        // exist. With nil plus one project that is a hard ceiling of two, and
        // which two depends on the order you opened them in. Both observed.
        //
        // `WindowSeed.fresh` mints a token nobody else holds, so this always
        // opens — and it can now carry the front window's study AND lens, which
        // is what the command always meant and what dedup made impossible.
        Button(i18n.t("desktop.menu.file.newWindow"), systemImage: "macwindow") {
            openWindow(id: "main", value: WindowSeed.fresh(
                project: frontProjectID,
                lens: LensMemory.remember(bridgeHandler.activeTab)))
        }
        .keyboardShortcut("n", modifiers: [.command, .option])

        // Add Files… — the menu twin of drag-drop. ⇧⌘A mirrors Apple Mail's
        // File ▸ Attach Files. Fires unconditionally (like New Project/Folder);
        // the window resolves its own selection and toasts if none.
        Button(i18n.t("desktop.menu.file.addFiles"), systemImage: "plus.rectangle.on.folder") {
            windowCommands?.perform(.addFiles)
        }
        .keyboardShortcut("a", modifiers: [.command, .shift])
        // Selection-targeted (group 3), so it needs a selected project as well
        // as a window — it was gated on the window alone, which let a
        // researcher pick files with nothing selected and then be told off.
        .disabled(!bridgeHandler.hasSelectedProject
                  || !WindowCommand.addFiles.isEnabled(hasKeyWindow: windowCommands != nil))

        // Import ▸ — cloud sources, beside Add Files… because that is the same
        // act from a different place (`docs/design-cloud-import.md` §9).
        //
        // A submenu holding one item is normally a Mac smell, and the design
        // doc says to stay flat until the second platform lands. It is a
        // submenu here because Teams and Zoom are both designed and queued
        // behind this, and the alternative — ship `Import from Google Meet…`
        // flat, then move it into a submenu two releases later — relocates a
        // menu item users have already learned. Cheaper to be one item wide
        // for a while than to move it afterwards.
        Menu {
            // Only platforms with a live adapter appear. An item that opens a
            // window which then says "not built yet" is worse than no item —
            // menus are a promise about what the app can do.
            // **While a batch is transferring, only the platform running it is
            // reachable, and its verb changes.** There is one import window
            // globally (§9), so picking another platform mid-transfer would
            // abandon the running batch — files still arriving, nothing left
            // that could show or stop them. Dimming is the HIG answer (menus
            // dim, never hide) and it prevents the request rather than refusing
            // it; `CloudImportCoordinator.openLive` keeps a guard behind this
            // because a menu can be raced and the notification has other
            // senders.
            //
            // The ellipsis goes with it. "Google Meet…" promises a window that
            // asks something; while a batch runs the window only *shows* what
            // is already happening, and HIG reserves the ellipsis for the
            // former.
            ForEach(CloudPlatform.shipping) { platform in
                let busyElsewhere = cloudImport.isFetching && cloudImport.platform != platform
                let showing = cloudImport.isFetching && cloudImport.platform == platform
                // No glyph. It was a stand-in — a person for Teams, a camera
                // for Meet — carried because a generic SF Symbol is *lawful*
                // where the vendor's real mark is not. Lawful was never the
                // argument for having one: it is there because we can, not
                // because it helps, and every other item in this menu bar is a
                // plain title. See `AccountService` for the same removal in
                // Settings ▸ Accounts, and why the real marks are not coming.
                Button(platform.displayName + (showing ? "" : "…")) {
                    NotificationCenter.default.post(name: .openCloudImport, object: platform)
                }
                .disabled(busyElsewhere)
            }
        } label: {
            Label("Import", systemImage: "square.and.arrow.down")
        }

        // **`File ▸ Open in New Window` (⇧⌘O) was retired here on 20 Aug 2026,
        // and the reason is structural rather than a matter of user
        // sophistication.**
        //
        // Its distinction from New Window was "opens the SELECTED project"
        // versus "another view of the one showing". That works in Finder, where
        // selection and current-folder are genuinely independent — you view A,
        // select B, and B is selected-but-not-shown. **Bristlenose has no such
        // state:** selecting a study in the sidebar IS how a window comes to
        // show it, so the two inputs are one input. The code said so too — both
        // items read `frontProjectID`; there was never a selection input here.
        //
        // Worse than no difference: ⌥⌘N always spawned, ⇧⌘O sometimes revealed,
        // and only when its target window had itself arrived by a reveal and
        // never switched study. `design-workspace.md` rules that shape out —
        // "an invisible clock deciding where you land is an unlearnable rule…
        // either always or never".
        //
        // **The three sidebar context-menu items stay**, because a clicked row
        // genuinely can be a study the window is not showing — an arbitrary
        // target, which the menu bar does not have. That is the real split:
        // arbitrary-target versus current-target, not two spellings of one.
        //
        // Cost, stated: those items now have no menu-bar twin, and the lens one
        // is pointer-only (there is no default system key for a context menu).
        // The capability is still reachable — select a study, ⌥⌘N — but the lens
        // accelerator is not, and the honest fix is a *named* menu item
        // ("Open Codebooks in New Window") rather than restoring this one.
        // ⇧⌘O is free.

        Divider()

        Button(i18n.t("desktop.menu.file.exportReport"), systemImage: "square.and.arrow.up") {
            bridgeHandler.menuAction("exportReport")
        }
        .keyboardShortcut("e", modifiers: [.command, .shift])

        // "Export Anonymised…" was removed here on 28 Jul 2026: anonymise is a
        // checkbox on the export save panel itself (`ExportAccessoryView`, attached
        // as the NSSavePanel accessoryView in `WebView.swift`), so a second menu
        // item offering the same choice was redundant — one command, one dialog,
        // the option lives in the dialog. Export Report… now stands alone here:
        // the File menu carries the whole-report export; per-quote destinations
        // (Miro, clips, spreadsheets) live in the Quotes menu.

        Divider()

        // Page Setup / Print are NATIVE (`NSPrintOperation`), not bridge calls.
        // They used to dispatch `menuAction("pageSetup"/"print")`, which no SPA
        // handler consumed — silent no-ops. `window.print()` inside a WKWebView
        // can't raise the macOS print panel, so the bridge was never the right
        // target. Prints whatever lens is on screen; see `PrintActions`.
        Button(i18n.t("desktop.menu.file.pageSetup")) {
            PrintActions.pageSetup()
        }

        Button(i18n.t("desktop.menu.file.print"), systemImage: "printer") {
            PrintActions.print(webView: bridgeHandler.webView, window: PanelHost.window)
        }
        .keyboardShortcut("p", modifiers: .command)
        // `isReady` is the only published signal that a web view has loaded
        // (`webView` itself is a plain weak var, so it can't drive SwiftUI).
        // It's an imperfect proxy — see the "isReady is NOT 'the report is
        // showing'" gotcha in desktop/CLAUDE.md — but it correctly separates
        // "nothing to print yet" from "something is on screen".
        .disabled(!bridgeHandler.isReady)
    }

    /// Group 1 — the two commands that must work with **no project window
    /// frontmost**, so neither is ever dimmed.
    ///
    /// With a key window it creates, selects and begins inline rename there, as
    /// before. Without one, `fallback` does the app-global half (the model
    /// mutation) and stages the rest on `ProjectIndex`'s one-shot batons; the
    /// window opened here drains them on appear. See `NewItemFallback`, which
    /// documents the one case this gets wrong.
    private func newItem(_ command: WindowCommand, fallback: () -> Void) {
        if let windowCommands {
            windowCommands.perform(command)
        } else {
            fallback()
            openWindow(id: "main")
        }
    }
}

// MARK: - Edit > Undo/Redo

private struct UndoRedoMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var removalStore: UndoableRemovalStore
    @ObservedObject var i18n: I18n

    /// Removal-undo takes priority over web-side undo when pending: it's the
    /// most recent action and has a strict 8s window. After commit it falls
    /// back to the previous (web) behaviour.
    private var undoLabel: String {
        if let name = removalStore.pendingName {
            return String(format: i18n.t("desktop.menu.edit.undoRemove"), name)
        }
        return bridgeHandler.undoLabel ?? i18n.t("desktop.menu.edit.undo")
    }

    private var canUndo: Bool {
        removalStore.hasPending || bridgeHandler.canUndo
    }

    var body: some View {
        if !bridgeHandler.isEditing {
            Button(undoLabel, systemImage: "arrow.uturn.backward") {
                if removalStore.hasPending {
                    removalStore.undoLastRemoval()
                } else {
                    bridgeHandler.menuAction("undo")
                }
            }
            .keyboardShortcut("z", modifiers: .command)
            .disabled(!canUndo)

            Button(i18n.t("desktop.menu.edit.redo"), systemImage: "arrow.uturn.forward") {
                bridgeHandler.menuAction("redo")
            }
            .keyboardShortcut("z", modifiers: [.command, .shift])
            .disabled(!bridgeHandler.canRedo)
        }
    }
}

// MARK: - Edit > Find

private struct FindMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    var body: some View {
        Divider()

        Button(i18n.t("desktop.menu.edit.find"), systemImage: "magnifyingglass") {
            bridgeHandler.menuAction("find")
        }
        .keyboardShortcut("f", modifiers: .command)

        Button(i18n.t("desktop.menu.edit.findNext")) {
            let text = NSPasteboard(name: .find).string(forType: .string) ?? ""
            bridgeHandler.menuAction("findNext", payload: ["text": text])
        }
        .keyboardShortcut("g", modifiers: .command)

        Button(i18n.t("desktop.menu.edit.findPrevious")) {
            let text = NSPasteboard(name: .find).string(forType: .string) ?? ""
            bridgeHandler.menuAction("findPrevious", payload: ["text": text])
        }
        .keyboardShortcut("g", modifiers: [.command, .shift])

        Button(i18n.t("desktop.menu.edit.useSelectionForFind")) {
            bridgeHandler.menuAction("useSelectionForFind")
        }
        .keyboardShortcut("e", modifiers: .command)

        Button(i18n.t("desktop.menu.edit.jumpToSelection")) {
            bridgeHandler.menuAction("jumpToSelection")
        }
        .keyboardShortcut("j", modifiers: .command)
    }
}

// MARK: - View menu

private struct ViewMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n
    @FocusedValue(\.windowCommands) private var windowCommands

    /// The FRONT window's projects-sidebar binding, published by its
    /// `ContentView` via `focusedSceneValue`. Window-scoped on purpose: Hide/Show
    /// Projects must move one window, not all of them. `nil` when no project
    /// window is key, which dims the item.
    @FocusedValue(\.sidebarVisibility) private var sidebarVisibility

    /// Locale key suffix for the left-panel label, per tab.
    ///
    /// `.sessions` deliberately absent since the popover switcher replaced that
    /// lens's left panel — its ⌘⌥L row is the dedicated switcher branch below,
    /// so this key never labels a toggle for a panel that no longer exists.
    private var leftPanelKey: String? {
        switch bridgeHandler.activeTab {
        case .quotes:   return "Contents"
        case .codebook: return "Codes"
        case .analysis: return "Signals"
        default:        return nil
        }
    }

    private var hasLeftPanel: Bool {
        // `Tab.hasLeftPanel` is the one list; `leftPanelKey` only names the
        // panel. Deriving membership from a label's nil-ness meant a new lens
        // needed both edited, and the toolbar's own gate was a third copy.
        // `activeTab` is optional here (it is not in ContentView): no tab yet
        // means no lens, which means no panel.
        bridgeHandler.activeTab?.hasLeftPanel ?? false
    }

    /// Whether Hide/Show All Sidebars should read "Hide". The projects column is
    /// read straight off the focused binding; the two web panels arrive over the
    /// `panel-state` mirror, because native can't see inside the WKWebView.
    ///
    /// Deliberately excludes `inspectorOpen`: the heatmap inspector is a bottom
    /// panel on the data, not navigation chrome, so counting it would let the
    /// row say "Hide All Sidebars" about something that isn't one.
    private var allSidebarsShowing: Bool {
        AllSidebars.anyShowing(
            projects: SidebarToggle.isVisible(sidebarVisibility?.wrappedValue ?? .all),
            leftPanel: bridgeHandler.leftPanelOpen,
            rightPanel: bridgeHandler.rightPanelOpen
        )
    }

    /// The tag sidebar and the heatmap inspector each exist on one lens only.
    /// Read once for both the row's label verb and its `.disabled`, so an
    /// unavailable row can't dim and still say "Hide".
    private var hasTagPanel: Bool {
        bridgeHandler.activeTab == .quotes
    }

    private var hasHeatmapPanel: Bool {
        bridgeHandler.activeTab == .analysis
    }

    var body: some View {
        // Tab shortcuts Cmd+1 through Cmd+5. `activateLens`, not `switchToTab`:
        // the Sessions lens restores the view the user left (route memory).
        // Iterates the RAIL, not Tab.allCases. The comment above LensItem.all
        // says the rail and these shortcuts "can't drift apart"; reading the
        // same array is what makes that structural rather than a promise. It
        // also means the DEBUG-only v2 lens gets its number automatically and
        // Release keeps five.
        ForEach(Array(LensItem.all.enumerated()), id: \.element.id) { index, lens in
            let tab = lens.tab
            Button(tab.localizedLabel(i18n), systemImage: lens.systemImage) {
                bridgeHandler.activateLens(tab)
            }
            // Menus dim (HIG): these rows follow the same availability truth
            // as the sidebar lens rows — mirrored onto the bridge by
            // ContentView, since the derivation reads objects the menu bar
            // can't see. Before this, ⌘1–⌘5 fired unconditionally and the
            // activation died silently wherever the sidebar was dimmed.
            .disabled(!bridgeHandler.lensesAvailable)
            .keyboardShortcut(
                KeyEquivalent(Character("\(index + 1)")),
                modifiers: .command
            )
        }

        // View ▸ Move Focus to Projects was REMOVED 28 Jul 2026 — deliberately
        // not replaced. It existed as a "§10.1 keyboard no-trap" escape, but a
        // menu item is not an accessibility affordance: a keyboard user stuck in
        // the web view will not discover the fourth row of the View menu. macOS
        // already provides the real escapes — ⌃F6 / ⇧⌃F6 cycle split-view panes,
        // ⌃F2 focuses the menu bar, and Tab should exit the WKWebView at document
        // end. WCAG 2.1.2 asks for "unmodified arrow or tab keys, or other
        // standard exit methods"; ⌃F6 is one, a bespoke menu item is not.
        // If a trap is ever demonstrated, the fix is the window's key-view loop,
        // not another unread menu row. Verification task filed in TODO.md.

        Divider()

        // All four rows are toggles, so all four swap Hide↔Show off the panel's
        // real state (Finder convention) — see `PanelToggle`. Projects reads its
        // own window's split-view visibility; the three web panels read the
        // SPA's `panel-state` mirror, which is the only way native can know.
        // Content-named "Projects" to match the reveal-family (Contents /
        // Sessions / Codes / Signals / Tags) and disambiguate from the web left
        // panel. Toggles through the `columnVisibility` binding via ContentView,
        // not the AppKit selector, so the auto toolbar button and this item
        // share one source of truth.
        Button(i18n.t(PanelToggle.labelKey(
            panel: "Projects",
            isOpen: SidebarToggle.isVisible(sidebarVisibility?.wrappedValue ?? .all),
            isAvailable: sidebarVisibility != nil
        )), systemImage: "sidebar.left") {
            guard let sidebarVisibility else { return }
            withAnimation {
                sidebarVisibility.wrappedValue = SidebarToggle.next(sidebarVisibility.wrappedValue)
            }
        }
        .keyboardShortcut("s", modifiers: [.command, .option])
        .disabled(sidebarVisibility == nil)

        // ⌘⌥L is lens-appropriate: a panel TOGGLE on Quotes/Codebook/Analysis,
        // the session SWITCHER on Sessions — where the left panel is gone and a
        // toggle row would confidently offer "Hide Sessions" for a panel not on
        // screen. Replaced, not hidden: the row stays real on every lens.
        if bridgeHandler.activeTab == .sessions {
            Button(i18n.t("desktop.toolbar.switchSession"), systemImage: "list.bullet") {
                windowCommands?.perform(.showSessionsSwitcher)
            }
            .keyboardShortcut("l", modifiers: [.command, .option])
            .disabled(!WindowCommand.showSessionsSwitcher
                .isEnabled(hasKeyWindow: windowCommands != nil))
        } else {
            Button(i18n.t(PanelToggle.labelKey(
                panel: leftPanelKey ?? "Contents",
                isOpen: bridgeHandler.leftPanelOpen,
                isAvailable: hasLeftPanel
            )), systemImage: "list.bullet") {
                bridgeHandler.menuAction("toggleLeftPanel")
            }
            .keyboardShortcut("l", modifiers: [.command, .option])
            .disabled(!hasLeftPanel)
        }

        Button(i18n.t(PanelToggle.labelKey(
            panel: "Tags",
            isOpen: bridgeHandler.rightPanelOpen,
            isAvailable: hasTagPanel
        )), systemImage: "sidebar.right") {
            bridgeHandler.menuAction("toggleRightPanel")
        }
        .keyboardShortcut("t", modifiers: [.command, .option])
        .disabled(!hasTagPanel)

        Button(i18n.t(PanelToggle.labelKey(
            panel: "Heatmap",
            isOpen: bridgeHandler.inspectorOpen,
            isAvailable: hasHeatmapPanel
        )), systemImage: "square.grid.2x2") {
            bridgeHandler.menuAction("toggleInspectorPanel")
        }
        .disabled(!hasHeatmapPanel)

        // Last in the panel group, reading specific → general: the umbrella over
        // the three items above it. ⌘⌥\ keeps the family shape of its siblings
        // (⌘⌥S/L/T) and reuses the key that already means "both sidebars" in the
        // web layer, where bare `\` does the same for the two content panels.
        // A *modified* equivalent is load-bearing, not taste — a bare menu key
        // equivalent fires before the responder chain and would eat the
        // character in every rename field and inline editor (desktop/CLAUDE.md,
        // "No bare-key menu shortcuts"). That is also why the ISO-only `§` is a
        // web-layer alias rather than what this row advertises.
        Button(i18n.t(allSidebarsShowing
                      ? "desktop.menu.view.hideAllSidebars"
                      : "desktop.menu.view.showAllSidebars"),
               systemImage: "rectangle.split.3x1") {
            guard let sidebarVisibility else { return }
            let hiding = allSidebarsShowing
            withAnimation {
                sidebarVisibility.wrappedValue = AllSidebars.nextVisibility(
                    sidebarVisibility.wrappedValue, hiding: hiding
                )
            }
            bridgeHandler.menuAction(AllSidebars.webAction(hiding: hiding))
        }
        .keyboardShortcut("\\", modifiers: [.command, .option])
        .disabled(sidebarVisibility == nil)

        Divider()

        // Radio-style pair: the active view mode carries a checkmark. A Toggle
        // inside a menu is the native idiom for "this option is on"; the set
        // closure ignores the new value and dispatches the action (the SPA owns
        // the state, mirrored back via `quotes-filter`). Tag filtering moved to
        // the tag sidebar (View ▸ Show Tags) — the old Filter by Tag item is gone.
        Toggle(i18n.t("desktop.menu.view.allQuotes"), isOn: Binding(
            get: { bridgeHandler.quotesViewMode == "all" },
            set: { _ in bridgeHandler.menuAction("allQuotes") }
        ))
        .disabled(bridgeHandler.activeTab != .quotes)

        Toggle(isOn: Binding(
            get: { bridgeHandler.quotesViewMode == "starred" },
            set: { _ in bridgeHandler.menuAction("starredQuotesOnly") }
        )) {
            Label(i18n.t("desktop.menu.view.starredQuotesOnly"), systemImage: "star")
        }
        .disabled(bridgeHandler.activeTab != .quotes)

        Divider()

        // Section of one. Bare title + checkmark, not a Turn On/Off verb swap:
        // the checkmark carries the state, so the label is the thing rather than
        // the act — matching the two items above, which is the register this menu
        // already has. `Turn On/Off` stays reserved for permissions that keep
        // working while you're not looking (Agent Access). No systemImage: the
        // radio pair above is the only item here carrying one. See
        // docs/design-focus-mode.md § Label and shortcut.
        //
        // Quotes-scoped like the pair above: the recede transform is defined for
        // quote cards only, and a live-but-inert menu item is worse than a dimmed
        // one. Un-dimming later, once the other lenses have a defined transform,
        // is a free upgrade.
        Toggle(i18n.t("desktop.menu.view.focusMode"), isOn: Binding(
            get: { bridgeHandler.focusModeActive },
            set: { _ in bridgeHandler.menuAction("focusMode") }
        ))
        .keyboardShortcut("f", modifiers: [.command, .option])
        .disabled(bridgeHandler.activeTab != .quotes)

        Divider()

        Button(i18n.t("desktop.menu.view.zoomIn"), systemImage: "plus.magnifyingglass") {
            bridgeHandler.menuAction("zoomIn")
        }
        .keyboardShortcut("=", modifiers: .command)

        Button(i18n.t("desktop.menu.view.zoomOut"), systemImage: "minus.magnifyingglass") {
            bridgeHandler.menuAction("zoomOut")
        }
        .keyboardShortcut("-", modifiers: .command)

        // ⌘0 — the platform's reset-zoom binding, and semantically identical to
        // WKWebView's own. Taking it here resolves the collision this file
        // previously worked around rather than creating one.
        Button(i18n.t("desktop.menu.view.actualSize")) {
            bridgeHandler.menuAction("actualSize")
        }
        .keyboardShortcut("0", modifiers: .command)
    }
}

// MARK: - Project menu

private struct ProjectMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var projectIndex: ProjectIndex
    @ObservedObject var i18n: I18n
    @FocusedValue(\.windowCommands) private var windowCommands

    /// Whether a folder is selected.
    private var hasFolder: Bool {
        !bridgeHandler.selectedFolderName.isEmpty
    }

    /// The single selected project, resolved by path — empty
    /// `selectedProjectPath` covers both no-selection and multi-selection
    /// (Rename's guard). Same path standardisation the badge identity uses.
    private var selectedProject: Project? {
        let path = bridgeHandler.selectedProjectPath
        guard !path.isEmpty else { return nil }
        return projectIndex.projects.first { AgentActivity.samePath($0.path, path) }
    }

    private var selectedProjectAccessOn: Bool { selectedProject?.agentAccess ?? false }

    private var selectedProjectCanShare: Bool {
        selectedProject.map {
            AgentAccessPolicy.canShare(
                $0, sessionCount: projectIndex.unanalysed[$0.id]?.sessionCount)
        } ?? false
    }

    /// Is there a window for this command to act in? Every item in this menu
    /// acts on the front window's sidebar selection, so all of them dim when no
    /// project window is frontmost — the same rule the View menu's Hide/Show
    /// Projects has followed since Stage 1. Composed with each item's own
    /// selection guard, which still reads app-global `BridgeHandler` state
    /// until Stage 3a makes it per-window.
    private func enabled(_ command: WindowCommand) -> Bool {
        command.isEnabled(hasKeyWindow: windowCommands != nil)
    }

    var body: some View {
        if hasFolder {
            // Folder-specific items
            Button(i18n.t("desktop.menu.folder.rename"), systemImage: "pencil") {
                windowCommands?.perform(.renameFolder)
            }
            .disabled(!enabled(.renameFolder))

            Button(i18n.t("desktop.menu.folder.archive"), systemImage: "archivebox") {
                // Phase 5
            }
            .disabled(true)

            Divider()

            Button(i18n.t("desktop.menu.folder.delete"), systemImage: "trash", role: .destructive) {
                windowCommands?.perform(.deleteFolder)
            }
            .keyboardShortcut(.delete, modifiers: .command)
            .disabled(!enabled(.deleteFolder))
        } else {
            // Project-specific items (or nothing selected)
            Button(i18n.t("desktop.menu.project.showInFinder"), systemImage: "folder") {
                let path = bridgeHandler.selectedProjectRevealablePath
                if !path.isEmpty {
                    NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath: path)
                }
            }
            .keyboardShortcut("r", modifiers: [.command, .shift])
            .disabled(bridgeHandler.selectedProjectRevealablePath.isEmpty)

            // Show Transcripts in Finder — the menu twin of the export popover's
            // row, which was the only surface carrying it (the menu bar is the
            // canonical accessible one). Sits with Show in Finder because the
            // object is the same — the selected project's files, one level down.
            // `doc.text`, not a second `folder`, so two adjacent reveals don't
            // share a glyph.
            Button(i18n.t("desktop.menu.quotes.revealTranscripts"), systemImage: "doc.text") {
                windowCommands?.perform(.revealTranscripts)
            }
            .disabled(bridgeHandler.selectedProjectPath.isEmpty || !enabled(.revealTranscripts))

            Button(i18n.t("desktop.chrome.locate"), systemImage: "location.magnifyingglass") {
                windowCommands?.perform(.locateProject)
            }
            .disabled(bridgeHandler.selectedProjectAvailable || !enabled(.locateProject))

            // HIG: every context-menu item is also reachable from the menu
            // bar. Turn On/Off Agent Access — the context menu's verb swap
            // (§3.6a). Opposite visibility rule to the context menu: menus
            // dim, context menus hide. Rename's single-selection guard, the
            // antenna on both label states, and deliberately NO keyboard
            // shortcut — exposure is a deliberate act, and accelerators are
            // for things fired without looking.
            Button(selectedProjectAccessOn
                       ? i18n.t("desktop.menu.project.turnOffAgentAccess")
                       : i18n.t("desktop.menu.project.turnOnAgentAccess"),
                   systemImage: "antenna.radiowaves.left.and.right") {
                if let project = selectedProject {
                    projectIndex.setAgentAccess(id: project.id, enabled: !project.agentAccess)
                }
            }
            .disabled(!selectedProjectCanShare)

            Button(i18n.t("desktop.menu.project.rename"), systemImage: "pencil") {
                windowCommands?.perform(.renameProject)
            }
            // Single-selection-only operation; receiver guards on `sole`.
            // `selectedProjectPath.isEmpty` covers both no-selection AND
            // multi-selection (cleared by applySelectionChange's default
            // branch). Indie-consensus: Finder/Notes/Mail/Things disable
            // Rename on multi-select rather than silently no-op.
            .disabled(bridgeHandler.selectedProjectPath.isEmpty || !enabled(.renameProject))

            // "Move to" submenu — lists all folders + "No Folder" for root.
            // Disabled on no-selection AND multi-selection for the same
            // reason as Rename — receiver guards on `sole`, so submenu
            // children would silently no-op (and that's especially bad in
            // a submenu, where the user has invested two clicks before
            // discovering the dead end).
            if !projectIndex.folders.isEmpty {
                Menu(i18n.t("desktop.menu.project.moveTo"), systemImage: "folder") {
                    Button(i18n.t("desktop.menu.project.noFolder")) {
                        windowCommands?.perform(.moveProject(toFolder: nil))
                    }

                    Divider()

                    ForEach(projectIndex.folders) { folder in
                        Button(folder.name) {
                            windowCommands?.perform(.moveProject(toFolder: folder.id))
                        }
                    }
                }
                .disabled(bridgeHandler.selectedProjectPath.isEmpty
                          || !enabled(.moveProject(toFolder: nil)))
            }

            // ⌘. is the canonical macOS Stop/Cancel; here it's the keyboard
            // accelerator for the row's hover-× and context-menu Stop. Acts on
            // the sole-selected project; dimmed (not hidden) when it isn't
            // running, per menu-bar HIG (context menus hide instead).
            Button(i18n.t("desktop.menu.project.stopAnalysis"), systemImage: "stop.circle") {
                windowCommands?.perform(.stopProject)
            }
            .keyboardShortcut(".", modifiers: .command)
            .disabled(!bridgeHandler.selectedProjectIsRunning || !enabled(.stopProject))

            // Routed natively (`windowCommands`), not through the web bridge —
            // it deletes a directory and spawns a subprocess, and the bridge
            // event it used to send had no listener anywhere in `frontend/src`.
            // Dims rather than hides, per menu-bar HIG; the context-menu twin
            // in `ProjectSidebarOutline.buildProjectMenu` hides instead.
            Button(i18n.t("desktop.menu.project.reAnalyse"), systemImage: "arrow.clockwise") {
                windowCommands?.perform(.reAnalyseProject)
            }
            .disabled(!bridgeHandler.selectedProjectIsAnalysed
                      || bridgeHandler.selectedProjectIsRunning
                      || !enabled(.reAnalyseProject))

            Button(i18n.t("desktop.menu.project.archive"), systemImage: "archivebox") {
                bridgeHandler.menuAction("archive")
            }
            .disabled(true)  // Future — Phase 5

            Divider()

            Button(i18n.t("desktop.menu.project.removeFromSidebar"), systemImage: "minus.circle") {
                windowCommands?.perform(.removeFromSidebar)
            }
            .keyboardShortcut(.delete, modifiers: .command)
            // Dims while the selected project is running — the menu-bar half
            // of the rule the context menu answers by hiding.
            .disabled(bridgeHandler.selectedProjectIsRunning || !enabled(.removeFromSidebar))
        }
    }
}

// MARK: - Codes menu

private struct CodesMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    private var isCodeTab: Bool {
        bridgeHandler.activeTab == .codebook || bridgeHandler.activeTab == .quotes
    }

    var body: some View {
        Button(i18n.t("desktop.menu.codes.createCodeGroup"), systemImage: "folder.badge.plus") {
            bridgeHandler.menuAction("createCodeGroup")
        }

        Button(i18n.t("desktop.menu.codes.renameCodeGroup"), systemImage: "pencil") {
            bridgeHandler.menuAction("renameCodeGroup")
        }
        .disabled(!isCodeTab)

        Button(i18n.t("desktop.menu.codes.deleteCodeGroup"), systemImage: "trash") {
            bridgeHandler.menuAction("deleteCodeGroup")
        }
        .disabled(!isCodeTab)

        Button(i18n.t("desktop.menu.codes.showHideCodeGroup"), systemImage: "eye") {
            bridgeHandler.menuAction("toggleCodeGroup")
        }
        .disabled(!isCodeTab)

        Divider()

        Button(i18n.t("desktop.menu.codes.createCode"), systemImage: "tag") {
            bridgeHandler.menuAction("createCode")
        }

        Button(i18n.t("desktop.menu.codes.renameCode"), systemImage: "pencil") {
            bridgeHandler.menuAction("renameCode")
        }
        .disabled(!isCodeTab)

        Button(i18n.t("desktop.menu.codes.deleteCode"), systemImage: "trash") {
            bridgeHandler.menuAction("deleteCode")
        }
        .disabled(!isCodeTab)

        // Merge Codes — withdrawn from the menu 28 Jul 2026, deliberately left
        // in place rather than deleted.
        //
        // Merging needs a *source* and a *target*. The codebook lens has no
        // multi-select, so the only way to express "merge A into B" is the
        // existing drag-one-code-onto-another in `CodebookPanel` — a menu item
        // simply cannot say which two codes it means. That's why `mergeCode` had
        // no handler on either side of the bridge and clicked through to nothing.
        //
        // Restore this when codebook selection lands (tracked in the sprint
        // planning notes). The web half already exists and works —
        // `mergeCodebookTags` in `frontend/src/utils/api.ts`, driven by the
        // panel's drag merge — so this becomes a one-line re-enable plus a
        // `case "mergeCode"` that reads the selection.
        //
        // Button(i18n.t("desktop.menu.codes.mergeCodes"), systemImage: "arrow.triangle.merge") {
        //     bridgeHandler.menuAction("mergeCode")
        // }
        // .disabled(!isCodeTab)

        Divider()

        Button(i18n.t("desktop.menu.codes.browseCodebooks"), systemImage: "books.vertical") {
            bridgeHandler.menuAction("browseCodebooks")
        }

        Button(i18n.t("desktop.menu.codes.importFramework"), systemImage: "square.and.arrow.down") {
            bridgeHandler.menuAction("importFramework")
        }

        Button(i18n.t("desktop.menu.codes.removeFramework"), systemImage: "minus.circle") {
            bridgeHandler.menuAction("removeFramework")
        }
        .disabled(!isCodeTab)
    }
}

// MARK: - Quotes menu

private struct QuotesMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n
    @FocusedValue(\.windowCommands) private var windowCommands

    private var onQuotesTab: Bool {
        bridgeHandler.activeTab == .quotes
    }

    private var hasFocus: Bool {
        onQuotesTab && bridgeHandler.focusedQuoteId != nil
    }

    private var hasSelection: Bool {
        onQuotesTab && bridgeHandler.selectedQuoteCount > 0
    }

    /// Star / Hide / Apply-Last-Tag act on the selection *or* the focused quote
    /// (the same `selection || focused` target the click and `s`/`h`/`r` keys
    /// use). ⌘A produces a selection with no focused quote, so gating these on
    /// `hasFocus` alone would wrongly disable them right after Select All.
    private var hasTarget: Bool {
        hasFocus || hasSelection
    }

    /// Star command label — flips Star⇄Unstar to match the click/`s`-key intent
    /// (unstar when the target set is all-starred), and carries the selection
    /// count when acting on a multi-selection ("Star 3 Quotes"), mirroring the
    /// Copy Quotes scope labels. Falls back to the plain verb for a single
    /// focused quote.
    private var starLabel: String {
        let base = bridgeHandler.starActionIsUnstar ? "unstar" : "star"
        let count = bridgeHandler.selectedQuoteCount
        if count > 0 {
            return i18n.plural("desktop.menu.quotes.\(base)Count", count: count)
        }
        return i18n.t("desktop.menu.quotes.\(base)")
    }

    /// Star glyph, flipped in step with `starLabel`. The icon previews the
    /// *result*, not the negation of it: "Star" shows the filled star the
    /// quote is about to get; "Unstar" shows the open star it reverts to.
    /// (`star.slash` would read as "starring is disabled" — wrong meaning.)
    private var starSymbol: String {
        bridgeHandler.starActionIsUnstar ? "star" : "star.fill"
    }

    /// Apply-last-tag label — names the tag when one has been applied this
    /// session ("Apply “usability”"); otherwise the generic verb (and the item
    /// is disabled, since there's nothing to repeat).
    private var applyLastTagLabel: String {
        if let name = bridgeHandler.lastTagName {
            return i18n.t("desktop.menu.quotes.applyTagNamed", ["name": name])
        }
        return i18n.t("desktop.menu.quotes.applyLastTag")
    }

    var body: some View {
        Button(starLabel, systemImage: starSymbol) {
            bridgeHandler.menuAction("star")
        }
        .disabled(!hasTarget)

        Button(i18n.t("desktop.menu.quotes.hide"), systemImage: "eye.slash") {
            bridgeHandler.menuAction("hide")
        }
        .disabled(!hasTarget)

        // Add Tag opens the tag input on the focused quote specifically, so it
        // stays focus-gated (unlike the bulk-capable Star/Hide/Apply above).
        Button(i18n.t("desktop.menu.quotes.addTag"), systemImage: "tag") {
            bridgeHandler.menuAction("addTag")
        }
        .disabled(!hasFocus)

        Button(applyLastTagLabel, systemImage: "tag.fill") {
            bridgeHandler.menuAction("applyLastTag")
        }
        .disabled(!hasTarget || bridgeHandler.lastTagName == nil)

        Button(i18n.t("desktop.menu.quotes.revealInTranscript"), systemImage: "doc.text.magnifyingglass") {
            bridgeHandler.menuAction("revealInTranscript")
        }
        .disabled(!hasFocus)

        Button(i18n.t("desktop.menu.quotes.playPause"), systemImage: "play") {
            bridgeHandler.menuAction("playPause")
        }
        .disabled(!onQuotesTab)

        Divider()

        Button(i18n.t("desktop.menu.quotes.nextQuote")) {
            bridgeHandler.menuAction("nextQuote")
        }
        .disabled(!onQuotesTab)

        Button(i18n.t("desktop.menu.quotes.previousQuote")) {
            bridgeHandler.menuAction("previousQuote")
        }
        .disabled(!onQuotesTab)

        Divider()

        Button(i18n.t("desktop.menu.quotes.extendSelectionDown")) {
            bridgeHandler.menuAction("extendSelectionDown")
        }
        .disabled(!onQuotesTab)

        Button(i18n.t("desktop.menu.quotes.extendSelectionUp")) {
            bridgeHandler.menuAction("extendSelectionUp")
        }
        .disabled(!onQuotesTab)

        Button(i18n.t("desktop.menu.quotes.toggleSelection")) {
            bridgeHandler.menuAction("toggleSelection")
        }
        .disabled(!onQuotesTab)

        Button(i18n.t("desktop.menu.quotes.clearSelection")) {
            bridgeHandler.menuAction("clearSelection")
        }
        .disabled(!hasSelection)

        Divider()

        // Export — mirrors the toolbar export popover so every export action has
        // a keyboard- and VoiceOver-reachable path (the popover is a convenience;
        // the menu bar is the canonical, accessible surface). Native submenus
        // give scope/format pickers proper keyboard nav + VoiceOver for free.
        // TODO: surface the global Anonymise toggle here too (needs a shared
        // persisted-flag decision) and retire the legacy copyAsCSV item below.
        Menu(i18n.t("desktop.menu.quotes.copyQuotes"), systemImage: "doc.on.clipboard") {
            Button(i18n.t("desktop.menu.quotes.copyScopeAll",
                          ["count": String(bridgeHandler.totalQuoteCount)])) {
                bridgeHandler.menuAction("copyQuotes", payload: ["scope": "all"])
            }
            Button(i18n.t("desktop.menu.quotes.copyScopeSelected",
                          ["count": String(bridgeHandler.selectedQuoteCount)])) {
                bridgeHandler.menuAction("copyQuotes", payload: ["scope": "selected"])
            }
            .disabled(bridgeHandler.selectedQuoteCount == 0)
            Button(i18n.t("desktop.menu.quotes.copyScopeStarred",
                          ["count": String(bridgeHandler.starredQuoteCount)])) {
                bridgeHandler.menuAction("copyQuotes", payload: ["scope": "starred"])
            }
            .disabled(bridgeHandler.starredQuoteCount == 0)
        }
        .disabled(!onQuotesTab)

        Menu(i18n.t("desktop.menu.quotes.saveSpreadsheet"), systemImage: "tablecells") {
            Button(i18n.t("desktop.menu.quotes.formatCSV")) {
                bridgeHandler.menuAction("saveSpreadsheet", payload: ["format": "csv"])
            }
            Button(i18n.t("desktop.menu.quotes.formatXLSX")) {
                bridgeHandler.menuAction("saveSpreadsheet", payload: ["format": "xlsx"])
            }
        }
        .disabled(!onQuotesTab)

        Button(i18n.t("desktop.menu.quotes.extractClips"), systemImage: "film") {
            bridgeHandler.menuAction("extractClips")
        }
        .disabled(!onQuotesTab)

        // Send to Miro — mirrors the toolbar popover's Miro row. Always enabled
        // (uploads the project's quotes regardless of the active tab), matching
        // the popover. Presents the native MiroSheet (ContentView owns the .sheet).
        // Lives HERE, not in File: Miro exports quotes, and File carries the
        // whole-report export. (Briefly moved to File on 28 Jul 2026 and moved
        // straight back — recorded so it isn't "tidied" there again.)
        Button(i18n.t("common.miro.menuLabel")) {
            windowCommands?.perform(.showMiro)
        }
        .disabled(!WindowCommand.showMiro.isEnabled(hasKeyWindow: windowCommands != nil))

        Divider()

        Button(i18n.t("desktop.menu.quotes.copyAsCSV"), systemImage: "doc.on.clipboard") {
            bridgeHandler.menuAction("copyAsCSV")
        }
        .disabled(!hasSelection)
    }
}

// MARK: - Video menu

private struct VideoMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    private var active: Bool { bridgeHandler.hasPlayer }

    var body: some View {
        Button(bridgeHandler.playerPlaying
               ? i18n.t("desktop.menu.video.pause")
               : i18n.t("desktop.menu.video.play"),
               systemImage: bridgeHandler.playerPlaying ? "pause" : "play") {
            bridgeHandler.menuAction("playPause")
        }
        .disabled(!active)

        Divider()

        Button(i18n.t("desktop.menu.video.skipForward5"), systemImage: "goforward.5") {
            bridgeHandler.menuAction("skipForward5")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.skipBack5"), systemImage: "gobackward.5") {
            bridgeHandler.menuAction("skipBack5")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.skipForward30"), systemImage: "goforward.30") {
            bridgeHandler.menuAction("skipForward30")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.skipBack30"), systemImage: "gobackward.30") {
            bridgeHandler.menuAction("skipBack30")
        }
        .disabled(!active)

        Divider()

        Button(i18n.t("desktop.menu.video.speedUp"), systemImage: "forward") {
            bridgeHandler.menuAction("speedUp")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.slowDown"), systemImage: "backward") {
            bridgeHandler.menuAction("slowDown")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.normalSpeed"), systemImage: "gauge.medium") {
            bridgeHandler.menuAction("normalSpeed")
        }
        .disabled(!active)

        Divider()

        Button(i18n.t("desktop.menu.video.volumeUp"), systemImage: "speaker.wave.3") {
            bridgeHandler.menuAction("volumeUp")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.volumeDown"), systemImage: "speaker.wave.1") {
            bridgeHandler.menuAction("volumeDown")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.mute"), systemImage: "speaker.slash") {
            bridgeHandler.menuAction("mute")
        }
        .disabled(!active)

        Divider()

        Button(i18n.t("desktop.menu.video.pictureInPicture"), systemImage: "pip.enter") {
            bridgeHandler.menuAction("pictureInPicture")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.fullscreen"), systemImage: "arrow.up.left.and.arrow.down.right") {
            bridgeHandler.menuAction("fullscreen")
        }
        .disabled(!active)
    }
}

// MARK: - Help menu

private struct HelpMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n
    @FocusedValue(\.windowCommands) private var windowCommands

    var body: some View {
        // Help, Keyboard Shortcuts, and Acknowledgements open external pages in
        // the browser — the in-app Help modal is retired ("Help opens browser
        // docs"). They don't route through the web bridge, so they work whether
        // or not the SPA is mounted (e.g. on the status page after a failed run).
        Button(i18n.t("desktop.menu.help.bristlenoseHelp"), systemImage: "questionmark.circle") {
            Self.open("https://bristlenose.app/docs/")
        }
        .keyboardShortcut("?", modifiers: .command)

        // Re-openable way back to the app-level Welcome home pane. No shortcut —
        // it's a rare, unmemorable destination (per the deliberate no-⌘⇧1 call);
        // discoverability comes from living in Help, not a keybinding. Clears the
        // project selection; ContentView shows WelcomeHomeView on no-selection.
        // Reuses the vetted, all-locale `chrome.welcomeTitle` ("Welcome to
        // Bristlenose") kept from the retired WelcomeView — see
        // docs/design-welcome-screen.md §Copy & i18n; this is now a live reference.
        Button(i18n.t("desktop.chrome.welcomeTitle")) {
            windowCommands?.perform(.showWelcome)
        }
        .disabled(!WindowCommand.showWelcome.isEnabled(hasKeyWindow: windowCommands != nil))

        Button(i18n.t("desktop.menu.help.keyboardShortcuts")) {
            Self.open("https://bristlenose.app/docs/keyboard-shortcuts.html")
        }

        Divider()

        Button(i18n.t("desktop.menu.help.releaseNotes")) {
            Self.open("https://bristlenose.app/docs/changelog.html")
        }

        // Always opens the native FeedbackSheet (report lens, status page, or
        // welcome screen). `openFeedback` posts `.showFeedbackSheet`; ContentView
        // presents it with the live-serve config or the serve-free `.serverless`
        // fallback when no project is selected.
        Button(i18n.t("desktop.menu.help.sendFeedback")) {
            bridgeHandler.openFeedback()
        }

        Divider()

        Button(i18n.t("desktop.menu.help.blog")) {
            bridgeHandler.menuAction("openBlog")
        }

        Button(i18n.t("desktop.menu.help.acknowledgements")) {
            Self.open("https://github.com/cassiocassio/bristlenose/blob/main/ACKNOWLEDGEMENTS.md")
        }
    }

    /// Open an external URL in the system browser, scheme-guarded (defence in
    /// depth — this is the native sink, so it doesn't pass through WebView's
    /// navigation allowlist).
    private static func open(_ string: String) {
        guard let url = URL(string: string),
              let scheme = url.scheme?.lowercased(),
              scheme == "https" || scheme == "http" else { return }
        NSWorkspace.shared.open(url)
    }
}
