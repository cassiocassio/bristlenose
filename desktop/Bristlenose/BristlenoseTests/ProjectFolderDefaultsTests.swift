import Foundation
import Testing

@testable import Bristlenose

// Where the next New Project panel opens.
//
// Two doors made this decision independently — the sidebar and the import
// window — and both hardcoded `~/Documents`, so a researcher who keeps every
// study in `~/Work/Studies` was sent to Documents every single time, by both.
// The duplication is the reason this type exists; the remembering is what
// makes it worth existing.
//
// Uses an isolated `UserDefaults` suite throughout: these tests must never
// read or write the real preference, or running the suite would move where the
// developer's own next project lands.

@Suite("Where new projects are proposed")
struct ProjectFolderDefaultsTests {

    private func scratchDefaults() -> UserDefaults {
        // A unique suite per test, so ordering cannot leak state between them.
        UserDefaults(suiteName: "bn-test-\(UUID().uuidString)")!
    }

    private var documents: URL? {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first
    }

    @Test("With nothing remembered, the first proposal is Documents")
    func fallsBackToDocuments() {
        let defaults = scratchDefaults()
        #expect(ProjectFolderDefaults.suggestedDirectory(defaults: defaults) == documents)
    }

    @Test("It proposes the parent of the last project, not the project itself")
    func remembersTheParent() throws {
        // The researcher chose a place to put a study. Starting the next panel
        // *inside* last week's project is the more annoying of the two
        // mistakes, so the parent is what gets kept.
        let defaults = scratchDefaults()
        let root = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("bn-folder-\(UUID().uuidString)", isDirectory: true)
        let project = root.appendingPathComponent("Ikea study", isDirectory: true)
        try FileManager.default.createDirectory(at: project, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }

        ProjectFolderDefaults.remember(projectFolder: project, defaults: defaults)

        let suggested = try #require(ProjectFolderDefaults.suggestedDirectory(defaults: defaults))
        #expect(suggested.standardizedFileURL == root.standardizedFileURL)
        #expect(suggested.lastPathComponent != "Ikea study")
    }

    @Test("A remembered folder that has gone away does not strand the panel")
    func fallsBackWhenTheFolderVanished() {
        // An external drive unplugged, a folder renamed, a study archived.
        // Opening a panel at a path that no longer exists reads as the app
        // being broken rather than as a disk being absent.
        let defaults = scratchDefaults()
        let gone = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("bn-absent-\(UUID().uuidString)/inner", isDirectory: true)
        ProjectFolderDefaults.remember(projectFolder: gone, defaults: defaults)

        #expect(ProjectFolderDefaults.suggestedDirectory(defaults: defaults) == documents)
    }

    @Test("A file where a folder was remembered is refused too")
    func fallsBackWhenThePathIsNotADirectory() throws {
        // `fileExists` alone would accept this and hand a panel a file to open
        // *at*, which AppKit does not do anything sensible with.
        let defaults = scratchDefaults()
        let root = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("bn-file-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let file = root.appendingPathComponent("notafolder.txt")
        try Data("x".utf8).write(to: file)

        // Remembering `<root>/notafolder.txt/child` stores `notafolder.txt`.
        ProjectFolderDefaults.remember(
            projectFolder: file.appendingPathComponent("child"), defaults: defaults)

        #expect(ProjectFolderDefaults.suggestedDirectory(defaults: defaults) == documents)
    }

    @Test("The root directory is never remembered")
    func refusesRoot() {
        // A project created at `/Something` would otherwise store `/`, and
        // every future panel would open at the volume root — technically a
        // directory, and a hostile place to start.
        let defaults = scratchDefaults()
        ProjectFolderDefaults.remember(
            projectFolder: URL(fileURLWithPath: "/Something", isDirectory: true),
            defaults: defaults)
        #expect(ProjectFolderDefaults.preferred(defaults: defaults) == nil)
    }
}
