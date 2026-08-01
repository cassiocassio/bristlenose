import Foundation

/// Which folder "Show Transcripts in Finder" should reveal.
///
/// Extracted from `ExportMenuButton.revealTranscripts` (30 Jul 2026) when the
/// command gained a second surface — the Project menu — so the fallback ladder
/// lives in one testable place rather than being duplicated per call site
/// (house convention: a view that decides something hands the decision to a
/// plain helper, cf. `ProjectSubtitle.resolve`, `SidebarToggle`).
///
/// The ladder prefers the most *shareable* form: PII-redacted transcripts if
/// the project has them, then raw, then progressively broader folders so the
/// command always lands somewhere real rather than failing silently.
enum TranscriptsRevealTarget {

    /// Folder to hand to Finder for `projectPath`, or `nil` when there is
    /// nothing usable (empty path).
    ///
    /// Order: `transcripts-cooked/` (present only when `--redact-pii` ran) →
    /// `transcripts-raw/` → `bristlenose-output/` → the project folder. The
    /// project folder is the floor: it always exists for a tracked project, so
    /// a reveal can't no-op just because analysis hasn't run yet.
    ///
    /// `fileManager` is injectable so tests don't need a real tree.
    static func resolve(
        projectPath: String,
        fileManager: FileManager = .default
    ) -> String? {
        guard !projectPath.isEmpty else { return nil }
        let output = (projectPath as NSString).appendingPathComponent("bristlenose-output")
        let candidates = [
            (output as NSString).appendingPathComponent("transcripts-cooked"),
            (output as NSString).appendingPathComponent("transcripts-raw"),
            output,
            projectPath,
        ]
        return candidates.first { fileManager.fileExists(atPath: $0) } ?? projectPath
    }
}
