import Foundation
import OSLog
import SQLite3

private let log = Logger(subsystem: "app.bristlenose", category: "source-files-reader")

// MARK: PII — paths returned here are filenames that may identify participants.
// Caller is responsible for keeping them UI-only. Never log basenames.

/// Read the set of already-ingested source filenames for a project, used by
/// `ProjectFolderWatcher` to diff against the live project folder.
///
/// Reads from `<project>/bristlenose-output/.bristlenose/bristlenose.db`,
/// table `source_files(path TEXT)`. We extract the basename so the watcher
/// can match against `URL.lastPathComponent` regardless of whether the row
/// stored an absolute or repo-relative path.
///
/// **Why SQLite and not the manifest:** the pipeline manifest doesn't carry
/// per-session source filenames (verified 15 May 2026 against real
/// `project-ikea` data — `stages.ingest.sessions` and `input_hashes` are
/// `null` once ingest completes). The SQLite `source_files` table is the
/// authoritative source-of-truth.
///
/// **Off-main:** every method opens, reads, and closes a SQLite handle
/// synchronously — call from a background queue. Callers in
/// `ProjectFolderWatcher` schedule reads on a private DispatchQueue.
enum SourceFilesReader {

    /// Return basenames (`URL.lastPathComponent`) of every row in
    /// `source_files` for the given project root. Empty set if the database
    /// doesn't exist yet (project hasn't been analysed), the schema is
    /// missing, or any read fails. Never throws — a failed read means
    /// "treat everything as new," which is the conservative default.
    static func ingestedBasenames(projectRoot: URL) -> Set<String> {
        let dbURL = projectRoot
            .appendingPathComponent("bristlenose-output", isDirectory: true)
            .appendingPathComponent(".bristlenose", isDirectory: true)
            .appendingPathComponent("bristlenose.db")

        guard FileManager.default.fileExists(atPath: dbURL.path) else {
            return []
        }

        var db: OpaquePointer?
        // SQLITE_OPEN_READONLY | SQLITE_OPEN_NOMUTEX — we only read, and the
        // pipeline server may be writing concurrently. SQLite handles WAL
        // readers safely. NOMUTEX = caller serialises (we do, per-call).
        let flags = SQLITE_OPEN_READONLY | SQLITE_OPEN_NOMUTEX
        guard sqlite3_open_v2(dbURL.path, &db, flags, nil) == SQLITE_OK else {
            log.debug("could not open source_files database (pre-analysis project)")
            sqlite3_close(db)
            return []
        }
        defer { sqlite3_close(db) }

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
                // SQLITE_BUSY / SQLITE_LOCKED / corruption — bail with an
                // empty set rather than returning a partial read. A partial
                // read would short-cut the ingested-set and spike every
                // non-included file into newFiles, flicking the count pill
                // unhelpfully during concurrent pipeline writes.
                return []
            }
        }
        return basenames
    }
}
