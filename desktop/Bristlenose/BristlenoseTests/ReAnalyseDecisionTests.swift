import Testing
@testable import Bristlenose

/// Whether **Re-analyse…** runs `--clean` unasked.
///
/// THE REGRESSION (decision #1, 21 Oct 2026). `askToReAnalyse` started the
/// destructive rebuild without a confirmation whenever the curation count came
/// back empty, and an unreadable database came back empty too. A count that
/// could not be taken now confirms, with its own sentence; only a real zero
/// proceeds.
struct ReAnalyseDecisionTests {

    @Test func anUnreadableCountConfirms() {
        #expect(ReAnalyseDecision.decide(nil) == .confirmUnreadable)
    }

    @Test func aRealZeroProceedsUnasked() {
        #expect(ReAnalyseDecision.decide(CurationCounts.none) == .proceed)
    }

    @Test func anyCurationConfirmsWithItsCounts() {
        let starred = CurationCounts(starredQuotes: 2)
        #expect(ReAnalyseDecision.decide(starred) == .confirm(starred))
        let renamed = CurationCounts(renamedSpeakers: 1)
        #expect(ReAnalyseDecision.decide(renamed) == .confirm(renamed))
    }
}
