import Foundation
import Testing
@testable import Bristlenose

/// The intent-policy table (P3/D3). Every row of `LensActivation.decide` —
/// what an activation DOES, per document state and lens relation.
struct LensActivationTests {

    private func decide(
        tab: Tab,
        activeTab: Tab? = nil,
        documentState: DocumentState = .spa,
        restoreSessionID: String? = nil
    ) -> LensActivation {
        LensActivation.decide(
            tab: tab,
            activeTab: activeTab,
            documentState: documentState,
            restoreSessionID: restoreSessionID
        )
    }

    // MARK: - Live SPA

    @Test func differentLensDispatchesToRoot() {
        #expect(decide(tab: .quotes, activeTab: .project) == .root(.quotes))
    }

    @Test func sessionsRestoresTheRememberedTranscript() {
        #expect(decide(tab: .sessions, activeTab: .quotes, restoreSessionID: "s3")
                == .restore(sessionID: "s3"))
    }

    @Test func sessionsWithNoMemoryGoesToTheGrid() {
        #expect(decide(tab: .sessions, activeTab: .quotes) == .root(.sessions))
    }

    /// D3, the Finder model: re-activating the current lens returns to its
    /// root — and deliberately BYPASSES the route memory (a transcript's
    /// Sessions click goes to the grid, not back to the transcript). The
    /// memory itself is kept, so leave-and-return still restores.
    @Test func reactivatingTheCurrentLensReturnsToItsRoot() {
        #expect(decide(tab: .sessions, activeTab: .sessions, restoreSessionID: "s3")
                == .root(.sessions))
        #expect(decide(tab: .quotes, activeTab: .quotes) == .root(.quotes))
    }

    // MARK: - Loading document (D1-C's lit-on-prior window)

    @Test func loadingQueues() {
        // Unconditionally: reachability is the affordance gates' job (rows,
        // rail, menu all dim on LensAvailability). A second gate here could
        // only produce false negatives — a stale mirror silently eating
        // clicks — so the queue takes whatever reaches it; a race's intent
        // is discarded on status-page/switch and can only replay on the
        // `ready` a truly dim rail never gets.
        #expect(decide(tab: .quotes, documentState: .loading) == .queue(.quotes))
    }

    @Test func sameLensWhileLoadingIgnores() {
        // `activeTab` derives from the SPA's route-change messages, so a
        // non-SPA document with a non-nil activeTab is a stale echo —
        // nothing to return to (and nothing worth queueing: the document
        // will land on its own route).
        #expect(decide(tab: .sessions, activeTab: .sessions, documentState: .loading)
                == .ignore)
    }

    // MARK: - Status page

    @Test func statusPageIgnoresEverything() {
        for outcome in [StatusPageOutcome.noRun, .failed, .cancelled, .unknown] {
            #expect(decide(tab: .quotes, documentState: .statusPage(outcome)) == .ignore)
            #expect(decide(tab: .quotes, activeTab: .quotes,
                           documentState: .statusPage(outcome)) == .ignore)
        }
    }
}
