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
/// - **A new class of RECIPIENT appears** — not just a new provider of the
///   same kind. v2 is the worked example: connecting an MCP agent sends
///   quotes to that agent's own vendor, which is a different company, under
///   different terms, at a different moment (when the researcher asks a
///   question, not when the analysis runs).
/// - **A claim the sheet made turns out to be false.** v3 is the worked
///   example: everyone acknowledged a sheet that said participant names stay
///   on the device, so everyone sees the corrected one.
///
/// Do NOT increment for:
/// - Copy tweaks or layout changes
/// - New local-only features (e.g. Ollama improvements)
/// - Bug fixes
struct AIConsentView: View {

    /// Bump this when disclosure content materially changes.
    /// The dialog re-appears for users who acknowledged a lower version.
    ///
    /// **v2 (0.23.0, 1 Aug 2026)** — agent access. The extension collapsed a
    /// five-step manual config into one button, removing the friction that
    /// was implicitly doing the disclosure work, so the disclosure has to do
    /// it explicitly instead.
    ///
    /// **v3 (27 Nov 2026)** — two claims on v2 were false. "Your data is not
    /// used to train AI models" is not ours to promise (a provider's own terms
    /// decide, and Gemini's unpaid tier may use what it is sent), and
    /// "participant names … always stay on your device" was wrong: speaker
    /// identification sends the transcript, names included, and the Mac app has
    /// no redaction control. v3 also names the discussion guide, which is sent,
    /// and the hosts models and the report typeface come from.
    static let currentVersion = 3

    /// Has the person acknowledged the disclosure as it stands? The decision
    /// that shows the first-run sheet (`ContentView.hasConsent`). Other gates
    /// (`PipelineRunner`, `NewsFetcher`, `StandbySidecar`) compare against
    /// `currentVersion` themselves and follow a bump the same way.
    static func isAcknowledged(_ acknowledgedVersion: Int) -> Bool {
        acknowledgedVersion >= currentVersion
    }

    /// Should an open sheet stay up once the stored version changes? A bump
    /// raises the first-run sheet in every open window; when the person answers
    /// it in one, the others close without recording anything, so a stale
    /// window cannot overwrite the analytics answer or log a second consent.
    /// The review-mode sheet (Bristlenose ▸ AI & Privacy…) is the person's own
    /// and stays.
    static func sheetStaysOpen(acknowledgedVersion: Int, isReviewMode: Bool) -> Bool {
        isReviewMode || !isAcknowledged(acknowledgedVersion)
    }

    @EnvironmentObject var i18n: I18n
    @EnvironmentObject var ollamaDownload: OllamaDownloadModel
    @AppStorage("aiConsentVersion") private var consentVersion: Int = 0
    @AppStorage("activeProvider") private var activeProvider: String = ActiveProviderChoice.unset
    @AppStorage("llmModel_local") private var ollamaModel: String = ""

    /// When true, shows "Done" instead of "Continue" (re-access mode).
    var isReviewMode: Bool = false

    /// Dismiss action — provided by the .sheet binding in the parent.
    var onDismiss: () -> Void

    /// The anonymous-counts answer (`docs/private/design-news-and-counts.md`
    /// D1, path B). **Off until ticked**: an explicit choice, never a
    /// pre-ticked box. Written as `true` or `false` when the disclosure is
    /// answered, by either button. Shown on first run only, not in review mode:
    /// existing users are not prompted unless the disclosure version
    /// (`currentVersion`) is bumped, which shows the whole disclosure again;
    /// otherwise they change it in Settings ▸ General. Adding this choice is
    /// not a disclosure change, so `currentVersion` is untouched.
    @State private var sendCounts = NewsPreferences.countsChoiceStartsOn(
        in: .standard, isForced: NewsPreferences.isManaged)

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            header
            introText
            sentToCloudBox
            staysLocalBox
            // AFTER the stays-local box, deliberately: it is the exception to
            // BOTH boxes, and an exception has to follow the claim it
            // qualifies. Above the box it read as a footnote to the cloud
            // list, leaving the box's "your edits, tags… — unless you turn
            // on Agent Access" six lines below the line that explains it.
            agentAccessText
            providersRow
            responsibilityText
            hostsText

