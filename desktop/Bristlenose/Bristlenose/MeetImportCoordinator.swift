import SwiftUI

/// Owns the one import window's store, app-wide.
///
/// §9: "One window, globally, with the destination pre-selected by how you
/// opened it." One store, therefore, not one per scene — a second window would
/// mean two tick sets and two batches racing for the same destination, and the
/// per-row outcomes recovery depends on would be split across them.
///
/// It also owns the live-vs-fixture choice, so that decision is made in exactly
/// one place and the window itself never learns which it has.
@MainActor
final class MeetImportCoordinator: ObservableObject {
    @Published private(set) var store: MeetImportStore?

    /// Which fixture scenario is showing, or nil when the window is live.
    /// Rendered in the window as a visible badge — a debug surface that isn't
    /// obviously a debug surface is a way to file fictional bug reports.
    @Published private(set) var fixtureScenario: MeetImportScenario?

    /// Set at open time by whichever door was used (§9: opening from a
    /// project's context menu pre-selects that project; from the File menu, the
    /// current one).
    @Published var preselectedProjectID: UUID?

    /// Nil when no client ID has been configured. Read once here rather than at
    /// each call site so "not set up" is a state the UI can render rather than
    /// a failure it has to catch.
    var oauthConfig: GoogleOAuthConfig? { GoogleOAuthConfig.resolve() }

    /// Open against the real Google APIs.
    func openLive(preselecting projectID: UUID?) {
        preselectedProjectID = projectID
        fixtureScenario = nil
        guard let config = oauthConfig else {
            // No client ID. Deliberately still opens the window: the honest
            // thing is a window that says what is missing, not a menu item that
            // does nothing when clicked.
            store = MeetImportStore(source: UnconfiguredMeetSource())
            return
        }
        store = MeetImportStore(source: GoogleMeetSource(config: config))
    }

    /// Open against fixtures. Diagnostics menu only.
    func openFixture(_ scenario: MeetImportScenario, preselecting projectID: UUID?) {
        preselectedProjectID = projectID
        fixtureScenario = scenario
        store = MeetImportStore(source: FixtureMeetSource(scenario: scenario))
    }
}

/// The source used when no OAuth client ID has been configured.
///
/// It exists so that "Bristlenose has not been set up to talk to Google yet" is
/// a *state of the window* rather than a crash, a disabled menu item, or a
/// sign-in button that fails in a way that looks like the researcher's fault.
/// Registering an OAuth client is an act of the maintainer's Google account;
/// the app cannot do it for itself, and pretending otherwise would be the
/// fake-success pattern this codebase keeps finding and removing.
final class UnconfiguredMeetSource: MeetImportSource {
    var accountEmail: String? { nil }
    var accountTier: GoogleAccountTier { .unknown }

    func signIn() async throws { throw GoogleOAuthError.notConfigured }

    func list(window: DateInterval) async -> MeetingListing {
        MeetingListing(
            rows: [],
            arithmetic: JoinArithmetic(eventsInWindow: 0, fetchable: 0,
                                       organisedByOthers: 0, outcome: .exhausted),
            window: window
        )
    }

    func fetch(
        row: GoogleImportRow,
        destination: URL,
        progress: @escaping @Sendable (FetchProgress) -> Void
    ) async -> FetchOutcome {
        .failed(reason: "Not set up", isRetryable: false)
    }
}
