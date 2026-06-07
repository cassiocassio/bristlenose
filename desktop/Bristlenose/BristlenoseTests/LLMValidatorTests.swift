import Foundation
import Testing

@testable import Bristlenose

/// Unit tests for `LLMValidator`'s pure functions and verdict cache.
@MainActor
@Suite("LLMValidator")
struct LLMValidatorTests {

    // MARK: - classify(provider:status:)

    @Test("2xx maps to .online with no error")
    func classifyOK() {
        let (status, err) = LLMValidator.classify(provider: .claude, status: 200)
        #expect(status == .online)
        #expect(err == nil)
    }

    @Test("401/403 maps to .invalid with key-rejected message")
    func classifyAuthFailure() {
        let (s401, e401) = LLMValidator.classify(provider: .claude, status: 401)
        #expect(s401 == .invalid)
        #expect(e401?.contains("rejected") == true)

        let (s403, _) = LLMValidator.classify(provider: .chatGPT, status: 403)
        #expect(s403 == .invalid)
    }

    @Test("402 maps to .outOfCredit (observed negative, not transient) with key-is-fine message")
    func classifyOutOfCredits() {
        let (status, err) = LLMValidator.classify(provider: .claude, status: 402)
        // .outOfCredit, NOT .unavailable: a 402 is an observed negative that
        // must show through (amber) rather than be masked by a cached green.
        #expect(status == .outOfCredit)
        // The invariant is the DISTINCTION, not the exact words: the 402 copy
        // must read differently from the 401 ("invalid key") copy so the user
        // tops up instead of deleting a good key. Asserting exact substrings on
        // user-facing copy reddens this test on any reword (prior Finding 21);
        // assert non-empty + differs-from-401 instead.
        let (_, invalidErr) = LLMValidator.classify(provider: .claude, status: 401)
        #expect(err?.isEmpty == false)
        #expect(err != invalidErr)
    }

    @Test("429 maps to .unavailable with rate-limit message naming the key as fine")
    func classifyRateLimit() {
        let (status, err) = LLMValidator.classify(provider: .claude, status: 429)
        #expect(status == .unavailable)
        #expect(err?.contains("rate-limited") == true)
        #expect(err?.contains("Your key is fine") == true)
    }

    @Test("Azure 404 maps to .invalid with endpoint-not-found message")
    func classifyAzure404() {
        let (status, err) = LLMValidator.classify(provider: .azure, status: 404)
        #expect(status == .invalid)
        #expect(err?.contains("endpoint or deployment not found") == true)
    }

    @Test("Anthropic 4xx other than auth/billing/rate-limit treated as .online (forward-compat)")
    func classifyAnthropicForwardCompat() {
        // The hardcoded haiku model getting deprecated would 4xx but auth
        // succeeded — the validator should keep working.
        for code in [400, 404, 422] {
            let (status, _) = LLMValidator.classify(provider: .claude, status: code)
            #expect(status == .online, "Anthropic \(code) should map to .online")
        }
    }

    @Test("OpenAI 400 does NOT get the Anthropic forward-compat path")
    func classifyOpenAINotAffected() {
        // The forward-compat is Anthropic-only because Anthropic has no
        // free auth-check endpoint. OpenAI uses GET /v1/models which
        // doesn't have the model-deprecation risk.
        let (status, _) = LLMValidator.classify(provider: .chatGPT, status: 400)
        #expect(status == .unavailable)
    }

    @Test("5xx and other unknown codes map to .unavailable")
    func classifyServerError() {
        let (status, _) = LLMValidator.classify(provider: .claude, status: 500)
        #expect(status == .unavailable)
    }

    // MARK: - resolveStatus (the cache-promotion / 402-masking decision)
    //
    // This is the actual masking site (the Settings view delegates to it), so
    // it's tested directly rather than only through the cache round-trip.

    @Test("resolveStatus: transient .unavailable defers to a cached verdict (offline survival)")
    func resolveTransientDefersToCache() {
        #expect(LLMValidator.resolveStatus(observed: .unavailable, cached: .ok) == .online)
        #expect(LLMValidator.resolveStatus(observed: .unavailable, cached: .invalid) == .invalid)
        #expect(LLMValidator.resolveStatus(observed: .unavailable, cached: .outOfCredit) == .outOfCredit)
    }

