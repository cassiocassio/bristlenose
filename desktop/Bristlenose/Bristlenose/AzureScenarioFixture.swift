import Foundation

/// What the Azure settings pane draws while a Diagnostics fixture is active: a
/// proposed-wording failure (`AzureSettingsFixture`, for height budgets) or a
/// shipped scenario (`AzureScenarioFixture`, for seeing what researchers see).
/// Exists in every build so the pane compiles the same way; only Debug builds
/// can create a `.shipped` one.
enum AzurePaneFixture: Equatable {
    case proposed(AzureSettingsFixture)
    case shipped(AzureScenarioVerdict)

    var id: String {
        switch self {
        case .proposed(let f): f.rawValue
        case .shipped(let v): v.id
        }
    }

    var status: ProviderStatus {
        switch self {
        case .proposed: .invalid
        case .shipped(let v): v.status
        }
    }

    var failure: FailureMessage? {
        switch self {
        case .proposed(let f): f.failure
        case .shipped(let v): v.failure
        }
    }

    /// The configuration the pane's fields show instead of the saved one, so a
    /// screenshot never carries the real endpoint, deployment or key.
    var shownConfig: AzureScenarioVerdict? {
        if case .shipped(let v) = self { return v }
        return nil
    }
}

/// A shipped scenario's configuration and the verdict the real validator gave
/// for it. Never written to settings, the Keychain or the verdict cache.
struct AzureScenarioVerdict: Equatable {
    let id: String
    let endpoint: String
    let deployment: String
    let apiVersion: String
    /// Shown as a masked placeholder, never a real key.
    let hasKey: Bool
    let status: ProviderStatus
    let failure: FailureMessage?
}

#if DEBUG
/// Diagnostics ▸ Azure Scenarios: every Azure scenario on the scenario page
/// (`docs/mockups/azure-scenarios.html`), drawn by the real app with the
/// **shipped** wording, for screenshots.
///
/// Unlike `AzureSettingsFixture` (proposed wording, a height budget), nothing
/// here supplies a sentence. Each settings case is a fake configuration plus the
/// answer Azure really sent for it (bodies from
/// `tests/fixtures/azure-transition-contract.json`), and the verdict comes from
/// `LLMValidator.validate` itself, answered through `ScenarioURLProtocol`
/// instead of the network, then through `resolveStatus` and the pane's own
/// cache-fallback rule. Each run case is the run's recorded output (the CLI
/// capture against the fake Azure, `experiments/azure-scenarios/`) passed
/// through the same functions a failed run goes through. Debug builds only.
enum AzureScenarioFixture: String, CaseIterable, Identifiable {
    case online
    case keyRejected
    case deploymentNotFound
    case wrongURLPasted
    case throttled
    case outage
    case redirect
    case unreachable
    case noEndpoint
    case noDeployment
    case noKey
    case offlineWithGoodCheck
    case relaunchAfterRejection
    case timedOut
    case noScheme
    case httpEndpoint

    var id: String { rawValue }

    var menuTitle: String {
        switch self {
        case .online: "Everything Right"
        case .keyRejected: "Key Rejected (401)"
        case .deploymentNotFound: "Deployment Name Wrong (404 DeploymentNotFound)"
        case .wrongURLPasted: "Wrong URL Pasted (Generic 404)"
        case .throttled: "Azure Throttling (429)"
        case .outage: "Azure Outage (503)"
        case .redirect: "Endpoint Redirects (302)"
        case .unreachable: "Nothing Answers"
        case .noEndpoint: "Key Saved, No Endpoint"
        case .noDeployment: "Key and Endpoint, No Deployment"
        case .noKey: "No Key"
        case .offlineWithGoodCheck: "Offline, Last Check Was Good"
        case .relaunchAfterRejection: "Relaunch After a Rejected Check"
        case .timedOut: "Check Timed Out"
        case .noScheme: "Endpoint Without https://"
        case .httpEndpoint: "An http:// Endpoint"
        }
    }

    static let resource = "https://contoso-research.openai.azure.com"
    static let deploymentName = "research-gpt41mini"

