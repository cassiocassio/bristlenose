import Foundation
import Testing
@testable import Bristlenose

/// R21 (20 Oct 2026): Stop on a run the app started left the row blank
/// (`.idle`), while the same Stop on a reconnected run read "Stopped" — the
/// orphan path re-reads what the run left on disk, the owned path did not.
/// Driven through the real `PipelineRunner` with the queue tests' rig.
@MainActor
struct PipelineRunnerStopStateTests {

    private typealias Rig = PipelineRunnerQueueTests.Rig

    private func until(_ condition: () -> Bool, seconds: Double = 5) async {
        let deadline = Date().addingTimeInterval(seconds)
        while !condition(), Date() < deadline {
            try? await Task.sleep(for: .milliseconds(10))
        }
    }

    /// What the CLI leaves when SIGINT stops it: a manifest with the stages
    /// that finished, and `run_cancelled` as the events log's last line.
    private static func writeCancelledRun(at path: String) {
        let dir = URL(fileURLWithPath: path)
            .appendingPathComponent("bristlenose-output/.bristlenose")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let manifest = #"{"stages":{"transcribe":{"status":"complete","completed_at":"2026-10-20T10:00:00+00:00"},"render":{"status":"pending"}}}"#
        try? Data(manifest.utf8).write(to: dir.appendingPathComponent("pipeline-manifest.json"))
        let lines = [
            #"{"schema_version":5,"ts":"2026-10-20T09:00:00Z","event":"run_started","run_id":"run-1","kind":"run","started_at":"2026-10-20T09:00:00Z"}"#,
            #"{"schema_version":5,"ts":"2026-10-20T10:00:00Z","event":"run_cancelled","run_id":"run-1","kind":"run","started_at":"2026-10-20T09:00:00Z","ended_at":"2026-10-20T10:00:00Z","outcome":"cancelled","cause":null}"#,
        ]
        try? Data((lines.joined(separator: "\n") + "\n").utf8)
            .write(to: dir.appendingPathComponent(EventLogReader.filename))
    }

    @Test func stoppingTheAppsOwnRunReadsStopped() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.onSignal = { launch, sig in
            guard sig == SIGINT else { return }
            Self.writeCancelledRun(at: launch.project.path)
            launch.exit(.exited(code: 130))
        }
        rig.runner.start(project: a)

        rig.runner.cancel(project: a)
        await until {
            if case .running = rig.runner.state[a.id] { return false }
            return rig.runner.state[a.id] != nil
        }

        #expect(rig.runner.state[a.id] == .stopped(stagesComplete: ["transcribe"]),
                "the app's own Stop left \(String(describing: rig.runner.state[a.id])), not Stopped")
    }

    /// The study queued behind the stopped one still starts.
    @Test func theQueueMovesOnAfterAStopThatReadsStopped() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A"), b = rig.project("B")
        rig.onSignal = { launch, sig in
            guard sig == SIGINT, launch.project.id == a.id else { return }
            Self.writeCancelledRun(at: launch.project.path)
            launch.exit(.exited(code: 130))
        }
        rig.runner.start(project: a)
        rig.runner.start(project: b)

        rig.runner.cancel(project: a)
        await until { rig.launches.count == 2 }

        #expect(rig.launches.last?.project.id == b.id)
        #expect(rig.runner.state[a.id] == .stopped(stagesComplete: ["transcribe"]))
    }
}
