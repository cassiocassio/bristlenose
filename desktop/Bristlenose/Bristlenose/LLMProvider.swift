import SwiftUI

/// LLM provider definitions for the Settings accounts list.
///
/// Raw values match `BristlenoseSettings.llm_provider` in `bristlenose/config.py`
/// and `KeychainHelper.serviceNames` keys.
enum LLMProvider: String, CaseIterable, Identifiable {
    case claude = "anthropic"
    case chatGPT = "openai"
    case gemini = "google"
    case azure = "azure"
    case ollama = "local"

    var id: String { rawValue }

    /// User-facing product name (not company name — matches CLAUDE.md convention).
    var displayName: String {
        switch self {
        case .claude: "Claude"
        case .chatGPT: "ChatGPT"
        case .gemini: "Gemini"
        case .azure: "Azure OpenAI"
        case .ollama: "Ollama"
        }
    }

    /// SF Symbol fallback for the sidebar list.
    var iconName: String {
        switch self {
        case .claude: "brain.head.profile"
        case .chatGPT: "bubble.left.and.text.bubble.right"
        case .gemini: "sparkles"
        case .azure: "cloud"
        case .ollama: "desktopcomputer"
        }
    }

    /// Asset catalog image name for the monochrome provider logo.
    var iconAssetName: String {
        switch self {
        case .claude: "provider-anthropic"
        case .chatGPT: "provider-openai"
        case .gemini: "provider-google"
        case .azure: "provider-azure"
        case .ollama: "provider-ollama"
        }
    }

    /// Whether this provider requires an API key (stored in Keychain).
    var needsAPIKey: Bool {
        self != .ollama
    }

    /// Keychain provider key, or nil for Ollama.
    var keychainProvider: String? {
        needsAPIKey ? rawValue : nil
    }

    /// Default model for this provider. Ollama default is RAM-aware via
    /// `OllamaCatalog.recommendedTag()` — see end of file.
    var defaultModel: String {
        switch self {
        case .claude: "claude-sonnet-4-20250514"
        case .chatGPT: "gpt-4o"
        case .gemini: "gemini-2.0-flash"
        case .azure: "gpt-4o"
        case .ollama: OllamaCatalog.recommendedTag()
        }
    }

    /// Known models for the picker. "Custom…" is appended by the UI.
    /// Ollama's list comes from the curated catalog (RAM tiers + sizes).
    var availableModels: [String] {
        switch self {
        case .claude: ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001", "claude-opus-4-20250514"]
        case .chatGPT: ["gpt-4o", "gpt-4o-mini"]
        case .gemini: ["gemini-2.0-flash", "gemini-2.5-pro"]
        case .azure: ["gpt-4o", "gpt-4o-mini"]
        case .ollama: OllamaCatalog.curated.map(\.tag)
        }
    }

    /// Helper text shown below the provider detail pane.
    var helperText: String? {
        switch self {
        case .ollama: "Free, runs locally. No API key needed."
        default: nil
        }
    }

    /// User-facing label for a status, with provider-specific overrides.
    /// Ollama swaps "Online" for "Local" — both healthy, but "Local"
    /// names the actual privacy property the user picked Ollama for.
    func statusLabel(for status: ProviderStatus) -> String {
        if self == .ollama && status == .online {
            return "Local"
        }
        return status.label
    }

    /// Label for the "Use this provider" activation toggle.
    /// Cloud providers use the generic phrasing — they're already named
    /// in the sidebar row above. Ollama gets a custom label that names
    /// the local-only property, since "Use this provider" undersells the
    /// reason a user would pick it.
    var activationToggleLabel: String {
        switch self {
        case .ollama: "Use the local Ollama model"
        default: "Use this provider"
        }
    }

    // MARK: - External links

    /// External links for the provider — homepage (label = bare domain),
    /// pricing page, and the console where keys are issued. Surfaced as a
    /// row under the Status toggle so a `.notSetUp` user knows where to
    /// go to get a key. URLs drift over time; keep them centralised here
    /// so updates are one-file. `pricing` and `console` are optional —
    /// Ollama has neither (free, local).
    struct ProviderLinks {
        let homepage: URL
        let homepageLabel: String
        let pricing: URL?
        let console: URL?
        let consoleLabel: String  // "Keys" for cloud APIs; "Portal" for Azure
    }

    var links: ProviderLinks {
        switch self {
        case .claude:
            return ProviderLinks(
                homepage: URL(string: "https://anthropic.com")!,
                homepageLabel: "anthropic.com",
                pricing: URL(string: "https://anthropic.com/pricing"),
                console: URL(string: "https://console.anthropic.com"),
                consoleLabel: "Keys"
            )
        case .chatGPT:
            return ProviderLinks(
                homepage: URL(string: "https://openai.com")!,
                homepageLabel: "openai.com",
                pricing: URL(string: "https://openai.com/api/pricing"),
                console: URL(string: "https://platform.openai.com/api-keys"),
                consoleLabel: "Keys"
            )
        case .gemini:
            return ProviderLinks(
                homepage: URL(string: "https://ai.google.dev")!,
                homepageLabel: "ai.google.dev",
                pricing: URL(string: "https://ai.google.dev/pricing"),
                console: URL(string: "https://aistudio.google.com/app/apikey"),
                consoleLabel: "Keys"
            )
        case .azure:
            // Azure customers manage keys inside their org's portal under
            // their own deployment — there's no single "get a key" page.
            return ProviderLinks(
                homepage: URL(
                    string: "https://azure.microsoft.com/en-us/products/ai-services/openai-service")!,
                homepageLabel: "azure.microsoft.com",
                pricing: URL(
                    string:
                        "https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/"
                ),
                console: URL(string: "https://portal.azure.com"),
                consoleLabel: "Portal"
            )
        case .ollama:
            return ProviderLinks(
                homepage: URL(string: "https://ollama.com")!,
                homepageLabel: "ollama.com",
                pricing: nil,
                console: nil,
                consoleLabel: ""
            )
        }
    }
}

