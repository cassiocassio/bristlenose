import SwiftUI
import os

/// Settings tab for LLM provider management.
///
/// Uses the Apple Mail Accounts pattern: left sidebar list of providers
/// with status dots, right detail pane for the selected provider's settings.
///
/// Two orthogonal indicators per provider:
/// - **Radio** (user choice) — which provider is active for analysis
/// - **Status dot** (system state) — whether the provider is configured/healthy
///
/// A provider can be selected (radio) even if not set up (grey dot),
/// which prompts the user to enter a key.
struct LLMSettingsView: View {

    private static let logger = Logger(
        subsystem: "app.bristlenose", category: "llm-settings")

    /// TTL for the verdict cache — within this window, opening Settings
    /// does NOT kick a fresh round-trip per provider. Keeps Settings snappy
    /// and avoids spamming four LLM APIs on every open.
    private static let cacheTTL: TimeInterval = 60

    private static let relativeFormatter: RelativeDateTimeFormatter = {
        let f = RelativeDateTimeFormatter()
        f.unitsStyle = .full
        return f
    }()

    @AppStorage("activeProvider") private var activeProvider: String = "anthropic"
    @State private var selectedProvider: LLMProvider = .claude
    @State private var statuses: [LLMProvider: ProviderStatus] = [:]
    @State private var statusErrors: [LLMProvider: String] = [:]
    @State private var validationTasks: [LLMProvider: Task<Void, Never>] = [:]
    @State private var lastVerifiedTick: Date = .now  // forces relative-time refresh
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        // Mac Settings convention: fixed width per tab, height animates
        // between tabs to fit each tab's content. Not user-resizable
        // (matches Mail / System Settings). HStack rather than HSplitView
        // — there's no splitter to drag.
        //
        // minHeight ensures the tallest provider config (Azure, with the
        // extra endpoint/deployment/version section) opens without a
        // scrollbar. Smaller configs get the same minimum height; cost
        // is negligible vs the alternative of an unexpected scrollbar.
        HStack(spacing: 0) {
            providerList
                .frame(width: 260)
            Divider()
            providerDetail
        }
        .frame(width: 720)
        .frame(minHeight: 660)
        .onAppear {
            if let active = LLMProvider(rawValue: activeProvider) {
                selectedProvider = active
            }
            refreshStatuses()
            revalidateAll()
        }
        // Refresh "Last verified" relative-time labels every 30s so they
        // don't go stale (e.g. "1 minute ago" forever).
        .task {
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(30))
                lastVerifiedTick = .now
            }
        }
    }

    // MARK: - Left sidebar

    private var providerList: some View {
        VStack(spacing: 0) {
            List(LLMProvider.allCases, selection: $selectedProvider) { provider in
                HStack(spacing: 10) {
                    // Radio indicator for active provider (user choice).
                    // Uses a Button for a reliable click target — onTapGesture
                    // on a small image inside a List row gets eaten by List selection.
                    Button {
                        // Only allow activation if the provider is configured.
                        guard statusFor(provider).isConfigured else { return }
                        activeProvider = provider.rawValue
                        syncGlobalModel()
                        refreshStatuses()
                        NotificationCenter.default.post(
                            name: .bristlenosePrefsChanged, object: nil)
                    } label: {
                        Image(systemName: provider.rawValue == activeProvider
                              ? "checkmark.circle.fill" : "circle")
                            .foregroundStyle(provider.rawValue == activeProvider
                                             ? Color.accentColor : .secondary)
                            .font(.system(size: 14))
                    }
                    .buttonStyle(.plain)
                    .disabled(!statusFor(provider).isConfigured
                              && provider.rawValue != activeProvider)

                    // Mail-density icon. Full saturation when the provider
                    // is set up (.online / .invalid / .unavailable / .checking
                    // — any state with a credential); dimmed for `.notSetUp`
                    // so the row reads as needs-attention rather than
                    // ready-to-use.
                    Image(provider.iconAssetName)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(width: 28, height: 28)
                        .opacity(statusFor(provider) == .notSetUp ? 0.45 : 1.0)

                    VStack(alignment: .leading, spacing: 3) {
                        Text(provider.displayName)
                            .foregroundStyle(
                                statusFor(provider) == .notSetUp
                                    ? .secondary : .primary)
                        HStack(spacing: 6) {
                            statusIndicator(for: provider, dotSize: 10)
                            Text(provider.statusLabel(for: statusFor(provider)))
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        .modifier(OptionalHelp(text: statusErrors[provider]))
                    }
                    .padding(.vertical, 2)
                    .animation(
                        reduceMotion ? nil : .easeInOut(duration: 0.2),
                        value: statusFor(provider))
                }
                .tag(provider)
            }

        }
    }

    // MARK: - Right detail pane

    private var providerDetail: some View {
        Form {
            Section("Status") {
                Toggle(selectedProvider.activationToggleLabel, isOn: activeBinding)
                    .disabled(!statusFor(selectedProvider).isConfigured
                              && activeProvider != selectedProvider.rawValue)

                providerLinks

                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 6) {
                        statusIndicator(for: selectedProvider, dotSize: 12)
                        Text(selectedProvider.statusLabel(for: statusFor(selectedProvider)))
                            .foregroundStyle(.secondary)
                    }
                    .animation(
                        reduceMotion ? nil : .easeInOut(duration: 0.2),
                        value: statusFor(selectedProvider))
                    if let error = statusErrors[selectedProvider],
                       statusFor(selectedProvider) != .online {
                        // Per Mac convention (Mail, Internet Accounts) the
                        // dot carries the colour signal; the error text is
                        // .secondary so we don't have two channels for one
                        // signal.
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    if let lastVerified = lastVerifiedText(for: selectedProvider) {
                        Text(lastVerified)
                            .font(.caption)
                            .foregroundStyle(.tertiary)
                            .id(lastVerifiedTick)  // refresh with the 30s ticker
                    }
                }
            }

            if selectedProvider.needsAPIKey {
                apiKeySection
            } else {
                ollamaSection
            }

            modelSection

            Section {
                temperatureSlider
                concurrencySlider
            }

            if selectedProvider == .azure {
                azureSection
            }
            // Ollama helper text moved into ollamaSection above the field;
            // no trailing helper card.
        }
        .formStyle(.grouped)
    }

    // MARK: - Active toggle binding

    /// Toggle that activates the selected provider (radio semantics —
    /// checking one unchecks all others, like Mail's "Enable this account").
    private var activeBinding: Binding<Bool> {
        Binding(
            get: { activeProvider == selectedProvider.rawValue },
            set: { newValue in
                if newValue, statusFor(selectedProvider).isConfigured {
                    activeProvider = selectedProvider.rawValue
                    syncGlobalModel()
                    refreshStatuses()
                    NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
                }
                // Unchecking the active provider is a no-op — one must always be active.
            }
        )
    }

    // MARK: - API Key section

    @State private var apiKeyInputs: [LLMProvider: String] = [:]
    @State private var apiKeyRevealed: [LLMProvider: Bool] = [:]
    @FocusState private var apiKeyFocused: Bool

    private var apiKeySection: some View {
        Section("API Key") {
            HStack {
                // `.labelsHidden()` stops SwiftUI's `.formStyle(.grouped)`
                // from injecting an inline "API Key" label that reflows the
                // row when the revealed plaintext is wide. Section header
                // already names the field; redundant inline label was the
                // source of the height jump on eye-toggle.
                let revealed = apiKeyRevealed[selectedProvider, default: false]
                if revealed {
                    TextField("API Key", text: apiKeyBinding)
                        .textFieldStyle(.roundedBorder)
                        .focused($apiKeyFocused)
                        .labelsHidden()
                        .lineLimit(1)
                } else {
                    SecureField("API Key", text: apiKeyBinding)
                        .textFieldStyle(.roundedBorder)
                        .focused($apiKeyFocused)
                        .labelsHidden()
                }

                Button {
                    apiKeyRevealed[selectedProvider, default: false].toggle()
                } label: {
                    Image(systemName: apiKeyRevealed[selectedProvider, default: false]
                          ? "eye.slash" : "eye")
                }
                .buttonStyle(.borderless)
                .help(apiKeyRevealed[selectedProvider, default: false]
                      ? "Hide API key" : "Show API key")

                if apiKeyInputs[selectedProvider]?.isEmpty == false {
                    // macOS inline-clear convention: xmark.circle.fill
                    // glyph, borderless. Matches Spotlight, Safari URL bar,
                    // every NSSearchField in System Settings.
                    Button {
                        clearAPIKey()
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.borderless)
                    .help("Clear API key")
                }
            }
            .onAppear { loadAPIKey() }
            .onChange(of: selectedProvider) { _, _ in loadAPIKey() }
            .onSubmit { saveAPIKey() }
            .onChange(of: apiKeyFocused) { _, focused in
                if !focused { saveAPIKey() }
            }
        }
    }

    private var apiKeyBinding: Binding<String> {
        Binding(
            get: { apiKeyInputs[selectedProvider, default: ""] },
            set: { apiKeyInputs[selectedProvider] = $0 }
        )
    }

    private func loadAPIKey() {
        guard let keychainKey = selectedProvider.keychainProvider else { return }
        let existing = KeychainHelper.get(provider: keychainKey) ?? ""
        apiKeyInputs[selectedProvider] = existing
    }

    private func saveAPIKey() {
        guard let keychainKey = selectedProvider.keychainProvider else { return }
        let value = apiKeyInputs[selectedProvider, default: ""]
        if value.isEmpty {
            KeychainHelper.delete(provider: keychainKey)
            LLMValidator.clearCache(provider: selectedProvider)
            validationTasks[selectedProvider]?.cancel()
            validationTasks[selectedProvider] = nil
            applyPresenceAndCache(provider: selectedProvider)
        } else {
            KeychainHelper.set(provider: keychainKey, value: value)
            // applyPresenceAndCache will pick up cache for this key (if it's
            // a re-paste of a previously-validated key) or fall through to
            // .checking for new keys; kickOffValidation refreshes truth.
            applyPresenceAndCache(provider: selectedProvider)
            kickOffValidation(provider: selectedProvider, key: value)
        }
        NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
    }

    private func clearAPIKey() {
        guard let keychainKey = selectedProvider.keychainProvider else { return }
        KeychainHelper.delete(provider: keychainKey)
        LLMValidator.clearCache(provider: selectedProvider)
        validationTasks[selectedProvider]?.cancel()
        validationTasks[selectedProvider] = nil
        apiKeyInputs[selectedProvider] = ""
        applyPresenceAndCache(provider: selectedProvider)
        NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
    }

    // MARK: - Ollama section

    /// Ollama server URL is hardwired in the desktop GUI. This is the
    /// trust boundary: a user social-engineered into pasting an attacker
    /// URL here would silently exfiltrate transcripts over plain HTTP,
    /// contradicting the "transcripts stay on your Mac" claim. CLI users
    /// keep the override path via the `BRISTLENOSE_LOCAL_URL` env var; in
    /// the desktop app, only localhost is reachable.
    private static let hardwiredOllamaURL = "http://localhost:11434/v1"
    private var ollamaURL: String { Self.hardwiredOllamaURL }

    private var ollamaSection: some View {
        Section("Server") {
            if let helper = selectedProvider.helperText {
                Text(helper)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            HStack {
                Text("URL")
                Spacer()
                Text("localhost:11434")
                    .monospaced()
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
            }
        }
    }

    // MARK: - Model section

    @AppStorage("llmModel") private var globalModel: String = "claude-sonnet-4-20250514"
    @State private var useCustomModel: Bool = false
    @State private var customModelText: String = ""
    @FocusState private var customModelFocused: Bool

    private var modelSection: some View {
        let models = selectedProvider.availableModels
        let currentModel = modelForProvider(selectedProvider)
        let isKnown = models.contains(currentModel)

        return Section("Model") {
            Picker("Model", selection: modelBinding) {
                ForEach(models, id: \.self) { model in
                    Text(model).tag(model)
                }
                Divider()
                Text("Custom…").tag("__custom__")
            }

            if !isKnown || useCustomModel {
                TextField("Custom model name", text: $customModelText)
                    .textFieldStyle(.roundedBorder)
                    .focused($customModelFocused)
                    .onSubmit {
                        setModel(customModelText)
                    }
                    .onChange(of: customModelFocused) { _, focused in
                        if !focused, !customModelText.isEmpty {
                            setModel(customModelText)
                        }
                    }
            }
        }
        .onAppear { syncModelState() }
        .onChange(of: selectedProvider) { _, _ in syncModelState() }
    }

    private func modelForProvider(_ provider: LLMProvider) -> String {
        UserDefaults.standard.string(forKey: "llmModel_\(provider.rawValue)")
            ?? provider.defaultModel
    }

    private func setModel(_ model: String) {
        UserDefaults.standard.set(model, forKey: "llmModel_\(selectedProvider.rawValue)")
        if selectedProvider.rawValue == activeProvider {
            globalModel = model
        }
        NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
    }

    /// Write the active provider's per-provider model to the global `llmModel` key
    /// so ServeManager picks it up.
    private func syncGlobalModel() {
        if let active = LLMProvider(rawValue: activeProvider) {
            globalModel = modelForProvider(active)
        }
    }

    private func syncModelState() {
        let current = modelForProvider(selectedProvider)
        let isKnown = selectedProvider.availableModels.contains(current)
        useCustomModel = !isKnown
        customModelText = isKnown ? "" : current
    }

    private var modelBinding: Binding<String> {
        Binding(
            get: {
                let current = modelForProvider(selectedProvider)
                if selectedProvider.availableModels.contains(current) {
                    return current
                }
                return "__custom__"
            },
            set: { newValue in
                if newValue == "__custom__" {
                    useCustomModel = true
                } else {
                    useCustomModel = false
                    customModelText = ""
                    setModel(newValue)
                }
            }
        )
    }

    // MARK: - Temperature & concurrency

    @AppStorage("llmTemperature") private var temperature: Double = 0.1
    @AppStorage("llmConcurrency") private var concurrency: Double = 3

    private var temperatureSlider: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("Temperature")
                Spacer()
                Text(temperature.formatted(.number.precision(.fractionLength(1))))
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
            }
            Slider(value: $temperature, in: 0...1, step: 0.1)
            Text("Low = focused, high = creative")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .onChange(of: temperature) { _, _ in
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
    }

    private var concurrencySlider: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("Concurrency")
                Spacer()
                Text("\(Int(concurrency))")
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
            }
            Slider(value: $concurrency, in: 1...10, step: 1)
            Text("Parallel LLM calls")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .onChange(of: concurrency) { _, _ in
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
    }

    // MARK: - Azure section

    @AppStorage("azureEndpoint") private var azureEndpoint: String = ""
    @AppStorage("azureDeployment") private var azureDeployment: String = ""
    @AppStorage("azureAPIVersion") private var azureAPIVersion: String = "2024-10-21"
    @FocusState private var azureEndpointFocused: Bool
    @FocusState private var azureAPIVersionFocused: Bool

    private var azureSection: some View {
        Section("Azure Settings") {
            TextField("Endpoint URL", text: $azureEndpoint)
                .textFieldStyle(.roundedBorder)
                .focused($azureEndpointFocused)
                .onSubmit { revalidateAzure() }
            TextField("Deployment name", text: $azureDeployment)
                .textFieldStyle(.roundedBorder)
            TextField("API version", text: $azureAPIVersion)
                .textFieldStyle(.roundedBorder)
                .focused($azureAPIVersionFocused)
                .onSubmit { revalidateAzure() }
        }
        // Prefs notification still fires on every change (cheap UI signal so
        // ServeManager can rebuild env vars when the user finishes typing).
        // Validation only fires on focus blur or Enter, so dragging through
        // a 30-character endpoint URL doesn't fire 30 billed round-trips.
        .onChange(of: azureEndpoint) { _, _ in
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
        .onChange(of: azureDeployment) { _, _ in
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
        .onChange(of: azureEndpointFocused) { _, focused in
            if !focused { revalidateAzure() }
        }
        .onChange(of: azureAPIVersionFocused) { _, focused in
            if !focused { revalidateAzure() }
        }
    }

    /// Re-run validation for Azure (endpoint or API version changed).
    /// No-op if no key in Keychain.
    private func revalidateAzure() {
        guard let azureKey = LLMProvider.azure.keychainProvider,
              let stored = KeychainHelper.get(provider: azureKey),
              !stored.isEmpty
        else {
            statuses[.azure] = .notSetUp
            statusErrors[.azure] = nil
            return
        }
        statuses[.azure] = .checking
        statusErrors[.azure] = nil
        kickOffValidation(provider: .azure, key: stored)
    }

    // MARK: - Status helpers

    private func statusFor(_ provider: LLMProvider) -> ProviderStatus {
        statuses[provider, default: .notSetUp]
    }

    /// Three small inline links under the "Use this provider" toggle:
    /// homepage (bare lowercase domain), Pricing, and Keys (or Portal for
    /// Azure). Opens in the system browser via SwiftUI `Link`. Generous
    /// 20pt spacing for visual separation. Pricing and Keys are hidden
    /// when the provider doesn't have them (Ollama).
    @ViewBuilder
    private var providerLinks: some View {
        let links = selectedProvider.links
        HStack(spacing: 20) {
            Link(links.homepageLabel, destination: links.homepage)
            if let pricing = links.pricing {
                Link("Pricing", destination: pricing)
            }
            if let console = links.console {
                Link(links.consoleLabel, destination: console)
            }
        }
        .font(.caption)
    }

    /// "Last verified 2 minutes ago" line for the detail pane, or nil
    /// if there's no cached verdict for this provider+key combo. Ollama
    /// is excluded — it has no cache; its own `.online` is "we just
    /// checked." The line refreshes via `lastVerifiedTick` (30s ticker).
    private func lastVerifiedText(for provider: LLMProvider) -> String? {
        if provider == .ollama { return nil }
        guard let kc = provider.keychainProvider,
              let stored = KeychainHelper.get(provider: kc),
              !stored.isEmpty,
              let entry = LLMValidator.cachedEntry(provider: provider, key: stored)
        else { return nil }
        let relative = Self.relativeFormatter.localizedString(
            for: entry.lastCheckedAt, relativeTo: Date())
        return "Last verified \(relative)"
    }

    /// Status indicator that swaps a `ProgressView` in for the dot when
    /// `.checking` (Mail's "Status: Connecting…" pattern). For `.notSetUp`
    /// the dot stays solid but pale — enough to register as "a thing"
    /// without competing visually with the colored states. Hollow outline
    /// would collide with the inactive-radio glyph next to it.
    /// `dotSize` is the diameter for the resting Circle; the slot reserves
    /// a fixed width so the row doesn't jiggle on transition.
    @ViewBuilder
    private func statusIndicator(for provider: LLMProvider, dotSize: CGFloat) -> some View {
        let slot = max(dotSize, 14)  // big enough for `.controlSize(.small)` ProgressView
        let status = statusFor(provider)
        ZStack {
            if status == .checking {
                ProgressView()
                    .controlSize(.small)
            } else if status == .notSetUp {
                Circle()
                    .fill(Color.secondary.opacity(0.3))
                    .frame(width: dotSize, height: dotSize)
            } else {
                Circle()
                    .fill(status.dotColor)
                    .frame(width: dotSize, height: dotSize)
            }
        }
        .frame(width: slot, height: slot)
    }

    /// Refresh the UI status for every provider from Keychain + verdict
    /// cache. Pure presence-and-cache read — never makes a network call.
    /// Called on every prefs change (radio toggles, active flips) so that
    /// switching the active provider doesn't quietly hammer four LLM APIs.
    /// Use `revalidateAll()` (onAppear) or per-provider `kickOffValidation`
    /// (after Save / Azure-config edit) when fresh truth is wanted.
    private func refreshStatuses() {
        for provider in LLMProvider.allCases {
            applyPresenceAndCache(provider: provider)
        }
    }

    /// Read the cache for one provider and update its UI state. No network.
    ///
    /// State derivation:
    /// - No key in Keychain → `.notSetUp`.
    /// - Key present, cache hit (hash matches), verdict `.ok` → `.online`.
    /// - Key present, cache hit, verdict `.invalid` → `.invalid` (definitive
    ///   verdict from a real 401/403 — we don't lose this when offline).
    /// - Key present, cache miss / hash mismatch → `.checking`. Caller is
    ///   expected to follow up with `kickOffValidation`.
    private func applyPresenceAndCache(provider: LLMProvider) {
        // Contract: this function shows last-known state only. It NEVER
        // sets `.checking` — only `kickOffValidation` does, immediately
        // before doing the network round-trip. Otherwise refreshStatuses
        // (called from radio toggle, active toggle, etc.) would strand
        // providers in `.checking` forever because those callers don't
        // follow up with a kickoff. SwiftUI batches state writes within
        // a tick, so when caller is saveAPIKey (applyPresenceAndCache
        // then kickOffValidation back-to-back), only `.checking` renders.
        if provider == .ollama {
            let urlStr = ollamaURL.trimmingCharacters(in: .whitespacesAndNewlines)
            if urlStr.isEmpty {
                statuses[provider] = .notSetUp
            }
            // URL set: leave the existing status (last validation result)
            // alone. revalidateAll on Settings open will kick a fresh check.
            statusErrors[provider] = nil
            return
        }
        guard let keychainKey = provider.keychainProvider,
              let stored = KeychainHelper.get(provider: keychainKey),
              !stored.isEmpty
        else {
            statuses[provider] = .notSetUp
            statusErrors[provider] = nil
            return
        }
        if let cached = LLMValidator.cachedVerdict(provider: provider, key: stored) {
            statuses[provider] = cached.status
            statusErrors[provider] =
                (cached == .invalid)
                ? "Last validation was rejected — re-checking…"
                : nil
        } else {
            // Key present but no cached verdict — let the existing status
            // stand (likely `.notSetUp` if first paste, since `kickOffValidation`
            // will follow within the same tick from the saveAPIKey path).
            statusErrors[provider] = nil
        }
    }

    /// Kick off background validation for every provider with a credential.
    /// Skips cloud providers whose verdict cache is fresher than `cacheTTL`
    /// — opening Settings 20×/day to tweak temperature shouldn't ping four
    /// LLM APIs every time. Ollama is always probed (localhost is cheap).
    private func revalidateAll() {
        for provider in LLMProvider.allCases {
            if provider == .ollama {
                let urlStr = ollamaURL.trimmingCharacters(in: .whitespacesAndNewlines)
                if !urlStr.isEmpty {
                    kickOffValidation(provider: .ollama, key: "")
                }
                continue
            }
            guard let keychainKey = provider.keychainProvider,
                  let stored = KeychainHelper.get(provider: keychainKey),
                  !stored.isEmpty
            else { continue }
            if LLMValidator.cacheIsFresh(
                provider: provider, key: stored, ttl: Self.cacheTTL)
            {
                Self.logger.debug(
                    "skip revalidate \(provider.rawValue, privacy: .public) — cache fresh")
                continue
            }
            kickOffValidation(provider: provider, key: stored)
        }
    }

    /// Validate `key` for `provider` in the background and write the
    /// resulting status + error string back on the main actor. Cancels any
    /// in-flight validation for the same provider so the latest paste wins.
    ///
    /// Offline survival: if the network round-trip returns `.unavailable`
    /// (timeout, no connectivity, 429, 402) AND we have a cached verdict
    /// for this exact key, the cache wins. The user's previously-validated
    /// key keeps showing `.online` at the café; a previously-rejected key
    /// keeps showing `.invalid`. Definitive verdicts (`.online`, `.invalid`)
    /// from the network always overwrite the cache.
    private func kickOffValidation(provider: LLMProvider, key: String) {
        validationTasks[provider]?.cancel()
        // Show .checking spinner from the moment validation kicks off — even
        // if the cache pre-set us to .online a tick earlier. SwiftUI batches
        // these state writes within the same synchronous tick, so the
        // rendered transition is dot → spinner → settled, never the
        // misleading green-flash-red on a rotated key.
        statuses[provider] = .checking
        statusErrors[provider] = nil
        let azureCfg: LLMValidator.AzureConfig? =
            (provider == .azure)
            ? LLMValidator.AzureConfig(
                endpoint: azureEndpoint, apiVersion: azureAPIVersion)
            : nil
        let ollamaURLValue: String? = (provider == .ollama) ? ollamaURL : nil
        validationTasks[provider] = Task { @MainActor in
            // Defence-in-depth — bail before the await if we were already
            // cancelled (e.g. another paste arrived in the same tick).
            if Task.isCancelled { return }
            let (status, error) = await LLMValidator.validate(
                provider: provider, key: key,
                azureConfig: azureCfg, ollamaURL: ollamaURLValue)
            if Task.isCancelled { return }

            if status == .unavailable,
               let cached = LLMValidator.cachedVerdict(provider: provider, key: key)
            {
                // Transient failure with a cached verdict — trust the cache.
                // Surface the network error in the tooltip though, so the user
                // knows we tried and what happened.
                statuses[provider] = cached.status
                statusErrors[provider] =
                    (cached == .invalid)
                    ? "Last validation was rejected — re-checking…"
                    : error  // typically "No network connection" / "rate-limited"
                Self.logger.info(
                    "validate \(provider.rawValue, privacy: .public) → \(cached.rawValue, privacy: .public) (cache fallback, network said unavailable)"
                )
                return
            }

            statuses[provider] = status
            statusErrors[provider] = error
            LLMValidator.recordVerdict(provider: provider, key: key, status: status)
            Self.logger.info(
                "validate \(provider.rawValue, privacy: .public) → \(String(describing: status), privacy: .public)"
            )
        }
    }
}

/// `.help()` with empty/nil text still attaches an empty tooltip — produces
/// a hover-delay beat with nothing showing, which feels like a bug. This
/// modifier only attaches the help when there's actual text to show.
private struct OptionalHelp: ViewModifier {
    let text: String?
    func body(content: Content) -> some View {
        if let text, !text.isEmpty {
            content.help(text)
        } else {
            content
        }
    }
}
