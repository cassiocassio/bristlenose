import Testing
import Foundation
@testable import Bristlenose

/// Pins the pure `OutlineTree.build` mapping — the AppKit sidebar's data-source
/// tree (spec §5 tree-mapping seam). Asserts output shape, not delegate calls.
@Suite struct OutlineNodeTests {
    private func project(_ name: String, folder: UUID? = nil, pos: Int = 0) -> Project {
        Project(id: UUID(), name: name, path: "/tmp/\(name)", folderId: folder, position: pos)
    }

    @Test func build_groupsLensesThenProjects() {
        let tree = OutlineTree.build(lenses: LensItem.all, projects: [], folders: [])
        #expect(tree.count == 2)
        #expect(tree[0].kind == .group("Lenses"))
        #expect(tree[0].children.count == LensItem.all.count)
        #expect(tree[1].kind == .group("Projects"))
    }

    @Test func build_noLensGroupWhenEmpty() {
        let tree = OutlineTree.build(lenses: [], projects: [], folders: [])
        #expect(tree.count == 1)
        #expect(tree[0].kind == .group("Projects"))
    }

    @Test func build_rootProjectsAndFoldersSortedByPosition() {
        let folder = Folder(id: UUID(), name: "F", position: 1)
        let p0 = project("A", pos: 0)
        let tree = OutlineTree.build(lenses: [], projects: [p0], folders: [folder])
        let projectsGroup = tree.first { $0.kind == .group("Projects") }!
        #expect(projectsGroup.children.map(\.kind) == [.project(p0.id), .folder(folder.id)])
    }

    @Test func build_folderDisclosesChildProjectsByPosition() {
        let folder = Folder(id: UUID(), name: "F", position: 0)
        let c0 = project("first", folder: folder.id, pos: 0)
        let c1 = project("second", folder: folder.id, pos: 1)
        let tree = OutlineTree.build(lenses: [], projects: [c1, c0], folders: [folder])
        let projectsGroup = tree.first { $0.kind == .group("Projects") }!
        let folderNode = projectsGroup.children.first { $0.kind == .folder(folder.id) }!
        #expect(folderNode.children.map(\.kind) == [.project(c0.id), .project(c1.id)])
        #expect(folderNode.children[0].parent === folderNode)
    }

    @Test func lensRows_areNotSelectable() {
        let tree = OutlineTree.build(lenses: LensItem.all, projects: [], folders: [])
        let lensGroup = tree[0]
        #expect(lensGroup.children.allSatisfy { !$0.isSelectable })
        #expect(lensGroup.children.allSatisfy { $0.selection == nil })
    }

    @Test func projectNode_mapsToSelection() {
        let p = project("A")
        let tree = OutlineTree.build(lenses: [], projects: [p], folders: [])
        let node = tree[0].children.first!
        #expect(node.selection == .project(p.id))
        #expect(node.isSelectable)
    }

    // MARK: - SidebarExternalDrop.resolve (Finder-import drop routing, review F34)

    @Test func externalDrop_nilKind_createsAtRoot() {
        #expect(SidebarExternalDrop.resolve(droppedOn: nil) == .root)
    }

    @Test func externalDrop_onProject_addsToThatProject() {
        let id = UUID()
        #expect(SidebarExternalDrop.resolve(droppedOn: .project(id)) == .project(id))
    }

    @Test func externalDrop_onFolder_createsInsideThatFolder() {
        let id = UUID()
        #expect(SidebarExternalDrop.resolve(droppedOn: .folder(id)) == .folder(id))
    }

    @Test func externalDrop_onProjectsGroup_createsAtRoot() {
        #expect(SidebarExternalDrop.resolve(droppedOn: .group(OutlineTree.projectsGroupKey)) == .root)
    }

    @Test func externalDrop_onLensesGroup_isRejected() {
        #expect(SidebarExternalDrop.resolve(droppedOn: .group(OutlineTree.lensesGroupKey)) == nil)
    }

    @Test func externalDrop_onLens_isRejected() {
        #expect(SidebarExternalDrop.resolve(droppedOn: .lens(.project)) == nil)
    }

    // MARK: - R56: rows redrawn around an open name field

    @Test func rowKinds_layOutOpenFoldersOnly() {
        let open = Folder(id: UUID(), name: "Open"), shut = Folder(id: UUID(), name: "Shut", collapsed: true)
        let a = project("A", folder: open.id), b = project("B", folder: shut.id)
        let tree = OutlineTree.build(lenses: [], projects: [a, b], folders: [open, shut])
        let rows = OutlineTree.rowKinds(tree) { node in
            node.kind == .folder(open.id)
        }
        #expect(rows.contains(.project(a.id)))
        #expect(!rows.contains(.project(b.id)), "a closed folder's study was laid out")
        #expect(rows.first == .group(OutlineTree.projectsGroupKey))
    }

    @Test func rowsToRefreshDuringRename_skipsOnlyTheEditedRow() {
        let a = UUID(), b = UUID()
        let next: [OutlineNode.Kind] = [.group("Projects"), .project(a), .project(b)]
        let rows = OutlineTree.rowsToRefreshDuringRename(displayed: next.map(Optional.some),
                                                         next: next, editing: a)
        #expect(rows == IndexSet([0, 2]))
    }

    @Test func rowsToRefreshDuringRename_waitsWhenTheRowsChange() {
        let a = UUID(), b = UUID()
        let shown: [OutlineNode.Kind?] = [.group("Projects"), .project(a)]
        #expect(OutlineTree.rowsToRefreshDuringRename(
            displayed: shown, next: [.group("Projects"), .project(b), .project(a)], editing: a) == nil)
        #expect(OutlineTree.rowsToRefreshDuringRename(
            displayed: shown, next: [.group("Projects"), .project(a)], editing: b) == nil,
                "no edited row to protect, so nothing may be redrawn")
    }
}
