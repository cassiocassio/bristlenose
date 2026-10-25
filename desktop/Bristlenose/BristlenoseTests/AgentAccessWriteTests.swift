import Foundation
import Testing
@testable import Bristlenose

/// N193 (sweep 2, MCP-4): turning Agent Access off never reported a failure.
///
/// The read-back after the write decoded the file with a plain `JSONDecoder`,
/// which throws on the file's ISO-8601 dates whenever there is a project, and
/// then compared only how many projects there were, never the flag. And
/// `setAgentAccess` returned `true` whatever the check said. So a turn-off that
/// was not saved (a full disk, a refused write) looked exactly like one that
/// was, and the study was open to agents again on the next launch.
///
/// A suite of its own and `.serialized`: two of these make a directory
/// read-only, and the ordering of the notification observers is easier to
/// reason about one test at a time.
@MainActor
@Suite("Agent Access write reaches the disk", .serialized)
struct AgentAccessWriteTests {

    private static func makeIndex() -> (ProjectIndex, URL, URL) {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let file = dir.appendingPathComponent("projects.json")
        return (ProjectIndex(fileURL: file), dir, file)
    }

    private static func cleanup(_ dir: URL) {
        // A read-only directory cannot be removed from.
        try? FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: dir.path)
        try? FileManager.default.removeItem(at: dir)
    }

    private static func lock(_ dir: URL) {
        try? FileManager.default.setAttributes([.posixPermissions: 0o555], ofItemAtPath: dir.path)
    }

    private static func unlock(_ dir: URL) {
        try? FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: dir.path)
    }

    /// Records the notifications one project's access change posts.
    private final class Posts {
        var changed: [Bool] = []
        var notSaved: [Bool] = []
        private var tokens: [any NSObjectProtocol] = []

        init(project id: UUID) {
            let center = NotificationCenter.default
            tokens.append(center.addObserver(
                forName: .bristlenoseAgentAccessChanged, object: nil, queue: nil
            ) { [weak self] note in
                guard note.userInfo?["id"] as? UUID == id else { return }
                self?.changed.append(note.userInfo?["enabled"] as? Bool ?? false)
            })
            tokens.append(center.addObserver(
                forName: .bristlenoseAgentAccessNotSaved, object: nil, queue: nil
            ) { [weak self] note in
                guard note.userInfo?["id"] as? UUID == id else { return }
                self?.notSaved.append(note.userInfo?["enabled"] as? Bool ?? false)
            })
        }

        deinit { tokens.forEach { NotificationCenter.default.removeObserver($0) } }
    }

    private static func onDisk(_ file: URL, _ id: UUID) -> Bool? {
        ProjectIndex(fileURL: file).projects.first { $0.id == id }?.agentAccess
    }

    // MARK: - The ordinary path

    /// With a project in the list, the read-back used to throw on every call;
    /// the answer was `true` anyway, so only the false ERROR in the log showed
    /// it. This pins the read-back to the app's own date decoding: a plain
    /// decoder reads the write as "did not persist" and turns this red.
    @Test func aTurnOffThatIsWrittenIsReportedAndStays() {
        let (index, dir, file) = Self.makeIndex()
        defer { Self.cleanup(dir) }
        let project = index.addProject(name: "Shared", path: "/tmp/shared")
        #expect(index.setAgentAccess(id: project.id, enabled: true))
        let posts = Posts(project: project.id)

        #expect(index.setAgentAccess(id: project.id, enabled: false))

        #expect(index.projects.first?.agentAccess == false)
        #expect(Self.onDisk(file, project.id) == false)
        #expect(posts.changed == [false])
        #expect(posts.notSaved.isEmpty, "a write that landed was reported as not saved")
    }

    // MARK: - The write fails

    @Test func aTurnOffThatCannotBeWrittenLeavesTheStudyShared() {
        let (index, dir, file) = Self.makeIndex()
        defer { Self.cleanup(dir) }
        let project = index.addProject(name: "Shared", path: "/tmp/shared")
        #expect(index.setAgentAccess(id: project.id, enabled: true))
        let posts = Posts(project: project.id)

        Self.lock(dir)
        let applied = index.setAgentAccess(id: project.id, enabled: false)
        Self.unlock(dir)

        #expect(applied == false, "a turn-off that did not reach the disk was reported as done")
        #expect(index.projects.first?.agentAccess == true,
                "the sidebar would show the study as private while the file still shares it")
        #expect(Self.onDisk(file, project.id) == true)
        #expect(posts.changed.isEmpty, "the handshake was told access went off when it did not")
        #expect(posts.notSaved == [false])
    }

    @Test func aTurnOnThatCannotBeWrittenLeavesTheStudyPrivate() {
        let (index, dir, file) = Self.makeIndex()
        defer { Self.cleanup(dir) }
        let project = index.addProject(name: "Private", path: "/tmp/private")
        let posts = Posts(project: project.id)

        Self.lock(dir)
        let applied = index.setAgentAccess(id: project.id, enabled: true)
        Self.unlock(dir)

        #expect(applied == false)
        #expect(index.projects.first?.agentAccess == false)
        #expect(Self.onDisk(file, project.id) == false)
        #expect(posts.changed.isEmpty)
        #expect(posts.notSaved == [true])
    }

    /// The write returns cleanly and stores nothing (the house rule: returning
    /// cleanly is not evidence anything was stored). Only reading the flag back
    /// catches it; a count of projects cannot.
    @Test func aWriteThatReturnsCleanlyButStoresNothingIsCaught() {
        let (index, dir, file) = Self.makeIndex()
        defer { Self.cleanup(dir) }
        let project = index.addProject(name: "Shared", path: "/tmp/shared")
        #expect(index.setAgentAccess(id: project.id, enabled: true))
        let posts = Posts(project: project.id)
        index.fileWriter = { _, _ in }   // lands nothing, throws nothing

        let applied = index.setAgentAccess(id: project.id, enabled: false)

        #expect(applied == false)
        #expect(index.projects.first?.agentAccess == true)
        #expect(Self.onDisk(file, project.id) == true)
        #expect(posts.changed.isEmpty)
        #expect(posts.notSaved == [false])
    }

    /// A failed turn-off is not stuck: once the disk takes writes again the
    /// same click works, because the flag was put back rather than half-set.
    @Test func theSameTurnOffWorksOnceTheDiskTakesWritesAgain() {
        let (index, dir, file) = Self.makeIndex()
        defer { Self.cleanup(dir) }
        let project = index.addProject(name: "Shared", path: "/tmp/shared")
        #expect(index.setAgentAccess(id: project.id, enabled: true))

        Self.lock(dir)
        #expect(index.setAgentAccess(id: project.id, enabled: false) == false)
        Self.unlock(dir)

        #expect(index.setAgentAccess(id: project.id, enabled: false))
        #expect(Self.onDisk(file, project.id) == false)
    }

    /// Unknown project, or nothing to change: still `false`, still silent.
    @Test func aChangeThatChangesNothingIsNotAFailure() {
        let (index, dir, _) = Self.makeIndex()
        defer { Self.cleanup(dir) }
        let project = index.addProject(name: "Private", path: "/tmp/private")
        let posts = Posts(project: project.id)

        #expect(index.setAgentAccess(id: project.id, enabled: false) == false)
        #expect(index.setAgentAccess(id: UUID(), enabled: true) == false)

        #expect(posts.changed.isEmpty)
        #expect(posts.notSaved.isEmpty)
    }
}
