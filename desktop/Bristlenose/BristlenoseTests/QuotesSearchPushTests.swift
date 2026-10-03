import Testing
@testable import Bristlenose

/// The two silent failures the toolbar search gate exists to prevent: an echo
/// loop (the SPA echoes the query back; re-sending it would ping-pong) and a
/// filter sent from a lens that does not filter. Both are silent — nothing
/// crashes, the field just fights itself or filters the wrong lens — which is
/// why the decision lives in a helper and not in the view's closure.
struct QuotesSearchPushTests {
    @Test("A value the store already holds is not re-sent")
    func sameValueIsNotPushed() {
        #expect(!QuotesSearchPush.shouldPush(typed: "pax", lastKnown: "pax", activeTab: .quotes))
    }

    @Test("A new value on Quotes is sent")
    func newValueOnQuotesIsPushed() {
        #expect(QuotesSearchPush.shouldPush(typed: "pax", lastKnown: "", activeTab: .quotes))
    }

    @Test("Nothing is sent from a lens that does not filter, or with no lens")
    func otherLensesAreSuppressed() {
        for tab in [Tab.sessions, .codebook, .signals, .project] {
            #expect(!QuotesSearchPush.shouldPush(typed: "pax", lastKnown: "", activeTab: tab))
        }
        #expect(!QuotesSearchPush.shouldPush(typed: "pax", lastKnown: "", activeTab: nil))
    }
}
