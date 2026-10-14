import Foundation
import Testing
@testable import Bristlenose

/// The runner, not only the reader: a re-analyse must not hand the pane from
/// the shoal to the report on the previous run's "every session readable".
///
/// `RunProgressReaderTests` pins `EventLogReader.currentRunProgress`; this pins
/// the caller that has to give it the previous run's id. Without the capture in
/// `beginSpawnedRun`, the reader is called with nil and the previous run's line
/// reads as this run's — which is what the Mac did on 14 Oct 2026.
@MainActor
@Suite struct PipelineRunnerProgressTests {

    private func events(_ lines: [String], in project: Project) throws -> URL {
        let url = PipelineRunner.eventsURL(for: project)
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try (lines.joined(separator: "\n") + "\n").write(to: url, atomically: true, encoding: .utf8)
        return url
    }

    private func started(_ run: String) -> String {
        #"{"schema_version":1,"ts":"2026-10-14T21:00:00Z","event":"run_started","run_id":"\#(run)","kind":"run","started_at":"2026-10-14T21:00:00Z","process":{"pid":1,"start_time":"x","hostname":"h","user":"u","bristlenose_version":"0","python_version":"3.12","os":"darwin-arm64"}}"#
    }

    private func readable(_ run: String, _ n: Int) -> String {
        #"{"schema_version":1,"ts":"2026-10-14T21:01:00Z","event":"run_progress","run_id":"\#(run)","kind":"run","started_at":"2026-10-14T21:00:00Z","stage":"transcribe","sessions_readable":\#(n)}"#
    }

    @Test func aReanalyseDoesNotReadThePreviousRunsReadableSessions() async throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-progress-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: dir) }
        let project = Project(id: UUID(), name: "Re-analyse", path: dir.path)
        let url = try events([started("OLD"), readable("OLD", 8)], in: project)

        let runner = PipelineRunner()
        runner.beginSpawnedRun(project)
        await runner.applyEventProgress(from: url, for: project.id)
        #expect(runner.sessionsReadable[project.id] == nil,
                "the previous run's count lifted the shoal before the new run began")

        // The new run starts and delivers its first session.
        _ = try events([started("OLD"), readable("OLD", 8), started("NEW"), readable("NEW", 1)],
                       in: project)
        await runner.applyEventProgress(from: url, for: project.id)
        #expect(runner.sessionsReadable[project.id] == 1)
    }
}
