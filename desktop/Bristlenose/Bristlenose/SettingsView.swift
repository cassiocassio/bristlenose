import AppKit
import Settings
import SwiftUI

// `PkgSettings` — a collision-free alias for the package's `Settings` namespace
// — is defined in SettingsPackageAlias.swift (a file without `import SwiftUI`,
// so `Settings` there resolves to the package, not SwiftUI's `Settings` scene).
// A bare `Settings.Pane` here would resolve to SwiftUI's `Settings` and fail.

// Stable identifiers for the three Settings panes (also used for deep-linking —
// e.g. the welcome "Setup →" opens `.llm`).
extension PkgSettings.PaneIdentifier {
    static let appearance = Self("appearance")
    static let llm = Self("llm")
    static let transcription = Self("transcription")
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
/// architecturally absent. Do NOT reintroduce a TabView here.
/// See `docs/design-desktop-settings.md` for the research trail.
@MainActor
final class SettingsWindow {
    static let shared = SettingsWindow()
    private init() {}

    /// Set once at launch by `BristlenoseApp` — the SwiftUI panes need it via
    /// `.environmentObject`. Read when the controller is first built (lazily,
    /// on first open), by which point launch has set it.
    var i18n: I18n?

    private lazy var controller: SettingsWindowController = {
        let i18n = self.i18n ?? I18n()
        return SettingsWindowController(
            panes: [
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
            ],
            style: .toolbarItems,
            animated: true
        )
    }()

    /// Open the Settings window on the last-used pane (Cmd+, / menu).
    func show() {
        applyAppearance()
        controller.show()
    }

    /// Open the Settings window on a specific pane (deep-link).
    func show(pane: PkgSettings.PaneIdentifier) {
        applyAppearance()
        controller.show(pane: pane)
    }

    /// Match the window chrome to the app appearance preference. Called at
    /// open time and again by `SettingsPaneChrome` whenever the preference
    /// changes while the window is open — the panes' `.preferredColorScheme`
    /// can't reach this AppKit window's chrome, only `window.appearance` can.
    fileprivate func applyAppearance() {
        let pref = UserDefaults.standard.string(forKey: "appearance") ?? "auto"
        controller.window?.appearance = switch pref {
        case "light": NSAppearance(named: .aqua)
        case "dark": NSAppearance(named: .darkAqua)
        default: nil  // follow system
        }
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
        switch appearance {
        case "light": .light
        case "dark": .dark
        default: nil
        }
    }
}
