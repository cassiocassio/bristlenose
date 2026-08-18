import CryptoKit
import Foundation
import OSLog

// Keeping a cloud sign-in across window opens.
//
// Design: docs/design-cloud-import.md. Until 17 Aug 2026 nothing here existed
// — all three adapters carried a `restoredTokens` seam whose only caller was
// the test suite, so every open of the import window was a fresh sign-in:
// system prompt, account chooser, consent, and then the media grant on top.
// The seams were built for this and then never wired.
//
// MARK: PII / credentials — never log a token, a file id, or the account.

/// A Google sign-in worth keeping.
///
/// Two grants, not one, and they are not interchangeable: the listing grant
/// (calendar + Meet) and the Picker's `drive.file` grant are separate
/// authorizations with different scopes, obtained through different flows, and
/// Google will not let the second carry any scope but its own.
struct GoogleGrant: Codable, Equatable, Sendable {
    /// The listing grant — calendar events and Meet conference records.
    var tokens: GoogleTokens

    /// The Picker grant. Optional because a researcher can list without ever
    /// importing, and that is a perfectly good session to remember.
    var media: MediaGrant?

    /// The signed-in address. Not a credential, and stored for one blunt
    /// reason: `CloudImportStore` decides its opening phase from
    /// `source.accountEmail`, so a restore without it opens on the sign-in
    /// button while holding a perfectly good token — the restore would be
    /// invisible and everyone would conclude it hadn't worked.
    var identity: String?

    /// The provider ended this sign-in. See `MicrosoftGrant.needsSignIn`.
    var needsSignIn: Bool? = nil

    /// This grant if it can still be used, nil if the provider ended it.
    var usable: GoogleGrant? { needsSignIn == true ? nil : self }

    /// The account, kept without its credential.
    static func revoked(identity: String?) -> GoogleGrant {
        GoogleGrant(
            tokens: GoogleTokens(accessToken: "", refreshToken: nil,
                                 expiresAt: .distantPast, granted: []),
            media: nil,
            identity: identity,
            needsSignIn: true)
    }

    /// The Picker grant is a **pair**. `fetch` guards on the file ids *before*
    /// it reads the token, so a token kept without its ids sits unused behind
    /// a failing guard — restored, and inert. Keeping them in one value makes
    /// half-restoring unrepresentable rather than merely discouraged.
    struct MediaGrant: Codable, Equatable, Sendable {
        var tokens: GoogleTokens
        /// Sorted, so one grant serialises identically twice — a `Set` would
        /// rewrite the stored blob on every save for no change.
        var fileIDs: [String]
    }
}

/// A Microsoft sign-in worth keeping.
///
/// One grant, not two. Teams needs no counterpart to Google's Picker step:
/// `Files.Read` reaches the recordings directly, so there is no second
/// authorization to hold and no half-restored state to make unrepresentable.
struct MicrosoftGrant: Codable, Equatable, Sendable {
    var tokens: MicrosoftTokenResponse

    /// The signed-in address, for the same blunt reason as Google's:
    /// `CloudImportStore` picks its opening phase from `source.accountEmail`,
    /// so a restore without it opens on the sign-in button while holding a
    /// working token, and the restore reads as a failure.
    var identity: String?

    /// The provider ended this sign-in, and the account is kept anyway.
    ///
    /// **Keeping it is the point.** A refused refresh used to delete the grant,
    /// which meant a revoked session *vanished from Settings ▸ Accounts* —
    /// indistinguishable from having disconnected it yourself, and the
    /// researcher's only evidence was that importing had quietly stopped
    /// working. The row survives its own credential so the pane can name the
    /// cause and offer a way back.
    ///
    /// Optional rather than a defaulted `Bool` because the synthesised decoder
    /// does **not** apply property defaults for a missing key — it throws, and
    /// `loadTeams` discards what it cannot decode. A non-optional would have
    /// dropped every sign-in stored before this field existed.
    var needsSignIn: Bool? = nil

