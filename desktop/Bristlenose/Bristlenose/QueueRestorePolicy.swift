import Foundation

/// One study the run queue held when the app last wrote it: the run in flight
/// first, then the studies waiting behind it, in order.
struct PersistedQueueEntry: Codable, Equatable, Sendable {
    let projectID: UUID
    /// Whether the request was a Re-analyse (`--clean`). A restored entry keeps
    /// it: a stopped Re-analyse put the old report back, so resuming without
    /// it would end "ready" on the old report (R18).
    let clean: Bool
    /// When the researcher asked. The restore window runs from here, never from
    /// a relaunch, so a queue cannot live for ever by being reopened.
    let enqueuedAt: Date
    /// The study id the folder carried when it was asked for, if it had one.
    let studyID: String?
    /// The run that was going when the app last wrote the queue.
    let inFlight: Bool
}

struct PersistedRunQueue: Codable, Equatable, Sendable {
    static let currentSchema = 1
    var schema: Int = currentSchema
    var entries: [PersistedQueueEntry]

    static let empty = PersistedRunQueue(entries: [])
}

/// Whether a study the queue held at Quit (or at a crash) runs again on the
/// next launch (R19 follow-up, decided 20 Oct 2026).
///
/// The queue is the researcher's intent to do the study, so it is honoured
/// while it is fresh and the study is still there. Fresh means less than
/// `window`: Friday 4 pm to Tuesday noon, so a queue left at the end of the
/// week is picked up on Monday. Past that it lapses; the researcher can ask
/// again. A study that is gone, moved out of reach, or has nothing left to
/// analyse is dropped. Every drop is logged and none is shown.
enum QueueRestorePolicy {
    /// Friday 4 pm to Tuesday noon.
    static let window: TimeInterval = 92 * 60 * 60

    /// How far in the future a stamp may sit and still be believed: a clock
    /// set back by the network after the stamp was taken. Beyond this the age
    /// cannot be told, and an entry of unknown age is not honoured.
    static let clockSkewTolerance: TimeInterval = 60 * 60

    /// Python ingests files at most this many levels below the study folder
    /// (`s01_ingest._MAX_SCAN_DEPTH`).
    static let ingestDepth = 3

    enum DropReason: String, Equatable, Sendable {
        case expired
        case stampedInFuture
        case notInSidebar
        case folderNotFound
        case folderInCloud
        case differentStudy
        case nothingToAnalyse
    }

    enum Decision: Equatable, Sendable {
        case restore
        case drop(DropReason)
    }

    /// Whether the study's folder still holds anything to analyse.
    enum Inputs: Equatable, Sendable {
        case present
        case gone
        /// Could not tell (unreadable, too slow, a link not followed). Not
        /// "gone": the run reads the folder itself and says what it finds.
        case unknown
    }

    /// What the study's folder says now, read off-main.
    struct DiskEvidence: Equatable, Sendable {
        var studyIDOnDisk: String?
        var inputs: Inputs
    }

    /// The age check alone, so an expired entry costs no disk read.
    static func timeliness(enqueuedAt: Date, now: Date) -> DropReason? {
        let age = now.timeIntervalSince(enqueuedAt)
        if age < -clockSkewTolerance { return .stampedInFuture }
        if age >= window { return .expired }
        return nil
    }

    /// The whole decision. `project` is the sidebar's entry for the id, nil
    /// when it has been removed; `evidence` is nil when the folder was not read
    /// (it is only read for a study that passed the checks before it).
    static func decide(
        _ entry: PersistedQueueEntry, now: Date,
        project: Project?, availability: ProjectAvailability?,
        evidence: DiskEvidence?
    ) -> Decision {
        if let reason = timeliness(enqueuedAt: entry.enqueuedAt, now: now) { return .drop(reason) }
        guard project != nil else { return .drop(.notInSidebar) }
        switch availability ?? .ready {
        case .ready: break
        case .cantFind: return .drop(.folderNotFound)
        case .inCloud: return .drop(.folderInCloud)
        }
        guard let evidence else { return .restore }
        // A study is its marker id, never its path (docs/design-project-identity.md):
        // a folder now carrying another id is another study.
        if let was = entry.studyID?.lowercased(), let now = evidence.studyIDOnDisk?.lowercased(),
           was != now {
            return .drop(.differentStudy)
        }
        if evidence.inputs == .gone { return .drop(.nothingToAnalyse) }
        return .restore
    }

    /// Whether a study folder holds at least one file the pipeline would
    /// ingest, looking as deep as Python does and stopping at the first. The
    /// whole folder, as the run reads it (`run` is given the folder, never
    /// `Project.inputFiles`). Same
    /// extensions as the folder watcher, companions (`.txt` notes) excluded,
    /// hidden entries and `bristlenose-output/` skipped. A folder that can't
    /// be listed, or a link not followed, makes it `.unknown`, never `.gone`.
    nonisolated static func ingestableFile(
        under root: URL, maxDepth: Int = ingestDepth, fileManager: FileManager = .default
    ) -> Inputs {
        let keys: [URLResourceKey] = [.isDirectoryKey, .isSymbolicLinkKey]
        var frontier: [(url: URL, depth: Int)] = [(root, 1)]
        var undecided = false
        while !frontier.isEmpty {
            let (dir, depth) = frontier.removeFirst()
            guard let contents = try? fileManager.contentsOfDirectory(
                at: dir, includingPropertiesForKeys: keys, options: [.skipsHiddenFiles]
            ) else {
                undecided = true
                continue
            }
            for url in contents {
                let name = url.lastPathComponent
                if name == "bristlenose-output" || name.hasPrefix(".") { continue }
                let values = try? url.resourceValues(forKeys: Set(keys))
                if values?.isSymbolicLink == true {
                    undecided = true
                    continue
                }
                if values?.isDirectory == true {
                    if depth < maxDepth { frontier.append((url, depth + 1)) }
                    continue
                }
                let ext = url.pathExtension.lowercased()
                if ProjectFolderWatcher.eligibleExtensions.contains(ext),
                   !ProjectFolderWatcher.companionExtensions.contains(ext) {
                    return .present
                }
            }
        }
        return undecided ? .unknown : .gone
    }
}
