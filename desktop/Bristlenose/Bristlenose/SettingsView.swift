import AppKit
import Combine
import Settings
import SwiftUI

// `PkgSettings` — a collision-free alias for the package's `Settings` namespace
// — is defined in SettingsPackageAlias.swift (a file without `import SwiftUI`,
// so `Settings` there resolves to the package, not SwiftUI's `Settings` scene).
// A bare `Settings.Pane` here would resolve to SwiftUI's `Settings` and fail.

// Stable identifiers for the six Settings panes (also used for deep-linking —
// e.g. the welcome "Setup →" opens `.llm`; Bristlenose ▸ Connect an Agent…
// opens `.mcpAgents`).
extension PkgSettings.PaneIdentifier {
    static let general = Self("general")
    static let appearance = Self("appearance")
    static let llm = Self("llm")
    static let transcription = Self("transcription")
    static let accounts = Self("accounts")
    static let mcpAgents = Self("mcpAgents")
}

/// Owns the macOS Settings window.
///
/// Built on Sindre Sorhus's `Settings` package (an AppKit `SettingsWindowController`
/// that swaps `NSViewController` panes), NOT a SwiftUI `Settings {}` + `TabView`.
/// Rationale: SwiftUI's `Settings` + `TabView` high-water-marks — it grows the
/// window to the tallest tab and never shrinks back (a greedy `.formStyle(.grouped)`
/// Form gives the window no natural content-height signal). The package sizes each
/// pane to its `view.fittingSize` fresh on every switch and animates the window in
/// both directions, so shorter tabs genuinely shrink and the high-water-mark is
/// architecturally absent.
///
/// **On every switch is the whole contract** — `setWindowFrame` has exactly two
/// callers and both are tab activation, and the pane view is pinned by required
/// constraints that beat `NSHostingView`'s 750-priority intrinsic height. So a
/// pane whose height depends on its own state compresses or clips rather than
/// resizing; it must call `refitToContent()`. See `docs/design-desktop-settings.md`. Do NOT reintroduce a TabView here.
/// See `docs/design-desktop-settings.md` for the research trail.
@MainActor
final class SettingsWindow {
    static let shared = SettingsWindow()
    private init() {}

    /// Set once at launch by `BristlenoseApp` — the SwiftUI panes need it via
    /// `.environmentObject`. Read when the controller is first built (lazily,
    /// on first open), by which point launch has set it.
    var i18n: I18n?
    /// The MCP Agents pane's live inputs, set at launch like `i18n`: the
    /// serve state (Now-showing line, payload values) and the project index
    /// (the agent-access list). App-lifetime objects; plain strong refs.
    /// The fleet, read at use time.
    ///
    /// This was a `ServeManager?` assigned once at first-window `.onAppear` —
    /// which is *before* anything is fronted, so it captured a manager that
    /// never spawns, and Settings ▸ MCP Agents then reported "built without
    /// agent support" for the whole session with a live serve running. Holding
    /// the fleet means the panes resolve the current one when they are built.
    var serveFleet: ServeFleet?

    /// The fronted serve, or the fleet's idle stand-in.
    private var serveManager: ServeManager? { serveFleet?.frontedOrIdle }
    var projectIndex: ProjectIndex?
    /// Read for one question only: is an analysis running? A language change
    /// offers to relaunch, and relaunching mid-run would kill the subprocess.
    var pipelineRunner: PipelineRunner?

    /// True when any project is mid-analysis.
    var isAnalysing: Bool {
        pipelineRunner?.state.values.contains { $0.keepsMachineAwake } ?? false
    }

