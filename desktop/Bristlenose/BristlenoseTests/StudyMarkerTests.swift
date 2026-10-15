import Foundation
import Testing
@testable import Bristlenose

/// The study marker and the drop decision that reads it
/// (`docs/design-project-identity.md` §3, §9).
@MainActor
@Suite("Study marker and the drop decision")
struct StudyMarkerTests {

    private func folder() throws -> URL {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-study-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    /// The bytes Python's `study_marker.write` produces, verbatim in shape.
    /// `tests/test_study_identity.py` reads the app's re-mint back the other way.
    private func writePythonMarker(_ dir: URL, id: String) throws {
        let json = """
        {
          "schema": 1,
          "study_id": "\(id)",
          "minted_at": "2026-10-15T10:00:00+00:00",
          "minted_by": "serve",
          "copied_from": null
        }
        """
        let target = StudyMarker.url(forFolder: dir)
        try FileManager.default.createDirectory(
            at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
        try json.write(to: target, atomically: true, encoding: .utf8)
    }

    @Test func readsWhatPythonWrites() throws {
        let dir = try folder()
        defer { try? FileManager.default.removeItem(at: dir) }
        let id = UUID().uuidString.lowercased()
        try writePythonMarker(dir, id: id)
        #expect(StudyMarker.read(folder: dir) == id)
    }

    @Test func aMarkerOfAnotherSchemaIsNotRead() throws {
        let dir = try folder()
        defer { try? FileManager.default.removeItem(at: dir) }
        let target = StudyMarker.url(forFolder: dir)
        try FileManager.default.createDirectory(
            at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
        try #"{"schema": 2, "study_id": "6f1c2b9e-0000-4000-8000-000000000000"}"#
            .write(to: target, atomically: true, encoding: .utf8)
        #expect(StudyMarker.read(folder: dir) == nil)
    }

    @Test func aReMintGivesANewIdAndRecordsTheOriginal() throws {
        let dir = try folder()
        defer { try? FileManager.default.removeItem(at: dir) }
        let original = UUID().uuidString.lowercased()
        try writePythonMarker(dir, id: original)
        let fresh = try StudyMarker.remint(folder: dir, copiedFrom: original)
        #expect(fresh != original)
        #expect(StudyMarker.read(folder: dir) == fresh)
        let data = try Data(contentsOf: StudyMarker.url(forFolder: dir))
        let object = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
        #expect(object["copied_from"] as? String == original)
        #expect(object["minted_by"] as? String == "app")
    }

    // ── The drop decision ───────────────────────────────────────────────────

    private let study = "6f1c2b9e-1111-4000-8000-000000000000"

    @Test func noMarkerOrNoHolderIsANewProject() {
        let row = StudyDropMatch.Candidate(id: UUID(), studyID: "other", path: "/a")
        #expect(StudyDropMatch.resolve(droppedStudyID: nil, candidates: [row],
                                       folderExists: { _ in true }) == .none)
        #expect(StudyDropMatch.resolve(droppedStudyID: study, candidates: [row],
                                       folderExists: { _ in true }) == .none)
    }

    @Test func aHolderWhoseFolderIsGoneMeansThisIsItsFolderMoved() {
        let id = UUID()
        let row = StudyDropMatch.Candidate(id: id, studyID: study, path: "/Old/Talismanic")
        #expect(StudyDropMatch.resolve(droppedStudyID: study, candidates: [row],
                                       folderExists: { _ in false }) == .moved(id))
    }

    @Test func aHolderStillInPlaceMeansThisIsACopy() {
        let id = UUID()
        let row = StudyDropMatch.Candidate(id: id, studyID: study, path: "/Studies/Talismanic")
        #expect(StudyDropMatch.resolve(droppedStudyID: study, candidates: [row],
                                       folderExists: { $0 == "/Studies/Talismanic" }) == .copy(of: id))
    }

    // ── Locate… ─────────────────────────────────────────────────────────────

    private func analysed(_ dir: URL) throws {
        let manifest = dir.appendingPathComponent("bristlenose-output/.bristlenose/pipeline-manifest.json")
        try FileManager.default.createDirectory(
            at: manifest.deletingLastPathComponent(), withIntermediateDirectories: true)
        try "{}".write(to: manifest, atomically: true, encoding: .utf8)
    }

    @Test func locateRefusesAFolderHoldingAnotherStudy() throws {
        let dir = try folder()
        defer { try? FileManager.default.removeItem(at: dir) }
        try analysed(dir)
        let mine = UUID().uuidString.lowercased()
        try writePythonMarker(dir, id: UUID().uuidString.lowercased())
        #expect(LocateFlow.verdict(url: dir, expectedStudyID: mine) == .differentStudy)
    }

    @Test func locateAcceptsItsOwnStudyAndAnyFolderWhenAnIdIsUnknown() throws {
        let dir = try folder()
        defer { try? FileManager.default.removeItem(at: dir) }
        try analysed(dir)
        #expect(LocateFlow.verdict(url: dir, expectedStudyID: "x") == .thisStudy)  // no marker
        let mine = UUID().uuidString.lowercased()
        try writePythonMarker(dir, id: mine)
        #expect(LocateFlow.verdict(url: dir, expectedStudyID: mine) == .thisStudy)
        #expect(LocateFlow.verdict(url: dir, expectedStudyID: nil) == .thisStudy)
        let bare = try folder()
        defer { try? FileManager.default.removeItem(at: bare) }
        #expect(LocateFlow.verdict(url: bare, expectedStudyID: mine) == .notAnalysed)
    }

    @Test func locateCannotPassAMarkerItMayNotRead() throws {
        let dir = try folder()
        defer { try? FileManager.default.removeItem(at: dir) }
        try analysed(dir)
        try writePythonMarker(dir, id: "not-a-uuid")  // exists, unreadable as an id
        #expect(LocateFlow.verdict(url: dir, expectedStudyID: "x", granted: false) == .unverified)
        #expect(LocateFlow.verdict(url: dir, expectedStudyID: "x", granted: true) == .thisStudy)
    }

    @Test func anotherSpellingOfAHeldFolderIsTheSameFolder() throws {
        let root = try folder()
        defer { try? FileManager.default.removeItem(at: root) }
        let real = root.appendingPathComponent("Talismanic")
        let copy = root.appendingPathComponent("Talismanic copy")
        let link = root.appendingPathComponent("Shortcut")
        for dir in [real, copy] {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        }
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: real)
        let index = ProjectIndex(fileURL: root.appendingPathComponent("projects.json"))
        let project = index.addProject(name: "Talismanic", path: real.path)
        #expect(index.findSameFolder(link)?.id == project.id)
        #expect(index.findSameFolder(copy) == nil, "a copy is not the same folder")
    }

    /// Two rows created in the same second (projects.json keeps whole seconds):
    /// whichever is captured first, the same folder keeps the original id.
    @Test func aCopyTieBreaksTheSameWayWhicheverIsSeenFirst() throws {
        let root = try folder()
        defer { try? FileManager.default.removeItem(at: root) }
        let one = root.appendingPathComponent("One"), two = root.appendingPathComponent("Two")
        for dir in [one, two] {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        }
        let id = UUID().uuidString.lowercased()
        let same = Date(timeIntervalSince1970: 1_800_000_000)
        let fixedA = UUID(), fixedB = UUID()

        func keeperAfter(capturingOneFirst: Bool) throws -> String {
            try writePythonMarker(one, id: id)
            try writePythonMarker(two, id: id)
            let index = ProjectIndex(fileURL: root.appendingPathComponent(UUID().uuidString + ".json"))
            index.projects = [
                Project(id: fixedA, name: "One", path: one.path, createdAt: same),
                Project(id: fixedB, name: "Two", path: two.path, createdAt: same),
            ]
            let order = capturingOneFirst ? [(fixedA, one), (fixedB, two)] : [(fixedB, two), (fixedA, one)]
            for (pid, dir) in order { index.captureStudyID(id: pid, folder: dir) }
            return StudyMarker.read(folder: one) == id ? "One" : "Two"
        }
        #expect(try keeperAfter(capturingOneFirst: true) == keeperAfter(capturingOneFirst: false))
    }

    // ── The index ───────────────────────────────────────────────────────────

    /// The upgrade order: the original was served (marker minted) but its
    /// row never learned the id, then a Finder copy was dropped and captured
    /// first. The original must keep its identity; the copy is re-minted.
    /// Found by review, 15 Oct 2026.
    @Test func theCopyIsReMintedEvenWhenItIsCapturedFirst() throws {
        let root = try folder()
        defer { try? FileManager.default.removeItem(at: root) }
        let original = root.appendingPathComponent("Talismanic")
        let copy = root.appendingPathComponent("Talismanic copy")
        for dir in [original, copy] {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        }
        let id = UUID().uuidString.lowercased()
        try writePythonMarker(original, id: id)
        try writePythonMarker(copy, id: id)

        let index = ProjectIndex(fileURL: root.appendingPathComponent("projects.json"))
        let a = index.addProject(name: "Talismanic", path: original.path)
        Thread.sleep(forTimeInterval: 0.01)  // the copy joins the sidebar later
        let b = index.addProject(name: "Talismanic copy", path: copy.path)
        #expect(index.captureStudyID(id: b.id, folder: copy) == id)  // nothing to compare yet
        #expect(index.captureStudyID(id: a.id, folder: original) == id, "the original lost its id")
        let copyID = index.projects.first(where: { $0.id == b.id })?.studyID
        #expect(copyID != nil && copyID != id, "the copy kept the original's identity")
        #expect(StudyMarker.read(folder: copy) == copyID)
        #expect(StudyMarker.read(folder: original) == id)
    }

    @Test func anAvailabilityRefreshLearnsTheStudyID() throws {
        let root = try folder()
        defer { try? FileManager.default.removeItem(at: root) }
        let study = root.appendingPathComponent("Talismanic")
        try FileManager.default.createDirectory(at: study, withIntermediateDirectories: true)
        let index = ProjectIndex(fileURL: root.appendingPathComponent("projects.json"))
        let project = index.addProject(name: "Talismanic", path: study.path)
        #expect(index.projects.first?.studyID == nil)
        let id = UUID().uuidString.lowercased()
        try writePythonMarker(study, id: id)  // the first run minted it
        index.refreshAvailability()
        #expect(index.projects.first(where: { $0.id == project.id })?.studyID == id)
    }

    @Test func theSecondProjectToCarryAnIdIsReMinted() throws {
        let root = try folder()
        defer { try? FileManager.default.removeItem(at: root) }
        let original = root.appendingPathComponent("Talismanic")
        let copy = root.appendingPathComponent("Talismanic copy")
        for dir in [original, copy] {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        }
        let id = UUID().uuidString.lowercased()
        try writePythonMarker(original, id: id)
        try writePythonMarker(copy, id: id)

        let index = ProjectIndex(fileURL: root.appendingPathComponent("projects.json"))
        let a = index.addProject(name: "Talismanic", path: original.path)
        let b = index.addProject(name: "Talismanic copy", path: copy.path)
        #expect(index.captureStudyID(id: a.id, folder: original) == id)
        let second = index.captureStudyID(id: b.id, folder: copy)
        #expect(second != nil && second != id, "a copy kept its original's identity")
        #expect(StudyMarker.read(folder: copy) == second)
        #expect(StudyMarker.read(folder: original) == id, "the original was re-minted")
    }
}
