import Foundation
import Testing

@testable import Bristlenose

// When to put a browser in front of the researcher, and what to ask for when
// we do.
//
// Both decisions fail invisibly at the call site. Asking when we needn't looks
// exactly like asking when we must — the researcher cannot tell a necessary
// consent screen from a redundant one, so a redundant one reads as the app
// having lost the last grant. And asking too narrowly does not fail at all
// today; it fails on the *next* import, which is the one that arrives after
// they have decided the feature is fine.
//
// Measured against the shipping behaviour on 17 Aug 2026: a Picker round trip
// per batch, every batch, including for files granted minutes earlier.

@Suite("When a Picker round trip is actually needed")
struct MediaGrantPlanTests {

    private typealias Plan = GoogleMeetSource.MediaGrantPlan

    // MARK: - Not asking

    @Test("A batch we already hold asks nothing")
    func heldBatchNeedsNoPicker() {
        // The case the shipping code got wrong: re-importing, or a second
        // batch drawn from a listing already granted, round-tripped the
        // Picker regardless.
        let plan = Plan.decide(
            batch: ["a", "b"],
            listing: ["a", "b", "c"],
            granted: ["a", "b", "c"],
            tokenUsable: true)
        #expect(plan == .alreadyHeld)
    }

    @Test("One un-granted file in the batch is enough to ask")
    func partialGrantStillAsks() {
        // Not "mostly held" — the grant is per file, so a batch is reachable
        // only if every file in it is.
        let plan = Plan.decide(
            batch: ["a", "b"],
            listing: ["a", "b"],
            granted: ["a"],
            tokenUsable: true)
        #expect(plan != .alreadyHeld)
    }

    @Test("A dead token re-asks even when every file is granted")
    func expiredTokenStillAsks() {
        // `fetch` guards on grantedFileIDs *then* reads the token, so
        // returning .alreadyHeld here would sail past the guard and 401 — a
        // failure that reads as a network fault rather than a permission one,
        // and sends the researcher to check their wifi.
        let plan = Plan.decide(
            batch: ["a"],
            listing: ["a"],
            granted: ["a"],
            tokenUsable: false)
        #expect(plan != .alreadyHeld)
    }

    // MARK: - What we ask for

    @Test("Asking covers the whole listing, not just the batch")
    func asksOverTheWholeListing() {
        // The fix for the second round trip. Ticking one recording and
        // importing it used to grant exactly that file, so ticking a second
        // one — from the same window, the same account, the same study —
        // asked again.
        let plan = Plan.decide(
            batch: ["b"],
            listing: ["a", "b", "c"],
            granted: [],
            tokenUsable: false)
        #expect(plan == .ask(fileIDs: ["a", "b", "c"]))
    }

    @Test("A batch file missing from the listing is still asked for")
    func batchIsNeverDroppedFromTheRequest() {
        // Defensive, and the direction that matters: the listing is a snapshot
        // and the batch is what is actually about to be fetched. Asking for
        // the union can only over-ask; asking for the listing alone could omit
        // the one file the transfer needs and fail it at the last step.
        let plan = Plan.decide(
            batch: ["z"],
            listing: ["a"],
            granted: [],
            tokenUsable: false)
        #expect(plan == .ask(fileIDs: ["a", "z"]))
    }

    @Test("The same listing produces the same request twice")
    func requestIsStable() {
        // Sets have no order. Without the sort this returned a different id
        // ordering per run, which makes a live consent URL undiffable and a
        // failing test unreadable.
        let listing: Set<String> = ["c", "a", "b"]
        let first = Plan.decide(batch: ["a"], listing: listing, granted: [], tokenUsable: false)
        let second = Plan.decide(batch: ["a"], listing: listing, granted: [], tokenUsable: false)
        #expect(first == second)
        #expect(first == .ask(fileIDs: ["a", "b", "c"]))
    }

    @Test("Granting the listing makes every later batch from it free")
    func grantingTheListingCoversLaterBatches() {
        // The whole point, stated end to end: one round trip over the window,
        // then nothing — whichever rows the researcher ticks next.
        let listing: Set<String> = ["a", "b", "c"]
        guard case .ask(let asked) = Plan.decide(
            batch: ["a"], listing: listing, granted: [], tokenUsable: false)
        else { Issue.record("first import must ask"); return }

        let granted = Set(asked)
        for later in [["b"], ["c"], ["a", "b", "c"]] {
            #expect(Plan.decide(batch: later, listing: listing,
                                granted: granted, tokenUsable: true) == .alreadyHeld,
                    "\(later) should be covered by the listing-wide grant")
        }
    }
}
