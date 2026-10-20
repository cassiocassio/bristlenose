import Foundation
import Testing

@testable import Bristlenose

/// A discussion guide still in the cloud (dataless) must never reach
/// `copyItem`: the copy waits with no timeout, and `install` runs on the main
/// actor, so it would freeze the whole app. The same defect as R45's drop
/// path (`CopyMachineryDatalessTests`).
///
/// No test can make a real cloud placeholder, so these inject the reader and
/// use local files. A local file copies instantly, which is what makes them
/// bite: without the check the install succeeds and the test goes red.
struct DiscussionGuideDatalessTests {

    private func makeTempDir() -> URL {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("guide-dataless-\(UUID().uuidString)", isDirectory: true)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    @Test("a guide still in the cloud is refused, and no guide folder appears")
    func offloadedGuideIsRefused() throws {
        let src = makeTempDir()
        let root = makeTempDir()
        defer {
            try? FileManager.default.removeItem(at: src)
            try? FileManager.default.removeItem(at: root)
        }
        let guide = src.appendingPathComponent("guide.docx")
        try Data("guide".utf8).write(to: guide)

        #expect(throws: DiscussionGuide.InstallError.notDownloaded) {
            try DiscussionGuide.install(guide, into: root, isDataless: { _ in true })
        }
        #expect(try FileManager.default.contentsOfDirectory(atPath: root.path).isEmpty)
    }

    @Test("choosing an offloaded guide again leaves the installed one as it was")
    func offloadedReplacementKeepsTheInstalledGuide() throws {
        let src = makeTempDir()
        let root = makeTempDir()
        defer {
            try? FileManager.default.removeItem(at: src)
            try? FileManager.default.removeItem(at: root)
        }
        let guide = src.appendingPathComponent("guide.md")
        try Data("# old".utf8).write(to: guide)
        let installed = try DiscussionGuide.install(guide, into: root, isDataless: { _ in false })

        try Data("# new".utf8).write(to: guide)
        #expect(throws: DiscussionGuide.InstallError.notDownloaded) {
            try DiscussionGuide.install(guide, into: root, isDataless: { _ in true })
        }
        #expect(try String(contentsOf: installed, encoding: .utf8) == "# old")
        let folder = installed.deletingLastPathComponent()
        #expect(try FileManager.default.contentsOfDirectory(atPath: folder.path) == ["guide.md"],
                "a refused replace left a staged copy behind")
    }

    @Test("a local guide still installs, through the real reader")
    func localGuideInstalls() throws {
        let src = makeTempDir()
        let root = makeTempDir()
        defer {
            try? FileManager.default.removeItem(at: src)
            try? FileManager.default.removeItem(at: root)
        }
        let guide = src.appendingPathComponent("guide.txt")
        try Data("questions".utf8).write(to: guide)

        let dest = try DiscussionGuide.install(guide, into: root)
        #expect(try String(contentsOf: dest, encoding: .utf8) == "questions")
    }

    @Test("the refusal carries a sentence and its key")
    func refusalHasASentenceAndAKey() {
        let err = DiscussionGuide.InstallError.notDownloaded
        #expect(!(err.errorDescription ?? "").isEmpty)
        #expect(!err.localizedDescription.contains("InstallError error"))
        #expect(err.localeKey == "desktop.discussion.guideNotDownloaded")
    }
}