    @Test("resolveStatus: transient .unavailable with NO cache shows .unavailable")
    func resolveTransientNoCache() {
        #expect(LLMValidator.resolveStatus(observed: .unavailable, cached: nil) == .unavailable)
    }

    @Test("resolveStatus: a fresh .outOfCredit (402) is NOT masked by a cached .ok")
    func resolveOutOfCreditNotMasked() {
        // The anti-masking invariant the whole branch exists for: an observed
        // 402 shows amber even when the cache still says the key was good.
        #expect(LLMValidator.resolveStatus(observed: .outOfCredit, cached: .ok) == .outOfCredit)
    }

    @Test("resolveStatus: a fresh .invalid (401) is NOT masked by a cached .ok")
    func resolveInvalidNotMasked() {
        #expect(LLMValidator.resolveStatus(observed: .invalid, cached: .ok) == .invalid)
    }

    @Test("resolveStatus: a definitive .online wins over any cache")
    func resolveOnlineWins() {
        #expect(LLMValidator.resolveStatus(observed: .online, cached: .invalid) == .online)
    }

    @Test("resolveStatus: an observed .outOfCredit is unchanged by any cache (incl. stale .outOfCredit)")
    func resolveOutOfCreditStableUnderCache() {
        // Double-amber: re-observing 402 while the cache already holds
        // .outOfCredit is a no-op, never a promotion to something greener.
        #expect(LLMValidator.resolveStatus(observed: .outOfCredit, cached: .outOfCredit) == .outOfCredit)
        #expect(LLMValidator.resolveStatus(observed: .outOfCredit, cached: .invalid) == .outOfCredit)
        #expect(LLMValidator.resolveStatus(observed: .outOfCredit, cached: nil) == .outOfCredit)
    }

    @Test("resolveStatus: only .unavailable defers to cache — .checking/.notSetUp pass through")
    func resolveNonTransientPassThrough() {
        // Contract pin: resolveStatus keys on observed == .unavailable. Should
        // validate() ever return .checking/.notSetUp as an observed value with
        // a cache present, it must pass through unchanged — under-report, never
        // mask a worse reality as green. Unreachable today; pinned so a future
        // validate() return value can't silently break the anti-masking rule.
        #expect(LLMValidator.resolveStatus(observed: .checking, cached: .ok) == .checking)
        #expect(LLMValidator.resolveStatus(observed: .notSetUp, cached: .ok) == .notSetUp)
    }

    // MARK: - Shell command extraction (copyable CLI help)

