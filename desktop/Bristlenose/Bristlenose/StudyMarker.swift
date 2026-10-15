import Foundation
import OSLog

private let log = Logger(subsystem: "app.bristlenose", category: "study-marker")

/// The study id a project folder carries: `bristlenose-output/.bristlenose/study.json`.
///
/// Written by Python (`bristlenose/study_marker.py`) the first time a run or a
/// serve touches the study, and by the app in one case only: a copy arriving
/// while its original is still in the sidebar is given a new id, with
/// `copied_from` recording where it came from (`docs/design-project-identity.md`
/// §3, §9). The shape is shared with Python and pinned on both sides:
/// `tests/test_study_identity.py::test_the_swift_writer_shape_reads` and
/// `StudyMarkerTests`.
enum StudyMarker {
    static let schema = 1

    static func url(forFolder folder: URL) -> URL {
        folder
            .appendingPathComponent("bristlenose-output", isDirectory: true)
            .appendingPathComponent(".bristlenose", isDirectory: true)
            .appendingPathComponent("study.json", isDirectory: false)
    }

    /// The visible copy of the id Spotlight can find (Python's
    /// `study_marker.BEACON_FILENAME`). A search aid, never read for identity.
    static let beaconFilename = "bristlenose-study.txt"

    static func beaconURL(forFolder folder: URL) -> URL {
        folder
            .appendingPathComponent("bristlenose-output", isDirectory: true)
            .appendingPathComponent(beaconFilename, isDirectory: false)
    }

    static func beaconText(_ id: String) -> String { "bristlenose-study \(id)\n" }

    /// The study id, or nil for no marker, an unreadable one, or one this
    /// release cannot read — never a guess.
    static func read(folder: URL) -> String? {
        guard let object = payload(folder: folder),
              let raw = object["study_id"] as? String,
              let id = UUID(uuidString: raw) else { return nil }
        return id.uuidString.lowercased()
    }

    /// The study this one was copied from, when the app gave a copy its own
    /// id (§9). Nil for an original, and for a marker this release cannot read.
    static func copiedFrom(folder: URL) -> String? {
        guard let object = payload(folder: folder),
              let raw = object["copied_from"] as? String,
              let id = UUID(uuidString: raw) else { return nil }
        return id.uuidString.lowercased()
    }

    private static func payload(folder: URL) -> [String: Any]? {
        guard let data = try? Data(contentsOf: url(forFolder: folder)),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              object["schema"] as? Int == schema else { return nil }
        return object
    }

    /// Give a copy its own identity. Atomic; throws if the folder is not
    /// writable, in which case the copy keeps the id it carries and the
    /// sidebar holds the same study twice until it can be written.
    @discardableResult
    static func remint(folder: URL, copiedFrom: String) throws -> String {
        let id = UUID().uuidString.lowercased()
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        let payload: [String: Any] = [
            "schema": schema,
            "study_id": id,
            "minted_at": formatter.string(from: Date()),
            "minted_by": "app",
            "copied_from": copiedFrom,
        ]
        let data = try JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted, .sortedKeys])
        let target = url(forFolder: folder)
        try FileManager.default.createDirectory(
            at: target.deletingLastPathComponent(), withIntermediateDirectories: true
        )
        try data.write(to: target, options: .atomic)
        // The copy's beacon still names the original; a stale one would make
        // a Spotlight search for the original find the copy too.
        do {
            try Data(beaconText(id).utf8).write(to: beaconURL(forFolder: folder), options: .atomic)
        } catch {
            log.error("could not update the copy's search beacon: \(error.localizedDescription, privacy: .public)")
        }
        log.notice("study marker re-minted for a copy")
        return id
    }
}

/// What a dropped folder's study id says about it, against the sidebar.
///
/// Reached only when no project holds the dropped folder's PATH: an exact path
/// match is a re-drop and is handled before this. Pure, so the decision has a
/// test without a window, a drop or a sandbox.
enum StudyDropMatch: Equatable {
    /// No project in the sidebar carries this study: create one as before.
    case none
    /// The project carrying this study has lost its folder: this is that
    /// folder, moved. The row follows it.
    case moved(UUID)
    /// The project carrying this study is live where it was: this is a copy.
    /// It gets its own id, then its own row (§9, decided 13 Oct 2026).
    case copy(of: UUID)
    /// The project carrying this study is on a disk that is not mounted, so
    /// this may be its folder moved, or a backup of it. Neither is guessed:
    /// the folder gets its own row with the id it carries, and when the disk
    /// returns the row that joined later is re-minted (`captureStudyID`)
    /// (Fable review, 15 Oct 2026).
    case unsure

    struct Candidate: Equatable {
        let id: UUID
        let studyID: String?
        let path: String
        /// On a network share: its folder's identity cannot be read on the
        /// main actor without risking a stall, so a re-spelled re-drop and a
        /// copy cannot be told apart there.
        var onNetwork: Bool = false
    }

    static func resolve(
        droppedStudyID: String?,
        candidates: [Candidate],
        droppedPath: String? = nil,
        folderExists: (String) -> Bool
    ) -> StudyDropMatch {
        guard let droppedStudyID else { return .none }
        let holders = candidates.filter { $0.studyID == droppedStudyID }
        guard !holders.isEmpty else { return .none }
        if let live = holders.first(where: { folderExists($0.path) }) {
            // The holder's own folder, spelled differently (case, a symlink
            // resolved by the caller): a re-drop. The row follows the new
            // spelling; nothing is re-minted (Fable review, 15 Oct 2026).
            if let droppedPath,
               live.path.lowercased() == droppedPath.lowercased() {
                return .moved(live.id)
            }
            // On a network share the two cannot be told apart without a
            // blocking read: neither guess. The shared-id rule settles it.
            if live.onNetwork { return .unsure }
            return .copy(of: live.id)
        }
        if let gone = holders.first(where: { volumeIsMounted($0.path, folderExists: folderExists) }) {
            return .moved(gone.id)
        }
        return .unsure
    }

    /// Whether the disk a path names is mounted: a missing folder on a mounted
    /// disk has moved; on an ejected one it may simply be out of reach.
    static func volumeIsMounted(_ path: String, folderExists: (String) -> Bool) -> Bool {
        let parts = path.split(separator: "/", omittingEmptySubsequences: true)
        guard parts.count >= 2, parts[0] == "Volumes" else { return true }
        return folderExists("/Volumes/\(parts[1])")
    }
}
