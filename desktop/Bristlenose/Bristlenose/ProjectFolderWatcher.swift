import Foundation
import OSLog

private let log = Logger(subsystem: "app.bristlenose", category: "folder-watcher")

// MARK: PII — UI-only, never log
// Filenames captured here may identify participants. Render to UI only.
// Never write basenames to os_log, pipeline-events.jsonl, or any persisted channel.

/// Snapshot of a project's data state: unanalysed-but-present files, missing
/// previously-ingested files, and the canonical session count. Published to
/// `ProjectIndex` by `ProjectFolderWatcher` on every scan.
struct UnanalysedState: Equatable {
    /// Files `run` would analyse (its own file selection, `ScanSelection`, so
    /// subfolders up to three deep count) that are not in the ingested-set.
    /// Matched by basename. Empty when there's nothing new.
    let newFiles: [URL]
    /// Files previously ingested that are no longer present and are not
    /// iCloud-evicted. Surfaces in the row subtitle delta and the sheet.
    let missingFiles: [URL]
    /// Count of rows in the `sessions` table — the canonical "size of the
    /// study" metric rendered on the row's title line. Nil when the DB
    /// isn't readable (pre-analysis, locked, etc.).
    let sessionCount: Int?
    /// Sum of `sessions.duration_seconds` — total interview time across the
    /// study, matching the Project dashboard's "Total" stat. Feeds the native
    /// window subtitle ("16 Sessions · 18h 23m"). Nil when the DB isn't
    /// readable; 0 when there are no sessions yet. Mirrors `sessionCount`.
    let totalDurationSeconds: Double?
    /// Whether the folder holds anything the pipeline would actually ingest.
    ///
    /// **Deliberately not derived from `newFiles`.** `newFiles` answers "what
    /// drifted since the last run", and `ProjectIndex` zeroes it for projects
    /// that have never been analysed (F14 policy). So a fresh folder full of
    /// recordings reports `newFiles: []` — reading that as "nothing to do"
    /// would hide Analyse on exactly the project that needs it. This field
    /// answers the different question, "is there anything here", and survives
    /// the F14 gate untouched.
    ///
    /// Counted with `run`'s own file selection (`ScanSelection`, decision #111):
    /// up to three folders deep, the same skips, the same extensions. A study
    /// kept in per-participant folders counted zero here until 21 Oct 2026,
    /// and read "Drag Interviews Here" over interviews `run` would analyse.
    /// Excludes companion types (`.txt`): drag-and-drop carries a note into the
    /// project, but `classify_file` returns `None` for it, so a folder holding
    /// only notes has nothing to analyse.
    ///
    /// **A count, not a flag, because the detail pane promises the number.**
    /// "6 files to analyse" and the decision to offer Analyse at all have to
    /// come from one measurement or the app contradicts itself — and a stored
    /// `Bool` would also make `Equatable` blind to a seventh file arriving in a
    /// never-analysed folder (F14 zeroes `newFiles`, so nothing else in the
    /// published state would move), leaving the pane's count stale.
    let ingestableFileCount: Int

    /// An analysed project whose Discussion lens has nothing to show yet — no
    /// record (analysed before the lens existed), or a guide folder changed
    /// after the record was written. Offers **Analyse**, which resumes: only
    /// the discussion stage runs and nothing the researcher edited is lost.
    /// Without it the only re-run on the Mac is **Re-analyse…**, which starts
    /// over (decided 4 Oct 2026). Defaulted so the many test constructions of
    /// this state stay as they are.
    var discussionWanted: Bool = false

    /// The analysis database holds more than one project row, so the report
    /// (which reads row 1) and the sidebar counts (now also row 1) may be
    /// describing less than the run produced. Always a defect upstream — a
    /// serve that started while `bristlenose-output/` was moved aside (12 Oct
    /// 2026) — and surfaced here because the sidebar is the one place that can
    /// say so. Defaulted for the same reason as `discussionWanted`.
    var databaseForked: Bool = false

    /// Whether the folder holds anything the pipeline would ingest. Derived, so
    /// the gate and the promised count cannot drift apart.
    var hasIngestableFiles: Bool { ingestableFileCount > 0 }

    static let empty = UnanalysedState(
        newFiles: [], missingFiles: [], sessionCount: nil, totalDurationSeconds: nil,
        ingestableFileCount: 0
    )

