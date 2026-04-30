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
    @AppStorage("aiConsentVersion") private var consentVersion: Int = 0
    @AppStorage("activeProvider") private var activeProvider: String = "anthropic"
    @AppStorage("llmModel_local") private var ollamaModel: String = ""
    @State private var showingOllamaSetup = false

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
            ollamaCallout
            responsibilityText

            Spacer(minLength: 8)

            buttonBar
        }
        .padding(24)
        .frame(width: 520)
        .fixedSize(horizontal: false, vertical: true)
        .sheet(isPresented: $showingOllamaSetup) {
            OllamaSetupSheet(
                onComplete: { chosenTag in
                    // Record consent BEFORE posting the prefs change.
                    // The prefs notification can drive ServeManager to
                    // start; consent must be on disk first so the
                    // gate at ContentView.handleSelectionChange sees
                    // the new version.
                    recordConsent(action: "ollama")
                    ollamaModel = chosenTag
                    activeProvider = LLMProvider.ollama.rawValue
                    NotificationCenter.default.post(
                        name: .bristlenosePrefsChanged, object: nil)
                    showingOllamaSetup = false
                    onDismiss()
                },
                onCancel: {
                    showingOllamaSetup = false
                }
            )
        }
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

    // MARK: - Ollama callout

    private var ollamaCallout: some View {
        HStack(spacing: 8) {
            Image(systemName: LLMProvider.ollama.iconName)
                .foregroundStyle(.green)
            Text(i18n.t("desktop.aiConsent.ollamaCallout"))
                .font(.callout)
        }
        .padding(8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.green.opacity(0.08), in: RoundedRectangle(cornerRadius: 6))
    }

    // MARK: - Researcher responsibility

    private var responsibilityText: some View {
        Text(i18n.t("desktop.aiConsent.researcherResponsibility"))
            .font(.caption)
            .foregroundStyle(.secondary)
    }

    // MARK: - Buttons

    private var buttonBar: some View {
        HStack {
            // Beat 3b: replaces the old direct activeProvider write with
            // a guided sheet that picks a model + downloads it. Consent
            // recording moves into the sheet's onComplete success path so
            // a mid-setup cancel leaves the user unconsented.
            Button(i18n.t("desktop.aiConsent.useOllama")) {
                showingOllamaSetup = true
            }
            .buttonStyle(.borderless)

            Spacer()

            Button(isReviewMode
                   ? i18n.t("desktop.aiConsent.done")
                   : i18n.t("desktop.aiConsent.continue")) {
                if !isReviewMode {
                    recordConsent(action: "continue")
                }
                onDismiss()
            }
            .buttonStyle(.borderedProminent)
            .keyboardShortcut(.defaultAction)
        }
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
