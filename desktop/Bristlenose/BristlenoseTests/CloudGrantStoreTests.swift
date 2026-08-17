import Foundation
import Testing

@testable import Bristlenose

// What survives the window closing.
//
// Deliberately NOT testing `CloudGrantStore.saveGoogle` / `loadGoogle`: those
// go through `KeychainHelper` to the real Keychain, and the house rule is that
// tests never touch it — a SIGKILL bypasses teardown, so cleanup is not
// crash-safe and a stray test could overwrite a real credential.
//
// What IS worth pinning is the shape in between, because it fails silently:
// a field added to `GoogleGrant` and not carried by the encoder does not
// break a build or a test, it just quietly stops being restored, and the
// symptom lands weeks later as "why am I signing in again?".

@Suite("A restored Google sign-in")
struct CloudGrantStoreTests {

    private func tokens(_ access: String, refresh: String? = "r", expiresIn: TimeInterval = 3600)
        -> GoogleTokens {
        GoogleTokens(accessToken: access, refreshToken: refresh,
                     expiresAt: Date().addingTimeInterval(expiresIn),
                     granted: ["https://www.googleapis.com/auth/calendar.events.readonly"])
    }

    @Test("Every field survives the round trip")
    func fullGrantRoundTrips() throws {
        let original = GoogleGrant(
            tokens: tokens("listing"),
            media: .init(tokens: tokens("media"), fileIDs: ["a", "b"]),
            identity: "martin@example.org")

        let decoded = try JSONDecoder().decode(
            GoogleGrant.self, from: try JSONEncoder().encode(original))

        // Asserted whole, not field by field. A field-by-field test passes
        // unchanged when someone adds a field and forgets it — which is the
        // only way this type breaks.
        #expect(decoded == original)
    }

    @Test("A listing-only sign-in is a grant worth keeping")
    func mediaGrantIsOptional() throws {
        // A researcher can list without ever importing. Requiring the Picker
        // grant to persist anything would throw away the sign-in they did do.
        let original = GoogleGrant(tokens: tokens("listing"), media: nil, identity: "m@e.org")
        let decoded = try JSONDecoder().decode(
            GoogleGrant.self, from: try JSONEncoder().encode(original))
        #expect(decoded == original)
        #expect(decoded.media == nil)
    }

    @Test("The identity is carried, because the window opens on it")
    func identityIsPersisted() throws {
        // `CloudImportStore` picks its opening phase from `accountEmail`. Drop
        // this field and a restore holding a perfectly good token still opens
        // on the sign-in button — the restore works and looks like it didn't.
        let decoded = try JSONDecoder().decode(
            GoogleGrant.self,
            from: try JSONEncoder().encode(
                GoogleGrant(tokens: tokens("t"), media: nil, identity: "martin@example.org")))
        #expect(decoded.identity == "martin@example.org")
    }

    @Test("Expiry is preserved to the second, so a restore knows to refresh")
    func expirySurvives() throws {
        // The whole restore path turns on this: an hour-old token must read as
        // expired, or `list` uses it raw and 401s into a sign-in nobody needed.
        let soon = tokens("t", expiresIn: -120)
        #expect(soon.isExpired)
        let decoded = try JSONDecoder().decode(
            GoogleGrant.self,
            from: try JSONEncoder().encode(GoogleGrant(tokens: soon, media: nil, identity: nil)))
        #expect(decoded.tokens.isExpired)
    }

    @Test("A grant with no refresh token is still storable, and still dead on expiry")
    func noRefreshTokenIsRepresentable() throws {
        // Google omits a refresh token when it decides one is already held.
        // Storing that is fine; what must not happen is a restore treating it
        // as renewable — `renewedListingTokenIfNeeded` drops the grant instead,
        // which costs one honest sign-in rather than a permanent loop.
        let stale = tokens("t", refresh: nil, expiresIn: -60)
        let decoded = try JSONDecoder().decode(
            GoogleGrant.self,
            from: try JSONEncoder().encode(GoogleGrant(tokens: stale, media: nil, identity: nil)))
        #expect(decoded.tokens.refreshToken == nil)
        #expect(decoded.tokens.isExpired)
    }
}
