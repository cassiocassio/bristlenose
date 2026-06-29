import Foundation
import Testing

@testable import Bristlenose

/// Pins the begin-once / end-once edge machine of the run sleep assertion: the
/// `ProcessInfo` activity must be acquired exactly once when a run starts and
/// released exactly once when the last finishes, with no double-begin on churn
/// and no leak. The real `ProcessInfo` call is injected so the state machine is
/// exercised without mutating global power state.
@MainActor @Suite struct RunSleepAssertionTests {

    private final class Counter {
        var begins = 0
        var ends = 0
    }

    private func make() -> (RunSleepAssertion, Counter) {
        let c = Counter()
        let token = NSObject()
        let a = RunSleepAssertion(
            begin: { _, _ in c.begins += 1; return token },
            end: { _ in c.ends += 1 }
        )
        return (a, c)
    }

    @Test func beginsOnFirstHeld() {
        let (a, c) = make()
        a.setHeld(true)
        #expect(c.begins == 1)
        #expect(c.ends == 0)
        #expect(a.isHeld)
    }

    @Test func idempotentWhenAlreadyHeld() {
        // Coarse state can land on `.running` more than once (re-scan, re-entry);
        // the assertion must not stack a second activity.
        let (a, c) = make()
        a.setHeld(true)
        a.setHeld(true)
        a.setHeld(true)
        #expect(c.begins == 1)
        #expect(a.isHeld)
    }

    @Test func endsOnRelease() {
        let (a, c) = make()
        a.setHeld(true)
        a.setHeld(false)
        #expect(c.ends == 1)
        #expect(!a.isHeld)
    }

    @Test func releaseWhenNeverHeldIsNoOp() {
        let (a, c) = make()
        a.setHeld(false)
        #expect(c.begins == 0)
        #expect(c.ends == 0)
        #expect(!a.isHeld)
    }

    @Test func reacquireAfterRelease() {
        // A second run after the first finishes begins a fresh activity.
        let (a, c) = make()
        a.setHeld(true)
        a.setHeld(false)
        a.setHeld(true)
        #expect(c.begins == 2)
        #expect(c.ends == 1)
        #expect(a.isHeld)
    }
}

/// The state→assertion mapping: only `.running` keeps the machine awake.
@Suite struct PipelineStateKeepsAwakeTests {

    @Test func runningKeepsAwake() {
        #expect(PipelineState.running.keepsMachineAwake)
    }

    @Test func nonRunningStatesDoNot() {
        #expect(!PipelineState.idle.keepsMachineAwake)
        #expect(!PipelineState.scanning.keepsMachineAwake)
        #expect(!PipelineState.queued(position: 1).keepsMachineAwake)
        #expect(!PipelineState.ready(Date()).keepsMachineAwake)
        #expect(!PipelineState.stopped(stagesComplete: []).keepsMachineAwake)
        #expect(!PipelineState.partial(kind: "transcribe-only", stagesComplete: []).keepsMachineAwake)
        #expect(!PipelineState.unreachable(reason: "x").keepsMachineAwake)
        #expect(!PipelineState.failed("x", category: .unknown).keepsMachineAwake)
    }
}
