import SwiftUI

/// The `meet-import` scene's root.
///
/// Its only job is to answer "has a store been prepared for me?". A scene can
/// be restored by macOS at launch — state restoration reopens whatever was open
/// when the app quit — so it must render sensibly with no store rather than
/// crash or show an empty table that looks like "no meetings".
struct MeetImportWindowHost: View {
    @EnvironmentObject var coordinator: MeetImportCoordinator

    var body: some View {
        Group {
            if let store = coordinator.store {
                MeetImportWindow(store: store)
            } else {
                ContentUnavailableView {
                    Label("Nothing to import yet", systemImage: "square.and.arrow.down")
                } description: {
                    Text("Choose File ▸ Import ▸ Google Meet to start.")
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
struct MeetImportOpener: ViewModifier {
    @ObservedObject var coordinator: MeetImportCoordinator
    @ObservedObject var projectIndex: ProjectIndex
    /// The project the researcher is looking at, so the destination can be
    /// pre-selected by how the window was opened (§9).
    let selectedProjectID: UUID?

    @Environment(\.openWindow) private var openWindow

    func body(content: Content) -> some View {
        content
            .onReceive(NotificationCenter.default.publisher(for: .openGoogleMeetImport)) { _ in
                coordinator.openLive(preselecting: selectedProjectID)
                openWindow(id: "meet-import")
            }
            .onReceive(NotificationCenter.default.publisher(for: .openGoogleMeetImportFixture)) { note in
                guard let scenario = note.object as? MeetImportScenario else { return }
                coordinator.openFixture(scenario, preselecting: selectedProjectID)
                openWindow(id: "meet-import")
            }
    }
}
