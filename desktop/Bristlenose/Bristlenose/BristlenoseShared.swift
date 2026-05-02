import Foundation

/// Shared helpers used by both ServeManager and PipelineRunner.
///
/// Keeps the Python-subprocess concerns (binary discovery, ANSI stripping)
/// in one place so the two runners stay in lockstep.
enum BristlenoseShared {

    /// Strip ANSI escape sequences, OSC sequences (BEL- and ST-terminated),
    /// 2-byte ESC sequences, and C0 control characters (except `\t`, `\n`,
    /// `\r`). Intentionally broad so "Copy error details" cannot ferry a
    /// terminal-control payload (cursor moves, iTerm2 OSC 1337 inline
    /// images, etc.) into the user's clipboard. Reviewed Apr 2026 after
    /// security finding #2 on `port-v01-ingestion`.
    static let ansiRegex: NSRegularExpression = {
        let pattern = [
            "\\x1b\\[[0-?]*[ -/]*[@-~]",            // CSI: any final byte
            "\\x1b\\][^\\x07\\x1b]*(?:\\x07|\\x1b\\\\)", // OSC: BEL- or ST-terminated
            "\\x1b[@-Z\\\\-_]",                     // 2-byte ESC
            "[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f]" // C0 controls except \t \n \r
        ].joined(separator: "|")
        // swiftlint:disable:next force_try
        return try! NSRegularExpression(pattern: pattern, options: [])
    }()

    /// Apply ANSI stripping to a single line.
    static func stripANSI(_ line: String) -> String {
        ansiRegex.stringByReplacingMatches(
            in: line,
            range: NSRange(line.startIndex..., in: line),
            withTemplate: ""
        )
    }

    /// Build the minimal environment for a `bristlenose` subprocess.
    /// Inherits only the handful of vars the CLI needs; avoids leaking
    /// credentials, DYLD_* vars, Xcode debug vars, etc. API keys are read
    /// from Keychain by Python directly — no env var needed for them.
    static func buildChildEnvironment() -> [String: String] {
        var env: [String: String] = [:]
        let parentEnv = ProcessInfo.processInfo.environment
        for key in ["PATH", "HOME", "TMPDIR", "USER", "SHELL",
                     "LANG", "LC_ALL", "LC_CTYPE", "VIRTUAL_ENV"] {
            if let val = parentEnv[key] { env[key] = val }
        }
        overlayPreferences(into: &env)
        return env
    }

    /// Overlay UserDefaults preferences as environment variables. Only sets
    /// vars that differ from defaults to avoid overriding `.env` or Keychain
    /// values unnecessarily. Used for both `bristlenose serve` and
    /// `bristlenose run`.
    static func overlayPreferences(into env: inout [String: String]) {
        let defaults = UserDefaults.standard

        if let provider = defaults.string(forKey: "activeProvider") {
            env["BRISTLENOSE_LLM_PROVIDER"] = provider
        }
        if let model = defaults.string(forKey: "llmModel") {
            env["BRISTLENOSE_LLM_MODEL"] = model
        }
        if defaults.object(forKey: "llmTemperature") != nil {
            env["BRISTLENOSE_LLM_TEMPERATURE"] = String(defaults.double(forKey: "llmTemperature"))
        }
        if defaults.object(forKey: "llmConcurrency") != nil {
            env["BRISTLENOSE_LLM_CONCURRENCY"] = String(Int(defaults.double(forKey: "llmConcurrency")))
        }
        if let backend = defaults.string(forKey: "whisperBackend"), backend != "auto" {
            env["BRISTLENOSE_WHISPER_BACKEND"] = backend
        }
        if let model = defaults.string(forKey: "whisperModel") {
            env["BRISTLENOSE_WHISPER_MODEL"] = model
        }
        if let lang = defaults.string(forKey: "language"), lang != "en" {
            env["BRISTLENOSE_WHISPER_LANGUAGE"] = lang
        }
        if let endpoint = defaults.string(forKey: "azureEndpoint"), !endpoint.isEmpty {
            env["BRISTLENOSE_AZURE_ENDPOINT"] = endpoint
        }
        if let deployment = defaults.string(forKey: "azureDeployment"), !deployment.isEmpty {
            env["BRISTLENOSE_AZURE_DEPLOYMENT"] = deployment
        }
        if let apiVersion = defaults.string(forKey: "azureAPIVersion"), !apiVersion.isEmpty {
            env["BRISTLENOSE_AZURE_API_VERSION"] = apiVersion
        }
        // Ollama — hardwired to localhost in the desktop GUI. Parent-env
        // override only (CLI / CI). See LLMSettingsView.hardwiredOllamaURL.
        if let envURL = ProcessInfo.processInfo.environment["BRISTLENOSE_LOCAL_URL"],
           !envURL.isEmpty {
            env["BRISTLENOSE_LOCAL_URL"] = envURL
        }
    }
}
