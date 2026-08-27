import Foundation
import Testing

@testable import Bristlenose

// A Zoom sign-in that survives the window closing.
//
// Zoom is the third platform to store a grant and the first where losing one
// is unrecoverable rather than annoying: its refresh tokens are single-use and
// rotate on every refresh, so a save that silently stores nothing does not cost
// the researcher an extra sign-in — it strands the account behind a consent
// screen Zoom will not let a public client skip.
//
// Everything here runs against an injected `InMemoryKeychain`. The house rule:
// tests never touch the real Keychain, because a SIGKILL bypasses teardown, so
// cleanup is not crash-safe and a stray test could overwrite a real credential.

@Suite("A restored Zoom sign-in")
struct ZoomGrantTests {

    private func tokens(_ access: String,
                        refresh: String = "r",
                        expiresIn: TimeInterval = 3600) -> ZoomTokens {
        ZoomTokens(accessToken: access,
                   refreshToken: refresh,
                   expiresAt: Date().addingTimeInterval(expiresIn),
                   scopes: ZoomScopes.requested)
    }

    @Test("Every field survives the round trip")
    func fullGrantRoundTrips() throws {
        let original = ZoomGrant(tokens: tokens("listing"), identity: "martin@example.org")

        let decoded = try JSONDecoder().decode(
            ZoomGrant.self, from: try JSONEncoder().encode(original))

        // Asserted whole, not field by field. A field-by-field test passes
        // unchanged when someone adds a field and forgets to carry it — which
        // is the only way this type breaks, and it breaks silently.
        #expect(decoded == original)
    }

    @Test("A grant stored before the two flags existed still decodes")
    func olderShapeStillDecodes() throws {
        // `needsSignIn` is `Bool?` rather than a defaulted `Bool` because the
        // synthesised decoder does NOT apply property defaults for a missing
        // key — it throws, and `loadZoom` discards what it cannot decode. A
        // non-optional would have dropped every sign-in stored before the
        // field existed.
        let raw = #"{"tokens":{"accessToken":"a","refreshToken":"r","expiresAt":0,"scopes":[]}}"#
        let decoded = try JSONDecoder().decode(ZoomGrant.self, from: Data(raw.utf8))

        #expect(decoded.needsSignIn == nil)
        #expect(decoded.usable != nil, "absent means never refused, not refused")
    }

    @Test("A revoked grant keeps the account and drops the credential")
    func revokedIsInert() {
        let dead = ZoomGrant.revoked(identity: "martin@example.org")

        #expect(dead.identity == "martin@example.org", "the row must survive to be nameable")
        #expect(dead.usable == nil)
        // Belt and braces: even a caller that ignores `usable` cannot build a
        // retry loop out of this, because there is nothing left to retry with.
        #expect(dead.tokens.refreshToken.isEmpty)
        #expect(dead.tokens.isExpired)
    }

    // MARK: - Through the store

