import Foundation
import OSLog
import SQLite3

private let log = Logger(subsystem: "app.bristlenose", category: "curation-counts")

/// What a researcher would lose if the analysis were rebuilt from scratch.
///
/// `--clean` moves `bristlenose-output/` aside — the whole directory, database
/// included — and discards the copy once the new run succeeds (since 30 Aug
/// 2026; it was an `rmtree` before that), so a re-analysis discards every one
/// of these. Counting them is what lets the confirmation sheet *measure* the
/// cost instead of saying "this cannot be undone", which tells a researcher
/// nothing they can weigh.
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
/// note for why that flag is load-bearing under App Sandbox.
///
/// **`nil` means the database could not be read, and is never a zero.** A zero
/// lets Re-analyse run `--clean` without asking, so a read that failed must not
/// come back as one (decision #1, 21 Oct 2026). Until then it did, two ways: a
/// file that would not open returned `.none`, and a file that opened but could
/// not be read (not a database, a torn page, an I/O error materialising an
/// evicted file) had each count's failure swallowed into 0. `ContentView`
/// confirms on nil with its own sentence (`ReAnalyseDecision`).
///
/// What still reads as a real zero: no database file (`ENOENT` — nothing has
/// been served, so nothing curated), and a curation table the schema does not
/// have (an older schema, a half-built project; asked of `sqlite_master`, not
/// guessed from an error), which yields zero for that line only, because a
/// sheet listing four of five losses is still worth far more than no sheet at
/// all. A table that is there but cannot be counted — a renamed column, a
/// missing join table — is nil. A database held locked by the serve
/// reads normally: `immutable=1` takes no locks.
///
/// Scoped to `SourceFilesReader.reportProjectID`, the one row the report shows:
/// a database that has forked into two rows (12 Oct 2026) must not have the
/// second row's curation counted as something the researcher would lose from
/// a report that never showed it. `persons` is instance-scoped by design and
/// stays unfiltered.
///
/// **Call it off the main actor.** It opens a file: on an iCloud-evicted or
/// sleeping-volume database that is a materialisation or a spin-up, and the
/// menu click that asks would beachball for it. `ContentView.askToReAnalyse`
/// hops to a detached task and back.
enum CurationCountsReader {

    nonisolated static func read(projectRoot: URL) -> CurationCounts? {
        let dbURL = projectRoot
            .appendingPathComponent("bristlenose-output", isDirectory: true)
            .appendingPathComponent(".bristlenose", isDirectory: true)
            .appendingPathComponent("bristlenose.db")

        // `stat`, not `fileExists`: `fileExists` answers false for a path the
        // sandbox refuses or a volume that errors, and false here is a zero.
        // Only a path that is not there is "no database".
        var info = stat()
        if stat(dbURL.path, &info) != 0 {
            let err = errno
            if err == ENOENT || err == ENOTDIR { return CurationCounts.none }
            log.notice("read: stat failed, errno \(err, privacy: .public)")
            return nil
        }

        var db: OpaquePointer?
        let uri = "file:\(dbURL.path)?immutable=1"
        let flags = SQLITE_OPEN_READONLY | SQLITE_OPEN_NOMUTEX | SQLITE_OPEN_URI
        guard sqlite3_open_v2(uri, &db, flags, nil) == SQLITE_OK else {
            let msg = db.flatMap { sqlite3_errmsg($0).map(String.init(cString:)) } ?? "unknown"
            log.notice("read: sqlite3_open_v2 failed: \(msg, privacy: .public)")
            sqlite3_close(db)
            return nil
        }
        defer { sqlite3_close(db) }

        // Which tables exist, asked once and exactly, rather than guessed from
        // a prepare's `SQLITE_ERROR` (which also means "unsupported file
        // format"). A read of the schema that fails is nil.
        guard let tables = tableNames(db) else {
            log.notice("read: the schema could not be read")
            return nil
        }
        let pid = SourceFilesReader.reportProjectID
        // The quote tables carry no `project_id`; they scope through `quotes`.
        // `source` distinguishes a researcher's tag from one AutoCode proposed
        // and nobody confirmed. Only the human ones are a loss.
        // A speaker is "renamed" once a person carries a name the pipeline
        // could not have produced — speaker codes are p1/m1/o1, so any non-empty
        // full name is the researcher's doing.
        guard
            let editedQuotes = count(db, tables, of: "quote_edits", joining: ["quotes"], """
                SELECT COUNT(*) FROM quote_edits e JOIN quotes q ON q.id = e.quote_id
                WHERE q.project_id = \(pid)
                """),
            let tags = count(db, tables, of: "quote_tags", joining: ["quotes"], """
                SELECT COUNT(*) FROM quote_tags t JOIN quotes q ON q.id = t.quote_id
                WHERE t.source = 'human' AND q.project_id = \(pid)
                """),
            let starredQuotes = count(db, tables, of: "quote_states", joining: ["quotes"], """
                SELECT COUNT(*) FROM quote_states s JOIN quotes q ON q.id = s.quote_id
                WHERE s.is_starred = 1 AND q.project_id = \(pid)
                """),
            let renamedSpeakers = count(db, tables, of: "persons", joining: [],
                "SELECT COUNT(*) FROM persons WHERE full_name IS NOT NULL AND full_name != ''"),
            let namedThemes = count(db, tables, of: "heading_edits", joining: [],
                "SELECT COUNT(*) FROM heading_edits WHERE project_id = \(pid)")
        else {
            return nil
        }
        let counts = CurationCounts(
            editedQuotes: editedQuotes, tags: tags, starredQuotes: starredQuotes,
            renamedSpeakers: renamedSpeakers, namedThemes: namedThemes)
        log.info("read: \(counts.total) curated items")
        return counts
    }