    /// Graph's raw `driveType` for this account, once a listing has established
    /// it. Nil until then.
    ///
    /// **The raw string, not a `DriveTier`.** `DriveTier` carries an associated
    /// value on its `unknown` case, so encoding it would mean a hand-written
    /// Codable conformance and a second home for the "documentLibrary counts as
    /// business" mapping. This is the exact token Graph returned;
    /// `DriveTier(driveType:)` stays the only derivation.
    ///
    /// **Why persist it at all.** Settings ▸ Accounts makes no network calls —
    /// that is the design, not an omission — so the only way the pane can tell a
    /// researcher their personal Microsoft account cannot hold Teams recordings
    /// is if something that *did* call wrote the answer down. Google's
    /// equivalent is free (it reads the address domain); Microsoft's costs
    /// `GET /me/drive?$select=driveType`, and the listing already pays it.
    ///
    /// Optional for the same decoder reason as `needsSignIn` above: the
    /// synthesised decoder does not apply property defaults for a missing key,
    /// so a non-optional would discard every sign-in stored before this field.
    var driveType: String? = nil

    /// This grant if it can still be used, nil if the provider ended it.
    ///
    /// The guard that keeps a kept grant inert. A revoked refresh token fails
    /// identically forever, so one that reached an adapter would turn a single
    /// honest sign-in into an unbreakable loop of failed listings — which is
    /// exactly why the old code deleted it. `revoked` also strips the refresh
    /// token, so even a caller that ignores this cannot build a retry loop.
    var usable: MicrosoftGrant? { needsSignIn == true ? nil : self }

    /// The account, kept without its credential.
    static func revoked(identity: String?) -> MicrosoftGrant {
        MicrosoftGrant(
            tokens: MicrosoftTokenResponse(accessToken: "", refreshToken: nil,
                                           expiresAt: .distantPast),
            identity: identity,
            needsSignIn: true)
    }
}

/// Which Keychain item a given sign-in lives in.
///
/// **One item per account, keyed on a hash of the signed-in address.** The
/// service name already differs per platform (`cloud-microsoft-teams` vs
/// `cloud-google-meet`), so `(service, account)` is platform-scoped without the
/// platform appearing here — adding it would key the same fact twice.
///
/// **Hashed, never the raw address.** `kSecAttrAccount` is unencrypted item
/// metadata: it is readable in Keychain Access without unlocking the item's
/// data, and a client's email address sitting there is exactly the leak this
/// project cares about. Same reasoning, same shape as `MCPTokenStore`, which
/// hashes a project path for the same reason.
///
/// **The address is the identifier, and that is a v1 decision.** Microsoft's
/// token carries an immutable object id and Google's a `sub`, either of which
/// would survive a rename — but a researcher who renames their account and
/// signs in again, acquiring a second row for the same account, is an edge case
/// not worth the parsing. The second row is visible, it is labelled with its
/// address, and it has a Disconnect button.
enum CloudAccountKey {

    /// Where a grant whose address never arrived is stored.
    ///
    /// `/me` can fail while the tokens are perfectly good, and a sign-in with no
    /// address is still a sign-in worth keeping. One slot, because there can
    /// only be one unidentified account per service before the identity lands
    /// and moves it.
    static let unidentified = "unidentified"

    /// The single fixed slot every cloud grant used before per-account keying.
    /// Read once by `migrateLegacyItems`, then deleted; nothing writes here.
    static let legacy = KeychainHelper.account

    static func derive(_ identity: String?) -> String {
        guard let identity, !identity.isEmpty else { return unidentified }
        // Lowercased: mail servers treat the domain case-insensitively and
        // providers hand back whatever casing the directory holds, so the same
        // account must not key two ways because Graph capitalised it today.
        let digest = SHA256.hash(data: Data(identity.lowercased().utf8))
        return digest.map { String(format: "%02x", $0) }.joined()
    }
}