    /// True when there's nothing to render for the data-state deltas (no
    /// newFiles, no missingFiles). The session count is independent — a
    /// project can have a session count but no deltas; that's the steady
    /// state.
    var hasDeltas: Bool { !newFiles.isEmpty || !missingFiles.isEmpty }
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
/// `→ .cantFind`.
///
/// **As deep as `run` looks.** The scan is `ScanSelection` — `run`'s file
/// selection — and `subitemMayChangeTheCount(_:)` lets through a change anywhere
/// that selection could see it, so a recording added to a participant folder
/// rescans. `bristlenose-output/` and hidden folders stay out, so a run's own
/// writes schedule nothing.
///
/// **Thread model.** `knownBasenames` is confined to `scanQueue`; both
/// `seedKnown(basenames:)` and `performScan()` mutate it on that queue.
/// `onChange` is always invoked on the main actor.
///
/// **`@unchecked Sendable` soundness.** Hand-audited: `lease` is set once
/// in init and never mutated except in `deinit`; `onChange` is `@Sendable`
/// by type and only invoked via `DispatchQueue.main.async`; `knownBasenames`,
/// `lastPublished`, and `pendingScan` are scanQueue-confined (all reads and
/// writes hop through `scanQueue.async`). NSFilePresenter callbacks arrive
/// on `sharedPresenterQueue` but only call `scheduleScan()`, which hops to
/// `scanQueue`. No state is read or written off-queue. The unchecked waiver
/// is justified by this confinement discipline — if a future change shares
/// state across queues, this conformance must become checked or drop.
final class ProjectFolderWatcher: NSObject, NSFilePresenter, @unchecked Sendable {

    /// Project ID this watcher belongs to. Used by callers to key state.
    let projectID: UUID
    private let lease: ProjectBookmarkLease
    private let onChange: @Sendable (UnanalysedState) -> Void
    /// Told, on the main actor, when the presented folder is renamed or moved
    /// under us. Optional: tests of the scan path pass nothing.
    private let onMove: (@Sendable (URL) -> Void)?

    /// Background queue used to serialise diff work and confine
    /// `knownBasenames`. All scan + mutation happens here.
    private let scanQueue: DispatchQueue
    /// Confined to `scanQueue`.
    private var knownBasenames: Set<String>
    /// Confined to `scanQueue`. Suppresses no-op `onChange` calls.
    /// Nil until the first scan publishes — **not** seeded to `.empty`.
    ///
    /// Seeding it to `.empty` meant "we have already published nothing", so a
    /// scan of an empty folder equalled it and was suppressed. The project's
    /// entry in `ProjectIndex.unanalysed` therefore stayed *absent*, which is
    /// the same signal as "no watcher running" — and consumers that treat
    /// absent as unknown could not tell a folder we had looked at and found
    /// empty from one we had never looked at. `canAnalyse` resolves unknown to
    /// *offer*, so Analyse kept appearing on empty projects even after it
    /// learned to check. Publishing the first scan unconditionally makes
    /// absence mean only what it says.
    private var lastPublished: UnanalysedState?
    /// Confined to `scanQueue`. Pending debounced scan; replaced on each new
    /// event so a burst of Finder callbacks collapses to one scan after the
    /// debounce window expires.
    private var pendingScan: DispatchWorkItem?
    /// Debounce window. Finder copying many files fires per-file
    /// `presentedSubitemDidAppear` callbacks in rapid succession; one scan
    /// after the burst quiets is enough.
    private static let scanDebounce: DispatchTimeInterval = .milliseconds(300)

    /// Eligible extensions. Lowercased; comparison is case-insensitive.
    ///
    /// **Must stay in step with `ContentView.acceptedExtensions` and, through it,
    /// `bristlenose/models.py`'s `ALL_EXTENSIONS`.** This set gates both halves of
    /// `UnanalysedState`, so anything missing here gets no new-files count and no
    /// missing-file warning — while drag-and-drop happily accepts, copies and
    /// analyses it. The two sets were written in separate commits (`0cfc99da` for
    /// drag-drop, `10680cbd` here) and silently disagreed for months: a dropped
    /// `.mkv`, `.webm`, `.avi`, `.m4v`, `.flac`, `.ogg`, `.wma` or `.aac` was
    /// invisible to the watcher. Pinned by `tests/test_accepted_extension_parity.py`.
    static let eligibleExtensions: Set<String> = [
        // Audio
        "wav", "mp3", "m4a", "flac", "ogg", "wma", "aac",
        "aiff", "aif", "caf",
        // Video
        "mp4", "m4v", "mov", "avi", "mkv", "webm",
        "wmv", "asf", "mts", "m2ts", "3gp", "flv", "mpg", "mpeg",
        // Subtitles
        "srt", "vtt",
        // Documents
        "docx", "txt",
    ]

