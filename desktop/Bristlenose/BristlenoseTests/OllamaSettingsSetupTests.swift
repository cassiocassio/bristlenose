import Foundation
import SwiftUI
import Testing
@testable import Bristlenose

// The Ollama setup moved from the AI disclosure to Settings ▸ LLM Provider (owner,
// 27 Nov 2026, app-privtext v3 C). These pin its mechanics: "Use …" switches the
// provider before it sets anything up, the pill follows Whisper's visibility rule,
// the window refits per stage and never per byte, and the picker dims by memory.

@MainActor
@Suite struct OllamaSettingsSetupTests {

    private func scratchDefaults() -> UserDefaults {
        let name = "OllamaSettingsSetupTests-\(UUID().uuidString)"
        let d = UserDefaults(suiteName: name)!
        d.removePersistentDomain(forName: name)
        return d
    }

    // MARK: - "Use …": the switch, then the setup

    @Test func useSwitchesTheProviderBeforeSettingUp() {
        let d = scratchDefaults()
        d.set(LLMProvider.claude.rawValue, forKey: "activeProvider")
        d.set("claude-sonnet", forKey: "llmModel")
        let model = OllamaDownloadModel(defaults: d, notifications: NotificationCenter())

        model.useModel(tag: "gemma4:e4b")
        // Synchronous, before any routing task has run: the switch is already made.
        #expect(d.string(forKey: "activeProvider") == LLMProvider.ollama.rawValue)
        #expect(d.string(forKey: "llmModel_local") == "gemma4:e4b")
        #expect(d.string(forKey: "llmModel") == "gemma4:e4b")
        #expect(model.currentTag == "gemma4:e4b")
        model.cancel()
    }

    /// Opening the picker only probes: nothing is switched until "Use …".
    @Test func openingThePickerSwitchesNothing() {
        let d = scratchDefaults()
        d.set(LLMProvider.claude.rawValue, forKey: "activeProvider")
        d.set("claude-sonnet", forKey: "llmModel")
        let model = OllamaDownloadModel(defaults: d, notifications: NotificationCenter())

        model.start(tag: "gemma4:e4b")
        #expect(model.phase == .choosingModel)
        #expect(d.string(forKey: "activeProvider") == LLMProvider.claude.rawValue)
        #expect(d.string(forKey: "llmModel") == "claude-sonnet")
        model.cancel()
        #expect(model.phase == .idle)
    }

    // MARK: - The pill: Whisper's rule

