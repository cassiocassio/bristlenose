import Foundation
import Testing
@testable import Bristlenose

/// R63's follow-up (decision #8, 20 Oct 2026): a study whose cloud folder has
/// gone was still spawned against its missing path.
///
/// A folder a sync client manages has no state of its own (decided 22 Oct 2026,
/// `docs/design-cloud-files.md`): an evicted folder is still there,
/// resolves `.ready` and runs, the sidecar fetching its files on demand
/// (`docs/design-project-storage.md` §3); a gone one is `.cantFind`, like any
/// gone folder, and is refused with Locate… offered. These pin that split, and
/// that a refusal writes the runner state a scan of the folder reads.
@MainActor
@Suite struct SpawnRefusalTests {

    /// A project in an iCloud Drive-shaped folder under a scratch root, so
    /// `detectLocation` classifies it cloud without touching iCloud.
    private static func cloudProject(
        _ index: ProjectIndex, root: URL, _ name: String
    ) -> Project {
        let dir = root
            .appendingPathComponent("Library/Mobile Documents/com~apple~CloudDocs")
            .appendingPathComponent(name)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return index.addProject(name: name, path: dir.path)
    }

    private static func scratch() -> (URL, ProjectIndex) {
        let root = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("spawn-refusal-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        return (root, ProjectIndex(fileURL: root.appendingPathComponent("projects.json")))
    }

    private func until(_ condition: () -> Bool, seconds: Double = 5) async {
        let deadline = Date().addingTimeInterval(seconds)
        while !condition(), Date() < deadline {
            try? await Task.sleep(for: .milliseconds(10))
        }
    }

    // MARK: - The decision

    @Test func aFolderThatIsThereIsRun() {
        #expect(PipelineRunner.spawnRefusal(for: .ready) == nil)
    }

    @Test func aFolderThatIsGoneIsRefusedHoweverItWent() {
        let gone: [ProjectAvailability] = [
            .cantFind(reason: .unmountedVolume(name: "T7")),
            .cantFind(reason: .networkUnreachable(host: "nas.local")),
            .cantFind(reason: .moved),
            .cantFind(reason: .missingBookmark),
        ]
        for availability in gone {
            #expect(PipelineRunner.spawnRefusal(for: availability)
                    == .unreachable(reason: .folderMissing),
                    "\(availability) was run against a folder that isn't there")
        }
    }

    // MARK: - Which case is which

    /// The evicted case's shape: a cloud-classified folder that is on disk is
    /// `.ready`. An ordinary directory stands in for one whose files are all
    /// placeholders: availability asks only whether the folder exists, which
    /// a stat answers without fetching anything.
    @Test func aCloudFolderThatIsThereIsReady() {
        let (root, index) = Self.scratch(); defer { try? FileManager.default.removeItem(at: root) }
        let p = Self.cloudProject(index, root: root, "Evicted")

        #expect(p.location?.type == .cloud)
        #expect(p.availability == .ready)
        #expect(PipelineRunner.spawnRefusal(for: p.availability) == nil)
    }

    /// No cloud-specific state: a cloud folder that has gone is a gone folder.
    @Test func aCloudFolderThatIsGoneCannotBeFound() {
        let (root, index) = Self.scratch(); defer { try? FileManager.default.removeItem(at: root) }
        let p = Self.cloudProject(index, root: root, "Gone")
        try? FileManager.default.removeItem(atPath: p.path)

        #expect(p.location?.type == .cloud)
        #expect(Self.cannotBeFound(p.availability))
        #expect(PipelineRunner.spawnRefusal(for: p.availability) == .unreachable(reason: .folderMissing))
        // The moved-folder treatment, as for any gone folder: Locate…, no cloud glyph.
        #expect(p.availability.primaryAction == .locate)
        #expect(p.availability.sfSymbolName == "questionmark.folder")
    }

    static func cannotBeFound(_ availability: ProjectAvailability) -> Bool {
        if case .cantFind = availability { return true }
        return false
    }

