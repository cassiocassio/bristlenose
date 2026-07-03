import Foundation

/// In-progress feature flags, read from `UserDefaults` so they can be flipped
/// without a rebuild: `defaults write app.bristlenose <key> -bool YES`.
enum BristlenoseFlags {
    /// Render the native AppKit `NSOutlineView` source-list sidebar instead of the
    /// SwiftUI `List`. **Default off** (SwiftUI is the shipping sidebar). The AppKit
    /// sidebar is the in-progress framework migration — see
    /// `docs/design-desktop-sidebar-appkit.md`. Flip with:
    /// `defaults write app.bristlenose BristlenoseAppKitSidebar -bool YES`
    static var appKitSidebar: Bool {
        UserDefaults.standard.bool(forKey: "BristlenoseAppKitSidebar")
    }

    /// SPIKE: run the typographic shoal behind the translucent AppKit sidebar,
    /// Maps-style (`.withinWindow` NSVisualEffectView frosting an SKView). **Default
    /// off.** Answers one empirical unknown — does vibrancy sample a Metal-backed
    /// SKView? Requires the AppKit sidebar too. Flip with:
    /// `defaults write app.bristlenose BristlenoseShoalSidebar -bool YES`.
    /// Design: `docs/private/design-shoal-ambient-future.md` §C.
    static var shoalSidebar: Bool {
        UserDefaults.standard.bool(forKey: "BristlenoseShoalSidebar")
    }
}