            if !isReviewMode && NewsKeys.isLive {
                countsChoice
            }

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
                bulletItem(i18n.t("desktop.aiConsent.sentItem4"))
            }
            .padding(.top, 4)
        } label: {
            Label(i18n.t("desktop.aiConsent.sentToCloudLabel"), systemImage: "arrow.up.doc")
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(i18n.t("desktop.aiConsent.sentSummary"))
    }

    // MARK: - Agent access (the second, conditional recipient — v2)

    /// A SEPARATE line rather than another bullet in the box above, because
    /// it is a different recipient: the box is headed "sent to your chosen
    /// cloud provider", and an agent's vendor is neither chosen there nor the
    /// same company. Conditional (off by default, per project) and triggered
    /// by asking rather than by analysing, so it cannot sit in a list of
    /// things every run sends.
    private var agentAccessText: some View {
        Text(i18n.t("desktop.aiConsent.agentAccess"))
            .font(.callout)
            .foregroundStyle(.secondary)
            .fixedSize(horizontal: false, vertical: true)
    }

    // MARK: - Stays local

    private var staysLocalBox: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 4) {
                bulletItem(i18n.t("desktop.aiConsent.localItem1"))
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

    // MARK: - Download hosts and the report typeface

    /// Who else sees the Mac's IP address, and the policy that says the rest.
    /// The link is an `AttributedString` run (`GeneralSettingsView.explanation`),
    /// so nothing a translator writes can become a link.
    private var hostsText: some View {
        Text(GeneralSettingsView.explanation(
            i18n.t("desktop.aiConsent.hostsNote"),
            link: i18n.t("desktop.aiConsent.privacyLink"),
            destination: NewsPreferences.privacyURL))
            .font(.caption)
            .foregroundStyle(.secondary)
            .fixedSize(horizontal: false, vertical: true)
    }

    // MARK: - Anonymous counts (first run only)

    /// A checkbox, because it is a yes/no the person answers on their way
    /// past, and the stock control for that in a dialog is a checkbox. Its
    /// label and explanation wrap (a control's label never truncates,
    /// `docs/design-control-labels.md`); the window is a fixed 520 pt wide.
    private var countsChoice: some View {
        VStack(alignment: .leading, spacing: 4) {
            Toggle(isOn: $sendCounts) {
                Text(i18n.t("desktop.aiConsent.countsChoice"))
                    .fixedSize(horizontal: false, vertical: true)
            }
            .toggleStyle(.checkbox)
            .disabled(NewsPreferences.isManaged(NewsPreferences.countsKey))
            Text(i18n.t("desktop.aiConsent.countsExplain"))
                .fixedSize(horizontal: false, vertical: true)
                .font(.caption)
            .foregroundStyle(.secondary)
            .padding(.leading, 20)   // under the label, not the box
            Link(i18n.t("desktop.news.whatsSent"), destination: NewsPreferences.analyticsURL)
                .font(.caption)
                .padding(.leading, 20)
        }
    }

    /// Both buttons answer the disclosure, so both record the counts choice.
    private func recordCountsChoice() {
        // Not shown, not answered: a hidden box must not record a "no".
        guard !isReviewMode, NewsKeys.isLive else { return }
        NewsPreferences.recordCountsAnswer(sendCounts, in: .standard,
                                           isForced: NewsPreferences.isManaged)
    }

    // MARK: - Buttons

    private var buttonBar: some View {
        HStack(alignment: .firstTextBaseline) {
            // Stay local: apply the RAM-aware default model, activate Ollama,
            // and pull the model ambiently (toolbar pill) — no blocking
            // picker. Micro-prefs (model choice, concurrency) live in Settings.
            // The size hint under the button discloses the multi-GB first-run
            // pull before the click (replacing the line the removed
            // OllamaSetupSheet used to show).
            VStack(alignment: .leading, spacing: 2) {
                Button(i18n.t("desktop.aiConsent.useOllama")) {
                    recordCountsChoice()
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
                recordCountsChoice()
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
            "provider": activeProvider.isEmpty ? "none" : activeProvider,
            "action": action,
        ]

        var log = UserDefaults.standard.array(forKey: "consentLog")
            as? [[String: String]] ?? []
        log.append(entry)
        UserDefaults.standard.set(log, forKey: "consentLog")
    }
}
