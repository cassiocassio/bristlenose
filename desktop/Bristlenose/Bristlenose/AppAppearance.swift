import AppKit
import SwiftUI

/// The single owner of the app's light/dark appearance.
///
/// **Adding a window, panel, alert, menu, or popover? You need to do nothing.**
/// `NSApp.appearance` is set from the user's Settings ▸ Appearance preference at
/// launch and on every change, and every AppKit surface the app creates inherits
/// it. Reach for the members below only to *read* the preference — never to
/// re-apply it per surface.
///
/// Why this exists: the preference (Automatic / Light / Dark) can disagree with
/// the system's. Applying it per-window — `.preferredColorScheme` on a SwiftUI
/// scene, `window.appearance` on an AppKit one — leaves every surface that isn't
/// a window on the *system* theme, and obliges every new surface to remember to
/// opt in. Seven auxiliary `Window` scenes, the export save panel, and both
/// Locate panels had each missed it. `NSApp.appearance` is the one seam AppKit
/// offers that reaches all of them at once.
@MainActor
enum AppAppearance {
    /// UserDefaults key, shared with `AppearanceSettingsView`'s picker.
    ///
    /// The web report needs no separate channel: the WKWebView inherits its
    /// window's effective appearance and the report CSS follows
    /// `prefers-color-scheme`. See the note at `BridgeHandler.swift:234` — a
    /// bridge `set-appearance` message existed, was consumed by nothing, and
    /// was removed. Don't re-add one.
    static let defaultsKey = "appearance"

    // MARK: - Reading the preference

    /// Stored preference: `"auto"` (default), `"light"`, or `"dark"`.
    static var preference: String {
        UserDefaults.standard.string(forKey: defaultsKey) ?? "auto"
    }

    /// AppKit's spelling of the preference. `nil` means "follow the system",
    /// which is also what `NSApp.appearance = nil` means — the two line up
    /// deliberately, so `apply()` needs no special case for "auto".
    static func nsAppearance(for preference: String) -> NSAppearance? {
        switch preference {
        case "light": NSAppearance(named: .aqua)
        case "dark": NSAppearance(named: .darkAqua)
        default: nil
        }
    }

    /// SwiftUI's spelling of the same preference, for `.preferredColorScheme`.
    static func colorScheme(for preference: String) -> ColorScheme? {
        switch preference {
        case "light": .light
        case "dark": .dark
        default: nil
        }
    }

    /// The stored preference as an `NSAppearance`.
    static var current: NSAppearance? { nsAppearance(for: preference) }

    /// The stored preference as a `ColorScheme`.
    static var currentColorScheme: ColorScheme? { colorScheme(for: preference) }

    // MARK: - Applying it

    private static var observation: NSKeyValueObservation?

    /// Apply the preference app-wide and keep it applied. Called once, from
    /// `AppDelegate.applicationDidFinishLaunching`.
    ///
    /// Observing UserDefaults rather than hooking the Settings picker's
    /// `onChange` means any future writer of the key is covered without a
    /// second call site — which is the whole point of having one owner.
    static func beginApplying() {
        apply()
        observation = UserDefaults.standard.observe(\.appearance, options: [.new]) { _, _ in
            Task { @MainActor in AppAppearance.apply() }
        }
    }

    /// Push the preference onto `NSApp`. Idempotent.
    static func apply() {
        NSApp.appearance = current
    }
}

/// KVO on UserDefaults needs an `@objc dynamic` keypath, and UserDefaults only
/// emits change notifications for a property whose **name matches the defaults
/// key** — so this must stay spelled `appearance`.
extension UserDefaults {
    @objc dynamic var appearance: String? { string(forKey: AppAppearance.defaultsKey) }
}
