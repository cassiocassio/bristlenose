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
        case cancelled
    }

    /// Name of the marker subdirectory that identifies a Bristlenose project root.
    static let outputMarker = "bristlenose-output"

    /// Files inside `bristlenose-output/` that signal a real analysed project.
    /// At least one of these must exist — defeats the "empty marker dir
    /// confuses Spotlight" path (security finding #15).
    static let outputArtefacts = ["manifest.json", ".bristlenose"]

    private let project: Project
    private let spotlight: SpotlightOneShot
    private let i18n: I18n

    init(project: Project, i18n: I18n, spotlight: SpotlightOneShot = SpotlightOneShot()) {
        self.project = project
        self.i18n = i18n
        self.spotlight = spotlight
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
            // Phase 1 — Spotlight one-shot.
            if let candidate = await spotlight.findUniqueMatch(for: project.name) {
                let choice = await confirm(candidate)
                switch choice {
                case .useThisFolder:
                    completion(self.validate(url: candidate))
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
            panel.begin { response in
                Task { @MainActor in
                    if response == .OK, let url = panel.url {
                        completion(self.validate(url: url))
                    } else {
                        completion(.cancelled)
                    }
                }
            }
        }
    }

    /// Inspect the picked directory for the `bristlenose-output/` marker plus
    /// at least one canonical artefact. One honest message either way.
    private func validate(url: URL) -> Result {
        Self.folderLooksAnalysed(url: url) ? .located(url) : .invalidFolder(picked: url)
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
/// Scope is limited to the user's home directory by default. Researchers who
/// keep work on external drives fall through to NSOpenPanel — by design.
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
        // Re-entrance guard — previous call's observer (if any) is removed
        // before adding the new one. Not hit today (one SpotlightOneShot per
        // LocateFlow) but cheap defence against future callers that reuse
        // an instance.
        if let prior = observation {
            NotificationCenter.default.removeObserver(prior)
            observation = nil
        }
        query?.stop()

        return await withCheckedContinuation { (cont: CheckedContinuation<URL?, Never>) in
            let q = NSMetadataQuery()
            self.query = q
            q.searchScopes = [NSMetadataQueryUserHomeScope]
            q.predicate = NSPredicate(
                format: "kMDItemDisplayName ==[c] %@ AND kMDItemContentType == %@",
                projectName, "public.folder"
            )

            // Single-fire continuation guard — gathering can complete before
            // the timeout fires and vice versa.
            let resumed = Resumed()

            observation = NotificationCenter.default.addObserver(
                forName: .NSMetadataQueryDidFinishGathering,
                object: q, queue: .main
            ) { [weak self] _ in
                guard let self else { return }
                let result = self.pickUnique(from: q)
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
                    cont.resume(returning: nil)
                }
            }
        }
    }

    /// Walk the gathered results and return the unique high-confidence URL,
    /// or nil if there's zero or more-than-one match.
    private func pickUnique(from query: NSMetadataQuery) -> URL? {
        let candidates = (0..<query.resultCount).compactMap { i -> URL? in
            guard let item = query.result(at: i) as? NSMetadataItem,
                  let path = item.value(forAttribute: NSMetadataItemPathKey) as? String
            else { return nil }
            let url = URL(fileURLWithPath: path)
            return LocateFlow.folderLooksAnalysed(url: url) ? url : nil
        }
        return candidates.count == 1 ? candidates.first : nil
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
