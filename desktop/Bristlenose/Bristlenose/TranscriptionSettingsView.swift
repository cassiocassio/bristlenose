import SwiftUI

/// Settings tab for Whisper transcription engine preferences, and for reading
/// the text on screens shared in recordings (the Screens lens).
///
/// With `BristlenoseFlags.appleSpeech` on, the engine section becomes one
/// behaviour choice, with a Whisper status that speaks only when it has news
/// (`docs/design-apple-first-transcription.md` §4.5, `docs/mockups/transcription-settings-states.html`).
/// Behind the Diagnostics preference sit a read-only line saying what was
/// detected (the backend, MLX on Apple silicon: no choice, the Mac sidecar has
/// only MLX) and the interim model picker. Off, the pane is as it shipped.
struct TranscriptionSettingsView: View {

    @EnvironmentObject var i18n: I18n

    @AppStorage("whisperBackend") private var backend: String = "auto"
    // Interim model picker: fix, don't grow (docs/design-pluggable-llm-routing.md §Interim model pickers).
    @AppStorage("whisperModel") private var model: String = "large-v3-turbo"
    @AppStorage(ScreenTextPreference.key)
    private var readSharedScreens: Bool = ScreenTextPreference.defaultValue
    @AppStorage(BristlenoseFlags.appleSpeechKey) private var appleSpeechFlag: Bool = true
    @AppStorage(DiagnosticsPreference.key)
    private var showDiagnostics: Bool = DiagnosticsPreference.defaultValue
    @ObservedObject private var whisperDownload = WhisperDownloadModel.shared

    /// The flag (read through `@AppStorage` so a flip re-renders), the helper
    /// in this bundle, and macOS 26. Below 26 there is nothing to choose, so the
    /// pane stays as it shipped rather than showing a one-item choice.
    private var appleSpeech: Bool {
        appleSpeechFlag && BristlenoseFlags.appleSpeechAvailable
            && ProcessInfo.processInfo.isOperatingSystemAtLeast(
                OperatingSystemVersion(majorVersion: 26, minorVersion: 0, patchVersion: 0))
    }

