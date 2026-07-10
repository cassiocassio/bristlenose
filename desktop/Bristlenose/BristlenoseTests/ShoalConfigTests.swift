import CoreGraphics
import Testing

@testable import Bristlenose

/// Pins the area-derived boid count (`ShoalConfig.targetCount`): the flock scales
/// with the scene's render area, clamped to a floor/ceiling, and thickens across
/// the phase ramp. Screen size sets the ambition; the clamps and ramp keep it sane.
@Suite struct ShoalConfigTests {

    @Test func clampsToFloorForTinyArea() {
        // A near-zero render area still flocks — the late (full) phase floors at minCount.
        #expect(ShoalConfig.targetCount(forArea: 1_000, phase: .late) == ShoalConfig.minCount)
    }

    @Test func clampsToCeilingForHugeArea() {
        // A wall-sized display can't run away with the count.
        #expect(ShoalConfig.targetCount(forArea: 100_000_000, phase: .late) == ShoalConfig.maxCount)
    }

    @Test func scalesWithAreaAtFullPhase() {
        // ~one boid per areaPerBoid points², at the late (full) phase.
        let area = ShoalConfig.areaPerBoid * 100   // between floor(24) and ceiling(200)
        #expect(ShoalConfig.targetCount(forArea: area, phase: .late) == 100)
    }

    @Test func phaseRampIsMonotonic() {
        // The flock thickens early → middle → late for a fixed area.
        let area = ShoalConfig.areaPerBoid * 100
        let early = ShoalConfig.targetCount(forArea: area, phase: .early)
        let middle = ShoalConfig.targetCount(forArea: area, phase: .middle)
        let late = ShoalConfig.targetCount(forArea: area, phase: .late)
        #expect(early < middle)
        #expect(middle < late)
    }

    @Test func biggerAreaYieldsMoreBoids() {
        // The whole point: a 24" external pane out-flocks a 16" pane at the same phase.
        let small = ShoalConfig.targetCount(forArea: ShoalConfig.areaPerBoid * 60, phase: .late)
        let large = ShoalConfig.targetCount(forArea: ShoalConfig.areaPerBoid * 120, phase: .late)
        #expect(large > small)
    }
}
