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
        let counts = CurationCountsReader.read(projectRoot: root)
        #expect(counts.editedQuotes == 1)
        #expect(counts.tags == 1)
        #expect(counts.starredQuotes == 1)
        #expect(counts.namedThemes == 1)
    }
}
