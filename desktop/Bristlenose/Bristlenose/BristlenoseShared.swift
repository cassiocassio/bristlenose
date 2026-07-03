import Foundation
import OSLog

/// Logger for shared subprocess concerns. Distinct category from ServeManager's
/// `serve` logger so credential/env injection from the *run* path is filed
/// under `subprocess`, not falsely under `serve`, in Console.app.
private let log = Logger(subsystem: "app.bristlenose", category: "subprocess")

/// Shared helpers used by both ServeManager and PipelineRunner.
///
/// Keeps the Python-subprocess concerns (binary discovery, ANSI stripping,
/// environment assembly, key redaction) in one place so the two runners stay
/// in lockstep.
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

    /// SSL/TLS environment overrides for the bundled sidecar's Python OpenSSL.
    ///
    /// PyInstaller's bundled Python has compile-time OpenSSL defaults pointing
    /// at the build machine's Homebrew paths (`/opt/homebrew/etc/openssl@3/
    /// openssl.cnf` + `/opt/homebrew/etc/ca-certificates/cert.pem`). Under
    /// macOS App Sandbox those paths are blocked → silent TLS init failure →
    /// every outbound HTTPS call (Anthropic, HuggingFace, OpenAI) errors out
    /// before stage 5 even reads its cache. See
    /// `docs/private/sandbox-violations-A1c.md` row 4.
    ///
    /// Fix: point Python at certifi's CA bundle (shipped by PyInstaller at
    /// `_internal/certifi/cacert.pem` next to the binary) and at `/dev/null`
    /// for `OPENSSL_CONF` so OpenSSL doesn't probe the missing system config.
    ///
    /// Returns an empty dict for non-bundled modes — dev sidecar / external
    /// both run outside the app bundle, against whatever OpenSSL their host
    /// Python was linked against.
    static func sslEnvironment(for mode: SidecarMode) -> [String: String] {
        guard case let .bundled(binaryURL) = mode else { return [:] }
        let certifiDir = binaryURL
            .deletingLastPathComponent()
            .appendingPathComponent("_internal/certifi")
        let cacert = certifiDir.appendingPathComponent("cacert.pem").path
        return [
            "SSL_CERT_FILE": cacert,
            "SSL_CERT_DIR": certifiDir.path,
            "REQUESTS_CA_BUNDLE": cacert,
            "OPENSSL_CONF": "/dev/null"
        ]
    }

    /// Bundled FFmpeg/ffprobe paths for the sandboxed sidecar.
    ///
    /// Under App Sandbox the sidecar inherits a stripped PATH
    /// (`/usr/bin:/bin:/usr/sbin:/sbin`), so Python's `shutil.which("ffmpeg")`
    /// can't find the bundled binaries even though they live next to the
    /// sidecar dir at `Contents/Resources/{ffmpeg,ffprobe}`. Set explicit
    /// env vars and let `bristlenose.utils.bundled_binary.bundled_binary_path`
    /// pick them up.
    ///
    /// Returns empty for non-bundled modes — CLI/dev-sidecar paths use
    /// the user's installed FFmpeg via PATH.
    static func bundledBinaryEnvironment(for mode: SidecarMode) -> [String: String] {
        guard case let .bundled(binaryURL) = mode else { return [:] }
        // binaryURL = .../Contents/Resources/bristlenose-sidecar/bristlenose-sidecar
        // ffmpeg/ffprobe live one level up at .../Contents/Resources/{ffmpeg,ffprobe}
        let resourcesDir = binaryURL
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        return [
            "BRISTLENOSE_FFMPEG": resourcesDir.appendingPathComponent("ffmpeg").path,
            "BRISTLENOSE_FFPROBE": resourcesDir.appendingPathComponent("ffprobe").path
        ]
    }

    /// Build the minimal base environment for a `bristlenose` subprocess.
    /// Inherits only the handful of vars the CLI needs; avoids leaking
    /// DYLD_* vars, Xcode debug vars, etc. Applies UserDefaults preferences.
    ///
    /// Does NOT inject TLS, bundled-binary, or API-key vars — use
    /// `childEnvironment(for:)` for the complete, spawn-ready environment.
    /// This base is the building block the factory wraps.
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

    /// Build the COMPLETE environment for a desktop-spawned `bristlenose`
    /// subprocess (serve or run). Single source of truth for every env concern
    /// a spawn site needs, so the two spawn sites can't drift:
    ///   1. minimal var allowlist + UserDefaults preferences (buildChildEnvironment)
    ///   2. `_BRISTLENOSE_HOSTED_BY_DESKTOP` parent-death handshake
    ///   3. TLS cert paths for the bundled OpenSSL (sslEnvironment)
    ///   4. bundled FFmpeg/ffprobe paths (bundledBinaryEnvironment)
    ///   5. the active provider's API key (overlayAPIKeys)
    ///
    /// Both `ServeManager.start` and `PipelineRunner.start` route through here.
    /// The run path previously hand-rolled this block and forgot step 5, which
    /// broke `bristlenose run` under App Sandbox (Python can't read Keychain
    /// itself). Adding a spawn site = one call here, not five lines to remember.
    ///
    /// - Parameter mode: resolved sidecar mode (bundled / dev-sidecar).
    /// - Parameter store: Keychain-abstracted store (`KeychainHelper.liveStore`
    ///   in production, `InMemoryKeychain` in tests).
    static func childEnvironment(
        for mode: SidecarMode,
        store: any KeychainStore = KeychainHelper.liveStore
    ) -> [String: String] {
        var env = buildChildEnvironment()
        // Tells the sidecar to install the parent-death watcher (so it
        // self-terminates if this host process dies abnormally, instead of
        // leaving an orphan holding a port). CLI users don't get this — they
        // may legitimately nohup the server.
        env["_BRISTLENOSE_HOSTED_BY_DESKTOP"] = "1"
        // Activate the desktop presentation themes on the served <html>.
        // data-platform="desktop" gates the SF Pro type scale (tokens-desktop.css);
        // without this the native type system ships dark (built-but-unplugged).
        // Colour palette (Appearance ▸ Colour palette) → canonical BRISTLENOSE_PALETTE,
        // which app.py renders as data-color-theme at serve start (no-flash first
        // paint / next-launch default). Defaults to "default" so Edo stays opt-in
        // (app.py would otherwise default desktop → Edo). Live changes ride the
        // setColorPalette bridge (no serve restart); this env is the cold-start seed.
        // Typography (sf/inter) rides overlayPreferences as BRISTLENOSE_TYPOGRAPHY.
        env["BRISTLENOSE_PLATFORM"] = "desktop"
        env["BRISTLENOSE_PALETTE"] = UserDefaults.standard.string(forKey: "palette") ?? "default"
        #if DEBUG
        // Mount the dev API router (/api/dev/*, incl. the Run Inspector) in the
        // sidecar. Distinct from `_BRISTLENOSE_DEV` (which flips the report mount
        // to Vite/HMR — wrong for the bundled sidecar). DEBUG builds only, so the
        // shipped Release app never exposes these endpoints.
        env["_BRISTLENOSE_DEV_ENDPOINTS"] = "1"
        #endif
        for (key, value) in sslEnvironment(for: mode) { env[key] = value }
        for (key, value) in bundledBinaryEnvironment(for: mode) { env[key] = value }
        overlayAPIKeys(into: &env, using: store)
        overlayMiroToken(into: &env, using: store)
        // Cross-seam resolution ledger: describe the provider/model/key decision
        // this host just made so it leads Python's own ledger in the run log.
        // Set last so it observes the same `store`/defaults overlayAPIKeys did.
        env["_BRISTLENOSE_HOST_RESOLUTION_TRACE"] =
            hostResolutionTrace(store: store).joined(separator: "\n")
        return env
    }

    /// Overlay UserDefaults preferences as environment variables. Only sets
    /// vars that differ from defaults to avoid overriding `.env` or Keychain
    /// values unnecessarily. Used for both `bristlenose serve` and
    /// `bristlenose run`.
    /// Resolve the provider/model pair the host will inject, WITHOUT mutating
    /// anything. Single source of truth shared by `overlayPreferences` (which
    /// turns it into env vars) and `hostResolutionTrace` (which describes it in
    /// the cross-seam ledger) so the two can never drift — a divergence here was
    /// exactly the 8 Jun 404 (the trace would have lied about what was injected).
    ///
    /// Returns `(nil, nil)` when no provider is active, so Python defaults both
    /// coherently. Model is non-nil ONLY when provider is — see the orphan-model
    /// hazard below.
    static func resolvedProviderModel(
        defaults: UserDefaults = .standard
    ) -> (provider: String?, model: String?) {
        guard let provider = defaults.string(forKey: "activeProvider") else {
            return (nil, nil)
        }
        // Inject the model that MATCHES the active provider, read from the
        // per-provider `llmModel_<provider>` key (fallback to the provider's
        // built-in default). The global `llmModel` key only tracks the active
        // provider while `syncGlobalModel` runs — a provider revert leaves it
        // stale, so spawning off it produces a provider≠model mismatch (e.g.
        // provider=anthropic + model=gemini-2.5-flash → 404).
        //
        // Critically: only resolve a model when a provider is also set. The old
        // `else if` arm injected the bare global `llmModel` key with NO
        // matching provider — so Python fell back to its *default* provider
        // (anthropic) but ran it against whatever model the global key last
        // held (e.g. gpt-4o left over from a ChatGPT session), producing a
        // cross-provider 404 (`model: gpt-4o` rejected by Anthropic). When
        // `activeProvider` is unset we resolve neither, letting Python default
        // both coherently.
        let model = defaults.string(forKey: "llmModel_\(provider)")
            ?? LLMProvider(rawValue: provider)?.defaultModel
        return (provider, model)
    }

    static func overlayPreferences(
        into env: inout [String: String], defaults: UserDefaults = .standard
    ) {
        let (provider, model) = resolvedProviderModel(defaults: defaults)
        if let provider {
            env["BRISTLENOSE_LLM_PROVIDER"] = provider
        }
        if let model {
            // Ollama execution reads `local_model` (BRISTLENOSE_LOCAL_MODEL) — a
            // SEPARATE config axis from cloud `llm_model` (BRISTLENOSE_LLM_MODEL).
            // See bristlenose/config.py: for the local provider `llm_model` is
            // cosmetic and execution reads `local_model`. Route the resolved
            // model to the axis the active provider actually reads, or the
            // user's Ollama model choice is silently ignored and the pipeline
            // falls back to the `local_model` default (llama3.2:3b).
            if provider == "local" {
                env["BRISTLENOSE_LOCAL_MODEL"] = model
            } else {
                env["BRISTLENOSE_LLM_MODEL"] = model
            }
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
            // UI locale for server-rendered surfaces (e.g. the failed-run
            // status page). The SPA localises client-side via the bridge, but
            // the Python-rendered status page reads BRISTLENOSE_LANG → set_locale.
            env["BRISTLENOSE_LANG"] = lang
        }
        // Typography (Appearance ▸ Typography). Default "sf" is the server's
        // implicit default (no attr → SF Pro), so only inject when the user
        // opted back to Inter — app.py then emits data-typography="inter".
        if let typography = defaults.string(forKey: "typography"), typography != "sf" {
            env["BRISTLENOSE_TYPOGRAPHY"] = typography
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

    /// Python's default `llm_provider` (`bristlenose/config.py`). Mirrored here
    /// because the Swift host must inject the matching API key when no provider
    /// is explicitly active. If the Python default ever changes, grep this
    /// constant and update both sides together.
    static let pythonDefaultProvider = "anthropic"

    /// Fetch the active LLM provider's API key from Keychain and overlay it as a
    /// `BRISTLENOSE_<PROVIDER>_API_KEY` env var on the subprocess environment.
    ///
    /// This is the sandbox-compatible credential path: the Swift host reads
    /// Keychain (Security.framework, no Python dep), the sidecar reads the env
    /// var via pydantic-settings. No `/usr/bin/security` subprocess call needed
    /// by Python, so the sidecar works under App Sandbox without
    /// `keychain-access-groups` or any Security.framework linkage on the
    /// Python side.
    ///
    /// Called from BOTH spawn sites (via `childEnvironment(for:)`): the serve
    /// sidecar and the `bristlenose run` pipeline. Reads `activeProvider` LIVE
    /// at call time (not a captured snapshot) so a mid-session provider switch
    /// picks up the right key on the next spawn.
    ///
    /// Residual risk: env vars are visible to same-UID processes via `ps -E`.
    /// Under that threat model the attacker can also call SecItemCopyMatching
    /// directly, so net attack-surface delta is small. Documented in
    /// `docs/design-desktop-python-runtime.md`.
    ///
    /// - Parameter env: env dict to mutate
    /// - Parameter store: Keychain-abstracted store (`KeychainHelper.liveStore` in
    ///   production, `InMemoryKeychain` in tests)
    static func overlayAPIKeys(
        into env: inout [String: String], using store: any KeychainStore,
        defaults: UserDefaults = .standard
    ) {
        // Scope to the active provider only. Eager fetch of all four cloud
        // keys (sandbox walk #7) caused 3× Keychain prompts the moment a
        // local-only user dropped a project — the loudest possible "I chose
        // local-only" failure. Ollama is keyless: nothing to inject; bail.
        // Miro is not an LLM provider key — it's injected separately by
        // overlayMiroToken (called from childEnvironment), so it's absent here.
        // Nil-case coupling: `overlayPreferences` injects NO
        // `BRISTLENOSE_LLM_PROVIDER` when `activeProvider` is unset, so Python
        // falls back to its own default (`config.py` `llm_provider`). This key
        // fallback MUST match that Python default or we'd inject the wrong
        // provider's key for a defaulted run. Kept as a named constant so a
        // change to either side is greppable across the Swift/Python boundary.
        let active = defaults.string(forKey: "activeProvider")
            ?? Self.pythonDefaultProvider
        let cloudProviders: Set<String> = ["anthropic", "openai", "azure", "google"]
        guard cloudProviders.contains(active) else {
            log.info("active provider=\(active, privacy: .public) is keyless — no API key injection")
            return
        }
        guard let value = store.get(provider: active), !value.isEmpty else {
            log.info("no API key in Keychain for active provider=\(active, privacy: .public)")
            return
        }
        let envKey = "BRISTLENOSE_\(active.uppercased())_API_KEY"
        env[envKey] = value
        log.info("injected API key for active provider=\(active, privacy: .public)")
    }

    /// Overlay the Miro access token (if connected) as
    /// `BRISTLENOSE_MIRO_ACCESS_TOKEN` so the sandboxed sidecar can reach Miro
    /// without a Python Keychain call.
    ///
    /// Parallel to `overlayAPIKeys` but UNCONDITIONAL — Miro is orthogonal to the
    /// active LLM provider, so a token is injected whenever one is in the
    /// Keychain. The Send-to-Miro panel writes it there via the `store-miro-token`
    /// bridge message (`BridgeHandler`); this carries it to the next sidecar
    /// launch. The env var name matches `EnvCredentialStore.ENV_VAR_MAP["miro"]`
    /// in `bristlenose/credentials.py` (read as `BRISTLENOSE_MIRO_ACCESS_TOKEN`).
    static func overlayMiroToken(
        into env: inout [String: String], using store: any KeychainStore
    ) {
        guard let token = store.get(provider: "miro"), !token.isEmpty else { return }
        env["BRISTLENOSE_MIRO_ACCESS_TOKEN"] = token
        log.info("injected Miro access token from Keychain")
    }

    /// Cloud (key-bearing) providers. Single source shared by `overlayAPIKeys`
    /// (decides whether to inject a key) and `hostResolutionTrace` (decides
    /// whether to report key presence vs `keyless`).
    static let cloudProviders: Set<String> = ["anthropic", "openai", "azure", "google"]

    /// Describe the host-side provider/model/key decision as cross-seam ledger
    /// lines, injected via `_BRISTLENOSE_HOST_RESOLUTION_TRACE` so they lead the
    /// Python resolution ledger in `<output>/.bristlenose/bristlenose.log`.
    ///
    /// The 8 Jun 404 lived ENTIRELY on this side of the seam — the wrong
    /// provider/model env vars were injected here, invisible to Python, which
    /// only ever saw the result. These lines make the host's decision legible in
    /// the same log as the LLM call, so a future cross-seam mismatch is one grep,
    /// not a debugger that can't step across the language boundary.
    ///
    /// SECURITY: emits `key=present/absent/keyless` ONLY, never the key value —
    /// these lines ride into bristlenose.log and are `ps -E`-visible on the env
    /// var. Provider and model NAMES are not secret and are emitted in full.
    ///
    /// Pure read (no env mutation), reads `activeProvider` + Keychain LIVE so a
    /// mid-session switch is reflected on the next spawn — matching
    /// `overlayAPIKeys`/`overlayPreferences`, with which it shares
    /// `resolvedProviderModel` and `cloudProviders` to prevent drift.
    static func hostResolutionTrace(
        defaults: UserDefaults = .standard,
        store: any KeychainStore = KeychainHelper.liveStore
    ) -> [String] {
        let (provider, model) = resolvedProviderModel(defaults: defaults)
        // The provider Python will actually use: explicit, else its own default
        // (which the keyless-fallback in overlayAPIKeys mirrors).
        let effectiveProvider = provider ?? Self.pythonDefaultProvider
        let keyState: String
        if Self.cloudProviders.contains(effectiveProvider) {
            if let value = store.get(provider: effectiveProvider), !value.isEmpty {
                keyState = "present"
            } else {
                keyState = "absent"
            }
        } else {
            keyState = "keyless"
        }
        let providerStr = provider.map { "'\($0)'" } ?? "nil"
        let modelStr = model.map { "'\($0)'" } ?? "nil"
        return [
            "llm_resolve | step=host-defaults | "
                + "event=spawn [BristlenoseShared.swift] | "
                + "activeProvider=\(providerStr) | "
                + "effectiveProvider='\(effectiveProvider)' | "
                + "model=\(modelStr) | key=\(keyState)"
        ]
    }

    /// Key-shape redactor — defence against Python-side leakage of LLM API keys
    /// (Uvicorn env dumps on startup errors, pydantic tracebacks that echo a
    /// SecretStr, accidental `print(os.environ)` from a future change). Applied
    /// at BOTH spawn sites' line handlers before output is buffered, because
    /// both now inject the key via `overlayAPIKeys`.
    ///
    /// Covers: Anthropic (`sk-ant-api/sid<NN>-<90+ chars>`), OpenAI (project-scoped
    /// `sk-proj-<48+>` + historical `sk-<48>`), Google (`AIza<35>`).
    ///
    /// Limitations:
    /// - Per-line only. If Python wraps a key across two log lines (e.g. in a
    ///   boxed stack trace) the redactor won't catch the split halves. Inherent
    ///   to line-based processing.
    /// - Azure deliberately NOT covered: 32-char hex false-positives on UUIDs
    ///   and SHA hashes are worse than the residual risk. Pre-beta audit
    ///   tracked in `docs/private/100days.md` §6 Risk → Should.
    /// - Does not catch provider-format changes after this code was written.
    /// - Does not catch misformatted keys the regex doesn't match by shape.
    ///
    /// This is defence in depth, not a substitute for avoiding key logs in the
    /// first place — see `check-logging-hygiene.sh` for the source-level gate.
    static let keyRedactionRegex = try! NSRegularExpression(
        pattern: [
            "sk-ant-(api|sid)[0-9]{2}-[A-Za-z0-9_\\-]{90,}",
            "sk-(proj|None)-[A-Za-z0-9_\\-]{48,}",
            "sk-[A-Za-z0-9]{48}",
            "AIza[A-Za-z0-9_\\-]{35}",
        ].joined(separator: "|"),
        options: []
    )

    /// Apply the key-shape redactor to a string. Exposed for testing.
    static func redactKeys(in line: String) -> String {
        keyRedactionRegex.stringByReplacingMatches(
            in: line,
            range: NSRange(line.startIndex..., in: line),
            withTemplate: "***REDACTED***"
        )
    }
}
