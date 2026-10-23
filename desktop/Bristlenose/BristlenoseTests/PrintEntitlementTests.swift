#if DEBUG
import AppKit
import Security
import Testing
@testable import Bristlenose

/// Printing is post-v1: no print entitlement, no Print item, no ⌘P.
///
/// R69 (21 Oct 2026) turned on `com.apple.security.print` so File ▸ Print would
/// open the print panel instead of the sandbox's "This application does not
/// support printing". The owner withdrew printing for v1 on 23 Oct 2026, because
/// what prints is not a deliverable (`docs/design-printing.md`). File ▸ Print and
/// Page Setup came out of the menus and the entitlement went off with them; these
/// tests hold both out, so neither can creep back on its own.
///
/// Tests run the Debug configuration only; `tests/test_entitlements_split.py`
/// pins the build setting for Release, which is what ships, and the artefact
/// gates (`check-pkg-shippable.sh`, `check-dmg-shippable.sh`) read the signed
/// app. **On CI the entitlement test is vacuous:** CI builds unsigned, so the
/// host carries no entitlements at all. The menu tests hold everywhere.
@MainActor
@Suite("Printing is post-v1")
struct PrintEntitlementTests {

    private static func entitlement(_ key: String) -> Bool {
        guard let task = SecTaskCreateFromSelf(nil),
              let value = SecTaskCopyValueForEntitlement(task, key as CFString, nil)
        else { return false }
        return (value as? Bool) == true
    }

    private static func allItems(_ menu: NSMenu) -> [NSMenuItem] {
        menu.items.flatMap { [$0] + ($0.submenu.map(allItems) ?? []) }
    }

    @Test func theHostDoesNotCarryThePrintEntitlement() {
        #expect(!Self.entitlement("com.apple.security.print"),
                "com.apple.security.print is back — printing is post-v1; set ENABLE_RESOURCE_ACCESS_PRINTING = NO")
    }

    /// No item answers ⌘P: not ours, and not a SwiftUI default print group
    /// standing in once ours is gone.
    @Test func noMenuItemTakesCommandP() throws {
        let menu = try Self.appMenu()
        let commandP = Self.allItems(menu).filter {
            $0.keyEquivalent == "p" && $0.keyEquivalentModifierMask == .command
        }
        #expect(commandP.isEmpty, "⌘P is bound to \(commandP.map(\.title)) — printing is post-v1")
    }

    /// Nor a Print or Page Setup item without the shortcut: by AppKit's print
    /// actions (a SwiftUI default print group would use them), and by our own
    /// titles in every bundled locale, since the test host's menu is built in
    /// whatever language the app was last left in.
    @Test func noMenuItemPrintsOrSetsUpThePage() throws {
        let menu = try Self.appMenu()
        let items = Self.allItems(menu)
        let printing: Set<Selector> = [
            NSSelectorFromString("print:"),
            NSSelectorFromString("printDocument:"),
            NSSelectorFromString("runPageLayout:"),
        ]
        let byAction = items.filter { $0.action.map(printing.contains) ?? false }
        #expect(byAction.isEmpty, "menu items with a print action: \(byAction.map(\.title))")

        let titles = try Self.fileMenuTitlesInEveryLocale(["print", "pageSetup"])
        try #require(titles.contains("Print…") && titles.contains("Page Setup…"),
                     "the bundled locales were not read, so the title check would pass on nothing")
        let byTitle = items.filter { titles.contains($0.title) }
        #expect(byTitle.isEmpty, "menu items titled \(byTitle.map(\.title))")
    }

    /// The app's own menu bar, proved by its File ▸ Export Report… item, in
    /// whatever language the host is in. Without this both menu tests are pure
    /// absence checks and would pass on a stock menu, or none.
    private static func appMenu() throws -> NSMenu {
        let menu = try #require(NSApp.mainMenu)
        let export = try fileMenuTitlesInEveryLocale(["exportReport"])
        try #require(allItems(menu).contains { export.contains($0.title) },
                     "File ▸ Export Report… is not in the menu bar, so this is not the app's menu")
        return menu
    }

    /// `desktop.menu.file.<key>` for each key, from every bundled locale.
    /// The print keys are kept for when printing is designed, which is what
    /// makes the title check possible.
    ///
    /// `findLocalesDirectory()` rather than fixtures, against the testing
    /// convention, on purpose: the menu is built from the shipped locales, so
    /// those are what the titles must be compared with.
    private static func fileMenuTitlesInEveryLocale(_ keys: [String]) throws -> Set<String> {
        let dir = try #require(I18n.findLocalesDirectory())
        var titles: Set<String> = []
        for locale in try FileManager.default.contentsOfDirectory(atPath: dir.path) {
            let file = dir.appendingPathComponent(locale).appendingPathComponent("desktop.json")
            guard let data = try? Data(contentsOf: file),
                  let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let fileMenu = (root["menu"] as? [String: Any])?["file"] as? [String: Any]
            else { continue }
            for key in keys {
                if let title = fileMenu[key] as? String { titles.insert(title) }
            }
        }
        return titles
    }
}
#endif
