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
    /// Takes `i18n` because the Ollama description is user-facing copy.
    /// `@MainActor` because `I18n` is main-actor-isolated.
    @MainActor
    func helperText(_ i18n: I18n) -> String? {
        switch self {
        case .ollama: i18n.t("desktop.llmSettings.providers.ollama.description")
        default: nil
        }
    }

    /// User-facing label for a status, with provider-specific overrides.
    /// Ollama swaps "Online" for "Local" — both healthy, but "Local"
    /// names the actual privacy property the user picked Ollama for.
    @MainActor
    func statusLabel(for status: ProviderStatus, i18n: I18n) -> String {
        if self == .ollama && status == .online {
            return i18n.t("desktop.llmSettings.status.local")
        }
        return status.label(i18n)
    }

    /// Label for the "Use this provider" activation toggle.
    /// Cloud providers use the generic phrasing — they're already named
    /// in the sidebar row above. Ollama gets a custom label that names
    /// the local-only property, since "Use this provider" undersells the
    /// reason a user would pick it.
    @MainActor
    func activationToggleLabel(_ i18n: I18n) -> String {
        switch self {
        case .ollama: i18n.t("desktop.llmSettings.activate.ollama")
        default: i18n.t("desktop.llmSettings.activate.generic")
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
        /// i18n key for the console label — "Keys" for cloud APIs, "Portal" for
        /// Azure. Resolve via `i18n.t(links.consoleLabel)` at the call site.
        let consoleLabel: String
    }

    var links: ProviderLinks {
        switch self {
        case .claude:
            return ProviderLinks(
                homepage: URL(string: "https://anthropic.com")!,
                homepageLabel: "anthropic.com",
                pricing: URL(string: "https://anthropic.com/pricing"),
                console: URL(string: "https://console.anthropic.com"),
                consoleLabel: "desktop.llmSettings.console.keys"
            )
        case .chatGPT:
            return ProviderLinks(
                homepage: URL(string: "https://openai.com")!,
                homepageLabel: "openai.com",
                pricing: URL(string: "https://openai.com/api/pricing"),
                console: URL(string: "https://platform.openai.com/api-keys"),
                consoleLabel: "desktop.llmSettings.console.keys"
            )
        case .gemini:
            return ProviderLinks(
                homepage: URL(string: "https://ai.google.dev")!,
                homepageLabel: "ai.google.dev",
                pricing: URL(string: "https://ai.google.dev/pricing"),
                console: URL(string: "https://aistudio.google.com/app/apikey"),
                consoleLabel: "desktop.llmSettings.console.keys"
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
                consoleLabel: "desktop.llmSettings.console.portal"
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
/// - 402 (out of credit) → `.outOfCredit` (observed negative — sticky, shown)
/// - 429/5xx/network error → `.unavailable` (transient — masked by cache)
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
    /// Transiently unusable: 429 rate-limited, 5xx, network error, or Ollama
    /// not running. A *failed observation* — we learned nothing about the
    /// credential, so a cached `.online` legitimately masks it (offline
    /// survival). Contrast `.outOfCredit`, which is an observed negative.
    case unavailable
    /// Key valid and authenticated, but the account is out of credit (HTTP
    /// 402). An *observed negative*, not a failed observation: it must NOT be
    /// masked by a cached `.online`, and it is sticky (persisted) so it
    /// survives going offline — topping up happens out-of-band at the
    /// provider's console, exactly like fixing an `.invalid` key. Amber, like
    /// `.unavailable`; the label + detail string disambiguate.
    case outOfCredit
    /// Validation in progress.
    case checking

    var dotColor: Color {
        switch self {
        case .online: .green
        case .notSetUp: .secondary
        case .invalid: .red
        case .unavailable: .orange
        case .outOfCredit: .orange
        case .checking: .secondary
        }
    }

    @MainActor
    func label(_ i18n: I18n) -> String {
        switch self {
        case .online: i18n.t("desktop.llmSettings.status.online")
        case .notSetUp: i18n.t("desktop.llmSettings.status.notSetUp")
        case .invalid: i18n.t("desktop.llmSettings.status.invalid")
        case .unavailable: i18n.t("desktop.llmSettings.status.unavailable")
        case .outOfCredit: i18n.t("desktop.llmSettings.status.outOfCredit")
        case .checking: i18n.t("desktop.llmSettings.status.checking")
        }
    }

    /// True when the provider is set up and confirmed healthy. `.online` only.
    /// Kept for "is this provider working right now" styling; activation uses
    /// the broader `canActivate`.
    var isConfigured: Bool {
        self == .online
    }

    /// True when this provider may be set active (the radio / "Use this
    /// provider" toggle). Broader than `isConfigured`: a provider whose
    /// account is out of credit, or merely unreachable right now, is still a
    /// legitimate choice — the user may top up or reconnect, and "never gate
    /// Run on a stale light" means activation must not require a live green.
    /// Only a definitively-bad key (`.invalid`), a missing one (`.notSetUp`),
    /// or an as-yet-unknown one (`.checking`) blocks activation.
    var canActivate: Bool {
        switch self {
        case .online, .outOfCredit, .unavailable: return true
        case .invalid, .notSetUp, .checking: return false
        }
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

    /// Quality tier shown as the picker's descriptor word (§9.1). Semantic
    /// only — the pill maps each case to localised copy. The two large
    /// models share `.best`; their RAM qualifier (`needs N GB`) tells them
    /// apart on a Mac that can't run either.
    enum Tier { case smallest, balanced, best }

    var tier: Tier {
        switch tag {
        case "llama3.2:3b": .smallest
        case "gemma4:e4b": .balanced
        default: .best
        }
    }
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
        #if DEBUG
        // QA convenience: override the RAM-aware pick with a tiny model so the
        // ambient download pill can be exercised without fetching multi-GB
        // weights. Opt-in via the scheme's environment — when unset, normal
        // RAM-aware behaviour applies, so DEBUG analysis-quality QA still runs
        // the real model. Point it at a tag you don't already have (e.g.
        // BRISTLENOSE_DEBUG_OLLAMA_TAG=qwen2.5:0.5b, ~400 MB) to guarantee a
        // genuine, visible download. Never compiled into Release.
        if let override = ProcessInfo.processInfo.environment["BRISTLENOSE_DEBUG_OLLAMA_TAG"],
           !override.isEmpty {
            return override
        }
        #endif
        return tagForRAM(ramGB)
    }

    /// Pure RAM → tag waterfall — the testable core of `recommendedTag`,
    /// with no environment reads or DEBUG override. Boundaries are deliberate:
    /// `>= 15` (not 16) and `>= 35` / `>= 47` carry the comfort margin above
    /// each model's `minRAMGB` floor, and `physicalMemory` under-reports the
    /// advertised tier. Unit-pinned in `OllamaCatalogTests`.
    static func tagForRAM(_ ramGB: Double) -> String {
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

    // MARK: - Disk space

    /// The largest model the user can actually run on this Mac — the
    /// biggest-weights model whose `minRAMGB` floor the hardware clears.
    /// Drives the low-disk advisory: we warn against the largest model the
    /// user could *select*, not the largest model merely *shown* (the
    /// greyed over-RAM rows can't be picked, so their size is irrelevant
    /// to the disk decision). Finding 19.
    static func largestSelectable(forRAMGB ramGB: Double = systemRAMGB) -> OllamaModel? {
        curated.filter { fits($0, ramGB: ramGB) }.max { $0.weightsGB < $1.weightsGB }
    }

    /// Free space on the volume backing the user's home directory, in
    /// bytes. Uses `volumeAvailableCapacityForImportantUsage` — the
    /// purgeable-aware figure macOS reports to apps for "will this
    /// download fit?" decisions. Returns nil if the query fails (unknown
    /// → caller treats as "don't warn").
    static func freeDiskBytes() -> Int64? {
        let home = URL(fileURLWithPath: NSHomeDirectory())
        let values = try? home.resourceValues(
            forKeys: [.volumeAvailableCapacityForImportantUsageKey])
        return values?.volumeAvailableCapacityForImportantUsage
    }

    /// Advisory: is free disk below the largest model the user could
    /// select? Advisory only — never blocks the picker's Use button; the
    /// pull either fits or Ollama reports the failure honestly. Returns
    /// false when free space is unknown (don't cry wolf) and when there's
    /// no selectable model at all. Finding 19.
    static func isLowDisk(
        freeBytes: Int64? = freeDiskBytes(),
        ramGB: Double = systemRAMGB
    ) -> Bool {
        guard let freeBytes,
              let largest = largestSelectable(forRAMGB: ramGB) else { return false }
        return freeBytes < Int64(largest.weightsGB * 1_000_000_000)
    }
}
