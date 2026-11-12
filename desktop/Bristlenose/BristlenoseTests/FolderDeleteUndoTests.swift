import Testing
import Foundation
@testable import Bristlenose

/// Delete Folder is undoable (R54, owner ruling 12 Nov 2026): instant, no confirm,
/// and Edit ▸ Undo puts the folder back with its studies, in their old order and at
/// their old place in the sidebar. Sibling to the `deleteFolder_…` tests in
/// `ProjectIndexDropTests`, which pin what the delete itself does.
@MainActor
@Suite("Folder delete undo")
struct FolderDeleteUndoTests {

    private static func makeStore() -> (UndoableRemovalStore, ProjectIndex, URL) {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("FolderDeleteUndoTests-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let index = ProjectIndex(fileURL: dir.appendingPathComponent("projects.json"))
        let store = UndoableRemovalStore()
        store.setProjectIndex(index)
        return (store, index, dir)
    }

    /// Root `A, F[X Y Z], B, C`, the layout the drop tests use.
    private static func seed(_ index: ProjectIndex) -> Folder {
        for name in ["A", "B", "C"].reversed() {
            index.addProject(name: name, path: "/tmp/\(name)")
        }
        return addFolder(index, "F", holding: ["X", "Y", "Z"], atRootIndex: 2)
    }

    private static func addFolder(_ index: ProjectIndex, _ name: String, holding: [String],
                                  atRootIndex at: Int) -> Folder {
        let folder = index.addFolder(name: name)
        for title in holding.reversed() {
            index.addProject(name: title, path: "/tmp/\(title)", intoFolder: folder.id)
        }
        index.apply(DropPlan(items: [.folder(folder.id)], toFolder: nil, atIndex: at))
        return folder
    }

    private static func rootNames(_ index: ProjectIndex) -> [String] {
        index.sidebarItems.map { item in
            switch item {
            case .project(let p): p.name
            case .folder(let f): f.name
            }
        }
    }

    private static func names(in folder: UUID, _ index: ProjectIndex) -> [String] {
        index.projectsInFolder(folder).map(\.name)
    }

    @Test func undoPutsTheFolderBackWithItsStudiesInOrderAndInPlace() {
        let (store, index, dir) = Self.makeStore()
        defer { try? FileManager.default.removeItem(at: dir) }
        let folder = Self.seed(index)
        #expect(Self.rootNames(index) == ["A", "F", "B", "C"])

        store.deleteFolders([folder.id])
        #expect(Self.rootNames(index) == ["A", "X", "Y", "Z", "B", "C"])
        #expect(store.hasPending)

        store.undoLastRemoval()

        #expect(Self.rootNames(index) == ["A", "F", "B", "C"])
        #expect(Self.names(in: folder.id, index) == ["X", "Y", "Z"])
        #expect(index.sidebarItems.map(\.position) == Array(0..<4))
        #expect(!store.hasPending)
    }

    @Test func undoKeepsTheFoldersOwnState() {
        let (store, index, dir) = Self.makeStore()
        defer { try? FileManager.default.removeItem(at: dir) }
        let folder = Self.seed(index)
        index.setFolderCollapsed(id: folder.id, collapsed: true)

        store.deleteFolders([folder.id])
        store.undoLastRemoval()

        let back = index.folders.first { $0.id == folder.id }
        #expect(back?.name == "F")
        #expect(back?.collapsed == true)
        #expect(back?.createdAt == folder.createdAt)
    }

    @Test func severalFoldersComeBackTogetherEachInItsPlace() {
        let (store, index, dir) = Self.makeStore()
        defer { try? FileManager.default.removeItem(at: dir) }
        let first = Self.seed(index)
        let second = Self.addFolder(index, "G", holding: ["P", "Q"],
                                    atRootIndex: DropRouting.append)
        #expect(Self.rootNames(index) == ["A", "F", "B", "C", "G"])

        store.deleteFolders([first.id, second.id])
        #expect(Self.rootNames(index) == ["A", "X", "Y", "Z", "B", "C", "P", "Q"])
        #expect(store.pendingFolderCount == 2)
        #expect(store.pendingFolderName == nil)

        store.undoLastRemoval()

        #expect(Self.rootNames(index) == ["A", "F", "B", "C", "G"])
        #expect(Self.names(in: first.id, index) == ["X", "Y", "Z"])
        #expect(Self.names(in: second.id, index) == ["P", "Q"])
    }

    @Test func aStudyMovedElsewhereMeanwhileStaysThere() {
        let (store, index, dir) = Self.makeStore()
        defer { try? FileManager.default.removeItem(at: dir) }
        let folder = Self.seed(index)
        let other = index.addFolder(name: "Other")
        store.deleteFolders([folder.id])
        let y = index.projects.first { $0.name == "Y" }!
        index.moveProject(projectId: y.id, toFolder: other.id)

        store.undoLastRemoval()

        #expect(Self.names(in: folder.id, index) == ["X", "Z"])
        #expect(Self.names(in: other.id, index) == ["Y"])
    }

    @Test func aStudyRemovedMeanwhileDoesNotComeBack() {
        let (store, index, dir) = Self.makeStore()
        defer { try? FileManager.default.removeItem(at: dir) }
        let folder = Self.seed(index)
        store.deleteFolders([folder.id])
        let y = index.projects.first { $0.name == "Y" }!
        index.removeProject(id: y.id)

        store.undoLastRemoval()

        #expect(Self.names(in: folder.id, index) == ["X", "Z"])
        #expect(!index.projects.contains { $0.name == "Y" })
    }

    @Test func aNewFolderWithTheSameNameMeanwhileGetsADistinctName() {
        let (store, index, dir) = Self.makeStore()
        defer { try? FileManager.default.removeItem(at: dir) }
        let folder = Self.seed(index)
        store.deleteFolders([folder.id])
        index.addFolder(name: "F")

        store.undoLastRemoval()

        let names = index.folders.map(\.name).sorted()
        #expect(names == ["F", "F 2"])
    }

    @Test func undoTwiceDoesNotDuplicateTheFolder() {
        let (store, index, dir) = Self.makeStore()
        defer { try? FileManager.default.removeItem(at: dir) }
        let folder = Self.seed(index)
        store.deleteFolders([folder.id])
        let removed = ProjectIndex.RemovedFolder(
            folder: folder, memberIds: [], rootIndex: 1)

        store.undoLastRemoval()
        index.restoreFolder(removed)

        #expect(index.folders.filter { $0.id == folder.id }.count == 1)
        #expect(Self.names(in: folder.id, index) == ["X", "Y", "Z"])
    }

    @Test func aNewDeleteSettlesTheOldOne() {
        let (store, index, dir) = Self.makeStore()
        defer { try? FileManager.default.removeItem(at: dir) }
        let first = Self.seed(index)
        let second = Self.addFolder(index, "G", holding: ["P"], atRootIndex: DropRouting.append)

        store.deleteFolders([first.id])
        store.deleteFolders([second.id])
        store.undoLastRemoval()

        // Only the most recent delete is undoable, as for a batch of studies.
        #expect(index.folders.map(\.id) == [second.id])
        #expect(store.pendingFolderName == nil)
    }

    @Test func deletingAFolderThatIsGoneMakesNothingPending() {
        let (store, index, dir) = Self.makeStore()
        defer { try? FileManager.default.removeItem(at: dir) }
        _ = Self.seed(index)

        store.deleteFolders([UUID()])

        #expect(!store.hasPending)
    }

    @Test func theEditMenuNamesTheFolder() {
        let (store, index, dir) = Self.makeStore()
        defer { try? FileManager.default.removeItem(at: dir) }
        let folder = Self.seed(index)

        store.deleteFolders([folder.id])

        #expect(store.pendingFolderName == "F")
        #expect(store.pendingName == nil)
        #expect(store.pendingFolderCount == 1)
    }

    @Test func undoSelectsTheRestoredFolder() {
        let (store, index, dir) = Self.makeStore()
        defer { try? FileManager.default.removeItem(at: dir) }
        let folder = Self.seed(index)
        var restored: Set<SidebarSelection>?
        store.setOnUndo { restored = $0 }

        store.deleteFolders([folder.id], priorSelection: [.folder(folder.id)])
        store.undoLastRemoval()

        #expect(restored == [.folder(folder.id)])
    }

    @Test func theEditMenuLabelsExistInEveryLocale() throws {
        // `I18n.t` falls back to English for a key a locale lacks, so a missed locale
        // shows as an English label, not a raw key: compare against English.
        func i18n(_ locale: String) throws -> I18n {
            let i = I18n()
            i.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
            i.setLocale(locale)
            return i
        }
        let en = try i18n("en")
        let enOne = en.t("desktop.menu.edit.undoDeleteFolder")
        let enMany = en.t("desktop.menu.edit.undoDeleteFolders")
        #expect(enOne == "Undo Delete Folder \u{201C}%@\u{201D}")
        for locale in ["ca", "cs", "da", "de", "es", "fi", "fr", "it", "ja", "ko", "nb", "nl",
                       "pl", "pt-BR", "pt-PT", "ru", "sv", "tr", "uk", "zh-Hant"] {
            let i = try i18n(locale)
            let one = i.t("desktop.menu.edit.undoDeleteFolder")
            let many = i.t("desktop.menu.edit.undoDeleteFolders")
            #expect(one != enOne && one.contains("%@"), "\(locale): \(one)")
            #expect(many != enMany && !many.contains("%@"), "\(locale): \(many)")
        }
    }
}
