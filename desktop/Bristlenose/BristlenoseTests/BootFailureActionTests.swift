import Testing
@testable import Bristlenose

/// The boot failure pane's buttons (N08). A first failure offers Retry, the
/// default, then Show details. Once a start the researcher asked for with Retry
/// has failed too, Retry goes: Show details, then Send Feedback…, and Return
/// presses neither (owner decisions, 22 and 24 Oct 2026). The bit itself is
/// pinned by `ServeManagerRetryTests`.
@Suite("Boot failure buttons")
struct BootFailureActionTests {

    @Test func aFirstFailureOffersRetryThenDetailsWithRetryAsDefault() {
        let set = BootView.failureButtons(startedByRetry: false)
        #expect(set.buttons == [.retry, .showDetails])
        #expect(set.defaultButton == .retry)
    }

    @Test func aFailedRetryOffersDetailsThenSendFeedbackWithNoDefault() {
        let set = BootView.failureButtons(startedByRetry: true)
        #expect(set.buttons == [.showDetails, .sendFeedback])
        #expect(set.defaultButton == nil)
    }

    @Test func aCauseRetryCannotFixSkipsStraightToDetailsAndFeedback() {
        for key in ["desktop.boot.failure.sidecarMissing", "desktop.boot.failure.launchFailed"] {
            let message = FailureMessage(key: key, english: "x")
            #expect(!BootView.isRetryable(message))
            let set = BootView.failureButtons(startedByRetry: false, retryable: false)
            #expect(set.buttons == [.showDetails, .sendFeedback])
            #expect(set.defaultButton == nil)
        }
    }

    @Test func anEngineThatStoppedOrTimedOutCanBeRetried() {
        for key in ["desktop.boot.failure.startTimeout", "desktop.boot.failure.exitedBeforeReady",
                    "desktop.boot.failure.exitedWithCode"] {
            #expect(BootView.isRetryable(FailureMessage(key: key, english: "x")))
        }
    }

    @Test func onlyAPlainLanguageCauseDrawsABody() {
        #expect(BootView.showsBody(FailureMessage(key: "desktop.boot.failure.startTimeout", english: "x")))
        for key in ["desktop.boot.failure.sidecarMissing", "desktop.boot.failure.launchFailed",
                    "desktop.boot.failure.exitedWithCode", "desktop.boot.failure.exitedBeforeReady"] {
            #expect(!BootView.showsBody(FailureMessage(key: key, english: "x")))
        }
    }
}
