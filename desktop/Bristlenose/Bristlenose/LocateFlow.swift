import AppKit
import Foundation

/// The "Locate…" flow for a `.cantFind` project (HANDOFF §8+9).
///
/// Two-step search:
///   1. Spotlight one-shot via `NSMetadataQuery` — fires only if there's a
///      single high-confidence match AND it looks like an analysed Bristlenose
///      project (`bristlenose-output/` plus at least one canonical artefact
///      inside, see `folderLooksAnalysed(url:)`).
///   2. Otherwise, falls back to `NSOpenPanel` (directory-only).
///
/// On a directory pick (from either path) the folder is validated against the
/// same marker check. A single failure case keeps the error copy honest —
/// the prior split (noOutputFolder vs wrongFolder) leaned on a heuristic
/// that misclassified researchers who keep recordings in subdirs.
///
/// Pure UI orchestration — does not touch `ProjectIndex` directly. The caller
/// wires `onLocated` to `projectIndex.relocateProject(...)`.
@MainActor
final class LocateFlow {

    /// Result of running the flow.
    enum Result {
        case located(URL)
        /// Folder picked but doesn't look like an analysed Bristlenose project.
        /// Caller surfaces an alert with retry affordance.
        case invalidFolder(picked: URL)
        /// Folder is an analysed project, but a different study from this one
        /// (its marker carries another id). Relocating onto it would show
        /// someone else's analysis under this row (design-project-identity §7).
        case differentStudy(picked: URL)
        /// The folder carries a study marker this process may not read yet: a
        /// Spotlight hit has no sandbox grant. The caller opens the panel at
        /// it, which grants, and checks again (second review, 15 Oct 2026).
        case needsGrant(picked: URL)
        case cancelled
    }

    /// What a picked folder is, for this project. Pure but for the reads.
    enum Verdict: Equatable { case thisStudy, notAnalysed, differentStudy, unverified }

    /// A folder is this project's when it is analysed and, if both carry a
    /// study id, the ids agree. An absent id on either side cannot disagree:
    /// projects from before the marker locate as they always did.
    ///
    /// `granted` says whether this process may read the folder (a panel pick
    /// or a drop). Without it a marker that exists cannot be read, and an
    /// unread id must not pass as agreement — that is `.unverified`.
    static func verdict(url: URL, expectedStudyID: String?, granted: Bool = true) -> Verdict {
        guard folderLooksAnalysed(url: url) else { return .notAnalysed }
        guard let expectedStudyID else { return .thisStudy }
        if let found = StudyMarker.read(folder: url) {
            return found == expectedStudyID ? .thisStudy : .differentStudy
        }
        let markerExists = FileManager.default.fileExists(atPath: StudyMarker.url(forFolder: url).path)
        return markerExists && !granted ? .unverified : .thisStudy
    }

    /// Name of the marker subdirectory that identifies a Bristlenose project root.
    static let outputMarker = "bristlenose-output"

    /// Files inside `bristlenose-output/` that signal a real analysed project.
    /// At least one of these must exist — defeats the "empty marker dir
    /// confuses Spotlight" path (security finding #15).
    ///
    /// `.bristlenose/pipeline-manifest.json` (not the bare `.bristlenose/`
    /// directory) is the canonical marker: the directory itself is created
    /// the moment a run starts, so its presence is a "looks started" not
    /// "looks analysed" signal. Requiring the manifest file matches what
    /// `PipelineRunner.readManifestState` reads.
    static let outputArtefacts = [".bristlenose/pipeline-manifest.json"]

    private let project: Project
    private let spotlight: SpotlightOneShot
    private let i18n: I18n

    // Default `spotlight` to nil and construct inside the body — Swift 6
    // evaluates default-arg expressions in the caller's isolation context,
    // and `SpotlightOneShot.init` is `@MainActor`-isolated. Constructing
    // here keeps the call MainActor-scoped (this initializer is @MainActor
    // by class annotation) without forcing every caller to be async.
    init(project: Project, i18n: I18n, spotlight: SpotlightOneShot? = nil) {
        self.project = project
        self.i18n = i18n
        self.spotlight = spotlight ?? SpotlightOneShot()
    }

