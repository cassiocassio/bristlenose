import AppKit
import Foundation
import SwiftUI
import Testing

@testable import Bristlenose

/// Pins the one seam the whole app's light/dark behaviour hangs off.
///
/// `AppAppearance` sets `NSApp.appearance` from the Settings preference, and
/// every window, panel, alert, menu and popover inherits it. Two things can
/// break that silently, and neither shows up in a build:
///
/// 1. The two spellings of the preference (`NSAppearance` for AppKit,
///    `ColorScheme` for SwiftUI) drifting apart — someone edits one `switch`
///    and not the other, and the chrome disagrees with the content.
/// 2. The UserDefaults KVO not firing — the preference would apply at launch
///    and then never again, so changing it in Settings appears to do nothing
///    until relaunch. That is the dangerous one: it looks like a working app.
///
/// Deliberately NOT tested: that a given window/panel actually renders dark.
/// That's a rendering fact, not a logic one — it needs the human QA pass
/// described in `desktop/CLAUDE.md` §Appearance (set the app preference
/// opposite to System Settings and open one of each surface).
@MainActor @Suite struct AppAppearanceTests {

    // MARK: - Mapping

    @Test func lightMapsToAqua() {
        #expect(AppAppearance.nsAppearance(for: "light")?.name == .aqua)
        #expect(AppAppearance.colorScheme(for: "light") == .light)
    }

    @Test func darkMapsToDarkAqua() {
        #expect(AppAppearance.nsAppearance(for: "dark")?.name == .darkAqua)
        #expect(AppAppearance.colorScheme(for: "dark") == .dark)
    }

    /// `nil` is "follow the system" in both spellings — and is also what
    /// `NSApp.appearance = nil` means, which is why `apply()` needs no `auto`
    /// case. If this ever stops being true, `apply()` needs one.
    @Test func autoMapsToNilInBothSpellings() {
        #expect(AppAppearance.nsAppearance(for: "auto") == nil)
        #expect(AppAppearance.colorScheme(for: "auto") == nil)
    }

    /// An unrecognised value must fall back to "follow the system", never to a
    /// forced appearance — a corrupt or future-versioned default should leave
    /// the user on the OS setting, not pin them to light.
    @Test func unknownPreferenceFollowsSystem() {
        for junk in ["", "Dark", "sepia", "true", "0"] {
            #expect(AppAppearance.nsAppearance(for: junk) == nil, "\(junk) should follow system")
            #expect(AppAppearance.colorScheme(for: junk) == nil, "\(junk) should follow system")
        }
    }

    /// The two spellings must never disagree about *which* appearance, only
    /// about how to say it. Catches an edit to one `switch` and not the other.
    @Test func bothSpellingsAgreeForEveryPreference() {
        for pref in ["auto", "light", "dark", "nonsense"] {
            let appkit = AppAppearance.nsAppearance(for: pref)
            let swiftUI = AppAppearance.colorScheme(for: pref)
            #expect((appkit == nil) == (swiftUI == nil), "\(pref): one forces, the other doesn't")
            if let appkit, let swiftUI {
                let appkitIsDark = appkit.name == .darkAqua
                #expect(appkitIsDark == (swiftUI == .dark), "\(pref): opposite polarity")
            }
        }
    }

    // MARK: - Live application

    /// The KVO idiom this whole feature rests on: UserDefaults only emits
    /// change notifications for a property whose **name matches the defaults
    /// key**, so `UserDefaults.appearance` must stay spelled `appearance`.
    /// Rename it and the observation goes quiet — the preference would apply
    /// at launch and never again, with no error anywhere.
    @Test func changingTheDefaultFiresKVO() async throws {
        let defaults = UserDefaults.standard
        let original = defaults.string(forKey: AppAppearance.defaultsKey)
        defer {
            if let original {
                defaults.set(original, forKey: AppAppearance.defaultsKey)
            } else {
                defaults.removeObject(forKey: AppAppearance.defaultsKey)
            }
        }

        // Start from a known value so the write below is a genuine change.
        defaults.set("auto", forKey: AppAppearance.defaultsKey)

        final class Box: @unchecked Sendable {
            var observed: [String?] = []
        }
        let box = Box()
        let observation = defaults.observe(\.appearance, options: [.new]) { _, change in
            box.observed.append(change.newValue ?? nil)
        }
        defer { observation.invalidate() }

        defaults.set("dark", forKey: AppAppearance.defaultsKey)
        // KVO on UserDefaults is synchronous on the writing thread, but yield
        // once so a coalesced delivery can't flake the assertion.
        await Task.yield()

        #expect(box.observed.contains("dark"), "KVO never fired — is the property still named `appearance`?")
    }

    /// `apply()` must push the *stored* preference, not a cached or default
    /// one. Restores whatever the developer's own appearance was.
    @Test func applyPushesStoredPreferenceOntoNSApp() {
        let defaults = UserDefaults.standard
        let originalPref = defaults.string(forKey: AppAppearance.defaultsKey)
        let originalAppearance = NSApp.appearance
        defer {
            if let originalPref {
                defaults.set(originalPref, forKey: AppAppearance.defaultsKey)
            } else {
                defaults.removeObject(forKey: AppAppearance.defaultsKey)
            }
            NSApp.appearance = originalAppearance
        }

        defaults.set("dark", forKey: AppAppearance.defaultsKey)
        AppAppearance.apply()
        #expect(NSApp.appearance?.name == .darkAqua)

        defaults.set("light", forKey: AppAppearance.defaultsKey)
        AppAppearance.apply()
        #expect(NSApp.appearance?.name == .aqua)

        // "auto" must *clear* the override, not leave the previous force in
        // place — otherwise switching back to Automatic would silently stick.
        defaults.set("auto", forKey: AppAppearance.defaultsKey)
        AppAppearance.apply()
        #expect(NSApp.appearance == nil)
    }
}