// MARK: - Account status

/// Normalised account status across all providers.
///
/// This is purely about whether the provider is set up and healthy —
/// orthogonal to which provider is "active" (user's choice, shown as
/// a radio/checkmark in the sidebar). A provider can be selected but
/// not set up, which prompts the user to enter a key.
///
/// Derived from API test calls (same validation as `bristlenose doctor`):
/// - 2xx → `.online`
/// - 401/403 → `.invalid`
/// - 402/429/network error → `.unavailable`
/// - No key in Keychain → `.notSetUp`
///
/// Providers don't expose balance, free-tier, or trial info via API,
/// so we can't distinguish "free demo" from "paid". We report what
/// we can actually detect.
enum ProviderStatus: Equatable {
    /// Key valid and API reachable (or Ollama running).
    case online
    /// No API key configured (or Ollama URL not set).
    case notSetUp
    /// Key rejected by the API (401 Unauthorized, 403 Forbidden).
    case invalid
    /// Key valid but unusable right now (402 no credits, 429 rate limited,
    /// network error, or Ollama not running).
    case unavailable
    /// Validation in progress.
    case checking

    var dotColor: Color {
        switch self {
        case .online: .green
        case .notSetUp: .secondary
        case .invalid: .red
        case .unavailable: .orange
        case .checking: .secondary
        }
    }

    var label: String {
        switch self {
        case .online: "Online"
        case .notSetUp: "Not set up"
        case .invalid: "Invalid key"
        case .unavailable: "Unavailable"
        case .checking: "Checking…"
        }
    }

    /// True when the provider may be activated. `.online` only — every
    /// other state (including `.unavailable`) blocks the radio.
    var isConfigured: Bool {
        self == .online
    }
}

// MARK: - Notification

extension Notification.Name {
    /// Posted when any LLM or transcription preference changes.
    /// ServeManager listens to this to auto-restart the serve process.
    static let bristlenosePrefsChanged = Notification.Name("bristlenosePrefsChanged")
    /// Posted by the app menu to re-show the AI data disclosure sheet.
    static let showAIConsentSheet = Notification.Name("showAIConsentSheet")
    /// Posted by the app menu to show the Build Info diagnostic sheet.
    static let showBuildInfoSheet = Notification.Name("showBuildInfoSheet")
}

// MARK: - Ollama catalog

/// Curated Ollama models with sizes + RAM tiers. The list is local
/// (we know what models exist + their costs without needing Ollama
/// installed or running). Mirrors `docs/design-gemma4-local-models.md`
/// LOCAL_MODEL_RAM but trimmed to four — one per RAM tier — to keep
/// the picker tight.
struct OllamaModel: Identifiable, Hashable {
    var id: String { tag }
    let tag: String
    let displayName: String
    let weightsGB: Double
    let minRAMGB: Double
}

enum OllamaCatalog {
    static let curated: [OllamaModel] = [
        // Order: small → large. The greyed unfit rows still appear so
        // the user can see what's possible at higher tiers.
        OllamaModel(tag: "llama3.2:3b",  displayName: "Llama 3.2 3B", weightsGB: 2,  minRAMGB: 4),
        OllamaModel(tag: "gemma4:e4b",   displayName: "Gemma 4 E4B",  weightsGB: 3,  minRAMGB: 8),
        OllamaModel(tag: "gemma4:26b",   displayName: "Gemma 4 26B",  weightsGB: 16, minRAMGB: 24),
        OllamaModel(tag: "gemma4:31b",   displayName: "Gemma 4 31B",  weightsGB: 20, minRAMGB: 32),
    ]

    /// System RAM in GB. Reads `ProcessInfo.processInfo.physicalMemory`
    /// (sandbox-safe, no entitlement required).
    static var systemRAMGB: Double {
        Double(ProcessInfo.processInfo.physicalMemory) / 1_000_000_000
    }

    /// Best-fit recommendation for the user's hardware. Threshold of
    /// `>= 15` rather than `>= 16` — `physicalMemory` reports slightly
    /// less than the advertised RAM tier (e.g. ~15.5 GB for a "16 GB"
    /// Mac), and we don't want a 16 GB machine to fall back to the
    /// floor model. Mirrors the waterfall in
    /// `docs/design-gemma4-local-models.md`.
    static func recommendedTag(forRAMGB ramGB: Double = systemRAMGB) -> String {
        if ramGB >= 47 { return "gemma4:31b" }
        if ramGB >= 35 { return "gemma4:26b" }
        if ramGB >= 15 { return "gemma4:e4b" }
        return "llama3.2:3b"
    }

    /// True if this model fits in the given RAM tier. Drives grey-out
    /// in the Set up sheet's picker.
    ///
    /// `minRAMGB` is the floor — total system RAM, with OS + foreground
    /// apps + Bristlenose itself already factored in (Llama 3.2 3B
    /// `minRAMGB: 4` = ~2 GB weights + ~2 GB everything else). Don't
    /// subtract additional headroom here — that double-counts and locks
    /// the smallest Mac tier out of every model. `recommendedTag`
    /// thresholds (15 / 35 / 47) carry the comfort margin above this
    /// floor.
    static func fits(_ model: OllamaModel, ramGB: Double = systemRAMGB) -> Bool {
        ramGB >= model.minRAMGB
    }

    /// Look up a model by tag. Returns nil for tags not in the curated
    /// list (e.g. user-typed Custom… values).
    static func model(for tag: String) -> OllamaModel? {
        curated.first { $0.tag == tag }
    }
}