    /// Built on first open, and **rebuilt when the UI language changes**.
    ///
    /// This was `private lazy var controller`, built once per process. The pane
    /// bodies below hold `i18n` as an `@EnvironmentObject` and re-render on a
    /// locale change; a `PkgSettings.Pane`'s `title` is a plain `String`,
    /// resolved when the pane is constructed, and cannot. So the six toolbar
    /// labels — and the window title, which the package derives from the
    /// selected pane — stayed frozen in whatever language was active the first
    /// time Settings was opened.
    ///
    /// **That is not an edge case: the language picker lives in this window.**
    /// The only way to change language is to open Settings (resolving the
    /// titles at the old locale) and then switch, so every user who changed
    /// language saw English tabs over translated content for the rest of the
    /// session, in every locale. Found on screen (a Polish screenshot,
    /// 21 Sep 2026), and findable no other way — the key is present, the value
    /// is correctly translated, `i18n.t` is called, and `check-locales.py` is
    /// green. `docs/i18n-defects.md` calls this failure class 6.
    ///
    /// Note the sibling trap the MCP Agents pane already documents below: that
    /// closure "runs ONCE, so anything resolved in it is pinned for the
    /// process". `serveManager` was fixed for exactly this reason. The titles
    /// have the same shape and were missed.
    private var builtController: SettingsWindowController?

    /// Where to put the user back after a locale rebuild, when the live window
    /// cannot be asked (it is already closed). Deep links set it; the picker
    /// path reads the toolbar instead — see `activePane`.
    private var lastShownPane: PkgSettings.PaneIdentifier?

    /// The pane the user is actually looking at.
    ///
    /// `SettingsTabViewController.activeTab` is `private`, but the package
    /// builds its toolbar with **the pane identifiers as item identifiers** —
    /// `PaneIdentifier(fromToolbarItemIdentifier:)` is public precisely for this
    /// round-trip — so the selected toolbar item is the active pane.
    ///
    /// Needed because a locale rebuild that guesses lands the user somewhere
    /// they did not ask to be: `lastShownPane` is only ever set by a deep link,
    /// so the everyday path (open Settings, change language) left it nil and the
    /// `show()` fallback restored the package's initial tab — **General** —
    /// yanking the user off Appearance the instant they used the picker that
    /// lives there. Reported from a screenshot, 21 Sep 2026.
    private var activePane: PkgSettings.PaneIdentifier? {
        guard let identifier = builtController?.window?.toolbar?.selectedItemIdentifier
        else { return lastShownPane }
        return PkgSettings.PaneIdentifier(fromToolbarItemIdentifier: identifier)
    }

    /// Live once the controller exists; `I18n.locale` is `@Published` and
    /// `AppearanceSettingsView` drives it through `setLocale`.
    private var localeObservation: AnyCancellable?

    private var controller: SettingsWindowController {
        if let built = builtController { return built }
        let made = makeController()
        builtController = made
        observeLocale()
        return made
    }

    /// Rebuild on the next locale change, restoring visibility and pane.
    ///
    /// `dropFirst()` because `@Published` publishes the current value on
    /// subscribe, and subscribing happens during the first build — without it
    /// the controller would tear itself down the moment it was created.
    private func observeLocale() {
        guard localeObservation == nil, let i18n else { return }
        localeObservation = i18n.$locale
            .dropFirst()
            .removeDuplicates()
            .sink { [weak self] _ in
                // Hop a tick before tearing down. The rebuild cancels this very
                // subscription, and it runs inside the picker's own change
                // handler — doing both on the current stack means cancelling a
                // Combine subscription from within its own `sink` and closing an
                // NSWindow mid-event. Neither is worth the risk for a rare,
                // deliberate action.
                DispatchQueue.main.async { self?.rebuildForLocaleChange() }
            }
    }

    private func rebuildForLocaleChange() {
        guard let existing = builtController else { return }
        let wasVisible = existing.window?.isVisible ?? false
        // Read the live toolbar BEFORE closing — afterwards there is nothing
        // left to ask, and the fallback is a guess.
        let pane = activePane
        existing.window?.close()
        builtController = nil
        localeObservation = nil
        guard wasVisible else { return }
        // Reopening is what re-resolves the titles. A closed window needs
        // nothing — the next `show()` builds fresh.
        if let pane { show(pane: pane) } else { show() }
        promptToRelaunch()
    }