/// Where a cloud sign-in lives between window opens.
///
/// The Keychain, via the same helper the LLM provider keys use: a refresh
/// token is a durable credential for a third-party account, which is the
/// definition of what belongs there and not in UserDefaults. It inherits the
/// data-protection keychain and iCloud Keychain sync from `KeychainHelper`,
/// which is right for a revocable per-user credential and matches how every
/// other secret in this app is held.
///
/// **iCloud Keychain sync is deliberate and settled (18 Aug 2026)** — see
/// `docs/design-cloud-import.md` §7, "Non-synchronizable was reversed", which
/// records the decision and the reasoning. _(Both §7 and §10 said the opposite
/// until `4e7aeb18` trued them; this comment used to say they were wrong, which
/// now reads as confusion rather than as the justification it is.)_ The
/// realistic loss event is
/// the Mac being stolen, iCloud Keychain is end-to-end encrypted regardless of
/// Advanced Data Protection, and the grant permits downloading recordings from
/// an account the researcher is already signed into on the same devices all
/// day. `MCPTokenStore` is non-synchronizable for a reason that does not apply
/// here: that token names a server on *this* machine.
///
/// **Storage is injected rather than reached for.** Every function takes a
/// `KeychainStore`, defaulting to the live one, because the house rule is that
/// tests never touch the real Keychain — a SIGKILL bypasses teardown, so
/// cleanup is not crash-safe and a stray test could overwrite a real
/// credential. The keying, the migration and the enumeration are exactly the
/// parts worth pinning, and they are unpinnable without this.
enum CloudGrantStore {
    private static let log = Logger(subsystem: "app.bristlenose", category: "cloud-import")

    /// Namespaced away from the LLM providers, which share this helper's
    /// keyspace.
    private static let googleAccount = "cloud-google-meet"
    private static let teamsAccount = "cloud-microsoft-teams"

    // MARK: - Google

    static func loadGoogle(account: String,
                           store: any KeychainStore = KeychainHelper.liveStore,
                           discardingUnreadable: Bool = true) -> GoogleGrant? {
        guard let raw = store.get(provider: googleAccount, account: account),
              let data = raw.data(using: .utf8)
        else { return nil }
        guard let grant = try? JSONDecoder().decode(GoogleGrant.self, from: data) else {
            // A blob we cannot read is a blob from an older shape. Dropping it
            // costs one sign-in; keeping it would fail the same way on every
            // launch, silently, forever.
            //
            // **But only where a sign-in immediately follows.** That reasoning
            // was written when `load` meant "restore a window", and it stopped
            // being true when `connections()` began decoding every stored grant
            // just to draw a Settings row — at which point merely opening the
            // pane deleted anything it could not parse, for services the
            // researcher was not even using. With iCloud sync on, that deletion
            // then propagates: an older Mac that cannot read a newer blob
            // destroys it everywhere. Chesterton's fence, moved rather than
            // removed.
            guard discardingUnreadable else {
                log.notice("cloud_grant google decode failed — keeping")
                return nil
            }
            log.notice("cloud_grant google decode failed — discarding")
            clearGoogle(account: account, store: store)
            return nil
        }
        return grant
    }

