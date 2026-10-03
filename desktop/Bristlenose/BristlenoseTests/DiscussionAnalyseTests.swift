import Foundation
import Testing
@testable import Bristlenose

/// Analyse is offered when an analysed project's Discussion lens has nothing
/// to show — the only non-destructive way to build it on the Mac, where
/// Re-analyse… starts over (decided 4 Oct 2026).
@Suite struct DiscussionAnalyseTests {

    private func state(sessions: Int?, ingestable: Int, wanted: Bool) -> UnanalysedState {
        UnanalysedState(
            newFiles: [], missingFiles: [], sessionCount: sessions, totalDurationSeconds: nil,
            ingestableFileCount: ingestable, discussionWanted: wanted)
    }

    @Test func aMissingDiscussionOffersAnalyse_evenWithRecordingsInASubfolder() {
        // No top-level recordings: the project's interviews sit in a subfolder.
        #expect(SidebarOutlineController.hasWorkToDo(state(sessions: 3, ingestable: 0, wanted: true)))
    }

    @Test func anAnalysedProjectWithItsDiscussionHasNothingToDo() {
        #expect(!SidebarOutlineController.hasWorkToDo(state(sessions: 3, ingestable: 3, wanted: false)))
    }

    @Test func aNeverAnalysedProjectIsUnchanged() {
        // discussionWanted only means something once there is an analysis.
        #expect(!SidebarOutlineController.hasWorkToDo(state(sessions: 0, ingestable: 0, wanted: true)))
        #expect(SidebarOutlineController.hasWorkToDo(state(sessions: 0, ingestable: 2, wanted: false)))
    }

    // MARK: - the filesystem check

    private func project() throws -> URL {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("discussion-analyse-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        return root
    }

    private func writeRecord(_ root: URL, at date: Date) throws {
        let dir = root.appendingPathComponent("bristlenose-output/.bristlenose/intermediate")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let file = dir.appendingPathComponent("discussion.json")
        try Data("{}".utf8).write(to: file)
        try FileManager.default.setAttributes([.modificationDate: date], ofItemAtPath: file.path)
    }

    private func writeGuide(_ root: URL, folder: String = "Discussion guide", at date: Date) throws {
        let dir = root.appendingPathComponent(folder)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let file = dir.appendingPathComponent("guide.docx")
        try Data("x".utf8).write(to: file)
        for path in [file.path, dir.path] {
            try FileManager.default.setAttributes([.modificationDate: date], ofItemAtPath: path)
        }
    }

    @Test func noRecordIsWanted() throws {
        let root = try project()
        defer { try? FileManager.default.removeItem(at: root) }
        #expect(ProjectFolderWatcher.discussionWanted(projectRoot: root))
    }

    @Test func aRecordAndNoGuideIsNotWanted() throws {
        let root = try project()
        defer { try? FileManager.default.removeItem(at: root) }
        try writeRecord(root, at: Date())
        #expect(!ProjectFolderWatcher.discussionWanted(projectRoot: root))
    }

    @Test func aGuideChangedAfterTheRecordIsWanted_whateverTheFolderCase() throws {
        let root = try project()
        defer { try? FileManager.default.removeItem(at: root) }
        let then = Date(timeIntervalSinceNow: -3600)
        try writeRecord(root, at: then)
        try writeGuide(root, folder: "Discussion Guide", at: Date())
        #expect(ProjectFolderWatcher.discussionWanted(projectRoot: root))
    }

    // MARK: - installing a chosen guide

    private func source(_ name: String, _ text: String) throws -> URL {
        // Its own folder, so the file keeps the exact name a researcher chose.
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("src-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let url = dir.appendingPathComponent(name)
        try Data(text.utf8).write(to: url)
        try FileManager.default.setAttributes([.modificationDate: Date(timeIntervalSinceNow: -86_400)],
                                              ofItemAtPath: url.path)
        return url
    }

    @Test func installCreatesTheFolderAndMakesTheDiscussionWanted() throws {
        let root = try project()
        defer { try? FileManager.default.removeItem(at: root) }
        try writeRecord(root, at: Date(timeIntervalSinceNow: -60))
        // a guide last saved yesterday must still read as newer than the record
        let dest = try DiscussionGuide.install(try source("guide.md", "# Guide"), into: root)
        #expect(dest.deletingLastPathComponent().lastPathComponent == DiscussionGuide.folderName)
        #expect(ProjectFolderWatcher.discussionWanted(projectRoot: root))
    }

    @Test func installUsesTheFolderThatIsThere_whateverItsCase() throws {
        let root = try project()
        defer { try? FileManager.default.removeItem(at: root) }
        try FileManager.default.createDirectory(
            at: root.appendingPathComponent("discussion GUIDE"), withIntermediateDirectories: true)
        let dest = try DiscussionGuide.install(try source("guide.txt", "x"), into: root)
        #expect(dest.deletingLastPathComponent().lastPathComponent == "discussion GUIDE")
        let folders = try FileManager.default.contentsOfDirectory(atPath: root.path)
        #expect(folders.filter { $0.lowercased() == "discussion guide" }.count == 1)
    }

    @Test func choosingTheSameNameAgainReplacesIt_andLeavesOtherFilesAlone() throws {
        let root = try project()
        defer { try? FileManager.default.removeItem(at: root) }
        try DiscussionGuide.install(try source("guide.md", "old"), into: root)
        let other = try DiscussionGuide.install(try source("notes.txt", "keep me"), into: root)
        let dest = try DiscussionGuide.install(try source("guide.md", "new"), into: root)
        #expect(try String(contentsOf: dest, encoding: .utf8) == "new")
        #expect(try String(contentsOf: other, encoding: .utf8) == "keep me")
        let names = try FileManager.default.contentsOfDirectory(atPath: dest.deletingLastPathComponent().path)
        #expect(Set(names) == ["guide.md", "notes.txt"])  // no staged leftovers
    }

    @Test func aGuideOlderThanTheRecordIsNotWanted() throws {
        let root = try project()
        defer { try? FileManager.default.removeItem(at: root) }
        try writeGuide(root, at: Date(timeIntervalSinceNow: -3600))
        try writeRecord(root, at: Date())
        #expect(!ProjectFolderWatcher.discussionWanted(projectRoot: root))
    }
}
