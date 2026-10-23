import Foundation
import SQLite3
import Testing
@testable import Bristlenose

/// The two sidebar readers of the analysis database, against a database that
/// holds **two** project rows.
///
/// THE REGRESSION. On 12 Oct 2026 a serve started while `bristlenose-output/`
/// was moved aside rooted its database in the interview folder and created
/// project row 1 empty; the run that followed was imported as row 2 with
/// everything in it. The SPA reads row 1 and showed every lens at zero — while
/// the sidebar showed the right session count, because both readers here
/// summed across **all** rows with no `project_id` filter. A forked database
/// was therefore invisible from the one surface that could have said so.
///
/// Both readers now scope to project 1 (the row the report reads), and the
/// snapshot carries the row count so a fork can be surfaced as a defect.
struct ProjectDBReadersTests {

    // MARK: - Fixture

    /// A project folder whose `bristlenose-output/.bristlenose/bristlenose.db`
    /// has the tables the readers query, populated with `rows`.
    private static func makeProject(rows: (OpaquePointer?) -> Void) throws -> URL {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-db-readers-\(UUID().uuidString)")
        let dot = root.appendingPathComponent("bristlenose-output/.bristlenose")
        try FileManager.default.createDirectory(at: dot, withIntermediateDirectories: true)
        var db: OpaquePointer?
        let path = dot.appendingPathComponent("bristlenose.db").path
        try #require(sqlite3_open(path, &db) == SQLITE_OK)
        defer { sqlite3_close(db) }
        // The columns the readers touch, nothing else. Shapes follow
        // `bristlenose/server/models.py`: `source_files` and the quote tables
        // scope to a project through `sessions` / `quotes`; `heading_edits`
        // carries `project_id` directly; `persons` is instance-scoped.
        exec(db, """
        CREATE TABLE projects (id INTEGER PRIMARY KEY, name TEXT, input_dir TEXT, output_dir TEXT);
        CREATE TABLE sessions (id INTEGER PRIMARY KEY, project_id INTEGER, session_id TEXT, duration_seconds REAL);
        CREATE TABLE source_files (id INTEGER PRIMARY KEY, session_id INTEGER, file_type TEXT, path TEXT);
        CREATE TABLE quotes (id INTEGER PRIMARY KEY, project_id INTEGER);
        CREATE TABLE quote_edits (id INTEGER PRIMARY KEY, quote_id INTEGER, edited_text TEXT);
        CREATE TABLE quote_tags (id INTEGER PRIMARY KEY, quote_id INTEGER, tag_definition_id INTEGER, source TEXT);
        CREATE TABLE quote_states (id INTEGER PRIMARY KEY, quote_id INTEGER, is_hidden INTEGER, is_starred INTEGER);
        CREATE TABLE persons (id INTEGER PRIMARY KEY, full_name TEXT);
        CREATE TABLE heading_edits (id INTEGER PRIMARY KEY, project_id INTEGER, heading_key TEXT, edited_text TEXT);
        """)
        rows(db)
        return root
    }

    private static func exec(_ db: OpaquePointer?, _ sql: String) {
        var err: UnsafeMutablePointer<CChar>?
        if sqlite3_exec(db, sql, nil, nil, &err) != SQLITE_OK {
            Issue.record("sqlite: \(err.map { String(cString: $0) } ?? "?") in \(sql)")
            sqlite3_free(err)
        }
    }

