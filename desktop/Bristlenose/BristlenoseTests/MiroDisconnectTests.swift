import Foundation
import Testing

@testable import Bristlenose

// Disconnecting Miro, from either surface.
//
// There are two doors — the Send-to-Miro sheet and Settings ▸ Accounts — and
// one irreversible act behind them. They were two sequences until 18 Aug 2026,
// and the sheet's was missing its last step: `.bristlenosePrefsChanged`, which
// drains the parked sidecar and restarts the fronted one. Without that restart
// the Keychain is empty and the running serve is still authenticated, because
// `overlayMiroToken` baked `BRISTLENOSE_MIRO_ACCESS_TOKEN` into it at spawn and
// the server resolves the credential store before the in-memory session. The
// researcher is told they disconnected; exports keep working.
//
// These pin the sequence at the shared implementation and pin that the
// convenience entry point reaches the same one — the property that stops the
// two doors drifting apart again.

/// Captures a notification synchronously. `NotificationCenter.post` runs the
/// observer on the posting thread when the queue is nil, so a reference box is
/// enough — no polling, no expectation timeout.
private final class PostBox: @unchecked Sendable {
    var count = 0
}

// `.serialized` is load-bearing, not tidiness. Two of the three things under
// test are process-wide singletons — `NotificationCenter.default` and
// `UserDefaults.standard` — and Swift Testing runs a suite's tests in parallel
// by default, so siblings posted into each other's observers (`posts → 3`) and
// overwrote each other's identity default. Same shape as the `StubURLProtocol`
// note in desktop/CLAUDE.md. No other suite posts `.bristlenosePrefsChanged` or
// writes `miroConnectionIdentity`, so serialising here is sufficient; if one
// ever does, this suite is where it will show up first.
@Suite("Disconnecting Miro clears every copy", .serialized)
struct MiroDisconnectTests {

    /// Run `body` with an observer on `.bristlenosePrefsChanged`.
    private func countingPrefsChanged(
        _ body: () async -> Void
    ) async -> Int {
        let box = PostBox()
        let token = NotificationCenter.default.addObserver(
            forName: .bristlenosePrefsChanged, object: nil, queue: nil
        ) { _ in box.count += 1 }
        defer { NotificationCenter.default.removeObserver(token) }
        await body()
        return box.count
    }

    /// Seed a cached identity, run `body`, and report what the store held
    /// **before** the real default is put back.
    ///
    /// The read has to happen inside, not after: this restores the user's own
    /// value on the way out, so an assertion placed after the call reads the
    /// restored value and fails on production code that is behaving correctly.
    /// (It did — that was the first version of these tests.) The store reads
    /// `UserDefaults.standard` directly, so preserving is not optional; a test
    /// must not eat a real cached account line.
    private func identityAfter(_ body: () async -> Void) async -> String? {
        let key = "miroConnectionIdentity"
        let saved = UserDefaults.standard.string(forKey: key)
        UserDefaults.standard.set("Ada · Research", forKey: key)
        await body()
        let observed = MiroConnectionStore.identity
        if let saved { UserDefaults.standard.set(saved, forKey: key) }
        else { UserDefaults.standard.removeObject(forKey: key) }
        return observed
    }

    @Test("the Keychain copy, the cached identity, and the sidecar's baked env")
    func disconnectClearsAllThree() async {
        let store = InMemoryKeychain()
        store.set(provider: MiroConnectionStore.provider, value: "miro-tok-abc")
        #expect(MiroConnectionStore.isConnected(store: store),
                "precondition: a token is stored")

        var posts = 0
        let identity = await identityAfter {
            posts = await countingPrefsChanged {
                // api: nil — no serve running, so no HTTP call. The other three
                // steps are the ones under test.
                await MiroConnectionStore.disconnect(api: nil, store: store)
            }
        }

        #expect(!MiroConnectionStore.isConnected(store: store))
        #expect(identity == nil)
        #expect(posts == 1,
                "no prefs-changed post means the running sidecar keeps its baked token")
    }

    /// The property that keeps the two doors from drifting: the
    /// `(servePort:authToken:)` entry point Settings uses must reach the same
    /// implementation the sheet calls, not a parallel copy of the steps.
    @Test("the ServeManager-shaped entry point runs the same sequence")
    func convenienceEntryPointMatches() async {
        let store = InMemoryKeychain()
        store.set(provider: MiroConnectionStore.provider, value: "miro-tok-abc")

        var posts = 0
        let identity = await identityAfter {
            posts = await countingPrefsChanged {
                await MiroConnectionStore.disconnect(servePort: nil,
                                                     authToken: nil,
                                                     store: store)
            }
        }

        #expect(!MiroConnectionStore.isConnected(store: store))
        #expect(identity == nil)
        #expect(posts == 1)
    }

    /// Disconnecting with nothing stored must still restart the serve — the
    /// token that matters may exist only as the sidecar's baked env var, which
    /// no Keychain read can see.
    @Test("restarts the serve even when the Keychain is already empty")
    func postsEvenWithNothingStored() async {
        let store = InMemoryKeychain()
        #expect(!MiroConnectionStore.isConnected(store: store))

        var posts = 0
        _ = await identityAfter {
            posts = await countingPrefsChanged {
                await MiroConnectionStore.disconnect(api: nil, store: store)
            }
        }

        #expect(posts == 1)
    }
}