    /// Whether a directory looks like a real analysed Bristlenose project —
    /// contains `bristlenose-output/` AND at least one canonical artefact
    /// inside. Exposed as a static so the retry path (Choose Different…
    /// alert button) can reuse the same check.
    static func folderLooksAnalysed(url: URL) -> Bool {
        let outputDir = url.appendingPathComponent(outputMarker, isDirectory: true)
        var isDir: ObjCBool = false
        guard FileManager.default.fileExists(atPath: outputDir.path, isDirectory: &isDir),
              isDir.boolValue else { return false }
        return outputArtefacts.contains { name in
            FileManager.default.fileExists(atPath: outputDir.appendingPathComponent(name).path)
        }
    }

    /// Run the full flow. Calls `completion` exactly once on the main actor.
    /// `confirm` is shown when the Spotlight one-shot finds a unique match —
    /// the caller renders the sheet (Use This Folder / Choose Different… /
    /// Cancel) and resolves the continuation accordingly.
    func run(
        confirm: @escaping (URL) async -> SpotlightConfirmChoice,
        completion: @escaping (Result) -> Void
    ) {
        Task { @MainActor in
            // Phase 1 — Spotlight one-shot: by the study's id when it has one
            // (found wherever the folder went and whatever it is now called),
            // else by name. Either way the hit is verified against the hidden
            // marker once the panel grants the folder.
            // An ambiguous id search (a study and a backup of it, written at
            // the same moment) skips the name search, which could resolve the
            // tie to whichever copy happens to sit under the home folder.
            var candidate: URL?
            var ambiguous = false
            if let studyID = project.studyID {
                switch await spotlight.findStudy(id: studyID) {
                case .found(let url): candidate = url
                case .ambiguous: ambiguous = true
                case .none: break
                }
            }
            if candidate == nil, !ambiguous {
                candidate = await spotlight.findUniqueMatch(for: project.name)
            }
            if let candidate {
                let choice = await confirm(candidate)
                switch choice {
                case .useThisFolder:
                    completion(Self.afterSpotlightConfirm(candidate))
                    return
                case .chooseDifferent:
                    break  // fall through to NSOpenPanel
                case .cancel:
                    completion(.cancelled)
                    return
                }
            }
            // Phase 2 — NSOpenPanel directory pick.
            let panel = NSOpenPanel()
            panel.canChooseDirectories = true
            panel.canChooseFiles = false
            panel.allowsMultipleSelection = false
            panel.message = String(
                format: self.i18n.t("desktop.chrome.locateMessage"),
                self.project.name
            )
            panel.adoptHostAppearance()
            panel.begin { response in
                Task { @MainActor in
                    if response == .OK, let url = panel.url {
                        completion(self.validate(url: url, granted: true))
                    } else {
                        completion(.cancelled)
                    }
                }
            }
        }
    }

    /// A Spotlight hit carries no sandbox grant, so it can never be located
    /// directly: no bookmark can be made from it, and the row would then fail
    /// every read as "Can't be read". The panel, opened at the hit, is the
    /// grant, and the verdict is taken there (Fable review, 15 Oct 2026).
    nonisolated static func afterSpotlightConfirm(_ candidate: URL) -> Result {
        .needsGrant(picked: candidate)
    }

    /// Inspect the picked directory for the `bristlenose-output/` marker plus
    /// at least one canonical artefact. One honest message either way.
    private func validate(url: URL, granted: Bool) -> Result {
        // A panel pick carries the grant.
        switch Self.verdict(url: url, expectedStudyID: project.studyID, granted: granted) {
        case .thisStudy: return .located(url)
        case .notAnalysed: return .invalidFolder(picked: url)
        case .differentStudy: return .differentStudy(picked: url)
        case .unverified: return .needsGrant(picked: url)
        }
    }
}

// MARK: - Spotlight one-shot

