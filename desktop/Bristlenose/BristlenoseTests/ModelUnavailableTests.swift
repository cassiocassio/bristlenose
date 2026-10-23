import Testing
@testable import Bristlenose

/// R102 — a provider retired the model and every analysis read "Provider
/// rejected request". A preflight abort exits before the run's lifecycle opens,
/// so no terminus carries a cause and the row is classified from stdout; these
/// are the lines a sidecar prints for a model the provider doesn't serve.
/// `tests/test_model_unavailable.py` holds the same arm to the preflight's
/// actual English, so a reworded sentence fails there.
@MainActor
@Suite("Model unavailable")
struct ModelUnavailableTests {

    @Test("Each provider's preflight sentence and raw 404 read as model unavailable",
          arguments: [
              "✗ The requested model is not available for your Claude account. Check available models at https://console.anthropic.com/ and either enable the model or set `BRISTLENOSE_LLM_MODEL` to one your account can use.",
              "✗ Azure deployment wasn't found. This is your Azure portal **deployment name**, not a model id.",
              "✗ Gemini denied access to the requested model. Underlying: 404 NOT_FOUND. {'error': {'code': 404}}.",
              "✗ The requested local model isn't pulled. Run `ollama pull <model>` to download it.",
              "✗ Mistral doesn't offer that model to this key.",
              "✗ Claude doesn't offer the model claude-3-opus-20240229.",
              "✗ Ollama doesn't have the model llama9:7b.",
              "Error code: 404 - {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-3-opus-20240229'}}",
              "Error code: 404 - {'error': {'code': 'DeploymentNotFound', 'message': 'The API deployment for this resource does not exist.'}}",
          ])
    func preflightLineIsModelUnavailable(line: String) {
        let lines = ["Checking your setup", line]
        #expect(PipelineRunner.categoriseFailure(lines: lines, exitStatus: 2) == .modelUnavailable)
    }

    @Test("Gemini's 403 and a Whisper warning are not the model",
          arguments: [
              "✗ Gemini denied access to the requested model. Underlying: 403 PERMISSION_DENIED. {}.",
              "whisper: BRISTLENOSE_WHISPER_MODEL set but model not found at /x; downloading",
          ])
    func notTheModel(line: String) {
        #expect(PipelineRunner.categoriseFailure(lines: [line], exitStatus: 2) != .modelUnavailable)
    }

    @Test("The generic preflight sentence still reads as a rejected request")
    func providerSaysStaysApiRequest() {
        let lines = ["✗ Provider says: Error code: 400 - max_tokens: 200000 > 64000."]
        #expect(PipelineRunner.categoriseFailure(lines: lines, exitStatus: 2) == .apiRequest)
    }

    @Test("It names the provider, and has a Generic sibling")
    func namesProvider() {
        let named = FailureMessage.failure(for: .modelUnavailable, provider: .claude)
        #expect(named.key == "desktop.pipeline.failure.modelUnavailable")
        #expect(named.english.hasPrefix("Claude doesn't offer the chosen model."))
        let generic = FailureMessage.failure(for: .modelUnavailable, provider: nil)
        #expect(generic.key == "desktop.pipeline.failure.modelUnavailableGeneric")
        #expect(generic.vars.isEmpty)
    }

    @Test("The wire word decodes on both mirrors")
    func decodesOnBothEnums() {
        #expect(PipelineFailureCategory(rawValue: "model_unavailable") == .modelUnavailable)
        #expect(CauseCategory(rawValue: "model_unavailable") == .modelUnavailable)
        #expect(PipelineFailureCategory.modelUnavailable.labelKey
                == "desktop.pipeline.category.modelUnavailable")
    }
}
