import Foundation

/// Has a Re-analyse (`--clean`) that is running produced a session yet?
///
/// A `--clean` start sets the old report aside and builds a new one; the old report is
/// replaced for good once the new analysis holds a session
/// (`bristlenose/utils/output_backup.py`, `holds_an_analysed_session`). Until then a
/// quit or crash puts the old report back, and the run restarts as a Re-analyse
/// (R18). From then on a restart as a Re-analyse would set the finished interviews
/// aside and pay for them again, so the restored run resumes as a plain Analyse
/// (owner, 12 Nov 2026). The runner asks this while the run is live and writes the
/// answer into the queue it keeps (`PipelineRunner.journalQueue`).
///
/// **Both halves are needed.** The output folder holds an analysed session either
/// way (the new analysis, or the old report before the set-aside happens a few seconds
/// into the run), so the set-aside copy beside it is what says which one it is.
enum FreshRunProbe {
    /// The set-aside copy: a hidden sibling of the output folder, `backup_path_for`.
    nonisolated static func setAsideURL(studyFolder: URL) -> URL {
        studyFolder.appendingPathComponent(".bristlenose-output-previous")
    }

    /// The new analysis of a `--clean` run holds a session: the old report is set aside
    /// and the output beside it holds one.
    nonisolated static func freshRunHoldsSession(
        studyFolder: URL, fileManager: FileManager = .default
    ) -> Bool {
        var isDirectory: ObjCBool = false
        guard fileManager.fileExists(
            atPath: setAsideURL(studyFolder: studyFolder).path, isDirectory: &isDirectory
        ), isDirectory.boolValue else { return false }
        return holdsAnalysedSession(
            output: studyFolder.appendingPathComponent("bristlenose-output"))
    }

    /// Python's `holds_an_analysed_session`: a session whose quote extraction is recorded
    /// complete in the manifest, and at least one quote on disk for it. Anything
    /// unreadable answers false.
    nonisolated static func holdsAnalysedSession(output: URL) -> Bool {
        let dot = output.appendingPathComponent(".bristlenose")
        guard let manifestData = try? Data(contentsOf: dot.appendingPathComponent("pipeline-manifest.json")),
              let manifest = try? JSONSerialization.jsonObject(with: manifestData) as? [String: Any],
              let stages = manifest["stages"] as? [String: Any],
              let stage = stages["quote_extraction"] as? [String: Any],
              let sessions = stage["sessions"] as? [String: Any]
        else { return false }
        let done = Set(sessions.compactMap { id, record -> String? in
            guard let record = record as? [String: Any], record["status"] as? String == "complete"
            else { return nil }
            return id
        })
        guard !done.isEmpty,
              let quotesData = try? Data(contentsOf: dot
                .appendingPathComponent("intermediate")
                .appendingPathComponent("extracted_quotes.json")),
              let quotes = try? JSONSerialization.jsonObject(with: quotesData) as? [Any]
        else { return false }
        return quotes.contains { quote in
            guard let quote = quote as? [String: Any], let id = quote["session_id"] as? String
            else { return false }
            return done.contains(id)
        }
    }
}
