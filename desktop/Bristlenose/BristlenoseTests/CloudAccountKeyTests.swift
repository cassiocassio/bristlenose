import Foundation
import Testing

@testable import Bristlenose

// One Keychain item per account.
//
// The bug this closes is silent and total: `KeychainHelper` keyed every item on
// a fixed account string, so a second sign-in to the same service hit
// `errSecDuplicateItem`, took the `SecItemUpdate` path, and **overwrote the
// first account's token in place**. No error, `set` returned `true`, and the
// first account stopped working at its next refresh with nothing anywhere
// saying why. A consultant with a personal Microsoft account and one per client
// meets this on their second connection, which is the ordinary case for this
// audience rather than an edge one.
//
// Every test here runs against `InMemoryKeychain`, never the real Keychain —
// the house rule, because a SIGKILL bypasses teardown and cleanup is not
// crash-safe. That mock is keyed on `(provider, account)` exactly as SecItem
// is, so it can reproduce the bug rather than paper over it.

@Suite("Per-account credential storage")
struct CloudAccountKeyTests {

    // MARK: Deriving the key

    @Test("The same address always keys the same item")
    func derivationIsStable() {
        #expect(CloudAccountKey.derive("martin@clientco.com")
                == CloudAccountKey.derive("martin@clientco.com"))
    }

    @Test("Two addresses key two items")
    func differentAddressesDiffer() {
        #expect(CloudAccountKey.derive("martin@clientco.com")
                != CloudAccountKey.derive("martin@outlook.com"))
    }

    @Test("Casing does not fork the account")
    func casingIsNormalised() {
        // Providers hand back whatever casing their directory holds, and a
        // second sign-in returning `Martin@ClientCo.com` must not read as a
        // different account.
        #expect(CloudAccountKey.derive("Martin@ClientCo.com")
                == CloudAccountKey.derive("martin@clientco.com"))
    }

    @Test("A sign-in whose address never arrived still has somewhere to live")
    func missingIdentityIsRepresentable() {
        // `/me` can fail while the tokens are perfectly good. Refusing to store
        // that grant would throw away a working sign-in over a cosmetic lookup.
        #expect(CloudAccountKey.derive(nil) == CloudAccountKey.unidentified)
        #expect(CloudAccountKey.derive("") == CloudAccountKey.unidentified)
    }

    @Test("The address never appears in the key")
    func addressIsNotReadableInMetadata() {
        // The point of hashing. `kSecAttrAccount` is unencrypted metadata,
        // readable in Keychain Access without unlocking the item's data — a
        // client's email sitting there is precisely the leak class this project
        // cares about.
        let key = CloudAccountKey.derive("martin@clientco.com")
        #expect(!key.contains("martin"))
        #expect(!key.contains("clientco"))
        #expect(!key.contains("@"))
        #expect(key.count == 64, "expected SHA-256 hex")
    }

    // MARK: The bug itself

    @Test("A second account does not overwrite the first")
    func twoAccountsCoexist() {
        // The regression that motivates the whole change. On the old fixed-key
        // storage the second save replaced the first in place and this failed.
        let keychain = InMemoryKeychain()

        let work = teamsGrant(access: "work-token", identity: "martin@clientco.com")
        let personal = teamsGrant(access: "personal-token", identity: "martin@outlook.com")

        CloudGrantStore.saveTeams(work, previousKey: CloudAccountKey.unidentified, store: keychain)
        CloudGrantStore.saveTeams(personal, previousKey: CloudAccountKey.unidentified, store: keychain)

        let workKey = CloudAccountKey.derive("martin@clientco.com")
        let personalKey = CloudAccountKey.derive("martin@outlook.com")

        #expect(CloudGrantStore.loadTeams(account: workKey, store: keychain)?.tokens.accessToken
                == "work-token",
                "the first account's token did not survive the second sign-in")
        #expect(CloudGrantStore.loadTeams(account: personalKey, store: keychain)?.tokens.accessToken
                == "personal-token")
    }

    @Test("Both accounts are listed, and the list can tell them apart")
    func bothAccountsEnumerate() {
        let keychain = InMemoryKeychain()
        CloudGrantStore.saveTeams(teamsGrant(access: "a", identity: "martin@clientco.com"),
                                  previousKey: CloudAccountKey.unidentified, store: keychain)
        CloudGrantStore.saveTeams(teamsGrant(access: "b", identity: "martin@outlook.com"),
                                  previousKey: CloudAccountKey.unidentified, store: keychain)

        let connections = CloudGrantStore.connections(store: keychain)

        #expect(connections.count == 2)
        #expect(Set(connections.compactMap(\.address))
                == ["martin@clientco.com", "martin@outlook.com"])
        // `ForEach` needs these distinct or one row silently disappears — which
        // is how "two accounts" would look like "one account" in the pane while
        // both were stored correctly underneath.
        #expect(Set(connections.map(\.id)).count == 2)
    }

    @Test("Disconnecting one account leaves the other connected")
    func disconnectIsPerAccount() {
        let keychain = InMemoryKeychain()
        CloudGrantStore.saveTeams(teamsGrant(access: "a", identity: "martin@clientco.com"),
                                  previousKey: CloudAccountKey.unidentified, store: keychain)
        CloudGrantStore.saveTeams(teamsGrant(access: "b", identity: "martin@outlook.com"),
                                  previousKey: CloudAccountKey.unidentified, store: keychain)

        CloudGrantStore.disconnect(.teams,
                                   accountKey: CloudAccountKey.derive("martin@outlook.com"),
                                   store: keychain)

        let remaining = CloudGrantStore.connections(store: keychain)
        #expect(remaining.map(\.address) == ["martin@clientco.com"])
    }

    @Test("Two platforms are separate keyspaces even for one address")
    func platformsDoNotCollide() {
        // The same researcher signed in to Teams and Meet with the same address
        // derives the same account key — the service name is what separates
        // them, which is why the platform is deliberately absent from the hash.
        let keychain = InMemoryKeychain()
        CloudGrantStore.saveTeams(teamsGrant(access: "teams", identity: "m@e.org"),
                                  previousKey: CloudAccountKey.unidentified, store: keychain)
        CloudGrantStore.saveGoogle(googleGrant(access: "meet", identity: "m@e.org"),
                                   previousKey: CloudAccountKey.unidentified, store: keychain)

        let key = CloudAccountKey.derive("m@e.org")
        #expect(CloudGrantStore.loadTeams(account: key, store: keychain)?.tokens.accessToken
                == "teams")
        #expect(CloudGrantStore.loadGoogle(account: key, store: keychain)?.tokens.accessToken
                == "meet")
    }

    // MARK: Rekeying when the identity arrives late

    @Test("An identity arriving late moves the item rather than duplicating it")
    func rekeyOnLateIdentity() {
        // Google's adapter fetches the address on its first listing when it was
        // restored without one, so the key a session should write under changes
        // mid-session. Leave the old item behind and the pane shows the same
        // person twice, with one row holding a grant nothing will ever update.
        let keychain = InMemoryKeychain()

        let anonymous = googleGrant(access: "t", identity: nil)
        let key = CloudGrantStore.saveGoogle(anonymous,
                                             previousKey: CloudAccountKey.unidentified,
                                             store: keychain)
        #expect(key == CloudAccountKey.unidentified)

        let identified = googleGrant(access: "t", identity: "martin@finca342.org")
        let moved = CloudGrantStore.saveGoogle(identified, previousKey: key, store: keychain)

        #expect(moved == CloudAccountKey.derive("martin@finca342.org"))
        #expect(CloudGrantStore.loadGoogle(account: CloudAccountKey.unidentified, store: keychain)
                == nil,
                "the pre-identity item was left behind")
        #expect(CloudGrantStore.connections(store: keychain).count == 1)
    }

    @Test("Forgetting a grant clears the slot it was actually in")
    func nilForgetsThePreviousKey() {
        let keychain = InMemoryKeychain()
        let key = CloudGrantStore.saveTeams(teamsGrant(access: "t", identity: "m@e.org"),
                                            previousKey: CloudAccountKey.unidentified,
                                            store: keychain)

        // A refused refresh drops the grant by publishing nil — it must reach
        // the item the session was writing to, not a key re-derived from a
        // grant that no longer exists.
        CloudGrantStore.saveTeams(nil, previousKey: key, store: keychain)

        #expect(CloudGrantStore.connections(store: keychain).isEmpty)
    }

    // MARK: Migration off the old fixed key

    @Test("A sign-in stored under the old fixed key moves to its own")
    func legacyItemMigrates() {
        let keychain = InMemoryKeychain()
        writeLegacyTeams(teamsGrant(access: "old", identity: "martin@clientco.com"),
                         into: keychain)

        let connections = CloudGrantStore.connections(store: keychain)

        #expect(connections.count == 1)
        #expect(connections.first?.address == "martin@clientco.com")
        #expect(connections.first?.accountKey == CloudAccountKey.derive("martin@clientco.com"))
    }

    @Test("The old item is deleted, not merely copied")
    func legacyItemIsRemoved() {
        // Leaving it means every future enumeration finds an account under a
        // key nothing derives — a duplicate row that comes back each time it is
        // removed.
        let keychain = InMemoryKeychain()
        writeLegacyTeams(teamsGrant(access: "old", identity: "martin@clientco.com"),
                         into: keychain)

        CloudGrantStore.migrateLegacyItems(store: keychain)

        #expect(keychain.get(provider: "cloud-microsoft-teams",
                             account: CloudAccountKey.legacy) == nil)
        #expect(CloudGrantStore.connections(store: keychain).count == 1)
    }

    @Test("Migrating twice does not produce two accounts")
    func migrationIsIdempotent() {
        // It runs on every read rather than behind a once-flag, so this is the
        // ordinary path and not a defensive extra.
        let keychain = InMemoryKeychain()
        writeLegacyTeams(teamsGrant(access: "old", identity: "m@e.org"), into: keychain)

        CloudGrantStore.migrateLegacyItems(store: keychain)
        CloudGrantStore.migrateLegacyItems(store: keychain)

        #expect(CloudGrantStore.connections(store: keychain).count == 1)
    }

    @Test("A legacy sign-in with no address migrates rather than being dropped")
    func legacyWithoutIdentityMigrates() {
        let keychain = InMemoryKeychain()
        writeLegacyTeams(teamsGrant(access: "old", identity: nil), into: keychain)

        let connections = CloudGrantStore.connections(store: keychain)

        #expect(connections.count == 1)
        #expect(connections.first?.accountKey == CloudAccountKey.unidentified)
        #expect(connections.first?.address == nil)
    }

    @Test("A window opens against the migrated account, not an empty slot")
    func firstAccountKeyFindsTheMigratedItem() {
        // The failure this catches is a researcher who was signed in before the
        // upgrade being shown the sign-in button afterwards — a working
        // credential sitting one key away.
        let keychain = InMemoryKeychain()
        writeLegacyTeams(teamsGrant(access: "old", identity: "martin@clientco.com"),
                         into: keychain)

        let key = CloudGrantStore.firstAccountKey(for: .teams, store: keychain)

        #expect(key == CloudAccountKey.derive("martin@clientco.com"))
        #expect(CloudGrantStore.loadTeams(account: key ?? "", store: keychain)?
                .tokens.accessToken == "old")
    }

    @Test("Nothing connected reports nothing, rather than an empty account")
    func emptyKeychainHasNoConnections() {
        let keychain = InMemoryKeychain()
        #expect(CloudGrantStore.connections(store: keychain).isEmpty)
        #expect(CloudGrantStore.firstAccountKey(for: .teams, store: keychain) == nil)
    }

    // MARK: Fixtures

    private func teamsGrant(access: String, identity: String?) -> MicrosoftGrant {
        MicrosoftGrant(
            tokens: MicrosoftTokenResponse(accessToken: access,
                                           refreshToken: "r",
                                           expiresAt: Date().addingTimeInterval(3600)),
            identity: identity)
    }

    private func googleGrant(access: String, identity: String?) -> GoogleGrant {
        GoogleGrant(
            tokens: GoogleTokens(accessToken: access,
                                 refreshToken: "r",
                                 expiresAt: Date().addingTimeInterval(3600),
                                 granted: []),
            media: nil,
            identity: identity)
    }

    /// Write a grant where the pre-migration code would have put it.
    private func writeLegacyTeams(_ grant: MicrosoftGrant, into keychain: InMemoryKeychain) {
        let raw = String(data: try! JSONEncoder().encode(grant), encoding: .utf8)!
        keychain.set(provider: "cloud-microsoft-teams",
                     account: CloudAccountKey.legacy,
                     value: raw)
    }
}
