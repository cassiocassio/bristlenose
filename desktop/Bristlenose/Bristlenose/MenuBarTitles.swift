import AppKit
import Combine
import OSLog

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

    /// The menu item itself, once found. Matching is the fragile part, so it is
    /// done as few times as possible: once at bind, and again only if a lookup
    /// later comes back empty.
    private var items: [String: NSMenuItem] = [:]

    /// The menu immediately after ours, and the only one guaranteed to read the
    /// same in every locale.
    private static let anchorTitle = "Diagnostics"
    private var observation: AnyCancellable?

    private static let log = Logger(subsystem: "app.bristlenose", category: "menubar")

    /// Call once at launch, after `i18n` is configured.
    func bind(to i18n: I18n) {
        guard observation == nil else { return }
        onScreen = Dictionary(uniqueKeysWithValues: Self.keys.map { ($0, i18n.t($0)) })
        locate()
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

    /// Locate the four menus, anchored on a title that never moves.
    ///
    /// **Not by matching our own titles.** The first version did, comparing
    /// `NSMenuItem.title` alone, found nothing and renamed nothing — silently —
    /// leaving a Polish menu bar in a Spanish app (screenshot, 21 Sep 2026). A
    /// menu-bar item carries its displayed text on the `NSMenu`, so an item
    /// wrapping a submenu can hold an empty `title`, and any match on a
    /// *translated* string is circular besides: it fails exactly when the
    /// language is the thing that changed.
    ///
    /// The anchor is `Diagnostics` — **ours, and English by decision** (
    /// App-Store-hidden chrome, `docs/design-i18n.md` §"Which surfaces are
    /// targets"), so it reads the same in all 22 locales. `MenuCommands`
    /// declares our four immediately before it, in `Self.keys` order, so the
    /// four items preceding it are exactly ours. Title matching stays as a
    /// fallback for the case where that layout changes.
    private func locate() {
        guard let mainMenu = NSApp.mainMenu else { return }
        guard Self.keys.contains(where: { items[$0] == nil }) else { return }

        let anchor = mainMenu.items.firstIndex {
            $0.title == Self.anchorTitle || $0.submenu?.title == Self.anchorTitle
        }
        if let anchor, anchor >= Self.keys.count {
            for (offset, key) in Self.keys.enumerated() {
                items[key] = mainMenu.items[anchor - Self.keys.count + offset]
            }
        } else {
            for key in Self.keys where items[key] == nil {
                guard let wanted = onScreen[key] else { continue }
                items[key] = mainMenu.items.first {
                    $0.title == wanted || $0.submenu?.title == wanted
                }
            }
        }

        let missing = Self.keys.filter { items[$0] == nil }
        if !missing.isEmpty {
            // Loud rather than silent: a miss means the menu bar stops following
            // the language and nothing else in the app will say so.
            Self.log.warning("""
                menu titles not located: \(missing.joined(separator: ", "), privacy: .public);                 anchor \(Self.anchorTitle, privacy: .public) at \(anchor.map(String.init) ?? "nil", privacy: .public);                 main menu: \(mainMenu.items.map { "\($0.title)|\($0.submenu?.title ?? "-")" }.joined(separator: ", "), privacy: .public)
                """)
        }
    }

    private func sync(with i18n: I18n) {
        locate()   // no-op for anything already held; retries anything that missed
        for key in Self.keys {
            let fresh = i18n.t(key)
            guard let current = onScreen[key], current != fresh else {
                onScreen[key] = fresh
                continue
            }
            guard let item = items[key] else {
                // Leave `onScreen` alone so the next attempt still hunts for the
                // title that IS on screen rather than one that never was.
                continue
            }
            item.title = fresh
            item.submenu?.title = fresh
            onScreen[key] = fresh
        }
    }
}
