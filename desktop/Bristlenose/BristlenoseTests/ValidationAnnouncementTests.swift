import AppKit
import Testing

@testable import Bristlenose

/// A key check the researcher asked for changes only a label away from focus,
/// so VoiceOver hears it only if it is announced. An unconfigured `I18n`
/// returns keys, so these assert which label is chosen, not its wording.
@MainActor
@Suite("Key check announcement")
struct ValidationAnnouncementTests {
    let i18n = I18n()

    @Test func aCheckNobodyAskedForSaysNothing() {
        #expect(ValidationAnnouncement.make(
            provider: .claude, status: .invalid, error: "Rejected", requested: false, i18n: i18n) == nil)
    }

    @Test func checkingAndNoKeySayNothing() {
        #expect(ValidationAnnouncement.make(
            provider: .claude, status: .checking, error: nil, requested: true, i18n: i18n) == nil)
        #expect(ValidationAnnouncement.make(
            provider: .claude, status: .notSetUp, error: nil, requested: true, i18n: i18n) == nil)
    }

    @Test func aValidKeyIsAnnouncedPolitely() {
        let a = ValidationAnnouncement.make(
            provider: .claude, status: .online, error: nil, requested: true, i18n: i18n)
        #expect(a?.text == "desktop.llmSettings.status.online")
        #expect(a?.priority == .medium)
    }

    @Test func aRejectedKeyIsAnnouncedWithItsReason() {
        let a = ValidationAnnouncement.make(
            provider: .chatGPT, status: .invalid, error: "Wrong key", requested: true, i18n: i18n)
        #expect(a?.text == "desktop.llmSettings.status.invalid. Wrong key")
        #expect(a?.priority == .high)
    }

    @Test func anOnlineVerdictSaysOnlyWhatThePaneShows() {
        // The pane draws no error under a green status, so none is spoken.
        let a = ValidationAnnouncement.make(
            provider: .claude, status: .online, error: "No network connection", requested: true, i18n: i18n)
        #expect(a?.text == "desktop.llmSettings.status.online")
    }

    @Test func outOfCreditWithNoReasonSaysTheLabel() {
        let a = ValidationAnnouncement.make(
            provider: .gemini, status: .outOfCredit, error: nil, requested: true, i18n: i18n)
        #expect(a?.text == "desktop.llmSettings.status.outOfCredit")
        #expect(a?.priority == .high)
    }
}
