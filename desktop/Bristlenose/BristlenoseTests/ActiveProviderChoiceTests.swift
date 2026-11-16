import Testing
@testable import Bristlenose

@Suite("Active provider choice")
struct ActiveProviderChoiceTests {
    @Test func unsetIsNotAProvider() {
        #expect(LLMProvider(rawValue: ActiveProviderChoice.unset) == nil)
    }

    @Test func firstValidatedProviderIsAdoptedWhenNothingChosen() {
        #expect(ActiveProviderChoice.adopt(
            current: ActiveProviderChoice.unset, validated: .claude, status: .online) == .claude)
        #expect(ActiveProviderChoice.adopt(
            current: ActiveProviderChoice.unset, validated: .gemini, status: .outOfCredit) == .gemini)
    }

    @Test func nothingIsAdoptedWithoutAUsableStatus() {
        for status in [ProviderStatus.notSetUp, .invalid, .checking] {
            #expect(ActiveProviderChoice.adopt(
                current: ActiveProviderChoice.unset, validated: .claude, status: status) == nil)
        }
    }

    @Test func aDeliberateChoiceIsNeverReplaced() {
        #expect(ActiveProviderChoice.adopt(
            current: LLMProvider.ollama.rawValue, validated: .claude, status: .online) == nil)
    }
}
