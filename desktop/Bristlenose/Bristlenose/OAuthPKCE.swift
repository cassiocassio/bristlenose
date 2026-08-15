import CryptoKit
import Foundation

// The token dance, as pure values. No networking, no UI, no Keychain — so every
// security-relevant decision here is unit-testable without an account, a tenant
// or a client ID.
//
// This exists partly to answer a design question with evidence rather than
// argument: docs/design-cloud-import.md §7 leaves "hand-roll PKCE vs adopt
// AppAuth" open. If the hand-rolled version is small, complete and fully
// covered, that is an argument for keeping it dependency-free. If it sprawls,
// that is an argument for the battle-tested library. Read the size before
// deciding.

// MARK: - PKCE

// PKCEPair and Data.base64URLEncodedString() are NOT declared here — they live
// in GoogleOAuth.swift and are shared. PKCE is RFC 7636, not a vendor thing, so
// both adapters use one implementation. That both sessions reached for it
// independently is the spine/adapter split (§7) asserting itself; when the
// spine is extracted properly, PKCE moves to a neutral file and both adapters
// keep importing it unchanged.

// MARK: - Authorization request

/// Everything needed to build one authorization URL, and the two secrets that
/// must survive until the callback comes back.
struct AuthorizationRequest {
    let clientID: String
    let redirectURI: String
    let scopes: [String]
    let pkce: PKCEPair
    /// Opaque anti-CSRF value. The callback is rejected unless it echoes this
    /// back exactly — without it, an attacker can feed us a code of their
    /// choosing and have us bind their account to this session.
    let state: String
    /// Microsoft's tenant segment. `common` accepts both work/school and
    /// personal accounts; `organizations` excludes personal.
    let tenant: String

    init(
        clientID: String,
        redirectURI: String,
        scopes: [String],
        tenant: String = "common",
        pkce: PKCEPair = PKCEPair(),
        state: String = PKCEPair.randomVerifier(byteCount: 24)
    ) {
        self.clientID = clientID
        self.redirectURI = redirectURI
        self.scopes = scopes
        self.tenant = tenant
        self.pkce = pkce
        self.state = state
    }

    var authorizationURL: URL? {
        var components = URLComponents(
            string: "https://login.microsoftonline.com/\(tenant)/oauth2/v2.0/authorize")
        components?.queryItems = [
            .init(name: "client_id", value: clientID),
            .init(name: "response_type", value: "code"),
            .init(name: "redirect_uri", value: redirectURI),
            .init(name: "response_mode", value: "query"),
            // offline_access is what yields a refresh token. Without it the
            // grant dies in an hour and every fetch re-prompts.
            .init(name: "scope", value: (scopes + ["offline_access"]).joined(separator: " ")),
            .init(name: "state", value: state),
            .init(name: "code_challenge", value: pkce.challenge),
            .init(name: "code_challenge_method", value: pkce.method),
        ]
        return components?.url
    }
}

// MARK: - Callback

enum AuthorizationCallback: Equatable {
    case success(code: String)
    /// The provider said no — user declined, admin approval needed, and so on.
    case failure(error: String, description: String?)
    /// The `state` did not match. Treated as its own case, never folded into
    /// `failure`, because this one means someone is interfering rather than
    /// that the user changed their mind.
    case stateMismatch
    /// Not a callback URL we recognise at all.
    case malformed

    /// Parses a redirect URL against the request that produced it.
    ///
    /// State is checked **first and unconditionally** — before the code is even
    /// read — so that no path exists where a mismatched state still yields a
    /// usable code.
    static func parse(url: URL, expecting request: AuthorizationRequest) -> AuthorizationCallback {
        guard let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems else {
            return .malformed
        }
        func value(_ name: String) -> String? {
            items.first { $0.name == name }?.value
        }

        guard let returnedState = value("state") else { return .malformed }
        guard constantTimeEquals(returnedState, request.state) else { return .stateMismatch }

        if let error = value("error") {
            return .failure(error: error, description: value("error_description"))
        }
        if let code = value("code"), !code.isEmpty {
            return .success(code: code)
        }
        return .malformed
    }

    /// Length-independent comparison. The timing risk on a locally-delivered
    /// callback is slight, but the cost of doing it properly is one loop.
    private static func constantTimeEquals(_ a: String, _ b: String) -> Bool {
        let lhs = Array(a.utf8), rhs = Array(b.utf8)
        guard lhs.count == rhs.count else { return false }
        var difference: UInt8 = 0
        for (x, y) in zip(lhs, rhs) { difference |= x ^ y }
        return difference == 0
    }
}

// MARK: - Token response

/// A Microsoft token endpoint response, with the one derived fact that matters.
/// Named for its provider because Google's equivalent has a different shape.
struct MicrosoftTokenResponse: Equatable {
    let accessToken: String
    /// Absent when the provider chose not to rotate it. Absence means "keep the
    /// one you have", never "you no longer have one" — discarding a refresh
    /// token because a response omitted it is how a session silently dies.
    let refreshToken: String?
    let expiresAt: Date

    private struct Payload: Decodable {
        let access_token: String
        let refresh_token: String?
        let expires_in: Double?
    }

    init?(data: Data, now: Date = Date()) {
        guard let payload = try? JSONDecoder().decode(Payload.self, from: data) else { return nil }
        self.accessToken = payload.access_token
        self.refreshToken = payload.refresh_token
        self.expiresAt = now.addingTimeInterval(payload.expires_in ?? 3600)
    }

    /// Deliberately conservative: a token is treated as stale a minute before it
    /// actually expires, so a long fetch cannot start on a token that dies
    /// mid-flight. Cheap insurance against the failure that would otherwise
    /// present as a mysterious 401 partway through a multi-gigabyte download.
    func isExpired(at moment: Date = Date(), leeway: TimeInterval = 60) -> Bool {
        moment.addingTimeInterval(leeway) >= expiresAt
    }
}
