import Foundation

// What Settings ▸ Accounts shows, worked out without touching the network.
//
// **The pane makes no calls, and that is the design.** Every state below is
// derived from what is already on disk — the Keychain, the OAuth config, and
// the address stored beside the tokens. A Settings pane that probed on appear
// would be slow, would do network I/O the researcher did not ask for, and would
// turn "you are offline" into something the pane asserts rather than observes.
// Reachability belongs in the import window, where a call is actually being
// made.
//
// The consequence is worth stating plainly: any state that can only be learnt
// from a call has to be **persisted when that call happens**, not discovered
// here. Google's account tier is free because it falls out of the address
// domain; Microsoft's does not, and is the one state below still owed a writer.

/// One thing Bristlenose talks to on the researcher's behalf.
///
/// Miro belongs here and is deliberately **not** a `CloudPlatform`: that enum
/// means "a meeting platform with an import adapter", and adding `.miro` would
/// put Miro in the import window's platform picker, in `CloudPlatform.built`
/// and in the fixture harness. To the person using it they are the same kind of
/// thing — an account you connect, see, and remove — so the sameness lives in
/// this type instead of being forced into that one.
enum AccountService: Hashable, Identifiable, Sendable {
    case cloud(CloudPlatform)
    case miro

    /// Every service the pane lists: the meeting platforms in §5's sequence,
    /// then Miro, the only one that sends rather than fetches.
    ///
    /// **`shipping`, not `built` — a parked service is not listed at all.** This
    /// read `built` for one release, on the argument that a catalogue which
    /// hides what is not ready cannot answer "what can this thing talk to?".
    /// That argument was wrong about the reader: a permanent row saying
    /// Bristlenose cannot sign in to Zoom answers a question nobody asked, and
    /// spends a quarter of the pane doing it. A service appears when connecting
    /// to it is possible.
    ///
    /// A computed `var` rather than a `static let`: `shipping` reads a
    /// UserDefaults flag, and a stored property would freeze whatever it said
    /// at first access.
    ///
    /// Safe only because a parked platform cannot hold a grant — `accountKeys`
    /// returns nothing for one, so hiding it cannot strand a credential where
    /// no UI can reach it. Check that again before parking a service that has
    /// ever stored a sign-in.
    static var all: [AccountService] { CloudPlatform.shipping.map(Self.cloud) + [.miro] }

    var id: String {
        switch self {
        case .cloud(let platform): return platform.rawValue
        case .miro: return "miro"
        }
    }

    var displayName: String {
        switch self {
        case .cloud(let platform): return platform.displayName
        case .miro: return "Miro"
        }
    }

    // **No symbol, deliberately.** The section headers carried SF Symbols
    // standing in for vendor marks — a person glyph for Teams, a camera for
    // Meet, a stacked rectangle for Miro. None of them is the thing they name,
    // and a glyph that is not the product's own mark is decoration wearing the
    // costume of identification — beside the vendor's name it reads *as* the
    // mark, which makes lawful-but-misleading a worse place than absent.
    //
    // **Not an interim.** The real marks would need a trademark licence from
    // all three vendors (§9a), and that paperwork is settled against, 18 Aug
    // 2026 — so this is the answer, not a wait. The name does the work, which
    // is what System Settings and Mail do with their own account group headers.
    //
    // `File ▸ Import` lost its symbols too (`5e426843`) — this comment briefly
    // claimed the menu was "a different case, menu furniture in a column of
    // other glyphs", and that was checked and false: those three items were the
    // only `systemImage` in the entire menu bar. The one surface where a vendor
    // mark belongs is the **sign-in button**, which §9a says the vendor requires
    // and grants.

    /// Whether connecting is something this pane can start.
    ///
    /// The meeting platforms open their import window, which is where sign-in
    /// lives — one flow, one implementation, and the researcher lands where the
    /// thing they wanted actually happens. Miro's connect is a pasted token
    /// inside the export sheet, which needs a running serve and an open
    /// project, so this pane says where rather than offering a door that fails
    /// when nothing is open.
    var connectsFromHere: Bool {
        if case .miro = self { return false }
        return true
    }
}

