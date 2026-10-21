import AppKit
import Testing
@testable import Bristlenose

/// Right-click ▸ Reload Report in the report (owner, 20 Oct 2026): the remedy the
/// broken mark asks for. WebKit builds the real menu in another process, so the
/// edit is tested on menus built here.
@MainActor
@Suite("Report context menu")
struct ReportContextMenuTests {
    private final class Target: NSObject {
        @objc func reload(_ sender: Any?) {}
    }

    private func item(_ title: String, _ id: String? = nil) -> NSMenuItem {
        let i = NSMenuItem(title: title, action: nil, keyEquivalent: "")
        if let id { i.identifier = NSUserInterfaceItemIdentifier(id) }
        return i
    }

    private func add(to menu: NSMenu, _ target: Target) {
        ReportContextMenu.addReload(
            to: menu, title: "Reload Report", target: target, action: #selector(Target.reload(_:)))
    }

    @Test func takesThePlaceOfWebKitsOwnReload() {
        let menu = NSMenu()
        menu.addItem(item("Back", "WKMenuItemIdentifierGoBack"))
        menu.addItem(item("Reload", "WKMenuItemIdentifierReload"))
        menu.addItem(item("Inspect Element"))
        let target = Target()
        add(to: menu, target)

        #expect(menu.items.map(\.title) == ["Back", "Reload Report", "Inspect Element"])
        let ours = menu.items[1]
        #expect(ours.identifier == ReportContextMenu.reloadReport)
        #expect(ours.target === target)
        #expect(ours.action == #selector(Target.reload(_:)))
    }

    @Test func isAppendedAfterASeparatorWhenWebKitOffersNone() {
        let menu = NSMenu()
        menu.addItem(item("Copy"))
        add(to: menu, Target())

        #expect(menu.items.count == 3)
        #expect(menu.items[1].isSeparatorItem)
        #expect(menu.items[2].title == "Reload Report")
    }

    @Test func anEmptyMenuGetsNoLeadingSeparator() {
        let menu = NSMenu()
        add(to: menu, Target())
        #expect(menu.items.map(\.title) == ["Reload Report"])
    }

    @Test func isAddedOnce() {
        let menu = NSMenu()
        menu.addItem(item("Copy"))
        let target = Target()
        add(to: menu, target)
        add(to: menu, target)
        #expect(menu.items.filter { $0.identifier == ReportContextMenu.reloadReport }.count == 1)
    }

    @Test func isWithheldWhileTextIsBeingEdited() {
        #expect(ReportContextMenu.offersReload(isEditing: false))
        #expect(!ReportContextMenu.offersReload(isEditing: true))
    }

    /// WebKit's own Reload would drop the typed words just as ours would, so
    /// while editing it goes too, and nothing takes its place.
    @Test func whileEditingWebKitsReloadGoesAndOursIsNotAdded() {
        let menu = NSMenu()
        menu.addItem(item("Cut"))
        menu.addItem(item("Reload", "WKMenuItemIdentifierReload"))
        ReportContextMenu.apply(
            to: menu, isEditing: true, title: "Reload Report", target: Target(),
            action: #selector(Target.reload(_:)))
        #expect(menu.items.map(\.title) == ["Cut"])
    }

    @Test func whenNotEditingApplyAddsOurs() {
        let menu = NSMenu()
        menu.addItem(item("Reload", "WKMenuItemIdentifierReload"))
        ReportContextMenu.apply(
            to: menu, isEditing: false, title: "Reload Report", target: Target(),
            action: #selector(Target.reload(_:)))
        #expect(menu.items.map(\.title) == ["Reload Report"])
    }
}
