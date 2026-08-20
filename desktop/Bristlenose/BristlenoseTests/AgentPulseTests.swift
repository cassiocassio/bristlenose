import Foundation
import Testing
@testable import Bristlenose

/// The antenna's activity animation, at its two decision points: what counts
/// as a call, and when the glyph radiates.
///
/// Both are places where the honest answer and the convenient one differ. The
/// counter resets when a sidecar restarts, so the convenient reading (any
/// change = activity) would animate on every serve start and claim an agent
/// asked something when nothing did. And the envelope is per-BURST, because
/// measured traffic fires several tool calls per question.
struct AgentPulseTests {

    // MARK: - What counts as a call

    @MainActor @Test func anIncreaseIsActivity() {
        let instance = ServeInstance()
        #expect(instance.noteAgentCallCount(1) == true)
        #expect(instance.lastAgentCallAt != nil)
    }

    @MainActor @Test func anUnchangedCountIsNotActivity() {
        let instance = ServeInstance()
        _ = instance.noteAgentCallCount(4)
        let first = instance.lastAgentCallAt
        #expect(instance.noteAgentCallCount(4) == false)
        #expect(instance.lastAgentCallAt == first)   // not refreshed
    }

    /// The one that matters: a restarted sidecar's counter goes back to 0.
    /// That is a NEW BASELINE, not a burst of activity — animating there would
    /// tell the researcher an agent read their study during app launch.
    @MainActor @Test func aDecreaseAdoptsTheNewBaselineSilently() {
        let instance = ServeInstance()
        _ = instance.noteAgentCallCount(9)
        instance.lastAgentCallAt = nil              // clear the earlier stamp
        #expect(instance.noteAgentCallCount(0) == false)
        #expect(instance.lastAgentCallAt == nil)
        #expect(instance.agentCallCount == 0)       // baseline adopted, not ignored
        // ...and the next real call off that baseline still registers.
        #expect(instance.noteAgentCallCount(1) == true)
    }

    // MARK: - When the antenna radiates

    private typealias Wave = SidebarOutlineController.AgentWave

    @MainActor @Test func radiatesThroughTheHoldAndItsDecayTail() {
        #expect(Wave.radiating(at: 0))
        #expect(Wave.radiating(at: Wave.hold - 0.01))
        #expect(Wave.radiating(at: Wave.hold + 0.1))            // tail
        #expect(!Wave.radiating(at: Wave.hold + Wave.tail + 0.1))  // the gap
    }

    @MainActor @Test func signsOffWithExactlyTwoTaps() {
        let firstTap = Wave.hold + Wave.tail + Wave.gap
        #expect(Wave.radiating(at: firstTap + 0.1))
        #expect(!Wave.radiating(at: firstTap + Wave.tap + 0.1))          // between
        let secondTap = firstTap + Wave.tap + Wave.tapGap
        #expect(Wave.radiating(at: secondTap + 0.1))
        #expect(!Wave.radiating(at: secondTap + Wave.tap + 0.1))         // done
    }

    /// Nothing radiates past the envelope — the animation is bounded, so an
    /// idle sidebar is a still sidebar. A looping activity light is the thing
    /// that makes an indicator unignorable.
    @MainActor @Test func theEnvelopeTerminates() {
        #expect(!Wave.radiating(at: Wave.duration + 0.5))
        #expect(!Wave.radiating(at: 60))
    }

    /// Each tap restarts the flipbook at the mast rather than resuming
    /// mid-sweep, so a tap reads as a discrete pulse and not as a fragment.
    @MainActor @Test func eachSegmentRestartsTheSweep() {
        let firstTap = Wave.hold + Wave.tail + Wave.gap
        #expect(Wave.segmentElapsed(at: firstTap + 0.05) < Wave.framePeriod)
        let secondTap = firstTap + Wave.tap + Wave.tapGap
        #expect(Wave.segmentElapsed(at: secondTap + 0.05) < Wave.framePeriod)
    }
}
