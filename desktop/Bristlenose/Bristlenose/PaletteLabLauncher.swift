#if DEBUG
import AppKit
import os

/// Diagnostics ▸ Palette Lab: starts `experiments/brand-palettes/workbench.py serve`
/// from this checkout and opens it in the default browser.
///
/// Dev machines only, like every item in the DEBUG section: the lab needs this
/// repo's Python, its `.venv` and local trial-run reports, none of which exist in
/// a shipped build. It is a browser page, not a native window, on purpose: it is
/// a colour tool for judging real pages, and it edits the same palette files the
/// app reads (`workbench.py promote`), so it runs beside the app, not inside it.
///
/// If something already answers on the port (the lab started from a terminal),
/// it is reused rather than spawned twice.
@MainActor
enum PaletteLabLauncher {
    private static let log = Logger(subsystem: "app.bristlenose", category: "palette-lab")
    private static let port = 8530
    private static var process: Process?
    private static var quitObserver: NSObjectProtocol?

    /// The checkout this build came from, read off this file's compile-time path
    /// (desktop/Bristlenose/Bristlenose/<file> -> four levels up).
    private static var repoRoot: URL {
        URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent()
    }

    private static var labURL: URL { URL(string: "http://127.0.0.1:\(port)/")! }

    static func open() {
        Task {
            if await isAnswering() {
                NSWorkspace.shared.open(labURL)
                return
            }
            guard start() else { return }
            for _ in 0..<40 {                       // up to 10 s for node + python to come up
                try? await Task.sleep(nanoseconds: 250_000_000)
                if await isAnswering() {
                    NSWorkspace.shared.open(labURL)
                    return
                }
            }
            log.error("palette lab did not answer on port \(port, privacy: .public) within 10 s")
            NSSound.beep()
        }
    }

    private static func isAnswering() async -> Bool {
        var request = URLRequest(url: labURL.appendingPathComponent("api/pages"))
        request.timeoutInterval = 1
        guard let (_, response) = try? await URLSession.shared.data(for: request) else { return false }
        return (response as? HTTPURLResponse)?.statusCode == 200
    }

    private static func start() -> Bool {
        let python = repoRoot.appendingPathComponent(".venv/bin/python")
        let script = repoRoot.appendingPathComponent("experiments/brand-palettes/workbench.py")
        guard FileManager.default.isExecutableFile(atPath: python.path),
              FileManager.default.fileExists(atPath: script.path) else {
            log.error("palette lab: no .venv/bin/python or workbench.py under \(repoRoot.path, privacy: .public)")
            NSSound.beep()
            return false
        }
        let p = Process()
        p.executableURL = python
        p.arguments = [script.path, "serve", "--port", "\(port)"]
        p.currentDirectoryURL = repoRoot
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        p.terminationHandler = { _ in Task { @MainActor in process = nil } }
        do { try p.run() } catch {
            log.error("palette lab: could not start: \(error.localizedDescription, privacy: .public)")
            NSSound.beep()
            return false
        }
        process = p
        if quitObserver == nil {                    // no orphan server after Quit
            quitObserver = NotificationCenter.default.addObserver(
                forName: NSApplication.willTerminateNotification, object: nil, queue: .main
            ) { _ in MainActor.assumeIsolated { process?.terminate() } }
        }
        return true
    }
}
#endif