    @Test("A saved grant can be found again, and removed")
    func saveEnumerateDisconnectRoundTrips() throws {
        // The invariant that matters is not "it saves". It is **every
        // credential this app can write, it can also show and delete.** Between
        // a writer shipping and its enumerator shipping there is a window in
        // which the app holds a client organisation's OAuth grant, replicates
        // it through iCloud Keychain, and offers no interface to see or remove
        // it. That is a data-subject-rights failure, not an inconvenience, and
        // it is avoidable purely by landing the three together.
        let store = InMemoryKeychain()
        let grant = ZoomGrant(tokens: tokens("a"), identity: "martin@example.org")

        let key = CloudGrantStore.saveZoom(grant, previousKey: CloudAccountKey.unidentified,
                                           store: store)
        #expect(key != nil, "a refused write must not report a key")

        let connections = CloudGrantStore.connections(store: store)
            .filter { $0.platform == .zoom }
        #expect(connections.count == 1)
        #expect(connections.first?.address == "martin@example.org")
        #expect(connections.first?.needsSignIn == false)

        CloudGrantStore.disconnect(.zoom, accountKey: try #require(key), store: store)
        #expect(CloudGrantStore.connections(store: store).filter { $0.platform == .zoom }.isEmpty)
    }

    @Test("A refused write returns nil rather than a key that holds nothing")
    func refusedWriteIsReported() {
        // This is the whole reason `saveZoom` returns `String?` where its two
        // siblings return `String`. They report a failed write by handing back
        // `previousKey`, which is indistinguishable from success whenever the
        // key did not change — survivable there, fatal here. `nil` is how
        // `refresh(_:)`'s persist closure knows to throw instead of returning a
        // token nobody can follow up.
        let store = InMemoryKeychain()
        store.refuseWrites = true

        let key = CloudGrantStore.saveZoom(
            ZoomGrant(tokens: tokens("a"), identity: "martin@example.org"),
            previousKey: CloudAccountKey.unidentified,
            store: store)

        #expect(key == nil)
    }

    @Test("A refused write fails the rotation rather than reporting success")
    func publishAndWaitReportsARefusedWrite() async {
        // **The seam the whole change rests on, and the one nothing else
        // reaches.** `persistRotation` → the sink → `publishAndWait` →
        // `saveZoom` is the chain that lets `refresh(_:)` refuse to report
        // success over a save that did not happen. The two neighbouring tests
        // stop short of it from either end: one injects a throwing `persist`
        // straight into the client, the other calls `saveZoom` standing alone.
        //
        // Three mutations this catches, each of which leaves every other test
        // in the repo green: resuming the continuation with `true`
        // unconditionally (every refused write reports success, and the account
        // strands); dropping the `key = next` assignment (the rekey never lands
        // and the next launch reads an empty slot); inverting the guard
        // (success reports failure and every rotation loses durability).
        let store = InMemoryKeychain()
        let writer = CloudGrantWriter(key: CloudAccountKey.unidentified)
        let grant = ZoomGrant(tokens: tokens("a"), identity: "martin@example.org")

        store.refuseWrites = true
        let refused = await writer.publishAndWait {
            CloudGrantStore.saveZoom(grant, previousKey: $0, store: store)
        }
        #expect(refused == false)
        #expect(writer.currentKey == CloudAccountKey.unidentified,
                "a refused write must not move the key it failed to write to")

        store.refuseWrites = false
        let landed = await writer.publishAndWait {
            CloudGrantStore.saveZoom(grant, previousKey: $0, store: store)
        }
        #expect(landed == true)
        #expect(writer.currentKey == CloudAccountKey.derive("martin@example.org"),
                "a successful write rekeys out of the anonymous slot")
    }

    @Test("A tombstone is stored, so the pane can still name the account")
    func revokedGrantIsStillEnumerable() {
        let store = InMemoryKeychain()
        _ = CloudGrantStore.saveZoom(ZoomGrant.revoked(identity: "martin@example.org"),
                                     previousKey: CloudAccountKey.unidentified,
                                     store: store)

        let row = CloudGrantStore.connections(store: store).first { $0.platform == .zoom }
        #expect(row?.needsSignIn == true)
        #expect(row?.address == "martin@example.org")
    }

    @Test("Reading a row does not delete a grant it merely failed to parse")
    func enumerationIsNonDestructive() {
        // `connections()` draws a Settings pane. A pane must not destroy a
        // credential because a newer build wrote a shape this one cannot read
        // — with iCloud sync on, that deletion propagates, so an older Mac
        // would destroy the grant everywhere.
        let store = InMemoryKeychain()
        let key = CloudAccountKey.derive("martin@example.org")
        _ = store.set(provider: "cloud-zoom", account: key, value: "{not json")

        _ = CloudGrantStore.connections(store: store)

        #expect(store.get(provider: "cloud-zoom", account: key) != nil,
                "the unreadable blob survives a read")
        // The restore path still discards, because there a sign-in follows
        // immediately and keeping it would fail identically on every launch.
        _ = CloudGrantStore.loadZoom(account: key, store: store)
        #expect(store.get(provider: "cloud-zoom", account: key) == nil)
    }
}
