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

    /// Progressive lenses: the count that hands the pane from the shoal to the
    /// report. Absent on older lines, where it must read as nil, not zero.
    @Test func sessionsReadableDecodesWhenPresent() throws {
        let readable = runProgress.replacingOccurrences(
            of: #""elapsed_seconds":40.0"#, with: #""elapsed_seconds":40.0,"sessions_readable":3"#
        )
        #expect(readable != runProgress, "the fixture line must actually change")
        #expect(EventLogReader.latestProgress(at: try writeEvents([runStarted, readable]))?
            .sessionsReadable == 3)
        #expect(EventLogReader.latestProgress(at: try writeEvents([runStarted, runProgress]))?
            .sessionsReadable == nil)
    }

    /// A re-analyse, before the new run has written its start: the log holds
    /// only the previous run, whose last line said every session was readable.
    /// That must not read as this run's progress (14 Oct 2026 — the shoal gave
    /// way to a status page five seconds into a re-analyse).
    @Test func thePreviousRunsProgressIsNotTheNewRuns() throws {
        let readable = runProgress.replacingOccurrences(
            of: #""elapsed_seconds":40.0"#, with: #""elapsed_seconds":40.0,"sessions_readable":8"#
        )
        let previousOnly = try writeEvents([runStarted, readable])
        #expect(EventLogReader.currentRunProgress(at: previousOnly, priorRunId: "RUN1") == nil)

        // The new run has started and said nothing yet: still nothing.
        let newStart = runStarted.replacingOccurrences(of: "RUN1", with: "RUN2")
        let started = try writeEvents([runStarted, readable, newStart])
        #expect(EventLogReader.currentRunProgress(at: started, priorRunId: "RUN1") == nil)

        // Its own first line is its progress.
        let newProgress = runProgress.replacingOccurrences(of: "RUN1", with: "RUN2")
        let going = try writeEvents([runStarted, readable, newStart, newProgress])
        let ev = EventLogReader.currentRunProgress(at: going, priorRunId: "RUN1")
        #expect(ev?.runId == "RUN2")
        #expect(ev?.sessionsReadable == nil)
    }

    /// Attached to a run already live, there is no prior run to exclude: its
    /// own start is the newest, and its progress is read as before.
    @Test func anAttachedRunReadsItsOwnProgress() throws {
        let url = try writeEvents([runStarted, runProgress])
        #expect(EventLogReader.currentRunProgress(at: url, priorRunId: nil)?.runId == "RUN1")
    }

    /// R26: on a large study the ring and the readable count froze partway.
    /// faster-whisper writes a progress line per decoded segment (~420 B, one
    /// every few seconds of audio), so a run's own `run_started` fell out of
    /// the fixed 64 KB tail after ~150 lines, `currentRunProgress` returned nil
    /// from then on, and the 1 Hz poll stopped folding anything in. Fixed by
    /// the widening tail read in 9eb4dafc; this drives the ring's own path
    /// through a study-sized log (40 sessions × 500 segments, ~8 MB).
    @Test func aLargeStudysProgressKeepsMovingTheRingAndTheReadableCount() throws {
        let sessions = 40, segmentsPerSession = 500
        var lines = [runStarted.replacingOccurrences(of: "RUN1", with: "RUN0"), runStarted]
        lines.reserveCapacity(sessions * segmentsPerSession + 2)
        for s in 0..<sessions {
            for seg in 0..<segmentsPerSession {
                let fraction = (Double(s) + Double(seg) / Double(segmentsPerSession)) / Double(sessions)
                lines.append(
                    #"{"schema_version":1,"ts":"2026-06-16T10:01:00Z","event":"run_progress","run_id":"RUN1","kind":"run","started_at":"2026-06-16T10:00:00Z","stage":"transcribe","sessions_complete":\#(s),"sessions_total":\#(sessions),"sessions_new":\#(sessions),"sessions_cached":0,"sessions_readable":\#(s),"stage_fraction":\#(fraction),"eta_remaining_seconds":null,"predicted_total_seconds":null,"elapsed_seconds":\#(Double(s * segmentsPerSession + seg))}"#
                )
            }
        }
        let url = try writeEvents(lines)
        let size = try #require(
            try FileManager.default.attributesOfItem(atPath: url.path)[.size] as? Int
        )
        try #require(size > 4 * 1_048_576, "the log must reach well past the first windows")

        let ev = try #require(
            EventLogReader.currentRunProgress(at: url, priorRunId: "RUN0"),
            "a long run's newest progress line must still be read as this run's"
        )
        #expect(ev.runId == "RUN1")
        #expect(ev.sessionsComplete == sessions - 1)
        #expect(ev.sessionsReadable == sessions - 1)

        // Folded into the ring as the poll does: it moves past where a frozen
        // read would have left it.
        let started = Date(timeIntervalSince1970: 0)
        var early = PipelineProgress(startedAt: started)
        early.ringFraction = 0.01
        let folded = RunProgressMath.apply(
            stage: ev.stage, sessionsComplete: ev.sessionsComplete,
            sessionsTotal: ev.sessionsTotal, stageFraction: ev.stageFraction,
            etaRemainingSeconds: ev.etaRemainingSeconds,
            predictedTotalSeconds: ev.predictedTotalSeconds,
            to: early, startedAt: started, now: started.addingTimeInterval(60)
        )
        #expect(folded.sessionsComplete == sessions - 1)
        #expect((folded.ringFraction ?? 0) > 0.9)
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
