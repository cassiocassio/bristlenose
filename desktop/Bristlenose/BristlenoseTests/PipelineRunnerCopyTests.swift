import Testing
@testable import Bristlenose

/// `FailureMessage.failure(for:provider:)` — the degraded-path failure
/// copy, as a key the view resolves.
///
/// **What this suite used to pin, and why it doesn't any more.** It asserted the
/// English subject/object grammar split — "Couldn't reach Claude" against
/// "Claude rate limit reached" — because one generic noun could not sit in both
/// slots (usual-suspects Finding D). That problem was English's, and it was
/// solved the way English solves it. Twenty other languages inflect the noun
/// itself, so no arrangement of two nouns would have worked there; each locale
/// now carries a whole sentence per case, named and generic, and the grammar is
/// the translator's. What survives here is the *routing* — which key, which
/// variables — plus the English the log still gets.
@MainActor
@Suite("FailureMessage.failure")
struct PipelineRunnerCopyTests {

    @Test("A known provider takes the naming key and rides in as a variable")
    func namesProvider() {
        let m = FailureMessage.failure(for: .apiRequest, provider: .claude)
        #expect(m.key == "desktop.pipeline.failure.apiRequest")
        #expect(m.vars == ["provider": "Claude"])
        #expect(m.english == "Claude rejected the request.")
    }

    @Test("No provider takes the Generic sibling and carries no variables")
    func nilProviderTakesTheGenericSibling() {
        let m = FailureMessage.failure(for: .apiRequest, provider: nil)
        #expect(m.key == "desktop.pipeline.failure.apiRequestGeneric")
        #expect(m.vars.isEmpty)
        #expect(m.english == "The AI provider rejected the request.")
    }

    @Test("Non-LLM categories ignore the provider and have no Generic sibling")
    func nonLLMIgnoresProvider() {
        for provider in [LLMProvider.claude, nil] {
            let m = FailureMessage.failure(for: .disk, provider: provider)
            #expect(m.key == "desktop.pipeline.failure.disk")
            #expect(m.vars.isEmpty)
            #expect(m.english == "Not enough disk space.")
        }
    }

    @Test("Every category resolves to a sentence, not to its own leaf")
    func everyCategoryHasEnglish() {
        // The fallback in `englishSentence` returns the leaf when the table has
        // no entry — which would render a bare "outputTruncated" on screen the
        // one time the app is already in trouble. Catch the gap here instead.
        let categories: [PipelineFailureCategory] = [
            .auth, .outOfCredit, .network, .quota, .disk, .whisper, .userSignal,
            .apiRequest, .apiServer, .missingDep, .missingInput, .missingBinary,
            .outputExists, .outputTruncated, .unusableInput, .unknown,
        ]
        for category in categories {
            for provider in [LLMProvider.claude, nil] {
                let m = FailureMessage.failure(for: category, provider: provider)
                #expect(m.english != category.localeLeaf,
                        "\(category.rawValue) has no English sentence")
                #expect(!m.english.contains("{{"),
                        "\(category.rawValue) left a placeholder unsubstituted: \(m.english)")
            }
        }
    }

    @Test("A passthrough resolves to its own words, key or no key")
    func passthroughIsNotLocalised() {
        // Python's `cause.message` is more specific than any category sentence
        // and arrives already written — the loss this codebase paid back once
        // already, in the cloud-import download verdicts.
        let m = FailureMessage.passthrough("Anthropic says: model gpt-4o not found")
        #expect(m.key == nil)
        #expect(m.resolved(I18n()) == "Anthropic says: model gpt-4o not found")
    }

    @Test("A key that cannot resolve falls back to English, never to the key")
    func missingKeyFallsBackToEnglish() {
        // A bare `I18n()` has no locales loaded, so `t` returns the key — which
        // is exactly the "key missing" case, and the one that must not reach a
        // researcher's screen.
        let m = FailureMessage(key: "desktop.pipeline.failure.disk",
                               english: "Not enough disk space.")
        #expect(m.resolved(I18n()) == "Not enough disk space.")
    }
}
