import AppKit
import Foundation
import Testing
@testable import Bristlenose

/// A window drag republishes the sidebar on every frame (ContentView re-reads the
/// split widths), and each republish used to reload the outline, rebuilding every
/// visible row's cell. The sidebar holds still while ITS window is being resized
/// and reloads once when the drag ends (traced 3 Nov 2026: `viewFor` and the
/// table's layout were the biggest native cost of a drag).
@MainActor
@Suite("Sidebar live resize")
struct SidebarOutlineLiveResizeTests {

    @MainActor private final class Rig {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        let index: ProjectIndex
        let controller = SidebarOutlineController()
        let window: NSWindow

        init() {
            try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            index = ProjectIndex(fileURL: dir.appendingPathComponent("projects.json"))
            controller.projectIndex = index
            _ = controller.view
            controller.view.frame = NSRect(x: 0, y: 0, width: 240, height: 600)
            // Never shown: the live-resize observers are scoped to the window the
            // outline is in, so the outline has to be in one.
            window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 240, height: 600),
                              styleMask: [.titled, .resizable], backing: .buffered, defer: true)
            window.isReleasedWhenClosed = false
            window.contentView = controller.view
        }

        func publish() {
            controller.update(
                roots: OutlineTree.build(lenses: LensItem.all,
                                         projects: index.projects,
                                         folders: index.folders),
                selection: [], activeTab: nil, lensesEnabled: true)
        }

        func post(_ name: Notification.Name, from window: NSWindow? = nil) {
            NotificationCenter.default.post(name: name, object: window ?? self.window)
        }

        /// The cell on screen for a row. A reload builds new ones, so a changed
        /// identity is the proof the table was reloaded.
        func cell(row: Int) -> NSView? {
            controller.outlineView.view(atColumn: 0, row: row, makeIfNecessary: false)
        }

        func projectRow() -> Int {
            let outline = controller.outlineView
            return (0..<outline.numberOfRows).first {
                if case .project? = (outline.item(atRow: $0) as? OutlineNode)?.kind { return true }
                return false
            } ?? -1
        }

        func cleanup() { try? FileManager.default.removeItem(at: dir) }
    }

    @Test func aRepublishDuringALiveResizeDoesNotRebuildTheRows() {
        let rig = Rig(); defer { rig.cleanup() }
        _ = rig.index.addProject(name: "First", path: "")
        rig.publish()
        let row = rig.projectRow()
        #expect(row >= 0)
        let before = rig.cell(row: row)
        #expect(before != nil)

        rig.post(NSWindow.willStartLiveResizeNotification)
        for _ in 0..<5 { rig.publish() }

        #expect(rig.cell(row: row) === before, "rows were rebuilt mid-drag")
    }

    @Test func whatChangedDuringTheDragShowsWhenItEnds() {
        let rig = Rig(); defer { rig.cleanup() }
        _ = rig.index.addProject(name: "First", path: "")
        rig.publish()
        let rowsBefore = rig.controller.outlineView.numberOfRows
        let before = rig.cell(row: rig.projectRow())

        rig.post(NSWindow.willStartLiveResizeNotification)
        _ = rig.index.addProject(name: "Second", path: "")
        rig.publish()
        #expect(rig.controller.outlineView.numberOfRows == rowsBefore, "reloaded mid-drag")

        rig.post(NSWindow.didEndLiveResizeNotification)
        #expect(rig.controller.outlineView.numberOfRows == rowsBefore + 1,
                "a study added during the drag never appeared")
        #expect(rig.cell(row: rig.projectRow()) !== before)
    }

    @Test func aDragThatChangedNothingReloadsNothingAtTheEnd() {
        let rig = Rig(); defer { rig.cleanup() }
        _ = rig.index.addProject(name: "First", path: "")
        rig.publish()
        let before = rig.cell(row: rig.projectRow())

        rig.post(NSWindow.willStartLiveResizeNotification)
        rig.post(NSWindow.didEndLiveResizeNotification)

        #expect(rig.cell(row: rig.projectRow()) === before)
    }

    @Test func anotherWindowsDragDoesNotHoldThisSidebar() {
        let rig = Rig(); defer { rig.cleanup() }
        _ = rig.index.addProject(name: "First", path: "")
        rig.publish()
        let before = rig.cell(row: rig.projectRow())
        let other = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 100, height: 100),
                             styleMask: [.titled], backing: .buffered, defer: true)
        other.isReleasedWhenClosed = false

        rig.post(NSWindow.willStartLiveResizeNotification, from: other)
        rig.publish()

        #expect(rig.cell(row: rig.projectRow()) !== before, "another window's drag held this sidebar")
    }
}
