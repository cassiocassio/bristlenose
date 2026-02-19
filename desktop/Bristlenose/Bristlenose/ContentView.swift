import SwiftUI

struct ContentView: View {
    @State private var phase: AppPhase = .ready
    @StateObject private var runner = ProcessRunner()

    var body: some View {
        VStack {
            switch phase {
            case .ready:
                ReadyView { url in
                    let result = FolderValidator.check(folder: url)
                    phase = .selected(
                        folder: url,
                        fileCount: result.fileCount,
                        hasExistingOutput: result.hasExistingOutput
                    )
                }

            case .selected(let folder, let fileCount, let hasExistingOutput):
                SelectedView(
                    folder: folder,
                    fileCount: fileCount,
                    hasExistingOutput: hasExistingOutput,
                    onAnalyse: {
                        phase = .running(folder: folder, mode: .analyse)
                        launchPipeline(command: "run", folder: folder, extraArgs: ["--clean"])
                    },
                    onRerender: {
                        phase = .running(folder: folder, mode: .rerender)
                        launchPipeline(command: "render", folder: folder)
                    },
                    onChangeFolder: {
                        phase = .ready
                    }
                )

            case .running(let folder, _):
                RunningView(folder: folder, runner: runner)

            case .done(let folder, let reportPath, _):
                DoneView(
                    reportPath: reportPath,
                    runner: runner,
                    onRunAgain: {
                        let result = FolderValidator.check(folder: folder)
                        phase = .selected(
                            folder: folder,
                            fileCount: result.fileCount,
                            hasExistingOutput: result.hasExistingOutput
                        )
                    },
                    onStartOver: {
                        phase = .ready
                    }
                )
            }
        }
        .frame(minWidth: 480, minHeight: 400)
        .padding()
        .onChange(of: runner.isRunning) { wasRunning, isNowRunning in
            // When the process finishes, transition to done
            if wasRunning && !isNowRunning {
                if case .running(let folder, _) = phase {
                    phase = .done(
                        folder: folder,
                        reportPath: runner.reportPath,
                        lines: runner.outputLines
                    )
                }
            }
        }
    }

    // MARK: - Pipeline launch

    /// Locate the bundled sidecar binary and launch it.
    private func launchPipeline(command: String, folder: URL, extraArgs: [String] = []) {
        // For release: use the bundled sidecar from the app's Resources.
        // For development: search common install locations.
        let sidecarURL: URL
        var env: [String: String] = [:]

        if let resourcePath = Bundle.main.resourcePath {
            let sidecarPath = (resourcePath as NSString)
                .appendingPathComponent("bristlenose-sidecar")
                .appending("/bristlenose-sidecar")
            if FileManager.default.isExecutableFile(atPath: sidecarPath) {
                sidecarURL = URL(fileURLWithPath: sidecarPath)

                // Prepend Resources dir to PATH so bundled ffmpeg/ffprobe are found
                let currentPath = ProcessInfo.processInfo.environment["PATH"] ?? "/usr/bin:/bin"
                env["PATH"] = resourcePath + ":" + currentPath

                // Point to bundled Whisper model
                let modelsPath = (resourcePath as NSString).appendingPathComponent("models")
                env["BRISTLENOSE_WHISPER_MODEL_DIR"] = modelsPath
                env["BRISTLENOSE_WHISPER_MODEL"] = "small.en"
                env["BRISTLENOSE_WHISPER_BACKEND"] = "faster-whisper"
            } else {
                sidecarURL = Self.findDevBinary()
            }
        } else {
            sidecarURL = Self.findDevBinary()
        }

        // TODO: Add ANTHROPIC_API_KEY from Keychain or bundled fallback

        runner.run(
            executableURL: sidecarURL,
            arguments: [command] + extraArgs + [folder.path],
            environment: env
        )
    }

    /// Search common locations for the bristlenose CLI binary (dev mode only).
    private static func findDevBinary() -> URL {
        let fm = FileManager.default
        let candidates = [
            // pipx / venv in the project directory
            NSString("~/Code/bristlenose/.venv/bin/bristlenose").expandingTildeInPath,
            // Homebrew
            "/opt/homebrew/bin/bristlenose",
            "/usr/local/bin/bristlenose",
            // pipx default
            NSString("~/.local/bin/bristlenose").expandingTildeInPath,
        ]
        for path in candidates where fm.isExecutableFile(atPath: path) {
            return URL(fileURLWithPath: path)
        }
        // Last resort — will fail with a clear error message
        return URL(fileURLWithPath: "/usr/local/bin/bristlenose")
    }
}
