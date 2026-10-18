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

// Zoom lists a meeting before its files exist, so an empty Zoom list with
// meetings in it is "still recording or processing", not Meet's "none with a
// recording you organised" (18 Oct 2026, the first live Pro listing).
@Suite("Empty-window sentence")
struct CloudImportEmptyDetailTests {

    @Test("Zoom says the meetings are still being recorded or processed")
    func zoomNamesProcessing() {
        #expect(CloudPlatform.zoom.emptyDetailKey(meetingsInWindow: 2)
                == "desktop.cloudImport.emptyDetailZoom")
    }

    @Test("Zoom with no meetings at all has no sentence")
    func zoomWithNothingIsSilent() {
        #expect(CloudPlatform.zoom.emptyDetailKey(meetingsInWindow: 0) == nil)
    }

    @Test("Meet and Teams keep the organiser sentence")
    func calendarPlatformsUnchanged() {
        #expect(CloudPlatform.meet.emptyDetailKey(meetingsInWindow: 3) == "desktop.cloudImport.emptyDetail")
        #expect(CloudPlatform.teams.emptyDetailKey(meetingsInWindow: 3) == "desktop.cloudImport.emptyDetail")
    }
}
