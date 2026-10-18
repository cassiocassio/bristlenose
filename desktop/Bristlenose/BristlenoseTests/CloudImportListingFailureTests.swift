import Foundation
import Testing

@testable import Bristlenose

// A listing that failed before any page arrived is not an empty month.
//
// Found by the pre-release review, 18 Oct 2026: every adapter returns no rows
// and a `.failed(after: 0, …)` outcome for a 503, a dropped connection or a
// refresh that could not reach the server, and the window drew "No recordings
// in the last 30 days" for all of them. A researcher reading that concludes the
// session was never recorded.

@MainActor
@Suite("Listing failure")
struct CloudImportListingFailureTests {

    private func loaded(_ scenario: CloudImportScenario) async -> CloudImportStore {
        let store = CloudImportStore(source: FixtureCloudSource(scenario: scenario, platform: .zoom))
        await store.load()
        return store
    }

    @Test("A listing that failed before any page is not an empty month")
    func failedIsNotEmpty() async {
        let store = await loaded(.listingFailed)
        #expect(store.phase == .loaded)
        #expect(store.listingFailed)
    }

    @Test("A genuinely empty month stays empty")
    func emptyIsNotFailed() async {
        let store = await loaded(.emptyWindow)
        #expect(!store.listingFailed)
    }

    @Test("A partial list keeps its rows rather than reading as failed")
    func partialIsNotFailed() async {
        let store = await loaded(.paginatorCapped)
        #expect(!store.listingFailed)
        #expect(!(store.listing?.rows.isEmpty ?? true))
    }
}