/// Why a connected account needs the researcher.
///
/// One slot in the row rather than two states, because the causes are mutually
/// exclusive in practice and the row draws identically for both.
enum AccountAttention: Equatable, Sendable {
    /// The provider ended the session. Rescues *"it just stopped working and I
    /// don't know why"* — before the grant survived its own refusal, a revoked
    /// sign-in disappeared from this pane entirely, which reads exactly like
    /// having disconnected it yourself.
    case signInAgain

    /// Signed in perfectly well, and this account can never hold a recording —
    /// a consumer Google account, where Meet recording is a Workspace feature.
    /// Rescues *"I signed in and there's nothing there"*, which is otherwise
    /// indistinguishable from having no recordings.
    case cannotHoldRecordings

    /// Takes `I18n` rather than reading a global, and stays out of the state
    /// engine above it: this enum is a pure value the view renders, so the
    /// locale arrives with the render, not with the verdict. Same shape as
    /// `CloudPlatform.windowTitle(_:)`.
    @MainActor
    func sentence(_ i18n: I18n) -> String {
        switch self {
        case .signInAgain:
            return i18n.t("desktop.accounts.signInAgain")
        case .cannotHoldRecordings:
            return i18n.t("desktop.accounts.cannotHoldRecordings")
        }
    }

    /// Whether the researcher can put it right from here.
    var isRecoverable: Bool { self == .signInAgain }
}

/// What one service's section shows.
enum AccountSectionState: Equatable, Sendable {
    /// Nothing to offer: no OAuth client is registered in this build, or the
    /// service is parked behind a flag. Not the researcher's doing and not
    /// something they can fix, so it offers no way to connect.
    ///
    /// `strandedIdentity` is set when a sign-in is nonetheless stored — a grant
    /// that outlived the client id it was obtained with. It is the only reason
    /// this state ever carries an account key, and the row says so rather than
    /// implying nothing is there.
    case unavailable(strandedIdentity: String?)
    case notConnected
    case connected(identity: String?)
    case attention(identity: String?, AccountAttention)

    /// The account this row is about, when there is one to name.
    var identity: String? {
        switch self {
        case .notConnected: return nil
        case .unavailable(let identity): return identity
        case .connected(let identity): return identity
        case .attention(let identity, _): return identity
        }
    }
}

/// A service and its state, ready to render.
struct AccountSection: Identifiable, Equatable, Sendable {
    let service: AccountService
    let state: AccountSectionState
    /// Which Keychain item Disconnect should remove. Nil when nothing is
    /// stored, or for Miro, whose token is not keyed per account.
    let accountKey: String?

    var id: String { service.id }
}

/// Turning what is stored into what is shown.
///
/// A pure function over values, so the whole state engine is testable without a
/// Keychain, a network, or a view — the house convention: if a view is making a
/// decision, the decision belongs in a testable helper.
enum AccountsSectionModel {

    /// - Parameters:
    ///   - available: the platforms this build can actually sign in to — an
    ///     OAuth client is registered *and* the service is not parked. Passed
    ///     in rather than resolved here so this stays pure.
    ///   - connections: everything the Keychain holds, from `CloudGrantStore`.
    ///   - miroConnected: whether a Miro token is stored.
    ///   - miroIdentity: the cached display line for Miro, if one was ever
    ///     resolved.
    static func sections(available: Set<CloudPlatform>,
                         connections: [CloudGrantStore.Connection],
                         miroConnected: Bool,
                         miroIdentity: String?) -> [AccountSection] {
        AccountService.all.map { service in
            switch service {
            case .cloud(let platform):
                return cloudSection(platform,
                                    available: available.contains(platform),
                                    connections: connections)
            case .miro:
                return AccountSection(
                    service: .miro,
                    state: miroConnected ? .connected(identity: miroIdentity) : .notConnected,
                    accountKey: nil)
            }
        }
    }

