import SwiftUI

/// The `meet-import` scene's root.
///
/// Its only job is to answer "has a store been prepared for me?". A scene can
/// be restored by macOS at launch — state restoration reopens whatever was open
/// when the app quit — so it must render sensibly with no store rather than
/// crash or show an empty table that looks like "no meetings".
struct CloudImportWindowHost: View {
    @EnvironmentObject var coordinator: CloudImportCoordinator
    @EnvironmentObject var i18n: I18n

    var body: some View {
        Group {
            if let store = coordinator.store {
                CloudImportWindow(store: store, platform: coordinator.platform)
            } else {
                ContentUnavailableView {
                    Label(i18n.t("desktop.cloudImport.restoredEmptyTitle"), systemImage: "square.and.arrow.down")
                } description: {
                    // Reached on macOS state restoration, when the platform is by
                    // definition unknown — so it must not name one.
                    Text(i18n.t("desktop.cloudImport.restoredEmptyBody"))
                }
            }
        }
        .safeAreaInset(edge: .top, spacing: 0) { fixtureBanner }
    }

    /// A visible, unmissable band when the window is showing fixtures.
    ///
    /// Not decoration. A debug surface that does not announce itself is how a
    /// fictional bug report gets filed against real code — and this window is
    /// unusually good at it, because the fixture data is deliberately
    /// realistic. The banner is what makes "P07 Interview — ward handover"
    /// obviously not the user's data.
    @ViewBuilder
    private var fixtureBanner: some View {
        if let scenario = coordinator.fixtureScenario {
            HStack(spacing: 6) {
                Image(systemName: "testtube.2")
                Text("Sample data — \(scenario.menuTitle)")
                Spacer()
            }
            .font(.caption.weight(.medium))
            .padding(.horizontal, 12)
            .padding(.vertical, 5)
            .background(.orange.opacity(0.18))
            .overlay(alignment: .bottom) { Divider() }
        }
    }
}

/// Listens for the two open-the-window notifications and opens the scene.
///
/// A modifier rather than code inside `ContentView` because the listener has to
/// be alive whenever the app is — including when no project is selected — and
/// because `openWindow` is only reachable from a `View`.
struct CloudImportOpener: ViewModifier {
    @ObservedObject var coordinator: CloudImportCoordinator
    @ObservedObject var projectIndex: ProjectIndex
    /// The project the researcher is looking at, so the destination can be
    /// pre-selected by how the window was opened (§9).
    let selectedProjectID: UUID?

    @Environment(\.openWindow) private var openWindow

    func body(content: Content) -> some View {
        content
            .onReceive(NotificationCenter.default.publisher(for: .openCloudImport)) { note in
                let platform = note.object as? CloudPlatform ?? .meet
                coordinator.openLive(platform, preselecting: selectedProjectID)
                openWindow(id: "cloud-import")
            }
            .onReceive(NotificationCenter.default.publisher(for: .openCloudImportFixture)) { note in
                guard let payload = note.object as? FixtureRequest else { return }
                coordinator.openFixture(payload.platform, payload.scenario,
                                        preselecting: selectedProjectID)
                openWindow(id: "cloud-import")
            }
    }
}


/// What a Diagnostics fixture menu item posts.
///
/// A struct rather than a tuple so the notification's `object` has a name the
/// receiver can check, and so adding a third field later doesn't silently
/// change the shape at every call site.
struct FixtureRequest {
    let platform: CloudPlatform
    let scenario: CloudImportScenario
}
