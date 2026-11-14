import Foundation
import Testing
@testable import Bristlenose

/// Diagnostics ▸ Azure Settings: what a fixture carries and how long a request
/// for one waits for a pane. The heights are in `SettingsRefitTests`.
@Suite @MainActor struct AzureSettingsFixtureTests {

    @Test func everyFixtureCarriesItsSentenceVerbatim() {
        // A passthrough, not a key: nothing here is a locale key, so the bare
        // `I18n` (which returns raw keys) must still give the sentence back.
        let i18n = I18n()
        for fixture in AzureSettingsFixture.allCases {
            #expect(fixture.failure.resolved(i18n) == fixture.sentence)
            #expect(!fixture.sentence.isEmpty)
        }
    }

    @Test func noSentenceSendsTheResearcherToSomeoneElse() {
        // Owner, 13 Nov 2026: the sentence says what is wrong and what to check,
        // and stops. Researchers know to ask whoever gave them the values.
        for fixture in AzureSettingsFixture.allCases {
            #expect(!fixture.sentence.localizedCaseInsensitiveContains("whoever"),
                    "\(fixture.rawValue): \(fixture.sentence)")
        }
    }

    @Test func theProviderIsNamedAzureNotAzureOpenAI() {
        // D10 (owner, 13 Nov 2026): "Azure OpenAI" reads as OpenAI-only.
        for fixture in AzureSettingsFixture.allCases {
            #expect(!fixture.sentence.contains("Azure OpenAI"), "\(fixture.sentence)")
        }
    }

    @Test func aStagedFixtureIsTakenOnce() {
        _ = AzureSettingsFixture.takePending()   // drop whatever an earlier test left
        AzureSettingsFixture.stage(.hostNotFound)
        #expect(AzureSettingsFixture.takePending() == .hostNotFound)
        #expect(AzureSettingsFixture.takePending() == nil)
    }

    @Test func aStagedFixtureExpires() {
        // A request nobody collected must not surface on a later visit to Settings.
        let asked = Date()
        AzureSettingsFixture.stage(.keyNotAccepted, at: asked)
        let late = asked.addingTimeInterval(AzureSettingsFixture.pendingLifetime + 1)
        #expect(AzureSettingsFixture.takePending(now: late) == nil)
    }

    @Test func aStagedFixtureWaitsUntilTheLifetimeEnds() {
        let asked = Date()
        AzureSettingsFixture.stage(.noSuchDeployment, at: asked)
        let justInTime = asked.addingTimeInterval(AzureSettingsFixture.pendingLifetime)
        #expect(AzureSettingsFixture.takePending(now: justInTime) == .noSuchDeployment)
    }
}