    /// Offer the relaunch, because AppKit will not change its mind without one.
    ///
    /// **Apple's pattern and Apple's words.** System Settings ▸ General ▸
    /// Language & Region ▸ Applications puts up exactly this dialog, and Apple
    /// DTS is explicit that there is no supported way for an app to change its
    /// own language at runtime (developer.apple.com/forums/thread/718512:
    /// *"AppleLanguages is an implementation detail, not something that's
    /// considered API"* … *"there is no supported mechanism for your app to
    /// change its own language"*). A relaunch is the platform's answer, not a
    /// shortcoming of ours — and Apple's own UI offers it rather than hiding it.
    ///
    /// The four strings are **lifted, not translated**, out of
    /// `Localization.appex/Localizable.loctable`, which carries all 21 of our
    /// locales. Same principle as the `Choose` button and the TCC prompts: look
    /// it up, do not write it. Apple writes the app-name slot two ways — plain
    /// `%@` and the typed `%[tt]@` (fi, ja, zh-Hant) — and both are baked to
    /// "Bristlenose" at seed time, because the app name is a constant here and
    /// not a variable.
    ///
    /// Without this the researcher gets what prompted it: a German menu bar
    /// over a French app, because AppKit read its language once at process
    /// start while everything else follows `I18n` live.
    ///
    /// **Never relaunches during an analysis.** That would kill the subprocess
    /// mid-run to fix a cosmetic mismatch. The alert then states Apple's own
    /// "will not use the new language until relaunched" and offers no button.
    private func promptToRelaunch() {
        guard let i18n else { return }
        let busy = isAnalysing
        let alert = NSAlert()
        alert.alertStyle = .informational
        alert.messageText = i18n.t(
            busy ? "settings.language.relaunchBody" : "settings.language.relaunchTitle")
        if busy {
            alert.addButton(withTitle: i18n.t("common.buttons.ok"))
        } else {
            alert.informativeText = i18n.t("settings.language.relaunchBody")
            alert.addButton(withTitle: i18n.t("settings.language.relaunchNow"))
            alert.addButton(withTitle: i18n.t("settings.language.dontRelaunch"))
        }

        let act = { (response: NSApplication.ModalResponse) in
            guard !busy, response == .alertFirstButtonReturn else { return }
            let configuration = NSWorkspace.OpenConfiguration()
            configuration.createsNewApplicationInstance = true
            NSWorkspace.shared.openApplication(
                at: Bundle.main.bundleURL, configuration: configuration
            ) { _, _ in
                DispatchQueue.main.async { NSApp.terminate(nil) }
            }
        }
        if let window {
            alert.beginSheetModal(for: window, completionHandler: act)
        } else {
            act(alert.runModal())
        }
    }