    /// The incident's shape: row 1 "Untitled" and empty but for one session the
    /// test gives it; row 2 holding the run — three sessions, their files, and
    /// curation on their quotes.
    private static func forkedProject() throws -> URL {
        try makeProject { db in
            exec(db, """
            INSERT INTO projects VALUES (1, 'Untitled', '/p', '/p');
            INSERT INTO projects VALUES (2, 'Talismanic', '/p', '/p/bristlenose-output');
            INSERT INTO sessions VALUES (1, 1, 's1', 600);
            INSERT INTO sessions VALUES (2, 2, 's1', 1000);
            INSERT INTO sessions VALUES (3, 2, 's2', 1000);
            INSERT INTO sessions VALUES (4, 2, 's3', 1000);
            INSERT INTO source_files VALUES (1, 1, 'video', '/p/one.mov');
            INSERT INTO source_files VALUES (2, 2, 'video', '/p/two.mov');
            INSERT INTO source_files VALUES (3, 3, 'video', '/p/three.mov');
            INSERT INTO source_files VALUES (4, 4, 'video', '/p/four.mov');
            INSERT INTO quotes VALUES (1, 1);
            INSERT INTO quotes VALUES (2, 2);
            INSERT INTO quotes VALUES (3, 2);
            INSERT INTO quote_edits VALUES (1, 1, 'edited in project 1');
            INSERT INTO quote_edits VALUES (2, 2, 'edited in project 2');
            INSERT INTO quote_tags VALUES (1, 1, 1, 'human');
            INSERT INTO quote_tags VALUES (2, 2, 1, 'human');
            INSERT INTO quote_tags VALUES (3, 3, 1, 'human');
            INSERT INTO quote_states VALUES (1, 1, 0, 1);
            INSERT INTO quote_states VALUES (2, 2, 0, 1);
            INSERT INTO quote_states VALUES (3, 3, 0, 1);
            INSERT INTO heading_edits VALUES (1, 1, 'theme-group-1:title', 'Mine');
            INSERT INTO heading_edits VALUES (2, 2, 'theme-group-1:title', 'Theirs');
            INSERT INTO heading_edits VALUES (3, 2, 'theme-group-2:title', 'Theirs too');
            """)
        }
    }

    // MARK: - SourceFilesReader

    /// The sidebar count must be the count the report shows — project 1's —
    /// not the sum across every row.
    @Test func sessionCountIsProjectOnesNotTheSum() throws {
        let root = try Self.forkedProject()
        defer { try? FileManager.default.removeItem(at: root) }
        let snap = SourceFilesReader.readSnapshot(projectRoot: root)
        #expect(snap.sessionCount == 1)
        #expect(snap.totalDurationSeconds == 600)
    }

    @Test func ingestedFilesAreProjectOnesOnly() throws {
        let root = try Self.forkedProject()
        defer { try? FileManager.default.removeItem(at: root) }
        let snap = SourceFilesReader.readSnapshot(projectRoot: root)
        #expect(snap.ingestedBasenames == ["one.mov"])
        #expect(snap.ingestedPaths == ["/p/one.mov"])
    }

    /// A healthy database still reads as before.
    @Test func aSingleRowDatabaseIsUnchanged() throws {
        let root = try Self.makeProject { db in
            Self.exec(db, """
            INSERT INTO projects VALUES (1, 'Study', '/p', '/p/bristlenose-output');
            INSERT INTO sessions VALUES (1, 1, 's1', 100);
            INSERT INTO sessions VALUES (2, 1, 's2', 200);
            INSERT INTO source_files VALUES (1, 1, 'video', '/p/a.mov');
            INSERT INTO source_files VALUES (2, 2, 'audio', '/p/b.m4a');
            """)
        }
        defer { try? FileManager.default.removeItem(at: root) }
        let snap = SourceFilesReader.readSnapshot(projectRoot: root)
        #expect(snap.sessionCount == 2)
        #expect(snap.totalDurationSeconds == 300)
        #expect(snap.ingestedBasenames == ["a.mov", "b.m4a"])
    }

    // MARK: - CurationCountsReader

    /// The re-analyse sheet weighs what the researcher would lose from the
    /// report they see — project 1's curation. `persons` is instance-scoped by
    /// design, so it is not in this fixture's second row.
    @Test func curationCountsAreProjectOnesOnly() throws {
        let root = try Self.forkedProject()
        defer { try? FileManager.default.removeItem(at: root) }
        let counts = try #require(CurationCountsReader.read(projectRoot: root))
        #expect(counts.editedQuotes == 1)
        #expect(counts.tags == 1)
        #expect(counts.starredQuotes == 1)
        #expect(counts.namedThemes == 1)
    }

    // MARK: - Unreadable is not zero (decision #1, 21 Oct 2026)
    //
    // A zero lets Re-analyse run `--clean` without asking, so a read that
    // FAILED must not come back as one. Until 21 Oct it did: an unopenable file
    // returned `.none`, and a file that opened but could not be read (not a
    // database, a torn page, an I/O error materialising an evicted file) had
    // every count's failure swallowed into 0. Both ran the destructive rebuild
    // with no confirmation.

    private static func dbURL(_ root: URL) -> URL {
        root.appendingPathComponent("bristlenose-output/.bristlenose/bristlenose.db")
    }

