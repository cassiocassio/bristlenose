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
                    try Data("a rec".utf8).write(to: to)
                    throw DiskGone()
                }
            )
        }
        #expect(everything(in: study).isEmpty)
    }
}
