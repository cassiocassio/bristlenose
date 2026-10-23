import Foundation
import SQLite3
import Testing
@testable import Bristlenose

/// A speaker recode into or out of participant is outstanding work, offered as
/// **Analyse** the way unanalysed files are (owner, 23 Oct 2026; design-people.md
/// §J7 R3). The per-session Re-analyse it replaces is gone: serve writes the
/// role pins as the recode lands, and the ordinary run honours them.
///
/// Three halves: the database read that counts owed sessions (its SQL is held
/// to Python's `needs_reanalysis` by `tests/test_swift_python_contract.py`), the
/// one Analyse gate every surface asks, and the report's nudge that makes the
/// sidebar read the database again.
@MainActor
@Suite struct RecodedSessionWorkTests {

    // MARK: - The count

    /// A project folder whose database holds one session per `(code, role)`
    /// pair list, in project 1 unless `project` says otherwise.
    private static func project(
        _ sessions: [[(code: String, role: String)]], project: Int = 1
    ) throws -> URL {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-recoded-\(UUID().uuidString)")
        let dot = root.appendingPathComponent("bristlenose-output/.bristlenose")
        try FileManager.default.createDirectory(at: dot, withIntermediateDirectories: true)
        var db: OpaquePointer?
        try #require(sqlite3_open(dot.appendingPathComponent("bristlenose.db").path, &db) == SQLITE_OK)
        defer { sqlite3_close(db) }
        var sql = """
        CREATE TABLE projects (id INTEGER PRIMARY KEY);
        CREATE TABLE sessions (id INTEGER PRIMARY KEY, project_id INTEGER, session_id TEXT, duration_seconds REAL);
        CREATE TABLE source_files (id INTEGER PRIMARY KEY, session_id INTEGER, path TEXT);
        CREATE TABLE session_speakers (id INTEGER PRIMARY KEY, session_id INTEGER, speaker_code TEXT, speaker_role TEXT);
        INSERT INTO projects VALUES (1);
        """
        var speaker = 0
        for (i, slots) in sessions.enumerated() {
            sql += "INSERT INTO sessions VALUES (\(i + 1), \(project), 's\(i + 1)', 60);\n"
            for slot in slots {
                speaker += 1
                sql += "INSERT INTO session_speakers VALUES (\(speaker), \(i + 1), '\(slot.code)', '\(slot.role)');\n"
            }
        }
        var err: UnsafeMutablePointer<CChar>?
        let rc = sqlite3_exec(db, sql, nil, nil, &err)
        #expect(rc == SQLITE_OK, "\(err.map { String(cString: $0) } ?? "")")
        return root
    }

    private static func count(_ root: URL) -> Int? {
        SourceFilesReader.readSnapshot(projectRoot: root).recodedSessionCount
    }

    @Test func anAgreeingStudyOwesNothing() throws {
        let root = try Self.project([[("m1", "researcher"), ("p1", "participant")],
                                     [("m1", "researcher"), ("o1", "observer"), ("p2", "participant")]])
        defer { try? FileManager.default.removeItem(at: root) }
        #expect(Self.count(root) == 0)
    }

    @Test func aRecodeIntoOrOutOfParticipantIsOwed() throws {
        let root = try Self.project([[("m1", "participant"), ("p1", "researcher")],
                                     [("p2", "observer")],
                                     [("m1", "researcher"), ("p3", "participant")]])
        defer { try? FileManager.default.removeItem(at: root) }
        // Two speakers in s1, one session: a session is owed once.
        #expect(Self.count(root) == 2)
    }

    @Test func moderatorToObserverIsNotOwed() throws {
        // Call 1: m ↔ o changes no evidence.
        let root = try Self.project([[("m1", "observer"), ("p1", "participant")]])
        defer { try? FileManager.default.removeItem(at: root) }
        #expect(Self.count(root) == 0)
    }

    @Test func anotherProjectRowIsNotCounted() throws {
        let root = try Self.project([[("p1", "researcher")]], project: 2)
        defer { try? FileManager.default.removeItem(at: root) }
        #expect(Self.count(root) == 0)
    }

    @Test func anOlderSchemaHasNoCountRatherThanZero() throws {
        let root = try Self.project([[("p1", "participant")]])
        defer { try? FileManager.default.removeItem(at: root) }
        var db: OpaquePointer?
        let path = root.appendingPathComponent("bristlenose-output/.bristlenose/bristlenose.db").path
        try #require(sqlite3_open(path, &db) == SQLITE_OK)
        sqlite3_exec(db, "DROP TABLE session_speakers;", nil, nil, nil)
        sqlite3_close(db)
        #expect(Self.count(root) == nil)
    }

    final class Box: @unchecked Sendable { var state: UnanalysedState? }

    /// The watcher carries the count to the sidebar: the whole path from the
    /// database to the state `analyseIsOffered` reads.
    @Test func theWatcherPublishesTheOwedCount() async throws {
        let root = try Self.project([[("m1", "researcher"), ("p1", "observer")],
                                     [("m1", "researcher"), ("p2", "participant")]])
        defer { try? FileManager.default.removeItem(at: root) }
        try Data("x".utf8).write(to: root.appendingPathComponent("interview.mp4"))
        let lease = try ProjectBookmarkLease(bookmarkData: root.bookmarkData(options: .withSecurityScope))
        let box = Box()
        let watcher = ProjectFolderWatcher(
            projectID: UUID(), lease: lease, initialKnownBasenames: [],
            onChange: { box.state = $0 })
        defer { watcher.stop() }
        let clock = ContinuousClock()
        let end = clock.now + .seconds(30)
        while box.state == nil && clock.now < end { try? await Task.sleep(for: .milliseconds(50)) }
        #expect(box.state?.sessionCount == 2)
        #expect(box.state?.recodedSessionCount == 1)
    }