    var body: some View {
        Form {
            if appleSpeech {
                // Behind Diagnostics: what was detected (read-only) and the
                // model a run uses, which is still this preference and so must
                // stay reachable. They concern Whisper, so they sit indented in
                // the engine card rather than as peers in cards of their own.
                // They do not dim for the engine choice: Apple's choice still
                // falls back to Whisper, which uses the model. (They are locked
                // while a download runs.)
                EngineSection {
                    if showDiagnostics {
                        detectedBackendRow
                        modelPicker
                    }
                }
            } else {
                backendSection
                modelSection
                // Whisper downloads in the background from launch, so its
                // Download Now / Stop / status row is here without the Apple
                // choice too. Download Now is not held by the 10 GB floor.
                Section { WhisperStatusRow(download: whisperDownload) }
                    .task { await whisperDownload.refresh() }
                    .onChange(of: WhisperStatusRow.heightSignature(of: whisperDownload)) { _, _ in
                        DispatchQueue.main.async { SettingsWindow.shared.refitToContent() }
                    }
            }

            // Read shared screens — the Screens lens's on-device reading of the
            // text participants shared on screen. Here rather than General: like
            // the transcription engine above, it turns what the recordings hold
            // into text, on this Mac. On by default (`ScreenTextPreference`).
            Section {
                Toggle(isOn: $readSharedScreens) {
                    Text(i18n.t("desktop.transcriptionSettings.readScreensLabel"))
                    Text(i18n.t("desktop.transcriptionSettings.readScreensHint"))
                        .foregroundStyle(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 660)
        .onChange(of: readSharedScreens) { _, _ in
            // It becomes BRISTLENOSE_SCREEN_TEXT, so the baked env is stale.
            // Off restarts every serve still reading screens, at once
            // (`ServeEnvStaleness`); on stays lazy, like every other preference.
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
        .onChange(of: backend) { _, _ in
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
            refreshWhisperStatus()
        }
        .onChange(of: model) { _, _ in
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
            refreshWhisperStatus()
        }
    }

    /// Whether Whisper is on disk depends on the backend and model (each resolves
    /// to its own repo), so the status row asks again when either changes. Both
    /// pickers are locked while a download runs, so this never overlaps one.
    private func refreshWhisperStatus() {
        Task { _ = await whisperDownload.refresh() }
    }

    /// What the Mac detected and what that runs, as information, not a choice:
    /// the Mac sidecar carries MLX only, so a picker could only offer an option
    /// that fails (`desktop/bristlenose-sidecar.spec`). A runtime check, not
    /// `#if arch(arm64)`, so the line says what was detected. Shown nowhere
    /// else, so a Mac that is not Apple silicon would show nothing, not a lie.
    @ViewBuilder
    private var detectedBackendRow: some View {
        if Self.isAppleSilicon {
            LabeledContent(i18n.t("desktop.transcriptionSettings.backendDetectedAppleSilicon")) {
                Text("MLX").foregroundStyle(.secondary)
            }
        }
    }

    private static var isAppleSilicon: Bool {
        var value: Int32 = 0
        var size = MemoryLayout<Int32>.size
        return sysctlbyname("hw.optional.arm64", &value, &size, nil, 0) == 0 && value == 1
    }

    private var backendSection: some View {
        Section { backendPicker }
    }

    private var modelSection: some View {
        Section { modelPicker }
    }

    /// A download in flight fetches the model it was started with, so changing
    /// the backend or model under it would leave a progress bar for the old one.
    private var downloading: Bool {
        if case .downloading = whisperDownload.phase { return true }
        return false
    }

    // Help text as an in-cell subtitle (no row keyline) — the
    // System Settings idiom, matching the Appearance toggles.
    //
    // macOS 15-25 only. `faster-whisper` is not offered: the Mac sidecar has MLX
    // alone, so it could only fail. A stored one reads as Auto.
    private var backendPicker: some View {
        Picker(selection: Binding(
            get: { backend == "mlx" ? "mlx" : "auto" },
            set: { backend = $0 }
        )) {
            Text(i18n.t("desktop.transcriptionSettings.backendAuto")).tag("auto")
            Text("MLX").tag("mlx")
        } label: {
            Text(i18n.t("desktop.transcriptionSettings.backendLabel"))
            Text(i18n.t("desktop.transcriptionSettings.backendHint"))
                .foregroundStyle(.secondary)
        }
        .disabled(downloading)
    }

    private var modelPicker: some View {
        Picker(i18n.t("desktop.transcriptionSettings.modelLabel"), selection: $model) {
            Text(i18n.t(
                "desktop.transcriptionSettings.modelRecommended",
                ["model": "large-v3-turbo"]
            )).tag("large-v3-turbo")
            Text("large-v3").tag("large-v3")
            Text("medium").tag("medium")
            Text("small").tag("small")
            Text("tiny").tag("tiny")
        }
        .disabled(downloading)
    }
}

/// "Transcription engine" and the Whisper status (§4.5).
///
/// The choice is read by each run when it starts (`appleSpeechEnvironment`),
/// so it posts no `.bristlenosePrefsChanged`: no serve reads it, and a
/// restart would cold-remount every open report for nothing.
///
/// The status shares the pop-up's row rather than being a row of its own: a
/// grouped Form draws a keyline between rows and `.listRowSeparator(.hidden)`
/// does nothing there (probed on macOS 27). The system primitive is the
/// labelled Picker, kept as it is; a VStack puts the status under it.
/// The status is silent when Whisper is on disk, the expected state, and says
/// only what is news otherwise. Under the Whisper choice it does not repeat the
/// word "Whisper"; under Apple's choice it keeps it, because Whisper is still
/// the fallback and "Not on this Mac" alone would read as Apple's model.
///
/// `dependents` are the Whisper settings, indented to show they belong to
/// Whisper. Nothing here dims under "Apple's speech model": that choice still
/// falls back to Whisper outside its nine languages (and for any session its
/// confidence gate defers), and Whisper uses the model, so Download Now and
/// the model picker must stay reachable.
private struct EngineSection<Dependents: View>: View {
    @EnvironmentObject var i18n: I18n
    @ObservedObject private var download = WhisperDownloadModel.shared
    @AppStorage(TranscriptionEngineChoice.key)
    private var choice: String = TranscriptionEngineChoice.whisperWhenReady.rawValue
    @ViewBuilder var dependents: () -> Dependents

    /// A stored value this build does not know (`whisperOnly`, removed on
    /// 12 Nov 2026) selects the default, as the runs do (`current`), instead of
    /// leaving the pop-up blank.
    private var selection: Binding<String> {
        Binding(
            get: { TranscriptionEngineChoice(rawValue: choice)?.rawValue
                ?? TranscriptionEngineChoice.whisperWhenReady.rawValue },
            set: { choice = $0 }
        )
    }

    /// On disk is the expected state, so the status row is absent, not blank.
    private var showsStatus: Bool {
        if case .onDisk = download.phase { return false }
        return true
    }

    var body: some View {
        Section {
            VStack(alignment: .leading, spacing: 8) {
                Picker(selection: selection) {
                    Text(i18n.t("desktop.transcriptionSettings.engineWhenReady"))
                        .tag(TranscriptionEngineChoice.whisperWhenReady.rawValue)
                    Text(i18n.t("desktop.transcriptionSettings.engineApple"))
                        .tag(TranscriptionEngineChoice.apple.rawValue)
                } label: {
                    Text(i18n.t("desktop.transcriptionSettings.engineLabel"))
                    Text(i18n.t("desktop.transcriptionSettings.engineHint"))
                        .foregroundStyle(.secondary)
                }
                if showsStatus {
                    WhisperStatusRow(
                        download: download,
                        named: choice == TranscriptionEngineChoice.apple.rawValue)
                }
            }
            Group { dependents() }
                .padding(.leading, 20)
        }
        .task { await download.refresh() }
        // The status row appears and goes with the phase, and the hint wraps
        // to the selected item, so the pane re-fits on either.
        .onChange(of: WhisperStatusRow.heightSignature(of: download)) { _, _ in refit() }
        .onChange(of: choice) { _, _ in refit() }
    }

    private func refit() {
        DispatchQueue.main.async { SettingsWindow.shared.refitToContent() }
    }
}

/// Whisper: Download Now / progress with Stop Download / failed with Retry /
/// On this Mac · 1.6 GB. The same `WhisperDownloadModel` as the toolbar pill,
/// so the two can never disagree.
///
/// `named` is the row with its "Whisper" label (the macOS 15 to 25 pane, and
/// the engine row under Apple's choice). Unnamed, the state sits on the left
/// and the button on the right, because the engine pop-up above has already
/// said "Whisper".
private struct WhisperStatusRow: View {
    @EnvironmentObject var i18n: I18n
    @ObservedObject var download: WhisperDownloadModel
    var named: Bool = true

    /// The row's height differs between its states, and in the engine row it is
    /// absent when Whisper is on disk; the Settings package re-fits only on a
    /// tab switch, so the pane asks when this changes
    /// (`SettingsWindow.refitToContent`).
    static func heightSignature(of download: WhisperDownloadModel) -> Int {
        switch download.phase {
        case .downloading: return 4
        case .failed: return 3
        case .missing, .partial: return 2
        case .unknown: return 1
        case .onDisk: return 0
        }
    }

    var body: some View {
        if named { namedRow } else { plainRow }
    }

    // MARK: Pieces shared by both layouts

    private var stopButton: some View {
        Button(i18n.t("desktop.modelDownload.stop")) { download.stop() }
            .fixedSize(horizontal: true, vertical: false)  // the line beside it wraps; the label never truncates
    }

    private var retryButton: some View {
        Button(i18n.t("common.buttons.retry")) { download.downloadNow() }
            .fixedSize(horizontal: true, vertical: false)  // the line beside it wraps; the label never truncates
    }

    private var downloadButton: some View {
        Button(i18n.t("desktop.transcriptionSettings.downloadNow")) { download.downloadNow() }
            .fixedSize(horizontal: true, vertical: false)  // the line beside it wraps; the label never truncates
    }

    private var onDiskText: some View {
        Text(i18n.t("desktop.transcriptionSettings.whisperOnDisk", [
            "size": ByteCountFormatter.string(
                fromByteCount: download.bytesOnDisk, countStyle: .file),
        ]))
        .foregroundStyle(.secondary)
    }

    private var failedText: some View {
        Text(i18n.t(WhisperFailureCause.lineKey(for: download.failureCause)))
            .foregroundStyle(.secondary)
    }

    private var missingText: some View {
        Text(i18n.t("desktop.transcriptionSettings.whisperMissing"))
            .foregroundStyle(.secondary)
    }

    @ViewBuilder
    private func progressBar(width: CGFloat?) -> some View {
        if let fraction = download.fractionDone {
            ProgressView(value: fraction).frame(width: width)
        } else {
            ProgressView().progressViewStyle(.linear).frame(width: width)
        }
    }

    // MARK: With the "Whisper" label

    private var namedRow: some View {
        LabeledContent {
            HStack(spacing: 8) {
                switch download.phase {
                case .downloading:
                    VStack(alignment: .trailing, spacing: 2) {
                        progressBar(width: 160)
                        Text(download.progressLine)
                            .font(.caption)
                            .monospacedDigit()
                            .foregroundStyle(.secondary)
                    }
                    stopButton
                case .onDisk:
                    onDiskText
                case .failed:
                    failedText
                    retryButton
                case .missing, .partial:
                    missingText
                    downloadButton
                case .unknown:
                    // Asking the sidecar takes a moment; say so, not a blank.
                    ProgressView().controlSize(.small)
                        .accessibilityLabel(i18n.t("desktop.transcriptionSettings.whisperChecking"))
                }
            }
        } label: {
            Text(i18n.t("desktop.transcriptionSettings.whisperLabel"))
        }
    }

    // MARK: Without it: state left, button right

    private var plainRow: some View {
        HStack(alignment: .center, spacing: 12) {
            switch download.phase {
            case .downloading:
                VStack(alignment: .leading, spacing: 2) {
                    progressBar(width: nil)
                    Text(download.progressLine)
                        .font(.caption)
                        .monospacedDigit()
                        .foregroundStyle(.secondary)
                }
                stopButton
            case .onDisk:
                onDiskText
                Spacer(minLength: 0)
            case .failed:
                failedText
                Spacer(minLength: 12)
                retryButton
            case .missing, .partial:
                missingText
                Spacer(minLength: 12)
                downloadButton
            case .unknown:
                ProgressView().controlSize(.small)
                Text(i18n.t("desktop.transcriptionSettings.whisperChecking"))
                    .foregroundStyle(.secondary)
                Spacer(minLength: 0)
            }
        }
    }
}
