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
}
