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
        #expect(StudyMarker.copiedFrom(folder: dir) == original)
        // The copy's Spotlight beacon must name the copy, or a search for the
        // original finds both folders.
        let beacon = try String(contentsOf: StudyMarker.beaconURL(forFolder: dir), encoding: .utf8)
        #expect(beacon == StudyMarker.beaconText(fresh))
    }

    @Test func anOriginalHasNoProvenance() throws {
        let dir = try folder()
        defer { try? FileManager.default.removeItem(at: dir) }
        try writePythonMarker(dir, id: UUID().uuidString.lowercased())
        #expect(StudyMarker.copiedFrom(folder: dir) == nil)
    }

    /// The bytes must be what Python writes (`study_marker.beacon_text`), so a
    /// beacon from either side is found by the same search.
    @Test func theBeaconMatchesPythonsForm() {
        let id = "6f1c2b9e-1111-4000-8000-000000000000"
        #expect(StudyMarker.beaconText(id) == "bristlenose-study \(id)\n")
        #expect(StudyMarker.beaconURL(forFolder: URL(fileURLWithPath: "/S/Talismanic")).path
                == "/S/Talismanic/bristlenose-output/bristlenose-study.txt")
    }

    // ── Locate's search by id (design-project-identity §13a) ────────────────

    @Test func theSearchQueryNamesTheBeaconAndTheID() throws {
        let id = "6F1C2B9E-1111-4000-8000-000000000000"
        let query = try #require(SpotlightOneShot.studyQuery(id: id))
        #expect(query == #"kMDItemFSName == "bristlenose-study.txt" && "#
                + #"kMDItemTextContent == "*6f1c2b9e-1111-4000-8000-000000000000*""#)
        #expect(NSPredicate(fromMetadataQueryString: query) != nil)
    }

    /// The id goes into a query string, so nothing but a UUID may reach it.
    @Test func anythingButAStudyIDMakesNoQuery() {
        #expect(SpotlightOneShot.studyQuery(id: "") == nil)
        #expect(SpotlightOneShot.studyQuery(id: #"x" || kMDItemFSName == "*"#) == nil)
        #expect(SpotlightOneShot.studyQuery(id: "not-a-uuid") == nil)
    }

    @Test func aBeaconHitNamesItsProjectFolder() {
        let hit = URL(fileURLWithPath: "/Volumes/Archive/Talismanic/bristlenose-output/bristlenose-study.txt")
        #expect(SpotlightOneShot.studyFolder(forBeacon: hit)?.path == "/Volumes/Archive/Talismanic")
    }

    // A moved study and a mounted backup of it both carry the beacon.
    private let live = URL(fileURLWithPath: "/Volumes/Work/Talismanic")
    private let backup = URL(fileURLWithPath: "/Volumes/Backup/Talismanic")

    @Test func oneHitIsTheAnswer() {
        #expect(SpotlightOneShot.newestStudy([(live, nil)]) == live)
    }

    @Test func amongSeveralTheOneWrittenLastIsInUse() {
        let older = Date(timeIntervalSince1970: 1_000), newer = Date(timeIntervalSince1970: 2_000)
        #expect(SpotlightOneShot.newestStudy([(backup, older), (live, newer)]) == live)
        #expect(SpotlightOneShot.newestStudy([(live, newer), (backup, older)]) == live)
    }

    /// A clone keeps its original's times, so a fresh backup ties: no guess.
    @Test func aTieOrAnUnknownTimeIsNoAnswer() {
        let same = Date(timeIntervalSince1970: 1_000)
        #expect(SpotlightOneShot.newestStudy([(backup, same), (live, same)]) == nil)
        #expect(SpotlightOneShot.newestStudy([(backup, nil), (live, same)]) == nil)
        #expect(SpotlightOneShot.newestStudy([]) == nil)
    }

    @Test func lastWrittenReadsTheStudyState() throws {
        let dir = try folder()
        defer { try? FileManager.default.removeItem(at: dir) }
        #expect(SpotlightOneShot.lastWritten(dir) == nil)
        let state = dir.appendingPathComponent("bristlenose-output/.bristlenose")
        try FileManager.default.createDirectory(at: state, withIntermediateDirectories: true)
        let manifest = state.appendingPathComponent("pipeline-manifest.json")
        try Data("{}".utf8).write(to: manifest)
        let stamp = Date(timeIntervalSince1970: 1_700_000_000)
        try FileManager.default.setAttributes([.modificationDate: stamp], ofItemAtPath: manifest.path)
        #expect(SpotlightOneShot.lastWritten(dir) == stamp)
    }

    @Test func aBeaconOutOfPlaceIsNoHit() {
        // Copied loose into a folder, or renamed: not a study's output folder.
        #expect(SpotlightOneShot.studyFolder(
            forBeacon: URL(fileURLWithPath: "/Users/r/Desktop/bristlenose-study.txt")) == nil)
        #expect(SpotlightOneShot.studyFolder(
            forBeacon: URL(fileURLWithPath: "/S/T/bristlenose-output/notes.txt")) == nil)
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
            // Exactly one keeps the id: a capture that re-mints nothing would
            // otherwise pass, both reading "One" (Fable review).
            #expect(StudyMarker.read(folder: one) != StudyMarker.read(folder: two))
            #expect([StudyMarker.read(folder: one), StudyMarker.read(folder: two)].contains(id))
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
        #expect(index.projects.first(where: { $0.id == b.id })?.copiedFrom == id,
                "the re-minted copy does not know where it came from")
        #expect(index.projects.first(where: { $0.id == a.id })?.copiedFrom == nil)
    }

    /// Two rows on one folder (a legacy pair, or a link and its target) are
    /// not a copy of each other: the folder must not be re-minted as one.
    @Test func twoSpellingsOfOneFolderAreNotACopy() throws {
        let root = try folder()
        defer { try? FileManager.default.removeItem(at: root) }
        let study = root.appendingPathComponent("Talismanic")
        try FileManager.default.createDirectory(at: study, withIntermediateDirectories: true)
        let link = root.appendingPathComponent("Talismanic link")
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: study)
        let id = UUID().uuidString.lowercased()
        try writePythonMarker(study, id: id)

        let index = ProjectIndex(fileURL: root.appendingPathComponent("projects.json"))
        let a = index.addProject(name: "Talismanic", path: study.path)
        let b = index.addProject(name: "Talismanic", path: link.path)
        #expect(index.captureStudyID(id: a.id, folder: study) == id)
        #expect(index.captureStudyID(id: b.id, folder: link) == id, "one folder was re-minted as a copy of itself")
        #expect(StudyMarker.read(folder: study) == id)
    }

    // ── The drop decision when a disk is ejected ────────────────────────────

    @Test func aNetworkReDropUnderAnotherCaseIsTheSameFolder() {
        let id = UUID()
        let row = StudyDropMatch.Candidate(id: id, studyID: study,
                                           path: "/Volumes/Share/Talismanic", onNetwork: true)
        #expect(StudyDropMatch.resolve(droppedStudyID: study, candidates: [row],
                                       droppedPath: "/Volumes/share/talismanic",
                                       folderExists: { _ in true }) == .moved(id))
    }

    /// Off a network share, folder identity has already said these are two
    /// folders (a case-sensitive volume): a case-only match is a copy.
    @Test func aLocalFolderDifferingOnlyByCaseIsACopy() {
        let id = UUID()
        let row = StudyDropMatch.Candidate(id: id, studyID: study, path: "/Users/r/Studies/Talismanic")
        #expect(StudyDropMatch.resolve(droppedStudyID: study, candidates: [row],
                                       droppedPath: "/Users/r/studies/talismanic",
                                       folderExists: { _ in true }) == .copy(of: id))
    }

    /// A network holder's folder identity cannot be read without risking a
    /// stall: a re-drop there is neither re-minted nor merged on a guess.
    @Test func aLiveHolderOnANetworkShareIsUnsure() {
        let row = StudyDropMatch.Candidate(id: UUID(), studyID: study,
                                           path: "/Volumes/Share/Talismanic", onNetwork: true)
        #expect(StudyDropMatch.resolve(droppedStudyID: study, candidates: [row],
                                       droppedPath: "/Volumes/Share-1/Talismanic",
                                       folderExists: { _ in true }) == .unsure)
    }

    /// Locate must not point a row at a folder another row holds.
    @Test func anotherRowsFolderIsFoundHoweverSpelled() throws {
        let root = try folder()
        defer { try? FileManager.default.removeItem(at: root) }
        let study = root.appendingPathComponent("Talismanic")
        try FileManager.default.createDirectory(at: study, withIntermediateDirectories: true)
        let link = root.appendingPathComponent("link")
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: study)
        let index = ProjectIndex(fileURL: root.appendingPathComponent("projects.json"))
        let holder = index.addProject(name: "Talismanic", path: study.path)
        let lost = index.addProject(name: "Old row", path: root.appendingPathComponent("gone").path)
        #expect(index.otherProject(holding: study, excluding: lost.id)?.id == holder.id)
        #expect(index.otherProject(holding: link, excluding: lost.id)?.id == holder.id)
        #expect(index.otherProject(holding: study, excluding: holder.id) == nil)
        // A duplicate row of the same study is not another study.
        if let i = index.projects.firstIndex(where: { $0.id == holder.id }),
           let j = index.projects.firstIndex(where: { $0.id == lost.id }) {
            index.projects[i].studyID = "6f1c2b9e-4444-4000-8000-000000000000"
            index.projects[j].studyID = "6f1c2b9e-4444-4000-8000-000000000000"
        }
        #expect(index.otherProject(holding: study, excluding: lost.id) == nil)
    }

    @Test func aHolderOnAnEjectedDiskIsUnsure() {
        let row = StudyDropMatch.Candidate(id: UUID(), studyID: study, path: "/Volumes/Work/Talismanic")
        #expect(StudyDropMatch.resolve(droppedStudyID: study, candidates: [row],
                                       folderExists: { _ in false }) == .unsure)
    }

    @Test func aHolderMissingFromAMountedDiskMoved() {
        let id = UUID()
        let row = StudyDropMatch.Candidate(id: id, studyID: study, path: "/Volumes/Work/Talismanic")
        #expect(StudyDropMatch.resolve(droppedStudyID: study, candidates: [row],
                                       folderExists: { $0 == "/Volumes/Work" }) == .moved(id))
    }

    @Test func theBootDiskIsAlwaysMounted() {
        #expect(StudyDropMatch.volumeIsMounted("/Users/r/Studies/Talismanic", folderExists: { _ in false }))
        #expect(!StudyDropMatch.volumeIsMounted("/Volumes/Work/T", folderExists: { _ in false }))
    }

    // ── Locate never relocates onto an ungranted Spotlight hit ──────────────

    @Test func aSpotlightHitAlwaysGoesThroughThePanel() {
        let hit = URL(fileURLWithPath: "/Volumes/Work/Talismanic")
        guard case .needsGrant(let picked) = LocateFlow.afterSpotlightConfirm(hit) else {
            Issue.record("a Spotlight hit was located without a grant"); return
        }
        #expect(picked == hit)
    }

    /// Drives the real `run()`: a Spotlight hit on an analysed folder with no
    /// marker must come back `.needsGrant`, never `.located` (which would
    /// relocate onto a folder the app may not read).
    @Test func locateRunNeverLocatesASpotlightHitDirectly() async throws {
        let dir = try folder()
        defer { try? FileManager.default.removeItem(at: dir) }
        let state = dir.appendingPathComponent("bristlenose-output/.bristlenose")
        try FileManager.default.createDirectory(at: state, withIntermediateDirectories: true)
        try Data("{}".utf8).write(to: state.appendingPathComponent("pipeline-manifest.json"))
        final class Stub: LocateSearching {
            let hit: URL
            init(hit: URL) { self.hit = hit }
            func findStudy(id: String) async -> SpotlightOneShot.StudySearch { .none }
            func findUniqueMatch(for projectName: String) async -> URL? { hit }
        }
        let project = Project(id: UUID(), name: "Talismanic", path: "/gone/Talismanic")
        let flow = LocateFlow(project: project, i18n: I18n(), spotlight: Stub(hit: dir))
        let result: LocateFlow.Result = await withCheckedContinuation { cont in
            flow.run(confirm: { _ in .useThisFolder }, completion: { cont.resume(returning: $0) })
        }
        guard case .needsGrant(let picked) = result else {
            Issue.record("a Spotlight hit was located without the panel's grant"); return
        }
        #expect(picked == dir)
    }

    @Test func anUnreadableFolderIdentityIsUnknownNotDifferent() {
        let a = URL(fileURLWithPath: "/Users/r/Talismanic"), b = URL(fileURLWithPath: "/Volumes/X/T")
        #expect(ProjectIndex.folderSameness(a, b, identity: { _ in nil }) == .unknown)
        #expect(ProjectIndex.folderSameness(a, a, identity: { _ in nil }) == .same)
        #expect(ProjectIndex.folderSameness(a, b, identity: { NSString(string: $0.path) }) == .different)
        #expect(ProjectIndex.folderSameness(a, b, identity: { _ in NSString(string: "1") }) == .same)
    }

    @Test func anAmbiguousIdSearchSaysSo() {
        let same = Date(timeIntervalSince1970: 1_000)
        let a = URL(fileURLWithPath: "/Volumes/Work/T"), b = URL(fileURLWithPath: "/Users/r/Backups/T")
        #expect(SpotlightOneShot.studySearch([]) == .none)
        #expect(SpotlightOneShot.studySearch([(a, same)]) == .found(a))
        #expect(SpotlightOneShot.studySearch([(a, same), (b, same)]) == .ambiguous)
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
        #expect(index.projects.first(where: { $0.id == b.id })?.copiedFrom == id,
                "the re-minted copy does not know where it came from")
    }
}

