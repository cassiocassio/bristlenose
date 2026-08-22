import Foundation
import Testing
@testable import Bristlenose

/// Tests for `EventLogReader` — Phase 1f Slice 4.
///
/// Fixture-driven: tests synthesise `pipeline-events.jsonl` lines that
/// match the Python writer's shape (`bristlenose/events.py`), then assert
/// that the reader maps to the right `PipelineState`.
///
/// PID-liveness tests are best-effort — they use the test process's own
/// PID + ps lstart so they're portable across macOS / CI Linux runners.
struct EventLogReaderTests {

    // MARK: - Helpers

    /// Write a JSONL file at `<dir>/pipeline-events.jsonl` from the given lines.
    private func writeEventLog(in dir: URL, lines: [String]) {
        let url = dir.appendingPathComponent(EventLogReader.filename)
        let body = lines.joined(separator: "\n") + "\n"
        try? body.data(using: .utf8)?.write(to: url, options: .atomic)
    }

    /// Make a temp directory inside `NSTemporaryDirectory()`. Caller cleans up.
    private func makeTempDir() -> URL {
        let url = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("evlog-tests-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    private func runStartedLine(runID: String = "01HZX4N9MXQ5T7B3YJZP2K8FCV", kind: String = "run") -> String {
        """
        {"schema_version":1,"ts":"2026-04-25T09:00:00Z","event":"run_started","run_id":"\(runID)","kind":"\(kind)","started_at":"2026-04-25T09:00:00Z","process":{"pid":1,"start_time":"2026-04-25T09:00:00Z","hostname":"h","user":"u","bristlenose_version":"0","python_version":"3","os":"x"}}
        """
    }

    private func runCompletedLine(runID: String = "01HZX4N9MXQ5T7B3YJZP2K8FCV", kind: String = "run") -> String {
        """
        {"schema_version":1,"ts":"2026-04-25T09:12:34Z","event":"run_completed","run_id":"\(runID)","kind":"\(kind)","started_at":"2026-04-25T09:00:00Z","ended_at":"2026-04-25T09:12:34Z","outcome":"completed","cause":null}
        """
    }

    private func runCancelledLine(runID: String = "01HZX4N9MXQ5T7B3YJZP2K8FCV") -> String {
        """
        {"schema_version":1,"ts":"2026-04-25T09:05:00Z","event":"run_cancelled","run_id":"\(runID)","kind":"run","started_at":"2026-04-25T09:00:00Z","ended_at":"2026-04-25T09:05:00Z","outcome":"cancelled","cause":{"category":"user_signal","signal":2,"signal_name":"SIGINT","message":"SIGINT received"}}
        """
    }

    private func runFailedLine(category: String, message: String) -> String {
        """
        {"schema_version":1,"ts":"2026-04-25T09:05:00Z","event":"run_failed","run_id":"01H","kind":"run","started_at":"2026-04-25T09:00:00Z","ended_at":"2026-04-25T09:05:00Z","outcome":"failed","cause":{"category":"\(category)","message":"\(message)"}}
        """
    }

    // MARK: - Bare reader

    @Test func tailEventReturnsNilWhenFileMissing() {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        let event = EventLogReader.tailEvent(at: dir.appendingPathComponent(EventLogReader.filename))
        #expect(event == nil)
    }

    @Test func tailEventReturnsMostRecentRunStarted() {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        writeEventLog(in: dir, lines: [runStartedLine()])
        let event = EventLogReader.tailEvent(at: dir.appendingPathComponent(EventLogReader.filename))
        #expect(event?.event == "run_started")
        #expect(event?.kind == "run")
    }

    @Test func tailEventPicksLatestWhenMultipleEvents() {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        writeEventLog(in: dir, lines: [runStartedLine(), runCompletedLine()])
        let event = EventLogReader.tailEvent(at: dir.appendingPathComponent(EventLogReader.filename))
        #expect(event?.event == "run_completed")
    }

    @Test func tailEventSurvivesNULPaddedTail() {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        let url = dir.appendingPathComponent(EventLogReader.filename)
        var body = (runStartedLine() + "\n").data(using: .utf8)!
        body.append(Data(repeating: 0x00, count: 1024))
        try? body.write(to: url, options: .atomic)
        let event = EventLogReader.tailEvent(at: url)
        #expect(event?.event == "run_started")
    }

    @Test func tailEventRefusesToAnswerFromAnOlderEventWhenTheNewestDoesNotFit() {
        // REGRESSION LOCK for the bug behind the bug.
        //
        // A terminus line that is well-formed JSON but doesn't fit `Event` means
        // the Python↔Swift contract drifted. The old loop skipped it and
        // answered from the line behind — so a run that COMPLETED was reported
        // as `.failed("Analysis stopped unexpectedly.")`, because the fallback
        // landed on that run's own `run_started` and the PID was gone. The
        // report was fine the whole time; only the row lied, and
        // `applyScanResult` then preserved the lie across relaunch.
        //
        // Refusing to answer is the honest outcome: nil sends `deriveState`
        // back to manifest inference instead of asserting a crash.
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        let url = dir.appendingPathComponent(EventLogReader.filename)
        // Valid JSON, wrong shape for Event (`kind` must be a String).
        let drifted = #"{"event":"run_completed","kind":42,"run_id":"x","started_at":"t"}"#
        writeEventLog(in: dir, lines: [runStartedLine(), drifted])

        #expect(EventLogReader.tailEvent(at: url) == nil)
        // And the derived state must not be a confident wrong verdict.
        let state = EventLogReader.deriveState(
            eventsURL: url,
            pidURL: dir.appendingPathComponent(EventLogReader.pidFilename),
            stagesComplete: []
        )
        #expect(state == nil, "must fall back to manifest inference, not claim a crash")
    }

    @Test func tailEventStillWalksPastAnUnparseableTornLine() {
        // The counterpart to the test above: the guard must NOT break crash
        // recovery. A line that isn't valid JSON at all is a torn write, and
        // skipping it is correct — the distinction is JSON-validity, not
        // decode success.
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        let url = dir.appendingPathComponent(EventLogReader.filename)
        let body = runStartedLine() + "\n" + "{\"event\":\"run_comp"
        try? body.data(using: .utf8)?.write(to: url, options: .atomic)
        #expect(EventLogReader.tailEvent(at: url)?.event == "run_started")
    }

    @Test func tailEventSurvivesPartialTrailingLine() {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        let url = dir.appendingPathComponent(EventLogReader.filename)
        let body = runStartedLine() + "\n" + "{partial broken json no newline"
        try? body.data(using: .utf8)?.write(to: url, options: .atomic)
        let event = EventLogReader.tailEvent(at: url)
        // The partial line doesn't parse; the good line still does.
        #expect(event?.event == "run_started")
    }

    // MARK: - Reaching the reader at all (parseManifest guard order)
    //
    // Every test below this file's other MARK calls `deriveState` directly, so
    // none of them can see whether the caller ever gets there. That was the
    // defect: `--clean` removes the manifest, the pipeline writes a new one
    // only after ingest, and `parseManifest` answered `.idle` at the
    // manifest-missing guard without consulting the events log. A failed
    // re-analysis therefore read as "never analysed" on the next launch, and
    // `Show Diagnostics…` — gated on the failure state — disappeared with it.

    /// A failure recorded on Tuesday is still a failure on Wednesday, even
    /// though `--clean` took the manifest with it.
    @Test func manifestAbsentButRunFailedPresentStillReportsFailure() async {
        let project = makeTempDir()
        defer { try? FileManager.default.removeItem(at: project) }
        let dot = project
            .appendingPathComponent("bristlenose-output", isDirectory: true)
            .appendingPathComponent(".bristlenose", isDirectory: true)
        try? FileManager.default.createDirectory(at: dot, withIntermediateDirectories: true)
        writeEventLog(in: dot, lines: [
            runStartedLine(),
            runFailedLine(category: "unusable_input", message: "Couldn't read one of the recordings"),
        ])
        // Deliberately no manifest at this path.
        let manifestURL = dot.appendingPathComponent("manifest.json")
        #expect(!FileManager.default.fileExists(atPath: manifestURL.path))

        let state = await PipelineRunner.parseManifest(at: manifestURL)
        guard case .failed = state else {
            Issue.record("expected .failed with no manifest present, got \(state)")
            return
        }
    }

    /// The case the old guard existed to serve must keep working: a project
    /// with no manifest *and* no history is genuinely idle, not failed.
    @Test func manifestAbsentAndNoEventLogIsStillIdle() async {
        let project = makeTempDir()
        defer { try? FileManager.default.removeItem(at: project) }
        let dot = project
            .appendingPathComponent("bristlenose-output", isDirectory: true)
            .appendingPathComponent(".bristlenose", isDirectory: true)
        try? FileManager.default.createDirectory(at: dot, withIntermediateDirectories: true)

        let state = await PipelineRunner.parseManifest(at: dot.appendingPathComponent("manifest.json"))
        guard case .idle = state else {
            Issue.record("expected .idle for a project with no manifest and no events, got \(state)")
            return
        }
    }

    // MARK: - State derivation

    @Test func deriveStateMissingFileReturnsNil() {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        let result = EventLogReader.deriveState(
            eventsURL: dir.appendingPathComponent(EventLogReader.filename),
            pidURL: dir.appendingPathComponent(EventLogReader.pidFilename),
            stagesComplete: [],
        )
        #expect(result == nil)
    }

    @Test func deriveStateRunCompletedRunMapsToReady() {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        writeEventLog(in: dir, lines: [runStartedLine(), runCompletedLine(kind: "run")])
        let result = EventLogReader.deriveState(
            eventsURL: dir.appendingPathComponent(EventLogReader.filename),
            pidURL: dir.appendingPathComponent(EventLogReader.pidFilename),
            stagesComplete: ["ingest", "render"],
        )
        if case .ready = result {
            // ok
        } else {
            Issue.record("expected .ready, got \(String(describing: result))")
        }
    }

    @Test func deriveStateRunCompletedTranscribeOnlyMapsToPartial() {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        writeEventLog(in: dir, lines: [
            runStartedLine(kind: "transcribe-only"),
            runCompletedLine(kind: "transcribe-only"),
        ])
        let stages = ["ingest", "extract_audio", "transcribe"]
        let result = EventLogReader.deriveState(
            eventsURL: dir.appendingPathComponent(EventLogReader.filename),
            pidURL: dir.appendingPathComponent(EventLogReader.pidFilename),
            stagesComplete: stages,
        )
        guard case .partial(let kind, let stagesComplete) = result else {
            Issue.record("expected .partial, got \(String(describing: result))")
            return
        }
        #expect(kind == "transcribe-only")
        #expect(stagesComplete == stages)
    }

    @Test func deriveStateRunCancelledMapsToStopped() {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        writeEventLog(in: dir, lines: [runStartedLine(), runCancelledLine()])
        let result = EventLogReader.deriveState(
            eventsURL: dir.appendingPathComponent(EventLogReader.filename),
            pidURL: dir.appendingPathComponent(EventLogReader.pidFilename),
            stagesComplete: ["ingest", "extract_audio"],
        )
        guard case .stopped(let stages) = result else {
            Issue.record("expected .stopped, got \(String(describing: result))")
            return
        }
        #expect(stages == ["ingest", "extract_audio"])
    }

    @Test(arguments: [
        ("auth", PipelineFailureCategory.auth),
        ("network", .network),
        ("quota", .quota),
        ("disk", .disk),
        ("whisper", .whisper),
        ("user_signal", .userSignal),
        ("api_request", .apiRequest),
        ("api_server", .apiServer),
        ("missing_dep", .missingDep),
        ("output_truncated", .outputTruncated),
        ("unknown", .unknown),
    ])
    func deriveStateRunFailedMapsAllCategories(rawCategory: String, expected: PipelineFailureCategory) {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        writeEventLog(in: dir, lines: [
            runStartedLine(),
            runFailedLine(category: rawCategory, message: "boom"),
        ])
        let result = EventLogReader.deriveState(
            eventsURL: dir.appendingPathComponent(EventLogReader.filename),
            pidURL: dir.appendingPathComponent(EventLogReader.pidFilename),
            stagesComplete: [],
        )
        guard case .failed(let summary, let category) = result else {
            Issue.record("expected .failed, got \(String(describing: result))")
            return
        }
        #expect(summary == "boom")
        #expect(category == expected)
    }

    @Test func deriveStateStrandedRunStartedMapsToFailedUnknown() {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        writeEventLog(in: dir, lines: [runStartedLine()])
        // No PID file → process is not alive.
        let result = EventLogReader.deriveState(
            eventsURL: dir.appendingPathComponent(EventLogReader.filename),
            pidURL: dir.appendingPathComponent(EventLogReader.pidFilename),
            stagesComplete: [],
        )
        guard case .failed(_, let category) = result else {
            Issue.record("expected .failed, got \(String(describing: result))")
            return
        }
        #expect(category == .unknown)
    }

    // MARK: - PID-liveness

    @Test func pythonOwnedRunIsAliveReturnsFalseWhenFileMissing() {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        let alive = EventLogReader.pythonOwnedRunIsAlive(
            at: dir.appendingPathComponent(EventLogReader.pidFilename),
        )
        #expect(alive == false)
    }

    @Test func pythonOwnedRunIsAliveReturnsFalseForDeadPID() {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        let url = dir.appendingPathComponent(EventLogReader.pidFilename)
        let body = "{\"pid\":999999,\"start_time\":\"any\",\"run_id\":\"X\"}"
        try? body.data(using: .utf8)?.write(to: url, options: .atomic)
        #expect(EventLogReader.pythonOwnedRunIsAlive(at: url) == false)
    }

    @Test func pythonOwnedRunIsAliveReturnsFalseForStartTimeMismatch() {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        let url = dir.appendingPathComponent(EventLogReader.pidFilename)
        // Use the test process's PID — alive — but a wrong start_time.
        let body = "{\"pid\":\(getpid()),\"start_time\":\"Wrong Date\",\"run_id\":\"X\"}"
        try? body.data(using: .utf8)?.write(to: url, options: .atomic)
        #expect(EventLogReader.pythonOwnedRunIsAlive(at: url) == false)
    }

    // MARK: - State derivation × live PID file

    @Test func deriveStateRunStartedWithLivePIDFileMapsToRunning() {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        writeEventLog(in: dir, lines: [runStartedLine()])
        // Write a PID file pointing at this test process so liveness check passes.
        // start_time uses the same libproc query the production code reads with —
        // a `proc_pidinfo(PROC_PIDTBSDINFO)` "<tvsec>.<tvusec>" token, byte-identical
        // to what Python's run_lifecycle._ps_start_time writes on macOS. Deterministic
        // and sandbox-safe (no /bin/ps subprocess).
        let pidURL = dir.appendingPathComponent(EventLogReader.pidFilename)
        guard let start = EventLogReader.procStartTime(pid: getpid()) else {
            Issue.record("procStartTime(getpid()) returned nil — libproc query failed")
            return
        }
        let body = "{\"pid\":\(getpid()),\"start_time\":\"\(start)\",\"run_id\":\"X\"}"
        try? body.data(using: .utf8)?.write(to: pidURL, options: .atomic)
        let result = EventLogReader.deriveState(
            eventsURL: dir.appendingPathComponent(EventLogReader.filename),
            pidURL: pidURL,
            stagesComplete: [],
        )
        guard case .running = result else {
            Issue.record("expected .running, got \(String(describing: result))")
            return
        }
    }

    // MARK: - v5 PipelineSummary routing (Finding 7)

    /// A `run_completed` line carrying a minimal v5 `summary` block with N
    /// transcript failures.
    private func runCompletedWithSummary(failures: Int) -> String {
        let failedJSON = (0..<failures).map { i in
            """
            {"session_id":"s\(i)","cause":{"category":"whisper","code":null,"message":"x","provider":null,"stage":"s05_transcribe","session_id":"s\(i)","exit_code":null,"signal":null,"signal_name":null}}
            """
        }.joined(separator: ",")
        let summary = """
        {"transcripts":{"attempted":\(failures + 1),"succeeded":1,"duration_ms":1000,"failed":[\(failedJSON)]},"topics":null,"quotes":null,"themes":null}
        """
        return """
        {"schema_version":1,"ts":"2026-04-25T09:12:34Z","event":"run_completed","run_id":"01H","kind":"run","started_at":"2026-04-25T09:00:00Z","ended_at":"2026-04-25T09:12:34Z","outcome":"completed","cause":null,"summary":\(summary)}
        """
    }

    /// A `run_failed` line carrying a populated v5 summary (abandon path).
    private func runFailedWithSummary(category: String) -> String {
        let summary = """
        {"transcripts":null,"topics":null,"quotes":{"attempted":2,"succeeded":0,"duration_ms":100,"failed":[{"session_id":"s1","cause":{"category":"\(category)","code":null,"message":"x","provider":null,"stage":"s09","session_id":"s1","exit_code":null,"signal":null,"signal_name":null}}]},"themes":null}
        """
        return """
        {"schema_version":1,"ts":"2026-04-25T09:05:00Z","event":"run_failed","run_id":"01H","kind":"run","started_at":"2026-04-25T09:00:00Z","ended_at":"2026-04-25T09:05:00Z","outcome":"failed","cause":{"category":"\(category)","message":"abandoned"},"summary":\(summary)}
        """
    }

    @Test func deriveStateRunCompletedWithFailuresMapsToCompletedPartial() {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        writeEventLog(in: dir, lines: [
            runStartedLine(),
            runCompletedWithSummary(failures: 2),
        ])
        let result = EventLogReader.deriveState(
            eventsURL: dir.appendingPathComponent(EventLogReader.filename),
            pidURL: dir.appendingPathComponent(EventLogReader.pidFilename),
            stagesComplete: [],
        )
        guard case .completedPartial(let summary) = result else {
            Issue.record("expected .completedPartial, got \(String(describing: result))")
            return
        }
        #expect(summary.totalFailureCount == 2)
    }

    @Test func deriveStateRunCompletedWithNilSummaryStaysReady() {
        // Pre-v5 logs and v5 logs from clean transcribe-then-analyze runs
        // carry no `summary` (or null). Must keep mapping to `.ready` so the
        // sidebar pill doesn't surface a diagnostic.
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        writeEventLog(in: dir, lines: [
            runStartedLine(),
            runCompletedLine(),  // no summary field
        ])
        let result = EventLogReader.deriveState(
            eventsURL: dir.appendingPathComponent(EventLogReader.filename),
            pidURL: dir.appendingPathComponent(EventLogReader.pidFilename),
            stagesComplete: [],
        )
        guard case .ready = result else {
            Issue.record("expected .ready, got \(String(describing: result))")
            return
        }
    }

    @Test func deriveStateRunFailedWithSummaryMapsToFailedWithDiagnostic() {
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        writeEventLog(in: dir, lines: [
            runStartedLine(),
            runFailedWithSummary(category: "auth"),
        ])
        let result = EventLogReader.deriveState(
            eventsURL: dir.appendingPathComponent(EventLogReader.filename),
            pidURL: dir.appendingPathComponent(EventLogReader.pidFilename),
            stagesComplete: [],
        )
        guard case .failedWithDiagnostic(let summary) = result else {
            Issue.record("expected .failedWithDiagnostic, got \(String(describing: result))")
            return
        }
        #expect(summary.dominantCategory() == .auth)
    }

    @Test func deriveStateRunFailedWithNilSummaryUsesLegacyFailed() {
        // Pre-v5 logs lack `summary` on failure events. Must fall through to
        // the legacy `.failed(summary, category:)` surface so older runs
        // (and runs from CLI users on older Bristlenose) keep rendering.
        let dir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        writeEventLog(in: dir, lines: [
            runStartedLine(),
            runFailedLine(category: "auth", message: "boom"),
        ])
        let result = EventLogReader.deriveState(
            eventsURL: dir.appendingPathComponent(EventLogReader.filename),
            pidURL: dir.appendingPathComponent(EventLogReader.pidFilename),
            stagesComplete: [],
        )
        guard case .failed(let summary, let category) = result else {
            Issue.record("expected .failed, got \(String(describing: result))")
            return
        }
        #expect(summary == "boom")
        #expect(category == .auth)
    }
}
