import SwiftUI

/// AI data disclosure dialog required by Apple Guideline 5.1.2(i).
///
/// Shown as a sheet on first launch (or when consent version bumps).
/// Non-dismissable on first run — user must actively acknowledge.
///
/// Re-accessible from Bristlenose menu > AI & Privacy... (shows "Done"
/// instead of "Continue" since consent is already recorded).
///
/// ## Consent version policy
///
/// Increment `currentVersion` when:
/// - A new cloud LLM provider is added
/// - The categories of data sent to LLMs change
/// - A provider's data handling terms materially change
///
/// Do NOT increment for:
/// - Copy tweaks or layout changes
/// - New local-only features (e.g. Ollama improvements)
/// - Bug fixes
struct AIConsentView: View {

    /// Bump this when disclosure content materially changes.
    /// The dialog re-appears for users who acknowledged a lower version.
    static let currentVersion = 1

    @EnvironmentObject var i18n: I18n
    @EnvironmentObject var ollamaDownload: OllamaDownloadModel
    @AppStorage("aiConsentVersion") private var consentVersion: Int = 0
    @AppStorage("activeProvider") private var activeProvider: String = "anthropic"
    @AppStorage("llmModel_local") private var ollamaModel: String = ""

    /// When true, shows "Done" instead of "Continue" (re-access mode).
    var isReviewMode: Bool = false

    /// Dismiss action — provided by the .sheet binding in the parent.
    var onDismiss: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            header
            introText
            sentToCloudBox
            staysLocalBox
            providersRow
            responsibilityText

            Spacer(minLength: 8)