    /// Accepted into a project, but never ingested — `classify_file` returns
    /// `None`. Carried so a researcher's notes travel with the recordings;
    /// excluded from `hasIngestableFiles` so a folder of only notes doesn't
    /// look analysable.
    static let companionExtensions: Set<String> = ["txt"]

    // MARK: - NSFilePresenter contract

    /// The folder as the coordinator last told us it is. Starts as the lease's
    /// URL and **follows a rename** via `presentedItemDidMove(to:)`. It was
    /// `lease.url` verbatim until 12 Oct 2026, so a Finder rename left every
    /// scan — and, through `onMove` not existing, the serve — on a path that
    /// no longer had a folder behind it. Read from arbitrary queues (the
    /// coordinator's, `scanQueue`), hence the lock.
    var presentedItemURL: URL? { urlLock.withLock { currentURL } }
    private let urlLock = NSLock()
    private var currentURL: URL
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
        onMove: (@Sendable (URL) -> Void)? = nil,
        onChange: @escaping @Sendable (UnanalysedState) -> Void
    ) {
        self.projectID = projectID
        self.lease = lease
        self.currentURL = lease.url
        self.knownBasenames = initialKnownBasenames
        self.onMove = onMove
        self.onChange = onChange
        self.scanQueue = DispatchQueue(
            label: "app.bristlenose.folder-watcher.scan.\(projectID.uuidString)",
            qos: .utility
        )
        super.init()
        NSFileCoordinator.addFilePresenter(self)
        // Run the initial scan immediately, not via the debounce window —
        // callers want baseline state without waiting 300ms.
        scanQueue.async { [weak self] in self?.performScanLocked() }
    }

    deinit {
        pendingScan?.cancel()
        NSFileCoordinator.removeFilePresenter(self)
    }

