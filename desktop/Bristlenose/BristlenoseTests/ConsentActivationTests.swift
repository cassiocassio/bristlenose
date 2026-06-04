import Testing
@testable import Bristlenose

/// Tests for the pure consent-activation decision. The impure
/// `cloudStatuses()` snapshot reader (Keychain + verdict cache) is left
/// untested by design — it's a thin presence-and-cache read with no logic of
/// its own. All the branching lives in `resolve`, so that's where the tests go.
@Suite("Consent activation resolution")
struct ConsentActivationTests {

    // MARK: - No-override: a working cloud choice is never replaced

    @Test func onlineCloudActive_returnsNil() {
        let result = ConsentActivation.resolve(
            active: "anthropic",
            statuses: [.claude: .online])
        #expect(result == nil)
    }

    @Test func onlineCloudActive_ignoresOtherOnlineClouds() {
        // Active is a working cloud — even if another cloud is also online,
        // don't switch. Deliberate choice wins.
        let result = ConsentActivation.resolve(
            active: "google",
            statuses: [.gemini: .online, .claude: .online])
        #expect(result == nil)
    }

    // MARK: - Re-consent path (the bug): local active + validated cloud

    @Test func localActive_oneOnlineCloud_returnsThatCloud() {
        let result = ConsentActivation.resolve(
            active: "local",
            statuses: [.claude: .online])
        #expect(result == .claude)
    }

    @Test func localActive_onlyGeminiOnline_returnsGemini() {
        let result = ConsentActivation.resolve(
            active: "local",
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
            statuses: [.gemini: .online, .claude: .online, .chatGPT: .online])
        #expect(result == .claude)
    }

    @Test func localActive_chatGPTAndAzureOnline_returnsChatGPT() {
        let result = ConsentActivation.resolve(
            active: "local",
            statuses: [.azure: .online, .chatGPT: .online])
        #expect(result == .chatGPT)
    }

    // MARK: - No validated cloud → keep default (true first run)

    @Test func localActive_noOnlineCloud_returnsNil() {
        let result = ConsentActivation.resolve(
            active: "local",
            statuses: [:])
        #expect(result == nil)
    }

    @Test func localActive_onlyNonOnlineStatuses_returnsNil() {
        // Key present but invalid / unavailable / checking must NOT activate.
        let result = ConsentActivation.resolve(
            active: "local",
            statuses: [.claude: .invalid, .chatGPT: .unavailable, .gemini: .checking])
        #expect(result == nil)
    }

    // MARK: - Unconfigured cloud active → adopt first validated cloud

    @Test func unconfiguredCloudActive_otherCloudOnline_switches() {
        // active is anthropic but anthropic isn't validated; gemini is online.
        let result = ConsentActivation.resolve(
            active: "anthropic",
            statuses: [.gemini: .online])
        #expect(result == .gemini)
    }

    @Test func unconfiguredCloudActive_noOnlineCloud_returnsNil() {
        let result = ConsentActivation.resolve(
            active: "anthropic",
            statuses: [.claude: .notSetUp])
        #expect(result == nil)
    }

    // MARK: - Malformed / empty active string treated as unconfigured

    @Test func emptyActive_oneOnlineCloud_returnsThatCloud() {
        let result = ConsentActivation.resolve(
            active: "",
            statuses: [.claude: .online])
        #expect(result == .claude)
    }

    @Test func garbageActive_oneOnlineCloud_returnsThatCloud() {
        let result = ConsentActivation.resolve(
            active: "not-a-provider",
            statuses: [.chatGPT: .online])
        #expect(result == .chatGPT)
    }

    @Test func garbageActive_noOnlineCloud_returnsNil() {
        let result = ConsentActivation.resolve(
            active: "not-a-provider",
            statuses: [:])
        #expect(result == nil)
    }
}
