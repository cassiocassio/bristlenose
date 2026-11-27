import Testing
@testable import Bristlenose

// The AI disclosure's version gate (Apple 5.1.2(i)). v3 (27 Nov 2026) corrected two false
// claims on v2, so everyone who acknowledged v2 must see the sheet again, once.

@Suite struct AIConsentVersionTests {

    @Test func aV2AcknowledgementNoLongerCounts() {
        #expect(!AIConsentView.isAcknowledged(2))
        #expect(!AIConsentView.isAcknowledged(AIConsentView.currentVersion - 1))
    }

    @Test func neverAnsweredShowsTheSheet() {
        #expect(!AIConsentView.isAcknowledged(0))
    }

    @Test func theCurrentVersionIsAcknowledged() {
        #expect(AIConsentView.isAcknowledged(AIConsentView.currentVersion))
        // A later build's answer, read by an older one (a downgrade), still counts.
        #expect(AIConsentView.isAcknowledged(AIConsentView.currentVersion + 1))
    }

    /// A bump raises the first-run sheet in every open window. Answered in one, the others
    /// close (and record nothing); unanswered, they stay.
    @Test func otherWindowsFirstRunSheetsCloseOnceAnswered() {
        let now = AIConsentView.currentVersion
        #expect(!AIConsentView.sheetStaysOpen(acknowledgedVersion: now, isReviewMode: false))
        #expect(AIConsentView.sheetStaysOpen(acknowledgedVersion: now - 1, isReviewMode: false))
    }

    /// Bristlenose ▸ AI & Privacy… is the person's own reading; a version change elsewhere
    /// does not take it away.
    @Test func theReviewSheetStays() {
        #expect(AIConsentView.sheetStaysOpen(acknowledgedVersion: AIConsentView.currentVersion,
                                             isReviewMode: true))
    }
}
