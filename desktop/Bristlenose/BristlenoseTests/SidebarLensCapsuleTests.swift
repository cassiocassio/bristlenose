import AppKit
import Foundation
import Testing
@testable import Bristlenose

/// A lens row has no selection of its own: its capsule is composed from `activeTab`,
/// so it moves only when the sidebar re-applies its selection after the route lands.
/// A project row is selected by the click itself, which is why a project click moved
/// the sidebar at once while a lens click left the capsule on the old lens until the
/// lens was clicked a second time (reported 11 Nov 2026).
///
/// These tests pin the half that does not need a mouse: whatever `update()` does with
/// the reload, the capsule has to land on the lens the report is showing.
@MainActor
@Suite("Sidebar lens capsule", .serialized)
struct SidebarLensCapsuleTests {

    @MainActor private final class Rig {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        let index: ProjectIndex
        let controller = SidebarOutlineController()
        let window: NSWindow
        var selection: Set<SidebarSelection> = []

        init() {
            try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            index = ProjectIndex(fileURL: dir.appendingPathComponent("projects.json"))
            controller.projectIndex = index
            _ = controller.view
            controller.view.frame = NSRect(x: 0, y: 0, width: 260, height: 600)
            window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 260, height: 600),
                              styleMask: [.titled, .resizable], backing: .buffered, defer: true)
            window.isReleasedWhenClosed = false
            window.contentView = controller.view
            _ = index.addProject(name: "First", path: "")
            if let first = index.projects.first { selection = [.project(first.id)] }
        }

        /// What `ContentView` hands the outline each time its body runs.
        func publish(activeTab: Tab?) {
            controller.update(
                roots: OutlineTree.build(lenses: LensItem.all,
                                         projects: index.projects,
                                         folders: index.folders),
                selection: selection, activeTab: activeTab, lensesEnabled: true)
        }

        /// The lens rows the table has drawn as selected.
        var capsules: [Tab] {
            let outline = controller.outlineView
            return outline.selectedRowIndexes.compactMap {
                if case .lens(let t)? = (outline.item(atRow: $0) as? OutlineNode)?.kind { return t }
                return nil
            }
        }

        var projectIsSelected: Bool {
            let outline = controller.outlineView
            return outline.selectedRowIndexes.contains {
                if case .project? = (outline.item(atRow: $0) as? OutlineNode)?.kind { return true }
                return false
            }
        }

        func cleanup() { try? FileManager.default.removeItem(at: dir) }
    }

    @Test func theCapsuleMovesWhenTheActiveLensChanges() {
        let rig = Rig(); defer { rig.cleanup() }
        rig.publish(activeTab: .project)
        #expect(rig.capsules == [.project])
        rig.publish(activeTab: .quotes)
        #expect(rig.capsules == [.quotes])
        #expect(rig.projectIsSelected, "the project selection was dropped")
    }

    /// A window drag holds the reload back (`update()` stores the new tree and returns).
    /// The capsule must still follow the lens, and the project must stay selected.
    @Test func theCapsuleMovesWhileALiveResizeHoldsTheReload() {
        let rig = Rig(); defer { rig.cleanup() }
        rig.publish(activeTab: .project)
        NotificationCenter.default.post(name: NSWindow.willStartLiveResizeNotification, object: rig.window)
        rig.publish(activeTab: .quotes)
        #expect(rig.capsules == [.quotes], "capsule is on \(rig.capsules)")
        #expect(rig.projectIsSelected, "the project selection was dropped")
    }

    /// R57's in-place refresh (the Debug row-height switch) redraws rows without a reload, and
    /// `applySelection` is part of the reload. A lens click changes only `activeTab`, so with the
    /// switch on the capsule stayed on the old lens (traced 11 Nov 2026, the click after the
    /// route landed ran `update()` and nothing re-applied the capsule).
    @Test func theCapsuleMovesWhenRowsAreRefreshedInPlace() {
        let key = "BristlenoseAnimateSidebarRowHeight"
        let before = UserDefaults.standard.object(forKey: key)
        UserDefaults.standard.set(true, forKey: key)
        defer {
            if let before { UserDefaults.standard.set(before, forKey: key) }
            else { UserDefaults.standard.removeObject(forKey: key) }
        }
        let rig = Rig(); defer { rig.cleanup() }
        // A new project's icon reveal is a one-shot that forces the full reload; clear it so the
        // update is the in-place kind.
        rig.index.pendingIconReveal = nil
        rig.index.pendingRename = nil
        rig.publish(activeTab: .project)
        rig.publish(activeTab: .quotes)
        #expect(rig.capsules == [.quotes], "capsule is on \(rig.capsules)")
        #expect(rig.projectIsSelected, "the project selection was dropped")
    }
}
