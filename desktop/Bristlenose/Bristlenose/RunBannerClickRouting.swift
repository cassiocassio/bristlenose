import SwiftUI

/// Clicking a run banner brings the app forward (the system does that) and then
/// opens the project the banner was about. The banner carries the project's id
/// and nothing else (`RunBannerNotificationDelegate`).
enum RunBannerClick {

    /// The project a banner click names, or nil for anything that is not a
    /// well-formed click.
    static func projectID(from userInfo: [AnyHashable: Any]?) -> UUID? {
        (userInfo?["projectID"] as? String).flatMap(UUID.init(uuidString:))
    }

    /// Whether this window should act on a click: the project must still be in
    /// the sidebar (a study removed since is a quiet no-op), and only the front
    /// window acts, so a second window does not change study under the
    /// researcher.
    static func shouldSelect(
        _ id: UUID, known: Set<UUID>, windowIsFront: Bool
    ) -> Bool {
        windowIsFront && known.contains(id)
    }
}

/// Listens for `.runBannerClicked` and selects the project in this window.
struct RunBannerClickRouting: ViewModifier {
    @Binding var selection: Set<SidebarSelection>
    let knownProjects: () -> Set<UUID>
    let windowIsFront: () -> Bool

    func body(content: Content) -> some View {
        content.onReceive(NotificationCenter.default.publisher(for: .runBannerClicked)) { note in
            guard let id = RunBannerClick.projectID(from: note.userInfo) else { return }
            // The click activates the app a moment before a window is front.
            Task { @MainActor in
                try? await Task.sleep(for: .milliseconds(200))
                if RunBannerClick.shouldSelect(id, known: knownProjects(), windowIsFront: windowIsFront()) {
                    selection = [.project(id)]
                }
            }
        }
    }
}
