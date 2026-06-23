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
    /// Sum of `sessions.duration_seconds` — total interview time across the
    /// study, the same figure the Project dashboard reports as its "Total"
    /// stat (`_format_duration_human(total_duration_s)` in
    /// `server/routes/dashboard.py`, which sums the per-session durations).
    /// Nil when the DB isn't readable or the column is absent; 0 when the
    /// sessions table is empty. Read in the same open as `sessionCount`.
    let totalDurationSeconds: Double?

    static let empty = ProjectDBSnapshot(
        ingestedBasenames: [], sessionCount: nil, totalDurationSeconds: nil
    )
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
            log.info("readSnapshot: no DB at \(dbURL.path, privacy: .public) — pre-analysis project")
            return .empty
        }

        var db: OpaquePointer?
        // URI form with `?immutable=1` is load-bearing under App Sandbox.
        //
        // SQLite WAL journal mode requires the reader to access (and
        // sometimes create) `*-wal` and `*-shm` companion files. If the
        // last pipeline writer checkpointed and removed the WAL, but left
        // the DB header in WAL mode, a fresh read connection in
        // `SQLITE_OPEN_READONLY` mode will still try to touch the WAL
        // and error with "unable to open database file" at prepare time.
        // Under macOS Sandbox the failure surfaces as ENOENT on `*-wal`.
        // `?immutable=1` tells SQLite "this DB will not change during
        // my session" — SQLite skips the WAL/SHM dance entirely and
        // reads pages directly from the main DB file. Trade-off: if the
        // pipeline writes mid-scan we get the prior state, which is
        // acceptable for the watcher's snapshot-style reads (next
        // callback re-scans).
        //
        // SQLITE_OPEN_NOMUTEX correctness rests on a single
        // open-prepare-step-finalise-close lifecycle per call: the handle
        // never crosses threads. Caller invokes from `ProjectFolderWatcher`'s
        // per-watcher serial scanQueue, satisfying the contract. Future
        // refactors that share a handle across queues must switch to
        // `SQLITE_OPEN_FULLMUTEX`.
        let uri = "file:\(dbURL.path)?immutable=1"
        let flags = SQLITE_OPEN_READONLY | SQLITE_OPEN_NOMUTEX | SQLITE_OPEN_URI
        guard sqlite3_open_v2(uri, &db, flags, nil) == SQLITE_OK else {
            let msg = db.flatMap { sqlite3_errmsg($0).map(String.init(cString:)) } ?? "unknown"
            log.notice("readSnapshot: sqlite3_open_v2 failed: \(msg, privacy: .public)")
            sqlite3_close(db)
            return .empty
        }
        defer { sqlite3_close(db) }

        let basenames = readBasenames(db: db)
        let sessions = readSessionCount(db: db)
        let totalDuration = readTotalDuration(db: db)
        log.info("readSnapshot: ingested=\(basenames.count), sessions=\(sessions.map { String($0) } ?? "nil", privacy: .public)")
        return ProjectDBSnapshot(
            ingestedBasenames: basenames,
            sessionCount: sessions,
            totalDurationSeconds: totalDuration
        )
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

    private static func readTotalDuration(db: OpaquePointer?) -> Double? {
        var stmt: OpaquePointer?
        let sql = "SELECT SUM(duration_seconds) FROM sessions"
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            // Prepare fails if the column/table is absent (older schema) —
            // nil so the subtitle falls back to the count alone.
            return nil
        }
        defer { sqlite3_finalize(stmt) }

        let rc = sqlite3_step(stmt)
        if rc == SQLITE_ROW {
            // SUM over an empty table is SQL NULL → 0 (no sessions, no
            // duration), kept distinct from nil (query/schema failure).
            if sqlite3_column_type(stmt, 0) == SQLITE_NULL {
                return 0
            }
            return sqlite3_column_double(stmt, 0)
        }
        return nil
    }
}
