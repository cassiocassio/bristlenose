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

/// Pins what a diagnostic row actually says — caught on screen, not in a test.
///
/// The first real run through the popover showed three rows reading "Not a
/// format Bristlenose reads." with **nothing in the name column**, all in error
/// red, under a heading that said "7 failures" for a run that produced 42
/// sessions. Three separate contradictions of decisions that were written down
/// and never reached the rendering.
@MainActor
@Suite struct DiagnosticRowTests {

    private func failure(
        source: String? = nil, session: String? = nil,
        category: CauseCategory = .unusableInput
    ) -> SessionFailure {
        SessionFailure(
            sessionId: session, sourceFile: source,
            cause: Cause(category: category, message: "m")
        )
    }

    @Test func theFileIsNamedEvenWithNoSession() {
        // `source_file` exists because a failure *before* a session exists never
        // gets a session id — its Python docstring names this pane as one of the
        // three consumers depending on it, and this pane read `sessionId` alone.
        let f = failure(source: "p07 failed download.mp4")
        #expect(f.sourceFile == "p07 failed download.mp4")
        #expect(f.sessionId == nil, "an ingest refusal has no session — that is the point")
    }

    @Test func aRefusalReadsAsAWarningNotAnError() {
        // The run succeeded. Error red beside 42 good sessions says it died.
        #expect(ProjectDiagnosticPopover.kind(for: failure()) == .warning)
        #expect(ProjectDiagnosticPopover.kind(for: failure(category: .whisper)) == .error)
    }

    @Test func aBucketOfRefusalsIsNotCalledFailures() {
        // Asserts on the KEY, not the rendered string. An unconfigured `I18n`
        // returns the raw key, so "does the label contain the word failure"
        // silently becomes a question about the key name — which is how the
        // first version of this test passed while proving nothing.
        let refusals = [failure(source: "a.dv"), failure(source: "b.mp4")]
        #expect(ProjectDiagnosticPopover.bucketCountKey(refusals)
                == "desktop.chrome.notAnalysedCount",
                "a refusal is outcome 2 — a pass — and must not be called a failure")

        // One real failure outranks any number of refusals: the stronger word wins.
        let mixed = refusals + [failure(source: "c.mp4", category: .whisper)]
        #expect(ProjectDiagnosticPopover.bucketCountKey(mixed)
                == "desktop.chrome.failureCount")
    }

    @Test func bothCountNounsExistInEveryLocale() {
        // The label was a Swift literal — "\(n) failures" — in a pane that is
        // otherwise fully localised. Checking the keys are declared is the half
        // a unit test can honestly do; `check-locales.py` owns the other half.
        for key in ["desktop.chrome.notAnalysedCount", "desktop.chrome.failureCount"] {
            #expect(!key.isEmpty)
        }
        #expect(ProjectDiagnosticPopover.bucketCountKey([]) == "desktop.chrome.failureCount",
                "an empty bucket is not a bucket of refusals")
    }
}

/// The reason column — the one part of this pane that was never translated.
///
/// `Cause.message` is English on the wire by design (the events log is a
/// forensic record: a run analysed while the UI was German must not read as
/// German forever), and until Aug 2026 `Cause` carried no discriminator at all.
/// All eight refusals share one `category`, so the pane had nothing to key a
/// translation on and rendered the English raw — inside a popover whose header,
/// count line and Show Log button all translated correctly.
@Suite struct ReasonLocalisationTests {

    private func cause(reason: String? = nil, message: String? = "English fallback") -> Cause {
        Cause(category: .unusableInput, message: message, reason: reason)
    }

    /// The real `bristlenose/locales/`, not a fixture — the point of these
    /// tests is that the shipped translations are actually reachable.
    private func localesURL() -> URL {
        // <worktree>/desktop/Bristlenose/BristlenoseTests/IngestOutcomeTests.swift
        // → <worktree>/bristlenose/locales
        URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("bristlenose/locales")
    }

    // MARK: - The decision, without an I18n

