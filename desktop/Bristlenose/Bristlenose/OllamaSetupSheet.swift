import os
import SwiftUI

/// Single-sheet setup flow for the local-AI path.
///
/// Presented from `AIConsentView` when the user clicks "Use the local
/// Ollama model instead." Renders a model picker (curated catalog,
/// recommended preselected based on system RAM) plus a "Set up"
/// button. On tap, installs Ollama if missing (via NSWorkspace + the
/// macOS installer) and downloads the chosen model via HTTP.
///
/// Ollama is framed as infrastructure — the user's mental model is
/// "I'm getting a local AI." Footer credits Ollama as open source
/// without making it feel like a separate decision.
struct OllamaSetupSheet: View {

    /// Called on success (model downloaded + ready). Caller writes
    /// `activeProvider`, records consent, and dismisses both the sheet
    /// and AIConsent.
    var onComplete: (_ chosenTag: String) -> Void

    /// Called on cancel. No consent recorded; `activeProvider` unchanged.
    var onCancel: () -> Void

    @StateObject private var model = OllamaSetupModel()
    @State private var selectedTag: String = OllamaCatalog.recommendedTag()

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            switch model.phase {
            case .idle, .failed:
                idleView
            case .installingOllama, .waitingForDaemon, .downloadingModel, .finishing:
                progressView
            }
        }
        .padding(20)
        .frame(width: 460)
        .onChange(of: model.phase) { _, phase in
            if case .finishing = phase {
                onComplete(selectedTag)
            }
        }
    }

    // MARK: - Idle (model picker)

    private var idleView: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Use local AI")
                .font(.headline)

            Text("Run analysis on your Mac. Your transcripts stay on your Mac.")
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            modelPicker

            if case .failed(let message) = model.phase {
                Text(message)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .fixedSize(horizontal: false, vertical: true)
            }

            HStack {
                Spacer()
                Button("Cancel") { onCancel() }
                    .keyboardShortcut(.cancelAction)
                Button("Set up") { startSetup() }
                    .keyboardShortcut(.defaultAction)
                    .buttonStyle(.borderedProminent)
            }

            ollamaCredit
        }
    }

    private var modelPicker: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("Model")
                Spacer()
                Picker("", selection: $selectedTag) {
                    ForEach(OllamaCatalog.curated) { m in
                        Text(label(for: m))
                            .tag(m.tag)
                    }
                }
                .labelsHidden()
                .frame(width: 240)
            }
            if let m = OllamaCatalog.model(for: selectedTag) {
                let recommended = (m.tag == OllamaCatalog.recommendedTag())
                let suffix = recommended ? " · best for this Mac" : ""
                Text("~\(m.weightsGB, specifier: "%.0f") GB\(suffix)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    /// Picker row label. Untranslated product names + dynamic suffixes.
    private func label(for m: OllamaModel) -> String {
        let recommendedTag = OllamaCatalog.recommendedTag()
        let fits = OllamaCatalog.fits(m)
        if !fits {
            return "\(m.displayName) (needs \(Int(m.minRAMGB)) GB RAM)"
        }
        if m.tag == recommendedTag {
            return "\(m.displayName) (recommended)"
        }
        return m.displayName
    }

    private var ollamaCredit: some View {
        HStack(spacing: 4) {
            Text("Uses")
                .font(.caption)
                .foregroundStyle(.tertiary)
            Link("Ollama", destination: URL(string: "https://ollama.com")!)
                .font(.caption)
            Text("(open source)")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
    }

    // MARK: - Progress

    private var progressView: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Setting up local AI…")
                .font(.headline)

            // Single progress bar across both phases. Indeterminate while
            // installing Ollama / waiting for the daemon (we don't know
            // how long Apple's installer takes); determinate during the
            // model download.
            if model.downloadRatio > 0 {
                ProgressView(value: model.downloadRatio) {
                    Text(model.statusLine)
                        .font(.caption)
                } currentValueLabel: {
                    Text(downloadByteString)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .progressViewStyle(.linear)
            } else {
                ProgressView {
                    Text(model.statusLine)
                        .font(.caption)
                }
                .progressViewStyle(.linear)
            }

            HStack {
                Spacer()
                Button("Cancel") { cancelSetup() }
                    .keyboardShortcut(.cancelAction)
            }
        }
    }

    private var downloadByteString: String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        let done = formatter.string(fromByteCount: model.completedBytes)
        let total = formatter.string(fromByteCount: model.totalBytes)
        return "\(done) of \(total)"
    }

    // MARK: - Actions

    private func startSetup() {
        Task { await model.run(tag: selectedTag) }
    }

    private func cancelSetup() {
        model.cancel()
        onCancel()
    }
}

// MARK: - State machine

@MainActor
final class OllamaSetupModel: ObservableObject {