/// Single-shot Spotlight directory lookup. Returns a unique high-confidence
/// match for a project name within the user's home tree, or nil.
///
/// "High confidence" means:
///   - Exactly one directory result from `NSMetadataQuery` with
///     `kMDItemDisplayName == project.name` and `kMDItemContentType ==
///     "public.folder"`.
///   - The directory passes `LocateFlow.folderLooksAnalysed` — i.e. has
///     `bristlenose-output/` containing a `manifest.json` or `.bristlenose`
///     marker. An empty `bristlenose-output/` is rejected.
///
/// The name search is limited to the user's home directory: a folder name is
/// weak evidence, and a wider search turns up strangers' folders. The study-id
/// search (`findUniqueStudy`) reaches every indexed volume, because an id is
/// strong evidence and a lost study has usually moved to another disk.
@MainActor
final class SpotlightOneShot {
    private var query: NSMetadataQuery?
    private var observation: NSObjectProtocol?

    /// Maximum time to wait for Spotlight to finish gathering. After this,
    /// we treat the query as "no result" and fall back to NSOpenPanel.
    /// 2s default — Apple Photos / Finder Spotlight panels wait around
    /// 2–3s before giving up; 1s was unfairly aggressive on cold indexes.
    let timeout: TimeInterval

    init(timeout: TimeInterval = 2.0) {
        self.timeout = timeout
    }

    deinit {
        if let observation { NotificationCenter.default.removeObserver(observation) }
    }

    func findUniqueMatch(for projectName: String) async -> URL? {
        guard !projectName.isEmpty else { return nil }
        let hits = await gather(
            predicate: NSPredicate(
                format: "kMDItemDisplayName ==[c] %@ AND kMDItemContentType == %@",
                projectName, "public.folder"
            ),
            scopes: [NSMetadataQueryUserHomeScope],
            folder: { $0 }
        )
        return hits.count == 1 ? hits.first : nil
    }

    /// What a search by study id found.
    enum StudySearch: Equatable {
        case found(URL)
        /// Several analysed hits and no way to tell which is in use.
        case ambiguous
        case none
    }

    /// The folder whose search beacon carries this study id
    /// (`StudyMarker.beaconFilename`, design-project-identity §13a). Searches
    /// every indexed volume, since a study is most often lost by being moved
    /// to another disk. More than one hit is a study plus a backup or a copy
    /// not yet given its own id: the one written to last is the one in use,
    /// and a tie is no answer, so the caller falls back to the name.
    func findStudy(id: String) async -> StudySearch {
        guard let query = Self.studyQuery(id: id),
              let predicate = NSPredicate(fromMetadataQueryString: query) else { return .none }
        let hits = await gather(
            predicate: predicate,
            scopes: [NSMetadataQueryLocalComputerScope],
            folder: Self.studyFolder(forBeacon:)
        )
        return Self.studySearch(hits.map { ($0, Self.lastWritten($0)) })
    }

    /// No hits is no answer; otherwise the newest, or ambiguous on a tie.
    nonisolated static func studySearch(_ hits: [(folder: URL, written: Date?)]) -> StudySearch {
        if hits.isEmpty { return .none }
        return newestStudy(hits).map(StudySearch.found) ?? .ambiguous
    }

    /// One hit is the answer; among several, the one whose study state was
    /// written strictly last. A clone made by a backup tool keeps its
    /// original's times, so a straight backup ties and gives no answer
    /// rather than a guess. The confirm sheet shows the path either way.
    nonisolated static func newestStudy(_ hits: [(folder: URL, written: Date?)]) -> URL? {
        if hits.count == 1 { return hits[0].folder }
        let dated = hits.compactMap { hit in hit.written.map { (hit.folder, $0) } }
        guard dated.count == hits.count,
              let newest = dated.map(\.1).max(),
              dated.filter({ $0.1 == newest }).count == 1 else { return nil }
        return dated.first { $0.1 == newest }?.0
    }

