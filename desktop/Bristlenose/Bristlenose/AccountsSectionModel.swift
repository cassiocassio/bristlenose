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

    /// Every service, in the order the pane lists them: the meeting platforms
    /// in §5's sequence, then Miro, the only one that sends rather than fetches.
    ///
    /// All four always, including the ones that cannot be connected yet. A
    /// catalogue that hides what is not ready cannot answer "what can this
    /// thing talk to?", which is half of what a researcher opens this pane for.
    static let all: [AccountService] = CloudPlatform.built.map(Self.cloud) + [.miro]

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

    var symbolName: String {
        switch self {
        case .cloud(let platform): return platform.symbolName
        case .miro: return "square.on.square.dashed"
        }
    }

    /// What the account is for. Sits in the section footer, so it reads as
    /// "why would I connect this" rather than as instructions.
    var purpose: String {
        switch self {
        case .cloud(.teams): return "Bring recordings in from OneDrive without downloading them by hand."
        case .cloud(.meet):  return "Bring recordings in from Drive without downloading them by hand."
        case .cloud(.zoom):  return "Bring cloud recordings in without downloading them by hand."
        case .miro:          return "Send quotes to a board."
        }
    }

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
    /// Signed in perfectly well, and this account can never hold a recording —
    /// a consumer Google account, where Meet recording is a Workspace feature.
    /// Rescues *"I signed in and there's nothing there"*, which is otherwise
    /// indistinguishable from having no recordings.
    case cannotHoldRecordings

    var sentence: String {
        switch self {
        case .cannotHoldRecordings:
            return "This account can't hold meeting recordings, so there's nothing to import."
        }
    }
}

/// What one service's section shows.
enum AccountSectionState: Equatable, Sendable {
    /// Nothing to offer: no OAuth client is registered in this build, or the
    /// service is parked behind a flag. Not the researcher's doing and not
    /// something they can fix, so it carries no verb.
    case unavailable
    case notConnected
    case connected(identity: String?)
    case attention(identity: String?, AccountAttention)

    /// The account this row is about, when there is one to name.
    var identity: String? {
        switch self {
        case .unavailable, .notConnected: return nil
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
        guard available else {
            return AccountSection(service: .cloud(platform), state: .unavailable, accountKey: nil)
        }
        // First, not chosen: one account per service today, and nothing yet
        // offers a way to connect a second.
        guard let connection = connections.first(where: { $0.platform == platform }) else {
            return AccountSection(service: .cloud(platform), state: .notConnected, accountKey: nil)
        }
        let state: AccountSectionState
        if let attention = attention(for: platform, address: connection.address) {
            state = .attention(identity: connection.address, attention)
        } else {
            state = .connected(identity: connection.address)
        }
        return AccountSection(service: .cloud(platform),
                              state: state,
                              accountKey: connection.accountKey)
    }

    /// What is wrong with an otherwise-working account, when it can be known
    /// from the address alone.
    ///
    /// **Google only, and that asymmetry is real rather than an omission.**
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
                                  address: String?) -> AccountAttention? {
        switch platform {
        case .meet:
            guard address != nil else { return nil }
            return GoogleAccountTier(email: address).canHoldMeetRecordings
                ? nil
                : .cannotHoldRecordings
        case .teams, .zoom:
            return nil
        }
    }
}
