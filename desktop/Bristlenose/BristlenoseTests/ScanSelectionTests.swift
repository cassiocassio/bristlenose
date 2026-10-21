import Foundation
import Testing
@testable import Bristlenose

/// The Mac counts a study's interviews with `run`'s own file selection
/// (decision #111, 21 Oct 2026).
///
/// THE REGRESSION. The watcher listed the top level only, so a study whose
/// recordings sat in per-participant folders (`p1/interview.mp4`) published
/// `ingestableFileCount: 0`: the detail pane said "Drag Interviews Here" and the
/// sidebar offered no Analyse, over a folder `run` would analyse in full — and,
/// since decision #82, over a serve page saying "Not analysed yet."
@Suite("ProjectFolderWatcher counts what run would find")
struct ProjectFolderWatcherScanDepthTests {

    final class Box: @unchecked Sendable { var state: UnanalysedState? }

    private func makeFolder(_ files: [String]) throws -> URL {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-scan-depth-\(UUID().uuidString)", isDirectory: true)
        for rel in files {
            let url = dir.appendingPathComponent(rel)
            try FileManager.default.createDirectory(
                at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try Data("x".utf8).write(to: url)
        }
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    private func waitUntil(_ deadline: Duration = .seconds(30),
                           _ condition: @escaping () -> Bool) async -> Bool {
        let clock = ContinuousClock()
        let end = clock.now + deadline
        while clock.now < end {
            if condition() { return true }
            try? await Task.sleep(for: .milliseconds(50))
        }
        return condition()
    }

    @Test func aSubfolderOnlyStudyIsCountedNotEmpty() async throws {
        let root = try makeFolder(["p1/interview.mp4", "p2/interview.m4a", "p2/chat.txt"])
        defer { try? FileManager.default.removeItem(at: root) }
        let lease = try ProjectBookmarkLease(bookmarkData: root.bookmarkData(options: .withSecurityScope))
        let box = Box()
        let watcher = ProjectFolderWatcher(
            projectID: UUID(), lease: lease, initialKnownBasenames: [],
            onChange: { box.state = $0 }
        )
        defer { watcher.stop() }
        #expect(await waitUntil { box.state != nil }, "the watcher never published its first scan")
        #expect(box.state?.ingestableFileCount == 2,
                "two recordings in participant folders; got \(box.state?.ingestableFileCount ?? -1)")
        #expect(box.state?.hasIngestableFiles == true)
    }
}

/// The Swift side of `tests/fixtures/scan-selection-contract.json`; the Python
/// side is `tests/test_scan_selection_contract.py`, against `run`'s own
/// `iter_scanned_files`. A failure here means the Mac's walk and `run`'s
/// disagree: fix the walk that is wrong, not the fixture.
@Suite("Scan selection contract")
struct ScanSelectionContractTests {

    private func contract() throws -> [String: Any] {
        // <repo>/desktop/Bristlenose/BristlenoseTests/<this file>
        let repo = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent()
        let data = try Data(contentsOf: repo.appendingPathComponent(
            "tests/fixtures/scan-selection-contract.json"))
        return try #require(JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    private func build(_ layout: [String: Any], in base: URL) throws -> URL {
        let fm = FileManager.default
        let root = base.appendingPathComponent(layout["root_name"] as? String ?? "study", isDirectory: true)
        try fm.createDirectory(at: root, withIntermediateDirectories: true)
        for rel in layout["dirs"] as? [String] ?? [] {
            try fm.createDirectory(at: root.appendingPathComponent(rel), withIntermediateDirectories: true)
        }
        func touch(_ url: URL) throws {
            try fm.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try Data("x".utf8).write(to: url)
        }
        for rel in layout["files"] as? [String] ?? [] { try touch(root.appendingPathComponent(rel)) }
        for rel in layout["outside"] as? [String] ?? [] {
            try touch(base.appendingPathComponent("outside").appendingPathComponent(rel))
        }
        for link in layout["links"] as? [[String: String]] ?? [] {
            let at = root.appendingPathComponent(link["at"]!)
            try fm.createDirectory(at: at.deletingLastPathComponent(), withIntermediateDirectories: true)
            try fm.createSymbolicLink(atPath: at.path, withDestinationPath: link["to"]!)
        }
        return root
    }

    @Test func theDepthIsRunsDepth() throws {
        #expect(try contract()["max_depth"] as? Int == ScanSelection.maxDepth)
    }

