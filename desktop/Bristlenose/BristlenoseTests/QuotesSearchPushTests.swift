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

/// The third silent failure: the report answers a keystroke late. Typing "pa" sends "p"; the
/// echo of "p" can arrive after the field already holds "pa", and taking it as a change made
/// by the store would put "p" back in the field and send the wrong word on. The field has to
/// recognise an old value of its own (N165).
struct QuotesSearchEchoTests {
    @Test("A late echo of an earlier keystroke does not replace what is typed now")
    func lateEchoOfOwnEarlierValueIsIgnored() {
        var echo = QuotesSearchEcho()
        echo.pushed("p")
        echo.pushed("pa")
        let r1 = echo.isStaleOwnEcho("p", typed: "pax")
        #expect(r1)
    }

    @Test("The echo that matches the field is not stale, and settles what was outstanding")
    func echoOfTheCurrentTextIsNotStale() {
        var echo = QuotesSearchEcho()
        echo.pushed("p")
        echo.pushed("pa")
        let r2 = echo.isStaleOwnEcho("pa", typed: "pa")
        #expect(!r2)
        // Settled: the same value arriving from the store later is the store's own doing.
        let r3 = echo.isStaleOwnEcho("p", typed: "pa")
        #expect(!r3)
    }

    @Test("A change the store makes on its own always reaches the field")
    func storeOriginatedChangeIsNotStale() {
        var echo = QuotesSearchEcho()
        echo.pushed("p")
        let r4 = echo.isStaleOwnEcho("hamburger", typed: "pax")
        #expect(!r4)
        // and it forgets what was outstanding: the old value now is also the store's
        let r5 = echo.isStaleOwnEcho("p", typed: "pax")
        #expect(!r5)
    }

    @Test("A reset to empty after typing is the store's, not an old echo")
    func resetToEmptyReachesTheField() {
        var echo = QuotesSearchEcho()
        echo.pushed("")      // typed, then cleared
        echo.pushed("abc")
        let r6 = echo.isStaleOwnEcho("abc", typed: "abc")
        #expect(!r6)   // settles everything
        let r7 = echo.isStaleOwnEcho("", typed: "abc")
        #expect(!r7)      // All Quotes reset
    }

    @Test("An echo older than one already seen settles those before it")
    func echoesAreInOrder() {
        var echo = QuotesSearchEcho()
        echo.pushed("p")
        echo.pushed("pa")
        echo.pushed("pax")
        let r8 = echo.isStaleOwnEcho("pa", typed: "paxe")
        #expect(r8)   // "p" is settled with it
        let r9 = echo.isStaleOwnEcho("p", typed: "paxe")
        #expect(!r9)   // so "p" is no longer outstanding
    }
}
