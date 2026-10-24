import Foundation
import Testing

@testable import Bristlenose

/// A study that is being analysed takes dropped files (decision #100, 22 Oct
/// 2026), so a run can be reading the folder while a file copies into it.
/// The copy wrote straight to the final name: across volumes that file sat
/// there half-written, under a name `run`'s scan reads, for as long as the copy
/// took. It now lands under a hidden staging name and is renamed into place.
///
/// The byte copy is injected so the test can stop half-way and ask what a run
/// would see — `ScanSelection` is `run`'s own selection, ported line for line.
@MainActor
struct CopyMachineryStagingTests {

    private final class Sightings: @unchecked Sendable {
        private let lock = NSLock()
        private var seen: [[String]] = []
        func record(_ names: [String]) { lock.withLock { seen.append(names) } }
        var all: [[String]] { lock.withLock { seen } }
    }

    private func makeTempDir() -> URL {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("copy-staging-\(UUID().uuidString)", isDirectory: true)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    /// `FileManager.copyItem` refuses a destination that exists (EEXIST); a
    /// fake that overwrites, as `Data.write` does, cannot see a leftover.
    nonisolated static func refuseExisting(_ url: URL) throws {
        if FileManager.default.fileExists(atPath: url.path) {
            throw CocoaError(.fileWriteFileExists)
        }
    }

    /// Every entry in `dir`, hidden ones included.
    private func everything(in dir: URL) -> [String] {
        ((try? FileManager.default.contentsOfDirectory(atPath: dir.path)) ?? []).sorted()
    }

    @Test("a file half-copied into a study is invisible to the run's scan")
    func aHalfCopiedFileIsNotReadByARun() async throws {
        let src = makeTempDir()
        let study = makeTempDir()
        defer {
            try? FileManager.default.removeItem(at: src)
            try? FileManager.default.removeItem(at: study)
        }
        let recording = src.appendingPathComponent("Session 4.mp4")
        try Data("the whole recording".utf8).write(to: recording)

        let sightings = Sightings()
        let copied = try await CopyMachinery().copy(
            urls: [recording], into: study,
            projectID: UUID(), projectName: "Probe",
            acceptedExtensions: ["mp4"],
            isDataless: { _ in false },
            copyFile: { from, to in
                // Refuse an existing destination, as `copyItem` does.
                try Self.refuseExisting(to)
                // Half the file is on disk: what would a run read now?
                try Data("the whole".utf8).write(to: to)
                sightings.record(ScanSelection.readableFiles(under: study).map(\.lastPathComponent))
                try Data(contentsOf: from).write(to: to)
            }
        )

        #expect(sightings.all == [[]], "a run could read the file while it was half-written")
        #expect(copied.map(\.lastPathComponent) == ["Session 4.mp4"])
        let landed = study.appendingPathComponent("Session 4.mp4")
        #expect(try Data(contentsOf: landed) == Data("the whole recording".utf8))
        #expect(everything(in: study) == ["Session 4.mp4"], "the staging file was left behind")
    }

    @Test("a copy that fails part-way leaves nothing in the study, hidden or not")
    func aFailedCopyLeavesNoStagingFile() async throws {
        let src = makeTempDir()
        let study = makeTempDir()
        defer {
            try? FileManager.default.removeItem(at: src)
            try? FileManager.default.removeItem(at: study)
        }
        let recording = src.appendingPathComponent("Session 5.mp4")
        try Data("a recording".utf8).write(to: recording)

        struct DiskGone: Error {}
        await #expect(throws: CopyMachinery.CopyError.self) {
            _ = try await CopyMachinery().copy(
                urls: [recording], into: study,
                projectID: UUID(), projectName: "Probe",
                acceptedExtensions: ["mp4"],
                isDataless: { _ in false },
                copyFile: { _, to in
                    try Self.refuseExisting(to)
                    try Data("a rec".utf8).write(to: to)
                    throw DiskGone()
                }
            )
        }
        #expect(everything(in: study).isEmpty)
    }

