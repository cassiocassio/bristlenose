import SwiftUI
import AppKit

/// Top-level Settings window with icon tabs (Apple canonical pattern).
///
/// Three tabs: Appearance, LLM, Transcription.
/// Mac convention: width fixed per tab, height animates to fit each tab's
/// content. SwiftUI's `Settings` + `TabView` won't do the height half on its
/// own — see `SettingsWindowHeightAnimator` below.
struct SettingsView: View {

    @EnvironmentObject var i18n: I18n
    @AppStorage("appearance") private var appearance: String = "auto"
    // Selected tab, bound so callers can deep-link (e.g. the welcome "Setup →" opens .llm).
    @AppStorage("settingsSelectedTab") private var selectedTab: String = "appearance"
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var colorScheme: ColorScheme? {
        switch appearance {
        case "light": .light
        case "dark": .dark
        default: nil
        }
    }

    // Per-tab target CONTENT height — the region below the tab-pill toolbar.
    // A `.formStyle(.grouped)` Form is greedy vertically (it fills whatever
    // height it's handed), so it never tells the window "I'm short"; SwiftUI
    // sizes the window to the tallest tab once and never shrinks back. We drive
    // the height ourselves. THESE THREE NUMBERS ARE THE TUNING KNOBS — eyeball
    // each tab against its real render and nudge (geometry fixed, content bends).
    private func targetContentHeight(for tab: String) -> CGFloat {
        switch tab {
        case "llm": return 660            // matches LLMSettingsView's minHeight
        case "transcription": return 220  // Backend cell + Model cell
        default: return 590               // appearance
        }
    }

    var body: some View {
        TabView(selection: $selectedTab) {
            AppearanceSettingsView()
                .environmentObject(i18n)
                .tabItem { Label(i18n.t("desktop.settingsTabs.appearance"), systemImage: "paintbrush") }
                .tag("appearance")

            LLMSettingsView()
                .tabItem { Label(i18n.t("desktop.settingsTabs.llm"), systemImage: "brain") }
                .tag("llm")

            TranscriptionSettingsView()
                .tabItem { Label(i18n.t("desktop.settingsTabs.transcription"), systemImage: "waveform") }
                .tag("transcription")
        }
        .preferredColorScheme(colorScheme)
        .background(
            SettingsWindowHeightAnimator(
                contentHeight: targetContentHeight(for: selectedTab),
                animate: !reduceMotion
            )
        )
    }
}

/// Animates the hosting Settings window to a per-tab content height.
///
/// SwiftUI's `Settings` + `TabView` high-water-marks: it grows the window to
/// the tallest tab and never shrinks back (a greedy grouped Form gives the
/// window no "I'm short" signal). We resize the `NSWindow` ourselves on each
/// tab change, anchoring the top edge so the title bar stays put (windows
/// anchor bottom-left). Honours Reduce Motion (the first sizing never
/// animates — there's no "from" state to animate).
private struct SettingsWindowHeightAnimator: NSViewRepresentable {
    let contentHeight: CGFloat
    let animate: Bool

    func makeNSView(context: Context) -> NSView {
        let view = NSView(frame: .zero)
        // Defer until the view has joined a window.
        DispatchQueue.main.async { apply(to: view.window, animated: false) }
        return view
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        DispatchQueue.main.async { apply(to: nsView.window, animated: animate) }
    }

    private func apply(to window: NSWindow?, animated: Bool) {
        guard let window else { return }

        // Frame rect for the desired content height, preserving the current
        // width (the tab content owns its 660 width; we never touch it here).
        let currentContent = window.contentRect(forFrameRect: window.frame)
        let targetContent = NSRect(
            x: currentContent.minX, y: currentContent.minY,
            width: currentContent.width, height: contentHeight
        )
        var targetFrame = window.frameRect(forContentRect: targetContent)

        // Anchor the top-left: keep origin.x, move origin.y so the top edge
        // (maxY) is unchanged as the height changes.
        targetFrame.origin.x = window.frame.origin.x
        targetFrame.origin.y = window.frame.maxY - targetFrame.height

        // No-op if we're already there (updateNSView fires on any state change).
        guard abs(targetFrame.height - window.frame.height) > 0.5 else { return }

        window.setFrame(targetFrame, display: true, animate: animated)
    }
}