            buttonBar
        }
        .padding(24)
        .frame(width: 520)
        .fixedSize(horizontal: false, vertical: true)
    }

    // MARK: - Header

    private var header: some View {
        HStack(spacing: 12) {
            Image(systemName: "brain.head.profile")
                .font(.largeTitle)
                .foregroundStyle(.secondary)
            Text(i18n.t("desktop.aiConsent.title"))
                .font(.title2)
                .fontWeight(.semibold)
        }
    }

    // MARK: - Intro

    private var introText: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(i18n.t("desktop.aiConsent.intro"))
                .font(.body)
            Text(i18n.t("desktop.aiConsent.notUsedForTraining"))
                .font(.callout)
                .foregroundStyle(.secondary)
        }
    }

    // MARK: - Sent to cloud

    private var sentToCloudBox: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 4) {
                bulletItem(i18n.t("desktop.aiConsent.sentItem1"))
                bulletItem(i18n.t("desktop.aiConsent.sentItem2"))
                bulletItem(i18n.t("desktop.aiConsent.sentItem3"))
            }
            .padding(.top, 4)
        } label: {
            Label(i18n.t("desktop.aiConsent.sentToCloudLabel"), systemImage: "arrow.up.doc")
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(i18n.t("desktop.aiConsent.sentSummary"))
    }

    // MARK: - Stays local

    private var staysLocalBox: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 4) {
                bulletItem(i18n.t("desktop.aiConsent.localItem1"))
                bulletItem(i18n.t("desktop.aiConsent.localItem2"))
                bulletItem(i18n.t("desktop.aiConsent.localItem3"))
            }
            .padding(.top, 4)
        } label: {
            Label(i18n.t("desktop.aiConsent.staysLocalLabel"), systemImage: "lock.shield")
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(i18n.t("desktop.aiConsent.localSummary"))
    }

    // MARK: - Cloud providers

    private var providersRow: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(i18n.t("desktop.aiConsent.providersIntro"))
                .font(.body)
            HStack(spacing: 16) {
                ForEach(LLMProvider.allCases.filter(\.needsAPIKey)) { provider in
                    Label(provider.displayName, systemImage: provider.iconName)
                        .font(.callout)
                }
            }
        }
    }

    // MARK: - Researcher responsibility

    private var responsibilityText: some View {
        Text(i18n.t("desktop.aiConsent.researcherResponsibility"))
            .font(.caption)
            .foregroundStyle(.secondary)
    }

    // MARK: - Buttons

    private var buttonBar: some View {
        HStack(alignment: .firstTextBaseline) {
            // Stay local: apply the RAM-aware default model, activate Ollama,
            // and pull the model ambiently (toolbar pill) — no blocking
            // picker. Micro-prefs (model choice, temperature) live in Settings.
            // The size hint under the button discloses the multi-GB first-run
            // pull before the click (replacing the line the removed
            // OllamaSetupSheet used to show).
            VStack(alignment: .leading, spacing: 2) {
                Button(i18n.t("desktop.aiConsent.useOllama")) {
                    activateLocalDefault()
                    onDismiss()
                }
                .buttonStyle(.borderless)

                if let sizeHint = ollamaDownloadSizeHint {
                    Text(sizeHint)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            Button(isReviewMode
                   ? i18n.t("desktop.aiConsent.done")
                   : i18n.t("desktop.aiConsent.continue")) {
                activateChosenCloudProviderIfNeeded()
                onDismiss()
            }
            .buttonStyle(.borderedProminent)
            .keyboardShortcut(.defaultAction)
        }
    }

    /// Approximate first-run download size for the RAM-aware default model,
    /// e.g. "~3 GB download". Nil for tags outside the curated catalog (a
    /// DEBUG tag override), so the hint simply doesn't render.
    private var ollamaDownloadSizeHint: String? {
        guard let model = OllamaCatalog.model(for: OllamaCatalog.recommendedTag())
        else { return nil }
        let size = "\(Int(model.weightsGB)) GB"
        return String(format: i18n.t("desktop.aiConsent.ollamaDownloadSize"), size)
    }

    // MARK: - Activation

    /// Stay-local path. Resolves the RAM-aware default, activates Ollama via
    /// the canonical triad (activeProvider → global model → prefs notify),
    /// records consent, and kicks off the ambient pull.
    private func activateLocalDefault() {
        let tag = OllamaCatalog.recommendedTag()
        // Order: provider + model writes FIRST (recordConsent reads
        // `activeProvider` for the audit trail), then sync the global model
        // so ServeManager routes to it, then consent, then notify, then pull.
        activeProvider = LLMProvider.ollama.rawValue
        ollamaModel = tag
        syncGlobalModel(for: .ollama)
        recordConsent(action: "ollama")
        NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        // Re-entry safe: start(tag:) cancels any in-flight pull before
        // launching, so a double-tap before dismissal can't race two pulls.
        ollamaDownload.start(tag: tag)
    }

    /// Continue / Done path. Runs the same decision the Settings "Use this
    /// provider" toggle makes: if the active provider is local / unconfigured
    /// and a validated cloud provider exists, activate it via the canonical
    /// triad. Never overrides a deliberate, working cloud choice. On true
    /// first run (no validated cloud) it just records consent and keeps the
    /// cloud default.
    private func activateChosenCloudProviderIfNeeded() {
        let statuses = ConsentActivation.cloudStatuses()
        let activeHasKey = ConsentActivation.hasStoredKey(forActive: activeProvider)
        let target = ConsentActivation.resolve(
            active: activeProvider, activeHasKey: activeHasKey, statuses: statuses)

        if let target {
            activeProvider = target.rawValue
            syncGlobalModel(for: target)
        }

        // Record consent on first acknowledgement; re-record when a re-consent
        // pass actually switches the active provider, so the audit `provider`
        // field stays truthful (US-7).
        if !isReviewMode {
            recordConsent(action: "continue")
        } else if target != nil {
            recordConsent(action: "switch")
        }

        if target != nil {
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
    }

    /// Mirror the canonical `syncGlobalModel()` from LLMSettingsView: write the
    /// newly-active provider's per-provider model into the global `llmModel`
    /// key so ServeManager injects the right model. Without this the Continue
    /// path would reproduce the same provider/model mismatch class of bug it
    /// exists to fix.
    private func syncGlobalModel(for provider: LLMProvider) {
        let model = UserDefaults.standard.string(forKey: "llmModel_\(provider.rawValue)")
            ?? provider.defaultModel
        UserDefaults.standard.set(model, forKey: "llmModel")
    }

    // MARK: - Helpers

    private func bulletItem(_ text: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 6) {
            Text("•").foregroundStyle(.secondary)
            Text(text).font(.callout)
        }
    }

    /// Record consent with an auditable timestamp for DPIA documentation.
    ///
    /// Writes both the simple version integer (for the re-show check) and
    /// a structured log entry (for audit). The log is an array of dictionaries
    /// stored in UserDefaults under "consentLog".
    ///
    /// Consent state is stored in UserDefaults. A user with shell access can
    /// bypass the dialog, but such a user already has direct access to all
    /// research data. The dialog protects against uninformed use, not
    /// determined circumvention.
    private func recordConsent(action: String) {
        consentVersion = Self.currentVersion

        let entry: [String: String] = [
            "version": "\(Self.currentVersion)",
            "date": Date().ISO8601Format(),
            "provider": activeProvider,
            "action": action,
        ]

        var log = UserDefaults.standard.array(forKey: "consentLog")
            as? [[String: String]] ?? []
        log.append(entry)
        UserDefaults.standard.set(log, forKey: "consentLog")
    }
}
