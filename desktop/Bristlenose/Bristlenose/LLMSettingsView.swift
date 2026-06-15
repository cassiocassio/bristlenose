import AppKit
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

    @EnvironmentObject var i18n: I18n

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
            // Eager board: paint EVERY row from Keychain presence + cache
            // immediately (no spinner wall), then silently reconfirm each keyed
            // provider whose cache is stale. Replaces the old lazy-load, which
            // left non-selected rows grey-by-laziness and broke radio
            // activation (Defect L). The "3× Keychain prompt cascade" (sandbox
            // walk #7) that justified lazy-load was a *legacy file-based
            // keychain* artifact (Always-Allow grant bound to the binary hash);
            // we moved to the data-protection keychain (8b2ef51), which
            // validates by Team ID and doesn't prompt for own-access-group reads
            // on a team-signed build (Apple TN3137; cf. steipete/CodexBar #585).
            refreshAllStatuses()
            revalidateAllStale()
        }
        // Lazy load: when the user clicks a different provider in the
        // sidebar, that's the moment we touch Keychain for it. This is the
        // entry point for the per-row "open the account" prompt — Mail
        // Accounts pattern.
        .onChange(of: selectedProvider) { _, _ in
            applyPresenceAndCache(provider: selectedProvider)
            revalidateSelectedIfNeeded()
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
                        activate(provider)
                    } label: {
                        Image(systemName: provider.rawValue == activeProvider
                              ? "checkmark.circle.fill" : "circle")
                            .foregroundStyle(provider.rawValue == activeProvider
                                             ? Color.accentColor : .secondary)
                            .font(.system(size: 14))
                    }
                    .buttonStyle(.plain)
                    .disabled(!statusFor(provider).canActivate
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
                            Text(provider.statusLabel(for: statusFor(provider), i18n: i18n))
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
            Section(i18n.t("desktop.llmSettings.statusSection")) {
                Toggle(selectedProvider.activationToggleLabel(i18n), isOn: activeBinding)
                    .disabled(!statusFor(selectedProvider).canActivate
                              && activeProvider != selectedProvider.rawValue)

                providerLinks

                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 6) {
                        statusIndicator(for: selectedProvider, dotSize: 12)
                        Text(selectedProvider.statusLabel(for: statusFor(selectedProvider), i18n: i18n))
                            .foregroundStyle(.secondary)
                    }
                    .animation(
                        reduceMotion ? nil : .easeInOut(duration: 0.2),
                        value: statusFor(selectedProvider))
                    if let error = statusErrors[selectedProvider],
                       statusFor(selectedProvider) != .online {
                        // Per Mac convention (Mail, Internet Accounts) the dot
                        // carries the colour signal; the error text is .secondary
                        // so we don't have two channels for one signal. Rendered
                        // as markdown so a backtick `command` shows inline
                        // monospace (not literal backticks); selectable so the
                        // whole explanation is copyable.
                        Text(LocalizedStringKey(error))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .textSelection(.enabled)
                            .fixedSize(horizontal: false, vertical: true)
                        // Any shell command in the message (today only Ollama's
                        // `ollama pull …` / `ollama serve`) gets a monospace,
                        // one-click-copyable row — reusing the popover's silent
                        // copy idiom.
                        ForEach(LLMValidator.shellCommands(in: error), id: \.self) { command in
                            HStack(spacing: 6) {
                                Text(command)
                                    .font(.system(.caption, design: .monospaced))
                                    .textSelection(.enabled)
                                    .padding(.vertical, 2)
                                    .padding(.horizontal, 6)
                                    .background(
                                        Color(nsColor: .quaternarySystemFill),
                                        in: RoundedRectangle(cornerRadius: 5))
                                CopyButton(
                                    text: command,
                                    label: i18n.t("desktop.llmSettings.copyCommand"))
                                Spacer(minLength: 0)
                            }
                        }
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
                if newValue { activate(selectedProvider) }
                // Unchecking the active provider is a no-op — one must always be active.
            }
        )
    }

    // MARK: - API Key section

    @State private var apiKeyInputs: [LLMProvider: String] = [:]
    @State private var apiKeyRevealed: [LLMProvider: Bool] = [:]
    @FocusState private var apiKeyFocused: Bool

    private var apiKeySection: some View {
        Section(i18n.t("desktop.llmSettings.apiKeySection")) {
            HStack {
                // `.labelsHidden()` stops SwiftUI's `.formStyle(.grouped)`
                // from injecting an inline "API Key" label that reflows the
                // row when the revealed plaintext is wide. Section header
                // already names the field; redundant inline label was the
                // source of the height jump on eye-toggle.
                let revealed = apiKeyRevealed[selectedProvider, default: false]
                if revealed {
                    TextField(i18n.t("desktop.llmSettings.apiKeyPlaceholder"), text: apiKeyBinding)
                        .textFieldStyle(.roundedBorder)
                        .focused($apiKeyFocused)
                        .labelsHidden()
                        .lineLimit(1)
                } else {
                    SecureField(i18n.t("desktop.llmSettings.apiKeyPlaceholder"), text: apiKeyBinding)
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
                      ? i18n.t("desktop.llmSettings.hideApiKey")
                      : i18n.t("desktop.llmSettings.showApiKey"))

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
                    .help(i18n.t("desktop.llmSettings.clearApiKey"))
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
            // Validate the *persisted* key, never the in-memory value — a green
            // "Online" must not outrun what actually reached the Keychain. If the
            // write silently fails (e.g. a future sandbox/entitlement regression),
            // the read-back mismatches and we reflect real Keychain state instead
            // of flashing green for a key that isn't stored.
            let saved = KeychainHelper.set(provider: keychainKey, value: value)
            if saved, KeychainHelper.get(provider: keychainKey) == value {
                applyPresenceAndCache(provider: selectedProvider)
                kickOffValidation(provider: selectedProvider, key: value)
            } else {
                applyPresenceAndCache(provider: selectedProvider)
            }
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
        Section(i18n.t("desktop.llmSettings.serverSection")) {
            if let helper = selectedProvider.helperText(i18n) {
                Text(helper)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            HStack {
                Text(i18n.t("desktop.llmSettings.serverURL"))
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

        return Section(i18n.t("desktop.llmSettings.modelSection")) {
            Picker(i18n.t("desktop.llmSettings.modelSection"), selection: modelBinding) {
                ForEach(models, id: \.self) { model in
                    Text(model).tag(model)
                }
                Divider()
                Text(i18n.t("desktop.llmSettings.customModelOption")).tag("__custom__")
            }

            if !isKnown || useCustomModel {
                TextField(i18n.t("desktop.llmSettings.customModelPlaceholder"), text: $customModelText)
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
                Text(i18n.t("desktop.llmSettings.temperatureLabel"))
                Spacer()
                Text(temperature.formatted(.number.precision(.fractionLength(1))))
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
            }
            Slider(value: $temperature, in: 0...1, step: 0.1)
            Text(i18n.t("desktop.llmSettings.temperatureHint"))
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
                Text(i18n.t("desktop.llmSettings.concurrencyLabel"))
                Spacer()
                Text("\(Int(concurrency))")
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
            }
            Slider(value: $concurrency, in: 1...10, step: 1)
            Text(i18n.t("desktop.llmSettings.concurrencyHint"))
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
        Section(i18n.t("desktop.llmSettings.azureSection")) {
            TextField(i18n.t("desktop.llmSettings.azureEndpoint"), text: $azureEndpoint)
                .textFieldStyle(.roundedBorder)
                .focused($azureEndpointFocused)
                .onSubmit { revalidateAzure() }
            TextField(i18n.t("desktop.llmSettings.azureDeployment"), text: $azureDeployment)
                .textFieldStyle(.roundedBorder)
            TextField(i18n.t("desktop.llmSettings.azureAPIVersion"), text: $azureAPIVersion)
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
                Link(i18n.t("desktop.llmSettings.pricingLink"), destination: pricing)
            }
            if let console = links.console {
                Link(i18n.t(links.consoleLabel), destination: console)
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
        return String(format: i18n.t("desktop.llmSettings.lastVerified"), relative)
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

    /// Refresh the UI status for the visible providers (selected + active)
    /// from Keychain + verdict cache. Pure presence-and-cache read — never
    /// makes a network call.
    ///
    /// Lazy-load contract (sandbox walk #7): we only touch Keychain for
    /// the provider the user is currently viewing (`selectedProvider`) and
    /// the one analysis will use (`activeProvider`). Other providers' rows
    /// in the sidebar keep whatever default they have — typically
    /// `.notSetUp` until the user clicks into them, at which point the
    /// `onChange(of: selectedProvider)` path runs presence-and-cache
    /// against the newly-selected row's key.
    private func refreshStatuses() {
        applyPresenceAndCache(provider: selectedProvider)
        if let active = LLMProvider(rawValue: activeProvider),
           active != selectedProvider {
            applyPresenceAndCache(provider: active)
        }
    }

    /// Set `provider` active (sidebar radio / detail-pane toggle), if it
    /// `canActivate`. Single home for the activation contract, shared by both
    /// controls. Gated on `canActivate` (key present + not known-bad), NOT a
    /// live `.online`: an out-of-credit or momentarily-unreachable provider is
    /// still a legitimate choice (Defect L / "never gate Run on a stale
    /// light"). A `.notSetUp` / `.invalid` / `.checking` provider can't be
    /// activated — its control is `.disabled`, so the click is visibly
    /// unavailable rather than silently swallowed (the old guard's failure
    /// mode). `syncGlobalModel` keeps provider+model coherent at activation.
    private func activate(_ provider: LLMProvider) {
        guard statusFor(provider).canActivate else { return }
        activeProvider = provider.rawValue
        syncGlobalModel()
        refreshStatuses()
        NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
    }

    /// Eager board: paint EVERY provider row from Keychain presence + verdict
    /// cache. Pure presence-and-cache read — no network. Replaces the lazy
    /// selected+active-only read on Settings open so no row is grey-by-laziness.
    /// Reading all keys is safe: the data-protection keychain grants
    /// own-access-group reads by Team ID without a prompt on a team-signed
    /// build (see `onAppear`).
    private func refreshAllStatuses() {
        for provider in LLMProvider.allCases {
            applyPresenceAndCache(provider: provider)
        }
    }

    /// Eager board: silently reconfirm every keyed provider whose cached
    /// verdict is stale (older than `cacheTTL`). "Silent" = keep showing the
    /// already-painted cached value instead of flashing `.checking`, so the
    /// lights settle into present-tense truth with no spinner wall (the
    /// "magically reconfirmed" behaviour). A provider with a key but NO cache
    /// gets a visible `.checking` — there's genuinely nothing to show yet.
    /// Ollama keeps selected/active scoping: probing localhost for an unused
    /// provider just generates `Socket SO_ERROR ::1.11434` console noise.
    private func revalidateAllStale() {
        for provider in LLMProvider.allCases {
            if provider == .ollama {
                let activeOllama = LLMProvider(rawValue: activeProvider) == .ollama
                guard provider == selectedProvider || activeOllama else { continue }
                let urlStr = ollamaURL.trimmingCharacters(in: .whitespacesAndNewlines)
                if !urlStr.isEmpty {
                    kickOffValidation(provider: .ollama, key: "")
                }
                continue
            }
            guard let kc = provider.keychainProvider,
                  let stored = KeychainHelper.get(provider: kc),
                  !stored.isEmpty
            else { continue }
            if LLMValidator.cacheIsFresh(
                provider: provider, key: stored, ttl: Self.cacheTTL)
            {
                continue
            }
            let hasCache = LLMValidator.cachedVerdict(
                provider: provider, key: stored) != nil
            kickOffValidation(provider: provider, key: stored, silent: hasCache)
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
                ? i18n.t("desktop.llmSettings.revalidating")
                : nil
        } else {
            // Key present but no cached verdict yet. Leave the existing status
            // (typically `.notSetUp`) — a follow-up `kickOffValidation` paints
            // the real state. Two callers reach here: `saveAPIKey` (kickoff in
            // the same tick → only `.checking` renders) and the eager board's
            // `revalidateAllStale` (a separate function, but it runs
            // synchronously in the same `.onAppear` pass and calls
            // `kickOffValidation(silent: false)` for a keyed-but-uncached
            // provider, so `.checking` still wins the batched render).
            statusErrors[provider] = nil
        }
    }

    /// Kick off background validation for the currently selected provider
    /// (and Ollama if it's the active provider, since the sidecar will
    /// route to it on the next pipeline run). Skips cloud providers whose
    /// verdict cache is fresher than `cacheTTL`.
    ///
    /// Per-provider scoping (sandbox walk #7 + #16): the previous
    /// `revalidateAll()` hit Keychain for every cloud provider on every
    /// Settings open, producing the 3× password prompt cascade. Ollama
    /// also fired its localhost probe regardless of active selection,
    /// generating "Socket SO_ERROR ::1.11434" console noise even when
    /// the user picked Claude.
    private func revalidateSelectedIfNeeded() {
        let provider = selectedProvider
        if provider == .ollama {
            // Probe localhost only when the user actually cares — looking
            // at the Ollama row, or it's the active provider.
            let active = LLMProvider(rawValue: activeProvider) == .ollama
            guard provider == selectedProvider || active else { return }
            let urlStr = ollamaURL.trimmingCharacters(in: .whitespacesAndNewlines)
            if !urlStr.isEmpty {
                kickOffValidation(provider: .ollama, key: "")
            }
            return
        }
        guard let keychainKey = provider.keychainProvider,
              let stored = KeychainHelper.get(provider: keychainKey),
              !stored.isEmpty
        else { return }
        if LLMValidator.cacheIsFresh(
            provider: provider, key: stored, ttl: Self.cacheTTL)
        {
            Self.logger.debug(
                "skip revalidate \(provider.rawValue, privacy: .public) — cache fresh")
            return
        }
        kickOffValidation(provider: provider, key: stored)
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
    private func kickOffValidation(
        provider: LLMProvider, key: String, silent: Bool = false
    ) {
        validationTasks[provider]?.cancel()
        // Non-silent (explicit user action — a paste, or no cache to show):
        // show the .checking spinner from the moment validation kicks off, even
        // if the cache pre-set us to .online a tick earlier. SwiftUI batches
        // these state writes within the same synchronous tick, so the rendered
        // transition is dot → spinner → settled, never the misleading
        // green-flash-red on a rotated key.
        // Silent (eager background reconfirm with a cached value already
        // painted): keep showing the cache and let the network result update it
        // when it lands — no spinner wall on Settings open. Companion to the
        // "applyPresenceAndCache never sets .checking" invariant.
        if !silent {
            statuses[provider] = .checking
        }
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

            // The 402-masking decision lives in LLMValidator.resolveStatus
            // (pure + unit-tested): a transient .unavailable defers to the
            // cache (offline survival); a definitive observation — including a
            // fresh .outOfCredit — wins and is shown through any cached green.
            let cached = LLMValidator.cachedVerdict(provider: provider, key: key)
            let resolved = LLMValidator.resolveStatus(observed: status, cached: cached)
            statuses[provider] = resolved
            if resolved != status {
                // Fell back to a cached verdict (transient failure). Surface the
                // network error so the user knows we tried; a cached .invalid
                // shows the "revalidating" hint instead.
                statusErrors[provider] =
                    (cached == .invalid)
                    ? i18n.t("desktop.llmSettings.revalidating")
                    : error  // typically "No network connection" / "rate-limited"
                Self.logger.info(
                    "validate \(provider.rawValue, privacy: .public) → \(String(describing: resolved), privacy: .public) (cache fallback, network said \(String(describing: status), privacy: .public))"
                )
            } else {
                // Definitive observation — record it and show its own error.
                statusErrors[provider] = error
                LLMValidator.recordVerdict(provider: provider, key: key, status: status)
                Self.logger.info(
                    "validate \(provider.rawValue, privacy: .public) → \(String(describing: status), privacy: .public)"
                )
            }
        }
    }
}

/// Small silent copy-to-clipboard button matching the diagnostic popover's idiom
/// (`ProjectDiagnosticPopover`): a `.bordered .small` `doc.on.doc` icon that copies
/// WITHOUT a "Copied" flash — the native Mac pattern (Finder, Safari "Copy URL").
/// Used for copyable CLI commands in the LLM status area.
private struct CopyButton: View {
    let text: String
    let label: String
    var body: some View {
        Button {
            let pb = NSPasteboard.general
            pb.clearContents()
            pb.setString(text, forType: .string)
        } label: {
            Image(systemName: "doc.on.doc")
        }
        .buttonStyle(.bordered)
        .controlSize(.small)
        .help(label)
        .accessibilityLabel(label)
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
