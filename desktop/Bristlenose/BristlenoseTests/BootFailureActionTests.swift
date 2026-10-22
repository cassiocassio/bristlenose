import Testing
@testable import Bristlenose

/// The boot failure pane's primary button (N08). A first failure offers Retry; a
/// failure of a start the researcher asked for with Retry offers Send Feedback…
/// instead, so they are not left hitting Retry over and over (owner decision,
/// 22 Oct 2026). The bit itself is pinned by `ServeManagerRetryTests`.
@Suite("Boot failure action")
struct BootFailureActionTests {

    @Test func aFirstFailureOffersRetry() {
        #expect(BootView.failureAction(startedByRetry: false) == .retry)
    }

    @Test func aFailedRetryOffersSendFeedback() {
        #expect(BootView.failureAction(startedByRetry: true) == .sendFeedback)
    }
}
