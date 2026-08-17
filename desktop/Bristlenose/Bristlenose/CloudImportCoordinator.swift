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
final class CloudImportCoordinator: ObservableObject {
    @Published private(set) var store: CloudImportStore?

    /// Which platform the window is showing. Drives every vendor-specific
    /// string in it — sign-in title, account noun, whether an Expires column
    /// exists at all.
    @Published private(set) var platform: CloudPlatform = .meet

    /// Which fixture scenario is showing, or nil when the window is live.
    /// Rendered in the window as a visible badge — a debug surface that isn't
    /// obviously a debug surface is a way to file fictional bug reports.
    @Published private(set) var fixtureScenario: CloudImportScenario?

    /// Set at open time by whichever door was used (§9: opening from a
    /// project's context menu pre-selects that project; from the File menu, the
    /// current one).
    @Published var preselectedProjectID: UUID?

    /// Open against a platform's real APIs.
    ///
    /// Every branch that cannot find credentials opens the window anyway, on an
    /// `UnconfiguredCloudSource`. Registering an OAuth client is an act of the
    /// maintainer's own vendor account — the app cannot do it for itself — so
    /// "not set up" is a state to render, not a menu item that does nothing when
    /// clicked.
    func openLive(_ platform: CloudPlatform, preselecting projectID: UUID?) {
        self.platform = platform
        preselectedProjectID = projectID
        fixtureScenario = nil

        switch platform {
        case .meet:
            guard let config = GoogleOAuthConfig.resolve() else {
                store = CloudImportStore(source: UnconfiguredCloudSource(), platform: platform); return
            }
            // Restore the previous sign-in if one survived. Both grants and
            // the identity, or none of them — see `GoogleGrant`.
            let saved = CloudGrantStore.loadGoogle()
            store = CloudImportStore(
                source: GoogleMeetSource(
                    config: config,
                    restoredTokens: saved?.tokens,
                    restoredMediaGrant: saved?.media.map {
                        (tokens: $0.tokens, fileIDs: Set($0.fileIDs))
                    },
                    restoredIdentity: saved?.identity,
                    onGrantChanged: { CloudGrantStore.saveGoogle($0) }),
                platform: platform)

        case .zoom:
            // Zoom needs TWO values, not one: a public client ID *and* an HTTPS
            // redirect, because Zoom does not derive the redirect from the
            // client ID the way Google does — it is whatever was registered in
            // the app's OAuth allow list, matched exactly.
            guard let config = ZoomOAuthConfig.resolve() else {
                store = CloudImportStore(source: UnconfiguredCloudSource(), platform: platform); return
            }
            store = CloudImportStore(source: ZoomSource(config: config), platform: platform)

        case .teams:
            // One value, not two: unlike Zoom, Microsoft derives nothing from
            // the client ID but accepts a conventional custom-scheme redirect,
            // so the redirect and tenant both have sane defaults.
            guard let config = MicrosoftOAuthConfig.resolve() else {
                store = CloudImportStore(source: UnconfiguredCloudSource(), platform: platform); return
            }
            store = CloudImportStore(source: TeamsSource(config: config), platform: platform)
        }
    }

    /// Open against fixtures. Diagnostics menu only.
    func openFixture(
        _ platform: CloudPlatform,
        _ scenario: CloudImportScenario,
        preselecting projectID: UUID?
    ) {
        self.platform = platform
        preselectedProjectID = projectID
        fixtureScenario = scenario
        store = CloudImportStore(
            source: FixtureCloudSource(scenario: scenario, platform: platform),
            platform: platform)
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
final class UnconfiguredCloudSource: CloudImportSource {
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
        row: CloudImportRow,
        destination: URL,
        progress: @escaping @Sendable (FetchProgress) -> Void
    ) async -> FetchOutcome {
        .failed(reason: "Not set up", isRetryable: false)
    }
}