    /// Save, or — on nil — forget. Returns the key the grant now lives under.
    ///
    /// One entry point for both because the callers that need to forget are
    /// exactly the callers that would otherwise leave a dead grant behind: a
    /// refresh that failed, a sign-in that was revoked. A separate `clear`
    /// that someone forgets to call is how a revoked account keeps its
    /// "signed in" appearance until the user reinstalls.
    ///
    /// `previousKey` is what makes the identity arriving *late* survivable. A
    /// grant restored without an address opens at `unidentified`, and Google's
    /// adapter then fetches the address on its first listing — so the key it
    /// should be stored under changes mid-session. Without the old key to
    /// delete, that leaves two items for one account and the pane shows the
    /// same person twice.
    @discardableResult
    static func saveGoogle(_ grant: GoogleGrant?,
                           previousKey: String,
                           store: any KeychainStore = KeychainHelper.liveStore) -> String {
        guard let grant else {
            clearGoogle(account: previousKey, store: store)
            return previousKey
        }
        let key = CloudAccountKey.derive(grant.identity)
        guard let data = try? JSONEncoder().encode(grant),
              let raw = String(data: data, encoding: .utf8)
        else {
            log.error("cloud_grant google encode failed")
            return previousKey
        }
        if !store.set(provider: googleAccount, account: key, value: raw) {
            // Not fatal, and deliberately not surfaced: the session still
            // works, it just will not survive the window closing. Logged
            // because "why am I signing in again?" is otherwise unanswerable.
            log.error("cloud_grant google keychain write refused")
            return previousKey
        }
        // Only after the new item is safely written. Deleting first would turn
        // a refused write into a lost sign-in.
        // **Only rekey out of the anonymous slot.** `previousKey` exists for one
        // case — a session that opened at `unidentified` and learnt its address
        // — and an unguarded delete silently generalises that to "the
        // researcher signed in as somebody else", which removes the account
        // they were previously using. That would make this change's own thesis
        // false: the second sign-in would still eat the first, just one layer up.
        if previousKey != key, previousKey == CloudAccountKey.unidentified {
            clearGoogle(account: previousKey, store: store)
        }
        return key
    }

    static func clearGoogle(account: String,
                            store: any KeychainStore = KeychainHelper.liveStore) {
        store.delete(provider: googleAccount, account: account)
    }

    // MARK: - Teams

    static func loadTeams(account: String,
                          store: any KeychainStore = KeychainHelper.liveStore,
                          discardingUnreadable: Bool = true) -> MicrosoftGrant? {
        guard let raw = store.get(provider: teamsAccount, account: account),
              let data = raw.data(using: .utf8)
        else { return nil }
        guard let grant = try? JSONDecoder().decode(MicrosoftGrant.self, from: data) else {
            // Same rule as Google's above, and the same reason.
            guard discardingUnreadable else {
                log.notice("cloud_grant teams decode failed — keeping")
                return nil
            }
            log.notice("cloud_grant teams decode failed — discarding")
            clearTeams(account: account, store: store)
            return nil
        }
        return grant
    }

    /// Save, or — on nil — forget. Same one-entry-point and same rekey rule as
    /// Google above.
    @discardableResult
    static func saveTeams(_ grant: MicrosoftGrant?,
                          previousKey: String,
                          store: any KeychainStore = KeychainHelper.liveStore) -> String {
        guard let grant else {
            clearTeams(account: previousKey, store: store)
            return previousKey
        }
        let key = CloudAccountKey.derive(grant.identity)
        guard let data = try? JSONEncoder().encode(grant),
              let raw = String(data: data, encoding: .utf8)
        else {
            log.error("cloud_grant teams encode failed")
            return previousKey
        }
        if !store.set(provider: teamsAccount, account: key, value: raw) {
            log.error("cloud_grant teams keychain write refused")
            return previousKey
        }
        // **Only rekey out of the anonymous slot.** `previousKey` exists for one
        // case — a session that opened at `unidentified` and learnt its address
        // — and an unguarded delete silently generalises that to "the
        // researcher signed in as somebody else", which removes the account
        // they were previously using. That would make this change's own thesis
        // false: the second sign-in would still eat the first, just one layer up.
        if previousKey != key, previousKey == CloudAccountKey.unidentified {
            clearTeams(account: previousKey, store: store)
        }
        return key
    }

    static func clearTeams(account: String,
                           store: any KeychainStore = KeychainHelper.liveStore) {
        store.delete(provider: teamsAccount, account: account)
    }

    // MARK: - The platform-agnostic surface the Accounts pane talks to

