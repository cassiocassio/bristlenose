import SwiftUI

// When _demoShoal is true in RunningView, block phase transitions so the
// shoal demo can run uninterrupted. Debug builds only.
#if DEBUG
let _demoShoalBlockTransition = true  // keep in sync with _demoShoal in RunningView
#endif

struct ContentView: View {
    @State private var phase: AppPhase = .ready
    @State private var needsSetup = false
    @StateObject private var runner = ProcessRunner()

    var body: some View {
        VStack {
            switch phase {
            case .ready:
                if needsSetup {
                    SetupView {
                        needsSetup = false
                    }
                } else {
                    ReadyView { url in
                        let result = FolderValidator.check(folder: url)
                        phase = .selected(
                            folder: url,
                            fileCount: result.fileCount,
                            hasExistingOutput: result.hasExistingOutput
                        )
                    }
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
                        runner.stopServe()
                        phase = .ready
                    }
                )

            case .running(let folder, let mode):
                RunningView(folder: folder, mode: mode, runner: runner)

            case .serving(let folder, let reportURL, _):
                DoneView(
                    reportURL: reportURL,
                    runner: runner,
                    onRunAgain: {
                        runner.stopServe()
                        let result = FolderValidator.check(folder: folder)
                        phase = .selected(
                            folder: folder,
                            fileCount: result.fileCount,
                            hasExistingOutput: result.hasExistingOutput
                        )
                    },
                    onStartOver: {
                        runner.stopServe()
                        phase = .ready
                    }
                )

            case .done(let folder, let reportPath, _):
                // Fallback — only reached if serve fails to start
                DoneView(
                    reportURL: reportPath.map { "file://\($0)" },
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
        .onAppear {
            needsSetup = !KeychainHelper.hasAnyAPIKey()
        }
        .onChange(of: runner.isRunning) { wasRunning, isNowRunning in
            // When the pipeline finishes, launch serve mode
            #if DEBUG
            if _demoShoalBlockTransition { return }
            #endif
            if wasRunning && !isNowRunning {
                if case .running(let folder, _) = phase {
                    if runner.exitCode == 0 {
                        launchServe(folder: folder)

                        // Fallback: if serve doesn't produce a URL within 5s,
                        // fall back to file:// report path
                        Task {
                            try? await Task.sleep(for: .seconds(5))
                            if case .running(let f, _) = phase {
                                phase = .done(
                                    folder: f,
                                    reportPath: runner.reportPath,
                                    lines: runner.outputLines
                                )
                            }
                        }
                    } else {
                        // Pipeline failed — show done state with error
                        phase = .done(
                            folder: folder,
                            reportPath: runner.reportPath,
                            lines: runner.outputLines
                        )
                    }
                }
            }
        }
        .onChange(of: runner.serveURL) { _, newURL in
            // When serve detects its URL, transition to serving state
            if let url = newURL, case .running(let folder, _) = phase {
                phase = .serving(
                    folder: folder,
                    reportURL: url,
                    lines: runner.outputLines
                )
            }
        }
    }

    // MARK: - Pipeline launch

    /// Locate the bundled sidecar binary and launch it.
    private func launchPipeline(command: String, folder: URL, extraArgs: [String] = []) {
        let (sidecarURL, env) = Self.resolveSidecar()

        runner.run(
            executableURL: sidecarURL,
            arguments: [command] + extraArgs + [folder.path],
            environment: env
        )
    }

    /// Launch `bristlenose serve` in the background after the pipeline completes.
    private func launchServe(folder: URL) {
        let (sidecarURL, env) = Self.resolveSidecar()

        runner.startServe(
            executableURL: sidecarURL,
            arguments: ["serve", "--no-open", folder.path],
            environment: env
        )
    }

    // MARK: - Sidecar resolution

    /// Find the sidecar binary and build the environment for it.
    private static func resolveSidecar() -> (URL, [String: String]) {
        var env: [String: String] = [:]

        if let resourcePath = Bundle.main.resourcePath {
            let sidecarPath = (resourcePath as NSString)
                .appendingPathComponent("bristlenose-sidecar")
                .appending("/bristlenose-sidecar")
            if FileManager.default.isExecutableFile(atPath: sidecarPath) {
                let sidecarURL = URL(fileURLWithPath: sidecarPath)

                // Prepend Resources dir to PATH so bundled ffmpeg/ffprobe are found
                let currentPath = ProcessInfo.processInfo.environment["PATH"] ?? "/usr/bin:/bin"
                env["PATH"] = resourcePath + ":" + currentPath

                // Point to bundled Whisper model
                let modelsPath = (resourcePath as NSString).appendingPathComponent("models")
                env["BRISTLENOSE_WHISPER_MODEL_DIR"] = modelsPath
                env["BRISTLENOSE_WHISPER_MODEL"] = "small.en"
                env["BRISTLENOSE_WHISPER_BACKEND"] = "faster-whisper"

                return (sidecarURL, env)
            }
        }

        return (findDevBinary(), env)
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
