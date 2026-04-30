import CryptoKit
import Foundation
import os

/// Round-trip credential validation for LLM providers.
///
/// Hits each provider's cheapest documented auth-check endpoint via URLSession
/// and maps the HTTP response to a `ProviderStatus`. Native Swift (not via the
/// sidecar) because Settings can be opened before any project is loaded.
enum LLMValidator {

    private static let logger = Logger(subsystem: "app.bristlenose", category: "llm-validator")

    /// Per-provider extra config the validator may need (currently Azure only).
    struct AzureConfig {
        var endpoint: String
        var apiVersion: String
    }

    /// Validate a credential and return the resulting status plus a short
    /// human-readable error string (for tooltip / inline display) when the
    /// status is anything other than `.online`.
    static func validate(
        provider: LLMProvider,
        key: String,
        azureConfig: AzureConfig? = nil,
        ollamaURL: String? = nil
    ) async -> (ProviderStatus, String?) {
        // Ollama is keyless — URL presence + reachability is the contract.
        if provider == .ollama {
            return await probeOllama(urlString: ollamaURL ?? "")
        }
        let trimmed = key.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            return (.notSetUp, nil)
        }
        if provider == .azure {
            let endpoint = azureConfig?.endpoint
                .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            if endpoint.isEmpty {
                // Started-but-incomplete: user has entered a key, the
                // endpoint is missing. Orange .unavailable is more honest
                // than grey .notSetUp — they've done work, they're not done.
                return (.unavailable, "Add the Azure endpoint URL to finish setting this up.")
            }
            // Reject schemeless input early with a friendly message rather
            // than letting URLSession fail with "unsupported URL scheme."
            if let scheme = URLComponents(string: endpoint)?.scheme?.lowercased(),
               scheme == "https" || scheme == "http"
            {
                // ok
            } else {
                return (
                    .invalid,
                    "Azure endpoint must start with https:// — got \"\(endpoint.prefix(40))…\""
                )
            }
        }

        let request: URLRequest
        do {
            request = try buildRequest(
                provider: provider, key: trimmed, azureConfig: azureConfig)
        } catch {
            logger.warning(
                "validate(\(provider.rawValue, privacy: .public)) build error: \(error.localizedDescription, privacy: .public)")
            return (.unavailable, "Could not build request")
        }