    private func makeController() -> SettingsWindowController {
        let i18n = self.i18n ?? I18n()
        return SettingsWindowController(
            panes: [
                // First, deliberately: General is the pane a Mac user checks for
                // app-level behaviour ("where do new things go"), and it holds
                // the answer the other four never touch. See
                // GeneralSettingsView for why it isn't a row in Appearance.
                PkgSettings.Pane(
                    identifier: .general,
                    title: i18n.t("desktop.settingsTabs.general"),
                    toolbarIcon: symbol("gearshape")
                ) {
                    GeneralSettingsView()
                        .environmentObject(i18n)
                        .modifier(SettingsPaneChrome())
                },
                PkgSettings.Pane(
                    identifier: .appearance,
                    title: i18n.t("desktop.settingsTabs.appearance"),
                    toolbarIcon: symbol("paintbrush")
                ) {
                    AppearanceSettingsView()
                        .environmentObject(i18n)
                        .modifier(SettingsPaneChrome())
                },
                PkgSettings.Pane(
                    identifier: .llm,
                    title: i18n.t("desktop.settingsTabs.llm"),
                    toolbarIcon: symbol("brain")
                ) {
                    LLMSettingsView()
                        .environmentObject(i18n)
                        .modifier(SettingsPaneChrome())
                },
                PkgSettings.Pane(
                    identifier: .transcription,
                    title: i18n.t("desktop.settingsTabs.transcription"),
                    toolbarIcon: symbol("waveform")
                ) {
                    TranscriptionSettingsView()
                        .environmentObject(i18n)
                        .modifier(SettingsPaneChrome())
                },
                // Accounts sits beside MCP Agents rather than near the engines:
                // both answer "who can reach your work and your material", where
                // the panes above answer "how does it run". §9 puts account
                // lifecycle here — "one place to disconnect, not two".
                PkgSettings.Pane(
                    identifier: .accounts,
                    title: i18n.t("desktop.settingsTabs.accounts"),
                    toolbarIcon: symbol("person.crop.circle")
                ) {
                    // The serve is needed for one thing only: disconnecting
                    // Miro has to clear the running sidecar's in-memory copy of
                    // the token as well as the Keychain one. Same shape as the
                    // cloud disconnect reaching an open import window, and the
                    // same `if let` as MCP Agents below — the pane is built
                    // lazily on first open, by which point launch has set it.
                    Group {
                        if let serve = self.serveManager {
                            AccountsSettingsView(serveManager: serve)
                        }
                    }
                    .environmentObject(i18n)
                    .modifier(SettingsPaneChrome())
                },
                // Last, deliberately: Appearance is chrome, LLM Provider and
                // Transcription are the engines; who can read your work is a
                // fourth concern (design-mcp-extension §3.7). The antenna
                // matches the sidebar badge — one concept, one symbol.
                PkgSettings.Pane(
                    identifier: .mcpAgents,
                    title: i18n.t("desktop.settingsTabs.mcpAgents"),
                    toolbarIcon: symbol("antenna.radiowaves.left.and.right")
                ) {
                    // Both are wired at launch (BristlenoseApp), before the
                    // window can open; the guard is defensive shape, not a
                    // real state.
                    Group {
                        if let index = self.projectIndex, let fleet = self.serveFleet {
                            // No `serveManager` here on purpose — this closure
                            // runs ONCE, so anything resolved in it is pinned
                            // for the process. The pane computes the fronted
                            // serve in its own body.
                            MCPAgentsSettingsView(projectIndex: index, serveFleet: fleet)
                        }
                    }
                    .environmentObject(i18n)
                    .modifier(SettingsPaneChrome())
                },
            ],
            style: .toolbarItems,
            animated: true
        )
    }

    /// Re-fit the window to the pane's current content height.
    ///
    /// The package sizes the window from `view.fittingSize`, which is the
    /// right mechanism — but it runs it only at tab activation
    /// (`immediatelyDisplayTab` and `animateTabTransition`, its only two
    /// callers). A pane whose own content changes shape while it is on screen
    /// — MCP Agents switching client tabs, or its projects register gaining a
    /// row — therefore compresses or clips instead of resizing.
    ///
    /// This is the same arithmetic, on demand: ask the content for the height
    /// it wants and set the frame from the top-left, so the title bar stays
    /// put and the window grows or shrinks downward. Deliberately NOT a
    /// reimplementation of layout — `fittingSize` is still the package's
    /// answer, and if the package ever gains a public re-fit this becomes a
    /// one-line forward.
    func refitToContent(animated: Bool = true, shrinkThreshold: CGFloat = 0) {
        guard let window = controller.window,
              let content = window.contentViewController?.view else { return }
        content.layoutSubtreeIfNeeded()
        let fitting = content.fittingSize
        guard fitting.height > 0 else { return }
        let wanted = window.frameRect(
            forContentRect: CGRect(origin: .zero, size: fitting)).size.height
        guard let target = Self.refitTarget(
            current: window.frame.height,
            fitting: wanted,
            shrinkThreshold: shrinkThreshold) else { return }
        var frame = window.frame
        frame.origin.y += frame.height - target
        frame.size.height = target
        // Reduce Motion is honoured HERE, not at the call sites, so a pane
        // cannot forget it. Both call sites had.
        let shouldAnimate = animated
            && !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
        (shouldAnimate ? window.animator() : window).setFrame(frame, display: false)
    }

    /// A sub-point difference is layout noise, and setting the frame to it
    /// would animate the window on every render pass.
    static let refitNoise: CGFloat = 0.5

