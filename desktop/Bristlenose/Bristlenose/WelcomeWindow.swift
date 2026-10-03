import AppKit
import SwiftUI

// MARK: - Welcome window (Model 2, design-welcome-screen.md, 3 Oct 2026)
//
// Welcome is its own ordinary, resizable macOS window — one for the whole app,
// not one per main window. It opens at launch when the researcher has left
// "Show Welcome when Bristlenose opens" ticked, and from Help ▸ Welcome to
// Bristlenose at any time. Nothing else summons it: a cleared selection in a
// main window shows that window's drop card, not Welcome.
//
// It is help, so it lives in Help and nowhere else — the scene is
// `.commandsRemoved()` so SwiftUI does not add its own Window-menu opener. It
// still appears in the Window menu's list of open windows, because it is a real
// window.

enum WelcomeWindow {
    /// The `Window` scene id `openWindow(id:)` targets.
    static let id = "welcome"

    /// The one setting behind the footer checkbox and its Settings ▸ Appearance
    /// mirror. Absent means ticked: a fresh install shows Welcome.
    static let showOnLaunchKey = "showWelcomeOnLaunch"

    /// The window's frame name. AppKit writes the frame here on every move and
    /// resize, and reads it back on the next open — so after the first open the
    /// window comes back exactly where the researcher left it. Versioned with the
    /// natural size: if `WelcomeSpiralLayout.naturalWidth` moves, bump it, or a
    /// saved frame from the old size fights the new limits.
    static let frameAutosaveName = "BristlenoseWelcomeWindow.v1"

    /// Content width at the spiral's natural size: the spiral plus 20 pt margins.
    static let naturalContentWidth = WelcomeSpiralLayout.naturalWidth + 40
    /// Narrowest content width: the Scientific background cell plus margins.
    static let minimumContentWidth = WelcomeSpiralLayout.minimumWidth + 40
    /// Below this content width the spiral stacks (Study tools on top); at or above
    /// it, the spiral narrows with the window. Set by eye on a real window, 3 Oct
    /// 2026: at ~600 pt the spiral is still legible, and stacking any earlier gave
    /// a window barely narrower than natural a Study tools cell as tall as it was
    /// wide, mostly empty.
    static let stackBelowContentWidth: CGFloat = 600

    /// Whether a window of this content width shows the stacked arrangement.
    static func stacks(atContentWidth width: CGFloat) -> Bool {
        width < stackBelowContentWidth
    }
    /// Opening height: margins, the spiral, and the footer checkbox — with a few
    /// points of slack over the footer's nominal 8 + checkbox + 16, so a taller
    /// control style or text size does not make the natural size scroll.
    static let naturalContentHeight = WelcomeSpiralLayout.naturalHeight + 40 + 48
    /// Tallest useful height: the stacked arrangement at the minimum width, with
    /// the same margins and footer. Caps the green button's zoom, which would
    /// otherwise stretch a narrow window into a tall empty one.
    static let maximumContentHeight = WelcomeSpiralLayout.stackedHeight(
        width: WelcomeSpiralLayout.minimumWidth,
        studyHeight: WelcomeSpiralLayout.naturalHeight * 1.5,
        scienceHeight: WelcomeSpiralLayout.naturalHeight * 1.5) + 40 + 48

    /// Whether this launch should open the window. Read once per launch.
    static var showsOnLaunch: Bool {
        UserDefaults.standard.object(forKey: showOnLaunchKey) as? Bool ?? true
    }
}

/// The Welcome window's content: the spiral, sized to its window, with the
/// frame-restoring accessor underneath.
struct WelcomeWindowContent: View {
    var body: some View {
        WelcomeHomeView()
            .frame(minWidth: WelcomeWindow.minimumContentWidth,
                   idealWidth: WelcomeWindow.naturalContentWidth,
                   maxWidth: WelcomeWindow.naturalContentWidth,
                   minHeight: 320,
                   idealHeight: WelcomeWindow.naturalContentHeight,
                   maxHeight: WelcomeWindow.maximumContentHeight)
            .background(WelcomeWindowFrameAccessor())
    }
}

/// Gives the window a remembered frame. The very first open has nothing saved, so
/// it is centred over the main window at the spiral's natural size. Every later
/// open restores what the researcher left: it is their screen.
private struct WelcomeWindowFrameAccessor: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView { FrameView() }
    func updateNSView(_ nsView: NSView, context: Context) {}

    private final class FrameView: NSView {
        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            guard let window else { return }
            // One runloop turn later: at this point SwiftUI has not finished placing
            // and sizing the window, and its `defaultSize` would land on top of
            // whatever frame we set now.
            Task { @MainActor in Self.adopt(window) }
        }

        @MainActor private static func adopt(_ window: NSWindow) {
            // Welcome is not a document; it never joins a main window's tab group,
            // whatever "Prefer tabs" says.
            window.tabbingMode = .disallowed
            guard window.frameAutosaveName != WelcomeWindow.frameAutosaveName else { return }
            // `setFrameUsingName` answers whether a saved frame existed; only then is
            // the frame the researcher's rather than ours.
            let restored = window.setFrameUsingName(WelcomeWindow.frameAutosaveName)
            // False when another window still holds the name — then this one is
            // simply not remembered, which is harmless; centring still applies.
            _ = window.setFrameAutosaveName(WelcomeWindow.frameAutosaveName)
            if !restored { centre(window) }
        }

        /// Centre over the main window it is opened beside — not the screen, which
        /// is only the same place while that window sits at its default spot.
        @MainActor private static func centre(_ window: NSWindow) {
            let others = NSApp.orderedWindows.filter {
                $0 !== window && $0.isVisible && $0.styleMask.contains(.titled)
            }
            // The main scene's windows carry its id as their identifier prefix; if
            // that ever changes, the frontmost other titled window is the next best.
            let anchor = others.first { $0.identifier?.rawValue.hasPrefix("main") == true } ?? others.first
            guard let anchor, let screen = anchor.screen ?? window.screen else { window.center(); return }
            var frame = window.frame
            frame.origin = CGPoint(x: anchor.frame.midX - frame.width / 2,
                                   y: anchor.frame.midY - frame.height / 2)
            // Keep the whole window on the anchor's screen.
            let visible = screen.visibleFrame
            frame.origin.x = min(max(frame.minX, visible.minX), visible.maxX - frame.width)
            frame.origin.y = min(max(frame.minY, visible.minY), visible.maxY - frame.height)
            window.setFrame(frame, display: true)
        }
    }
}
