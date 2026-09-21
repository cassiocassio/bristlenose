import AppKit
import Combine

/// Keeps the four Bristlenose menu-bar titles in the app's language.
///
/// **Why AppKit and not SwiftUI.** `CommandMenu` takes its title as a
/// `LocalizedStringKey`, and `MenuCommands` resolves it through `i18n.t` so it
/// renders translated — but SwiftUI installs the menu *once*, when the scene is
/// set up. The items inside re-render (they are `View`s); the `NSMenu`'s own
/// title does not. So before this type, changing language left the menu bar
/// frozen at whatever locale the app launched in: a Spanish app with a Polish
/// menu bar, seen on screen 21 Sep 2026.
///
/// This is `docs/i18n-defects.md` failure class 6 — key present, value
/// correctly translated, `i18n.t` called, and still wrong because of *when* the
/// call ran — in its second form. The first was `SettingsView`'s `lazy var`,
/// where we owned the construction and could rebuild it. Here the construction
/// belongs to SwiftUI, so the only seam is the `NSMenu` it produced.
///
/// **Diagnostics is deliberately absent**: App-Store-hidden chrome, English by
/// `docs/design-i18n.md` §"Which surfaces are targets". So are File / Edit /
/// View / Window / Help, which are AppKit's own and English for an unrelated
/// reason (`knownRegions = (en, Base)`, no `.lproj` shipped) that renaming
/// items here must not paper over.
@MainActor
final class MenuBarTitles {
    static let shared = MenuBarTitles()
    private init() {}

    /// Must match the `CommandMenu` titles in `MenuCommands.CustomMenus`.
    /// Pinned by `tests/test_menu_title_keys.py`, which fails if either side
    /// stops naming a key the other uses.
    private static let keys = [
        "common.nav.project",
        "desktop.toolbar.codes",
        "common.nav.quotes",
        "desktop.menu.video.title",
    ]

    /// The title we believe is on screen for each key — which is how the menu
    /// is *found*, since SwiftUI gives us no identifier to match on. Seeded at
    /// launch from the same `i18n.t` calls SwiftUI used, so the two agree.
    private var onScreen: [String: String] = [:]
    private var observation: AnyCancellable?

    /// Call once at launch, after `i18n` is configured.
    func bind(to i18n: I18n) {
        guard observation == nil else { return }
        onScreen = Dictionary(uniqueKeysWithValues: Self.keys.map { ($0, i18n.t($0)) })
        observation = i18n.$locale
            .dropFirst()   // `@Published` replays on subscribe
            .removeDuplicates()
            .sink { [weak self, weak i18n] _ in
                // A tick, so SwiftUI has finished whatever it does with the
                // menu on this change before we rename what it left behind.
                DispatchQueue.main.async {
                    guard let i18n else { return }
                    self?.sync(with: i18n)
                }
            }
    }

    private func sync(with i18n: I18n) {
        guard let mainMenu = NSApp.mainMenu else { return }
        for key in Self.keys {
            let fresh = i18n.t(key)
            guard let current = onScreen[key] else {
                onScreen[key] = fresh
                continue
            }
            if current == fresh { continue }
            // Not found means SwiftUI rebuilt the menu after all, or something
            // renamed it. Leave `onScreen` alone so the next change hunts for
            // the title that IS there rather than one that never was.
            guard let item = mainMenu.items.first(where: { $0.title == current }) else { continue }
            item.title = fresh
            item.submenu?.title = fresh
            onScreen[key] = fresh
        }
    }
}