    /// Unregister from `NSFileCoordinator`. Call it before dropping the last
    /// reference: the coordinator retains its registered presenters, so
    /// `deinit` — and the removal in it — never runs on its own, and a
    /// released watcher would keep its lease (the security scope) open and
    /// go on scanning. Pinned by `ProjectFolderWatcherLifetimeTests`.
    func stop() {
        NSFileCoordinator.removeFilePresenter(self)
        scanQueue.async { [weak self] in
            self?.pendingScan?.cancel()
            self?.pendingScan = nil
        }
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

    /// The folder itself was renamed or moved. Follow it, tell the owner, and
    /// rescan — the recorded source paths are now all stale and
    /// `missingIngestedFiles` resolves them against the live root.
    func presentedItemDidMove(to newURL: URL) {
        urlLock.withLock { currentURL = newURL }
        if let onMove {
            DispatchQueue.main.async { onMove(newURL) }
        }
        scheduleScan()
    }

    func presentedSubitemDidAppear(at url: URL) {
        guard subitemMayChangeTheCount(url) else { return }
        scheduleScan()
    }

    func presentedSubitemDidChange(at url: URL) {
        guard subitemMayChangeTheCount(url) else { return }
        scheduleScan()
    }

    /// A participant folder renamed, or moved to the Trash, in Finder.
    func presentedSubitem(at oldURL: URL, didMoveTo newURL: URL) {
        guard subitemMayChangeTheCount(oldURL) || subitemMayChangeTheCount(newURL) else { return }
        scheduleScan()
    }

    func accommodatePresentedSubitemDeletion(
        at url: URL,
        completionHandler: @escaping ((any Error)?) -> Void
    ) {
        if subitemMayChangeTheCount(url) {
            scheduleScan()
        }
        completionHandler(nil)
    }

    // MARK: - Scan

    /// Debounced scan trigger. A burst of NSFilePresenter callbacks during a
    /// Finder copy of N files collapses to a single scan ~300ms after the
    /// last callback. Replaces the pending work item on each call.
    private func scheduleScan() {
        scanQueue.async { [weak self] in
            guard let self else { return }
            self.pendingScan?.cancel()
            let item = DispatchWorkItem { [weak self] in
                self?.performScanLocked()
            }
            self.pendingScan = item
            self.scanQueue.asyncAfter(deadline: .now() + Self.scanDebounce, execute: item)
        }
    }

    /// Diff the files `run` would analyse against the ingested-set and the
    /// known-set; publish a new state if it changed. Caller must already be on
    /// `scanQueue` — the walk lists and stats a folder tree.
    private func performScanLocked() {
        guard let projectURL = presentedItemURL else { return }

        // `run`'s own selection (decision #111): subfolders up to three deep,
        // the same skips and refusals, never a file opened.
        let readable = ScanSelection.readableFiles(under: projectURL)
        let snapshot = SourceFilesReader.readSnapshot(projectRoot: projectURL)
        let ingested = snapshot.ingestedBasenames

        let newFiles = Self.newFiles(
            readable: readable, root: projectURL, ingested: ingested, known: knownBasenames
        )

        // An unreadable snapshot must not retract a correct warning. `nil` here
        // is SQLITE_BUSY or corruption — publishing `[]` for it would clear a
        // standing "these files are gone" alarm AND record the empty state as
        // the new baseline, and nothing schedules a rescan for a DB-only change.
        let missingFiles: [URL]
        if let paths = snapshot.ingestedPaths {
            missingFiles = Self.missingIngestedFiles(
                ingestedPaths: paths, projectRoot: projectURL
            )
        } else {
            missingFiles = lastPublished?.missingFiles ?? []
        }

        // Computed from the raw selection, before any drift logic — see the
        // field's doc comment for why it must not come from `newFiles`.
        let ingestableCount = readable.count

        let state = UnanalysedState(
            newFiles: newFiles,
            missingFiles: missingFiles,
            sessionCount: snapshot.sessionCount,
            totalDurationSeconds: snapshot.totalDurationSeconds,
            ingestableFileCount: ingestableCount,
            discussionWanted: (snapshot.sessionCount ?? 0) > 0
                && Self.discussionWanted(projectRoot: projectURL),
            databaseForked: snapshot.isForked
        )
        guard Self.shouldPublish(state, lastPublished: lastPublished) else { return }
        lastPublished = state
        let cb = onChange
        DispatchQueue.main.async { cb(state) }
    }

    /// The record the Discussion stage writes, and the guide folder beside the
    /// recordings — both found the way the pipeline finds them
    /// (`bristlenose/discussion/guide.py`): the output folder if there is one,
    /// and the guide folder by name, case-blind.
    nonisolated static func discussionWanted(projectRoot: URL, fileManager: FileManager = .default) -> Bool {
        let output = projectRoot.appendingPathComponent("bristlenose-output")
        var isDir: ObjCBool = false
        let outputDir = fileManager.fileExists(atPath: output.path, isDirectory: &isDir) && isDir.boolValue
            ? output : projectRoot
        let record = outputDir.appendingPathComponent(".bristlenose/intermediate/discussion.json")
        guard let recordDate = modified(record, fileManager) else { return true }
        guard let entries = try? fileManager.contentsOfDirectory(
            at: projectRoot, includingPropertiesForKeys: [.isDirectoryKey], options: [.skipsHiddenFiles]),
              let guide = entries.first(where: {
                  $0.lastPathComponent.lowercased() == DiscussionGuide.folderName.lowercased() })
        else { return false }
        // The folder's own date moves when a file is added or removed; a file's
        // moves when it is saved in place.
        var newest = modified(guide, fileManager) ?? .distantPast
        let inside = (try? fileManager.contentsOfDirectory(
            at: guide, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles])) ?? []
        for file in inside {
            if let d = modified(file, fileManager), d > newest { newest = d }
        }
        return newest > recordDate
    }

    private nonisolated static func modified(_ url: URL, _ fileManager: FileManager) -> Date? {
        (try? fileManager.attributesOfItem(atPath: url.path))?[.modificationDate] as? Date
    }

    /// Whether a freshly-computed state is worth publishing.
    ///
    /// Pure so the first-scan invariant can be tested without an
    /// `NSFilePresenter`, a lease or a temp folder: a `nil` previous value
    /// means nothing has been published yet, so **every** first scan goes out —
    /// including one that found nothing.
    static func shouldPublish(_ state: UnanalysedState, lastPublished: UnanalysedState?) -> Bool {
        state != lastPublished
    }

    // MARK: - Filters