    var endpoint: String {
        switch self {
        case .noEndpoint: ""
        case .wrongURLPasted:
            Self.resource + "/openai/deployments/" + Self.deploymentName
                + "/chat/completions?api-version=2024-10-21"
        case .noScheme: "contoso-research.openai.azure.com"
        case .httpEndpoint: "http://contoso-research.openai.azure.com"
        case .unreachable: "https://contoso-reserach.openai.azure.com"
        default: Self.resource
        }
    }

    var deployment: String { self == .noDeployment ? "" : Self.deploymentName }
    var hasKey: Bool { self != .noKey }

    enum Answer {
        case http(Int, String)
        case network(URLError.Code)
        /// The validator decides without asking (missing field, bad scheme).
        case none
    }

    var answer: Answer {
        switch self {
        case .online: .http(200, Body.okChat)
        case .keyRejected: .http(401, Body.unauthorized)
        case .deploymentNotFound: .http(404, Body.deploymentNotFound)
        case .wrongURLPasted, .httpEndpoint: .http(404, Body.generic404)
        case .throttled: .http(429, Body.throttled)
        case .outage: .http(503, Body.outage)
        case .redirect: .http(302, "")
        case .unreachable: .network(.cannotFindHost)
        case .offlineWithGoodCheck, .relaunchAfterRejection: .network(.notConnectedToInternet)
        case .timedOut: .network(.timedOut)
        case .noEndpoint, .noDeployment, .noKey, .noScheme: .none
        }
    }

    /// The verdict cached from an earlier check, for the cases about one.
    var cached: LLMValidator.CachedVerdict? {
        switch self {
        case .offlineWithGoodCheck: .ok
        case .relaunchAfterRejection: .invalid
        default: nil
        }
    }

    /// Recorded Azure bodies (`tests/fixtures/azure-transition-contract.json`).
    enum Body {
        static let okChat = #"{"choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}], "id": "chatcmpl-fake", "object": "chat.completion", "model": "gpt-4.1-mini"}"#
        static let unauthorized = #"{"error": {"code": "401", "message": "Access denied due to invalid subscription key or wrong API endpoint. Make sure to provide a valid key for an active subscription and use a correct regional API endpoint for your resource."}}"#
        static let deploymentNotFound = #"{"error": {"type": "invalid_request_error", "code": "DeploymentNotFound", "message": "The API deployment for this resource does not exist. If you created the deployment within the last 5 minutes, please wait a moment and try again."}}"#
        static let generic404 = #"{"error": {"code": "404", "message": "Resource not found"}}"#
        static let throttled = #"{"error": {"code": "429", "message": "Rate limit is exceeded."}}"#
        static let outage = #"{"error": {"code": "503", "message": "Service unavailable"}}"#
    }

    /// Run the real validator against this scenario's answer.
    func verdict() async -> AzureScenarioVerdict {
        let config = LLMValidator.AzureConfig(
            endpoint: endpoint, apiVersion: "2024-10-21", deployment: deployment)
        ScenarioURLProtocol.answer = answer
        let session = LLMValidator.makeSession(protocolClasses: [ScenarioURLProtocol.self])
        let (observed, error) = await LLMValidator.validate(
            provider: .azure, key: hasKey ? "scenario-fixture-key-not-real" : "",
            azureConfig: config, session: session)
        let shown = LLMValidator.resolveStatus(observed: observed, cached: cached)
        // The pane's cache-fallback rule (`LLMSettingsView.kickOffValidation`).
        let failure: FailureMessage? = shown != observed
            ? (cached == .invalid ? .keyed("desktop.llmSettings.revalidating") : error)
            : error
        return AzureScenarioVerdict(
            id: rawValue, endpoint: endpoint, deployment: deployment,
            apiVersion: config.apiVersion, hasKey: hasKey, status: shown, failure: failure)
    }

    @MainActor static func present(_ fixture: AzureScenarioFixture) {
        Task { @MainActor in
            let verdict = await fixture.verdict()
            pending = (verdict, Date())
            NotificationCenter.default.post(name: .azureScenarioFixture, object: verdict)
            SettingsWindow.shared.show(pane: .llm)
        }
    }

    @MainActor private static var pending: (verdict: AzureScenarioVerdict, at: Date)?

