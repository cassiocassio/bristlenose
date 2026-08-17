import Foundation

/// Where a new project's folder is proposed, and how that answer improves.
///
/// **One owner, because there were four doors.** Loose-file drops on the sidebar
/// and on the welcome screen (`ContentView.createFolderProjectViaSavePanel`,
/// both routed through `createProjectFromURLs`) and the import window's
/// `NewProjectDestination` each open a panel, and each used to hardcode
/// `~/Documents` — the same decision written three times, free to drift with
/// nothing to notice. A researcher who keeps every study in `~/Work/Studies` was
/// sent to Documents every single time, by every door. The fourth door,
/// `+ New Project`, deliberately proposes *nothing* — see "the fourth door"
/// below.
///
/// **Three rungs, in this order:**
///
/// 1. **Configured** — the folder set in Settings ▸ General. Absent by default.
/// 2. **Remembered** — the parent of the last project actually created.
/// 3. **`~/Documents`** — the floor.
///
/// Configured outranks remembered rather than merging with it: a preference the
/// researcher set explicitly, then silently overridden by wherever they last
/// saved something, is not a setting but a suggestion — and the drift is the
/// very thing they set it to stop. `remember(projectFolder:)` keeps writing
/// underneath regardless, so clearing the preference falls back to learned
/// behaviour rather than all the way to Documents.
///
/// **Remembering is the platform's own behaviour** — an `NSSavePanel` with no
/// `directoryURL` remembers per app — and we were overriding it, so most of rung
/// 2 is to stop insisting. Keeping our own value rather than simply dropping
/// `directoryURL` buys two things the bare panel does not: a sane *first*
/// answer, and a location specifically about projects rather than one shared
/// with every other panel in the app (exports, transcripts, the CSS dump — they
/// all share AppKit's single per-app `NSNavLastRootDirectory`).
///
/// **The two rungs store different things, and behave differently on rename.**
/// Remembered is a plain path, because it only ever pre-*navigates* a panel and
/// under App Sandbox the panel itself is what grants access to whatever the
/// researcher picks — so pointing it at a folder we hold no grant for is fine.
/// Configured is a **security-scoped bookmark**, because a folder chosen once in
/// Settings and consulted on a later launch has no live panel grant behind it,
/// and because a value the researcher set deliberately must not be lost the
/// first time they rename its parent. The consequence, stated plainly rather
/// than glossed: **renaming the folder loses a remembered location and keeps a
/// configured one.** That asymmetry is the point of the bookmark, not an
/// accident of it.
///
/// **The fourth door does not use any of this, and must not.**
/// `+ New Project` / File ▸ New Project creates a *pathless placeholder* and
/// goes straight to inline rename; the location decision is deferred until the
/// researcher drops files on it or relocates it through a panel. It is tempting
/// to have a configured folder make that door eager — create
/// `<configured>/New project/` and skip the panel entirely. **Don't**, and the
/// blocker is not the sandbox: `ProjectIndex.renameProject` writes `.name` and
/// never `.path`, so the researcher would type "Ikea Study", the sidebar would
/// say Ikea Study, and the folder on disk would stay `New project` — silently,
/// permanently. Here the folder *is* the document: it is what gets shared,
/// backed up, dropped into the client's tree and found in Finder six months on,
/// so two names for one document is the worst available outcome. The invariant
/// that prevents it today is precisely that the placeholder has no path. Eager
/// creation deletes that invariant, and is only safe once rename renames the
/// folder too (a good feature, and its own piece of work).
enum ProjectFolderDefaults {

    // MARK: - What the panels ask

    /// Where the next New Project panel should open.
    ///
    /// `nil` means "we have no opinion" — the panel then falls back to AppKit's
    /// own per-app memory, which is a reasonable last resort and better than
    /// pointing it somewhere that does not exist.
    /// `home` is injectable so a test can prove the floor is derived from the
    /// *real* home rather than from `FileManager.urls(for: .documentDirectory,
    /// in: .userDomainMask)`, which under App Sandbox silently returns the app
    /// container. The difference is invisible from the unsandboxed test target,
    /// so a test that computes its expectation the same way the code does cannot
    /// fail on the bug — which is exactly how the container bug survived. Point
    /// this at a fixture home instead and the derivation itself is under test.
    static func suggestedDirectory(
        defaults: UserDefaults = .standard,
        fileManager: FileManager = .default,
        home: URL = UserHome.url
    ) -> URL? {
        if case .resolved(let url) = configured(defaults: defaults, fileManager: fileManager) {
            return url
        }
        if let remembered = rememberedDirectory(defaults: defaults, fileManager: fileManager) {
            return remembered
        }
        let documents = home.appendingPathComponent("Documents", isDirectory: true)
        return isDirectory(documents, fileManager) ? documents : nil
    }

    // MARK: - Rung 2: remembered

    /// Record where a project was actually made, so the next one starts there.
    ///
    /// Takes the project folder and stores its **parent** — the researcher chose
    /// a place to put a study, not a place to put things inside that study, and
    /// starting the next panel inside last week's project would be the more
    /// annoying of the two mistakes.
    static func remember(projectFolder: URL, defaults: UserDefaults = .standard) {
        let parent = projectFolder.deletingLastPathComponent()
        guard isSaneRoot(parent) else { return }
        defaults.set(parent.path, forKey: rememberedKey)
    }

    /// The remembered parent, if it is still a usable directory.
    ///
    /// A folder that has since been deleted, renamed or unmounted must not
    /// strand the panel somewhere that no longer exists — that reads as the app
    /// being broken rather than as an external drive being unplugged.
    static func rememberedDirectory(
        defaults: UserDefaults = .standard,
        fileManager: FileManager = .default
    ) -> URL? {
        guard let stored = remembered(defaults: defaults) else { return nil }
        let url = URL(fileURLWithPath: stored, isDirectory: true)
        return isDirectory(url, fileManager) ? url : nil
    }

