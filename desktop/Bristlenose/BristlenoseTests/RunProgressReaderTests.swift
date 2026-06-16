import Foundation
import Testing

@testable import Bristlenose

/// Pins the cross-language wire contract: Swift's `EventLogReader` decodes a
/// `run_progress` line written in Python's snake_case format, and the lifecycle
/// reader skips it (Finding 1 spine). A single mis-named `CodingKey` would
/// silently decode as nil — the ring would just stay a spinner with no failure
/// — exactly the silent regression a unit test catches.
@Suite struct RunProgressReaderTests {

    private func writeEvents(_ lines: [String]) throws -> URL {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(
            at: dir, withIntermediateDirectories: true
        )
        let url = dir.appendingPathComponent("pipeline-events.jsonl")
        try (lines.joined(separator: "\n") + "\n")
            .write(to: url, atomically: true, encoding: .utf8)
        return url
    }

    // Matches bristlenose/events.py model_dump_json(exclude_none=False).
    private let runStarted = #"""
    {"schema_version":1,"ts":"2026-06-16T10:00:00Z","event":"run_started","run_id":"RUN1","kind":"run","started_at":"2026-06-16T10:00:00Z","process":{"pid":1,"start_time":"x","hostname":"h","user":"u","bristlenose_version":"0","python_version":"3.12","os":"darwin-arm64"}}
    """#
    private let runProgress = #"""
    {"schema_version":1,"ts":"2026-06-16T10:01:00Z","event":"run_progress","run_id":"RUN1","kind":"run","started_at":"2026-06-16T10:00:00Z","stage":"transcribe","sessions_complete":2,"sessions_total":8,"stage_fraction":0.3,"eta_remaining_seconds":120.0,"predicted_total_seconds":200.0,"elapsed_seconds":40.0}
    """#

    @Test func latestProgressDecodesPythonFields() throws {
        let url = try writeEvents([runStarted, runProgress])
        let ev = EventLogReader.latestProgress(at: url)
        #expect(ev?.event == "run_progress")
        #expect(ev?.runId == "RUN1")
        #expect(ev?.stage == "transcribe")
        #expect(ev?.sessionsComplete == 2)
        #expect(ev?.sessionsTotal == 8)
        #expect(ev?.stageFraction == 0.3)
        #expect(ev?.etaRemainingSeconds == 120.0)
        #expect(ev?.predictedTotalSeconds == 200.0)
    }

    @Test func tailEventSkipsTrailingProgress() throws {
        // run_started then a trailing run_progress: the lifecycle read returns
        // the run_started, not the progress line — so a live run isn't read as
        // "ended" and the run-id gate has the right current run to match.
        let url = try writeEvents([runStarted, runProgress])
        let ev = EventLogReader.tailEvent(at: url)
        #expect(ev?.event == "run_started")
        #expect(ev?.runId == "RUN1")
    }
}
