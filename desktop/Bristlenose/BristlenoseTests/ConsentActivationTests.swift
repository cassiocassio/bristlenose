import Testing
@testable import Bristlenose

/// Tests for the pure consent-activation decision. The impure
/// `cloudStatuses()` snapshot reader (Keychain + verdict cache) is left
/// untested by design — it's a thin presence-and-cache read with no logic of
/// its own. All the branching lives in `resolve`, so that's where the tests go.
@Suite("Consent activation resolution")
struct ConsentActivationTests {

    // MARK: - No-override: a cloud choice with a key is never replaced

    @Test func onlineCloudActive_returnsNil() {
        let result = ConsentActivation.resolve(
            active: "anthropic",
            activeHasKey: true,
            statuses: [.claude: .online])
        #expect(result == nil)
    }

    @Test func onlineCloudActive_ignoresOtherOnlineClouds() {
        // Active is a configured cloud — even if another cloud is also online,
        // don't switch. Deliberate choice wins.
        let result = ConsentActivation.resolve(
            active: "google",
            activeHasKey: true,
            statuses: [.gemini: .online, .claude: .online])
        #expect(result == nil)
    }

    // MARK: - Defect #1: a keyed cloud with no/stale verdict is NOT flipped

    @Test func keyedCloudActive_noVerdict_otherCloudOnline_returnsNil() {
        // The 5 Jun ghost-bug: Gemini is deliberately active and has a stored
        // key, but its `.online` verdict isn't cached (stale cache / post-
        // relaunch). Anthropic IS cached online. The old verdict gate flipped
        // google → anthropic here, producing a cross-provider 404. With a key
        // present, the deliberate choice must survive an absent verdict.
        let result = ConsentActivation.resolve(
            active: "google",
            activeHasKey: true,
            statuses: [.claude: .online])
        #expect(result == nil)
    }

    @Test func keyedCloudActive_invalidVerdict_returnsNil() {
        // Even an explicitly non-online cached verdict doesn't trigger a
        // silent flip while a key is present — re-validation is the run path's
        // job, not the consent sheet's. (The user sees the invalid state in
        // Settings; we don't reroute their data behind their back.)
        let result = ConsentActivation.resolve(
            active: "google",
            activeHasKey: true,
            statuses: [.gemini: .invalid, .claude: .online])
        #expect(result == nil)
    }

    // MARK: - Re-consent path: local active + validated cloud

    @Test func localActive_oneOnlineCloud_returnsThatCloud() {
        let result = ConsentActivation.resolve(
            active: "local",
            activeHasKey: false,
            statuses: [.claude: .online])
        #expect(result == .claude)
    }

    @Test func localActive_onlyGeminiOnline_returnsGemini() {
        let result = ConsentActivation.resolve(
            active: "local",
            activeHasKey: false,
            statuses: [.gemini: .online])
        #expect(result == .gemini)
    }

    // MARK: - Ordering determinism with multiple validated clouds

    @Test func cloudProviderOrder_isClaudeChatGPTGeminiAzure() {
        // Pins the order `resolve` depends on. If `LLMProvider.allCases` is
        // reordered, this fails loudly rather than silently rotting the
        // determinism tests below.
        #expect(LLMProvider.allCases.filter(\.needsAPIKey)
                == [.claude, .chatGPT, .gemini, .azure])
    }

    @Test func localActive_multipleOnline_returnsFirstByAllCasesOrder() {
        // allCases order: claude, chatGPT, gemini, azure → claude wins.
        let result = ConsentActivation.resolve(
            active: "local",
            activeHasKey: false,
            statuses: [.gemini: .online, .claude: .online, .chatGPT: .online])
        #expect(result == .claude)
    }

    @Test func localActive_chatGPTAndAzureOnline_returnsChatGPT() {
        let result = ConsentActivation.resolve(
            active: "local",
            activeHasKey: false,
            statuses: [.azure: .online, .chatGPT: .online])
        #expect(result == .chatGPT)
    }

    // MARK: - No validated cloud → keep default (true first run)

    @Test func localActive_noOnlineCloud_returnsNil() {
        let result = ConsentActivation.resolve(
            active: "local",
            activeHasKey: false,
            statuses: [:])
        #expect(result == nil)
    }

    @Test func localActive_onlyNonOnlineStatuses_returnsNil() {
        // Key present but invalid / unavailable / checking must NOT activate.
        let result = ConsentActivation.resolve(
            active: "local",
            activeHasKey: false,
            statuses: [.claude: .invalid, .chatGPT: .unavailable, .gemini: .checking])
        #expect(result == nil)
    }

    // MARK: - Cloud active with NO stored key → adopt first validated cloud

    @Test func keylessCloudActive_otherCloudOnline_switches() {
        // active is anthropic but anthropic has no stored key; gemini is
        // online. With no key the choice isn't deliberate/usable, so adopt
        // the validated cloud. (Contrast keyedCloudActive_* above.)
        let result = ConsentActivation.resolve(
            active: "anthropic",
            activeHasKey: false,
            statuses: [.gemini: .online])
        #expect(result == .gemini)
    }

    @Test func keylessCloudActive_noOnlineCloud_returnsNil() {
        let result = ConsentActivation.resolve(
            active: "anthropic",
            activeHasKey: false,
            statuses: [.claude: .notSetUp])
        #expect(result == nil)
    }

    // MARK: - Malformed / empty active string treated as keyless

    @Test func emptyActive_oneOnlineCloud_returnsThatCloud() {
        let result = ConsentActivation.resolve(
            active: "",
            activeHasKey: false,
            statuses: [.claude: .online])
        #expect(result == .claude)
    }

    @Test func garbageActive_oneOnlineCloud_returnsThatCloud() {
        let result = ConsentActivation.resolve(
            active: "not-a-provider",
            activeHasKey: false,
            statuses: [.chatGPT: .online])
        #expect(result == .chatGPT)
    }

    @Test func garbageActive_noOnlineCloud_returnsNil() {
        let result = ConsentActivation.resolve(
            active: "not-a-provider",
            activeHasKey: false,
            statuses: [:])
        #expect(result == nil)
    }
}
