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

    /// Default model for this provider.
    var defaultModel: String {
        switch self {
        case .claude: "claude-sonnet-4-20250514"
        case .chatGPT: "gpt-4o"
        case .gemini: "gemini-2.0-flash"
        case .azure: "gpt-4o"
        case .ollama: "llama3.2:3b"
        }
    }

    /// Known models for the picker. "Custom…" is appended by the UI.
    var availableModels: [String] {
        switch self {
        case .claude: ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001", "claude-opus-4-20250514"]
        case .chatGPT: ["gpt-4o", "gpt-4o-mini"]
        case .gemini: ["gemini-2.0-flash", "gemini-2.5-pro"]
        case .azure: ["gpt-4o", "gpt-4o-mini"]
        case .ollama: ["llama3.2:3b", "mistral"]
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
}
