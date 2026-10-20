import AppKit
import Foundation
import Testing
@testable import Bristlenose

/// Quitting the app stops every run it knows about (R19, 20 Oct 2026).
///
/// A run's stdout and stderr are a pipe to the app. With no Quit handler the
/// run outlived the app until its next print, the write failed with EPIPE, and
/// Python recorded `run_failed` — so a relaunch inside that window attached,
/// read "Resuming…", and then showed "CLI exited with code 1". Measured against
/// the real CLI: the pipe closed after ingest gave `run_failed` 0.1 s later;
/// SIGINT and then the pipe closing gave `run_cancelled` at every point tried,
/// mid-transcription included. `run_cancelled` reads "Stopped", resumable.
@MainActor
struct PipelineRunnerQuitTests {

    private final class SignalLog {
        var sent: [(pid: pid_t, sig: Int32)] = []
    }

    private func runner(center: NotificationCenter, log: SignalLog) -> PipelineRunner {
        PipelineRunner(notificationCenter: center, sendSignal: { pid, sig in
            // Signal 0 is a liveness probe (an attached run's poll), not a
            // signal Quit sent.
            if sig != 0 { log.sent.append((pid, sig)) }
            return 0
        })
    }

    /// The relaunch R19 describes, then a second Quit: the attached orphan —
    /// this test process, recorded the way a spawn records it — gets SIGINT.
    @Test func quitInterruptsAnAttachedOrphan() async throws {
        let center = NotificationCenter()
        let log = SignalLog()
        let r = runner(center: center, log: log)
        let p = Project(id: UUID(), name: "Quit", path: "/p/quit-\(UUID().uuidString)")
        let url = PipelineRunner.pidFileURL(for: p)
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        let start = try #require(EventLogReader.procStartTime(pid: getpid()))
        try Data("\(getpid())\n\(start)\n".utf8).write(to: url, options: .atomic)
        defer { try? FileManager.default.removeItem(at: url) }

        r.scan(project: p)
        for _ in 0..<200 where r.state[p.id] != .running {
            try await Task.sleep(for: .milliseconds(10))
        }
        try #require(r.state[p.id] == .running, "the orphan was not attached")

        center.post(name: NSApplication.willTerminateNotification, object: nil)

        #expect(log.sent.count == 1, "Quit sent \(log.sent.count) signals, wanted one")
        #expect(log.sent.first?.pid == getpid())
        #expect(log.sent.first?.sig == SIGINT)
    }

    /// The run this process spawned is in the set as well as the orphans.
    @Test func quitTargetsIncludeTheOwnedRun() {
        #expect(PipelineRunner.quitSignalTargets(owned: 42, orphans: [7, 9]) == [7, 9, 42])
        #expect(PipelineRunner.quitSignalTargets(owned: 42, orphans: []) == [42])
        #expect(PipelineRunner.quitSignalTargets(owned: nil, orphans: []) == [])
        #expect(PipelineRunner.quitSignalTargets(owned: 7, orphans: [7]) == [7], "one signal per process")
    }

    /// Nothing running: Quit signals nothing.
    @Test func quitWithNoRunSignalsNothing() {
        let center = NotificationCenter()
        let log = SignalLog()
        let r = runner(center: center, log: log)
        center.post(name: NSApplication.willTerminateNotification, object: nil)
        #expect(log.sent.isEmpty)
        _ = r
    }
}
