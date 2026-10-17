import Foundation
import Testing
@testable import Bristlenose

/// Copy Screens puts only the open project's exported stills on the clipboard.
@Suite struct ScreensPasteboardTests {
    private func project() throws -> (URL, URL) {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("screens-pb-\(UUID().uuidString)")
        let folder = root.appendingPathComponent("bristlenose-output/screens")
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        for name in ["p1-01.jpg", "p1-02.jpg"] {
            try Data([0xFF, 0xD8]).write(to: folder.appendingPathComponent(name))
        }
        return (root, folder)
    }

    @Test func theExportedStillsInExportOrder() throws {
        let (root, folder) = try project()
        let urls = try ScreensPasteboard.fileURLs(
            dir: folder.path, files: ["p1-02.jpg", "p1-01.jpg"], projectPath: root.path).get()
        #expect(urls.map(\.lastPathComponent) == ["p1-02.jpg", "p1-01.jpg"])
    }

    @Test func nothingFromOutsideTheProjectOrOutsideTheFolder() throws {
        let (root, folder) = try project()
        let other = root.deletingLastPathComponent().appendingPathComponent("another-study").path
        #expect(refusal(dir: folder.path, files: ["p1-01.jpg"], projectPath: other) == .notTheScreensFolder)
        #expect(refusal(dir: folder.deletingLastPathComponent().path, files: ["screens/p1-01.jpg"],
                        projectPath: root.path) == .notTheScreensFolder)
        #expect(refusal(dir: folder.path, files: ["../../secret.jpg"], projectPath: root.path) == .notAPlainName)
        #expect(refusal(dir: folder.path, files: ["p1-01.jpg"], projectPath: "") == .noProject)
    }

    @Test func oneBadNameWritesNothing() throws {
        let (root, folder) = try project()
        for (bad, why) in [(".screens_manifest.json", ScreensPasteboard.Refusal.notAPlainName),
                           ("notes.txt", .notAPlainName), ("p1-09.jpg", .missingFile)] {
            #expect(refusal(dir: folder.path, files: ["p1-01.jpg", bad], projectPath: root.path) == why, "\(bad)")
        }
    }

    private func refusal(dir: String, files: [String], projectPath: String) -> ScreensPasteboard.Refusal? {
        if case .failure(let why) = ScreensPasteboard.fileURLs(dir: dir, files: files, projectPath: projectPath) {
            return why
        }
        return nil
    }
}
