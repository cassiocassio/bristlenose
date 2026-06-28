#if DEBUG
import AppKit
import Foundation

// MARK: - Debug menu actions (DEBUG only)
//
// "Reveal existing data" helpers behind the Debug menu — Finder reveal, open
// log, copy build provenance. They read artifacts the pipeline already writes;
// no new logging. The served project (ServeManager.currentProjectPath) is the
// one whose report is on screen, so these act on it.

@MainActor
enum DebugMenuActions {
    /// `<project>/bristlenose-output/.bristlenose` — where logs / events /
    /// llm-calls / db / last-failure live. Mirrors the Python `OutputPaths`
    /// layout and `run_inspector.resolve_internal_dir`.
    static func internalDir(forProjectPath path: String) -> URL {
        URL(fileURLWithPath: path)
            .appendingPathComponent("bristlenose-output", isDirectory: true)
            .appendingPathComponent(".bristlenose", isDirectory: true)
    }

    /// Reveal the served project's `.bristlenose/` in Finder. Falls back to the
    /// project folder if it hasn't been analysed yet; beeps if nothing is served.
    static func revealInternalDir(serveManager: ServeManager) {
        guard let projectPath = serveManager.currentProjectPath else { NSSound.beep(); return }
        let dir = internalDir(forProjectPath: projectPath)
        let target = FileManager.default.fileExists(atPath: dir.path)
            ? dir
            : URL(fileURLWithPath: projectPath)
        NSWorkspace.shared.activateFileViewerSelecting([target])
    }

    /// Open the served project's `bristlenose.log` (opens in Console.app by
    /// default). Beeps if there's no served project or no log yet.
    static func openLog(serveManager: ServeManager) {
        guard let projectPath = serveManager.currentProjectPath else { NSSound.beep(); return }
        let log = internalDir(forProjectPath: projectPath)
            .appendingPathComponent("bristlenose.log")
        guard FileManager.default.fileExists(atPath: log.path) else { NSSound.beep(); return }
        NSWorkspace.shared.open(log)
    }

    /// Copy a build-provenance block to the clipboard. Answers the recurring
    /// "is the bundled sidecar stale?" question (see desktop/CLAUDE.md): the app
    /// build vs the live sidecar's version vs the version that last produced the
    /// artifacts.
    static func copyBuildProvenance(serveManager: ServeManager) {
        let sha = GeneratedBuildInfo.gitDirty
            ? "\(GeneratedBuildInfo.gitSHA)-dirty"
            : GeneratedBuildInfo.gitSHA
        var lines = [
            "Bristlenose build provenance",
            "  app build : \(GeneratedBuildInfo.gitBranch) @ \(sha) · \(GeneratedBuildInfo.configuration) · built \(GeneratedBuildInfo.buildDate)",
            "  sandbox   : \(GeneratedBuildInfo.sandboxEnabled)  ·  hardened runtime: \(GeneratedBuildInfo.hardenedRuntimeEnabled)",
            "  sidecar   : \(serveManager.mode?.logDescription ?? "—")",
            "  serving   : version \(serveManager.serverVersion ?? "—")",
        ]
        if let path = serveManager.currentProjectPath {
            lines.append("  project   : \(path)")
            lines.append("  last run  : bristlenose_version \(eventsVersion(projectPath: path) ?? "—")")
        }
        let text = lines.joined(separator: "\n")
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
    }

    /// `process.bristlenose_version` from the first `run_started` line of the
    /// project's pipeline-events.jsonl — the version that actually produced the
    /// artifacts on disk (distinct from the app build and the live sidecar).
    private static func eventsVersion(projectPath: String) -> String? {
        let events = internalDir(forProjectPath: projectPath)
            .appendingPathComponent("pipeline-events.jsonl")
        guard let content = try? String(contentsOf: events, encoding: .utf8) else { return nil }
        for line in content.split(separator: "\n") {
            guard let data = line.data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  (obj["event"] as? String) == "run_started",
                  let proc = obj["process"] as? [String: Any],
                  let version = proc["bristlenose_version"] as? String
            else { continue }
            return version
        }
        return nil
    }
}
#endif