    /// One connected account.
    struct Connection: Equatable, Identifiable, Sendable {
        let platform: CloudPlatform
        /// Which Keychain item this row is. Carried rather than re-derived
        /// because the address is optional and two rows can share a platform —
        /// so this is the only thing that identifies a row well enough to
        /// disconnect it.
        let accountKey: String
        /// The address signed in with. **Optional on purpose**: a grant stored
        /// before the identity travelled with it, or one whose `/me` lookup
        /// failed, is still a real connection that a researcher must be able to
        /// see and remove. A row with no address beats no row.
        let address: String?
        /// The provider ended this sign-in and the row is a tombstone: real,
        /// nameable, removable, and holding nothing that works.
        let needsSignIn: Bool
        /// What a past listing established about the account's drive, or nil if
        /// none ever has.
        ///
        /// Microsoft only. Google's equivalent is derived from the address for
        /// free and needs no storage; Zoom's tier question is answered by the
        /// provider at listing time. **Nil is a real and common state** — a
        /// researcher who signed in and never listed has an account nobody has
        /// asked about yet, and the pane must say nothing rather than guess.
        let driveTier: DriveTier?
        /// Platform *and* account: a consultant with a personal Microsoft
        /// account and a client's has two Teams rows, and a list keyed on the
        /// platform alone cannot hold both.
        var id: String { "\(platform.rawValue)/\(accountKey)" }
    }

    /// Every account currently holding a sign-in, platforms in the order §5
    /// sequences them.
    static func connections(store: any KeychainStore = KeychainHelper.liveStore) -> [Connection] {
        migrateLegacyItems(store: store)
        return CloudPlatform.built.flatMap { platform -> [Connection] in
            accountKeys(for: platform, store: store).compactMap { key in
                switch platform {
                case .teams:
                    // Non-destructive: this is a read to *draw a row*, and a
                    // Settings pane must not delete a credential it merely
                    // failed to parse. The restore path keeps the discard.
                    return loadTeams(account: key, store: store,
                                     discardingUnreadable: false).map {
                        Connection(platform: platform, accountKey: key,
                                   address: $0.identity, needsSignIn: $0.needsSignIn == true,
                                   // `map`, not a default: a grant stored before
                                   // the field existed, or by a session that
                                   // never listed, has no verdict — and "not
                                   // asked" must not read as "asked and found
                                   // nothing".
                                   driveTier: $0.driveType.map(DriveTier.init(driveType:)))
                    }
                case .meet:
                    return loadGoogle(account: key, store: store,
                                      discardingUnreadable: false).map {
                        Connection(platform: platform, accountKey: key,
                                   address: $0.identity, needsSignIn: $0.needsSignIn == true,
                                   // Google's tier comes from the address, free,
                                   // in `AccountsSectionModel`. Nothing to store
                                   // and nothing to carry.
                                   driveTier: nil)
                    }
                case .zoom:
                    // No store yet — Zoom is parked and cannot sign in, so there
                    // is never a grant to find. An explicit case rather than a
                    // `default` so wiring Zoom's store is a compile-time prompt.
                    return nil
                }
            }
        }
    }

    /// The key an import window should open against, or nil when nothing is
    /// connected.
    ///
    /// **First, not chosen.** Choosing between two accounts belongs at the
    /// moment of use, where the researcher knows which client they are working
    /// on — a picker in the import window, and only once a second account
    /// exists (§3 issue 4). Until that ships this returns the first, which is
    /// the only account there is: nothing yet offers a way to add a second.
    static func firstAccountKey(for platform: CloudPlatform,
                                store: any KeychainStore = KeychainHelper.liveStore) -> String? {
        migrateLegacyItems(store: store)
        return accountKeys(for: platform, store: store).first
    }

    private static func accountKeys(for platform: CloudPlatform,
                                    store: any KeychainStore) -> [String] {
        switch platform {
        case .teams: return store.accounts(provider: teamsAccount)
        case .meet:  return store.accounts(provider: googleAccount)
        case .zoom:  return []
        }
    }