    /// Whether a change at `url` can move the count, so is worth a rescan.
    /// Was "top level, eligible extension" until decision #111, so a recording
    /// added to a participant folder never rescanned.
    func subitemMayChangeTheCount(_ url: URL) -> Bool {
        guard let root = presentedItemURL else { return false }
        return Self.mayChangeTheCount(url, root: root)
    }

    /// In the selection's reach (`scanScopeDepth`), and either a file of a kind
    /// the watcher counts or something that may be a folder. Above the deepest
    /// level anything but an existing file of another kind counts as a possible
    /// folder: `P1.Smith/` has an "extension", and a folder that has just been
    /// deleted or moved cannot be asked what it was.
    static func mayChangeTheCount(
        _ url: URL, root: URL,
        isRegularFile: (URL) -> Bool = {
            (try? $0.resourceValues(forKeys: [.isRegularFileKey]))?.isRegularFile == true
        }
    ) -> Bool {
        guard let depth = scanScopeDepth(url, root: root) else { return false }
        if eligibleExtensions.contains(url.pathExtension.lowercased()) { return true }
        return depth < ScanSelection.maxDepth && !isRegularFile(url)
    }

    /// How many levels below `root` the change is, when it is somewhere `run`'s
    /// selection could see: at most `ScanSelection.maxDepth` deep, and not under
    /// a hidden folder, OS metadata, our own artefacts, `bristlenose-output/`
    /// or the top-level discussion guide. Nil otherwise — so a run's writes into
    /// its own output schedule nothing.
    static func scanScopeDepth(_ url: URL, root: URL) -> Int? {
        let rootPath = root.standardizedFileURL.path
        let path = url.standardizedFileURL.path
        let prefix = rootPath.hasSuffix("/") ? rootPath : rootPath + "/"
        guard path.hasPrefix(prefix) else { return nil }
        let parts = path.dropFirst(prefix.count).split(separator: "/").map(String.init)
        guard !parts.isEmpty, parts.count <= ScanSelection.maxDepth else { return nil }
        for part in parts {
            if part.hasPrefix(".") || ScanSelection.isOSMetadata(part)
                || ScanSelection.isArtefact(part) || part == ScanSelection.outputDirName {
                return nil
            }
        }
        if parts.count > 1,
           parts[0].lowercased() == DiscussionGuide.folderName.lowercased() {
            return nil
        }
        return parts.count
    }

    /// Readable files not yet analysed, by name.
    ///
    /// `source_files` holds ONE path per session (`session.files[0]`), so a
    /// session's other files — the `.m4a` beside a Zoom folder's `.mp4`, the
    /// `.vtt` beside a Teams recording — never appear in `ingested`. Matching by
    /// basename alone would list them as unanalysed after every run, and offer
    /// an Analyse that changes nothing. So below the top level a folder holding
    /// any ingested file counts as analysed whole: a new participant folder is
    /// new, a file added to an analysed one is not reported (a known gap — the
    /// sessions `run` would form are `group_into_sessions`' call, not ours). At
    /// the top level each file stands alone, as it always has. Names, not
    /// paths: a recorded path goes stale on every folder rename
    /// (`missingIngestedFiles`).
    static func newFiles(
        readable: [URL], root: URL, ingested: Set<String>, known: Set<String>
    ) -> [URL] {
        let rootPath = root.standardizedFileURL.path
        func folder(_ url: URL) -> String { url.deletingLastPathComponent().standardizedFileURL.path }
        let analysedFolders = Set(readable
            .filter { ingested.contains($0.lastPathComponent) && folder($0) != rootPath }
            .map(folder))
        return readable.filter { url in
            let base = url.lastPathComponent
            if ingested.contains(base) || known.contains(base) { return false }
            return !analysedFolders.contains(folder(url))
        }
        // Sorted for stable Equatable comparison and stable display order.
        .sorted { $0.lastPathComponent < $1.lastPathComponent }
    }