        do {
            let (_, response) = try await urlSession.data(for: request)
            guard let http = response as? HTTPURLResponse else {
                return (.unavailable, "No HTTP response")
            }
            return classify(provider: provider, status: http.statusCode)
        } catch let urlErr as URLError {
            // URLError code is fine to log publicly (it's an integer code).
            // localizedDescription can in principle echo the failing URL —
            // and Gemini puts the API key in the URL query string — so it's
            // marked private and never bubbled up into user-visible text.
            logger.info(
                "validate(\(provider.rawValue, privacy: .public)) URLError \(urlErr.code.rawValue, privacy: .public)")
            switch urlErr.code {
            case .timedOut:
                return (.unavailable, "Request timed out — \(provider.displayName) didn't respond in 5s.")
            case .notConnectedToInternet, .networkConnectionLost:
                return (.unavailable, "No network connection. Your key is fine — we just can't check it right now.")
            case .cannotFindHost, .cannotConnectToHost, .dnsLookupFailed:
                return (.unavailable, "Could not reach \(provider.displayName). Check your network connection.")
            default:
                return (.unavailable, "Network error reaching \(provider.displayName).")
            }
        } catch {
            logger.error(
                "validate(\(provider.rawValue, privacy: .public)) error: \(error.localizedDescription, privacy: .private)")
            return (.unavailable, "Network error reaching \(provider.displayName).")
        }
    }

    // MARK: - Internals

    private static let urlSession: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 5
        config.timeoutIntervalForResource = 5
        config.waitsForConnectivity = false
        return URLSession(configuration: config)
    }()

    private static func buildRequest(
        provider: LLMProvider,
        key: String,
        azureConfig: AzureConfig?
    ) throws -> URLRequest {
        switch provider {
        case .claude:
            // Cheapest documented auth check: POST /v1/messages with max_tokens=1.
            // Bad key returns 401 before billing; good key consumes < $0.0001.
            guard let url = URL(string: "https://api.anthropic.com/v1/messages")
            else { throw URLError(.badURL) }
            var req = URLRequest(url: url)
            req.httpMethod = "POST"
            req.setValue(key, forHTTPHeaderField: "x-api-key")
            req.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            let body: [String: Any] = [
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1,
                "messages": [["role": "user", "content": "."]],
            ]
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
            return req

        case .chatGPT:
            // GET /v1/models is free and 401s on bad keys.
            guard let url = URL(string: "https://api.openai.com/v1/models")
            else { throw URLError(.badURL) }
            var req = URLRequest(url: url)
            req.httpMethod = "GET"
            req.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
            return req

        case .azure:
            guard let cfg = azureConfig else { throw URLError(.badURL) }
            let trimmedEndpoint = cfg.endpoint
                .trimmingCharacters(in: .whitespacesAndNewlines)
                .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            let apiVersion = cfg.apiVersion.isEmpty ? "2024-10-21" : cfg.apiVersion
            guard
                let url = URL(
                    string:
                        "\(trimmedEndpoint)/openai/deployments?api-version=\(apiVersion)"
                )
            else { throw URLError(.badURL) }
            var req = URLRequest(url: url)
            req.httpMethod = "GET"
            req.setValue(key, forHTTPHeaderField: "api-key")
            return req

        case .gemini:
            guard
                let escaped = key.addingPercentEncoding(
                    withAllowedCharacters: .urlQueryAllowed),
                let url = URL(
                    string:
                        "https://generativelanguage.googleapis.com/v1beta/models?key=\(escaped)"
                )
            else { throw URLError(.badURL) }
            var req = URLRequest(url: url)
            req.httpMethod = "GET"
            return req

        case .ollama:
            // Out of scope for Beat 3 — LLMSettingsView treats Ollama as a
            // URL-presence check today. Beat 3b will surface the richer probe
            // from bristlenose/ollama.py.
            throw URLError(.badURL)
        }
    }

    /// Map an HTTP status code to a `ProviderStatus` + user-visible
    /// error string. Pure function — exposed `internal` so unit tests
    /// can drive it without spinning up URLSession.
    static func classify(
        provider: LLMProvider,
        status: Int
    ) -> (ProviderStatus, String?) {
        // Messages are deliberately phrased to make 401 vs 402 unmistakable
        // — a user staring at "key rejected" will delete and regenerate a
        // perfectly good key if the actual problem was unpaid credit, so the
        // 402 path explicitly says "your key is fine".
        switch status {
        case 200...299:
            return (.online, nil)
        case 401, 403:
            return (
                .invalid,
                "\(provider.displayName) rejected this key (\(status)). It may have been deleted, rotated, or never had access — generate a new key in your provider dashboard."
            )
        case 402:
            return (
                .unavailable,
                "\(provider.displayName) is out of credits (402). Your key is fine — top up your account to use it."
            )
        case 429:
            return (
                .unavailable,
                "\(provider.displayName) is rate-limited right now (429). Your key is fine — try again in a minute."
            )
        case 404 where provider == .azure:
            // Azure 404 = wrong endpoint URL or wrong deployment name —
            // not a key problem. Routed to .invalid so the radio is blocked
            // until the user fixes the config; message points them at the
            // endpoint, not the key.
            return (
                .invalid,
                "Azure endpoint or deployment not found (404). The key is fine — check the endpoint URL and deployment name."
            )
        case 400..<500 where provider == .claude:
            // Anthropic auth-checks before payload parsing, so any 4xx that
            // isn't 401/403/402/429 means the key passed auth but the request
            // was malformed (e.g. our hardcoded haiku model got deprecated).
            // Treat as `.online` so this validator survives Anthropic model
            // deprecations without breaking every user on a stale binary.
            // The "auth before payload" pattern is institutional across
            // well-designed APIs; the specific status code returned for a
            // good-key/bad-payload is fragile, but the order isn't.
            logger.info(
                "validate(\(provider.rawValue, privacy: .public)) treating HTTP \(status, privacy: .public) as auth-passed (Anthropic auth-before-payload)"
            )
            return (.online, nil)
        default:
            return (.unavailable, "\(provider.displayName) returned HTTP \(status).")
        }
    }

    // MARK: - Ollama probe

    /// HTTP-only Ollama detection. Mirrors `bristlenose/ollama.py`'s
    /// `validate_local_endpoint` but stays inside the Mac shell so this
    /// doesn't depend on the sidecar running. Beat 3b will deepen this
    /// (install method probe, model auto-pull, etc.); for now we want the
    /// dot to reflect "Ollama is reachable + has at least one model" so
    /// the user doesn't activate Ollama and then hit a confusing
    /// localhost:11434 connection error at pipeline-run time.
    private static func probeOllama(urlString: String) async -> (ProviderStatus, String?) {
        let trimmed = urlString
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        if trimmed.isEmpty {
            return (.notSetUp, "Set the Ollama server URL.")
        }
        // Match bristlenose/ollama.py: strip trailing /v1 if present so we
        // can hit /api/tags directly.
        let base = trimmed.hasSuffix("/v1")
            ? String(trimmed.dropLast(3))
            : trimmed
        guard let url = URL(string: "\(base)/api/tags") else {
            return (.invalid, "Ollama URL is not valid.")
        }
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        do {
            let (data, response) = try await urlSession.data(for: req)
            guard let http = response as? HTTPURLResponse else {
                return (.unavailable, "Ollama: no HTTP response.")
            }
            guard (200...299).contains(http.statusCode) else {
                return (
                    .unavailable,
                    "Ollama returned HTTP \(http.statusCode). Is the server running?"
                )
            }
            // Parse models list — empty list means Ollama is up but has no
            // models pulled, which would also fail at run time.
            if let payload = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let models = payload["models"] as? [[String: Any]],
               !models.isEmpty
            {
                return (.online, nil)
            }
            return (
                .unavailable,
                "Ollama is reachable but has no models pulled. Run `ollama pull llama3.2:3b` to add one."
            )
        } catch let urlErr as URLError {
            logger.info(
                "probeOllama URLError \(urlErr.code.rawValue, privacy: .public)")
            return (
                .unavailable,
                "Ollama not reachable at \(base). Start it with `ollama serve` or open the Ollama app."
            )
        } catch {
            return (.unavailable, "Ollama probe failed.")
        }
    }

    // MARK: - Verdict cache
    //
    // Persists the last definitive validation result (`.online` / `.invalid`)
    // per provider, keyed by a hash of the credential. Lets the Settings UI
    // show last-known truth offline and survive an app relaunch without a
    // network round-trip. Transient states (`.unavailable`, `.checking`,
    // `.notSetUp`) never write to the cache — they carry no information
    // about the credential's validity. The cache is the reason the user can
    // activate a previously-valid Claude key at a café with no Wi-Fi.
    //
    // **Why UserDefaults, not Keychain.** The cache stores a 64-bit SHA-256
    // prefix of the credential, plus a verdict ("ok" / "invalid"), plus a
    // timestamp. None of that is the credential itself — that lives in
    // Keychain via `KeychainHelper`. The 8-byte hash is a stable identity
    // ("is this the same key we last validated?"), preimage-resistant at
    // the relevant scale (4 providers × one user lifetime ≈ 4 hashes ever),
    // not a secret. Keychain would be over-engineering for this. The
    // exposure: a process running as the user can read the plist and
    // fingerprint which providers the user has configured + when keys
    // were last rotated. Documented as such in the security audit.

    /// UserDefaults instance backing the verdict cache. Production uses
    /// `.standard`; tests substitute an isolated suite via
    /// `LLMValidator.verdictStore = UserDefaults(suiteName: ...)!`.
    static var verdictStore: UserDefaults = .standard

    enum CachedVerdict: String {
        case ok
        case invalid

        /// Map a cached verdict back to a UI status.
        var status: ProviderStatus {
            switch self {
            case .ok: return .online
            case .invalid: return .invalid
            }
        }
    }

    /// Bundle of "what does the cache know about this key right now."
    struct CacheEntry {
        let verdict: CachedVerdict
        let lastCheckedAt: Date
    }

    /// Last definitive verdict for `key` under `provider`, or `nil` if
    /// the cache is empty or the stored hash doesn't match this key
    /// (i.e. the user pasted a different key since the last check).
    static func cachedVerdict(provider: LLMProvider, key: String) -> CachedVerdict? {
        cachedEntry(provider: provider, key: key)?.verdict
    }

    /// Full cache entry including timestamp — used by the TTL gate in
    /// `revalidateAll` and the "Last verified" UI surfacing.
    static func cachedEntry(provider: LLMProvider, key: String) -> CacheEntry? {
        let trimmed = key.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        let defaults = verdictStore
        guard let cachedHash = defaults.string(forKey: hashKey(provider)),
              cachedHash == hash(trimmed),
              let raw = defaults.string(forKey: verdictKey(provider)),
              let verdict = CachedVerdict(rawValue: raw)
        else { return nil }
        let lastChecked: Date
        if let isoString = defaults.string(forKey: timestampKey(provider)),
           let parsed = ISO8601DateFormatter().date(from: isoString)
        {
            lastChecked = parsed
        } else {
            // Pre-existing cache entries written before the timestamp
            // field landed — treat as ancient so the TTL gate triggers
            // a fresh validation rather than trusting forever.
            lastChecked = .distantPast
        }
        return CacheEntry(verdict: verdict, lastCheckedAt: lastChecked)
    }

    /// True if the cache has a definitive verdict for this exact key
    /// AND that verdict is younger than `ttl` seconds. Used to skip
    /// background revalidation when the user is opening Settings rapidly
    /// (e.g. tweaking temperature in another tab).
    static func cacheIsFresh(
        provider: LLMProvider, key: String, ttl: TimeInterval
    ) -> Bool {
        guard let entry = cachedEntry(provider: provider, key: key) else { return false }
        return Date().timeIntervalSince(entry.lastCheckedAt) < ttl
    }

    /// Persist the verdict for `key` under `provider`. No-op for non-definitive
    /// statuses — `.unavailable` from a transient network failure must not
    /// overwrite a previous `.online` verdict.
    static func recordVerdict(provider: LLMProvider, key: String, status: ProviderStatus) {
        let trimmed = key.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        let verdict: CachedVerdict?
        switch status {
        case .online: verdict = .ok
        case .invalid: verdict = .invalid
        default: verdict = nil
        }
        guard let verdict else { return }
        let defaults = verdictStore
        defaults.set(hash(trimmed), forKey: hashKey(provider))
        defaults.set(verdict.rawValue, forKey: verdictKey(provider))
        defaults.set(ISO8601DateFormatter().string(from: Date()), forKey: timestampKey(provider))
    }

    /// Drop the cache for a provider — called when the key is cleared.
    static func clearCache(provider: LLMProvider) {
        let defaults = verdictStore
        defaults.removeObject(forKey: hashKey(provider))
        defaults.removeObject(forKey: verdictKey(provider))
        defaults.removeObject(forKey: timestampKey(provider))
    }

    private static func hashKey(_ provider: LLMProvider) -> String {
        "llmValidation_\(provider.rawValue)_keyHash"
    }

    private static func verdictKey(_ provider: LLMProvider) -> String {
        "llmValidation_\(provider.rawValue)_status"
    }

    private static func timestampKey(_ provider: LLMProvider) -> String {
        "llmValidation_\(provider.rawValue)_lastCheckedAt"
    }

    /// Truncated SHA-256 — we only need a stable identity for "is this the
    /// same key we last validated?" Storing 16 hex chars (8 bytes) is plenty
    /// for that (single-entry-per-provider cache, not a hash table) and
    /// avoids putting the full digest in UserDefaults.
    private static func hash(_ key: String) -> String {
        let digest = SHA256.hash(data: Data(key.utf8))
        return digest.prefix(8).map { String(format: "%02x", $0) }.joined()
    }

    // MARK: - Model download

    /// Aggregate progress across pull layers. Ollama's `/api/pull` emits
    /// per-layer totals; the caller sees a single 0…1 ratio so the
    /// progress bar doesn't reset between layers.
    struct PullProgress {
        let completedBytes: Int64
        let totalBytes: Int64
        let statusLine: String

        var ratio: Double {
            guard totalBytes > 0 else { return 0 }
            return min(1, Double(completedBytes) / Double(totalBytes))
        }
    }

    /// Stream `POST /api/pull` and report aggregated progress.
    /// Layers download serially in Ollama; we sum their totals and
    /// emit (sumCompleted, sumOfSeenTotals, currentStatusLine) per
    /// JSON line received. Cancellation propagates via task cancel.
    /// Throws on HTTP error or stream failure.
    static func pullModel(
        tag: String,
        baseURL: URL,
        onProgress: @escaping @MainActor (PullProgress) -> Void
    ) async throws {
        // Strip trailing /v1 if user pasted the OpenAI-compat URL.
        let trimmed = baseURL.absoluteString
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let base = trimmed.hasSuffix("/v1") ? String(trimmed.dropLast(3)) : trimmed
        guard let pullURL = URL(string: "\(base)/api/pull") else {
            throw URLError(.badURL)
        }
        var req = URLRequest(url: pullURL)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = ["model": tag, "stream": true]
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        // No timeout for the resource — model pulls take minutes.
        let session = URLSession(configuration: .ephemeral)
        defer { session.finishTasksAndInvalidate() }

        let (bytes, response) = try await session.bytes(for: req)
        guard let http = response as? HTTPURLResponse,
              (200..<300).contains(http.statusCode)
        else {
            throw URLError(.badServerResponse)
        }

        // Per-digest layer accumulation: layers come in serially with
        // their own `total`/`completed` fields. Track the maximum
        // `completed` we've seen for each digest, then sum across.
        var seen: [String: (completed: Int64, total: Int64)] = [:]
        var lastStatus = "Starting download…"
        var lineBuffer = ""
        for try await byte in bytes {
            try Task.checkCancellation()
            if byte == 0x0A {  // newline
                if !lineBuffer.isEmpty {
                    if let event = try? JSONDecoder().decode(
                        PullEvent.self,
                        from: Data(lineBuffer.utf8))
                    {
                        if let status = event.status {
                            lastStatus = status
                        }
                        if let digest = event.digest, let total = event.total {
                            let completed = event.completed ?? 0
                            seen[digest] = (completed, total)
                        }
                        let sumCompleted = seen.values.reduce(0) { $0 + $1.completed }
                        let sumTotal = seen.values.reduce(0) { $0 + $1.total }
                        let snapshot = PullProgress(
                            completedBytes: sumCompleted,
                            totalBytes: sumTotal,
                            statusLine: lastStatus)
                        await MainActor.run { onProgress(snapshot) }
                    }
                    lineBuffer.removeAll(keepingCapacity: true)
                }
            } else {
                lineBuffer.unicodeScalars.append(Unicode.Scalar(byte))
            }
            // Defensive cap — abort on absurdly long lines.
            if lineBuffer.utf8.count > 65_536 {
                throw URLError(.cannotParseResponse)
            }
        }
    }

    /// Subset of fields we read from each /api/pull stream line.
    private struct PullEvent: Decodable {
        let status: String?
        let digest: String?
        let total: Int64?
        let completed: Int64?
    }
}
