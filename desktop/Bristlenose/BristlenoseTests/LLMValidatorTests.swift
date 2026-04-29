import Foundation
import Testing

@testable import Bristlenose

/// Unit tests for `LLMValidator`'s pure functions and verdict cache.
///
/// **Aspirational reference** — `BristlenoseTests/` is not wired into the
/// Xcode target as of 29 Apr 2026 (see `desktop/CLAUDE.md` "Test target
/// setup"). This file compiles standalone and is ready to run the moment
/// the target line lands; until then it serves as documented intent for
/// what coverage looks like.
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

        let (s403, _) = LLMValidator.classify(provider: .openai, status: 403)
        #expect(s403 == .invalid)
    }

    @Test("402 maps to .unavailable with out-of-credits message that names the key as fine")
    func classifyOutOfCredits() {
        let (status, err) = LLMValidator.classify(provider: .claude, status: 402)
        #expect(status == .unavailable)
        // The whole point of a separate message: user sees orange, reads
        // "Your key is fine — top up", does NOT delete the key.
        #expect(err?.contains("out of credits") == true)
        #expect(err?.contains("Your key is fine") == true)
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
        let (status, _) = LLMValidator.classify(provider: .openai, status: 400)
        #expect(status == .unavailable)
    }

    @Test("5xx and other unknown codes map to .unavailable")
    func classifyServerError() {
        let (status, _) = LLMValidator.classify(provider: .claude, status: 500)
        #expect(status == .unavailable)
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
            LLMValidator.recordVerdict(provider: .openai, key: key, status: .invalid)
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == .ok)
            #expect(LLMValidator.cachedVerdict(provider: .openai, key: key) == .invalid)
        }
    }
}
