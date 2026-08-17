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
}

/// Where a cloud sign-in lives between window opens.
///
/// The Keychain, via the same helper the LLM provider keys use: a refresh
/// token is a durable credential for a third-party account, which is the
/// definition of what belongs there and not in UserDefaults. It inherits the
/// data-protection keychain and iCloud Keychain sync from `KeychainHelper`,
/// which is right for a revocable per-user credential and matches how every
/// other secret in this app is held.
enum CloudGrantStore {
    private static let log = Logger(subsystem: "app.bristlenose", category: "cloud-import")

    /// Namespaced away from the LLM providers, which share this helper's
    /// keyspace.
    private static let googleAccount = "cloud-google-meet"

    static func loadGoogle() -> GoogleGrant? {
        guard let raw = KeychainHelper.get(provider: googleAccount),
              let data = raw.data(using: .utf8)
        else { return nil }
        guard let grant = try? JSONDecoder().decode(GoogleGrant.self, from: data) else {
            // A blob we cannot read is a blob from an older shape. Dropping it
            // costs one sign-in; keeping it would fail the same way on every
            // launch, silently, forever.
            log.notice("cloud_grant google decode failed — discarding")
            clearGoogle()
            return nil
        }
        return grant
    }

    /// Save, or — on nil — forget.
    ///
    /// One entry point for both because the callers that need to forget are
    /// exactly the callers that would otherwise leave a dead grant behind: a
    /// refresh that failed, a sign-in that was revoked. A separate `clear`
    /// that someone forgets to call is how a revoked account keeps its
    /// "signed in" appearance until the user reinstalls.
    static func saveGoogle(_ grant: GoogleGrant?) {
        guard let grant else { clearGoogle(); return }
        guard let data = try? JSONEncoder().encode(grant),
              let raw = String(data: data, encoding: .utf8)
        else {
            log.error("cloud_grant google encode failed")
            return
        }
        if !KeychainHelper.set(provider: googleAccount, value: raw) {
            // Not fatal, and deliberately not surfaced: the session still
            // works, it just will not survive the window closing. Logged
            // because "why am I signing in again?" is otherwise unanswerable.
            log.error("cloud_grant google keychain write refused")
        }
    }

    static func clearGoogle() {
        KeychainHelper.delete(provider: googleAccount)
    }

    private static let teamsAccount = "cloud-microsoft-teams"

    static func loadTeams() -> MicrosoftGrant? {
        guard let raw = KeychainHelper.get(provider: teamsAccount),
              let data = raw.data(using: .utf8)
        else { return nil }
        guard let grant = try? JSONDecoder().decode(MicrosoftGrant.self, from: data) else {
            log.notice("cloud_grant teams decode failed — discarding")
            clearTeams()
            return nil
        }
        return grant
    }

    /// Save, or — on nil — forget. Same one-entry-point rule as Google: the
    /// callers that need to forget are exactly the ones that would otherwise
    /// leave a revoked grant looking live.
    static func saveTeams(_ grant: MicrosoftGrant?) {
        guard let grant else { clearTeams(); return }
        guard let data = try? JSONEncoder().encode(grant),
              let raw = String(data: data, encoding: .utf8)
        else {
            log.error("cloud_grant teams encode failed")
            return
        }
        if !KeychainHelper.set(provider: teamsAccount, value: raw) {
            log.error("cloud_grant teams keychain write refused")
        }
    }

    static func clearTeams() {
        KeychainHelper.delete(provider: teamsAccount)
    }

    // MARK: - The platform-agnostic surface the Accounts pane talks to

    /// One connected account.
    struct Connection: Equatable, Identifiable, Sendable {
        let platform: CloudPlatform
        /// The address signed in with. **Optional on purpose**: a grant stored
        /// before the identity travelled with it, or one whose `/me` lookup
        /// failed, is still a real connection that a researcher must be able to
        /// see and remove. A row with no address beats no row.
        let address: String?
        var id: String { platform.rawValue }
    }

    /// Every platform currently holding a sign-in, in the order §5 sequences
    /// them.
    static func connections() -> [Connection] {
        CloudPlatform.built.compactMap { platform in
            switch platform {
            case .teams:
                return loadTeams().map { Connection(platform: platform, address: $0.identity) }
            case .meet:
                return loadGoogle().map { Connection(platform: platform, address: $0.identity) }
            case .zoom:
                // No store yet — Zoom is parked and cannot sign in, so there is
                // never a grant to find. An explicit case rather than a
                // `default` so wiring Zoom's store is a compile-time prompt.
                return nil
            }
        }
    }

    /// Forget one platform's sign-in.
    ///
    /// **Removing the stored copy is not the whole job.** A live adapter in an
    /// open import window holds its tokens in memory, so clearing the Keychain
    /// alone would leave a window that keeps listing and fetching against an
    /// account the researcher has just disconnected — the disconnect would look
    /// done and not be, which is the worst shape for a control whose entire
    /// purpose is revocation. The notification is how the live session learns.
    static func disconnect(_ platform: CloudPlatform) {
        switch platform {
        case .teams: clearTeams()
        case .meet:  clearGoogle()
        case .zoom:  break
        }
        NotificationCenter.default.post(
            name: .bristlenoseCloudAccountDisconnected,
            object: nil,
            userInfo: ["platform": platform.rawValue])
    }
}

extension Notification.Name {
    /// Posted after a cloud sign-in is forgotten. `userInfo["platform"]` carries
    /// the `CloudPlatform` raw value.
    static let bristlenoseCloudAccountDisconnected =
        Notification.Name("bristlenoseCloudAccountDisconnected")
}
