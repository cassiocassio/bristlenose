import Foundation
import OSLog

private let log = Logger(subsystem: "app.bristlenose", category: "folder-watcher")

// MARK: PII — UI-only, never log
// Filenames captured here may identify participants. Render to UI only.
// Never write basenames to os_log, pipeline-events.jsonl, or any persisted channel.

/// Snapshot of unanalysed files in a project's top-level folder, plus a count
/// of previously-ingested files that have gone missing. Published to
/// `ProjectIndex` by `ProjectFolderWatcher`.
struct UnanalysedState: Equatable {
    /// Files present at the project root, with eligible extensions, that are
    /// not in the ingested-set. Empty when there's nothing new.
    let newFiles: [URL]
    /// Files previously ingested that are no longer present and are not
    /// iCloud-evicted. Used to render the "N missing" badge.
    let missingFiles: [URL]

    static let empty = UnanalysedState(newFiles: [], missingFiles: [])

    var isEmpty: Bool { newFiles.isEmpty && missingFiles.isEmpty }
}

/// Watches a project's top-level folder for Finder-side file additions and
/// deletions; emits an `UnanalysedState` whenever the diff changes.
///
/// **API choice — NSFilePresenter, not DispatchSource.** Sandbox-friendly,
/// push-based, recommended for user-selected folders. Revisit only if
/// `presentedSubitemDidAppear` proves unreliable on external volumes.
///
/// **Lease lifetime.** The watcher holds a strong reference to a
/// `ProjectBookmarkLease`. The security scope stays open for the entire
/// life of the watcher; NSFilePresenter callbacks fire from arbitrary
/// queues and must find scope still open. Caller (typically `ProjectIndex`)
/// owns watcher lifecycle: register on `→ .ready`, dispose on
/// `→ .cantFind` / `→ .inCloud`.
///
/// **Top-level only.** Subfolder content changes are filtered out by
/// `subitemIsTopLevel(_:)` before any scan is scheduled.
///
/// **Thread model.** `knownBasenames` is confined to `scanQueue`; both
/// `seedKnown(basenames:)` and `performScan()` mutate it on that queue.
/// `onChange` is always invoked on the main actor.
final class ProjectFolderWatcher: NSObject, NSFilePresenter, @unchecked Sendable {

    /// Project ID this watcher belongs to. Used by callers to key state.
    let projectID: UUID
    private let lease: ProjectBookmarkLease
    private let onChange: @Sendable (UnanalysedState) -> Void

    /// Background queue used to serialise diff work and confine
    /// `knownBasenames`. All scan + mutation happens here.
    private let scanQueue: DispatchQueue
    /// Confined to `scanQueue`.
    private var knownBasenames: Set<String>
    /// Confined to `scanQueue`. Suppresses no-op `onChange` calls.
    private var lastPublished: UnanalysedState = .empty

    /// Eligible top-level extensions. Lowercased; comparison is case-insensitive.
    static let eligibleExtensions: Set<String> = [
        "mp4", "mov", "m4a", "mp3", "wav", "vtt", "srt", "docx", "txt"
    ]

    // MARK: - NSFilePresenter contract

    var presentedItemURL: URL? { lease.url }
    var presentedItemOperationQueue: OperationQueue { Self.sharedPresenterQueue }

    nonisolated(unsafe) private static let sharedPresenterQueue: OperationQueue = {
        let q = OperationQueue()
        q.maxConcurrentOperationCount = 1
        q.name = "app.bristlenose.folder-watcher.presenter"
        return q
    }()

    // MARK: - Lifecycle

    init(
        projectID: UUID,
        lease: ProjectBookmarkLease,
        initialKnownBasenames: Set<String>,
        onChange: @escaping @Sendable (UnanalysedState) -> Void
    ) {
        self.projectID = projectID
        self.lease = lease
        self.knownBasenames = initialKnownBasenames
        self.onChange = onChange
        self.scanQueue = DispatchQueue(
            label: "app.bristlenose.folder-watcher.scan.\(projectID.uuidString)",
            qos: .utility
        )
        super.init()
        NSFileCoordinator.addFilePresenter(self)
        scheduleScan()
    }

    deinit {
        NSFileCoordinator.removeFilePresenter(self)
    }

    // MARK: - Public API

    /// Extend the known-basenames set after a copy completes. Suppresses the
    /// count pill for files freshly copied via drag-onto (#11).
    func seedKnown(basenames: Set<String>) {
        scanQueue.async { [weak self] in
            guard let self else { return }
            self.knownBasenames.formUnion(basenames)
            self.performScanLocked()
        }
    }