    /// One kind of curation, or nil when the database could not answer.
    ///
    /// A `table` this schema doesn't have counts 0: an older schema or a
    /// half-built project has nothing of that kind to lose, and the sheet's job
    /// is to name what it can see. Everything else that goes wrong is nil — a
    /// table that holds curation but whose `joining` table is missing, a
    /// column that has been renamed, any prepare failure, and any step that does
    /// not return the row (`COUNT(*)` always returns one).
    private nonisolated static func count(
        _ db: OpaquePointer?, _ tables: Set<String>,
        of table: String, joining: [String], _ sql: String
    ) -> Int? {
        guard tables.contains(table) else { return 0 }
        guard joining.allSatisfy(tables.contains) else {
            log.notice("count: \(table, privacy: .public) is present without the tables it joins")
            return nil
        }
        return scalar(db, sql)
    }

    /// The names of the tables in this database, or nil if its schema can't be read.
    private nonisolated static func tableNames(_ db: OpaquePointer?) -> Set<String>? {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(
            db, "SELECT name FROM sqlite_master WHERE type = 'table'", -1, &stmt, nil
        ) == SQLITE_OK else {
            log.notice("tableNames: prepare failed, sqlite \(sqlite3_errcode(db), privacy: .public)")
            sqlite3_finalize(stmt)
            return nil
        }
        defer { sqlite3_finalize(stmt) }
        var names = Set<String>()
        while true {
            let stepped = sqlite3_step(stmt)
            if stepped == SQLITE_DONE { return names }
            guard stepped == SQLITE_ROW else {
                log.notice("tableNames: step failed, sqlite \(stepped, privacy: .public)")
                return nil
            }
            if let text = sqlite3_column_text(stmt, 0) { names.insert(String(cString: text)) }
        }
    }

    /// One `COUNT(*)`, or nil on any failure.
    private nonisolated static func scalar(_ db: OpaquePointer?, _ sql: String) -> Int? {
        var stmt: OpaquePointer?
        let prepared = sqlite3_prepare_v2(db, sql, -1, &stmt, nil)
        guard prepared == SQLITE_OK else {
            log.notice("scalar: prepare failed, sqlite \(prepared, privacy: .public)")
            sqlite3_finalize(stmt)
            return nil
        }
        defer { sqlite3_finalize(stmt) }
        let stepped = sqlite3_step(stmt)
        guard stepped == SQLITE_ROW else {
            log.notice("scalar: step failed, sqlite \(stepped, privacy: .public)")
            return nil
        }
        return Int(sqlite3_column_int64(stmt, 0))
    }
}
