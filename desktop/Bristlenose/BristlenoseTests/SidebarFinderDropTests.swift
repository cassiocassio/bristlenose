import Foundation
import Testing
@testable import Bristlenose

@Suite("Sidebar Finder drop classification")
struct SidebarFinderDropTests {
    private func directory(_ name: String) throws -> URL {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-drop-\(UUID().uuidString)")
            .appendingPathComponent(name, isDirectory: true)
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    @Test func projectsOutrankLooseMediaInAWrapper() throws {
        let root = try directory("Last year")
        defer { try? FileManager.default.removeItem(at: root.deletingLastPathComponent()) }
        let project = root.appendingPathComponent("IKEA", isDirectory: true)
        try FileManager.default.createDirectory(at: project, withIntermediateDirectories: true)
        let recording = root.appendingPathComponent("leftover.mov")
        try Data().write(to: recording)

        let result = SidebarFinderDrop.resolve([root], acceptedExtensions: ["mov"],
            folderLooksAnalysed: { ScanSelection.realPath($0.path) == ScanSelection.realPath(project.path) })
        guard case .projects(let found) = result else {
            Issue.record("Expected projects, got \(result)"); return
        }
        // FileManager can enumerate /var through /private/var. Compare actual
        // filesystem locations, retaining payload-kind and multiplicity checks.
        #expect(found.count == 1)
        #expect(found.map { ScanSelection.realPath($0.path) }
            == [ScanSelection.realPath(project.path)])
    }

    @Test func severalProjectsInOneWrapperAreAllClassifiedForRegistration() throws {
        let root = try directory("Archive")
        defer { try? FileManager.default.removeItem(at: root.deletingLastPathComponent()) }
        let projects = ["IKEA", "Museum", "Winter research"].map {
            root.appendingPathComponent($0, isDirectory: true)
        }
        for project in projects {
            try FileManager.default.createDirectory(at: project, withIntermediateDirectories: true)
        }
        try Data().write(to: root.appendingPathComponent("unprocessed.mov"))

        let result = SidebarFinderDrop.resolve([root], acceptedExtensions: ["mov"],
            folderLooksAnalysed: { candidate in
                projects.contains {
                    ScanSelection.realPath($0.path) == ScanSelection.realPath(candidate.path)
                }
            })
        guard case .projects(let found) = result else {
            Issue.record("Expected projects, got \(result)"); return
        }
        #expect(found.count == projects.count)
        #expect(Set(found.map { ScanSelection.realPath($0.path) })
            == Set(projects.map { ScanSelection.realPath($0.path) }))
    }

    @Test func mixedMediaAndIrrelevantFilesRemainASourceDrop() throws {
        let root = try directory("Raw interviews")
        defer { try? FileManager.default.removeItem(at: root.deletingLastPathComponent()) }
        try Data().write(to: root.appendingPathComponent("interview.mov"))
        try Data().write(to: root.appendingPathComponent("notes.pdf"))

        #expect(SidebarFinderDrop.resolve([root], acceptedExtensions: ["mov"],
            folderLooksAnalysed: { _ in false }) == .source)
    }

    @Test func irrelevantMaterialDoesNotBecomeAnEmptyProject() throws {
        let root = try directory("Notes")
        defer { try? FileManager.default.removeItem(at: root.deletingLastPathComponent()) }
        try Data().write(to: root.appendingPathComponent("brief.pdf"))
        #expect(SidebarFinderDrop.resolve([root], acceptedExtensions: ["mov"],
            folderLooksAnalysed: { _ in false }) == .irrelevant)
    }

    @Test func aCloudOnlyDirectoryIsRefusedBeforeItsMarkerOrListingIsProbed() throws {
        let root = try directory("Cloud-only archive")
        defer { try? FileManager.default.removeItem(at: root.deletingLastPathComponent()) }
        var probedMarker = false
        let result = SidebarFinderDrop.resolve([root], acceptedExtensions: ["mov"],
            folderLooksAnalysed: { _ in probedMarker = true; return false },
            isDataless: { _ in true })
        #expect(result == .indeterminate)
        #expect(!probedMarker)
    }

    @Test func aCloudOnlyFileIsAnOrdinaryLeafNotAReasonToRefuseTheFolder() throws {
        let root = try directory("Interviews")
        defer { try? FileManager.default.removeItem(at: root.deletingLastPathComponent()) }
        let evicted = root.appendingPathComponent("session-1.mov")
        let other = root.appendingPathComponent("brief.pdf")
        try Data().write(to: evicted)
        try Data().write(to: other)
        // Only files are cloud-only here; the folder itself is local.
        let result = SidebarFinderDrop.resolve([root], acceptedExtensions: ["mov"],
            folderLooksAnalysed: { _ in false },
            isDataless: { $0 == evicted || $0 == other })
        #expect(result == .source)
    }

    @Test func aDeepHierarchyStopsRatherThanWalkingWithoutBound() throws {
        let root = try directory("Deep")
        defer { try? FileManager.default.removeItem(at: root.deletingLastPathComponent()) }
        var cursor = root
        for level in 0...SidebarFinderDrop.maximumDepth {
            cursor = cursor.appendingPathComponent("\(level)", isDirectory: true)
            try FileManager.default.createDirectory(at: cursor, withIntermediateDirectories: true)
        }
        #expect(SidebarFinderDrop.resolve([root], acceptedExtensions: ["mov"],
            folderLooksAnalysed: { _ in false }) == .indeterminate)
    }

    @Test func mediaBeyondThePipelineScanDepthIsNotAcceptedAsANewProject() throws {
        let root = try directory("Too deep")
        defer { try? FileManager.default.removeItem(at: root.deletingLastPathComponent()) }
        var cursor = root
        for level in 1...ScanSelection.maxDepth {
            cursor = cursor.appendingPathComponent("\(level)", isDirectory: true)
            try FileManager.default.createDirectory(at: cursor, withIntermediateDirectories: true)
        }
        try Data().write(to: cursor.appendingPathComponent("interview.mov"))

        #expect(SidebarFinderDrop.resolve([root], acceptedExtensions: ["mov"],
            folderLooksAnalysed: { _ in false }) == .irrelevant)
    }

    @Test func hoverRefusesADirectBNProjectButNotAWrapperAroundOne() throws {
        let root = try directory("Wrapper")
        defer { try? FileManager.default.removeItem(at: root.deletingLastPathComponent()) }
        let project = root.appendingPathComponent("Existing study", isDirectory: true)
        try FileManager.default.createDirectory(at: project, withIntermediateDirectories: true)

        #expect(SidebarFinderDrop.quicklyContainsProject([project],
            folderLooksAnalysed: { $0.standardizedFileURL == project.standardizedFileURL }))
        #expect(!SidebarFinderDrop.quicklyContainsProject([root],
            folderLooksAnalysed: { $0.standardizedFileURL == project.standardizedFileURL }))
        #expect(!SidebarFinderDrop.quicklyContainsProject([root],
            folderLooksAnalysed: { _ in false }))
    }
}
