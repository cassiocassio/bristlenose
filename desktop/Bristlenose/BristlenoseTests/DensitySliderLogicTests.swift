import Foundation
import Testing
@testable import Bristlenose

/// The decisions behind the Display popover's Density slider: where it snaps,
/// when it sends, and when the report's value is the echo of its own.
struct DensitySliderLogicTests {
    @Test func aMouseDragSettlesOnNormalNearTheMiddle() {
        #expect(DensitySliderLogic.snapped(0.52, mouseEditing: true) == 0.5)
        #expect(DensitySliderLogic.snapped(0.47, mouseEditing: true) == 0.5)
    }

    @Test func aMouseDragFarFromNormalIsLeftAlone() {
        #expect(DensitySliderLogic.snapped(0.6, mouseEditing: true) == 0.6)
        #expect(DensitySliderLogic.snapped(0.0, mouseEditing: true) == 0.0)
    }

    @Test func aKeyboardStepNeverSnapsSoTheArrowsCanLeaveNormal() {
        // One notch either side of Normal must stay where the key put it.
        #expect(DensitySliderLogic.snapped(0.51, mouseEditing: false) == 0.51)
        #expect(DensitySliderLogic.snapped(0.49, mouseEditing: false) == 0.49)
    }

    @Test func aSendGoesAtOnceOnlyAfterTheIntervalHasPassed() {
        let t = Date()
        #expect(!DensitySliderLogic.shouldSendNow(now: t.addingTimeInterval(0.03), lastSent: t))
        #expect(DensitySliderLogic.shouldSendNow(now: t.addingTimeInterval(0.1), lastSent: t))
        #expect(DensitySliderLogic.shouldSendNow(now: t, lastSent: .distantPast))
    }

    @Test func theReportStoresTwoDecimalsAndTheSliderComparesAtThatPrecision() {
        #expect(DensitySliderLogic.rounded(0.3333333) == 0.33)
        #expect(DensitySliderLogic.echoMatches(shown: 0.3333333, report: 0.33))
        #expect(!DensitySliderLogic.echoMatches(shown: 0.3333333, report: 0.4))
    }

    @Test func aHalfWayRoundingStillCountsAsTheEcho() {
        // 0.125 is stored as 0.13: a difference of exactly 0.005, which must match.
        #expect(DensitySliderLogic.echoMatches(shown: 0.125, report: 0.13))
    }

    @Test func theEndsAndTheMiddleAreExact() {
        for v in [0.0, 0.5, 1.0] {
            #expect(DensitySliderLogic.echoMatches(shown: v, report: v))
        }
    }

    @Test func theSettleDelayOutlastsTheTrailingSend() {
        // The give-up timer must not fire before a held-back send could go out.
        #expect(DensitySliderLogic.settleDelay > DensitySliderLogic.trailingDelay * 3)
    }
}
