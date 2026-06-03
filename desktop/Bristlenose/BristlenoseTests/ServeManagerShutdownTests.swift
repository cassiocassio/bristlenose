import Testing
import Foundation
@testable import Bristlenose

/// Tests for ServeManager.shutdown(timeout:) — Mini-spec 4 step 3 invariant.
///
/// switchProject correctness rests on shutdown's post-condition:
/// after `await shutdown(...)` returns, `state == .idle`, `process == nil`,
/// `authToken == nil`, `serverVersion == nil`, `currentProjectPath == nil`.
///
/// Until ServeManager grows a `Process` protocol seam for full mock-driven
/// teardown coverage, this suite asserts the cheap-but-load-bearing path:
/// shutdown on an already-idle manager leaves the invariants intact.
@Suite("ServeManager.shutdown invariants")
@MainActor
struct ServeManagerShutdownTests {

    @Test func shutdown_from_idle_is_noop_with_intact_invariants() async {
        let manager = ServeManager()
        // Sanity precondition — fresh manager starts idle (or .failed if mode
        // resolution failed). We accept either; the post-condition is what
        // matters.
        await manager.shutdown(timeout: .seconds(1))

        // After shutdown from idle, all teardown invariants must hold.
        if case .running = manager.state {
            Issue.record("shutdown from idle left state == .running")
        }
        #expect(manager.serverVersion == nil)
        #expect(manager.authToken == nil)
    }

    @Test func shutdown_idempotent_when_called_twice() async {
        let manager = ServeManager()
        await manager.shutdown(timeout: .seconds(1))
        await manager.shutdown(timeout: .seconds(1))
        // Second call must not crash; invariants still hold.
        #expect(manager.serverVersion == nil)
        #expect(manager.authToken == nil)
    }
}
