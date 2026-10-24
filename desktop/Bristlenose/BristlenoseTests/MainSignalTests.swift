import Foundation
import Testing
@testable import Bristlenose

/// `MainSignal` is what the Miro sheet tests wait on in place of a 10 s clock. Its one promise
/// beyond firing is that a cancel ends the wait, so a test's `.timeLimit` can end the test.
@MainActor
@Suite("MainSignal")
struct MainSignalTests {

    @Test("a signal fired before the wait returns at once")
    func firedBeforeTheWait() async {
        let s = MainSignal()
        s.fire()
        await s.wait()
        #expect(s.fired)
    }

    @Test("a signal fired during the wait wakes it", .timeLimit(.minutes(1)))
    func firedDuringTheWait() async {
        let s = MainSignal()
        let waiting = Task { await s.wait() }
        await Task.yield()
        s.fire()
        await waiting.value
        #expect(s.fired)
    }

    @Test("cancelling the waiting task ends the wait without the signal", .timeLimit(.minutes(1)))
    func cancelEndsTheWait() async throws {
        let s = MainSignal()
        var returned = false
        let waiting = Task { await s.wait(); returned = true }
        await Task.yield()
        waiting.cancel()
        // Bounded so a wait that ignores the cancel fails here rather than hanging the run:
        // `.timeLimit` cancels a test and then waits for it, which is the case being tested.
        let deadline = Date().addingTimeInterval(30)
        while !returned, Date() < deadline { try await Task.sleep(for: .milliseconds(10)) }
        #expect(returned, "a cancelled wait never returned")
        #expect(!s.fired)
    }
}
