import Testing
@testable import Bristlenose

/// What **Re-analyse…** shows: it never runs `--clean` unasked.
///
/// THE REGRESSION (decision #1, 21 Oct 2026). `askToReAnalyse` started the
/// destructive rebuild without a confirmation whenever the curation count came
/// back empty, and an unreadable database came back empty too. A count that
/// could not be taken now confirms, with its own sentence; a real zero confirms
/// too, without a list (N130).
struct ReAnalyseDecisionTests {

    @Test func anUnreadableCountConfirms() {
        #expect(ReAnalyseDecision.decide(nil) == .confirmUnreadable)
    }

    /// N130 (decision #314, 12 Nov 2026): a real zero used to start the run
    /// unasked. It asks now, without a list, so `--clean` never runs unasked at all.
    @Test func aRealZeroStillAsksWithoutAList() {
        #expect(ReAnalyseDecision.decide(CurationCounts.none) == .confirm(CurationCounts.none))
        #expect(CurationCounts.none.isEmpty)
    }

    @Test func theListIsDrawnOnlyWhenSomethingIsCounted() {
        #expect(!ReAnalyseConfirmSheet.drawsLossList(CurationCounts.none))
        #expect(ReAnalyseConfirmSheet.drawsLossList(CurationCounts(renamedSpeakers: 1)))
        #expect(ReAnalyseConfirmSheet.drawsLossList(CurationCounts(removedBadges: 1)))
    }

    @Test func theRebuildLineIsNeverDrawnForAZeroCountOfInterviews() {
        #expect(!ReAnalyseConfirmSheet.drawsRebuildLine(sessionCount: 0))
        #expect(ReAnalyseConfirmSheet.drawsRebuildLine(sessionCount: 1))
        #expect(ReAnalyseConfirmSheet.drawsRebuildLine(sessionCount: 14))
    }

    @Test func anyCurationConfirmsWithItsCounts() {
        let starred = CurationCounts(starredQuotes: 2)
        #expect(ReAnalyseDecision.decide(starred) == .confirm(starred))
        let renamed = CurationCounts(renamedSpeakers: 1)
        #expect(ReAnalyseDecision.decide(renamed) == .confirm(renamed))
    }
}
