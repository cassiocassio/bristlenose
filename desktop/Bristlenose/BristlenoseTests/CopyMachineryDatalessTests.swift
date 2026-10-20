import Foundation
import Testing

@testable import Bristlenose

/// A dropped recording that is still in the cloud (dataless) must never reach
/// `copyItem`. Under this app's materialisation policy (ON, pinned by
/// `DatalessPolicyProbeTests`) that call waits with no timeout, and
/// `Task.cancel()` cannot interrupt it, so the row sat at "Copying · 0%" until
/// a force-quit (`desktop/CLAUDE.md`, the `copyItem` gotcha).
///
/// No test can make a real dataless file — the flag is the File Provider's to
/// set — so these inject the reader and use ordinary local files. A local file
/// copies instantly, which is what makes the assertions bite: if the check is
/// skipped, the copy *succeeds* and the test goes red.
@MainActor
struct CopyMachineryDatalessTests {

    private func makeTempDir() -> URL {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("copy-dataless-\(UUID().uuidString)", isDirectory: true)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    private func write(_ url: URL, _ content: String) throws {
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data(content.utf8).write(to: url)
    }

    /// Every regular file under `root`, so "nothing was written" is checked
    /// against the disk rather than against what `copy()` claims it returned.
    private func filesUnder(_ root: URL) -> [String] {
        guard let walker = FileManager.default.enumerator(
            at: root, includingPropertiesForKeys: [.isRegularFileKey]) else { return [] }
        var out: [String] = []
        for case let url as URL in walker
        where (try? url.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) == true {
            out.append(url.lastPathComponent)
        }
        return out
    }

    @Test("one offloaded file in a dropped folder refuses the whole drop, writing nothing")
    func offloadedFileInAFolderRefusesTheDrop() async throws {
        let src = makeTempDir()
        let dest = makeTempDir()
        defer {
            try? FileManager.default.removeItem(at: src)
            try? FileManager.default.removeItem(at: dest)
        }
        let folder = src.appendingPathComponent("Round 2", isDirectory: true)
        try write(folder.appendingPathComponent("P01.mp4"), "local one")
        try write(folder.appendingPathComponent("P02.mp4"), "in the cloud")
        try write(folder.appendingPathComponent("P03.mp4"), "local three")

        // Offloaded at planning only. If the planning refusal goes, the copy
        // loop sees a local file and the whole folder lands — red whatever
        // order the walk yields the files in.
        let reader = ScriptedLooks(target: "P02.mp4", answers: [true, false])
        let machinery = CopyMachinery()
        var caught: CopyMachinery.CopyError?
        do {
            _ = try await machinery.copy(
                urls: [folder], into: dest,
                projectID: UUID(), projectName: "Probe",
                acceptedExtensions: ["mp4"],
                isDataless: reader.check
            )
        } catch let err as CopyMachinery.CopyError {
            caught = err
        }

        let err = try #require(caught)
        guard case .sourceNotDownloaded(let count) = err else {
            Issue.record("expected .sourceNotDownloaded, got \(err)")
            return
        }
        #expect(count == 1)
        #expect(filesUnder(dest).isEmpty, "a refused drop wrote \(filesUnder(dest))")
        // Refused before the copy starts, not rolled back after it: a rollback
        // removes files but leaves the empty "Round 2" folder in the project.
        let entries = try FileManager.default.contentsOfDirectory(atPath: dest.path)
        #expect(entries.isEmpty, "a refused drop left \(entries) in the project")
        #expect(machinery.inFlight == nil)
    }

    /// Walking a folder whose own listing is in the cloud would fetch it on the
    /// main thread. The folder is refused before the walk; the files inside are
    /// local here, so without that check the drop copies and the test goes red.
    @Test("a dropped folder that is itself offloaded is refused before it is walked")
    func offloadedFolderIsRefusedBeforeTheWalk() async throws {
        let src = makeTempDir()
        let dest = makeTempDir()
        defer {
            try? FileManager.default.removeItem(at: src)
            try? FileManager.default.removeItem(at: dest)
        }
        let folder = src.appendingPathComponent("Round 3", isDirectory: true)
        try write(folder.appendingPathComponent("P01.mp4"), "one")

        let machinery = CopyMachinery()
        var caught: CopyMachinery.CopyError?
        do {
            _ = try await machinery.copy(
                urls: [folder], into: dest,
                projectID: UUID(), projectName: "Probe",
                acceptedExtensions: ["mp4"],
                isDataless: { $0.hasDirectoryPath }
            )
        } catch let err as CopyMachinery.CopyError {
            caught = err
        }
        guard case .sourceNotDownloaded(let count) = try #require(caught) else {
            Issue.record("expected .sourceNotDownloaded, got \(String(describing: caught))")
            return
        }
        #expect(count == 1)
        #expect(try FileManager.default.contentsOfDirectory(atPath: dest.path).isEmpty)
        #expect(machinery.inFlight == nil)
    }

