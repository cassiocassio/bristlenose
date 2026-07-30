import Testing

@testable import Bristlenose

/// The pure half of `MCPTokenStore` — the account-key derivation. Keychain
/// read/write/mint stay untested by design: they'd hit the real
/// data-protection keychain (per the KeychainHelper convention, tests never
/// touch real SecItem), and the derivation is where the decisions live.
struct MCPTokenStoreTests {

    @Test func accountKeyIsDeterministic() {
        let a = MCPTokenStore.accountKey(for: "/Users/x/Projects/study")
        let b = MCPTokenStore.accountKey(for: "/Users/x/Projects/study")
        #expect(a == b)
    }

    @Test func accountKeyDistinguishesProjects() {
        let a = MCPTokenStore.accountKey(for: "/Users/x/Projects/study-a")
        let b = MCPTokenStore.accountKey(for: "/Users/x/Projects/study-b")
        #expect(a != b)
    }

    @Test func accountKeyStandardisesThePath() {
        // Same folder spelled two ways must map to one token — ServeManager
        // and the Python importer both identify projects by resolved path.
        let direct = MCPTokenStore.accountKey(for: "/Users/x/Projects/study")
        let dotted = MCPTokenStore.accountKey(for: "/Users/x/Projects/../Projects/study/")
        #expect(direct == dotted)
    }

    @Test func accountKeyNeverEmbedsThePath() {
        // The key is Keychain item metadata, readable without unlocking the
        // item — a client's folder name must not leak into it.
        let key = MCPTokenStore.accountKey(for: "/Users/x/Clients/Acme Bank/study")
        #expect(!key.contains("Acme"))
        #expect(key.count == 64)  // SHA-256 hex
        #expect(key.allSatisfy { $0.isHexDigit })
    }
}