    // MARK: - What the row says

    /// The refusal writes the state a scan of the gone folder reads, so the
    /// row says the same whichever got there first.
    @Test func theRefusalReadsWhatAScanReads() async {
        let (root, index) = Self.scratch(); defer { try? FileManager.default.removeItem(at: root) }
        let p = Self.cloudProject(index, root: root, "Gone")
        try? FileManager.default.removeItem(atPath: p.path)

        let scanned = await PipelineRunner.parseManifest(at: PipelineRunner.manifestURL(for: p))
        #expect(PipelineRunner.spawnRefusal(for: p.availability) == scanned)
    }

    /// A refused study whose cloud folder has gone gets the moved-folder row,
    /// as any gone folder does: availability outranks the refusal.
    @Test func aRefusedCloudStudysRowSaysItCannotBeFound() {
        let (root, index) = Self.scratch(); defer { try? FileManager.default.removeItem(at: root) }
        let p = Self.cloudProject(index, root: root, "Gone")
        try? FileManager.default.removeItem(atPath: p.path)

        let variant = ProjectSubtitle.resolve(
            availability: p.availability,
            pipelineState: PipelineRunner.spawnRefusal(for: p.availability),
            isStopping: false, addingCount: nil, copy: nil, importBatch: nil,
            lastRunAt: nil, missingCount: 0, unanalysedCount: 0
        )
        guard case .cantFind = variant else {
            Issue.record("a gone cloud folder's row read \(variant), not the missing-folder line")
            return
        }
    }

    // MARK: - Through the runner

    @Test func aStudyWhoseCloudFolderIsGoneIsNotRun() {
        let rig = PipelineRunnerQueueTests.Rig(); defer { rig.cleanUp() }
        let a = Self.cloudProject(rig.index, root: rig.root, "A")
        try? FileManager.default.removeItem(atPath: a.path)
        #expect(Self.cannotBeFound(a.availability))

        rig.runner.start(project: a)

        #expect(rig.launches.isEmpty, "a run was started against a cloud folder that is gone")
        #expect(rig.runner.state[a.id] == .unreachable(reason: .folderMissing))
    }

    @Test func aQueuedStudyWhoseCloudFolderWentIsSkipped() async throws {
        let rig = PipelineRunnerQueueTests.Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        let b = Self.cloudProject(rig.index, root: rig.root, "B")
        let c = rig.project("C")
        rig.runner.start(project: a)
        rig.runner.start(project: b)
        rig.runner.start(project: c)
        try? FileManager.default.removeItem(atPath: b.path)
        #expect(Self.cannotBeFound(b.availability))

        try #require(rig.launches.first).exit()
        await until { rig.launches.count == 2 }

        #expect(rig.launches.map(\.project.name) == ["A", "C"])
        #expect(rig.runner.state[b.id] == .unreachable(reason: .folderMissing))
    }

    /// A start handed the `Project` a sheet opened with runs the folder where
    /// it is now, not where it was (silent-failure review, 20 Oct 2026).
    @Test func aStartWithAStaleProjectRunsTheFolderWhereItIsNow() throws {
        let rig = PipelineRunnerQueueTests.Rig(); defer { rig.cleanUp() }
        let stale = rig.project("A")
        let moved = rig.root.appendingPathComponent("A renamed")
        try FileManager.default.moveItem(atPath: stale.path, toPath: moved.path)
        rig.index.relocateProject(id: stale.id, newPath: moved.path)

        rig.runner.start(project: stale)

        #expect(rig.launches.map(\.project.path) == [moved.path])
    }

    /// The evicted case through the runner: a cloud folder that is there runs.
    @Test func aStudyInACloudFolderThatIsThereIsRun() {
        let rig = PipelineRunnerQueueTests.Rig(); defer { rig.cleanUp() }
        let a = Self.cloudProject(rig.index, root: rig.root, "A")

        rig.runner.start(project: a)

        #expect(rig.launches.map(\.project.name) == ["A"])
    }
}
