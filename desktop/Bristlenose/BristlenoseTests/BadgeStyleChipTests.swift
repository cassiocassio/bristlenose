#if DEBUG
import AppKit
import Testing
@testable import Bristlenose

/// The CSS → AppKit weight mapping in Picker Lab's badge painter, the first
/// Swift code to paint a `SearchBadgeStyle`. A straight line through 400 and
/// 500 is right there and wrong everywhere else (600 would land past bold), so
/// it follows Apple's named weights.
@Suite("BadgeStyleChip weight")
struct BadgeStyleChipTests {
    private func w(_ css: Double) -> Double { BadgeStyleChip.appKitWeight(css: css) }

    @Test func namedWeightsLandExactly() {
        #expect(w(400) == Double(NSFont.Weight.regular.rawValue))
        #expect(w(500) == Double(NSFont.Weight.medium.rawValue))
        #expect(w(600) == Double(NSFont.Weight.semibold.rawValue))
        #expect(w(700) == Double(NSFont.Weight.bold.rawValue))
    }

    @Test func theBadgeNameWeightSitsJustUnderMedium() {
        // --bn-weight-emphasis is 490.
        #expect(w(490) > Double(NSFont.Weight.regular.rawValue))
        #expect(w(490) < Double(NSFont.Weight.medium.rawValue))
    }

    @Test func outOfRangeIsClamped() {
        #expect(w(50) == Double(NSFont.Weight.ultraLight.rawValue))
        #expect(w(1000) == Double(NSFont.Weight.black.rawValue))
    }
}
#endif
