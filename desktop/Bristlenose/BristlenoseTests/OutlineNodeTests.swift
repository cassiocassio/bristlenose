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
}
