import Foundation
import OSLog
import SQLite3

private let log = Logger(subsystem: "app.bristlenose", category: "source-files-reader")

// MARK: PII — paths returned here are filenames that may identify participants.
// Caller is responsible for keeping them UI-only. Never log basenames.

/// Snapshot of what the project's analysis database knows: which sources have
/// been ingested (by basename) and how many sessions exist. Both come from a
/// single SQLite open/read so the scan pays one fd hit per pass, not two.
struct ProjectDBSnapshot: Equatable {
    /// Basenames of source files referenced by the `source_files` table.
    /// Empty if the DB doesn't exist yet, the schema is missing, or any
    /// read fails. Caller treats "empty" as "treat everything as new."
    let ingestedBasenames: Set<String>
    /// Count of rows in the `sessions` table — the canonical "how many
    /// interviews is this study" metric. Nil when the DB isn't readable
    /// (pre-analysis project, locked database, etc.). Renderers should
    /// treat nil as "no count to show," not "zero."
    let sessionCount: Int?

    static let empty = ProjectDBSnapshot(ingestedBasenames: [], sessionCount: nil)
}

/// Read the analysis database for a project. Reads are bundled into a single
/// snapshot to avoid double-open. Off-main only — caller schedules via the
/// watcher's scan queue.
///
/// **Why SQLite and not the manifest:** the pipeline manifest doesn't carry
/// per-session source filenames (verified 15 May 2026 against real
/// `project-ikea` data — `stages.ingest.sessions` and `input_hashes` are
/// `null` once ingest completes). The SQLite `source_files` + `sessions`
/// tables are the authoritative source-of-truth.
enum SourceFilesReader {

    /// Read both the ingested-basename set and the session count in one
    /// SQLite open. Returns `ProjectDBSnapshot.empty` if the database
    /// doesn't exist yet, the schema is missing, or any step returns
    /// a busy/locked/error code — conservative "show nothing" behaviour.
    static func readSnapshot(projectRoot: URL) -> ProjectDBSnapshot {
        let dbURL = projectRoot
            .appendingPathComponent("bristlenose-output", isDirectory: true)
            .appendingPathComponent(".bristlenose", isDirectory: true)
            .appendingPathComponent("bristlenose.db")

        guard FileManager.default.fileExists(atPath: dbURL.path) else {
            return .empty
        }

        var db: OpaquePointer?
        // SQLITE_OPEN_READONLY | SQLITE_OPEN_NOMUTEX — we only read, and the
        // pipeline server may be writing concurrently. SQLite handles WAL
        // readers safely. NOMUTEX = caller serialises (we do, per-call).
        let flags = SQLITE_OPEN_READONLY | SQLITE_OPEN_NOMUTEX
        guard sqlite3_open_v2(dbURL.path, &db, flags, nil) == SQLITE_OK else {
            log.debug("could not open source_files database (pre-analysis project)")
            sqlite3_close(db)
            return .empty
        }
        defer { sqlite3_close(db) }

        let basenames = readBasenames(db: db)
        let sessions = readSessionCount(db: db)
        return ProjectDBSnapshot(ingestedBasenames: basenames, sessionCount: sessions)
    }

    /// Convenience wrapper preserving the prior call shape — returns only
    /// the basename set, dropping the session count. Kept so callers that
    /// only need the ingested-set don't pay a `sessions` count query.
    static func ingestedBasenames(projectRoot: URL) -> Set<String> {
        readSnapshot(projectRoot: projectRoot).ingestedBasenames
    }

    // MARK: - Helpers (open handle borrowed from `readSnapshot`)

    private static func readBasenames(db: OpaquePointer?) -> Set<String> {
        var stmt: OpaquePointer?
        let sql = "SELECT path FROM source_files"
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            return []
        }
        defer { sqlite3_finalize(stmt) }

        var basenames: Set<String> = []
        while true {
            let rc = sqlite3_step(stmt)
            if rc == SQLITE_ROW {
                if let cStr = sqlite3_column_text(stmt, 0) {
                    let path = String(cString: cStr)
                    if !path.isEmpty {
                        basenames.insert((path as NSString).lastPathComponent)
                    }
                }
            } else if rc == SQLITE_DONE {
                break
            } else {
                // SQLITE_BUSY / LOCKED / corruption — bail with empty set so
                // the watcher doesn't spike every uncovered file into
                // newFiles during concurrent pipeline writes.
                return []
            }
        }
        return basenames
    }

    private static func readSessionCount(db: OpaquePointer?) -> Int? {
        var stmt: OpaquePointer?
        let sql = "SELECT COUNT(*) FROM sessions"
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            return nil
        }
        defer { sqlite3_finalize(stmt) }

        let rc = sqlite3_step(stmt)
        if rc == SQLITE_ROW {
            return Int(sqlite3_column_int64(stmt, 0))
        }
        return nil
    }
}
