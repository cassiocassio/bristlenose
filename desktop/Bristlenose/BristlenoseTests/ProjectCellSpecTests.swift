import AppKit
import Testing

@testable import Bristlenose

/// Pins the ONE deliberate divergence of the native cell port from `ProjectRow`:
/// `.placeholder` collapses to a single line; every other state keeps the
/// subtitle line (two-line). The absolute row-height pixels are tuned visually
/// against the gallery; the *rule* and the height *ordering* are invariants.
@Suite struct ProjectCellSpecTests {

    /// BR-14 (16 Nov 2026): a clean completed run — `.ready`, nothing missing or
    /// unanalysed — resolves to `.placeholder`, which is a single-line row. A tall
    /// row with an empty second line after a normal run therefore means a delta or
    /// another state is on the line, not the placeholder reservation.
    @Test func cleanCompletedRunIsSingleLine() {
        let variant = ProjectSubtitle.resolve(
            availability: .ready, pipelineState: .ready(Date()), isStopping: false,
            addingCount: nil, copy: nil, importBatch: nil, lastRunAt: Date(),
            missingCount: 0, unanalysedCount: 0)
        #expect(variant == .placeholder)
        #expect(ProjectCellSpec.isTwoLine(variant) == false)
        #expect(ProjectCellSpec.rowHeight(twoLine: ProjectCellSpec.isTwoLine(variant))
                == ProjectCellSpec.singleLineHeight)
    }

    @Test func placeholderIsSingleLine() {
        #expect(ProjectCellSpec.isTwoLine(.placeholder) == false)
    }

    @Test func statesWithContentAreTwoLine() {
        let twoLineCases: [SubtitleVariant] = [
            .running,
            .stopping,
            .queued(position: 1),
            .stopped(),
            .partial(transcribeOnly: false),
            .copying(fraction: 0.5),
            .copyCancelling,
            .failed(message: .passthrough("boom")),
            .failedDiagnostic(),
            .completedPartial(analysed: SessionsAnalysed(done: 6, total: 8)),
            .unreachable(reason: .timedOut),
        ]
        for variant in twoLineCases {
            #expect(ProjectCellSpec.isTwoLine(variant) == true,
                    "\(variant) should keep its subtitle line (two-line)")
        }
    }

    @Test func singleLineIsShorterThanTwoLine() {
        #expect(ProjectCellSpec.rowHeight(twoLine: false)
                < ProjectCellSpec.rowHeight(twoLine: true))
    }

    @Test func twoLineClearsBothFonts() {
        // The two-line height must leave room for title + gap + subtitle. Pixels
        // are tuned at review; this ordering invariant is not negotiable.
        let two = ProjectCellSpec.rowHeight(twoLine: true)
        let title = ceil(ProjectCellSpec.titleFont.boundingRectForFont.height)
        let subtitle = ceil(ProjectCellSpec.subtitleFont.boundingRectForFont.height)
        #expect(two >= title + ProjectCellSpec.titleToSubtitle + subtitle)
    }
}
