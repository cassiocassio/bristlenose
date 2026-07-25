import Testing
@testable import Bristlenose

// WelcomeBaton is @MainActor; nextHolder is a static on it → suite-level @MainActor.
@Suite @MainActor
struct WelcomeBatonTests {

    @Test func nobodyWants_returnsNil() {
        #expect(WelcomeBaton.nextHolder(after: nil, wants: [:]) == nil)
        #expect(WelcomeBaton.nextHolder(after: .science, wants: [.tip: false, .ai: false]) == nil)
    }

    @Test func fromNil_picksFirstWantingInSpiralOrder() {
        #expect(WelcomeBaton.nextHolder(after: nil, wants: [.science: true]) == .science)
        // study (0) precedes ai (3) in spiral order → study wins from the start
        #expect(WelcomeBaton.nextHolder(after: nil, wants: [.ai: true, .studyTools: true]) == .studyTools)
    }

    @Test func advancesToNextWanting() {
        let wants: [WelcomeSlot: Bool] = [.studyTools: true, .science: true, .ai: true]
        #expect(WelcomeBaton.nextHolder(after: .studyTools, wants: wants) == .science)
        #expect(WelcomeBaton.nextHolder(after: .science, wants: wants) == .ai)
    }

    @Test func wrapsAround() {
        let wants: [WelcomeSlot: Bool] = [.studyTools: true, .science: true]
        #expect(WelcomeBaton.nextHolder(after: .science, wants: wants) == .studyTools)
        #expect(WelcomeBaton.nextHolder(after: .delight, wants: wants) == .studyTools)
    }

    @Test func skipsNonWanting() {
        // science doesn't want it → after study, skip to ai
        let wants: [WelcomeSlot: Bool] = [.studyTools: true, .ai: true]
        #expect(WelcomeBaton.nextHolder(after: .studyTools, wants: wants) == .ai)
    }

    @Test func soleWanter_returnsItself() {
        #expect(WelcomeBaton.nextHolder(after: .science, wants: [.science: true]) == .science)
    }
}
