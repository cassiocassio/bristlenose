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

    private func variant(_ state: PipelineState?, availability: ProjectAvailability = .ready,
                         serveFailed: Bool = false, missing: Int = 0) -> SubtitleVariant {
        ProjectSubtitle.resolve(
            availability: availability, pipelineState: state,
            isStopping: false, addingCount: nil, copy: nil, importBatch: nil,
            serveFailedToStart: serveFailed,
            lastRunAt: nil, missingCount: missing, unanalysedCount: 0)
    }

    private func rowText(_ state: PipelineState?, locale: String = "en",
                         availability: ProjectAvailability = .ready,
                         serveFailed: Bool = false, missing: Int = 0) -> String? {
        let v = variant(state, availability: availability, serveFailed: serveFailed, missing: missing)
        return SidebarSubtitleText.text(for: v, availability: availability,
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
            (.quota, "Rate limited"),
            (.whisper, "Transcription failed"),
            (.modelUnavailable, "Model unavailable"),
        ]
        for (category, label) in cases {
            #expect(rowText(.failed(.passthrough("raw"), category: category)) == label)
        }
    }

    /// The labels the owner approved from `docs/mockups/sidebar-failure-labels.html`
    /// (15 Nov 2026), where the category's own label was vague.
    @Test func vagueCategoriesGetTheirRowLabel() {
        let cases: [(PipelineFailureCategory, String)] = [
            (.apiRequest, "Request rejected"),
            (.providerNotSetUp, "No AI provider set up"),
            (.disk, "Disk full"),
            (.missingInput, "No interviews found"),
            (.missingBinary, "FFmpeg missing"),
            (.unusableInput, "Files not analysed"),
            (.userSignal, "Stopped"),
        ]
        for (category, label) in cases {
            #expect(rowText(.failed(.passthrough("raw"), category: category)) == label, "\(category)")
        }
    }

    /// Credit, reachability and outage are fixed at the provider, so they name it when known.
    @Test func providerCausesNameTheProvider() {
        let cases: [(PipelineFailureCategory, String, String)] = [
            (.outOfCredit, "Gemini out of credit", "Out of credit"),
            (.network, "Couldn’t reach Gemini", "No connection"),
            (.apiServer, "Gemini unavailable", "Provider unavailable"),
        ]
        for (category, named, generic) in cases {
            #expect(rowText(.failed(pythonSaid("raw", provider: .gemini), category: category)) == named)
            #expect(rowText(.failed(.passthrough("raw"), category: category)) == generic)
        }
    }

    @Test func momentsWithNoCategorySayWhatHappened() {
        #expect(rowText(.failed(EventLogReader.stranded, category: .unknown)) == "Interrupted")
        let launch = FailureMessage.keyed(FailureMessage.launchFailedKey, vars: ["reason": "x"])
        #expect(rowText(.failed(launch, category: .unknown)) == "Couldn’t start")
        #expect(rowText(.stopped(stagesComplete: [], interrupted: true)) == "Interrupted")
        #expect(rowText(.stopped(stagesComplete: [])) == "Stopped")
    }

    /// Not failures: "Already analysed" is information, a stop is the researcher's,
    /// and a run the app or the power cut short is a warning Resume fixes.
    @Test func glyphsFollowWhatTheResearcherMustDo() {
        #expect(variant(.failed(.passthrough("x"), category: .outputExists)).glyphKind == .info)
        #expect(variant(.failed(.passthrough("x"), category: .userSignal)).glyphKind == nil)
        #expect(variant(.failed(EventLogReader.stranded, category: .unknown)).glyphKind == .warning)
        #expect(variant(.stopped(stagesComplete: [], interrupted: true)).glyphKind == .warning)
        #expect(variant(.stopped(stagesComplete: [])).glyphKind == nil)
        #expect(variant(.failed(.passthrough("x"), category: .disk)).glyphKind == .error)
    }

    /// Audit row 27: a report server that can't start had no row line at all.
    @Test func aServerThatCannotStartSaysCouldntOpen() {
        #expect(rowText(.ready(Date()), serveFailed: true) == "Couldn’t open")
        #expect(rowText(nil, serveFailed: true) == "Couldn’t open")
        #expect(variant(nil, serveFailed: true).glyphKind == .error)
        // No popover to open: the pane says why and offers Retry.
        #expect(variant(nil, serveFailed: true).glyphAction == .none)
        // A run in flight and a failed run keep the line.
        #expect(variant(.running, serveFailed: true) == .running)
        #expect(rowText(.failed(.passthrough("x"), category: .disk), serveFailed: true) == "Disk full")
    }

    @Test func folderLinesSayWhatIsWrong() {
        #expect(rowText(.unreachable(reason: .unreadable)) == "No access to folder")
        #expect(rowText(.unreachable(reason: .damaged)) == "Project file damaged")
        #expect(rowText(nil, availability: .cantFind(reason: .unmountedVolume(name: "Interviews SSD")))
                == "Interviews SSD not connected")
        #expect(rowText(nil, availability: .cantFind(reason: .moved)) == "Folder not found")
        #expect(rowText(nil, missing: 2) == "2 files missing")
        #expect(rowText(nil, missing: 1) == "1 file missing")
        #expect(SidebarSubtitleText.completedPartialRowText(nil, i18n: i18n("en")) == "Some steps failed")
        // The popover headline keeps "Partial completion", above its list.
        #expect(SidebarSubtitleText.completedPartialText(nil, i18n: i18n("en")) == "Partial completion")
    }

    @Test func anUnknownCauseStillReadsRunFailed() {
        #expect(rowText(.failed(.passthrough("Something odd"), category: .unknown)) == "Run failed")
    }

    @Test func theLabelFollowsTheLanguageShowingNow() {
        let state = PipelineState.failed(pythonSaid("bad key", provider: .gemini), category: .auth)
        #expect(rowText(state, locale: "de") == "Gemini-Schlüssel abgelehnt")
    }

    /// No category label may render as a raw key or a placeholder, in any
    /// locale, and none may blow far past the ~22-character row budget in
    /// English (a provider's name is the researcher's own length: "Couldn’t
    /// reach Azure OpenAI" is 27, so the budget is checked with Gemini).
    @Test func everyCategoryHasARealLabel() {
        for locale in ["en", "de", "ja", "ru"] {
            for provider in [LLMProvider.gemini, .azure, nil] {
                for category in PipelineFailureCategory.allCases {
                    let text = rowText(.failed(pythonSaid("raw", provider: provider), category: category),
                                       locale: locale) ?? ""
                    #expect(!text.hasPrefix("desktop."), "\(locale) \(category): \(text)")
                    #expect(!text.contains("{{"), "\(locale) \(category): \(text)")
                    if locale == "en", provider != .azure {
                        #expect(text.count <= 26, "\(category): \(text)")
                    }
                }
            }
        }
    }
}
