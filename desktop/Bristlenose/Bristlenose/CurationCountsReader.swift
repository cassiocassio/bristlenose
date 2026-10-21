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
/// confirms on nil with its own sentence (`ReAnalyseDecision`). A commit the
/// serve has not yet checkpointed out of `-wal` is nil too, since the
/// immutable read cannot see it (`walVouch`, decision #115).
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
        read(projectRoot: projectRoot, shmIsMaintained: dmsLockIsHeld, betweenReads: {})
    }

    /// `read(projectRoot:)` with its two seams exposed for tests:
    /// `shmIsMaintained` (the DMS-lock probe, which cannot see a lock this
    /// process holds) and `betweenReads`, run after the count and before the
    /// WAL index is read the second time.
    nonisolated static func read(
        projectRoot: URL,
        shmIsMaintained: (Int32) -> Bool,
        betweenReads: () -> Void
    ) -> CurationCounts? {
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

        // `immutable=1` reads the main file and nothing else, so a commit the
        // serve could not yet checkpoint is invisible to it (decision #115).
        // Asked before the count and again after, like a seqlock: a commit
        // landing in between moves `mxFrame` (or the salt, if it restarted the
        // WAL), and the count it may have missed is not trusted.
        guard let before = walVouch(dbURL, shmIsMaintained: shmIsMaintained) else { return nil }
        guard let measured = counts(at: dbURL) else { return nil }
        betweenReads()
        guard walVouch(dbURL, shmIsMaintained: shmIsMaintained) == before else {
            log.notice("read: the database changed while it was being counted")
            return nil
        }
        log.info("read: \(measured.total) curated items")
        return measured
    }

    /// The five counts from the main file, or nil when it could not be read.
    private nonisolated static func counts(at dbURL: URL) -> CurationCounts? {
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
        return CurationCounts(
            editedQuotes: editedQuotes, tags: tags, starredQuotes: starredQuotes,
            renamedSpeakers: renamedSpeakers, namedThemes: namedThemes)
    }

    /// What the WAL index vouched for at one moment.
    enum WALVouch: Equatable {
        /// No `-wal`, or an empty one: the main file is the whole database.
        case noWAL
        /// Every commit up to `mxFrame` of the WAL era named by `salt` is in
        /// the main file.
        case current(salt: [UInt8], mxFrame: UInt32)
    }

    /// Whether the main database file holds every committed transaction, so an
    /// `immutable=1` read of it is the whole truth. Nil means "can't tell", and
    /// the caller reads that as couldn't count (decision #115, 21 Oct 2026).
    ///
    /// **Why it can be nil while the serve checkpoints after every commit.** A
    /// checkpoint copies WAL frames into the main file only up to the oldest
    /// open reader's snapshot, and `wal_autocheckpoint` comes back for the rest
    /// only at the next commit. A star committed while any statement was in
    /// flight on another connection (a concurrent request, the elaboration
    /// stream, the importer, a second serve) stays in `-wal` until then, and
    /// the researcher's last edit before Re-analyse has no "then". Measured
    /// against the serve in `tests/test_serve_wal_visibility.py`.
    ///
    /// **The signal is the WAL index, not the WAL file.** A served database's
    /// `-wal` is never empty after its first write (SQLite reuses the file
    /// rather than truncating it), so "non-empty" would ask on every study;
    /// and a partial checkpoint writes the main file *after* the star went into
    /// the WAL, so "newer than the main file" misses it. The `-shm` header
    /// (sqlite.org/walformat.html, native byte order) says it exactly:
    /// `mxFrame`, the last committed frame, at offset 16, and `nBackfill`, how
    /// many have been copied to the main file, at 96. Equal means current.
    ///
    /// **But only an index somebody maintains.** SQLite trusts `-shm` only while
    /// a connection holds its DMS lock (byte 128), and rebuilds it from `-wal`
    /// otherwise; a `-shm` and `-wal` from different moments (a sync between
    /// Macs, a restore, a copy taken while the serve ran) can say "current"
    /// over a later commit. So: nobody holding the lock with a non-empty
    /// `-wal` is nil; the index's salt must be the `-wal` header's (same era);
    /// and a frame of that era past `mxFrame` is nil.
    ///
    /// Overcautious by design, never the other way: a write in flight, a
    /// rolled-back transaction's leftover frames, or a `-wal` that survived an
    /// unclean exit (recovery sets `nBackfill` to 0) all read as nil, so an
    /// idle study can show the sheet once, until its next commit.
    nonisolated static func walVouch(
        _ dbURL: URL, shmIsMaintained: (Int32) -> Bool
    ) -> WALVouch? {
        let walPath = dbURL.path + "-wal"
        var info = stat()
        if stat(walPath, &info) != 0 {
            let err = errno
            if err == ENOENT || err == ENOTDIR { return .noWAL }
            log.notice("wal: stat failed, errno \(err, privacy: .public)")
            return nil
        }
        if info.st_size == 0 { return .noWAL }

        let shm = open(dbURL.path + "-shm", O_RDONLY)
        guard shm >= 0 else {
            log.notice("wal: a -wal with no readable -shm, errno \(errno, privacy: .public)")
            return nil
        }
        defer { close(shm) }
        guard shmIsMaintained(shm) else {
            log.notice("wal: no connection holds the -shm, so its index is not current")
            return nil
        }
        guard let index = readExactly(shm, count: 100, at: 0) else {
            log.notice("wal: the -shm header is short")
            return nil
        }
        // Two copies of the header, written in turn: unequal means a writer is
        // mid-update. `isInit` is the byte at 12; the version is SQLite's 3007000.
        guard index[0..<48] == index[48..<96], u32(index, 0) == 3_007_000, index[12] != 0 else {
            log.notice("wal: the -shm header is not readable as a WAL index")
            return nil
        }
        let mxFrame = u32(index, 16)
        guard mxFrame == u32(index, 96) else {
            log.notice("wal: frames up to \(mxFrame, privacy: .public) are not all checkpointed")
            return nil
        }

        let wal = open(walPath, O_RDONLY)
        guard wal >= 0, let header = readExactly(wal, count: 32, at: 0) else {
            if wal >= 0 { close(wal) }
            log.notice("wal: the -wal header could not be read")
            return nil
        }
        defer { close(wal) }
        // Big-endian, unlike the index: magic 0x377f0682/3, page size at 8.
        let magic = beU32(header, 0)
        let pageSize = Int(beU32(header, 8))
        guard magic & 0xFFFF_FFFE == 0x377F_0682, pageSize >= 512, pageSize <= 65536,
              pageSize & (pageSize - 1) == 0 else {
            log.notice("wal: the -wal header is not a WAL header")
            return nil
        }
        let salt = Array(header[16..<24])
        guard Array(index[32..<40]) == salt else {
            log.notice("wal: the -shm index is from another WAL era")
            return nil
        }
        // A frame of this era past the last commit the index knows of is a
        // commit it has not caught up with (or one being written).
        let next = off_t(32) + off_t(mxFrame) * off_t(pageSize + 24)
        if off_t(info.st_size) >= next + 24 {
            guard let frame = readExactly(wal, count: 24, at: next) else {
                log.notice("wal: a frame past the index could not be read")
                return nil
            }
            if Array(frame[8..<16]) == salt {
                log.notice("wal: the -wal holds frames past the index's last commit")
                return nil
            }
        }
        return .current(salt: salt, mxFrame: mxFrame)
    }

    /// Whether another process holds `-shm`'s DMS lock (byte 128), i.e. a
    /// live connection is keeping the index current. A process never sees its
    /// own POSIX locks, which is why tests inject this.
    nonisolated static func dmsLockIsHeld(_ shm: Int32) -> Bool {
        var lock = flock()
        lock.l_type = Int16(F_WRLCK)
        lock.l_whence = Int16(SEEK_SET)
        lock.l_start = 128
        lock.l_len = 1
        guard fcntl(shm, F_GETLK, &lock) == 0 else {
            log.notice("wal: F_GETLK failed, errno \(errno, privacy: .public)")
            return false
        }
        return lock.l_type != Int16(F_UNLCK)
    }

    private nonisolated static func readExactly(_ fd: Int32, count: Int, at offset: off_t) -> [UInt8]? {
        var buffer = [UInt8](repeating: 0, count: count)
        let got = buffer.withUnsafeMutableBytes { pread(fd, $0.baseAddress, count, offset) }
        return got == count ? buffer : nil
    }

    private nonisolated static func u32(_ bytes: [UInt8], _ offset: Int) -> UInt32 {
        bytes.withUnsafeBytes { $0.loadUnaligned(fromByteOffset: offset, as: UInt32.self) }
    }

    private nonisolated static func beU32(_ bytes: [UInt8], _ offset: Int) -> UInt32 {
        UInt32(bigEndian: u32(bytes, offset))
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