    /// Forget one account's sign-in.
    ///
    /// **Removing the stored copy is not the whole job.** A live adapter in an
    /// open import window holds its tokens in memory, so clearing the Keychain
    /// alone would leave a window that keeps listing and fetching against an
    /// account the researcher has just disconnected — the disconnect would look
    /// done and not be, which is the worst shape for a control whose entire
    /// purpose is revocation. The notification is how the live session learns.
    ///
    /// It carries the account key as well as the platform because with two
    /// accounts on one platform, matching on the platform alone would close a
    /// window signed in to the *other* one.
    static func disconnect(_ platform: CloudPlatform,
                           accountKey: String,
                           store: any KeychainStore = KeychainHelper.liveStore) {
        switch platform {
        case .teams: clearTeams(account: accountKey, store: store)
        case .meet:  clearGoogle(account: accountKey, store: store)
        case .zoom:  break
        }
        NotificationCenter.default.post(
            name: .bristlenoseCloudAccountDisconnected,
            object: nil,
            userInfo: ["platform": platform.rawValue, "account": accountKey])
    }

    // MARK: - Migration

    /// Move anything stored under the old fixed key to its per-account key.
    ///
    /// Runs on every read rather than behind a once-flag: it is one Keychain
    /// miss in the ordinary case, and a flag is a thing to reset in tests and
    /// to get wrong across processes.
    ///
    /// **The old item is deleted.** Leaving it would mean every future
    /// enumeration finds an account under a key nothing derives, so the pane
    /// would show a duplicate row that reappears each time it is removed. If
    /// the rewrite fails the researcher signs in again — stated plainly here
    /// rather than answered with a fallback chain to maintain forever.
    static func migrateLegacyItems(store: any KeychainStore = KeychainHelper.liveStore) {
        migrate(provider: teamsAccount, store: store) { raw in
            (try? JSONDecoder().decode(MicrosoftGrant.self, from: raw))?.identity
        }
        migrate(provider: googleAccount, store: store) { raw in
            (try? JSONDecoder().decode(GoogleGrant.self, from: raw))?.identity
        }
    }

    private static func migrate(provider: String,
                                store: any KeychainStore,
                                identity: (Data) -> String?) {
        guard let raw = store.get(provider: provider, account: CloudAccountKey.legacy),
              let data = raw.data(using: .utf8)
        else { return }
        // An undecodable legacy blob still moves. Its key would be
        // `unidentified` either way, and `load` discards what it cannot read —
        // so this leaves the deletion to the reader rather than doing it here,
        // where a decoder change would look like a data loss bug.
        let key = CloudAccountKey.derive(identity(data))
        // **Never overwrite an item that is already there.** With iCloud
        // Keychain sync on, a two-Mac fleet on two versions can loop: the new
        // build migrates and deletes the legacy item, the old build sees
        // nothing, prompts a re-sign-in and writes the legacy key again, and
        // the new build migrates *again* — over a grant it has since refreshed,
        // reverting to a rotated-away refresh token. The same shape happens on
        // a plain downgrade. Deleting the legacy item is still right: it has
        // already been superseded.
        guard store.get(provider: provider, account: key) == nil else {
            store.delete(provider: provider, account: CloudAccountKey.legacy)
            return
        }
        guard store.set(provider: provider, account: key, value: raw) else {
            log.error("cloud_grant migration write refused — leaving the legacy item in place")
            return
        }
        store.delete(provider: provider, account: CloudAccountKey.legacy)
        log.info("cloud_grant migrated a sign-in to per-account storage")
    }
}

