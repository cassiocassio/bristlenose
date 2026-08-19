import Foundation
import OSLog
import SQLite3

private let log = Logger(subsystem: "app.bristlenose", category: "curation-counts")

/// What a researcher would lose if the analysis were rebuilt from scratch.
///
/// `--clean` is `shutil.rmtree(output_dir)` — the whole directory, database
/// included — so a re-analysis discards every one of these. Counting them is
/// what lets the confirmation sheet *measure* the cost instead of saying "this
/// cannot be undone", which tells a researcher nothing they can weigh.
///
/// **The analysis itself is deliberately not counted here.** It is rebuilt, not
/// lost, and it is the thing the researcher just asked for; the sheet's opening
/// line states the re-run in its own words. These five are *their* work.
struct CurationCounts: Equatable {
    var editedQuotes = 0
    var tags = 0
    var starredQuotes = 0
    var renamedSpeakers = 0
    var namedThemes = 0

    static let none = CurationCounts()

    /// True when there is nothing of the researcher's to lose — the sheet stays
    /// silent and the re-analysis just runs.
    var isEmpty: Bool {
        editedQuotes == 0 && tags == 0 && starredQuotes == 0
            && renamedSpeakers == 0 && namedThemes == 0
    }

    var total: Int {
        editedQuotes + tags + starredQuotes + renamedSpeakers + namedThemes
    }
}

/// Reads `CurationCounts` from a project's analysis database.
///
/// Same `?immutable=1` read-only idiom as `SourceFilesReader` — see its long
/// note for why that flag is load-bearing under App Sandbox. Every count is
/// independently fallible: a missing table (an older schema, a half-built
/// project) yields zero for that line rather than failing the whole read,
/// because a sheet listing four of five losses is still worth far more than no
/// sheet at all.
enum CurationCountsReader {

    static func read(projectRoot: URL) -> CurationCounts {
        let dbURL = projectRoot
            .appendingPathComponent("bristlenose-output", isDirectory: true)
            .appendingPathComponent(".bristlenose", isDirectory: true)
            .appendingPathComponent("bristlenose.db")

        guard FileManager.default.fileExists(atPath: dbURL.path) else { return .none }

        var db: OpaquePointer?
        let uri = "file:\(dbURL.path)?immutable=1"
        let flags = SQLITE_OPEN_READONLY | SQLITE_OPEN_NOMUTEX | SQLITE_OPEN_URI
        guard sqlite3_open_v2(uri, &db, flags, nil) == SQLITE_OK else {
            let msg = db.flatMap { sqlite3_errmsg($0).map(String.init(cString:)) } ?? "unknown"
            log.notice("read: sqlite3_open_v2 failed: \(msg, privacy: .public)")
            sqlite3_close(db)
            return .none
        }
        defer { sqlite3_close(db) }

        var counts = CurationCounts()
        counts.editedQuotes = count(db, "SELECT COUNT(*) FROM quote_edits")
        // `source` distinguishes a researcher's tag from one AutoCode proposed
        // and nobody confirmed. Only the human ones are a loss.
        counts.tags = count(db, "SELECT COUNT(*) FROM quote_tags WHERE source = 'human'")
        counts.starredQuotes = count(db, "SELECT COUNT(*) FROM quote_states WHERE is_starred = 1")
        // A speaker is "renamed" once a person carries a name the pipeline
        // could not have produced — speaker codes are p1/m1/o1, so any non-empty
        // full name is the researcher's doing.
        counts.renamedSpeakers = count(
            db, "SELECT COUNT(*) FROM persons WHERE full_name IS NOT NULL AND full_name != ''")
        counts.namedThemes = count(db, "SELECT COUNT(*) FROM heading_edits")
        log.info("read: \(counts.total) curated items")
        return counts
    }

    /// One scalar count. Returns 0 — never nil — for a table this schema
    /// doesn't have: the sheet's job is to name what it can see, and a missing
    /// table means there is nothing of that kind to lose.
    private static func count(_ db: OpaquePointer?, _ sql: String) -> Int {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            log.info("count: prepare failed for \(sql, privacy: .public)")
            return 0
        }
        defer { sqlite3_finalize(stmt) }
        return sqlite3_step(stmt) == SQLITE_ROW ? Int(sqlite3_column_int64(stmt, 0)) : 0
    }
}