    @Test func everyLayoutSelectsWhatRunSelects() throws {
        let layouts = try #require(try contract()["layouts"] as? [[String: Any]])
        #expect(layouts.count >= 8, "the contract lost its layouts")
        for layout in layouts {
            let name = layout["name"] as? String ?? "?"
            let base = FileManager.default.temporaryDirectory
                .appendingPathComponent("bn-scan-contract-\(UUID().uuidString)", isDirectory: true)
            defer { try? FileManager.default.removeItem(at: base) }
            let root = try build(layout, in: base)
            let home = (layout["home"] as? String).map {
                root.appendingPathComponent($0).standardizedFileURL.path
            } ?? UserHome.path

            let rootPath = root.path
            func relative(_ urls: [URL]) -> [String] {
                urls.map { String($0.path.dropFirst(rootPath.count + 1)) }.sorted()
            }
            let selected = ScanSelection.scannedFiles(under: root, home: home)
            #expect(relative(selected) == (layout["selected"] as? [String] ?? []).sorted(),
                    "\(name): selection")
            #expect(relative(selected.filter(ScanSelection.isReadable))
                    == (layout["readable"] as? [String] ?? []).sorted(),
                    "\(name): readable")
        }
    }

    @Test func theRootsRunRefusesAreRefused() throws {
        let cases = try #require(try contract()["refusals"] as? [[String: Any]])
        #expect(!cases.isEmpty)
        for c in cases {
            let path = try #require(c["path"] as? String)
            let refused = try #require(c["refused"] as? Bool)
            #expect((ScanSelection.refusal(for: URL(fileURLWithPath: path)) != nil) == refused, "\(path)")
        }
    }
}

/// The presenter rescans for a change anywhere the selection could see it, and
/// for nothing a run writes into its own output.
@Suite("ProjectFolderWatcher scan scope")
struct ProjectFolderWatcherScopeTests {
    private let root = URL(fileURLWithPath: "/p/study", isDirectory: true)

    /// Nothing under `/p` exists, so "is it an existing file" answers no unless
    /// a test says otherwise.
    private func rescans(_ rel: String, isFile: Bool = false) -> Bool {
        ProjectFolderWatcher.mayChangeTheCount(
            root.appendingPathComponent(rel), root: root, isRegularFile: { _ in isFile })
    }

    @Test func aRecordingInAParticipantFolderRescans() {
        #expect(rescans("a.mp4", isFile: true))
        #expect(rescans("p3"))
        #expect(rescans("p3/interview.mp4", isFile: true))
        #expect(rescans("week1/zoom1/video.mp4", isFile: true))
    }

    @Test func aFolderWithADotInItsNameRescans() {
        // Dropped, renamed or deleted: `P1.Smith` has an "extension", and a
        // deleted folder cannot be asked what it was.
        #expect(rescans("P1.Smith"))
        #expect(rescans("Round 1.5/P1.Smith"))
    }

    @Test func whatRunNeverReadsDoesNot() {
        #expect(!rescans("notes.xlsx", isFile: true), "an existing file of another kind")
        #expect(!rescans("a/b/c.xlsx"), "deepest level: only a counted kind")
        #expect(!rescans("a/b/c/d.mp4", isFile: true), "deeper than run looks")
        #expect(!rescans("bristlenose-output/x.mp4", isFile: true))
        #expect(!rescans("bristlenose-output/.bristlenose/bristlenose.db", isFile: true))
        #expect(!rescans("p1/bristlenose-output/x.mp4", isFile: true))
        #expect(!rescans(".claude/a.mp4", isFile: true))
        #expect(!rescans("p1/._a.mp4", isFile: true))
        #expect(!rescans("Discussion guide/guide.docx", isFile: true))
        #expect(!rescans("bristlenose.db", isFile: true))
        #expect(!ProjectFolderWatcher.mayChangeTheCount(
            URL(fileURLWithPath: "/p/other/a.mp4"), root: root), "outside the folder")
        #expect(!ProjectFolderWatcher.mayChangeTheCount(root, root: root), "the folder itself")
    }
}

/// `newFiles` against a database that records one file per session.
@Suite("ProjectFolderWatcher new files")
struct ProjectFolderWatcherNewFilesTests {
    private let root = URL(fileURLWithPath: "/p/study", isDirectory: true)

    private func new(_ files: [String], ingested: Set<String>, known: Set<String> = []) -> [String] {
        ProjectFolderWatcher.newFiles(
            readable: files.map { root.appendingPathComponent($0) },
            root: root, ingested: ingested, known: known
        ).map { String($0.path.dropFirst(root.path.count + 1)) }
    }

    @Test func aSessionsOtherFilesAreNotUnanalysed() {
        // `source_files` holds `files[0]` only: the audio beside an analysed
        // Zoom video must not read "+1 unanalysed" after every run.
        #expect(new(["p2/zoom1/audio123.m4a", "p2/zoom1/video123.mp4"],
                    ingested: ["video123.mp4"]).isEmpty)
    }

    @Test func aNewParticipantFolderIsUnanalysed() {
        #expect(new(["p1/interview.mp4", "p3/session.mp4"], ingested: ["interview.mp4"])
                == ["p3/session.mp4"])
    }

    @Test func atTheTopLevelEachFileStandsAlone() {
        #expect(new(["a.mp4", "b.mp4"], ingested: ["a.mp4"]) == ["b.mp4"])
        #expect(new(["a.mp4", "b.mp4"], ingested: [], known: ["b.mp4"]) == ["a.mp4"])
    }

    @Test func aNeverAnalysedStudyListsEverything() {
        #expect(new(["p1/a.mp4", "p2/b.m4a"], ingested: []) == ["p1/a.mp4", "p2/b.m4a"])
    }
}
