import AppKit
import Foundation

/// The default-folder chooser (Settings ▸ General) never offers `/` or `/Volumes` (R44).
///
/// `ProjectFolderDefaults.setConfigured` has always refused them, because a preference pointing at
/// the volume root or the volume list opens every future panel on the volume list. But the panel
/// accepted the pick, closed, and the pane changed nothing, so choosing "Macintosh HD" looked like
/// a click that did nothing. Now the panel itself refuses them: they are greyed where they are
/// listed, and Choose on one leaves the panel open. Owner call, 7 Nov 2026; no new wording.
final class SaneFolderPanelDelegate: NSObject, NSOpenSavePanelDelegate {
    func panel(_ sender: Any, shouldEnable url: URL) -> Bool {
        ProjectFolderDefaults.isSaneRoot(url)
    }

    func panel(_ sender: Any, validate url: URL) throws {
        // A cancelled-by-user error keeps the panel open without an alert (and without a sentence).
        guard ProjectFolderDefaults.isSaneRoot(url) else { throw CocoaError(.userCancelled) }
    }
}
