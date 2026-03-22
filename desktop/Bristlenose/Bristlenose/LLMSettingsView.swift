import SwiftUI

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

    @AppStorage("activeProvider") private var activeProvider: String = "anthropic"
    @State private var selectedProvider: LLMProvider = .claude
    @State private var statuses: [LLMProvider: ProviderStatus] = [:]

    var body: some View {
        HSplitView {
            providerList
                .frame(minWidth: 200, maxWidth: 200)

            providerDetail
                .frame(minWidth: 440)
        }
        .frame(width: 660, height: 460)
        .onAppear {
            if let active = LLMProvider(rawValue: activeProvider) {
                selectedProvider = active
            }
            refreshStatuses()
        }
    }

    // MARK: - Left sidebar

    private var providerList: some View {
        VStack(spacing: 0) {
            List(LLMProvider.allCases, selection: $selectedProvider) { provider in
                HStack(spacing: 8) {
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

                    Image(provider.iconAssetName)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(width: 16, height: 16)
                        .opacity(0.55)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(provider.displayName)
                        HStack(spacing: 4) {
                            Circle()
                                .fill(statusFor(provider).dotColor)
                                .frame(width: 6, height: 6)
                            Text(statusFor(provider).label)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                .tag(provider)
            }

            Divider()

            HStack {
                Button(action: {}) {
                    Image(systemName: "plus")
                }
                .buttonStyle(.borderless)
                .disabled(true)
                .help("Multiple keys per provider — coming soon")

                Spacer()
            }
            .padding(6)
        }
    }

    // MARK: - Right detail pane

    private var providerDetail: some View {
        Form {
            Section {
                Toggle("Use this provider", isOn: activeBinding)
                    .disabled(!statusFor(selectedProvider).isConfigured
                              && activeProvider != selectedProvider.rawValue)

                HStack(spacing: 6) {
                    Text("Status:")
                    Circle()
                        .fill(statusFor(selectedProvider).dotColor)
                        .frame(width: 8, height: 8)
                    Text(statusFor(selectedProvider).label)
                        .foregroundStyle(.secondary)
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

            if let helper = selectedProvider.helperText {
                Section {
                    Text(helper)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
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

    private var apiKeySection: some View {
        Section("API Key") {
            HStack {
                let revealed = apiKeyRevealed[selectedProvider, default: false]
                if revealed {
                    TextField("API Key", text: apiKeyBinding)
                        .textFieldStyle(.roundedBorder)
                } else {
                    SecureField("API Key", text: apiKeyBinding)
                        .textFieldStyle(.roundedBorder)
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
                    Button("Clear") {
                        clearAPIKey()
                    }
                }
            }
            .onAppear { loadAPIKey() }
            .onChange(of: selectedProvider) { _, _ in loadAPIKey() }
            .onSubmit { saveAPIKey() }
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
        } else {
            KeychainHelper.set(provider: keychainKey, value: value)
        }
        refreshStatuses()
        NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
    }

    private func clearAPIKey() {
        guard let keychainKey = selectedProvider.keychainProvider else { return }
        KeychainHelper.delete(provider: keychainKey)
        apiKeyInputs[selectedProvider] = ""
        refreshStatuses()
        NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
    }

    // MARK: - Ollama section

    @AppStorage("localURL") private var ollamaURL: String = "http://localhost:11434/v1"

    private var ollamaSection: some View {
        Section("Server URL") {
            TextField("URL", text: $ollamaURL)
                .textFieldStyle(.roundedBorder)
                .onSubmit {
                    refreshStatuses()
                    NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
                }
        }
    }

    // MARK: - Model section

    @AppStorage("llmModel") private var globalModel: String = "claude-sonnet-4-20250514"
    @State private var useCustomModel: Bool = false
    @State private var customModelText: String = ""

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
                    .onSubmit {
                        setModel(customModelText)
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
                Text(String(format: "%.1f", temperature))
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

    private var azureSection: some View {
        Section("Azure Settings") {
            TextField("Endpoint URL", text: $azureEndpoint)
                .textFieldStyle(.roundedBorder)
            TextField("Deployment name", text: $azureDeployment)
                .textFieldStyle(.roundedBorder)
            TextField("API version", text: $azureAPIVersion)
                .textFieldStyle(.roundedBorder)
        }
        .onChange(of: azureEndpoint) { _, _ in
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
        .onChange(of: azureDeployment) { _, _ in
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
    }

    // MARK: - Status helpers

    private func statusFor(_ provider: LLMProvider) -> ProviderStatus {
        statuses[provider, default: .notSetUp]
    }

    /// Refresh status for all providers based on Keychain state.
    /// Does not perform network validation (that would be slow in Settings).
    /// Full validation happens on first API call / `bristlenose doctor`.
    private func refreshStatuses() {
        for provider in LLMProvider.allCases {
            if provider == .ollama {
                // Ollama: mark as online if URL is set. True connectivity
                // check would require a network call.
                statuses[provider] = .online
            } else if let key = provider.keychainProvider,
                      KeychainHelper.get(provider: key) != nil {
                statuses[provider] = .online
            } else {
                statuses[provider] = .notSetUp
            }
        }
    }
}