    /// When the study's database or manifest was last written: a metadata
    /// read, which a sandboxed app may make without a grant.
    nonisolated static func lastWritten(_ folder: URL) -> Date? {
        let state = folder.appendingPathComponent(LocateFlow.outputMarker, isDirectory: true)
            .appendingPathComponent(".bristlenose", isDirectory: true)
        let dates = ["bristlenose.db", "bristlenose.db-wal", "pipeline-manifest.json"].compactMap {
            (try? FileManager.default.attributesOfItem(
                atPath: state.appendingPathComponent($0).path))?[.modificationDate] as? Date
        }
        return dates.max()
    }

    /// The Spotlight query for a study's beacon, or nil for anything that is
    /// not a study id — the id is interpolated into a query string, so only a
    /// UUID's characters may reach it.
    nonisolated static func studyQuery(id: String) -> String? {
        guard let uuid = UUID(uuidString: id) else { return nil }
        let canonical = uuid.uuidString.lowercased()
        return "kMDItemFSName == \"\(StudyMarker.beaconFilename)\" && "
            + "kMDItemTextContent == \"*\(canonical)*\""
    }

    /// The project folder a beacon hit names: the beacon must sit, under its
    /// own name, directly inside a `bristlenose-output/` folder.
    nonisolated static func studyFolder(forBeacon url: URL) -> URL? {
        let output = url.deletingLastPathComponent()
        guard url.lastPathComponent == StudyMarker.beaconFilename,
              output.lastPathComponent == LocateFlow.outputMarker else { return nil }
        return output.deletingLastPathComponent()
    }

    /// The analysed folders a query names; empty on a timeout.
    private func gather(
        predicate: NSPredicate,
        scopes: [Any],
        folder: @escaping (URL) -> URL?
    ) async -> [URL] {
        // Re-entrance guard — previous call's observer (if any) is removed
        // before adding the new one. Not hit today (one SpotlightOneShot per
        // LocateFlow) but cheap defence against future callers that reuse
        // an instance.
        if let prior = observation {
            NotificationCenter.default.removeObserver(prior)
            observation = nil
        }
        query?.stop()

        return await withCheckedContinuation { (cont: CheckedContinuation<[URL], Never>) in
            let q = NSMetadataQuery()
            self.query = q
            q.searchScopes = scopes
            q.predicate = predicate

            // Single-fire continuation guard — gathering can complete before
            // the timeout fires and vice versa.
            let resumed = Resumed()

            observation = NotificationCenter.default.addObserver(
                forName: .NSMetadataQueryDidFinishGathering,
                object: q, queue: .main
            ) { [weak self] _ in
                guard let self else { return }
                let result = self.analysedHits(from: q, folder: folder)
                q.stop()
                if let obs = self.observation {
                    NotificationCenter.default.removeObserver(obs)
                    self.observation = nil
                }
                if resumed.tryConsume() {
                    cont.resume(returning: result)
                }
            }

            q.start()

            // Belt-and-suspenders timeout.
            Task { @MainActor in
                try? await Task.sleep(for: .seconds(self.timeout))
                if resumed.tryConsume() {
                    q.stop()
                    if let obs = self.observation {
                        NotificationCenter.default.removeObserver(obs)
                        self.observation = nil
                    }
                    cont.resume(returning: [])
                }
            }
        }
    }

    /// Walk the gathered results and return the unique high-confidence URL,
    /// or nil if there's zero or more-than-one match.
    private func analysedHits(from query: NSMetadataQuery, folder: (URL) -> URL?) -> [URL] {
        (0..<query.resultCount).compactMap { i -> URL? in
            guard let item = query.result(at: i) as? NSMetadataItem,
                  let path = item.value(forAttribute: NSMetadataItemPathKey) as? String,
                  let url = folder(URL(fileURLWithPath: path))
            else { return nil }
            return LocateFlow.folderLooksAnalysed(url: url) ? url : nil
        }
    }
}

/// Outcome of the Spotlight confirm sheet.
enum SpotlightConfirmChoice {
    case useThisFolder
    case chooseDifferent
    case cancel
}

/// Tiny mutual-exclusion box so the gathering callback and the timeout
/// Task can't both resume the continuation.
@MainActor
private final class Resumed {
    private var done = false
    func tryConsume() -> Bool {
        if done { return false }
        done = true
        return true
    }
}
