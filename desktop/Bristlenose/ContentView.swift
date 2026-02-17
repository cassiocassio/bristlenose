import SwiftUI

struct ContentView: View {
    @State private var phase: AppPhase = .ready
    @StateObject private var runner = ProcessRunner()

    var body: some View {
        VStack(spacing: 0) {
            switch phase {
            case .ready:
                ReadyView(onFolderSelected: handleFolderSelected)

            case .selected(let folder, let fileCount, let hasExistingOutput):
                SelectedView(
                    folder: folder,
                    fileCount: fileCount,
                    hasExistingOutput: hasExistingOutput,
                    onAnalyse: { startPipeline(folder: folder, mode: .analyse) },
                    onRerender: { startPipeline(folder: folder, mode: .rerender) },
                    onChangeFolder: { phase = .ready }
                )

            case .running(let folder, _):
                RunningView(folder: folder, runner: runner)

            case .done(_, let reportPath, _):
                DoneView(
                    reportPath: reportPath,
                    runner: runner,
                    onStartOver: { phase = .ready }
                )
            }
        }
        .frame(minWidth: 500, minHeight: 400)
        .padding(24)
        .onChange(of: runner.isRunning) { _, running in
            if !running, case .running(let folder, _) = phase {
                phase = .done(
                    folder: folder,
                    reportPath: runner.reportPath ?? findReport(in: folder),
                    lines: runner.outputLines
                )
            }
        }
    }

    // MARK: - Actions

    private func handleFolderSelected(_ url: URL) {
        let result = FolderValidator.check(folder: url)
        phase = .selected(
            folder: url,
            fileCount: result.fileCount,
            hasExistingOutput: result.hasExistingOutput
        )
    }

    private func startPipeline(folder: URL, mode: RunMode) {
        phase = .running(folder: folder, mode: mode)

        guard let binary = sidecarURL() else {
            runner.outputLines.append("Error: bristlenose-cli not found in app bundle.")
            return
        }

        var args: [String]
        switch mode {
        case .analyse:
            args = ["run", folder.path]
        case .rerender:
            let outputDir = folder.appendingPathComponent("bristlenose-output")
            args = ["render", outputDir.path]
        }

        // Environment: inject bundled API key as fallback.
        // The Python side checks Keychain first (via credentials_macos.py),
        // so friends with their own key get theirs used automatically.
        var env: [String: String] = [:]
        // TODO: Set ANTHROPIC_API_KEY to your capped-account key here
        // env["ANTHROPIC_API_KEY"] = "sk-ant-..."

        // Prepend the Resources directory to PATH so the bundled ffmpeg
        // is found by shutil.which("ffmpeg") inside the Python sidecar.
        if let resourcesPath = Bundle.main.resourceURL?.path {
            let currentPath = ProcessInfo.processInfo.environment["PATH"] ?? "/usr/bin:/bin"
            env["PATH"] = "\(resourcesPath):\(currentPath)"
        }

        runner.run(executableURL: binary, arguments: args, environment: env)
    }

    // MARK: - Helpers

    private func sidecarURL() -> URL? {
        Bundle.main.url(forResource: "bristlenose-cli", withExtension: nil)
    }

    /// Fallback: scan the output directory for the report HTML file if we
    /// couldn't extract it from stdout.
    private func findReport(in folder: URL) -> String? {
        let outputDir = folder.appendingPathComponent("bristlenose-output")
        guard let contents = try? FileManager.default.contentsOfDirectory(
            at: outputDir,
            includingPropertiesForKeys: nil
        ) else { return nil }

        let report = contents.first { url in
            let name = url.lastPathComponent
            return name.hasPrefix("bristlenose-") && name.hasSuffix("-report.html")
        }
        return report?.path
    }
}
