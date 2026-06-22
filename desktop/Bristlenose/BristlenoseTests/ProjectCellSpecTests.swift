import AppKit
import Testing

@testable import Bristlenose

/// Pins the ONE deliberate divergence of the native cell port from `ProjectRow`:
/// `.placeholder` collapses to a single line; every other state keeps the
/// subtitle line (two-line). The absolute row-height pixels are tuned visually
/// against the gallery; the *rule* and the height *ordering* are invariants.
@Suite struct ProjectCellSpecTests {

    @Test func placeholderIsSingleLine() {
        #expect(ProjectCellSpec.isTwoLine(.placeholder) == false)
    }

    @Test func statesWithContentAreTwoLine() {
        let twoLineCases: [SubtitleVariant] = [
            .running,
            .stopping,
            .queued(position: 1),
            .stopped,
            .partial(transcribeOnly: false),
            .copying(fraction: 0.5),
            .copyCancelling,
            .failed(summary: "boom"),
            .failedDiagnostic,
            .completedPartial,
            .unreachable(reason: "offline"),
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