    @Test func thePillShowsOnlyWhileDownloadingAndAfterAFailure() {
        let shown: [OllamaDownloadModel.Phase] = [.downloading, .finishing, .failed(.noInternet),
                                                  .failed(.generic("x"))]
        let hidden: [OllamaDownloadModel.Phase] = [.idle, .choosingModel, .needsOllama,
                                                   .waitingForOllama]
        for phase in shown { #expect(OllamaDownloadModel.isPillVisible(phase), "\(phase)") }
        for phase in hidden { #expect(!OllamaDownloadModel.isPillVisible(phase), "\(phase)") }
    }

    // MARK: - The Model card and the window refit

    @Test func theCardShowsEveryStageAfterTheChoiceAndNothingElse() {
        let shown: [OllamaDownloadModel.Phase] = [.needsOllama, .waitingForOllama, .downloading,
                                                  .finishing, .failed(.timedOut)]
        for phase in shown { #expect(OllamaSetupStageView.shows(phase), "\(phase)") }
        #expect(!OllamaSetupStageView.shows(.idle))
        #expect(!OllamaSetupStageView.shows(.choosingModel))
    }

    /// One refit per change of stage: every stage has its own signature, a failure's
    /// cause does not make a new one, and another provider on screen contributes none.
    @Test func theRefitSignatureChangesPerStageOnly() {
        let phases: [OllamaDownloadModel.Phase] = [.idle, .choosingModel, .needsOllama,
                                                   .waitingForOllama, .downloading, .finishing,
                                                   .failed(.noInternet)]
        func sig(_ p: OllamaDownloadModel.Phase, _ total: Bool = false,
                 _ selected: LLMProvider = .ollama) -> String {
            LLMSettingsView.ollamaSetupSignature(selected: selected, phase: p, hasByteTotal: total)
        }
        #expect(Set(phases.map { sig($0) }).count == phases.count)
        #expect(sig(.failed(.noInternet)) == sig(.failed(.timedOut)))
        #expect(sig(.downloading, false, .claude) == "")
        // The byte total arriving changes the card once (spinner → line and bar)…
        #expect(sig(.downloading, true) != sig(.downloading, false))
        // …and means nothing in any other stage.
        #expect(sig(.finishing, true) == sig(.finishing, false))
    }

    // MARK: - Closing the picker

    /// "Use …" then closing the picker (what its onCommit does) must not cancel the
    /// route "Use …" started: the phase is still `.choosingModel` until the probe
    /// returns. Found by review, 27 Nov 2026.
    @Test func closingThePickerAfterUseKeepsTheSetupGoing() {
        let model = OllamaDownloadModel(defaults: scratchDefaults(), notifications: NotificationCenter())
        model.start(tag: "gemma4:e4b")
        model.useModel(tag: "gemma4:e4b")
        model.pickerDismissed()
        #expect(model.phase == .choosingModel)   // the route's probe is still out
        model.cancel()
    }

    @Test func closingThePickerWithoutAChoiceGoesBackToIdle() {
        let model = OllamaDownloadModel(defaults: scratchDefaults(), notifications: NotificationCenter())
        model.start(tag: "gemma4:e4b")
        model.pickerDismissed()
        #expect(model.phase == .idle)
    }

    /// A failure (with its Retry) or "Get Ollama" survives a look at the picker.
    @Test func closingThePickerWithoutAChoiceKeepsAFailureOrGetOllama() {
        let model = OllamaDownloadModel(defaults: scratchDefaults(), notifications: NotificationCenter())
        model.debugApply(.failNoInternet)
        let tag = model.currentTag
        model.start(tag: "llama3.2:3b")
        model.pickerDismissed()
        #expect(model.phase == .failed(.noInternet))
        #expect(model.currentTag == tag)

        model.debugApply(.needsOllama)
        model.start(tag: "llama3.2:3b")
        model.pickerDismissed()
        #expect(model.phase == .needsOllama)
    }

    // MARK: - Another provider made active

    @Test func switchingAwayStopsAWaitButNotADownload() {
        let model = OllamaDownloadModel(defaults: scratchDefaults(), notifications: NotificationCenter())
        model.debugApply(.waiting)
        model.activeProviderChanged(to: LLMProvider.claude.rawValue)
        #expect(model.phase == .idle)

        model.debugApply(.downloadingDeterminate)
        model.activeProviderChanged(to: LLMProvider.claude.rawValue)
        #expect(model.phase == .downloading)

        model.debugApply(.waiting)
        model.activeProviderChanged(to: LLMProvider.ollama.rawValue)
        #expect(model.phase == .waitingForOllama)
        model.cancel()
    }

    /// Re-using the model already set changes nothing, so the serve is not restarted.
    @Test func activatingTheSameModelAgainChangesNothing() {
        let d = scratchDefaults()
        #expect(OllamaDownloadModel.activate(tag: "gemma4:e4b", in: d))
        #expect(!OllamaDownloadModel.activate(tag: "gemma4:e4b", in: d))
        #expect(OllamaDownloadModel.activate(tag: "llama3.2:3b", in: d))
    }

    /// The Model row's button is dimmed while a setup with its own Cancel is running:
    /// opening the picker would restart it.
    @Test func theModelButtonIsLockedOnlyWhileASetupRuns() {
        #expect(LLMSettingsView.ollamaPickerLocked(.waitingForOllama))
        #expect(LLMSettingsView.ollamaPickerLocked(.downloading))
        #expect(LLMSettingsView.ollamaPickerLocked(.finishing))
        #expect(!LLMSettingsView.ollamaPickerLocked(.idle))
        #expect(!LLMSettingsView.ollamaPickerLocked(.needsOllama))
        #expect(!LLMSettingsView.ollamaPickerLocked(.failed(.cantReach)))
    }

    // MARK: - The picker dims by memory

    /// `physicalMemory` for an "8 GB" and a "16 GB" Mac, in decimal GB.
    private let ram8 = 8 * 1.073741824, ram16 = 16 * 1.073741824, ram32 = 32 * 1.073741824

    private func dimmed(_ tag: String, _ ram: Double) -> Bool {
        OllamaModelPicker.isDimmed(OllamaCatalog.model(for: tag)!, ramGB: ram)
    }

    @Test func thePickerDimsWhatThisMacsMemoryCannotRun() {
        #expect(!dimmed("llama3.2:3b", ram8))
        #expect(!dimmed("gemma4:e4b", ram8))
        #expect(dimmed("gemma4:26b", ram8))
        #expect(dimmed("gemma4:31b", ram16))
        #expect(!dimmed("gemma4:26b", ram32))
        #expect(!dimmed("gemma4:31b", ram32))
    }

    // MARK: - The disclosure's footnote

    @Test func theFootnoteKeepsTheLinkAsItsOwnRunAndTheItalic() {
        let url = URL(string: "https://bristlenose.app/privacy.html")!
        let text = AIConsentView.footnote(
            agentAccess: "Edits *are* sent.", responsibility: "Tell participants.",
            hosts: "Models come from Apple.", link: "Privacy Policy", destination: url, locale: "en")
        #expect(String(text.characters) == "Edits are sent. Tell participants. Models come from Apple. Privacy Policy")
        let linked = text.runs.filter { $0.link != nil }.map { String(text[$0.range].characters) }
        #expect(linked == ["Privacy Policy"])
        let italic = text.runs.filter { $0.inlinePresentationIntent?.contains(.emphasized) == true }
            .map { String(text[$0.range].characters) }
        #expect(italic == ["are"])
    }

    /// Markdown in a translation cannot make a link: only the policy link is one.
    @Test func aTranslationCannotMakeALink() {
        let url = URL(string: "https://bristlenose.app/privacy.html")!
        let text = AIConsentView.footnote(
            agentAccess: "See [here](https://example.com) *now*.", responsibility: "R.",
            hosts: "H.", link: "Privacy Policy", destination: url, locale: "en")
        let links = text.runs.compactMap { $0.link }
        #expect(links == [url])
    }

    @Test func japaneseAndChineseJoinSentencesWithoutASpace() {
        #expect(AIConsentView.sentenceJoiner(for: "ja") == "")
        #expect(AIConsentView.sentenceJoiner(for: "zh-Hant") == "")
        #expect(AIConsentView.sentenceJoiner(for: "zh-Hant-HK") == "")
        #expect(AIConsentView.sentenceJoiner(for: "en") == " ")
        #expect(AIConsentView.sentenceJoiner(for: "ko") == " ")
    }
}
