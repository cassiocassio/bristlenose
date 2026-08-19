import Testing
import Foundation
@testable import Bristlenose

/// The wire contract for files that aren't in the report.
///
/// Stages 1-2 had no slot on `PipelineSummary` until Aug 2026, which is why
/// refusals reached no surface at all: `StageFailure.source_file` had existed
/// since Jul 2026 and three consumers already keyed on it, but there was
/// nowhere in the summary to put one.
@Suite struct IngestOutcomeTests {

    private func decode(_ json: String) throws -> PipelineSummary {
        try JSONDecoder().decode(PipelineSummary.self, from: Data(json.utf8))
    }

    @Test func theIngestBucketDecodesAndLeadsTheOrder() throws {
        let summary = try decode("""
        {"ingest": {"attempted": 58, "succeeded": 41, "duration_ms": 320,
          "failed": [
            {"source_file": "p07 failed download.mp4",
             "cause": {"category": "unusable_input",
                       "message": "The file is empty — the transfer produced no data."}},
            {"source_file": "tape-capture.dv",
             "cause": {"category": "unusable_input",
                       "message": "Not a format Bristlenose reads."}}
          ]},
         "transcripts": {"attempted": 41, "succeeded": 41, "failed": []}}
        """)
        #expect(summary.ingest?.attempted == 58)
        #expect(summary.ingest?.succeeded == 41)
        #expect(summary.ingest?.failed.count == 2)
        // Files come before transcripts because that is the order they happen
        // in, and the popover renders buckets in this order.
        #expect(summary.allBuckets.first?.name == .ingest)
    }

    @Test func aDeclinedFormatAndADamagedFileShareOneCategory() throws {
        // Different causes, same consequence — a participant missing from the
        // findings — so they carry the same weight on screen and differ only in
        // what the message says.
        let summary = try decode("""
        {"ingest": {"attempted": 2, "succeeded": 0, "failed": [
            {"source_file": "a.dv", "cause": {"category": "unusable_input",
                                              "message": "Not a format Bristlenose reads."}},
            {"source_file": "b.mp4", "cause": {"category": "unusable_input",
                                               "message": "The file is empty — the transfer produced no data."}}
        ]}}
        """)
        let causes = summary.ingest?.failed.map(\.cause.category) ?? []
        #expect(causes == [.unusableInput, .unusableInput])
        #expect(Set(summary.ingest?.failed.map(\.cause.message) ?? []).count == 2,
                "same category, and still two different sentences")
    }

    @Test func anOlderRunWithNoIngestBucketStillDecodes() throws {
        // Schema-additive in the direction that matters: a terminus written
        // before this field existed must keep working.
        let summary = try decode("""
        {"transcripts": {"attempted": 2, "succeeded": 2, "failed": []}}
        """)
        #expect(summary.ingest == nil)
        #expect(summary.allBuckets.map(\.name) == [.transcripts])
    }

    // MARK: - The reader has to tolerate a word it hasn't heard

    @Test func anUnknownCategoryDoesNotTakeTheWholeEventDown() throws {
        // Before this, an unmirrored category threw during decode — and because
        // the category sits inside Cause inside the terminus event, the throw
        // took the entire event with it: no summary, no per-stage rows, no
        // cause, for a run that merely used a newer word. `unusable_input`
        // itself would have done exactly that to any build shipped before this
        // change.
        let summary = try decode("""
        {"ingest": {"attempted": 1, "succeeded": 0, "failed": [
            {"source_file": "x.mp4",
             "cause": {"category": "a_category_from_the_future", "message": "…"}}
        ]}}
        """)
        #expect(summary.ingest?.failed.first?.cause.category == .unknown)
        #expect(summary.ingest?.failed.first?.sourceFile == "x.mp4",
                "the rest of the row must survive the unknown word")
    }

    @Test func everyKnownCategoryStillDecodesToItself() throws {
        // The fallback must not swallow real values — so every case the enum
        // declares is round-tripped, not a hand-picked few. `CaseIterable` is
        // what makes this test grow on its own when a category is added.
        for category in CauseCategory.allCases where category != .unknown {
            let summary = try decode("""
            {"ingest": {"attempted": 1, "succeeded": 0, "failed": [
                {"source_file": "x", "cause": {"category": "\(category.rawValue)", "message": "m"}}]}}
            """)
            #expect(summary.ingest?.failed.first?.cause.category == category,
                    "\(category.rawValue) must decode to itself, not to .unknown")
        }
    }

    @Test func theTwoCategoryEnumsAreDeliberatelyDifferentSets() {
        // `CauseCategory` (per-stage, inside the summary) and
        // `PipelineFailureCategory` (run-level, inside the terminus cause) do
        // not carry the same cases, and should not: `output_exists` is a
        // refusal of the whole *attempt* and can never describe one file, while
        // `unusable_input` describes exactly one file and never the run.
        //
        // Both mirror one Python enum, so the asymmetry is ours. It is safe
        // only because each side now decodes an unrecognised word as
        // `.unknown` instead of throwing — noted here so the next person to
        // find the two lists differing knows it was a decision.
        #expect(CauseCategory(rawValue: "output_exists") == nil)
        #expect(PipelineFailureCategory(rawValue: "unusable_input") != nil)
        #expect(CauseCategory(rawValue: "unusable_input") != nil)
    }

    // MARK: - What the researcher reads

    @Test func theBucketIsCalledFilesNotIngest() {
        // "Ingest" is our word for it, not theirs. "Files" is already the word
        // on the empty-project pane and in the unanalysed sheet.
        #expect(PipelineSummary.BucketName.ingest.label == "Files")
        #expect(ProjectDiagnosticPopover.humanCategoryLabel(.unusableInput) == "Not analysed")
    }

    @Test func everyBucketHasALabel() {
        for name in [PipelineSummary.BucketName.ingest, .transcripts, .topics, .quotes, .themes] {
            #expect(!name.label.isEmpty, "\(name.rawValue) needs a label")
        }
    }
}
