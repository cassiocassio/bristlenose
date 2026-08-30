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
    /// FULL paths of the same rows, exactly as the pipeline recorded them.
    ///
    /// Basenames alone cannot answer "is this file still there", because
    /// `discover_files` descends up to `_MAX_SCAN_DEPTH = 3` while the
    /// watcher's own enumeration is top-level only. A project whose
    /// recordings live in an `interviews/` subfolder therefore matched
    /// nothing, and every ingested file was reported missing — on 30 Aug 2026
    /// that was a project with all three files present and correct, told they
    /// were "no longer in the project folder".
    /// **nil means "could not read", NOT "zero rows".** An empty set is a
    /// claim — "nothing is ingested" — and downstream that claim publishes
    /// `missingFiles: []`, which CLEARS a correct standing warning and records
    /// the empty state as the new baseline. `shouldPublish` compares against
    /// `lastPublished`, and nothing schedules a corrective rescan for a DB-only
    /// change, so the alarm stays cleared until the folder happens to change.
    /// The struct already models unreadability this way for `sessionCount` and
    /// `totalDurationSeconds`; this field joins that vocabulary rather than
    /// choosing between two kinds of wrong answer.
    let ingestedPaths: Set<String>?
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
        ingestedBasenames: [], ingestedPaths: [],
        sessionCount: nil, totalDurationSeconds: nil
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

        let sources = readSources(db: db)
        let sessions = readSessionCount(db: db)
        let totalDuration = readTotalDuration(db: db)
        log.info("readSnapshot: ingested=\(sources.basenames.count), sessions=\(sessions.map { String($0) } ?? "nil", privacy: .public)")
        return ProjectDBSnapshot(
            ingestedBasenames: sources.basenames,
            ingestedPaths: sources.paths,
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

    /// Both the basenames (for new-file detection) and the full recorded paths
    /// (for missing-file detection) from one pass over `source_files`.
    private static func readSources(
        db: OpaquePointer?
    ) -> (basenames: Set<String>, paths: Set<String>?) {
        var stmt: OpaquePointer?
        let sql = "SELECT path FROM source_files"
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            return ([], nil)
        }
        defer { sqlite3_finalize(stmt) }

        var basenames: Set<String> = []
        var paths: Set<String> = []
        while true {
            let rc = sqlite3_step(stmt)
            if rc == SQLITE_ROW {
                if let cStr = sqlite3_column_text(stmt, 0) {
                    let path = String(cString: cStr)
                    if !path.isEmpty {
                        basenames.insert((path as NSString).lastPathComponent)
                        paths.insert(path)
                    }
                }
            } else if rc == SQLITE_DONE {
                break
            } else {
                // SQLITE_BUSY / LOCKED / corruption. Empty BASENAMES so the
                // watcher doesn't spike every uncovered file into newFiles
                // during concurrent pipeline writes — but nil PATHS, because
                // an empty path set is a claim that nothing is missing, and
                // publishing that retracts a correct warning permanently.
                // Refusing to answer is the third option the two-kinds-of-
                // wrong framing misses.
                log.warning("readSources: sqlite3_step rc=\(rc, privacy: .public) — snapshot unreadable")
                return ([], nil)
            }
        }
        return (basenames, paths)
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