    /// Force a re-scan. Useful when the caller knows the ingested-set has
    /// changed (e.g. analysis just finished).
    func refresh() {
        scheduleScan()
    }

    // MARK: - NSFilePresenter callbacks

    func presentedSubitemDidAppear(at url: URL) {
        guard subitemIsTopLevel(url), isEligibleExtension(url) else { return }
        scheduleScan()
    }

    func presentedSubitemDidChange(at url: URL) {
        guard subitemIsTopLevel(url), isEligibleExtension(url) else { return }
        scheduleScan()
    }

    func accommodatePresentedSubitemDeletion(
        at url: URL,
        completionHandler: @escaping ((any Error)?) -> Void
    ) {
        if subitemIsTopLevel(url), isEligibleExtension(url) {
            scheduleScan()
        }
        completionHandler(nil)
    }

    // MARK: - Scan

    private func scheduleScan() {
        scanQueue.async { [weak self] in
            self?.performScanLocked()
        }
    }

    /// Diff the on-disk top-level eligible files against the ingested-set
    /// and the known-set; publish a new state if it changed. Caller must
    /// already be on `scanQueue`.
    private func performScanLocked() {
        guard let projectURL = presentedItemURL else { return }

        let topLevelEligible = Self.enumerateTopLevelEligible(projectURL)
        let ingested = SourceFilesReader.ingestedBasenames(projectRoot: projectURL)

        var newFiles: [URL] = []
        var presentBasenames: Set<String> = []
        for url in topLevelEligible {
            let base = url.lastPathComponent
            presentBasenames.insert(base)
            if !ingested.contains(base) && !knownBasenames.contains(base) {
                newFiles.append(url)
            }
        }

        var missingFiles: [URL] = []
        for base in ingested where !presentBasenames.contains(base) {
            let candidate = projectURL.appendingPathComponent(base)
            if Self.isCloudEvicted(candidate) { continue }
            missingFiles.append(candidate)
        }

        let state = UnanalysedState(newFiles: newFiles, missingFiles: missingFiles)
        if state == lastPublished { return }
        lastPublished = state
        let cb = onChange
        DispatchQueue.main.async { cb(state) }
    }

    // MARK: - Filters (also used by unit tests via DropDecision-style pure helpers)

    func subitemIsTopLevel(_ url: URL) -> Bool {
        guard let root = presentedItemURL else { return false }
        return url.deletingLastPathComponent().standardizedFileURL ==
            root.standardizedFileURL
    }

    func isEligibleExtension(_ url: URL) -> Bool {
        Self.eligibleExtensions.contains(url.pathExtension.lowercased())
    }

    /// Pure helper exposed for unit testing — filters a candidate URL list to
    /// the same "top-level eligible" set used by the watcher.
    static func filterEligible(at root: URL, candidates: [URL]) -> [URL] {
        candidates.filter { url in
            let name = url.lastPathComponent
            if name == "bristlenose-output" { return false }
            if name.hasPrefix(".") { return false }
            if !eligibleExtensions.contains(url.pathExtension.lowercased()) {
                return false
            }
            return url.deletingLastPathComponent().standardizedFileURL ==
                root.standardizedFileURL
        }
    }

    private static func enumerateTopLevelEligible(_ root: URL) -> [URL] {
        let fm = FileManager.default
        let keys: [URLResourceKey] = [.isRegularFileKey]
        guard let contents = try? fm.contentsOfDirectory(
            at: root,
            includingPropertiesForKeys: keys,
            options: [.skipsHiddenFiles, .skipsSubdirectoryDescendants]
        ) else { return [] }

        return contents.filter { url in
            let name = url.lastPathComponent
            if name == "bristlenose-output" { return false }
            if name.hasPrefix(".") { return false }
            if !eligibleExtensions.contains(url.pathExtension.lowercased()) {
                return false
            }
            let values = try? url.resourceValues(forKeys: [.isRegularFileKey])
            return values?.isRegularFile == true
        }
    }

    /// True when a missing file is actually iCloud-evicted (still "logically
    /// present"). Such files are not treated as truly missing.
    static func isCloudEvicted(_ url: URL) -> Bool {
        let values = try? url.resourceValues(
            forKeys: [.ubiquitousItemDownloadingStatusKey]
        )
        guard let status = values?.ubiquitousItemDownloadingStatus else { return false }
        return status == .notDownloaded || status == .downloaded
    }
}
