import Foundation
import Testing

@testable import Bristlenose

/// Pins the completion → count-refresh transition predicate: which projects are
/// considered to have *left* the analysing state (so their analysis DB may have
/// changed and the sidebar count needs a re-scan). The folder watcher can't see
/// DB writes under `bristlenose-output/`, so this transition is the only signal
/// that triggers `ProjectIndex.rescan`; the cases below are the contract.
@Suite struct CompletionRescanTests {

    private let a = UUID()
    private let b = UUID()
    private let c = UUID()

    // MARK: - isAnalysing vocabulary

    @Test func isAnalysing_trueOnlyForScanningAndRunning() {
        #expect(CompletionRescan.isAnalysing(.scanning))
        #expect(CompletionRescan.isAnalysing(.running))

        #expect(!CompletionRescan.isAnalysing(nil))
        #expect(!CompletionRescan.isAnalysing(.idle))
        #expect(!CompletionRescan.isAnalysing(.queued(position: 1)))
        #expect(!CompletionRescan.isAnalysing(.ready(Date())))
        #expect(!CompletionRescan.isAnalysing(.failed("x", category: .unknown)))
        #expect(!CompletionRescan.isAnalysing(.unreachable(reason: "x")))
        #expect(!CompletionRescan.isAnalysing(.partial(kind: "transcribe-only", stagesComplete: [])))
        #expect(!CompletionRescan.isAnalysing(.stopped(stagesComplete: [])))
        #expect(!CompletionRescan.isAnalysing(.completedPartial(summary: PipelineSummary())))
        #expect(!CompletionRescan.isAnalysing(.failedWithDiagnostic(summary: PipelineSummary())))
    }

    // MARK: - Included transitions (analysing → any terminal state)

    @Test func includes_runningToTerminalStates() {
        // Every terminal outcome may have mutated the sessions table.
        let terminals: [PipelineState] = [
            .ready(Date()),
            .completedPartial(summary: PipelineSummary()),
            .failed("boom", category: .unknown),
            .partial(kind: "transcribe-only", stagesComplete: []),
            .stopped(stagesComplete: []),
            .idle,
        ]
        for terminal in terminals {
            let result = CompletionRescan.projectsLeavingAnalysis(
                old: [a: .running], new: [a: terminal]
            )
            #expect(result == [a], "running → \(terminal) should refresh")
        }
    }

    @Test func includes_scanningToIdle() {
        let result = CompletionRescan.projectsLeavingAnalysis(
            old: [a: .scanning], new: [a: .idle]
        )
        #expect(result == [a])
    }

    // MARK: - Excluded transitions

    @Test func excludes_stillAnalysing() {
        // running → running and scanning → running are both still in-flight.
        #expect(CompletionRescan.projectsLeavingAnalysis(
            old: [a: .running], new: [a: .running]
        ).isEmpty)
        #expect(CompletionRescan.projectsLeavingAnalysis(
            old: [a: .scanning], new: [a: .running]
        ).isEmpty)
    }

    @Test func excludes_terminalToTerminal() {
        // ready → ready (e.g. a manifest re-read) never analysed in `old`.
        #expect(CompletionRescan.projectsLeavingAnalysis(
            old: [a: .ready(Date())], new: [a: .ready(Date())]
        ).isEmpty)
    }

    @Test func excludes_newlyAddedProject() {
        // A project absent from `old` isn't "leaving" anything, whether it
        // appears as analysing or already-terminal.
        #expect(CompletionRescan.projectsLeavingAnalysis(
            old: [:], new: [a: .scanning]
        ).isEmpty)
        #expect(CompletionRescan.projectsLeavingAnalysis(
            old: [:], new: [a: .ready(Date())]
        ).isEmpty)
    }

    @Test func excludes_removedProject() {
        // Analysing in `old`, gone from `new` (removed mid-run) → no watcher to
        // refresh, so it must not appear.
        #expect(CompletionRescan.projectsLeavingAnalysis(
            old: [a: .running], new: [:]
        ).isEmpty)
    }

    // MARK: - Mixed map

    @Test func returnsExactlyTheLeavingSubset() {
        let result = CompletionRescan.projectsLeavingAnalysis(
            old: [a: .running, b: .running, c: .ready(Date())],
            new: [a: .ready(Date()), b: .running, c: .ready(Date())]
        )
        // a finished; b still running; c never analysed.
        #expect(Set(result) == [a])
    }
}