    /// Which ingested files are genuinely gone.
    ///
    /// ASK THE RECORDED PATH, NOT THE TOP-LEVEL SCAN. This used to diff
    /// ingested *basenames* against the basenames of `enumerateTopLevelEligible`
    /// — a top-level-only walk. Python's `discover_files` descends up to
    /// `_MAX_SCAN_DEPTH = 3`, so any project whose recordings sit in a subfolder
    /// matched nothing and had EVERY ingested file reported missing. Seen
    /// 30 Aug 2026 on a project with all three recordings present in
    /// `interviews/`, told they were "no longer in the project folder" — which
    /// they were not.
    ///
    /// The pipeline already records the full path it ingested, so checking that
    /// path directly is both correct and cheaper than deepening the enumeration
    /// to match. It also removes any need for the two scanners to agree on depth.
    ///
    /// The eviction skip stays load-bearing: an evicted placeholder fails
    /// `exists` exactly as it failed the old `isRegularFileKey` test, so without
    /// it a file that is merely not-downloaded reads as deleted.
    ///
    /// AND THE RECORDED PATH IS NOT THE WHOLE ANSWER EITHER. `source_files.path`
    /// is written once, absolute, at import (`importer.py`), and nothing ever
    /// corrects it — `_import_source_files` skips sessions that already have
    /// rows. Meanwhile `ProjectIndex.refreshAvailability` and `relocateProject`
    /// rewrite `project.path` whenever the folder moves or is re-Located, and
    /// neither touches the database. So renaming or moving a study folder makes
    /// EVERY recorded path stale at once.
    ///
    /// That is the failure mode the old basename diff was accidentally immune
    /// to, and researchers rename and move project folders far more often than
    /// they nest recordings. Checking only the recorded path would have traded
    /// one false alarm for a louder one. So: a file is present if its recorded
    /// path resolves, OR if a file of that name can be found under the LIVE
    /// project root. The walk is bounded to the same depth Python's
    /// `discover_files` uses, and is only ever paid on a miss — which on a
    /// healthy project is never.
    ///
    /// `exists`, `evicted` and `locatable` are injected so this is unit-testable
    /// without a filesystem — the same shape as `LensItem.all` and
    /// `ProjectSubtitle.resolve`.
    static func missingIngestedFiles(
        ingestedPaths: Set<String>,
        projectRoot: URL,
        exists: (String) -> Bool = { FileManager.default.fileExists(atPath: $0) },
        evicted: (URL) -> Bool = { ProjectFolderWatcher.isCloudEvicted($0) },
        locatable: (String, URL) -> Bool = {
            ProjectFolderWatcher.basenameResolves($0, under: $1)
        }
    ) -> [URL] {
        var missing: [URL] = []
        for path in ingestedPaths {
            if exists(path) { continue }
            let candidate = URL(fileURLWithPath: path)
            if evicted(candidate) { continue }
            // The folder moved, or the file did. Either way it is here.
            if locatable(candidate.lastPathComponent, projectRoot) { continue }
            missing.append(candidate)
        }
        // Sort for stable Equatable comparison and stable display order.
        missing.sort { $0.lastPathComponent < $1.lastPathComponent }
        return missing
    }

    /// Is a file of this name anywhere under `root`, within the same depth
    /// Python's `discover_files` scans (`_MAX_SCAN_DEPTH = 3`)?
    ///
    /// Deliberately matches on NAME, not content: this answers "did the path we
    /// recorded go stale", not "is this the same bytes". A researcher who moved
    /// a folder has the same file; one who replaced a recording with a different
    /// one of the same name has bigger problems than this glyph.
    static func basenameResolves(_ basename: String, under root: URL) -> Bool {
        guard let walker = FileManager.default.enumerator(
            at: root,
            includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles, .skipsPackageDescendants]
        ) else { return false }
        for case let url as URL in walker {
            if walker.level > maxScanDepth {
                walker.skipDescendants()
                continue
            }
            if url.lastPathComponent == basename { return true }
        }
        return false
    }

    /// Mirrors `_MAX_SCAN_DEPTH` in `bristlenose/stages/s01_ingest.py`. The two
    /// scanners disagreeing about depth is what produced the false "3 missing"
    /// this function was rewritten to fix. One constant with `ScanSelection`.
    static let maxScanDepth = ScanSelection.maxDepth

    /// True when a missing file is actually iCloud-evicted (still "logically
    /// present"). Such files are not treated as truly missing.
    ///
    /// Only `.notDownloaded` counts as evicted. `.downloaded` and `.current`
    /// mean the file IS locally present — those would normally show up in
    /// directory enumeration and never reach this branch; if they don't,
    /// the file is genuinely gone, not evicted.
    static func isCloudEvicted(_ url: URL) -> Bool {
        let values = try? url.resourceValues(
            forKeys: [.ubiquitousItemDownloadingStatusKey]
        )
        guard let status = values?.ubiquitousItemDownloadingStatus else { return false }
        return status == .notDownloaded
    }
}
