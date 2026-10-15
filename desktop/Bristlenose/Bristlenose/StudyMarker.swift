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

    /// The study id, or nil for no marker, an unreadable one, or one this
    /// release cannot read — never a guess.
    static func read(folder: URL) -> String? {
        guard let data = try? Data(contentsOf: url(forFolder: folder)),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              object["schema"] as? Int == schema,
              let raw = object["study_id"] as? String,
              let id = UUID(uuidString: raw) else { return nil }
        return id.uuidString.lowercased()
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

    struct Candidate: Equatable {
        let id: UUID
        let studyID: String?
        let path: String
    }

    static func resolve(
        droppedStudyID: String?,
        candidates: [Candidate],
        folderExists: (String) -> Bool
    ) -> StudyDropMatch {
        guard let droppedStudyID else { return .none }
        let holders = candidates.filter { $0.studyID == droppedStudyID }
        guard !holders.isEmpty else { return .none }
        if let live = holders.first(where: { folderExists($0.path) }) {
            return .copy(of: live.id)
        }
        return .moved(holders[0].id)
    }
}
