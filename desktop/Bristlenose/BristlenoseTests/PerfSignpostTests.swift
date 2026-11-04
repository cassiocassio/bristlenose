import Foundation
import Testing
@testable import Bristlenose

/// The bookkeeping behind the perf signposts: which moments are open, and that none can dangle.
@MainActor
@Suite("Perf signposts", .serialized)
struct PerfSignpostTests {
    init() { PerfSignpost.resetForTests() }

    @Test func aMomentIsOpenBetweenBeginAndEnd() {
        PerfSignpost.begin(.lensSwitch, scope: "w1")
        #expect(PerfSignpost.isOpen(.lensSwitch, scope: "w1"))
        #expect(PerfSignpost.end(.lensSwitch, scope: "w1"))
        #expect(!PerfSignpost.isOpen(.lensSwitch, scope: "w1"))
    }

    @Test func endingAMomentThatIsNotOpenDoesNothing() {
        #expect(PerfSignpost.end(.serveReady, scope: "s") == false)
        PerfSignpost.begin(.serveReady, scope: "s")
        #expect(PerfSignpost.end(.serveReady, scope: "s"))
        #expect(PerfSignpost.end(.serveReady, scope: "s") == false)   // already closed
    }

    @Test func aSecondBeginSupersedesTheFirstSoNothingDangles() {
        PerfSignpost.begin(.projectSelect, scope: "w1")
        PerfSignpost.begin(.projectSelect, scope: "w1")
        #expect(PerfSignpost.end(.projectSelect, scope: "w1"))        // one interval left, not two
        #expect(PerfSignpost.end(.projectSelect, scope: "w1") == false)
    }

    @Test func twoWindowsDoNotCloseEachOther() {
        PerfSignpost.begin(.lensSwitch, scope: "w1")
        PerfSignpost.begin(.lensSwitch, scope: "w2")
        #expect(PerfSignpost.end(.lensSwitch, scope: "w1"))
        #expect(PerfSignpost.isOpen(.lensSwitch, scope: "w2"))
        #expect(PerfSignpost.end(.lensSwitch, scope: "w3") == false)   // a window that never began
    }

    @Test func differentMomentsInOneScopeAreIndependent() {
        PerfSignpost.begin(.openTranscript, scope: "w1")
        PerfSignpost.begin(.firstCardPainted, scope: "w1")
        #expect(PerfSignpost.end(.openTranscript, scope: "w1"))
        #expect(PerfSignpost.isOpen(.firstCardPainted, scope: "w1"))
    }

    /// The sidecar's opt-in stage stamps are re-emitted as signposts; any other output line is not.
    @Test func onlyAStageStampIsTakenForASidecarStage() {
        #expect(PerfSignpost.sidecarStage(fromLine: "@startup-stage create-app-start 1793787585294"))
        #expect(!PerfSignpost.sidecarStage(fromLine: "Report: http://127.0.0.1:51234/report/"))
        #expect(!PerfSignpost.sidecarStage(fromLine: "[bristlenose] auth-token: abc"))
        #expect(!PerfSignpost.sidecarStage(fromLine: ""))
    }

    /// The names are the cross-layer contract with the server's Server-Timing and the page's
    /// performance.mark: a rename here has to be a rename there.
    @Test func theMomentNamesAreTheSharedOnes() {
        #expect(Set(PerfMoment.allCases.map(\.rawValue)) == [
            "launch-to-ready", "lens-switch", "project-select", "serve-ready", "open-transcript", "first-card-painted",
        ])
        for m in PerfMoment.allCases { #expect("\(m.signpostName)" == m.rawValue) }
    }
}