    @Test("shellCommands extracts backtick commands; empty for plain messages")
    func shellCommandsExtraction() {
        #expect(LLMValidator.shellCommands(
            in: "Run `ollama pull llama3.2:3b` to add one.") == ["ollama pull llama3.2:3b"])
        #expect(LLMValidator.shellCommands(
            in: "Start it with `ollama serve` or open the Ollama app.") == ["ollama serve"])
        #expect(LLMValidator.shellCommands(
            in: "Claude rejected this key (401).") == [])
        #expect(LLMValidator.shellCommands(
            in: "No network connection. Your key was fine — we just can't check it right now.") == [])
    }

    // MARK: - Verdict cache round-trip

    /// Each cache test gets its own UserDefaults suite so they don't share
    /// state. Resets `verdictStore` to `.standard` after each test runs.
    private func withIsolatedStore(_ body: () -> Void) {
        let suiteName = "LLMValidatorTests-\(UUID().uuidString)"
        let suite = UserDefaults(suiteName: suiteName)!
        let original = LLMValidator.verdictStore
        LLMValidator.verdictStore = suite
        defer {
            LLMValidator.verdictStore = original
            suite.removePersistentDomain(forName: suiteName)
        }
        body()
    }

    @Test(".online verdict round-trips through cache")
    func cacheRoundTripOnline() {
        withIsolatedStore {
            let key = "sk-ant-test-key-1234567890"
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .online)
            let cached = LLMValidator.cachedVerdict(provider: .claude, key: key)
            #expect(cached == .ok)
        }
    }

    @Test(".invalid verdict round-trips through cache")
    func cacheRoundTripInvalid() {
        withIsolatedStore {
            let key = "sk-ant-bad-key"
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .invalid)
            let cached = LLMValidator.cachedVerdict(provider: .claude, key: key)
            #expect(cached == .invalid)
        }
    }

    @Test("Transient statuses do NOT overwrite a cached verdict")
    func cacheTransientNoOverwrite() {
        withIsolatedStore {
            let key = "sk-ant-rotation-test"
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .online)
            // .unavailable from a network failure must not replace the .ok.
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .unavailable)
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == .ok)
            // Same for .checking, .notSetUp.
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .checking)
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .notSetUp)
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == .ok)
        }
    }

    @Test("Definitive verdict overwrites prior verdict")
    func cacheDefinitiveOverwrite() {
        withIsolatedStore {
            let key = "sk-ant-rotated-test"
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .online)
            // Network round-trip on a now-rotated key returns 401 → .invalid.
            // That IS authoritative and should replace the cache.
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .invalid)
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == .invalid)
        }
    }

    @Test(".outOfCredit verdict round-trips through cache (sticky)")
    func cacheRoundTripOutOfCredit() {
        withIsolatedStore {
            let key = "sk-ant-broke-account"
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .outOfCredit)
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == .outOfCredit)
        }
    }

    @Test("402-then-transient does NOT re-green: cached .outOfCredit survives a later .unavailable")
    func cacheOutOfCreditStickyUnderTransient() {
        withIsolatedStore {
            let key = "sk-ant-ran-dry"
            // Was good, then ran out of credit.
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .online)
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .outOfCredit)
            // Then the network drops. A transient .unavailable must NOT overwrite
            // the sticky out-of-credit verdict, so the offline fallback resolves
            // to amber, not stale green. (Finding 2: 402-then-timeout re-green.)
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .unavailable)
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == .outOfCredit)
        }
    }

    @Test("Top-up clears it: a fresh .online overwrites a cached .outOfCredit")
    func cacheTopUpClearsOutOfCredit() {
        withIsolatedStore {
            let key = "sk-ant-topped-up"
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .outOfCredit)
            // User tops up; next validation returns 200 → .online. Authoritative,
            // so it replaces the amber verdict.
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .online)
            // `.ok` is the CachedVerdict *representation* of an .online
            // observation (cache layer), not the rendered ProviderStatus.
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == .ok)
        }
    }

    @Test("Different key → cache miss (hash mismatch)")
    func cacheHashMismatch() {
        withIsolatedStore {
            LLMValidator.recordVerdict(provider: .claude, key: "key-A", status: .online)
            // Looking up a different key under the same provider returns nil.
            let cached = LLMValidator.cachedVerdict(provider: .claude, key: "key-B")
            #expect(cached == nil)
        }
    }

    @Test("clearCache wipes all three keys (hash, verdict, timestamp)")
    func cacheClear() {
        withIsolatedStore {
            let key = "sk-ant-clear-test"
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .online)
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == .ok)

            LLMValidator.clearCache(provider: .claude)
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == nil)
            #expect(LLMValidator.cachedEntry(provider: .claude, key: key) == nil)
        }
    }

    @Test("cacheIsFresh respects TTL")
    func cacheTTL() {
        withIsolatedStore {
            let key = "sk-ant-ttl-test"
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .online)
            // Just-recorded — fresh under any plausible TTL.
            #expect(LLMValidator.cacheIsFresh(provider: .claude, key: key, ttl: 60))
            // 0s TTL → never fresh.
            #expect(!LLMValidator.cacheIsFresh(provider: .claude, key: key, ttl: 0))
        }
    }

    @Test("Empty key returns nil from cachedVerdict")
    func cacheEmptyKey() {
        withIsolatedStore {
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: "") == nil)
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: "   ") == nil)
        }
    }

    @Test("Per-provider cache isolation")
    func cachePerProvider() {
        withIsolatedStore {
            let key = "shared-string"
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .online)
            LLMValidator.recordVerdict(provider: .chatGPT, key: key, status: .invalid)
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == .ok)
            #expect(LLMValidator.cachedVerdict(provider: .chatGPT, key: key) == .invalid)
        }
    }
}