    private static func cloudSection(_ platform: CloudPlatform,
                                     available: Bool,
                                     connections: [CloudGrantStore.Connection]) -> AccountSection {
        // Unavailable is checked first and unconditionally. A grant left behind
        // by an earlier build whose client id has since gone would otherwise
        // render as a working connection nothing can use.
        //
        // **But it still carries the account key.** This guard exists precisely
        // because a stored grant can outlive its client id — and the first
        // version answered that by making the grant *undeletable*, in a pane
        // whose whole purpose is deleting it. A client's refresh token with no
        // UI anywhere to remove it is a worse outcome than a row that offers
        // Disconnect on a service it cannot currently sign in to. Connect stays
        // suppressed; only the removal survives.
        guard available else {
            let stranded = connections.first { $0.platform == platform }
            return AccountSection(service: .cloud(platform),
                                  state: .unavailable(strandedIdentity: stranded?.address),
                                  accountKey: stranded?.accountKey)
        }
        // First, not chosen: one account per service today, and nothing yet
        // offers a way to connect a second.
        guard let connection = connections.first(where: { $0.platform == platform }) else {
            return AccountSection(service: .cloud(platform), state: .notConnected, accountKey: nil)
        }
        let state: AccountSectionState
        if let attention = attention(for: platform, connection: connection) {
            state = .attention(identity: connection.address, attention)
        } else {
            state = .connected(identity: connection.address)
        }
        return AccountSection(service: .cloud(platform),
                              state: state,
                              accountKey: connection.accountKey)
    }

    /// What needs the researcher, when it can be known without a call.
    ///
    /// **A refusal outranks the account tier.** A revoked personal Google
    /// sign-in is both, and only one of the two is worth saying: telling
    /// someone their account is the wrong kind, when the thing that actually
    /// happened is that their session ended, sends them to fix something that
    /// is not broken.
    ///
    /// The tier half is **Google only, and that asymmetry is real rather than
    /// an omission.**
    /// `GoogleAccountTier(email:)` is pure string work — a `gmail.com` address
    /// is a consumer account, and Meet recording is a Workspace feature, so the
    /// verdict is free and always current. Microsoft's equivalent is a personal
    /// account with no `/Recordings` folder, and that comes from
    /// `GET /me/drive?$select=driveType` — a call, which this pane does not
    /// make. Surfacing it here needs the adapter to write its `DriveTier`
    /// verdict onto the grant when a listing establishes it; until then a
    /// personal Microsoft account reads as `.connected` and the researcher
    /// learns the truth in the import window, as they do today.
    private static func attention(for platform: CloudPlatform,
                                  connection: CloudGrantStore.Connection) -> AccountAttention? {
        if connection.needsSignIn { return .signInAgain }
        switch platform {
        case .meet:
            // An address we never learnt is `.unknown`, whose
            // `canHoldMeetRecordings` is false — reading that as "wrong kind of
            // account" would tell a Workspace researcher their account is wrong
            // because one `/me` call failed.
            guard connection.address != nil else { return nil }
            return GoogleAccountTier(email: connection.address).canHoldMeetRecordings
                ? nil
                : .cannotHoldRecordings
        case .teams:
            // **Only what a listing actually established.** Nil means nobody
            // has asked yet — a researcher who signed in and never opened the
            // window — and silence is the only honest thing to render for it.
            // Guessing from an address would be wrong in the direction that
            // matters: plenty of work tenants use consumer-looking domains, and
            // telling a researcher their perfectly good account is the wrong
            // kind is worse than saying nothing.
            // **`.personal` only — deliberately not `!canHoldTeamsRecordings`.**
            // That property is false for `.unknown` as well, which is correct
            // where it is used (deciding whether to *expect* recordings) and
            // wrong here: an unrecognised `driveType` is a drive kind this code
            // has not met, and reading it as "personal" would turn every future
            // Microsoft drive type into an accusation against a working
            // account. Same failure direction the Google branch guards above.
            guard connection.driveTier == .personal else { return nil }
            return .cannotHoldRecordings
        case .zoom:
            // Parked, and its tier question is answered by the provider at
            // listing time rather than by anything stored. Separate from
            // `.teams` so unparking Zoom is a compile-time prompt.
            return nil
        }
    }
}