    /// A quit or crash mid-copy leaves the hidden staging file behind. The
    /// next drop of the same recording must still land: `copyItem` refuses a
    /// destination that exists, so the copy used to fail once, with a toast
    /// naming a file the researcher cannot see (review of 8332d20c).
    @Test("a staging file left by a crash does not fail the next copy")
    func aLeftoverStagingFileDoesNotFailTheNextCopy() async throws {
        let src = makeTempDir()
        let study = makeTempDir()
        defer {
            try? FileManager.default.removeItem(at: src)
            try? FileManager.default.removeItem(at: study)
        }
        let recording = src.appendingPathComponent("Session 6.mp4")
        try Data("a whole recording".utf8).write(to: recording)
        let leftover = CopyMachinery.stagingURL(for: study.appendingPathComponent("Session 6.mp4"))
        try Data("a recor".utf8).write(to: leftover)

        // The real byte copy, which refuses an existing destination.
        let copied = try await CopyMachinery().copy(
            urls: [recording], into: study,
            projectID: UUID(), projectName: "Probe",
            acceptedExtensions: ["mp4"],
            isDataless: { _ in false }
        )

        #expect(copied.map(\.lastPathComponent) == ["Session 6.mp4"])
        #expect(try Data(contentsOf: study.appendingPathComponent("Session 6.mp4"))
                == Data("a whole recording".utf8))
        #expect(everything(in: study) == ["Session 6.mp4"])
    }

    // MARK: - A failed drop leaves no empty folders (N46, 24 Oct 2026)

    /// A dropped folder is copied with its own shape, so a failure part-way
    /// rolled the files back and left `Batch/a/b/…` behind, empty, in the study.
    private func makeBatch(in src: URL) throws -> URL {
        let batch = src.appendingPathComponent("Batch", isDirectory: true)
        for (folder, name) in [("a/b", "one.mp4"), ("a/c", "two.mp4"), ("d", "three.mp4")] {
            let dir = batch.appendingPathComponent(folder, isDirectory: true)
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            try Data(name.utf8).write(to: dir.appendingPathComponent(name))
        }
        return batch
    }

    /// A fake byte copy that fails on the file named `failing`.
    nonisolated static func failing(on failing: String) -> @Sendable (URL, URL) throws -> Void {
        { from, to in
            struct DiskGone: Error {}
            try Self.refuseExisting(to)
            if from.lastPathComponent == failing { throw DiskGone() }
            try Data(contentsOf: from).write(to: to)
        }
    }

    @Test("a dropped folder whose copy fails part-way leaves no empty folders in the study")
    func aFailedFolderDropLeavesNoEmptyFolders() async throws {
        let src = makeTempDir()
        let study = makeTempDir()
        defer {
            try? FileManager.default.removeItem(at: src)
            try? FileManager.default.removeItem(at: study)
        }
        let batch = try makeBatch(in: src)

        await #expect(throws: CopyMachinery.CopyError.self) {
            _ = try await CopyMachinery().copy(
                urls: [batch], into: study,
                projectID: UUID(), projectName: "Probe",
                acceptedExtensions: ["mp4"],
                isDataless: { _ in false },
                copyFile: Self.failing(on: "three.mp4")
            )
        }
        #expect(everything(in: study).isEmpty, "empty folders were left in the study")
    }

    @Test("a rollback keeps the folders the study already had, and removes only the new ones")
    func aRollbackKeepsTheResearchersOwnFolders() async throws {
        let src = makeTempDir()
        let study = makeTempDir()
        defer {
            try? FileManager.default.removeItem(at: src)
            try? FileManager.default.removeItem(at: study)
        }
        let batch = try makeBatch(in: src)
        // An earlier drop of the same folder name left `Batch/a` (with a file in it).
        let existing = study.appendingPathComponent("Batch/a", isDirectory: true)
        try FileManager.default.createDirectory(at: existing, withIntermediateDirectories: true)
        try Data("mine".utf8).write(to: existing.appendingPathComponent("kept.mp4"))

        await #expect(throws: CopyMachinery.CopyError.self) {
            _ = try await CopyMachinery().copy(
                urls: [batch], into: study,
                projectID: UUID(), projectName: "Probe",
                acceptedExtensions: ["mp4"],
                isDataless: { _ in false },
                copyFile: Self.failing(on: "three.mp4")
            )
        }
        #expect(everything(in: study) == ["Batch"])
        #expect(everything(in: study.appendingPathComponent("Batch")) == ["a"])
        #expect(everything(in: existing) == ["kept.mp4"], "a folder that was already there was touched")
    }

    @Test("a folder something else has since written into is kept by a rollback")
    func aRollbackKeepsAFolderThatIsNoLongerEmpty() async throws {
        let src = makeTempDir()
        let study = makeTempDir()
        defer {
            try? FileManager.default.removeItem(at: src)
            try? FileManager.default.removeItem(at: study)
        }
        let batch = try makeBatch(in: src)
        let late = study.appendingPathComponent("Batch/d/late.txt")

        await #expect(throws: CopyMachinery.CopyError.self) {
            _ = try await CopyMachinery().copy(
                urls: [batch], into: study,
                projectID: UUID(), projectName: "Probe",
                acceptedExtensions: ["mp4"],
                isDataless: { _ in false },
                copyFile: { from, to in
                    try Self.refuseExisting(to)
                    if from.lastPathComponent == "three.mp4" {
                        // A run, or the researcher, writes into the new folder
                        // before the failure lands.
                        try Data("x".utf8).write(to: late)
                        struct DiskGone: Error {}
                        throw DiskGone()
                    }
                    try Data(contentsOf: from).write(to: to)
                }
            )
        }
        #expect(FileManager.default.fileExists(atPath: late.path))
    }
}