    @MainActor static func takePending(now: Date = Date()) -> AzureScenarioVerdict? {
        defer { pending = nil }
        guard let pending, now.timeIntervalSince(pending.at) <= AzureSettingsFixture.pendingLifetime
        else { return nil }
        return pending.verdict
    }
}

/// Answers the validator's one request with the scenario's recorded answer.
final class ScenarioURLProtocol: URLProtocol {
    private static let lock = NSLock()
    nonisolated(unsafe) private static var _answer: AzureScenarioFixture.Answer = .none
    static var answer: AzureScenarioFixture.Answer {
        get { lock.withLock { _answer } }
        set { lock.withLock { _answer = newValue } }
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        switch Self.answer {
        case .http(let status, let body):
            let response = HTTPURLResponse(
                url: request.url!, statusCode: status, httpVersion: "HTTP/1.1",
                headerFields: ["Content-Type": "application/json"])!
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: Data(body.utf8))
            client?.urlProtocolDidFinishLoading(self)
        case .network(let code):
            client?.urlProtocol(self, didFailWithError: URLError(code))
        case .none:
            client?.urlProtocol(self, didFailWithError: URLError(.badURL))
        }
    }

    override func stopLoading() {}
}

/// Diagnostics ▸ Debug ▸ Diagnostic Fixtures, the Azure run scenarios: a project
/// row in the state a failed Azure run leaves it in, from the run's recorded
/// output.
enum AzureRunScenario: String, CaseIterable {
    case refusedBadKey = "azure_run_refused_bad_key"
    case refusedDeployment = "azure_run_refused_deployment"
    case keyRevokedMidRun = "azure_run_key_revoked_mid_run"

    /// A refusal at the pre-run check exits before the events log opens, so the
    /// Mac sorts it from the output (`categoriseFailure`); a refusal mid-run
    /// leaves a `run_failed` cause, read as `deriveFailureState` reads it.
    @MainActor var state: PipelineState {
        switch self {
        case .refusedBadKey, .refusedDeployment:
            let lines = (self == .refusedBadKey ? Self.badKeyOutput : Self.deploymentOutput)
                .components(separatedBy: "\n")
            let category = PipelineRunner.categoriseFailure(
                lines: lines, exitStatus: 1, provider: .azure)
            return .failed(FailureMessage.failure(for: category, provider: .azure),
                           category: category)
        case .keyRevokedMidRun:
            // The recorded cause: {"category": "auth", "code": "401",
            // "message": "All topic segmentation calls failed.", "provider": "azure"}
            return .failed(
                PipelineRunner.failureSummary(
                    category: .auth, message: "All topic segmentation calls failed.",
                    provider: .azure),
                category: .auth)
        }
    }

    private static let setupLines = """
        Checking your setup
         ✓ FFmpeg          8.1.1 (/opt/homebrew/bin/ffmpeg)
         ✓ FFprobe         /opt/homebrew/bin/ffprobe
         ✓ Transcription   mlx-whisper 0.4.3 (MLX)
         — Whisper model   large-v3-turbo not cached (~1.6 GB download on first run)
        """

    private static let rejectedTail = """
         ✓ Network         contoso-research.openai.azure.com reachable (10ms)
         — PII redaction   off (use --redact-pii to enable)
         ✓ Disk space      48 GB free
         ✓ Serve mode      6 deps installed

        Your Azure OpenAI credentials were rejected. Check:

          1. API key is correct (Azure portal > your OpenAI resource > Keys)
          2. Endpoint URL matches your resource (https://NAME.openai.azure.com/)
          3. Deployment name exists in your resource

        Then re-run: bristlenose configure azure
        """

    static let badKeyOutput = setupLines + "\n"
        + " ✗ API key         Azure OpenAI rejected (401 Unauthorized)\n" + rejectedTail
    static let deploymentOutput = setupLines + "\n"
        + " ✗ API key         Azure OpenAI rejected (Deployment 'research-gpt41mini' not \nfound)\n"
        + rejectedTail
}
#endif

extension Notification.Name {
    /// Posted by Diagnostics ▸ Azure Scenarios; `object` is an `AzureScenarioVerdict`.
    static let azureScenarioFixture = Notification.Name("bristlenoseAzureScenarioFixture")
}