/// The one place a live session's grant is written.
///
/// **Serial by construction, and that is the whole point.** Each adapter
/// published through `Task.detached`, and two detached tasks have no relative
/// ordering — so a refusal published moments before a successful re-sign-in
/// could land *after* it and write a tombstone over a working grant. The
/// account then silently reverted to "sign in again" with nothing anywhere
/// explaining it. A serial queue makes the order the publishes were made in the
/// order they land, by construction rather than by comparison.
///
/// It also closes the other half. The value it replaced held a lock across the
/// Keychain write, while the disconnect matcher read the key on the main actor
/// through the same lock — so a write parked on an authorisation prompt (routine
/// on an ad-hoc build) blocked the main thread, which is exactly what the
/// detached hop existed to prevent, re-entered through the mutex. Here the write
/// happens on the queue under no lock at all, and `currentKey`'s lock is held
/// for a pointer swap and nothing else.
///
/// The key *moves*, which is why this owns it rather than the caller: a session
/// restored without an address starts at `unidentified` and rekeys the moment
/// the identity lands.
final class CloudGrantWriter: @unchecked Sendable {

    /// One queue, no concurrency. `.utility` because nothing waits on it.
    private let queue = DispatchQueue(label: "app.bristlenose.cloud-grant", qos: .utility)

    /// The authoritative key. Touched only on `queue`, so it needs no lock.
    private var key: String

    /// A copy for readers that must not block — the disconnect matcher runs on
    /// the main actor. Deliberately a *snapshot*: it can lag an in-flight write
    /// by the length of one Keychain call, and that is the right trade. Erring
    /// stale makes `CloudDisconnectMatch` see an unknown key, and unknown drops
    /// the session, which is already the safe direction.
    private let snapshotLock = NSLock()
    private var snapshot: String

    init(key: String) {
        self.key = key
        self.snapshot = key
    }

    var currentKey: String {
        snapshotLock.lock(); defer { snapshotLock.unlock() }
        return snapshot
    }

    /// Enqueue a write and return immediately.
    ///
    /// `write` is handed the key the grant is currently stored under and returns
    /// the one it now lives under — `CloudGrantStore.saveTeams`/`saveGoogle`'s
    /// `previousKey` contract, which is why this is a closure rather than a
    /// grant: the store owns the rekey decision, and this owns the ordering.
    func publish(_ write: @escaping @Sendable (String) -> String) {
        queue.async { [self] in
            let next = write(key)
            key = next
            snapshotLock.lock(); snapshot = next; snapshotLock.unlock()
        }
    }

    /// Wait for every enqueued write to finish. **Tests only** — production has
    /// nothing that needs to know, and a synchronous barrier on the main actor
    /// would reintroduce the block this type exists to remove.
    func settleForTesting() {
        queue.sync {}
    }
}

/// Whether a disconnect reaches a live import session.
///
/// A free function rather than a branch inside the coordinator's notification
/// block, because it is the decision worth pinning and a `NotificationCenter`
/// observer is an awkward place to test one.
enum CloudDisconnectMatch {

    /// - Parameters:
    ///   - liveAccountKey: nil when the session holds no credentials — a
    ///     fixture window, or one opened before the key was known.
    ///   - notedAccountKey: nil when the notification predates account keys or
    ///     is malformed.
    ///
    /// **Unknown on either side drops the session.** The costs are not
    /// symmetric: dropping a session that would have survived costs a re-open,
    /// while keeping one that should have gone leaves a window listing and
    /// fetching under an account the researcher believes they disconnected —
    /// which is the exact failure the disconnect control exists to prevent.
    static func dropsSession(livePlatform: CloudPlatform,
                             liveAccountKey: String?,
                             notedPlatform: String?,
                             notedAccountKey: String?) -> Bool {
        // Fail closed in the safe direction: an unreadable payload must not be
        // read as "disconnect whatever is open".
        guard let notedPlatform, notedPlatform == livePlatform.rawValue else { return false }
        guard let notedAccountKey, let liveAccountKey else { return true }
        return notedAccountKey == liveAccountKey
    }
}

extension Notification.Name {
    /// Posted after a cloud sign-in is forgotten. `userInfo["platform"]` carries
    /// the `CloudPlatform` raw value and `userInfo["account"]` the account key.
    static let bristlenoseCloudAccountDisconnected =
        Notification.Name("bristlenoseCloudAccountDisconnected")
}
