import Foundation

/// Where a new project's folder is proposed, and how that answer improves.
///
/// **One owner, because there were two.** `ContentView`'s sidebar path and the
/// import window's `NewProjectDestination` each hardcoded
/// `~/Documents` — the same decision, written twice, free to drift apart with
/// nothing to notice. A researcher who keeps every study in
/// `~/Work/Studies` was sent to Documents every single time, by both doors.
///
/// **It remembers rather than asks.** The first proposal is Documents; after
/// that it is wherever they last made one. That is the platform's own
/// behaviour — an `NSSavePanel` with no `directoryURL` remembers per app — and
/// we were overriding it, so the fix is mostly to stop insisting. Keeping a
/// stored value rather than simply dropping `directoryURL` buys two things
/// the bare panel does not: a sane *first* answer, and a location that is
/// specifically about projects rather than shared with every other panel in
/// the app (exports, transcripts, the CSS dump).
///
/// **A plain path, not a bookmark, and that is deliberate.** This value only
/// ever pre-*navigates* a panel. Under App Sandbox the panel itself is what
/// grants access to whatever the researcher picks, so pointing it at a folder
/// we hold no grant for is fine — the powerbox shows it, the choice grants it.
/// Storing a security-scoped bookmark here would imply we could create folders
/// without asking, which we cannot and should not.
///
/// **If a Settings row is wanted**, it writes `preferred` and nothing else
/// changes: both doors already read this type, so the row is the only new
/// surface. Deliberately not built yet — remembering may well be enough, and
/// `feedback_tune_defaults_dont_expose_threshold_ui` says to make the screen
/// disappear before adding one.
enum ProjectFolderDefaults {

    /// Where the next New Project panel should open.
    static func suggestedDirectory(
        defaults: UserDefaults = .standard,
        fileManager: FileManager = .default
    ) -> URL? {
        if let stored = defaults.string(forKey: key), !stored.isEmpty {
            let url = URL(fileURLWithPath: stored, isDirectory: true)
            // A remembered folder that has since been deleted, renamed or
            // unmounted must not strand the panel somewhere that no longer
            // exists — that reads as the app being broken rather than as an
            // external drive being unplugged.
            var isDirectory: ObjCBool = false
            if fileManager.fileExists(atPath: url.path, isDirectory: &isDirectory),
               isDirectory.boolValue {
                return url
            }
        }
        return fileManager.urls(for: .documentDirectory, in: .userDomainMask).first
    }

    /// Record where a project was actually made, so the next one starts there.
    ///
    /// Takes the project folder and stores its **parent** — the researcher
    /// chose a place to put a study, not a place to put things inside that
    /// study, and starting the next panel inside last week's project would be
    /// the more annoying of the two mistakes.
    static func remember(projectFolder: URL, defaults: UserDefaults = .standard) {
        let parent = projectFolder.deletingLastPathComponent()
        guard !parent.path.isEmpty, parent.path != "/" else { return }
        defaults.set(parent.path, forKey: key)
    }

    /// The stored preference, or nil while it is still Documents by default.
    /// Exposed for a future Settings row and for tests; nothing else reads it.
    static func preferred(defaults: UserDefaults = .standard) -> String? {
        defaults.string(forKey: key).flatMap { $0.isEmpty ? nil : $0 }
    }

    private static let key = "defaultProjectsFolder"
}
