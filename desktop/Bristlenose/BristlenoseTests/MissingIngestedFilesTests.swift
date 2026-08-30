import Foundation
import Testing
@testable import Bristlenose

/// Tests for `ProjectFolderWatcher.missingIngestedFiles`.
///
/// THE REGRESSION. On 30 Aug 2026 a project with all three of its recordings
/// present and correct in an `interviews/` subfolder displayed
/// "⚠ 3 missing — These files are no longer in the project folder."
///
/// The comparison diffed ingested *basenames* against the basenames returned by
/// `enumerateTopLevelEligible`, which walks the top level only. Python's
/// `discover_files` descends up to `_MAX_SCAN_DEPTH = 3`. So for any project
/// organised into subfolders — which is how researchers actually keep them —
/// nothing matched and everything read as gone.
///
/// Both probes are injected, so these run without touching a filesystem.
struct MissingIngestedFilesTests {

    private static let inSubfolder = "/p/interviews/Screen Recording 2026-01-27.mov"
    private static let atTopLevel = "/p/Interview One.mov"
    private static let root = URL(fileURLWithPath: "/p")

    // MARK: The regression

    /// A file in a subfolder is present. It must not be called missing.
    @Test func fileInASubfolderIsNotMissing() {
        let missing = ProjectFolderWatcher.missingIngestedFiles(
            ingestedPaths: [Self.inSubfolder],
            projectRoot: Self.root,
            exists: { $0 == Self.inSubfolder },
            evicted: { _ in false },
            locatable: { _, _ in false }
        )
        #expect(missing.isEmpty)
    }

    /// The reported shape of the incident: three files, all present, all in a
    /// subfolder, all previously reported gone.
    @Test func awholeSubfolderOfPresentFilesIsNotMissing() {
        let paths: Set<String> = [
            "/p/interviews/Screen Recording 2026-01-27 at 23.37.37.mov",
            "/p/interviews/Screen Recording 2026-01-28 at 00.13.56.mov",
            "/p/interviews/Screen Recording 2026-01-28 at 00.18.49.mov",
        ]
        let missing = ProjectFolderWatcher.missingIngestedFiles(
            ingestedPaths: paths,
            projectRoot: Self.root,
            exists: { paths.contains($0) },
            evicted: { _ in false },
            locatable: { _, _ in false }
        )
        #expect(missing.isEmpty)
    }

    // MARK: Still detects a genuine loss

    /// The alarm has to keep working, or the fix is just a mute button.
    @Test func aDeletedFileIsStillMissing() {
        let missing = ProjectFolderWatcher.missingIngestedFiles(
            ingestedPaths: [Self.inSubfolder],
            projectRoot: Self.root,
            exists: { _ in false },
            evicted: { _ in false },
            locatable: { _, _ in false }
        )
        #expect(missing.map(\.path) == [Self.inSubfolder])
    }

    @Test func onlyTheAbsentOnesAreReported() {
        let present = Self.atTopLevel
        let missing = ProjectFolderWatcher.missingIngestedFiles(
            ingestedPaths: [present, Self.inSubfolder],
            projectRoot: Self.root,
            exists: { $0 == present },
            evicted: { _ in false },
            locatable: { _, _ in false }
        )
        #expect(missing.map(\.path) == [Self.inSubfolder])
    }

    // MARK: The eviction rescue stays load-bearing

    /// An iCloud-evicted placeholder fails `exists` but is logically present.
    /// Without this skip, "not downloaded yet" reads as "you deleted it".
    @Test func evictedFilesAreNotMissing() {
        let missing = ProjectFolderWatcher.missingIngestedFiles(
            ingestedPaths: [Self.inSubfolder],
            projectRoot: Self.root,
            exists: { _ in false },
            evicted: { _ in true },
            locatable: { _, _ in false }
        )
        #expect(missing.isEmpty)
    }

    // MARK: Ordering and edges

    /// Sorted by last path component for stable `Equatable` comparison — an
    /// unstable order would republish state on every scan.
    @Test func resultIsSortedByFilename() {
        let paths: Set<String> = ["/p/b/zebra.mov", "/p/a/apple.mov", "/p/c/mango.mov"]
        let missing = ProjectFolderWatcher.missingIngestedFiles(
            ingestedPaths: paths,
            projectRoot: Self.root,
            exists: { _ in false },
            evicted: { _ in false },
            locatable: { _, _ in false }
        )
        #expect(missing.map(\.lastPathComponent) == ["apple.mov", "mango.mov", "zebra.mov"])
    }

    /// A project with no DB yields no paths, which must mean "nothing missing"
    /// rather than an empty-set alarm. `SourceFilesReader` also returns empty on
    /// SQLITE_BUSY, so this is the concurrent-write case too.
    @Test func noIngestedPathsMeansNothingMissing() {
        let missing = ProjectFolderWatcher.missingIngestedFiles(
            ingestedPaths: [],
            projectRoot: Self.root,
            exists: { _ in false },
            evicted: { _ in false },
            locatable: { _, _ in false }
        )
        #expect(missing.isEmpty)
    }

    // MARK: The relocation case — the regression the first fix introduced

    /// `source_files.path` is written once at import and NEVER corrected, while
    /// `ProjectIndex.refreshAvailability` and `relocateProject` rewrite
    /// `project.path` whenever the folder moves or is re-Located. So renaming a
    /// study folder makes every recorded path stale at once.
    ///
    /// Checking only the recorded path would have swapped a subfolder false
    /// alarm for a relocation one — and researchers move and rename project
    /// folders far more often than they nest recordings.
    @Test func aMovedProjectFolderDoesNotMakeEveryFileMissing() {
        let recorded = "/old/place/interviews/a.mov"
        let missing = ProjectFolderWatcher.missingIngestedFiles(
            ingestedPaths: [recorded],
            projectRoot: URL(fileURLWithPath: "/new/place"),
            exists: { _ in false },          // the recorded path is stale
            evicted: { _ in false },
            locatable: { name, _ in name == "a.mov" }  // but it is under the new root
        )
        #expect(missing.isEmpty)
    }

    /// A file moved WITHIN the project is present too — same mechanism.
    @Test func aFileMovedWithinTheProjectIsNotMissing() {
        let missing = ProjectFolderWatcher.missingIngestedFiles(
            ingestedPaths: [Self.atTopLevel],
            projectRoot: Self.root,
            exists: { _ in false },
            evicted: { _ in false },
            locatable: { name, _ in name == "Interview One.mov" }
        )
        #expect(missing.isEmpty)
    }

    /// And the alarm still fires when the file is genuinely gone — not at the
    /// recorded path, and nowhere under the live root either.
    @Test func aFileFoundNowhereIsStillMissing() {
        let missing = ProjectFolderWatcher.missingIngestedFiles(
            ingestedPaths: [Self.inSubfolder],
            projectRoot: Self.root,
            exists: { _ in false },
            evicted: { _ in false },
            locatable: { _, _ in false }
        )
        #expect(missing.map(\.path) == [Self.inSubfolder])
    }

    /// The walk is only paid on a miss. On a healthy project it never runs —
    /// which is what makes an O(N) fallback acceptable on a network volume.
    @Test func theLocateWalkIsNotRunWhenTheRecordedPathResolves() {
        var walked = false
        _ = ProjectFolderWatcher.missingIngestedFiles(
            ingestedPaths: [Self.inSubfolder],
            projectRoot: Self.root,
            exists: { _ in true },
            evicted: { _ in false },
            locatable: { _, _ in walked = true; return false }
        )
        #expect(!walked)
    }
}
