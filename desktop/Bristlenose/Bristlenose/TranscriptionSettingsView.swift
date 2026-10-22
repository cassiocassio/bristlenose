import SwiftUI

/// Settings tab for Whisper transcription engine preferences, and for reading
/// the text on screens shared in recordings (the Screens lens).
///
/// With `BristlenoseFlags.appleSpeech` on, the engine section becomes one
/// behaviour choice and a Whisper status row
/// (`docs/design-apple-first-transcription.md` §4.5); MLX vs faster-whisper
/// moves behind the Diagnostics preference and the interim model picker leaves
/// the pane (`BRISTLENOSE_WHISPER_MODEL` stays as an override). Off, the pane is
/// as it shipped.
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
                TranscribeWithSection()
                // The engine and model pickers behind Diagnostics: the model a
                // run uses is still this preference, so it must stay reachable.
                if showDiagnostics {
                    backendSection
                    modelSection
                }
            } else {
                backendSection
                modelSection
                // Whisper downloads in the background from launch, so its
                // Download Now / Stop / status row is here without the Apple
                // choice too. Download Now is not held by the 20 GB floor.
                Section { WhisperStatusRow(download: whisperDownload) }
                    .task { await whisperDownload.refresh() }
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
        }
        .onChange(of: model) { _, _ in
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
    }

    private var backendSection: some View {
        Section {
            // Help text as an in-cell subtitle (no row keyline) — the
            // System Settings idiom, matching the Appearance toggles.
            Picker(selection: $backend) {
                Text(i18n.t("desktop.transcriptionSettings.backendAuto")).tag("auto")
                Text("MLX").tag("mlx")
                Text("faster-whisper").tag("faster-whisper")
            } label: {
                Text(i18n.t("desktop.transcriptionSettings.backendLabel"))
                Text(i18n.t("desktop.transcriptionSettings.backendHint"))
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var modelSection: some View {
        Section {
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
        }
    }
}

/// "Transcribe with" and the Whisper status row (§4.5).
///
/// The choice is read by each run when it starts (`appleSpeechEnvironment`),
/// so it posts no `.bristlenosePrefsChanged`: no serve reads it, and a
/// restart would cold-remount every open report for nothing.
private struct TranscribeWithSection: View {
    @EnvironmentObject var i18n: I18n
    @ObservedObject private var download = WhisperDownloadModel.shared
    @AppStorage(TranscriptionEngineChoice.key)
    private var choice: String = TranscriptionEngineChoice.whisperWhenReady.rawValue

    var body: some View {
        Section {
            Picker(selection: $choice) {
                Text(i18n.t("desktop.transcriptionSettings.engineWhenReady"))
                    .tag(TranscriptionEngineChoice.whisperWhenReady.rawValue)
                Text(i18n.t("desktop.transcriptionSettings.engineWhisperOnly"))
                    .tag(TranscriptionEngineChoice.whisperOnly.rawValue)
                Text(i18n.t("desktop.transcriptionSettings.engineApple"))
                    .tag(TranscriptionEngineChoice.apple.rawValue)
            } label: {
                Text(i18n.t("desktop.transcriptionSettings.engineLabel"))
                Text(i18n.t("desktop.transcriptionSettings.engineHint"))
                    .foregroundStyle(.secondary)
            }
            WhisperStatusRow(download: download)
        }
        .task { await download.refresh() }
    }
}

/// Whisper: Download Now / progress with Stop Download / On this Mac · 1.6 GB.
/// The same `WhisperDownloadModel` as the toolbar pill, so the two can never
/// disagree.
private struct WhisperStatusRow: View {
    @EnvironmentObject var i18n: I18n
    @ObservedObject var download: WhisperDownloadModel

    /// The row's height differs between its states; the Settings package
    /// re-fits only on a tab switch, so the pane asks when this changes
    /// (`SettingsWindow.refitToContent`).
    private var heightSignature: Int {
        switch download.phase {
        case .downloading: return 2
        case .failed: return 1
        case .unknown, .missing, .partial, .onDisk: return 0
        }
    }

    var body: some View {
        LabeledContent {
            HStack(spacing: 8) {
                switch download.phase {
                case .downloading:
                    VStack(alignment: .trailing, spacing: 2) {
                        if let fraction = download.fractionDone {
                            ProgressView(value: fraction).frame(width: 160)
                        } else {
                            ProgressView().progressViewStyle(.linear).frame(width: 160)
                        }
                        Text(download.progressLine)
                            .font(.caption)
                            .monospacedDigit()
                            .foregroundStyle(.secondary)
                    }
                    Button(i18n.t("desktop.modelDownload.stop")) { download.stop() }
                case .onDisk:
                    Text(i18n.t("desktop.transcriptionSettings.whisperOnDisk", [
                        "size": ByteCountFormatter.string(
                            fromByteCount: download.bytesOnDisk, countStyle: .file),
                    ]))
                    .foregroundStyle(.secondary)
                case .failed:
                    Text(i18n.t("desktop.transcriptionSettings.whisperFailed"))
                        .foregroundStyle(.secondary)
                    Button(i18n.t("common.buttons.retry")) { download.downloadNow() }
                case .missing, .partial:
                    Text(i18n.t("desktop.transcriptionSettings.whisperMissing"))
                        .foregroundStyle(.secondary)
                    Button(i18n.t("desktop.transcriptionSettings.downloadNow")) { download.downloadNow() }
                case .unknown:
                    // Asking the sidecar takes a moment; say so, not a blank.
                    ProgressView().controlSize(.small)
                }
            }
        } label: {
            Text(i18n.t("desktop.transcriptionSettings.whisperLabel"))
        }
        .onChange(of: heightSignature) { _, _ in
            DispatchQueue.main.async { SettingsWindow.shared.refitToContent() }
        }
    }
}