    /// The raw remembered path, whether or not it still resolves.
    /// Exposed for tests and for the Settings row's "Last location used" copy.
    static func remembered(defaults: UserDefaults = .standard) -> String? {
        defaults.string(forKey: rememberedKey).flatMap { $0.isEmpty ? nil : $0 }
    }

    // MARK: - Rung 1: configured

    /// What Settings ▸ General should display.
    ///
    /// `unavailable` deliberately survives as a distinct state rather than
    /// collapsing into `notSet`: an unplugged drive is not a decision to change
    /// where your projects go, so the *panel* falls through to the next rung
    /// while the *row* keeps saying what was set and why it cannot be used.
    enum Configured: Equatable {
        /// Nothing configured — the row reads "Last location used".
        case notSet
        /// Configured and usable.
        case resolved(URL)
        /// Configured, but not reachable right now. `name` is the folder's own
        /// name, kept for the row so it can still say *which* folder is missing.
        case unavailable(name: String, reason: Unavailable)
    }

    enum Unavailable: Equatable {
        /// The folder lives on a volume that is not mounted. Name the volume —
        /// "On Iona, which isn't connected" is actionable; "unavailable" isn't.
        case volumeOffline(volume: String)
        /// Resolvable-but-gone, or never resolvable, on a mounted volume.
        case missing
    }

    static func configured(
        defaults: UserDefaults = .standard,
        fileManager: FileManager = .default
    ) -> Configured {
        guard let bookmark = defaults.data(forKey: configuredBookmarkKey) else { return .notSet }
        let lastKnownPath = defaults.string(forKey: configuredPathKey) ?? ""

        if let url = resolveBookmark(bookmark), isDirectory(url, fileManager) {
            // Bookmarks follow a rename, so the stored path can be stale the
            // moment after it is written. Re-record it, or the *label* shown
            // when the volume later goes offline would name the old folder.
            if url.path != lastKnownPath {
                defaults.set(url.path, forKey: configuredPathKey)
            }
            return .resolved(url)
        }

        return .unavailable(
            name: displayName(forPath: lastKnownPath),
            reason: unavailableReason(forPath: lastKnownPath, fileManager: fileManager)
        )
    }

    /// Store the folder the researcher picked in Settings.
    ///
    /// Returns `false` — and changes nothing — for a target that would make the
    /// panel worse than having no preference at all. The same guard rung 2
    /// applies to what it learns: a preference pointing at `/` or at `/Volumes`
    /// opens every future panel on the volume list, which is technically a
    /// directory and a hostile place to start.
    @discardableResult
    static func setConfigured(
        _ url: URL,
        defaults: UserDefaults = .standard,
        fileManager: FileManager = .default
    ) -> Bool {
        guard isSaneRoot(url), isDirectory(url, fileManager) else { return false }
        guard let bookmark = try? url.bookmarkData(options: .withSecurityScope) else { return false }
        defaults.set(bookmark, forKey: configuredBookmarkKey)
        defaults.set(url.path, forKey: configuredPathKey)
        return true
    }

    /// "Use Last Location" — drop the preference and fall back to rung 2.
    static func clearConfigured(defaults: UserDefaults = .standard) {
        defaults.removeObject(forKey: configuredBookmarkKey)
        defaults.removeObject(forKey: configuredPathKey)
    }

    // MARK: - Shared checks

    /// `fileExists` alone would accept a *file* and hand the panel something it
    /// does nothing sensible with, so the directory bit is checked explicitly.
    private static func isDirectory(_ url: URL, _ fileManager: FileManager) -> Bool {
        var isDirectory: ObjCBool = false
        guard fileManager.fileExists(atPath: url.path, isDirectory: &isDirectory) else {
            return false
        }
        return isDirectory.boolValue
    }

    /// Refuses the volume root and the volume *list*. Both are directories; both
    /// are places no researcher meant to keep studies.
    private static func isSaneRoot(_ url: URL) -> Bool {
        let path = url.standardizedFileURL.path
        return !path.isEmpty && path != "/" && path != "/Volumes"
    }

    private static func resolveBookmark(_ data: Data) -> URL? {
        var isStale = false
        guard let url = try? URL(
            resolvingBookmarkData: data,
            options: .withSecurityScope,
            relativeTo: nil,
            bookmarkDataIsStale: &isStale
        ) else { return nil }
        // Held for the process lifetime, like the project bookmarks in
        // `ProjectIndex` — the panel may be opened at any point in a session and
        // there is no later moment that would obviously release it.
        _ = url.startAccessingSecurityScopedResource()
        return url
    }

    /// Whether the missing folder is merely on an absent volume. `/Volumes/Iona`
    /// not existing is a disconnected drive; anything else is a deletion.
    private static func unavailableReason(
        forPath path: String, fileManager: FileManager
    ) -> Unavailable {
        let prefix = "/Volumes/"
        guard path.hasPrefix(prefix) else { return .missing }
        let volume = String(path.dropFirst(prefix.count).split(separator: "/").first ?? "")
        guard !volume.isEmpty,
              !fileManager.fileExists(atPath: prefix + volume) else { return .missing }
        return .volumeOffline(volume: volume)
    }

    private static func displayName(forPath path: String) -> String {
        let name = URL(fileURLWithPath: path).lastPathComponent
        return name.isEmpty || name == "/" ? path : name
    }

    // MARK: - Storage

    private static let rememberedKey = "defaultProjectsFolder"
    private static let configuredBookmarkKey = "configuredProjectsFolderBookmark"
    private static let configuredPathKey = "configuredProjectsFolderPath"
}
