import Combine
import Foundation
import Testing
@testable import Bristlenose

/// The two R35 follow-ups in `ServeManager`'s restart path.
///
/// `ServeManager` has no `Process` seam (see `ServeManagerShutdownTests`), so
/// these hand the manager a real child process — `/bin/sh` — in place of a
/// sidecar, and wire its exit to `handleTermination` the way `start()` does.
/// The manager is resolved to an external server so a `start()` lands on
/// `.running(port:)` without spawning anything.
@Suite("ServeManager restart", .serialized)
@MainActor
struct ServeManagerRestartTests {

    private static let port = 9_998

    private func manager() -> ServeManager {
        ServeManager(resolvedMode: .success(.external(port: Self.port)))
    }

    /// A child standing in for a sidecar, adopted as the manager's fronted
    /// process with its exit wired to `handleTermination`.
    private func adopt(_ script: String, into m: ServeManager) throws -> Process {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/sh")
        p.arguments = ["-c", script]
        p.terminationHandler = { [weak m] proc in
            let id = ObjectIdentifier(proc)
            let status = proc.terminationStatus
            Task { @MainActor in m?.handleTermination(processID: id, status: status) }
        }
        try p.run()
        m.instance.process = p
        return p
    }

    private func wait(_ ms: Int) async {
        try? await Task.sleep(for: .milliseconds(ms))
    }

    /// Wait, with a deadline, until `condition` holds. Under a full suite the
    /// main actor is shared, so "after N ms" is not "after the Task ran".
    private func waitUntil(_ condition: () -> Bool) async {
        for _ in 0..<300 where !condition() {
            try? await Task.sleep(for: .milliseconds(10))
        }
    }

    /// Restarting a booting serve showed "stopped before it finished
    /// starting": `shutdown` interrupted the process while `process` still
    /// named it, so its exit read as the serve dying.
    @Test func aRestartDuringBootNeverReportsTheServeAsStopped() async throws {
        let m = manager()
        var seen: [ServeState] = []
        let watch = m.instance.$state.sink { seen.append($0) }
        defer { watch.cancel() }

        let p = try adopt("exec sleep 30", into: m)
        defer { if p.isRunning { kill(p.processIdentifier, SIGKILL) } }
        m.instance.state = .starting
        m.instance.currentProjectPath = "/p/a"
        #expect(p.isRunning, "precondition: there is a booting process to tear down")

        await m.shutdown(timeout: .seconds(2))
        await wait(300)  // let the exit's handler run

        #expect(!p.isRunning)
        let failures = seen.filter { if case .failed = $0 { true } else { false } }
        #expect(failures.isEmpty, "our own teardown was reported as a failure: \(failures)")
    }

    /// A `start()` that lands before the restart's Task runs owns the serve;
    /// the restart must not tear it down and start the old path.
    @Test func aRestartSupersededBeforeItRunsLeavesTheNewServe() async {
        let m = manager()
        m.start(projectPath: "/p/a")
        #expect(m.state == .running(port: Self.port))

        m.restartIfRunning()
        m.start(projectPath: "/p/b")  // same tick: before the Task runs
        await wait(300)

        #expect(m.currentProjectPath == "/p/b", "the superseded restart restarted the old path")
        #expect(m.state == .running(port: Self.port))
    }

    /// …and one that lands while the restart awaits teardown. The child
    /// ignores what `Process.interrupt()` sends, so `shutdown` sits in its wait
    /// for the full timeout before SIGKILL. It must be given time to install
    /// its trap: the restart's Task runs within milliseconds, and a SIGINT that
    /// lands first kills the child, closes the window, and lets this test pass
    /// vacuously. The precondition below is what catches that.
    @Test func aRestartSupersededMidTeardownLeavesTheNewServe() async throws {
        let m = manager()
        let p = try adopt("trap '' INT TERM HUP; while :; do sleep 0.1; done", into: m)
        defer { if p.isRunning { kill(p.processIdentifier, SIGKILL) } }
        await wait(200)  // until the shell has installed its trap
        m.instance.state = .running(port: Self.port)
        m.instance.currentProjectPath = "/p/a"

        m.restartIfRunning()
        // Only `shutdown` detaches the process, so this is "the restart is
        // inside shutdown's wait", not merely "time has passed".
        await waitUntil { m.instance.process == nil }
        #expect(m.instance.process == nil, "precondition: the restart has begun its teardown")
        #expect(p.isRunning, "precondition: the teardown is still waiting on the child")
        m.start(projectPath: "/p/b")
        await wait(2_600)  // past the 2 s timeout and the SIGKILL grace

        #expect(!p.isRunning)
        #expect(m.currentProjectPath == "/p/b", "the superseded restart restarted the old path")
        #expect(m.state == .running(port: Self.port))
    }

    /// A `stop()` while the restart awaits teardown — the window left the
    /// study, or `ServeFleet.discard` dropped the manager — must stay stopped.
    /// It used to bump nothing, so the restart came back and spawned a serve
    /// nothing showed or tracked.
    @Test func aRestartStoppedMidTeardownStaysStopped() async throws {
        let m = manager()
        let p = try adopt("trap '' INT TERM HUP; while :; do sleep 0.1; done", into: m)
        defer { if p.isRunning { kill(p.processIdentifier, SIGKILL) } }
        await wait(200)  // until the shell has installed its trap
        m.instance.state = .running(port: Self.port)
        m.instance.currentProjectPath = "/p/a"

        m.restartIfRunning()
        await waitUntil { m.instance.process == nil }
        #expect(m.instance.process == nil, "precondition: the restart has begun its teardown")
        m.stop()
        await waitUntil { !p.isRunning }  // the restart's 2 s timeout, then SIGKILL
        await wait(300)  // and whatever the restart does after its teardown

        #expect(!p.isRunning)
        #expect(m.state == .idle, "a stopped serve was restarted")
    }

    // MARK: The agent-scope PUT (100days §2, "false agent-scope PUT failed")

    /// A serve being torn down still reads `.running` until `shutdown`
    /// finishes, so the fleet's handshake sync PUT to a dying port and logged
    /// a false ERROR on every restart. The detach that stops the failure flash
    /// is the mark: no PUT goes out after it.
    @Test func noAgentScopePutGoesToAServeBeingTornDown() async throws {
        let m = ServeManager(resolvedMode: .success(.devSidecar(path: URL(fileURLWithPath: "/bin/sh"))))
        let p = try adopt("trap '' INT TERM HUP; while :; do sleep 0.1; done", into: m)
        defer { if p.isRunning { kill(p.processIdentifier, SIGKILL) } }
        await wait(200)  // until the shell has installed its trap
        m.instance.state = .running(port: Self.port)
        #expect(m.agentScopeURL != nil, "precondition: a live serve takes the PUT")

        // Everything in `shutdown` before its first await runs as soon as the
        // Task starts, so once the Task has suspended the mark is in place.
        var begun = false
        let teardown = Task {
            begun = true
            await m.shutdown(timeout: .seconds(1))
        }
        await waitUntil { begun }
        await wait(50)  // it is now in the poll loop
        #expect(begun, "precondition: the teardown has begun")
        #expect(p.isRunning, "precondition: the teardown is still waiting on the child")
        #expect(m.state == .running(port: Self.port), "precondition: it still reads as running")
        #expect(m.agentScopeURL == nil, "a serve being torn down still took the agent-scope PUT")
        await teardown.value
    }

    /// An external server has no process of ours and is never going away.
    @Test func anExternalServerTakesTheAgentScopePut() {
        let m = manager()
        m.start(projectPath: "/p/a")
        #expect(m.agentScopeURL != nil)
    }
}
