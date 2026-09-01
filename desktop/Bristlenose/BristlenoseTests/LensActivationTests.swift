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
        lensesAvailable: Bool = true,
        restoreSessionID: String? = nil
    ) -> LensActivation {
        LensActivation.decide(
            tab: tab,
            activeTab: activeTab,
            documentState: documentState,
            lensesAvailable: lensesAvailable,
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

    @Test func loadingWithALitRailQueues() {
        #expect(decide(tab: .quotes, documentState: .loading) == .queue(.quotes))
    }

    @Test func loadingWithADimRailIgnores() {
        // Only a lit rail queues — a dim rail's controls are unreachable
        // anyway; anything arriving here is a race, not an intent.
        #expect(decide(tab: .quotes, documentState: .loading, lensesAvailable: false)
                == .ignore)
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
