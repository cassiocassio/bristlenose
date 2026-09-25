import AppKit
import Combine
import Foundation
import Testing
@testable import Bristlenose

/// Drives the real `SidebarOutlineController` the way `ProjectSidebarOutline`'s
/// `updateNSViewController` does: a `ProjectIndex` on a temp file, the controller's
/// own `loadView`, and `update(roots:)` fed from `OutlineTree.build`. `publish()`
/// stands in for a SwiftUI republish — a selection change, a run's progress tick —
/// which in the app is exactly one `update()` → `reloadAndRestore()`.
@MainActor
private final class SidebarOutlineHarness {
    let tempDir: URL
    let fileURL: URL
    let index: ProjectIndex
    let controller = SidebarOutlineController()

    init(tempDir: URL? = nil) {
        let dir = tempDir ?? FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        self.tempDir = dir
        self.fileURL = dir.appendingPathComponent("projects.json")
        self.index = ProjectIndex(fileURL: fileURL)
        controller.projectIndex = index
        _ = controller.view
        controller.view.frame = NSRect(x: 0, y: 0, width: 240, height: 600)
    }

    var outlineView: NSOutlineView { controller.outlineView }

    func publish(selection: Set<SidebarSelection> = []) {
        controller.update(
            roots: OutlineTree.build(lenses: LensItem.all,
                                     projects: index.projects,
                                     folders: index.folders),
            selection: selection,
            activeTab: nil,
            lensesEnabled: true
        )
    }

    /// A folder holding one project, so it is expandable.
    @discardableResult
    func seedFolder(_ name: String) -> UUID {
        let folder = index.addFolder(name: name)
        index.addProject(name: "\(name) study", path: "", intoFolder: folder.id)
        return folder.id
    }

    /// The node currently on screen for a folder. Every `publish()` builds fresh
    /// nodes, so this must be re-read after each one.
    func node(_ folderID: UUID) -> OutlineNode {
        for row in 0..<outlineView.numberOfRows {
            if let node = outlineView.item(atRow: row) as? OutlineNode,
               node.kind == .folder(folderID) { return node }
        }
        fatalError("folder \(folderID) not in the outline")
    }

    func isExpanded(_ folderID: UUID) -> Bool { outlineView.isItemExpanded(node(folderID)) }
    func modelCollapsed(_ folderID: UUID) -> Bool? {
        index.folders.first { $0.id == folderID }?.collapsed
    }

    func cleanup() { try? FileManager.default.removeItem(at: tempDir) }
}

/// A collapsed folder must stay collapsed across the sidebar's own reloads.
/// Regression: the AppKit outline read `Folder.collapsed` on every reload but never
/// wrote it, so a triangle click collapsed the view only and the next republish —
/// selecting a root project — sprang every folder open again.
@MainActor
@Suite("Sidebar folder expansion")
struct SidebarOutlineExpansionTests {

    @Test func collapse_survivesRepublish() {
        let h = SidebarOutlineHarness()
        defer { h.cleanup() }
        let a = h.seedFolder("A")
        let b = h.seedFolder("B")
        h.publish()
        #expect(h.isExpanded(a) && h.isExpanded(b))

        // `collapseItem` posts the same `…DidCollapse` a triangle click, ← or ⌥-click does.
        h.outlineView.collapseItem(h.node(a))
        h.publish()

        #expect(!h.isExpanded(a))
        #expect(h.isExpanded(b))
        #expect(h.modelCollapsed(a) == true)
        #expect(h.modelCollapsed(b) == false)
    }

    @Test func expand_survivesRepublish() {
        let h = SidebarOutlineHarness()
        defer { h.cleanup() }
        let a = h.seedFolder("A")
        h.index.setFolderCollapsed(id: a, collapsed: true)
        h.publish()
        #expect(!h.isExpanded(a))

        h.outlineView.expandItem(h.node(a))
        h.publish()

        #expect(h.isExpanded(a))
        #expect(h.modelCollapsed(a) == false)
    }

    /// The relaunch case: a new index and controller over the same `projects.json`.
    @Test func collapse_survivesRelaunch() {
        let first = SidebarOutlineHarness()
        defer { first.cleanup() }
        let a = first.seedFolder("A")
        first.publish()
        first.outlineView.collapseItem(first.node(a))

        let second = SidebarOutlineHarness(tempDir: first.tempDir)
        second.publish()
        #expect(!second.isExpanded(a))
    }

    /// A republish restores expansion; it must never write it — a write would save,
    /// republish and reload again. An ordinary republish expands nothing (nodes are
    /// equal by model id, so `reloadData` keeps expansion); the restore only acts
    /// when the model leads the view, as a Finder drop onto a collapsed folder does
    /// (`handleDropOnFolder` → `setFolderCollapsed(false)`).
    @Test func modelLedExpand_republishWritesNothing() {
        let h = SidebarOutlineHarness()
        defer { h.cleanup() }
        let a = h.seedFolder("A")
        h.publish()
        h.outlineView.collapseItem(h.node(a))
        h.index.setFolderCollapsed(id: a, collapsed: false)   // the drop path

        var changes = 0
        let sink = h.index.objectWillChange.sink { changes += 1 }
        defer { sink.cancel() }
        h.publish()

        #expect(h.isExpanded(a))
        #expect(changes == 0)
    }
}
