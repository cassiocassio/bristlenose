import Foundation
import Testing
@testable import Bristlenose

/// A study read while its folder was away kept that reading after the folder
/// came back (R63 open item 1, 21 Oct 2026): "Folder not found", no Analyse,
/// until relaunch. Nothing re-read it: a remount re-leased the folder but
/// rescanned only a path that moved, and a cloud folder put back has no event
/// at all. The rule now is general — whenever a folder becomes reachable again,
/// whatever made it so, the index says so once and the runner reads it again.
@MainActor
@Suite struct FolderReturnTests {

    private static func scratch() -> (URL, ProjectIndex) {
        let root = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("folder-return-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        return (root, ProjectIndex(fileURL: root.appendingPathComponent("projects.json")))
    }

    private func until(_ condition: () -> Bool, seconds: Double = 5) async {
        let deadline = Date().addingTimeInterval(seconds)
        while !condition(), Date() < deadline {
            try? await Task.sleep(for: .milliseconds(10))
        }
    }

    private static func remove(_ p: Project) {
        try? FileManager.default.removeItem(atPath: p.path)
    }

    private static func restore(_ p: Project) {
        try? FileManager.default.createDirectory(atPath: p.path, withIntermediateDirectories: true)
    }

    // MARK: - The index notices a return, once

    @Test func aFolderThatComesBackIsReportedOnce() {
        let (root, index) = Self.scratch(); defer { try? FileManager.default.removeItem(at: root) }
        let dir = root.appendingPathComponent("A")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let p = index.addProject(name: "A", path: dir.path)
        var returned: [UUID] = []
        index.onFolderReturned = { returned.append($0.id) }

        Self.remove(p)
        index.syncWatchers()
        #expect(returned.isEmpty, "a folder that went away was reported as back")

        Self.restore(p)
        index.syncWatchers()
        index.syncWatchers()
        #expect(returned == [p.id])
    }

    @Test func aFolderThatNeverWentIsNotReported() {
        let (root, index) = Self.scratch(); defer { try? FileManager.default.removeItem(at: root) }
        let dir = root.appendingPathComponent("A")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        _ = index.addProject(name: "A", path: dir.path)
        var returned: [UUID] = []
        index.onFolderReturned = { returned.append($0.id) }

        index.syncWatchers()

        #expect(returned.isEmpty)
    }

    /// Activation looks only at the folders that were away, and finds the one
    /// that came back with no event of ours (a cloud folder restored).
    @Test func activationFindsAFolderPutBack() async {
        let (root, index) = Self.scratch(); defer { try? FileManager.default.removeItem(at: root) }
        let a = root.appendingPathComponent("A"), b = root.appendingPathComponent("B")
        for d in [a, b] { try? FileManager.default.createDirectory(at: d, withIntermediateDirectories: true) }
        let pa = index.addProject(name: "A", path: a.path)
        let pb = index.addProject(name: "B", path: b.path)
        Self.remove(pa); Self.remove(pb)
        index.syncWatchers()
        var returned: [UUID] = []
        index.onFolderReturned = { returned.append($0.id) }

        Self.restore(pa)
        index.syncIfAFolderReturned()
        await until { !returned.isEmpty }

        #expect(returned == [pa.id], "B is still away")
        _ = pb
    }

    // MARK: - Through the runner

    /// A drive remounted: `refreshAvailability` ends in `syncWatchers`, and the
    /// study refused while it was away reads again.
    @Test func aStudyRefusedWhileItsDriveWasAwayIsReadAgainOnRemount() async {
        let rig = PipelineRunnerQueueTests.Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        Self.remove(a)
        rig.index.syncWatchers()
        rig.runner.start(project: a)
        #expect(rig.runner.state[a.id] == .unreachable(reason: .folderMissing))

        Self.restore(a)
        rig.index.refreshAvailability()
        await until { rig.runner.state[a.id] != .unreachable(reason: .folderMissing) }

        #expect(rig.runner.state[a.id] == .idle)
        #expect(rig.launches.isEmpty, "a return reads the study; it does not run it")
    }

    /// A cloud folder put back while the app was in the background: the
    /// activation look finds it and the row stops saying "Folder not found".
    @Test func aCloudStudyPutBackIsReadAgainOnActivation() async {
        let rig = PipelineRunnerQueueTests.Rig(); defer { rig.cleanUp() }
        let dir = rig.root
            .appendingPathComponent("Library/Mobile Documents/com~apple~CloudDocs/A")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let a = rig.index.addProject(name: "A", path: dir.path)
        Self.remove(a)
        rig.index.syncWatchers()
        #expect(a.availability == .inCloud(downloading: nil))
        rig.runner.start(project: a)
        #expect(rig.runner.state[a.id] == .unreachable(reason: .folderMissing))

        Self.restore(a)
        rig.index.syncIfAFolderReturned()
        await until { rig.runner.state[a.id] != .unreachable(reason: .folderMissing) }

        #expect(rig.runner.state[a.id] == .idle)
    }
}