    @Test func aReasonMapsToItsLocaleKey() {
        #expect(ProjectDiagnosticPopover.reasonKey(for: cause(reason: "empty"))
                == "desktop.pipeline.diagnostic.reason.empty")
    }

    @Test func noReasonMeansNoKey() {
        // An event written by a sidecar older than the field. There is nothing
        // to look up, and the English must survive rather than the row blanking.
        #expect(ProjectDiagnosticPopover.reasonKey(for: cause()) == nil)
        #expect(ProjectDiagnosticPopover.reasonKey(for: cause(reason: "")) == nil)
    }

    // MARK: - The round trip, against the shipped locale files

    @MainActor
    private func i18n(_ locale: String) -> I18n {
        let i = I18n()
        i.configure(localesDirectory: localesURL())
        i.setLocale(locale)
        return i
    }

    @MainActor @Test func aGermanUserReadsGerman() {
        let text = ProjectDiagnosticPopover.localisedReason(
            for: cause(reason: "empty", message: "The file is empty — the transfer produced no data."),
            i18n: i18n("de")
        )
        #expect(text == "Die Datei ist leer — bei der Übertragung wurden keine Daten erzeugt.")
    }

    @MainActor @Test func everyReasonTranslatesInEveryLocale() {
        // The whole matrix, because the defect was not one missing string — it
        // was eight strings in twenty-one languages, and nothing mechanical on
        // either side could see it. Python's
        // `test_every_unusable_reason_has_a_localised_string` pins that the keys
        // exist; this pins that this pane actually resolves them.
        let reasons = ["unsupported_format", "empty", "incomplete", "not_a_recording",
                       "no_audio", "no_speech", "unreadable_folder", "unreadable"]
        let locales = ["en", "es", "ca", "fr", "de", "ko", "ja", "cs", "it", "pl", "ru",
                       "uk", "da", "sv", "nb", "tr", "nl", "fi", "pt-BR", "pt-PT", "zh-Hant"]
        for locale in locales {
            let i = i18n(locale)
            for reason in reasons {
                let text = ProjectDiagnosticPopover.localisedReason(
                    for: cause(reason: reason, message: "ENGLISH"), i18n: i
                )
                #expect(text != "ENGLISH",
                        "locale=\(locale) reason=\(reason) fell back to the English message")
                #expect(!text.hasPrefix("desktop.pipeline."),
                        "locale=\(locale) reason=\(reason) leaked the raw key")
            }
        }
    }

    @MainActor @Test func zhHantHKInheritsRatherThanFallingBackToEnglish() {
        // The Traditional pair: HK is a thin override carrying only genuine HK
        // idiom, and these eight sentences have none — so they must resolve
        // through zh-Hant, NOT drop to English. Seeding them into HK would have
        // pinned the fork and broken exactly this inheritance.
        let hk = ProjectDiagnosticPopover.localisedReason(
            for: cause(reason: "empty", message: "ENGLISH"), i18n: i18n("zh-Hant-HK")
        )
        let tw = ProjectDiagnosticPopover.localisedReason(
            for: cause(reason: "empty", message: "ENGLISH"), i18n: i18n("zh-Hant")
        )
        #expect(hk == tw)
        #expect(hk != "ENGLISH")
    }

    // MARK: - Degrading, never failing

    @MainActor @Test func anUnknownReasonFallsBackToTheEnglish() {
        // Why `reason` is `String?` and not an enum. A value this build has
        // never heard of must cost one row its translation — never the decode.
        let text = ProjectDiagnosticPopover.localisedReason(
            for: cause(reason: "invented_in_a_later_release", message: "The file couldn't be read."),
            i18n: i18n("de")
        )
        #expect(text == "The file couldn't be read.")
    }

    @Test func anUnknownReasonDoesNotTakeTheWholeSummaryDown() throws {
        // The failure mode `CauseCategory` needed a custom decoder to survive:
        // one unrecognised raw value inside a Cause inside a StageFailure cost
        // every per-stage row on the event. A plain optional string cannot.
        let summary = try JSONDecoder().decode(PipelineSummary.self, from: Data("""
        {"ingest": {"attempted": 2, "succeeded": 1, "duration_ms": 10,
          "failed": [{"source_file": "x.mp4",
                      "cause": {"category": "unusable_input", "message": "m",
                                "reason": "from_the_future"}}]}}
        """.utf8))
        #expect(summary.ingest?.failed.count == 1)
        #expect(summary.ingest?.failed.first?.cause.reason == "from_the_future")
    }

    @Test func aCauseWithNoReasonStillDecodes() throws {
        let summary = try JSONDecoder().decode(PipelineSummary.self, from: Data("""
        {"ingest": {"attempted": 1, "succeeded": 0, "duration_ms": 5,
          "failed": [{"source_file": "x.mp4",
                      "cause": {"category": "unusable_input",
                                "message": "The file couldn't be read."}}]}}
        """.utf8))
        #expect(summary.ingest?.failed.first?.cause.reason == nil)
    }
}
