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

    /// True when the key has been validated successfully.
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
