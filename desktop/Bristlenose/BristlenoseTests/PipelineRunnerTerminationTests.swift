import Foundation
import Testing
@testable import Bristlenose

/// Tests for the disk-state-gated `.ready` transition in `PipelineRunner`.
///
/// Two layers:
///   1. `decideTermination(...)` — pure branch table, the core invariant: only
///      a manifest-confirmed `.ready` ever produces a `.ready` user-visible
///      state. Exit code 0 alone is never sufficient.
///   2. `readManifestState(...)` — disk derivation; exercises the path
///      `parseManifest` + `EventLogReader.deriveState` integration.
///
/// The state-machine glue itself (`handleTermination`'s generation re-check,
/// queue pump, cancel-vs-finish race) is exercised end-to-end by the cohort
/// walkthrough rather than here; the pure-function tests below pin the bit
/// that's most likely to regress silently.
///
/// Stays non-`@MainActor` — only exercises `nonisolated static` helpers.
struct PipelineRunnerTerminationTests {

    // MARK: - Helpers

    /// Build `<root>/bristlenose-output/.bristlenose/` and return the
    /// manifest URL (file not yet written — tests write it explicitly).
    private func makeProjectOutput() -> (root: URL, manifestURL: URL, dotBristlenose: URL) {
        let root = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("pipelinerunner-term-\(UUID().uuidString)")
        let outputDir = root.appendingPathComponent("bristlenose-output")
        let dotBn = outputDir.appendingPathComponent(".bristlenose")
        try? FileManager.default.createDirectory(at: dotBn, withIntermediateDirectories: true)
        return (root, dotBn.appendingPathComponent("pipeline-manifest.json"), dotBn)
    }

    private func writeRunCompletedEventLog(in dotBristlenose: URL) {
        let line = """
        {"schema_version":1,"ts":"2026-05-15T09:12:34Z","event":"run_completed","run_id":"01HZX","kind":"run","started_at":"2026-05-15T09:00:00Z","ended_at":"2026-05-15T09:12:34Z","outcome":"completed","cause":null}
        """
        let url = dotBristlenose.appendingPathComponent(EventLogReader.filename)
        try? (line + "\n").data(using: .utf8)?.write(to: url, options: .atomic)
    }

    private func isReady(_ state: PipelineState) -> Bool {
        if case .ready = state { return true }
        return false
    }

    private func isIdle(_ state: PipelineState) -> Bool {
        if case .idle = state { return true }
        return false
    }

    // MARK: - decideTermination — the pure-function branch table

    /// Exit 0 + disk says ready → accept ready. The clean-success path.
    @Test func decide_exit0_diskReady_acceptsReady() {
        let decision = PipelineRunner.decideTermination(
            exitStatus: 0, sidecarReportedSuccess: true,
            derived: .ready(Date(timeIntervalSince1970: 1_000_000))
        )
        guard case .accept(let state) = decision else {
            Issue.record("expected .accept, got \(decision)"); return
        }
        #expect(isReady(state))
    }

    /// Exit 0 + empty manifest → accept .idle (the silent-honesty case).
    /// This is the original bug being pinned: clean exit, no real work,
    /// must NOT produce .ready and must NOT produce a red toast.
    @Test func decide_exit0_diskIdle_acceptsIdleNotReady() {
        let decision = PipelineRunner.decideTermination(
            exitStatus: 0, sidecarReportedSuccess: true, derived: .idle
        )
        guard case .accept(let state) = decision else {
            Issue.record("expected .accept, got \(decision)"); return
        }
        #expect(isIdle(state))
        #expect(!isReady(state))
    }

    /// Exit 0 + slow-disk `.unreachable` → accept .unreachable. Sidebar's
    /// next passive scan will retry the read and resolve to .ready or .idle.
    /// Pinning the propagation (don't silently downgrade to .failed).
    @Test func decide_exit0_diskUnreachable_acceptsUnreachable() {
        let decision = PipelineRunner.decideTermination(
            exitStatus: 0, sidecarReportedSuccess: true,
            derived: .unreachable(reason: "Taking too long to respond.")
        )
        guard case .accept(let state) = decision else {
            Issue.record("expected .accept, got \(decision)"); return
        }
        if case .unreachable = state { /* ok */ } else {
            Issue.record("expected .unreachable, got \(state)")
        }
    }

    /// Non-zero exit + log markers passed + disk confirms ready → accept.
    /// The "uvicorn graceful shutdown exits 1 even on success" case.
    @Test func decide_nonZeroWithSuccessMarkers_diskReady_acceptsReady() {
        let decision = PipelineRunner.decideTermination(
            exitStatus: 1, sidecarReportedSuccess: true,
            derived: .ready(Date())
        )
        guard case .accept(let state) = decision else {
            Issue.record("expected .accept, got \(decision)"); return
        }
        #expect(isReady(state))
    }

    /// Non-zero exit + log markers passed + disk says NOT ready → fall
    /// through to failure. This is the asymmetry decision: when log
    /// markers lied (claimed success on a non-zero exit) and disk agrees
    /// the run didn't finish, surface a real failure rather than silence.
    @Test func decide_nonZeroWithSuccessMarkers_diskIdle_treatsAsFailure() {
        let decision = PipelineRunner.decideTermination(
            exitStatus: 1, sidecarReportedSuccess: true, derived: .idle
        )
        #expect(decision == .treatAsFailure)
    }

    /// Non-zero exit + no success markers → straight to failure.
    @Test func decide_nonZeroNoMarkers_treatsAsFailure() {
        let decision = PipelineRunner.decideTermination(
            exitStatus: 1, sidecarReportedSuccess: false, derived: .idle
        )
        #expect(decision == .treatAsFailure)
    }

    // MARK: - readManifestState — disk derivation integration

    /// Empty `.bristlenose/` (no manifest written) → .idle.
    @Test func readManifestState_emptyOutputDirReturnsIdle() async {
        let (root, manifestURL, _) = makeProjectOutput()
        defer { try? FileManager.default.removeItem(at: root) }

        let state = await PipelineRunner.readManifestState(
            at: manifestURL, timeout: .seconds(2)
        )
        #expect(isIdle(state))
    }

    /// Manifest stub + `run_completed` event → .ready.
    @Test func readManifestState_runCompletedEventReturnsReady() async {
        let (root, manifestURL, dotBn) = makeProjectOutput()
        defer { try? FileManager.default.removeItem(at: root) }

        let stub = #"{"stages":{}}"#
        try? stub.data(using: .utf8)?.write(to: manifestURL, options: .atomic)
        writeRunCompletedEventLog(in: dotBn)

        let state = await PipelineRunner.readManifestState(
            at: manifestURL, timeout: .seconds(2)
        )
        #expect(isReady(state))
    }

    // MARK: - looksLikeSuccess — deletion guard only

    /// Single positive assertion guards against accidental deletion of the
    /// helper. The heuristic is now a trigger (not a verdict), so don't
    /// over-pin its shape — it may be removed entirely in a future pass.
    @Test func looksLikeSuccess_recognisesCanonicalMarkers() {
        #expect(PipelineRunner.looksLikeSuccess(lines: ["Done", "Report: http://…"]))
    }
}
