import Foundation
import Testing
@testable import Bristlenose

/// `projects.json` that fails to decode must not be overwritten by the next
/// save. `load()` left `projects = []` on a decode error and the first
/// `save()` after it — any add, rename or reorder — wrote an empty list over
/// the researcher's whole sidebar.
@MainActor
@Suite("ProjectIndex damaged file")
struct ProjectIndexDamagedFileTests {

    @Test func aFileThatFailedToDecodeIsPreservedNotOverwritten() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-index-damaged-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let fileURL = dir.appendingPathComponent("projects.json")
        let damaged = Data("{\"version\":\"1.0\",\"projects\":[{\"id\":\"not-a-uuid\"".utf8)
        try damaged.write(to: fileURL)

        let index = ProjectIndex(fileURL: fileURL)
        index.addProject(name: "After", path: "/tmp/after")   // triggers save()

        // The damaged bytes must still exist somewhere in the directory — either
        // untouched at the original path, or set aside under a sibling name.
        let files = try FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil)
        let preserved = files.contains { (try? Data(contentsOf: $0)) == damaged }
        #expect(preserved, "the undecodable projects.json was overwritten; files now: \(files.map(\.lastPathComponent))")
    }
}
