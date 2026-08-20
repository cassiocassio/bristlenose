import Testing
@testable import Bristlenose

/// Pins the two welcome cell-tint tables — v1 (shipping) and the flagged
/// Whisper-reversed candidate (the recorded pick from the gradient playground;
/// `docs/design-welcome-screen.md` §2, open decision #3). The numbers ARE the
/// decision: a drive-by edit should fail here, not ship silently.
struct WelcomeCellTintTests {
    private let spiralOrder: [WelcomeCellTint] = [.studyTools, .science, .tip, .ai, .delight]

    @Test func v1RampIsTheShippedSet() {
        #expect(spiralOrder.map { $0.value(candidate: false) } == [0.03, 0.07, 0.12, 0.18, 0.26])
    }

    @Test func candidateRampIsWhisperReversed() {
        #expect(spiralOrder.map { $0.value(candidate: true) } == [0.11, 0.08, 0.06, 0.04, 0.02])
    }

    /// Colour on the stage, quiet eye — the candidate descends down the spiral,
    /// the inverse of v1's ascent. Shape check, independent of exact values.
    @Test func candidateDescendsWhereV1Ascends() {
        let v1 = spiralOrder.map(\.v1)
        let candidate = spiralOrder.map(\.candidate)
        #expect(v1 == v1.sorted())
        #expect(candidate == candidate.sorted(by: >))
    }
}
