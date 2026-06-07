import Testing
@testable import Bristlenose

/// `PipelineRunner.humanSummary(for:provider:)` — the degraded-path failure
/// copy. Pins the subject/object grammar split (so "Couldn't reach Claude" and
/// "Claude rejected the request" both read right) and the nil-provider
/// fallback, which a careless single-noun refactor could silently collapse into
/// ungrammatical copy ("Couldn't reach Claude rate limit reached"). usual-
/// suspects Finding D.
@MainActor
@Suite("PipelineRunner.humanSummary")
struct PipelineRunnerCopyTests {

    @Test("Provider name threads into LLM-error copy, in subject and object slots")
    func namesProvider() {
        // Subject position.
        #expect(PipelineRunner.humanSummary(for: .apiRequest, provider: .claude)
            == "Claude rejected the request.")
        #expect(PipelineRunner.humanSummary(for: .quota, provider: .chatGPT)
            == "ChatGPT rate limit reached.")
        // Object position — the half a naive single-noun refactor would break.
        #expect(PipelineRunner.humanSummary(for: .network, provider: .gemini)
            == "Couldn't reach Gemini.")
    }

    @Test("Nil provider falls back to grammatical generic phrasing")
    func nilProviderGrammar() {
        #expect(PipelineRunner.humanSummary(for: .apiRequest, provider: nil)
            == "LLM provider rejected the request.")
        #expect(PipelineRunner.humanSummary(for: .network, provider: nil)
            == "Couldn't reach the LLM provider.")
    }

    @Test("Non-LLM categories ignore the provider")
    func nonLLMIgnoresProvider() {
        #expect(PipelineRunner.humanSummary(for: .disk, provider: .claude)
            == "Not enough disk space to finish.")
    }
}
