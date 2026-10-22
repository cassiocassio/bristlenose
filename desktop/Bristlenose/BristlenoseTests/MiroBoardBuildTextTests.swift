import Foundation
import Testing

@testable import Bristlenose

/// Pins what the Send-to-Miro sheet says while a board builds: which line each phase reads, when
/// a wait for Miro takes over, when the bar has a value, and when a time left is shown — and that
/// the server's status decodes. The web panel's `buildLine`/`etaLine` make the same decisions.
@Suite struct MiroBoardBuildTextTests {

    private func build(_ phase: String, waiting: Bool = false, countDone: Int = 0, countTotal: Int = 0,
                       fraction: Double? = nil, eta: Double? = nil) -> MiroBoardBuild {
        MiroBoardBuild(phase: phase, done: 0, total: 20, count_done: countDone, count_total: countTotal,
                       waiting: waiting, fraction: fraction, eta_seconds: eta)
    }

    @Test func beforeTheFirstReadTheLineSaysCreating() {
        #expect(MiroBoardBuildText.lineKey(nil).key == "common.miro.creatingBoard")
        #expect(MiroBoardBuildText.fraction(nil) == nil)
    }

    @Test func eachPhaseReadsItsOwnLineWithItsCounts() {
        let cases: [(String, String)] = [
            ("preparing", "common.miro.progressPreparing"),
            ("quotes", "common.miro.progressQuotes"),
            ("groups", "common.miro.progressGroups"),
            ("screens", "common.miro.progressScreens"),
        ]
        for (phase, key) in cases {
            let line = MiroBoardBuildText.lineKey(build(phase, countDone: 3, countTotal: 9))
            #expect(line.key == key)
            #expect(line.vars == ["done": "3", "total": "9"])
        }
        #expect(MiroBoardBuildText.lineKey(build("opening")).key == "common.miro.progressOpening")
    }

    @Test func aWaitForMiroIsSaidExceptWhileTheBoardOpens() {
        #expect(MiroBoardBuildText.lineKey(build("quotes", waiting: true)).key == "common.miro.progressWaiting")
        // Opening's own line already explains the wait (Miro refusing a new board's frames).
        #expect(MiroBoardBuildText.lineKey(build("opening", waiting: true)).key == "common.miro.progressOpening")
    }

    @Test func noLongQuotesToGroupFallsBackToCreating() {
        #expect(MiroBoardBuildText.lineKey(build("groups", countTotal: 0)).key == "common.miro.creatingBoard")
    }

    @Test func theBarHasAValueOnlyWithAnHonestFraction() {
        #expect(MiroBoardBuildText.fraction(build("opening")) == nil)
        #expect(MiroBoardBuildText.fraction(build("quotes", fraction: 0.4)) == 0.4)
        #expect(MiroBoardBuildText.fraction(build("quotes", fraction: 1.2)) == 1.0)
        #expect(MiroBoardBuildText.fraction(build("quotes", fraction: .nan)) == nil)
    }

    @Test func timeLeftUsesTheRunsOwnWords() {
        let localize: (String, [String: String]) -> String = { key, vars in
            key == "desktop.chrome.pipeline.etaMinutes" ? "~\(vars["count"] ?? "?") min left"
                : key == "desktop.chrome.pipeline.etaUnderMinute" ? "<1 min left" : key
        }
        let pluralize: (String, Int) -> String = { key, n in localize(key, ["count": String(n)]) }
        #expect(MiroBoardBuildText.eta(build("quotes"), localize: localize, pluralize: pluralize) == nil)
        #expect(MiroBoardBuildText.eta(build("quotes", eta: 150), localize: localize,
                                       pluralize: pluralize) == "~3 min left")
        #expect(MiroBoardBuildText.eta(build("quotes", eta: 20), localize: localize,
                                       pluralize: pluralize) == "<1 min left")
    }

    @Test func theServersStatusDecodes() throws {
        // The shape `BoardProgress.snapshot()` sends (pinned field-for-field by
        // tests/test_board_progress_contract.py).
        let json = Data("""
        {"phase": "quotes", "done": 6, "total": 20, "count_done": 40, "count_total": 120,
         "waiting": false, "fraction": 0.3, "eta_seconds": null}
        """.utf8)
        let b = try JSONDecoder().decode(MiroBoardBuild.self, from: json)
        #expect(b.phase == "quotes" && b.count_total == 120 && b.fraction == 0.3 && b.eta_seconds == nil)
    }
}