    @Test func curationCountsAreNilWhenTheFileIsNotADatabase() throws {
        let root = try Self.makeProject { _ in }
        defer { try? FileManager.default.removeItem(at: root) }
        try Data(repeating: 0x42, count: 8192).write(to: Self.dbURL(root))
        let counts: CurationCounts? = CurationCountsReader.read(projectRoot: root)
        #expect(counts == nil)
    }

    @Test func curationCountsAreNilWhenTheFileCannotBeOpened() throws {
        let root = try Self.forkedProject()
        let db = Self.dbURL(root)
        try FileManager.default.setAttributes([.posixPermissions: 0], ofItemAtPath: db.path)
        defer {
            try? FileManager.default.setAttributes([.posixPermissions: 0o644], ofItemAtPath: db.path)
            try? FileManager.default.removeItem(at: root)
        }
        let counts: CurationCounts? = CurationCountsReader.read(projectRoot: root)
        #expect(counts == nil)
    }

    /// The schema page reads, the table pages do not: `prepare` succeeds and
    /// `step` returns `SQLITE_CORRUPT`. Every page after the first is
    /// overwritten, so every curation table's root page is garbage.
    @Test func curationCountsAreNilWhenATablePageIsCorrupt() throws {
        let root = try Self.forkedProject()
        defer { try? FileManager.default.removeItem(at: root) }
        // The premise: the schema sits wholly on page 1, so what fails is the
        // count's step, not its prepare.
        var probe: OpaquePointer?
        try #require(sqlite3_open(Self.dbURL(root).path, &probe) == SQLITE_OK)
        var stmt: OpaquePointer?
        sqlite3_prepare_v2(probe, "PRAGMA page_size", -1, &stmt, nil)
        sqlite3_step(stmt)
        let pageSize = sqlite3_column_int(stmt, 0)
        sqlite3_finalize(stmt)
        sqlite3_close(probe)
        try #require(pageSize == 4096)
        let handle = try FileHandle(forUpdating: Self.dbURL(root))
        let size = try handle.seekToEnd()
        try #require(size > 4096)
        try handle.seek(toOffset: 4096)
        try handle.write(contentsOf: Data(repeating: 0xFF, count: Int(size) - 4096))
        try handle.close()
        let counts: CurationCounts? = CurationCountsReader.read(projectRoot: root)
        #expect(counts == nil)
    }

