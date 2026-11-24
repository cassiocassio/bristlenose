import Foundation
import Testing
@testable import Bristlenose

/// The Mac's AutoCode parsers fed the server's own answers, captured from a real run on
/// 24 Nov 2026 (a UXR first apply on a scratch copy of the public Talismanic study, Claude
/// Sonnet 4.6, stopped after its first batch; `docs/design-autocode-landing-plan.md`, Phase 4
/// measurements). The other suites build their JSON by hand; this one pins that what the server
/// really sends, field for field, reads as the row's line (D23, D40): a running first apply is
/// "AutoCode · N of M", and a stop is "Stopped", keyed by the run. Counts, a title and a time
/// only; no participant text.
@Suite struct AutoCodeRealAnswerTests {

    private func object(_ body: String) throws -> [String: Any] {
        let data = try #require(body.data(using: .utf8))
        return try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    /// `GET /api/projects/1/autocode/jobs` while the run coded its first batch.
    private let running = """
    {"jobs": [{"framework_id": "uxr", "title": "Bristlenose UXR Codebook", "status": "running",
    "completed_at": null, "processed_quotes": 0, "total_quotes": 111}]}
    """

    /// `GET /api/projects/1/autocode/jobs?include_ended=true` once the stop had settled.
    private let stopped = """
    {"jobs": [{"framework_id": "uxr", "title": "Bristlenose UXR Codebook", "status": "cancelled",
    "completed_at": null, "processed_quotes": 65, "total_quotes": 111, "failure_kind": "",
    "started_at": "2026-11-24T03:05:39", "catch_up_total": 0, "catch_up_processed": 0}]}
    """

    @Test func aRunningFirstApplyReadsAsItsCount() throws {
        let progress = try #require(AutoCodeProgress.parse(try object(running)))
        #expect(progress == AutoCodeProgress(done: 0, total: 111, frameworkID: "uxr"))
    }

    @Test func aStoppedRunReadsAsStopped() throws {
        let lines = AutoCodeEndedLine.parseAll(try object(stopped))
        #expect(lines.count == 1)
        let line = try #require(lines.first)
        #expect(line.outcome == .stopped)
        #expect(line.frameworkID == "uxr")
        #expect(line.title == "Bristlenose UXR Codebook")
        #expect(line.processed == 65 && line.total == 111)
        #expect(line.key.contains("2026-11-24T03:05:39"))
    }

    @Test func theEndedAnswerShowsNoRunningCount() throws {
        #expect(AutoCodeProgress.parse(try object(stopped)) == nil)
    }
}