    @Test("every file offloaded: refused, counted, and the next drop is accepted")
    func allOffloadedThenNextDropWorks() async throws {
        let src = makeTempDir()
        let dest = makeTempDir()
        defer {
            try? FileManager.default.removeItem(at: src)
            try? FileManager.default.removeItem(at: dest)
        }
        let a = src.appendingPathComponent("A.mov")
        let b = src.appendingPathComponent("B.mov")
        try write(a, "a")
        try write(b, "b")

        let machinery = CopyMachinery()
        var caught: CopyMachinery.CopyError?
        do {
            _ = try await machinery.copy(
                urls: [a, b], into: dest,
                projectID: UUID(), projectName: "Probe",
                acceptedExtensions: ["mov"],
                isDataless: { _ in true }
            )
        } catch let err as CopyMachinery.CopyError {
            caught = err
        }
        guard case .sourceNotDownloaded(let count) = try #require(caught) else {
            Issue.record("expected .sourceNotDownloaded, got \(String(describing: caught))")
            return
        }
        #expect(count == 2)
        #expect(machinery.inFlight == nil)

        // Once the files are down, the same drop goes through: nothing was
        // left in flight to bounce it with "Another copy is already in flight".
        let copied = try await machinery.copy(
            urls: [a, b], into: dest,
            projectID: UUID(), projectName: "Probe",
            acceptedExtensions: ["mov"],
            isDataless: { _ in false }
        )
        #expect(copied.map(\.lastPathComponent).sorted() == ["A.mov", "B.mov"])
    }

    /// The file a batch reaches last can be evicted by iCloud's Optimise Mac
    /// Storage while earlier files copy. The planning check has already passed
    /// it, so the loop asks again just before each copy.
    @Test("a file evicted after planning is caught before its copy, and earlier copies roll back")
    func evictedMidBatchIsCaughtAndRolledBack() async throws {
        let src = makeTempDir()
        let dest = makeTempDir()
        defer {
            try? FileManager.default.removeItem(at: src)
            try? FileManager.default.removeItem(at: dest)
        }
        let first = src.appendingPathComponent("P01.mp4")
        let second = src.appendingPathComponent("P02.mp4")
        try write(first, "one")
        try write(second, "two")

        let reader = ScriptedLooks(target: "P02.mp4", answers: [false, true])
        let machinery = CopyMachinery()
        var caught: CopyMachinery.CopyError?
        do {
            _ = try await machinery.copy(
                urls: [first, second], into: dest,
                projectID: UUID(), projectName: "Probe",
                acceptedExtensions: ["mp4"],
                isDataless: reader.check
            )
        } catch let err as CopyMachinery.CopyError {
            caught = err
        }
        guard case .sourceNotDownloaded(let count) = try #require(caught) else {
            Issue.record("expected .sourceNotDownloaded, got \(String(describing: caught))")
            return
        }
        #expect(count == 1)
        #expect(filesUnder(dest).isEmpty, "rollback left \(filesUnder(dest))")
        #expect(machinery.inFlight == nil)
    }

    @Test("a local file drop is unchanged: copied, not refused")
    func localFileStillCopies() async throws {
        let src = makeTempDir()
        let dest = makeTempDir()
        defer {
            try? FileManager.default.removeItem(at: src)
            try? FileManager.default.removeItem(at: dest)
        }
        let file = src.appendingPathComponent("P01.m4a")
        try write(file, "local")

        // The real reader, not an injected one: a file we just wrote is local.
        #expect(CopyMachinery.isDataless(file) == false)
        let copied = try await CopyMachinery().copy(
            urls: [file], into: dest,
            projectID: UUID(), projectName: "Probe",
            acceptedExtensions: ["m4a"]
        )
        #expect(copied.map(\.lastPathComponent) == ["P01.m4a"])
    }

    @Test("the refusal has a sentence and a key, never the enum-index fallback")
    func refusalReadsAsASentence() {
        let err = CopyMachinery.CopyError.sourceNotDownloaded(count: 2)
        let shown = err.localizedDescription
        #expect(!shown.isEmpty)
        #expect(!shown.contains("CopyError error"))
        #expect(err.localeKey == "desktop.chrome.copySourceNotDownloaded")
    }
}

/// Answers for `target` in the order given — the first look is the planning
/// pass, the second the copy loop's — repeating the last answer after that.
/// Every other URL is local.
private final class ScriptedLooks: @unchecked Sendable {
    private let target: String
    private let answers: [Bool]
    private var looks = 0
    private let lock = NSLock()

    init(target: String, answers: [Bool]) {
        self.target = target
        self.answers = answers
    }

    var check: @Sendable (URL) -> Bool {
        { [self] url in
            guard url.lastPathComponent == target else { return false }
            lock.lock(); defer { lock.unlock() }
            let answer = answers[min(looks, answers.count - 1)]
            looks += 1
            return answer
        }
    }
}
