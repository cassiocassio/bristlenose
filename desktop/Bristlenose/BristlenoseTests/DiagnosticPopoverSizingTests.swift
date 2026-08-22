import AppKit
import SwiftUI
import Testing
@testable import Bristlenose

/// The diagnostic popover's height follows its content, capped at a ceiling.
///
/// Measured through `NSHostingController.view.fittingSize` — deliberately, because
/// that is the same number `NSPopover` sizes from, so a green suite here is
/// evidence about the shipped mechanism rather than about a parallel calculation.
///
/// Assertions are **relational**, never in points. "Four refusals produce a
/// shorter popover than eleven" is the invariant; "four refusals produce 173pt"
/// is a snapshot of a font metric, and pinning it would lock the implementation
/// and break on the next system font revision.
///
/// What this catches, and what nothing else would: `ViewThatFits` silently
/// choosing the greedy `ScrollView` candidate for everything (the popover goes
/// back to a fixed box, every case measuring exactly the ceiling), or silently
/// choosing the un-scrolled candidate for everything (tall content overshoots
/// the ceiling and clips, with no scroller). Both render without error.
///
/// See `docs/design-pipeline-popover-sizing.md`.
@Suite @MainActor struct DiagnosticPopoverSizingTests {

    // MARK: - Fixtures

    private func project() -> Project {
        Project(id: UUID(), name: "Sizing", path: "/tmp/bristlenose-sizing")
    }

    /// `n` transcript failures carrying `message`, as one bucket.
    private func summary(failures n: Int, message: String) -> PipelineSummary {
        PipelineSummary(
            transcripts: StageOutcome(
                attempted: n + 4, succeeded: 4, durationMs: 1000,
                failed: (1...max(n, 1)).prefix(n).map { i in
                    SessionFailure(
                        sessionId: "s\(i)",
                        cause: Cause(
                            category: .whisper, code: nil, message: message,
                            provider: nil, stage: "s05_transcribe", sessionId: "s\(i)",
                            exitCode: nil, signal: nil, signalName: nil))
                }),
            topics: nil, quotes: nil, themes: nil)
    }

    /// The size `NSPopover` would give this state.
    private func size(for state: PipelineState) -> CGSize {
        let view = ProjectDiagnosticPopover(
            project: project(), state: state, liveData: PipelineLiveData()
        ).environmentObject(I18n())
        let host = NSHostingController(rootView: view)
        host.sizingOptions = .preferredContentSize
        host.view.layoutSubtreeIfNeeded()
        return host.view.fittingSize
    }

    private func partial(failures n: Int, message: String = "Whisper transcription timed out.") -> CGSize {
        size(for: .completedPartial(summary: summary(failures: n, message: message)))
    }

    // MARK: - The rule

    @Test func widthIsFixedRegardlessOfContent() {
        // Only the height moves. The width is the column the copy is written to.
        #expect(partial(failures: 1).width == ProjectDiagnosticPopover.width)
        #expect(partial(failures: 10).width == ProjectDiagnosticPopover.width)
    }

    @Test func aShortDiagnosticGetsAShortPopover() {
        // The whole complaint: one refusal used to be served a 320pt box.
        #expect(partial(failures: 1).height < ProjectDiagnosticPopover.ceiling)
    }

    @Test func heightGrowsWithContentDepth() {
        let one = partial(failures: 1).height
        let three = partial(failures: 3).height
        #expect(one < three, "three failures must be taller than one — got \(one) then \(three)")
        #expect(three < ProjectDiagnosticPopover.ceiling)
    }

    @Test func theCeilingHolds() {
        // Ten failures each wrapping to several lines: far past the ceiling.
        // Exactly the ceiling means the ScrollView candidate was chosen and the
        // content is reachable; anything above it means the un-scrolled candidate
        // was chosen and the tail is clipped with no way to reach it.
        let tall = partial(
            failures: 10,
            message: "Whisper transcription timed out after 600s. The 47-minute "
                + "interview file exceeds the timeout cap; consider splitting the "
                + "recording or raising BRISTLENOSE_WHISPER_TIMEOUT."
        ).height
        #expect(tall == ProjectDiagnosticPopover.ceiling)
    }

    @Test func theDegradedBodyAlsoSizesToItself() {
        // `.failed` carries no summary — a sentence and a category line, and it
        // must not be padded out to the ceiling either.
        let size = size(for: .failed(
            "Anthropic API authentication failed: invalid API key", category: .auth))
        #expect(size.width == ProjectDiagnosticPopover.width)
        #expect(size.height < ProjectDiagnosticPopover.ceiling)
    }

    @Test func theCeilingIsNotAlsoTheFloor() {
        // Guards the failure mode where the greedy ScrollView candidate wins
        // everything: every state would measure exactly the ceiling and the
        // popover would be a fixed box again, silently.
        #expect(partial(failures: 1).height != partial(failures: 5).height)
    }
}
