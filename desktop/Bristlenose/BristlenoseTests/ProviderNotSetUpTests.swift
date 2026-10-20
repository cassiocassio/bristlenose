import Foundation
import Testing
@testable import Bristlenose

/// A run with no AI provider set up — found by the 20 Oct 2026 guest walk
/// (`experiments/guest-walk/README.md`, "A product finding") on 0.42.0 with no
/// provider configured: adding an interview started a run that could only fail,
/// the failure was classified `unknown` ("Something went wrong during
/// analysis."), and its only advice was the CLI's `bristlenose configure claude`.
///
/// Three halves, each pinned here: the app does not spawn a run it has no key
/// for (`start`), the classifier names the cause when a run gets past that
/// (`categoriseFailure`), and the popover offers the fix (`needsProvider`).
@MainActor
@Suite("Provider not set up")
struct ProviderNotSetUpTests {

    // MARK: - The refusal before a spawn

    @Test("start() refuses, without spawning, when there is no key to inject")
    func startRefusesWithoutAKey() {
        let runner = PipelineRunner(
            notificationCenter: NotificationCenter(),
            hasConsent: { true },
            keyReadiness: { .missing(provider: "anthropic") }
        )
        let project = Project(id: UUID(), name: "New Project", path: "/nonexistent/new-project")
        runner.start(project: project)
        guard case .failed(_, let category) = runner.state[project.id] else {
            Issue.record("expected .failed, got \(String(describing: runner.state[project.id]))")
            return
        }
        #expect(category == .providerNotSetUp)
        #expect(runner.state[project.id]?.needsProvider == true)
    }

    @Test("A keyless provider (Ollama) is not refused")
    func keylessIsNotRefused() {
        #expect(PipelineRunner.providerRefusal(.keyless(provider: "local"), chosen: .ollama) == nil)
        #expect(PipelineRunner.providerRefusal(
            .present(provider: "openai", key: "sk-test"), chosen: .chatGPT) == nil)
    }

    @Test("Nothing chosen says 'no AI provider'; a choice is named")
    func refusalNamesOnlyAChosenProvider() {
        // A fresh install with consent accepted and no key: `activeProvider` is
        // unset, and Python's default (Claude) is not something they picked.
        guard case .failed(let generic, _) = PipelineRunner.providerRefusal(
            .missing(provider: "anthropic"), chosen: nil
        ) else { Issue.record("expected a refusal"); return }
        #expect(generic.key == "desktop.pipeline.failure.providerNotSetUpGeneric")
        #expect(generic.english == "No AI provider is set up yet.")

        guard case .failed(let named, _) = PipelineRunner.providerRefusal(
            .missing(provider: "openai"), chosen: .chatGPT
        ) else { Issue.record("expected a refusal"); return }
        #expect(named.key == "desktop.pipeline.failure.providerNotSetUp")
        #expect(named.vars == ["provider": "ChatGPT"])
    }

    // MARK: - The one key decision, shared with the overlay

    @Test("Readiness follows the Keychain for the provider the overlay would use")
    func readinessMatchesTheOverlay() {
        withIsolatedDefaults { defaults in
            let store = InMemoryKeychain()
            // Nothing chosen: the overlay falls back to Python's default.
            #expect(BristlenoseShared.apiKeyReadiness(using: store, defaults: defaults)
                    == .missing(provider: BristlenoseShared.pythonDefaultProvider))
            store.set(provider: "anthropic", value: "sk-ant-test")
            #expect(BristlenoseShared.apiKeyReadiness(using: store, defaults: defaults)
                    == .present(provider: "anthropic", key: "sk-ant-test"))
            defaults.set("openai", forKey: "activeProvider")
            #expect(BristlenoseShared.apiKeyReadiness(using: store, defaults: defaults)
                    == .missing(provider: "openai"))
            defaults.set("local", forKey: "activeProvider")
            #expect(BristlenoseShared.apiKeyReadiness(using: store, defaults: defaults)
                    == .keyless(provider: "local"))
        }
    }

    // MARK: - The classifier, for a run that got past the gate

    /// The output of `bristlenose run` spawned as the app spawns it
    /// (`_BRISTLENOSE_HOSTED_BY_DESKTOP=1`, no key), captured at 2407fedc on
    /// 20 Oct 2026. The FFmpeg row is shown as passing: the app bundles it, and
    /// the capture's ✗ came from the shell's stripped PATH.
    static let noKeyOutput = """
    Bristlenose v0.42.0 · 2407fedc-dirty · Claude · Apple Silicon (unknown model) ·
    MLX

    Checking your setup
     ✓ FFmpeg          8.0 (bundled)
     ✓ Transcription   mlx-whisper 0.4.3 (MLX)
     — Whisper model   large-v3-turbo not cached (~1.6 GB download on first run)
     ✗ API key         No Anthropic API key
     ✓ Network         api.anthropic.com reachable (149ms)
     — PII redaction   off (use --redact-pii to enable)
     ✓ Disk space      134 GB free
     ✓ Serve mode      6 deps installed

    bristlenose needs an API key to analyse transcripts.
    Get a Claude API key from console.anthropic.com, then:

      bristlenose configure claude

    This stores your key securely in your macOS Keychain.

    To use ChatGPT instead:  bristlenose run <input> --llm chatgpt
    To only transcribe:      bristlenose transcribe <input>
    """.components(separatedBy: "\n")

    @Test("The setup check's missing-key output is 'not set up', not 'unknown'")
    func missingKeyIsClassified() {
        #expect(PipelineRunner.categoriseFailure(lines: Self.noKeyOutput, exitStatus: 1)
                == .providerNotSetUp)
    }

    @Test("Each provider's missing-key and Azure's missing-config rows")
    func everyProvidersMissingRow() {
        for detail in [
            "No OpenAI API key", "No Azure OpenAI API key", "No Google Gemini API key",
            "No Azure OpenAI endpoint", "No Azure OpenAI deployment name",
        ] {
            let lines = ["Checking your setup", " ✗ API key         \(detail)"]
            #expect(PipelineRunner.categoriseFailure(lines: lines, exitStatus: 1)
                    == .providerNotSetUp, "\(detail)")
        }
    }

    @Test("A healthy key row never reads as 'not set up'")
    func healthyKeyRowIsNotMatched() {
        let lines = [
            "Checking your setup",
            " ✓ API key         Claude (sk-ant-…abcd) from Keychain",
            "Error: disk full while writing transcripts",
        ]
        #expect(PipelineRunner.categoriseFailure(lines: lines, exitStatus: 1) == .disk)
    }

    private func withIsolatedDefaults(_ body: (UserDefaults) -> Void) {
        let name = "ProviderNotSetUpTests-\(UUID().uuidString)"
        let suite = UserDefaults(suiteName: name)!
        defer { suite.removePersistentDomain(forName: name) }
        body(suite)
    }
}