    // MARK: - The gate

    private func analysed(recoded: Int = 0, newFiles: Int = 0, sessions: Int? = 3) -> UnanalysedState {
        UnanalysedState(
            newFiles: (0..<newFiles).map { URL(fileURLWithPath: "/tmp/p\($0).mp4") },
            missingFiles: [], sessionCount: sessions, totalDurationSeconds: nil,
            ingestableFileCount: 4, recodedSessionCount: recoded)
    }

    private func analyseOffered(_ state: PipelineState?, _ data: UnanalysedState) -> Bool {
        SidebarOutlineController.analyseIsOffered(
            hasPath: true, isAvailable: true, state: state, data: data)
    }

    @Test func aRecodedSessionOffersAnalyseOnAFinishedStudy() {
        #expect(analyseOffered(.ready(Date()), analysed(recoded: 1)))
        #expect(!analyseOffered(.ready(Date()), analysed(recoded: 0)), "nothing owed, nothing offered")
    }

    @Test func aRecodedSessionOffersAnalyseWhenTheRecordingsAreInSubfolders() {
        let data = UnanalysedState(newFiles: [], missingFiles: [], sessionCount: 3,
                                   totalDurationSeconds: nil, ingestableFileCount: 0,
                                   recodedSessionCount: 1)
        #expect(analyseOffered(.ready(Date()), data))
    }

    @Test func aRecodeDoesNotOfferAnalyseWhileARunIsBusy() {
        #expect(!analyseOffered(.running, analysed(recoded: 1)))
    }

    private func failure(_ bucket: PipelineSummary.BucketName,
                         _ category: CauseCategory = .unknown) -> PipelineSummary {
        let outcome = StageOutcome(
            attempted: 8, succeeded: 6, durationMs: 1000,
            failed: ["s4", "s7"].map { sid in
                SessionFailure(sessionId: sid, cause: Cause(
                    category: category, code: nil, message: "boom", provider: nil,
                    stage: nil, sessionId: sid, exitCode: nil, signal: nil, signalName: nil))
            })
        var s = PipelineSummary()
        switch bucket {
        case .ingest: s.ingest = outcome
        case .transcripts: s.transcripts = outcome
        case .topics: s.topics = outcome
        case .quotes: s.quotes = outcome
        case .themes: s.themes = outcome
        }
        return s
    }

    /// Decision 1b (4): a fresh start that finished with sessions failed
    /// continues by Analyse, which retries them. The survey found it hidden.
    @Test func aPartialCompletionWithFailedSessionsOffersAnalyse() {
        for bucket in [PipelineSummary.BucketName.transcripts, .topics, .quotes, .themes] {
            #expect(analyseOffered(.completedPartial(summary: failure(bucket)), analysed()),
                    "\(bucket)")
        }
    }

    /// A refusal is refused by every run: a format declined at ingest, or a
    /// recording with nobody talking in it, refused at transcription (Talismanic
    /// has four). Offering Analyse for those alone would be a button that
    /// changes nothing, for ever.
    @Test func aPartialCompletionOfRefusalsAloneDoesNotOfferAnalyse() {
        #expect(!analyseOffered(.completedPartial(summary: failure(.ingest, .unusableInput)), analysed()))
        #expect(!analyseOffered(.completedPartial(summary: failure(.transcripts, .unusableInput)), analysed()))
        #expect(analyseOffered(.completedPartial(summary: failure(.ingest, .unusableInput)), analysed(newFiles: 1)),
                "new files still are")
    }

    /// A recording iCloud didn't hand over in time is failed at ingest, and a
    /// later run may read it: not a refusal.
    @Test func aPartialCompletionOfAnUnfetchedRecordingOffersAnalyse() {
        #expect(analyseOffered(.completedPartial(summary: failure(.ingest, .cloudFetch)), analysed()))
    }

    /// RE#13's other endings of a fresh start that kept what finished: raised
    /// (run_failed), stopped (run_cancelled), and killed (no terminus, read as
    /// stranded, a `.failed`). Each continues by Analyse.
    @Test func everyUnfinishedFreshStartOffersAnalyse() {
        #expect(analyseOffered(.failed(.passthrough("credit ran out"), category: .unknown), analysed()))
        #expect(analyseOffered(.failedWithDiagnostic(summary: failure(.quotes)), analysed()))
        #expect(analyseOffered(.stopped(stagesComplete: ["transcribe"]), analysed()))
    }

    // MARK: - The nudge

    @Test func theReportsRecodeReachesTheWindow() {
        let bridge = BridgeHandler()
        #expect(bridge.speakersRecodedRequests == 0)
        bridge.handleMessage(["type": "project-action", "action": "speakers-recoded",
                              "data": ["sessionId": "s3"]])
        #expect(bridge.speakersRecodedRequests == 1)
    }

    @Test func theRetiredRequestDoesNothing() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "project-action", "action": "reanalyse-session",
                              "data": ["sessionId": "s3"]])
        #expect(bridge.speakersRecodedRequests == 0)
    }
}
