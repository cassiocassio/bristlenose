import AppKit
import Testing
@testable import Bristlenose

/// Which view counts as "on the sidebar list" for the empty-space deselect. A click on something
/// drawn over the list must not clear the selection (Send Feedback sits inside the table's bounds
/// on macOS 26), and the table's own ancestors are not the list.
@MainActor
@Suite("Sidebar click target")
struct SidebarClickTargetTests {

    private struct Rig {
        let container = NSView(frame: NSRect(x: 0, y: 0, width: 240, height: 400))
        let scroll = NSScrollView(frame: NSRect(x: 0, y: 0, width: 240, height: 400))
        let outline = NSOutlineView(frame: NSRect(x: 0, y: 0, width: 240, height: 400))
        let cell = NSTextField(labelWithString: "row")
        let overlay = NSButton(title: "Send Feedback", target: nil, action: nil)

        init() {
            outline.addTableColumn(NSTableColumn(identifier: NSUserInterfaceItemIdentifier("c")))
            outline.addSubview(cell)
            scroll.documentView = outline
            container.addSubview(scroll)
            container.addSubview(overlay)   // a sibling drawn over the list, not inside it
        }
    }

    @Test func theTableItselfCounts() {
        let rig = Rig()
        #expect(SidebarClickTarget.enclosingTableView(of: rig.outline) === rig.outline)
    }

    @Test func aViewInsideTheTableCounts() {
        let rig = Rig()
        #expect(SidebarClickTarget.enclosingTableView(of: rig.cell) === rig.outline)
    }

    @Test func theTablesClipViewAndScrollViewDoNot() throws {
        let rig = Rig()
        let clip = try #require(rig.scroll.contentView as NSView?)
        #expect(SidebarClickTarget.enclosingTableView(of: clip) == nil)
        #expect(SidebarClickTarget.enclosingTableView(of: rig.scroll) == nil)
    }

    @Test func aButtonDrawnOverTheListDoesNotCount() {
        let rig = Rig()
        #expect(SidebarClickTarget.enclosingTableView(of: rig.overlay) == nil)
    }

    @Test func aViewWithNoTableAtAllDoesNotCount() {
        #expect(SidebarClickTarget.enclosingTableView(of: NSView()) == nil)
    }
}
