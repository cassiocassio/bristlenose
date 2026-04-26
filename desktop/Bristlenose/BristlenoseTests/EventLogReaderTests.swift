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
        let pidURL = dir.appendingPathComponent(EventLogReader.pidFilename)
        let lstart = lstartForCurrentProcess() ?? "fallback"
        let body = "{\"pid\":\(getpid()),\"start_time\":\"\(lstart)\",\"run_id\":\"X\"}"
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

    private func lstartForCurrentProcess() -> String? {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/bin/ps")
        proc.arguments = ["-o", "lstart=", "-p", String(getpid())]
        let pipe = Pipe()
        proc.standardOutput = pipe
        do { try proc.run() } catch { return nil }
        proc.waitUntilExit()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        return String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
