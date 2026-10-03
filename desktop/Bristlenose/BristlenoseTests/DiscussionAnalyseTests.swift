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

    @Test func aGuideOlderThanTheRecordIsNotWanted() throws {
        let root = try project()
        defer { try? FileManager.default.removeItem(at: root) }
        try writeGuide(root, at: Date(timeIntervalSinceNow: -3600))
        try writeRecord(root, at: Date())
        #expect(!ProjectFolderWatcher.discussionWanted(projectRoot: root))
    }
}
