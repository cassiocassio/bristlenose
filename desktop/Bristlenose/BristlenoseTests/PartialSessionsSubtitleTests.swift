import Foundation
import Testing
@testable import Bristlenose

/// A partial completion's row line says how much of the report there is:
/// "6 of 8 sessions analysed" (decision #139, 24 Oct 2026), the same numbers
/// the CLI's end line prints (#134). Read through the real English locale file,
/// so a mistyped key renders as a raw key and fails here.
@MainActor
@Suite struct PartialSessionsSubtitleTests {

    private func english() -> I18n {
        let locales = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()   // BristlenoseTests
            .deletingLastPathComponent()   // Bristlenose (project)
            .deletingLastPathComponent()   // desktop
            .deletingLastPathComponent()   // repo root
            .appendingPathComponent("bristlenose/locales")
        let i18n = I18n()
        i18n.configure(localesDirectory: locales)
        i18n.setLocale("en")
        return i18n
    }

    private func summary(_ json: String) throws -> PipelineSummary {
        try JSONDecoder().decode(PipelineSummary.self, from: Data(json.utf8))
    }

    private func resolve(_ summary: PipelineSummary) -> SubtitleVariant {
        ProjectSubtitle.resolve(
            availability: .ready, pipelineState: .completedPartial(summary: summary),
            isStopping: false, addingCount: nil, copy: nil, importBatch: nil,
            lastRunAt: nil, missingCount: 0, unanalysedCount: 0)
    }

    private func text(_ variant: SubtitleVariant) -> String? {
        SidebarSubtitleText.text(for: variant, availability: .ready, progress: nil, i18n: english())
    }

    @Test func lostRecordingsReadAsHowMuchWasAnalysed() throws {
        let s = try summary(#"""
            {"transcripts": {"attempted": 8, "succeeded": 6, "failed": [
              {"session_id": "s7", "cause": {"category": "cloud_fetch", "message": "m"}},
              {"session_id": "s8", "cause": {"category": "whisper", "message": "m"}}]},
             "quotes": {"attempted": 6, "succeeded": 6, "failed": []}}
            """#)
        let variant = resolve(s)
        #expect(variant == .completedPartial(analysed: SessionsAnalysed(done: 6, total: 8)))
        #expect(text(variant) == "6 of 8 sessions analysed")
    }

    @Test func onlyRefusedFilesKeepThePartialHeader() throws {
        // A stray PDF: every session analysed, so a count would read "5 of 5".
        let s = try summary(#"""
            {"ingest": {"attempted": 6, "succeeded": 5, "failed": [
              {"source_file": "notes.pdf", "cause": {"category": "unusable_input", "message": "m"}}]},
             "transcripts": {"attempted": 5, "succeeded": 5, "failed": []},
             "quotes": {"attempted": 5, "succeeded": 5, "failed": []}}
            """#)
        let variant = resolve(s)
        #expect(variant == .completedPartial(analysed: nil))
        #expect(text(variant) == "Partial completion")
    }

    @Test func oneSessionIsSingular() {
        #expect(text(.completedPartial(analysed: SessionsAnalysed(done: 0, total: 1)))
                == "0 of 1 session analysed")
    }
}