/// Where a copy came from, on its row's hover (design-project-identity §9).
@MainActor
@Suite("Copy provenance on the sidebar row")
struct CopyProvenanceTests {

    private func english() throws -> I18n {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("copy-i18n-\(UUID().uuidString)")
        let en = dir.appendingPathComponent("en")
        try FileManager.default.createDirectory(at: en, withIntermediateDirectories: true)
        let desktop: [String: Any] = ["chrome": [
            "tooltipCopiedFrom": "Copied from {{name}}",
            "tooltipCopiedFromElsewhere": "Copied from another project",
        ]]
        try JSONSerialization.data(withJSONObject: desktop)
            .write(to: en.appendingPathComponent("desktop.json"))
        let i18n = I18n()
        i18n.configure(localesDirectory: dir)
        i18n.setLocale("en")
        return i18n
    }

    private let original = "6f1c2b9e-2222-4000-8000-000000000000"

    @Test func anOriginalSaysNothing() {
        let p = Project(id: UUID(), name: "Talismanic", path: "/S/T", studyID: original)
        #expect(CopyProvenance.resolve(copiedFrom: nil, projects: [p]) == nil)
    }

    /// By id, so a renamed original still resolves under its name today.
    @Test func theOriginalIsNamedByItsStudyNotItsName() {
        let renamed = Project(id: UUID(), name: "Talismanic (final)", path: "/S/T", studyID: original)
        let lookalike = Project(id: UUID(), name: "Talismanic", path: "/S/U",
                                studyID: "6f1c2b9e-3333-4000-8000-000000000000")
        #expect(CopyProvenance.resolve(copiedFrom: original, projects: [lookalike, renamed])
                == .of("Talismanic (final)"))
    }

    @Test func anOriginalNotInTheSidebarIsElsewhere() {
        #expect(CopyProvenance.resolve(copiedFrom: original, projects: []) == .elsewhere)
    }

    @Test func theHoverSaysWhereTheCopyCameFrom() throws {
        let i18n = try english()
        #expect(SidebarSubtitleText.tooltip(for: .placeholder, data: nil, progress: nil,
                                            copy: .of("Talismanic"), i18n: i18n)
                == "Copied from Talismanic")
        #expect(SidebarSubtitleText.tooltip(for: .placeholder, data: nil, progress: nil,
                                            copy: .elsewhere, i18n: i18n)
                == "Copied from another project")
        #expect(SidebarSubtitleText.tooltip(for: .placeholder, data: nil, progress: nil,
                                            i18n: i18n) == nil)
    }
}
