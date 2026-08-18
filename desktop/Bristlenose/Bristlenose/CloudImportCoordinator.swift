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

    private var disconnectObserver: NSObjectProtocol?

    /// The live session's grant writer, or nil when the window is showing
    /// fixtures. It owns the Keychain account key, which moves: a session
    /// restored without an address rekeys once the identity lands.
    private var grantWriter: CloudGrantWriter?

    init() {
        // Disconnecting an account in Settings must reach a window that is
        // already open. Without this the Keychain copy goes and the live
        // adapter — which holds its tokens in memory — carries on listing and
        // fetching against the account just disconnected, so the control
        // appears to work and does not. §9's "one place to disconnect" only
        // holds if that one place actually reaches everywhere.
        disconnectObserver = NotificationCenter.default.addObserver(
            forName: .bristlenoseCloudAccountDisconnected,
            object: nil,
            queue: .main
        ) { [weak self] note in
            let raw = note.userInfo?["platform"] as? String
            let account = note.userInfo?["account"] as? String
            MainActor.assumeIsolated {
                guard let self else { return }
                // The account is matched as well as the platform, or
                // disconnecting the personal Teams account would close a window
                // signed in to the work one.
                guard CloudDisconnectMatch.dropsSession(
                    livePlatform: self.platform,
                    liveAccountKey: self.grantWriter?.currentKey,
                    notedPlatform: raw,
                    notedAccountKey: account)
                else { return }
                // **Stop the transfer before dropping the reference.**
                // Releasing the store cancels nothing: `fetchTask` captures
                // `self` strongly and the per-row tasks deliberately do not
                // inherit cancellation from it (`stopFetch`'s own comment says
                // so). So a disconnect during a batch used to clear the row in
                // Settings while gigabytes kept arriving from the account just
                // removed — the precise failure this notification exists to
                // prevent, one layer down. Second-order: with `store` nil,
                // `isFetching` reads false, so the guard in `openLive` would
                // let a new batch start alongside the orphaned one.
                self.store?.stopFetch()
                // Drop the store rather than re-opening on the sign-in button:
                // the window's whole state — ticks, outcomes, the batch — belongs
                // to a session that no longer exists.
                self.store = nil
            }
        }
    }

    deinit {
        if let disconnectObserver {
            NotificationCenter.default.removeObserver(disconnectObserver)
        }
    }

    /// Open against a platform's real APIs.
    ///
    /// Every branch that cannot find credentials opens the window anyway, on an
    /// `UnconfiguredCloudSource`. Registering an OAuth client is an act of the
    /// maintainer's own vendor account — the app cannot do it for itself — so
    /// "not set up" is a state to render, not a menu item that does nothing when
    /// clicked.
    /// True while a batch is transferring, whichever platform started it.
    ///
    /// Read by the File ▸ Import menu so the other platforms can dim rather
    /// than silently discard a running batch — see `openLive`'s guard.
    var isFetching: Bool { store?.isFetching ?? false }

    func openLive(_ platform: CloudPlatform, preselecting projectID: UUID?) {
        // **Never replace a store that is mid-transfer.**
        //
        // This method used to swap `store` unconditionally, and there is one
        // store globally (§9). So starting a batch, closing the window, and
        // opening Import on another platform released the only reference to the
        // fetching store — leaving the transfers running, invisible, with
        // nothing left that could show or stop them. The researcher's files
        // kept arriving from a window that no longer existed.
        //
        // Re-presenting the running one is the honest answer rather than a
        // refusal: the batch is the thing they most likely want to see. The
        // menu dims the other platforms so this guard is a safety net rather
        // than the primary mechanism — but it is the guard that makes the
        // defect unreachable, because a menu can be raced and a notification
        // can arrive from anywhere.
        guard !isFetching else {
            preselectedProjectID = projectID
            return
        }

        self.platform = platform
        preselectedProjectID = projectID
        fixtureScenario = nil

        // Which account this window is for. `firstAccountKey` is the whole of
        // the choice today because nothing yet offers a way to connect a second
        // — the picker belongs at the moment of use and arrives with Add
        // Account. A window opened before anyone has signed in writes its first
        // grant under `unidentified` and rekeys when `/me` answers.
        let key = CloudGrantStore.firstAccountKey(for: platform) ?? CloudAccountKey.unidentified
        let writer = CloudGrantWriter(key: key)
        grantWriter = writer

        switch platform {
        case .meet:
            guard let config = GoogleOAuthConfig.resolve() else {
                store = CloudImportStore(source: UnconfiguredCloudSource(), platform: platform); return
            }
            // Restore the previous sign-in if one survived. Both grants and
            // the identity, or none of them — see `GoogleGrant`.
            //
            // `.usable` drops a grant the provider ended. **The identity has to
            // go with it**: `CloudImportStore` picks its opening phase from
            // `accountEmail`, so restoring the address alone would open the
            // window on `.loading` holding no token at all.
            let saved = CloudGrantStore.loadGoogle(account: key)?.usable
            store = CloudImportStore(
                source: GoogleMeetSource(
                    config: config,
                    restoredTokens: saved?.tokens,
                    restoredMediaGrant: saved?.media.map {
                        (tokens: $0.tokens, fileIDs: Set($0.fileIDs))
                    },
                    restoredIdentity: saved?.identity,
                    // Enqueues and returns — the writer owns both the hop off
                    // the caller's thread and the ordering between publishes.
                    onGrantChanged: { grant in
                        writer.publish { CloudGrantStore.saveGoogle(grant, previousKey: $0) }
                    }),
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
            // Restore the previous sign-in if one survived. One grant here, not
            // Google's two — see `MicrosoftGrant`. `.usable` drops one the
            // provider ended, identity included; see the Google case above.
            let savedTeams = CloudGrantStore.loadTeams(account: key)?.usable
            store = CloudImportStore(
                source: TeamsSource(
                    config: config,
                    restoredTokens: savedTeams?.tokens,
                    restoredIdentity: savedTeams?.identity,
                    onGrantChanged: { grant in
                        writer.publish { CloudGrantStore.saveTeams(grant, previousKey: $0) }
                    }),
                platform: platform)
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
        // No account: a fixture session holds no credentials, so there is no
        // key to match a disconnect against. It is dropped on any disconnect of
        // its platform, which is the erring-toward-dropping rule above.
        grantWriter = nil
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