    /// A folder the app may not look into is not "no database": `fileExists`
    /// would say false and read as a zero. `stat` says `EACCES`.
    @Test func curationCountsAreNilWhenTheFolderCannotBeSearched() throws {
        let root = try Self.forkedProject()
        let dot = root.appendingPathComponent("bristlenose-output/.bristlenose")
        try FileManager.default.setAttributes([.posixPermissions: 0], ofItemAtPath: dot.path)
        defer {
            try? FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: dot.path)
            try? FileManager.default.removeItem(at: root)
        }
        let counts: CurationCounts? = CurationCountsReader.read(projectRoot: root)
        #expect(counts == nil)
    }

    /// Stars with no `quotes` table to scope them by cannot be counted, and must
    /// not count as none.
    @Test func curationCountsAreNilWhenAJoinTableIsMissing() throws {
        let root = try Self.forkedProject()
        defer { try? FileManager.default.removeItem(at: root) }
        var db: OpaquePointer?
        try #require(sqlite3_open(Self.dbURL(root).path, &db) == SQLITE_OK)
        Self.exec(db, "DROP TABLE quotes;")
        sqlite3_close(db)
        let counts: CurationCounts? = CurationCountsReader.read(projectRoot: root)
        #expect(counts == nil)
    }

    /// A column renamed by a later migration is a count that failed, not a zero.
    @Test func curationCountsAreNilWhenAColumnHasBeenRenamed() throws {
        let root = try Self.forkedProject()
        defer { try? FileManager.default.removeItem(at: root) }
        var db: OpaquePointer?
        try #require(sqlite3_open(Self.dbURL(root).path, &db) == SQLITE_OK)
        Self.exec(db, "ALTER TABLE quote_states RENAME COLUMN is_starred TO starred;")
        sqlite3_close(db)
        let counts: CurationCounts? = CurationCountsReader.read(projectRoot: root)
        #expect(counts == nil)
    }

    /// No database is a real zero: nothing has been served, so nothing has been
    /// curated, and Re-analyse need not ask.
    @Test func curationCountsAreZeroNotNilWithNoDatabase() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-db-readers-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let counts: CurationCounts? = CurationCountsReader.read(projectRoot: root)
        #expect(counts == CurationCounts.none)
    }

    /// An older schema without the curation tables is a real zero too: there is
    /// nothing of that kind to lose. Which tables exist is asked of
    /// `sqlite_master`, so this stays distinct from a file that can't be read.
    @Test func curationCountsAreZeroNotNilWithAnOlderSchema() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-db-readers-\(UUID().uuidString)")
        let dot = root.appendingPathComponent("bristlenose-output/.bristlenose")
        try FileManager.default.createDirectory(at: dot, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        var db: OpaquePointer?
        try #require(sqlite3_open(dot.appendingPathComponent("bristlenose.db").path, &db) == SQLITE_OK)
        Self.exec(db, "CREATE TABLE projects (id INTEGER PRIMARY KEY, name TEXT);")
        sqlite3_close(db)
        let counts: CurationCounts? = CurationCountsReader.read(projectRoot: root)
        #expect(counts == CurationCounts.none)
    }

    // MARK: - A commit still in the WAL (decision #115, 21 Oct 2026)
    //
    // The serve checkpoints after every commit, but a checkpoint cannot copy
    // frames past an open reader's snapshot, and nothing comes back for them
    // until the next commit. A star made while any statement was in flight
    // stays in `-wal`, the `immutable=1` read sees only the main file, and the
    // count read zero: Re-analyse ran `--clean` unasked over it. Measured
    // against the serve in `tests/test_serve_wal_visibility.py`.

    struct HolderError: Error, CustomStringConvertible { let description: String }

    /// The serve's stand-in: a `sqlite3` shell in its own process, holding the
    /// database open in WAL mode with automatic checkpoints off, so a commit
    /// stays in `-wal` until the test checkpoints it. Its own process because
    /// `dmsLockIsHeld` asks whether *another* process holds `-shm` (a process
    /// never sees its own POSIX locks), and running these tests under the
    /// sandboxed test host is what shows `F_GETLK` works there.
    final class Holder {
        private let process = Process()
        private let input = Pipe()
        private let errors = Pipe()
        private let dir: URL

        init(_ db: URL) throws {
            dir = db.deletingLastPathComponent()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/sqlite3")
            process.arguments = ["-bail", db.path]
            process.standardInput = input
            process.standardOutput = FileHandle.nullDevice
            process.standardError = errors
            try process.run()
            try run("PRAGMA journal_mode=WAL; PRAGMA wal_autocheckpoint=0;")
        }

        /// Runs `sql`, returning once the shell has finished it: the shell's
        /// stdout is buffered, so it signals by writing a file.
        func run(_ sql: String) throws {
            let mark = dir.appendingPathComponent("done-\(UUID().uuidString)")
            input.fileHandleForWriting.write(Data("\(sql)\n.once '\(mark.path)'\nSELECT 'ok';\n".utf8))
            let deadline = Date().addingTimeInterval(10)
            while (try? String(contentsOf: mark, encoding: .utf8))?.contains("ok") != true {
                guard process.isRunning, Date() < deadline else {
                    if process.isRunning { process.terminate() }
                    process.waitUntilExit()
                    let err = String(decoding: errors.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
                    throw HolderError(description: "sqlite3 did not finish `\(sql)`: \(err)")
                }
                usleep(10_000)
            }
            try? FileManager.default.removeItem(at: mark)
        }

        func close() {
            try? input.fileHandleForWriting.close()
            process.waitUntilExit()
        }
    }

    private static func walSize(_ root: URL) throws -> Int {
        let attrs = try FileManager.default.attributesOfItem(atPath: dbURL(root).path + "-wal")
        return (attrs[.size] as? Int) ?? 0
    }

    /// A project with one quote, its database held in WAL mode by another process.
    private static func heldProject() throws -> (URL, Holder) {
        let root = try makeProject { db in exec(db, "INSERT INTO quotes VALUES (1, 1);") }
        return (root, try Holder(dbURL(root)))
    }

    /// A second project folder holding copies of `files` (suffixes of the
    /// database name: "", "-wal", "-shm") from `root`. Nobody holds it open.
    private static func copyDatabase(of root: URL, _ files: [String]) throws -> URL {
        let copy = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-db-readers-\(UUID().uuidString)")
        let copyDB = dbURL(copy)
        try FileManager.default.createDirectory(
            at: copyDB.deletingLastPathComponent(), withIntermediateDirectories: true)
        for suffix in files {
            try FileManager.default.copyItem(
                atPath: dbURL(root).path + suffix, toPath: copyDB.path + suffix)
        }
        return copy
    }

    private static func read(_ root: URL, maintained: Bool) -> CurationCounts? {
        CurationCountsReader.read(projectRoot: root, shmIsMaintained: { _ in maintained }, betweenReads: {})
    }

    @Test func curationCountsAreNilWhileACommitIsOnlyInTheWAL() throws {
        let (root, holder) = try Self.heldProject()
        defer { try? FileManager.default.removeItem(at: root) }
        defer { holder.close() }
        try holder.run("INSERT INTO quote_states VALUES (1, 1, 0, 1);")
        let counts: CurationCounts? = CurationCountsReader.read(projectRoot: root)
        #expect(counts == nil)

        // Checkpointed, the main file holds the star and is counted, though
        // `-wal` keeps its size: SQLite reuses the file rather than truncating.
        // Counted at all only because the DMS probe saw the holder's lock.
        try holder.run("PRAGMA wal_checkpoint(PASSIVE);")
        try #require(try Self.walSize(root) > 0)
        let after = try #require(CurationCountsReader.read(projectRoot: root))
        #expect(after.starredQuotes == 1)
    }

    /// A served study with nothing curated still runs straight away: its WAL
    /// is fully checkpointed but not empty, which is every served database
    /// after its first write.
    @Test func curationCountsAreZeroWithAnIdleCheckpointedWAL() throws {
        let (root, holder) = try Self.heldProject()
        defer { try? FileManager.default.removeItem(at: root) }
        defer { holder.close() }
        try holder.run("INSERT INTO projects VALUES (1, 'P', '/p', '/p'); PRAGMA wal_checkpoint(PASSIVE);")
        try #require(try Self.walSize(root) > 0)
        let counts: CurationCounts? = CurationCountsReader.read(projectRoot: root)
        #expect(counts == CurationCounts.none)
    }

    /// A WAL with no index beside it (a copied folder, a leftover) may hold
    /// commits the main file lacks, and nothing says whether it does.
    @Test func curationCountsAreNilWhenTheWALHasNoIndex() throws {
        let (root, holder) = try Self.heldProject()
        defer { try? FileManager.default.removeItem(at: root) }
        defer { holder.close() }
        try holder.run("INSERT INTO quote_states VALUES (1, 1, 0, 1);")
        let copy = try Self.copyDatabase(of: root, ["", "-wal"])
        defer { try? FileManager.default.removeItem(at: copy) }
        #expect(Self.read(copy, maintained: true) == nil)
    }

    /// An index nobody holds open is one SQLite itself would rebuild before
    /// trusting. The copy is consistent and idle; only the lock is missing.
    @Test func curationCountsAreNilWhenNobodyHoldsTheIndex() throws {
        let (root, holder) = try Self.heldProject()
        defer { try? FileManager.default.removeItem(at: root) }
        defer { holder.close() }
        try holder.run("INSERT INTO projects VALUES (1, 'P', '/p', '/p'); PRAGMA wal_checkpoint(PASSIVE);")
        let copy = try Self.copyDatabase(of: root, ["", "-wal", "-shm"])
        defer { try? FileManager.default.removeItem(at: copy) }
        let counts: CurationCounts? = CurationCountsReader.read(projectRoot: copy)
        #expect(counts == nil)
        #expect(Self.read(copy, maintained: true) == CurationCounts.none)  // the lock is why
    }

    /// A stale index from the same WAL era: it says every frame is in the main
    /// file, and the WAL holds a later commit. A reader holding a snapshot
    /// stops the writer restarting the WAL, so the star lands in the same era.
    @Test func curationCountsAreNilWhenTheIndexIsBehindTheWAL() throws {
        let (root, holder) = try Self.heldProject()
        defer { try? FileManager.default.removeItem(at: root) }
        defer { holder.close() }
        try holder.run("INSERT INTO projects VALUES (1, 'P', '/p', '/p');")
        var reader: OpaquePointer?
        try #require(sqlite3_open(Self.dbURL(root).path, &reader) == SQLITE_OK)
        defer { sqlite3_close(reader) }
        Self.exec(reader, "BEGIN; SELECT COUNT(*) FROM projects;")
        try holder.run("PRAGMA wal_checkpoint(PASSIVE);")
        let staleIndex = try Data(contentsOf: URL(fileURLWithPath: Self.dbURL(root).path + "-shm"))
        try holder.run("INSERT INTO quote_states VALUES (1, 1, 0, 1);")
        Self.exec(reader, "COMMIT;")

        let copy = try Self.copyDatabase(of: root, ["", "-wal"])
        defer { try? FileManager.default.removeItem(at: copy) }
        try staleIndex.write(to: URL(fileURLWithPath: Self.dbURL(copy).path + "-shm"))
        // The premise: the stale index vouches for itself and is of this era.
        let wal = try Data(contentsOf: URL(fileURLWithPath: Self.dbURL(copy).path + "-wal"))
        try #require(staleIndex.subdata(in: 16..<20) == staleIndex.subdata(in: 96..<100))
        try #require(staleIndex.subdata(in: 32..<40) == wal.subdata(in: 16..<24))
        #expect(Self.read(copy, maintained: true) == nil)
    }

    /// A stale index from an earlier WAL era: the writer restarted the WAL
    /// for the star, so the index's salt is not the WAL's.
    @Test func curationCountsAreNilWhenTheIndexIsFromAnotherWALEra() throws {
        let (root, holder) = try Self.heldProject()
        defer { try? FileManager.default.removeItem(at: root) }
        defer { holder.close() }
        for id in 1...6 { try holder.run("INSERT INTO projects VALUES (\(id), 'P', '/p', '/p');") }
        try holder.run("PRAGMA wal_checkpoint(PASSIVE);")
        let staleIndex = try Data(contentsOf: URL(fileURLWithPath: Self.dbURL(root).path + "-shm"))
        try holder.run("INSERT INTO quote_states VALUES (1, 1, 0, 1);")

        let copy = try Self.copyDatabase(of: root, ["", "-wal"])
        defer { try? FileManager.default.removeItem(at: copy) }
        try staleIndex.write(to: URL(fileURLWithPath: Self.dbURL(copy).path + "-shm"))
        let wal = try Data(contentsOf: URL(fileURLWithPath: Self.dbURL(copy).path + "-wal"))
        try #require(staleIndex.subdata(in: 32..<40) != wal.subdata(in: 16..<24))
        #expect(Self.read(copy, maintained: true) == nil)
    }

    /// The index's two header copies disagree: a writer was mid-update.
    @Test func curationCountsAreNilWhenTheIndexHeaderCopiesDisagree() throws {
        let (root, holder) = try Self.heldProject()
        defer { try? FileManager.default.removeItem(at: root) }
        defer { holder.close() }
        try holder.run("INSERT INTO projects VALUES (1, 'P', '/p', '/p'); PRAGMA wal_checkpoint(PASSIVE);")
        let copy = try Self.copyDatabase(of: root, ["", "-wal", "-shm"])
        defer { try? FileManager.default.removeItem(at: copy) }
        try #require(Self.read(copy, maintained: true) == CurationCounts.none)
        let shm = URL(fileURLWithPath: Self.dbURL(copy).path + "-shm")
        var index = try Data(contentsOf: shm)
        index[8] ^= 0xFF  // iChange, first copy only
        try index.write(to: shm)
        #expect(Self.read(copy, maintained: true) == nil)
    }

    /// A commit landing between the check and the count (a star request still
    /// in flight when Re-analyse is picked) moves the index, and the count it
    /// may have missed is not trusted.
    @Test func curationCountsAreNilWhenACommitLandsWhileCounting() throws {
        let (root, holder) = try Self.heldProject()
        defer { try? FileManager.default.removeItem(at: root) }
        defer { holder.close() }
        try holder.run("INSERT INTO projects VALUES (1, 'P', '/p', '/p'); PRAGMA wal_checkpoint(PASSIVE);")
        let counts = CurationCountsReader.read(
            projectRoot: root, shmIsMaintained: CurationCountsReader.dmsLockIsHeld,
            betweenReads: {
                do {
                    try holder.run("INSERT INTO quote_states VALUES (1, 1, 0, 1); PRAGMA wal_checkpoint(PASSIVE);")
                } catch {
                    Issue.record("\(error)")
                }
            })
        #expect(counts == nil)
    }
}