    /// The height the window should take next, or `nil` to stay put.
    ///
    /// **Asymmetric, and the asymmetry is load-bearing.** Growth is deadbanded
    /// only by `refitNoise` — never by `shrinkThreshold`: a pane wanting more
    /// room than the window has does not get a scrollbar, it gets compressed
    /// by the required constraints that pin it
    /// (`Utilities.constrainToSuperviewBounds`), silently. That was the shipped
    /// Azure defect — 681pt of content in a window pinned at 660 whenever Azure
    /// was reached by *switching* rather than by opening Settings on it, so the
    /// same pane rendered differently depending on how you arrived.
    ///
    /// Shrinking is deadbanded because the saving has to be worth the motion.
    /// Switching tabs is navigation and a resize reads as arrival; picking a row
    /// in a master-detail list is browsing, and a window that resizes by a row's
    /// worth on every click makes the comparison feel unstable. A caller passing
    /// `0` (the default, and what MCP Agents wants) gets exact fit in both
    /// directions.
    ///
    /// Both arms return `fitting`, so a mis-edit here is invisible to the type
    /// checker — pinned by `SettingsRefitTests`.
    static func refitTarget(
        current: CGFloat, fitting: CGFloat, shrinkThreshold: CGFloat
    ) -> CGFloat? {
        if fitting > current + refitNoise { return fitting }       // grow: past noise
        if current - fitting > max(shrinkThreshold, refitNoise) {  // shrink: earned
            return fitting
        }
        return nil
    }

    /// The window itself, for panes that need to know when the visit ends.
    ///
    /// `MCPAgentsSettingsView`'s revocation receipts live for one visit, and
    /// "the visit" is this window being open — not the pane being on screen,
    /// which the package's tab transition changes underneath it. Reading
    /// `controller.window` would build the controller on first access; the
    /// panes only ask once they exist, so by then it is built.
    var window: NSWindow? { controller.window }

    /// Open the Settings window on the last-used pane (Cmd+, / menu).
    func show() {
        applyAppearance()
        controller.show()
    }

    /// Open the Settings window on a specific pane (deep-link).
    func show(pane: PkgSettings.PaneIdentifier) {
        applyAppearance()
        lastShownPane = pane
        controller.show(pane: pane)
    }

    /// Match the window chrome to the app appearance preference.
    ///
    /// Belt-and-braces since `AppAppearance` began setting `NSApp.appearance`,
    /// which this window inherits like any other. Kept because it costs one
    /// line and this window is built by an AppKit controller rather than a
    /// SwiftUI scene — the panes' `.preferredColorScheme` can't reach its
    /// chrome, only `window.appearance` can.
    fileprivate func applyAppearance() {
        controller.window?.appearance = AppAppearance.current
    }

    private func symbol(_ name: String) -> NSImage {
        NSImage(systemSymbolName: name, accessibilityDescription: nil)
            ?? NSImage(size: NSSize(width: 1, height: 1))
    }
}

/// Per-pane chrome: palette-aware tint + appearance, tracking `@AppStorage`
/// live (the panes are real SwiftUI views hosted by the package, so this
/// updates without rebuilding the window).
private struct SettingsPaneChrome: ViewModifier {
    @AppStorage("appearance") private var appearance = "auto"
    @AppStorage("palette") private var palette = "default"

    func body(content: Content) -> some View {
        content
            // Palette-aware SwiftUI accent (matches the main window). AppKit
            // chrome — the pane toolbar icons — still reads the system accent,
            // deliberate per the seam-alignment discipline.
            .tint(Color("Palette\(palette.capitalized)Accent"))
            .preferredColorScheme(colorScheme)
            // Re-apply the AppKit window appearance live — the pref is edited
            // from the Appearance pane, so this modifier is on-screen whenever
            // it changes.
            .onChange(of: appearance) { _, _ in
                SettingsWindow.shared.applyAppearance()
            }
    }

    private var colorScheme: ColorScheme? {
        AppAppearance.colorScheme(for: appearance)
    }
}
