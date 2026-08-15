import Foundation
import Testing

@testable import Bristlenose

@Suite("PKCE")
struct PKCETests {

    /// The worked example from RFC 7636 Appendix B. If this passes, the
    /// challenge derivation is correct against the spec rather than against our
    /// own assumptions about it.
    @Test("Matches the RFC 7636 reference vector")
    func rfcVector() {
        let pair = PKCEPair(verifier: "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")
        #expect(pair.challenge == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")
    }

    @Test("Only S256 is offered")
    func neverPlain() {
        // `plain` is spec-legal and useless: the challenge is the verifier, so
        // anyone who can see the browser request can complete the exchange.
        #expect(PKCEPair().method == "S256")
    }

    @Test("Generated verifiers are URL-safe and long enough for the spec")
    func verifierShape() {
        let pair = PKCEPair()
        #expect(pair.verifier.count >= 43, "RFC 7636 sets 43 characters as the minimum")
        #expect(pair.verifier.count <= 128)
        #expect(!pair.verifier.contains("+"))
        #expect(!pair.verifier.contains("/"))
        #expect(!pair.verifier.contains("="), "base64url is unpadded")
    }

    @Test("Every pair is fresh")
    func freshEveryTime() {
        // A reused verifier across attempts collapses PKCE back to a static
        // secret, which is the thing it exists to replace.
        let pairs = (0..<64).map { _ in PKCEPair().verifier }
        #expect(Set(pairs).count == pairs.count)
    }
}

@Suite("Authorization request")
struct AuthorizationRequestTests {

    private func request() -> AuthorizationRequest {
        AuthorizationRequest(
            clientID: "test-client",
            redirectURI: "bristlenose://auth",
            scopes: ["Files.Read", "Calendars.Read"],
            pkce: PKCEPair(verifier: "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"),
            state: "fixed-state-for-test")
    }

    private func query(_ url: URL) -> [String: String] {
        let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        return Dictionary(uniqueKeysWithValues: items.compactMap { item in
            item.value.map { (item.name, $0) }
        })
    }

    @Test("Carries every parameter the flow requires")
    func requiredParameters() throws {
        let url = try #require(request().authorizationURL)
        let q = query(url)
        #expect(q["client_id"] == "test-client")
        #expect(q["response_type"] == "code")
        #expect(q["redirect_uri"] == "bristlenose://auth")
        #expect(q["code_challenge"] == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")
        #expect(q["code_challenge_method"] == "S256")
        #expect(q["state"] == "fixed-state-for-test")
    }

    /// Without `offline_access` there is no refresh token, the grant dies in an
    /// hour, and every fetch re-prompts — which would look like a bug in us.
    @Test("offline_access is always requested")
    func offlineAccessAlwaysPresent() throws {
        let url = try #require(request().authorizationURL)
        let scope = try #require(query(url)["scope"])
        #expect(scope.contains("offline_access"))
        #expect(scope.contains("Files.Read"))
        #expect(scope.contains("Calendars.Read"))
    }

    /// The verifier must never travel in the browser — only its digest does.
    @Test("The verifier never appears in the URL")
    func verifierNeverLeaves() throws {
        let req = request()
        let url = try #require(req.authorizationURL)
        #expect(!url.absoluteString.contains(req.pkce.verifier))
    }

    @Test("Defaults to the tenant that accepts both account types")
    func defaultTenant() throws {
        let url = try #require(request().authorizationURL)
        #expect(url.absoluteString.contains("/common/"))
    }
}

@Suite("Authorization callback")
struct AuthorizationCallbackTests {

    private let request = AuthorizationRequest(
        clientID: "c", redirectURI: "bristlenose://auth", scopes: ["Files.Read"],
        pkce: PKCEPair(verifier: "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"),
        state: "the-expected-state")

    private func parse(_ string: String) -> AuthorizationCallback {
        AuthorizationCallback.parse(url: URL(string: string)!, expecting: request)
    }

    @Test("A well-formed callback yields the code")
    func success() {
        #expect(parse("bristlenose://auth?code=abc123&state=the-expected-state")
            == .success(code: "abc123"))
    }

    /// The security-critical one. A mismatched state means someone is
    /// interfering — feeding us a code of their choosing to bind their account
    /// to this session — so it gets its own case and is never mistaken for the
    /// user simply declining.
    @Test("A mismatched state is rejected and is its own outcome")
    func stateMismatchRejected() {
        #expect(parse("bristlenose://auth?code=abc123&state=attacker-state") == .stateMismatch)
    }

    /// State is validated *before* the code is read, so no path exists where a
    /// bad state still hands back something usable.
    @Test("State is checked ahead of everything else")
    func stateCheckedFirst() {
        // Both an error and a code present, but the state is wrong: the answer
        // is still stateMismatch, not the error and not the code.
        #expect(parse("bristlenose://auth?error=access_denied&code=x&state=wrong")
            == .stateMismatch)
    }

    @Test("A provider refusal carries its reason through")
    func providerError() {
        let outcome = parse(
            "bristlenose://auth?error=access_denied&error_description=Need%20admin%20approval&state=the-expected-state")
        #expect(outcome == .failure(error: "access_denied", description: "Need admin approval"))
    }

    @Test("Missing pieces are malformed rather than silently accepted")
    func malformed() {
        #expect(parse("bristlenose://auth?code=abc123") == .malformed, "no state at all")
        #expect(parse("bristlenose://auth?state=the-expected-state") == .malformed, "no code")
        #expect(parse("bristlenose://auth?code=&state=the-expected-state") == .malformed)
    }
}

@Suite("Microsoft token response")
struct TokenResponseTests {

    private let now = Date(timeIntervalSince1970: 1_000_000)

    @Test("Parses a normal response")
    func parses() throws {
        let json = Data(#"{"access_token":"at","refresh_token":"rt","expires_in":3599}"#.utf8)
        let token = try #require(MicrosoftTokenResponse(data: json, now: now))
        #expect(token.accessToken == "at")
        #expect(token.refreshToken == "rt")
        #expect(token.expiresAt == now.addingTimeInterval(3599))
    }

    /// Absence means "keep the one you have", never "you no longer have one".
    /// Discarding a refresh token because a response omitted it is how a session
    /// silently dies days later.
    @Test("An omitted refresh token is absence, not revocation")
    func refreshTokenMayBeAbsent() throws {
        let json = Data(#"{"access_token":"at","expires_in":3599}"#.utf8)
        let token = try #require(MicrosoftTokenResponse(data: json, now: now))
        #expect(token.refreshToken == nil)
    }

    /// Deliberately conservative: a long download must not begin on a token that
    /// dies mid-flight, because that presents as a mysterious 401 partway
    /// through several gigabytes.
    @Test("A token about to expire is already treated as expired")
    func leewayIsConservative() throws {
        let json = Data(#"{"access_token":"at","expires_in":3600}"#.utf8)
        let token = try #require(MicrosoftTokenResponse(data: json, now: now))
        #expect(!token.isExpired(at: now))
        #expect(token.isExpired(at: now.addingTimeInterval(3600 - 30)),
                "inside the leeway window, so treated as stale")
        #expect(token.isExpired(at: now.addingTimeInterval(3600)))
    }

    @Test("A malformed body does not produce a half-built token")
    func malformedBody() {
        #expect(MicrosoftTokenResponse(data: Data("not json".utf8)) == nil)
        #expect(MicrosoftTokenResponse(data: Data(#"{"refresh_token":"rt"}"#.utf8)) == nil,
                "no access token means no usable response")
    }
}
