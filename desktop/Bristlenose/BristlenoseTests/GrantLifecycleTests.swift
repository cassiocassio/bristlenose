import Foundation
import Testing

@testable import Bristlenose

// What an adapter tells the store, and when.
//
// **This is the hole the 18 Aug review found behind its own findings.**
// `onGrantChanged` — the single seam through which every cloud credential is
// written, moved and destroyed — was executed by no test in the suite. The
// pure-value tests pinned what `MicrosoftGrant.revoked()` *constructs*; nothing
// pinned that anything ever *calls* it. So reverting `publishRefusal()` to
// `publishGrant(nil)` passed all 48 tests, and every credential-loss bug in that
// review lived in code no test ran.
//
// The layer is the adapter's public entry point (`list(window:)`) over the
// stubbed transport that `CloudTransportTests` already owns, with a spy on the
// callback. That is the cheapest place these behaviours are observable at all:
// they are decisions the adapter makes about a *network outcome*, so a unit test
// below the transport cannot reach them and a test above it cannot see them.

// **Nested inside `CloudTransportTests`, and `.serialized`.** `StubURLProtocol`
// is process-wide shared state, so a suite that enqueues responses in parallel
// with another one gets the other's queue. That file's own header records the
// same lesson from the other direction — three suites that passed in isolation
// and failed six tests in the full run — and these three did exactly that on
// first write: the 400 meant for one test was consumed by another, so the
// tombstone assertion timed out on an empty spy.
extension CloudTransportTests {

@Suite("What a refused refresh tells the store", .serialized)
struct GrantLifecycleTests {

    private let window = DateInterval(start: Date(timeIntervalSince1970: 1_723_000_000),
                                      duration: 30 * 24 * 3600)

    /// Records every grant the adapter publishes.
    ///
    /// An `actor` because `publishGrant` hands the callback to
    /// `Task.detached`, so the writes genuinely arrive off the caller's actor —
    /// the same property that makes the ordering hazard in the review's
    /// Finding 15 real. A plain array would be a data race in the test itself.
    private actor Spy {
        private(set) var published: [MicrosoftGrant?] = []
        func record(_ grant: MicrosoftGrant?) { published.append(grant) }

        /// Detached publishes land asynchronously, so wait for the count rather
        /// than sleeping — a sleep either flakes or wastes a second per test.
        func settle(untilAtLeast count: Int) async -> [MicrosoftGrant?] {
            for _ in 0..<200 {
                if published.count >= count { return published }
                try? await Task.sleep(nanoseconds: 5_000_000)
            }
            return published
        }
    }

    /// An adapter holding an **expired** token, so `list` must go through the
    /// refresh path — which is the only path that can publish a refusal.
    private func expiredTeamsSource(spy: Spy) -> TeamsSource {
        TeamsSource(
            config: MicrosoftOAuthConfig(clientID: "cid", tenant: "common",
                                         redirectURI: "msauth.test://auth"),
            session: StubURLProtocol.session(),
            restoredTokens: MicrosoftTokenResponse(accessToken: "stale",
                                                   refreshToken: "R",
                                                   expiresAt: .distantPast),
            restoredIdentity: "martin@clientco.com",
            onGrantChanged: { grant in Task { await spy.record(grant) } })
    }

    @Test("A refusal from the provider keeps the account and strips the credential")
    func authoritativeRefusalWritesATombstone() async {
        // The behaviour `a27f85b4` is named for, pinned through the path that
        // performs it rather than through the value it constructs. Before this
        // test, reverting `publishRefusal()` to `publishGrant(nil)` — which
        // deletes the account and makes a revoked sign-in vanish from Settings
        // — passed the entire suite.
        let spy = Spy()
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.json(#"{"error":"invalid_grant"}"#, status: 400))

        _ = await expiredTeamsSource(spy: spy).list(window: window)
        let published = await spy.settle(untilAtLeast: 1)

        let grant = try? #require(published.last ?? nil)
        #expect(grant?.needsSignIn == true, "the refusal did not mark the account")
        #expect(grant?.identity == "martin@clientco.com",
                "the account must stay nameable — a row that vanishes is the bug")
        #expect(grant?.tokens.refreshToken == nil,
                "a tombstone carrying a refresh token is a retry loop waiting to happen")
        #expect(grant?.usable == nil)
    }

    @Test("A dropped connection is not a refusal, and must not touch the stored grant")
    func networkFailureLeavesTheGrantAlone() async {
        // The review's highest-blast-radius finding, and it was logged LOW.
        // `try?` made a `URLError` indistinguishable from a 4xx, and since a
        // tombstone strips the refresh token, one moment of bad wifi destroyed
        // a working sign-in *permanently* and told the researcher their
        // provider had ended it. This path runs only when a token has aged out
        // — the ordinary next-morning case the whole restore feature exists to
        // serve, on the connection a researcher most often has.
        let spy = Spy()
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.transportFailure())

        _ = await expiredTeamsSource(spy: spy).list(window: window)
        let published = await spy.settle(untilAtLeast: 1)

        #expect(published.isEmpty,
                "a network blip published \(published.count) grant(s); it must publish none")
    }

    @Test("A 5xx is not a refusal either")
    func serverErrorLeavesTheGrantAlone() async {
        // Same rule, the other shape. Microsoft having a bad afternoon is not
        // the researcher's client revoking them, and the two must not produce
        // the same permanent outcome.
        let spy = Spy()
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.json(#"{"error":"temporarily_unavailable"}"#, status: 503))

        _ = await expiredTeamsSource(spy: spy).list(window: window)
        let published = await spy.settle(untilAtLeast: 1)

        #expect(published.isEmpty, "a 5xx was treated as a revocation")
    }
}

}
