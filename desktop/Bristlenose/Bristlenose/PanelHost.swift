import AppKit

/// Which window a save/open panel belongs to.
///
/// Appearance is handled app-wide by `AppAppearance` — read that first. This
/// type exists for the two things `NSApp.appearance` can't do:
///
/// 1. **Attach a sheet.** `beginSheetModal(for:)` needs a host window, and a
///    drop-initiated panel presents just as the drag's modal event loop
///    unwinds, when `keyWindow` is momentarily `nil`. Hence the fallback chain;
///    `canBecomeMain` filters out panels and utility windows.
/// 2. **Insure the out-of-process panel.** Under App Sandbox a save/open panel
///    is hosted by the powerbox, not by us. It should inherit `NSApp.appearance`
///    like any other surface, but it's the one surface where that crosses a
///    process boundary — so `adoptHostAppearance()` states it explicitly rather
///    than trusting the inheritance.
@MainActor
enum PanelHost {
    /// The window a panel should attach to and match, or `nil` when there
    /// genuinely isn't one.
    static var window: NSWindow? {
        NSApp.keyWindow ?? NSApp.mainWindow
            ?? NSApp.windows.first { $0.isVisible && $0.canBecomeMain }
    }
}

extension NSSavePanel {
    /// Match the host window's appearance. `NSOpenPanel` inherits this — it's
    /// an `NSSavePanel` subclass.
    ///
    /// Call before presenting. Pass the host if you already resolved one for
    /// `beginSheetModal(for:)`; otherwise omit it and `PanelHost` resolves one.
    /// Falls back to the app's own appearance when there is no window at all —
    /// with no host there is nothing to be inconsistent *with*, and the app
    /// preference is still the right answer.
    @MainActor
    func adoptHostAppearance(_ host: NSWindow? = nil) {
        appearance = (host ?? PanelHost.window)?.effectiveAppearance ?? AppAppearance.current
    }
}
