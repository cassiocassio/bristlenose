import Foundation
import Testing
@testable import Bristlenose

/// A failed run's sidebar line names what failed, from its category ("Gemini
/// key rejected", "Out of credit"), and says "Run failed" only when the cause
/// is unknown (owner, 14 Nov 2026). Driven from a `PipelineState` through the
/// resolver and the AppKit cell's text, and read through the real locale files,
/// so a mistyped key renders as a raw key and fails here.
@MainActor
@Suite struct FailedRowTextTests {

    private func i18n(_ locale: String) -> I18n {
        let locales = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()   // BristlenoseTests
            .deletingLastPathComponent()   // Bristlenose (project)
            .deletingLastPathComponent()   // desktop
            .deletingLastPathComponent()   // repo root
            .appendingPathComponent("bristlenose/locales")
        let i18n = I18n()
        i18n.configure(localesDirectory: locales)
        i18n.setLocale(locale)
        return i18n
    }

    private func rowText(_ state: PipelineState, locale: String = "en") -> String? {
        let variant = ProjectSubtitle.resolve(
            availability: .ready, pipelineState: state,
            isStopping: false, addingCount: nil, copy: nil, importBatch: nil,
            lastRunAt: nil, missingCount: 0, unanalysedCount: 0)
        return SidebarSubtitleText.text(for: variant, availability: .ready,
                                        progress: nil, i18n: i18n(locale))
    }

    /// Python's own sentence, as `PipelineRunner` stores it: the usual path.
    private func pythonSaid(_ text: String, provider: LLMProvider?) -> FailureMessage {
        FailureMessage(vars: provider.map { ["provider": $0.displayName] } ?? [:], english: text)
    }

    @Test func aRejectedKeyInPythonsWordsNamesTheProvider() {
        let state = PipelineState.failed(
            pythonSaid("400 API key not valid. Please pass a valid API key.", provider: .gemini),
            category: .auth)
        #expect(rowText(state) == "Gemini key rejected")
    }

    @Test func aRejectedKeyTheAppDerivedNamesTheProvider() {
        let state = PipelineState.failed(.failure(for: .auth, provider: .gemini), category: .auth)
        #expect(rowText(state) == "Gemini key rejected")
    }

    @Test func aRejectedKeyWithNoKnownProviderSaysAPIKey() {
        let state = PipelineState.failed(.passthrough("401 Unauthorized"), category: .auth)
        #expect(rowText(state) == "API key rejected")
    }

    @Test func otherCausesUseTheirCategoryLabel() {
        let cases: [(PipelineFailureCategory, String)] = [
            (.outOfCredit, "Out of credit"),
            (.quota, "Rate limited"),
            (.whisper, "Transcription failed"),
            (.disk, "Not enough disk space"),
        ]
        for (category, label) in cases {
            #expect(rowText(.failed(.passthrough("raw"), category: category)) == label)
        }
    }

    @Test func anUnknownCauseStillReadsRunFailed() {
        #expect(rowText(.failed(.passthrough("Something odd"), category: .unknown)) == "Run failed")
        #expect(rowText(.failed(EventLogReader.stranded, category: .unknown)) == "Run failed")
    }

    @Test func theLabelFollowsTheLanguageShowingNow() {
        let state = PipelineState.failed(pythonSaid("bad key", provider: .gemini), category: .auth)
        #expect(rowText(state, locale: "de") == "Gemini-Schlüssel abgelehnt")
    }

    /// No category label may render as a raw key, a placeholder, or blow far
    /// past the ~22-character row budget in English.
    @Test func everyCategoryHasARealEnglishLabel() {
        for category in PipelineFailureCategory.allCases {
            let text = rowText(.failed(pythonSaid("raw", provider: .azure), category: category)) ?? ""
            #expect(!text.hasPrefix("desktop."), "\(category): \(text)")
            #expect(!text.contains("{{"), "\(category): \(text)")
            #expect(text.count <= 26, "\(category): \(text)")
        }
    }
}