    enum Phase: Equatable {
        case idle
        case installingOllama
        case waitingForDaemon
        case downloadingModel
        case finishing
        case failed(String)
    }

    @Published var phase: Phase = .idle
    @Published var statusLine: String = ""
    @Published var completedBytes: Int64 = 0
    @Published var totalBytes: Int64 = 0

    var downloadRatio: Double {
        guard totalBytes > 0 else { return 0 }
        return min(1, Double(completedBytes) / Double(totalBytes))
    }

    private static let logger = Logger(subsystem: "app.bristlenose", category: "ollama-setup")
    private static let ollamaAppPath = "/Applications/Ollama.app"
    private static let defaultBaseURL = URL(string: "http://127.0.0.1:11434")!

    private var task: Task<Void, Never>?

    func run(tag: String) async {
        task?.cancel()
        let work = Task { @MainActor in
            do {
                // Reachability first: if the daemon answers, we don't
                // care how it got there (Homebrew, .app bundle, or
                // user-launched binary). Skip install entirely.
                let alreadyReachable = await isDaemonReachable()
                if !alreadyReachable {
                    if !FileManager.default.fileExists(atPath: Self.ollamaAppPath) {
                        phase = .installingOllama
                        statusLine = "Installing local runtime…"
                        Self.logger.info("Ollama.app not found; opening installer page")
                        NSWorkspace.shared.open(URL(string: "https://ollama.com/download")!)
                        try await waitForOllamaApp()
                    }
                    phase = .waitingForDaemon
                    statusLine = "Starting local runtime…"
                    try await waitForDaemon()
                }

                phase = .downloadingModel
                statusLine = "Downloading \(displayName(for: tag))…"
                try await LLMValidator.pullModel(
                    tag: tag, baseURL: Self.defaultBaseURL
                ) { [weak self] progress in
                    self?.completedBytes = progress.completedBytes
                    self?.totalBytes = progress.totalBytes
                    if !progress.statusLine.isEmpty {
                        self?.statusLine = progress.statusLine
                    }
                }

                Self.logger.info("Ollama setup complete: \(tag, privacy: .public)")
                phase = .finishing
            } catch is CancellationError {
                phase = .idle
            } catch {
                Self.logger.error("Ollama setup failed: \(error.localizedDescription, privacy: .public)")
                phase = .failed("Setup failed: \(error.localizedDescription)")
            }
        }
        task = work
        await work.value
    }

    func cancel() {
        task?.cancel()
        phase = .idle
    }

    /// Poll the filesystem for `/Applications/Ollama.app`. Apple's
    /// installer drops it there. Times out after ~5 min.
    private func waitForOllamaApp() async throws {
        let deadline = Date().addingTimeInterval(300)
        while !FileManager.default.fileExists(atPath: Self.ollamaAppPath) {
            try Task.checkCancellation()
            if Date() > deadline {
                throw NSError(
                    domain: "OllamaSetup", code: 1,
                    userInfo: [NSLocalizedDescriptionKey:
                        "Ollama wasn't installed. Try downloading from ollama.com."])
            }
            try await Task.sleep(for: .seconds(2))
        }
        // Once the app appears, give Ollama a moment to launch its daemon.
        // The Ollama installer auto-launches the app. Otherwise our
        // daemon-wait loop will trigger it via NSWorkspace below.
    }

    /// Poll `/api/tags` until the daemon answers. Times out after 60 s.
    /// If the app exists but isn't running, attempt to launch it via
    /// NSWorkspace.
    private func waitForDaemon() async throws {
        let deadline = Date().addingTimeInterval(60)
        var didLaunch = false
        while true {
            try Task.checkCancellation()
            if await isDaemonReachable() { return }
            if Date() > deadline {
                throw NSError(
                    domain: "OllamaSetup", code: 2,
                    userInfo: [NSLocalizedDescriptionKey:
                        "Local runtime didn't start in time. Try launching Ollama from Applications."])
            }
            if !didLaunch,
               FileManager.default.fileExists(atPath: Self.ollamaAppPath)
            {
                NSWorkspace.shared.open(URL(fileURLWithPath: Self.ollamaAppPath))
                didLaunch = true
            }
            try await Task.sleep(for: .seconds(1))
        }
    }

    private func isDaemonReachable() async -> Bool {
        var req = URLRequest(url: URL(string: "\(Self.defaultBaseURL.absoluteString)/api/tags")!)
        req.httpMethod = "GET"
        req.timeoutInterval = 2
        do {
            let (_, response) = try await URLSession(configuration: .ephemeral).data(for: req)
            if let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) {
                return true
            }
            return false
        } catch {
            return false
        }
    }

    private func displayName(for tag: String) -> String {
        OllamaCatalog.model(for: tag)?.displayName ?? tag
    }
}
