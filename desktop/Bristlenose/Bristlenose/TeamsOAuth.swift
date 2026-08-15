import AuthenticationServices
import Foundation

// Microsoft OAuth for an installed app. The value types — the authorize URL,
// the callback parse with its constant-time state check, the token response —
// already exist in OAuthPKCE.swift; this is the network and UI half.
//
// Three ways Microsoft differs from the two adapters already built, each of
// which would be a bug if inherited by assumption:
//
//  1. **`offline_access` is what yields a refresh token.** Google returns one
//     to installed apps unconditionally and Zoom returns one always; Microsoft
//     returns none unless you ask, and the failure is delayed — the grant works
//     for an hour and then every fetch re-prompts.
//  2. **The tenant segment is part of the URL, not a parameter.** `common`
//     accepts work/school *and* personal accounts, which is the right choice
//     precisely because the personal case must be *diagnosed* rather than
//     excluded — see `DriveTier`, and §6's note that a personal account has no
//     `/Recordings` folder at all.
//  3. **A custom scheme is available here**, unlike Zoom. Azure's "Mobile and
//     desktop applications" platform accepts one, so §2's preferred mechanism
//     — `ASWebAuthenticationSession(url:callbackURLScheme:)`, whose callback
//     the OS routes to the initiating session alone — is usable. It needs a
//     `CFBundleURLTypes` entry the target does not have yet.

// MARK: - Scopes

enum MicrosoftScopes {
    /// The user's own files, delegated, **no admin consent** — verified, and
    /// the single property §5's whole sequencing rests on.
    static let filesRead = "Files.Read"

    /// The roster, and the calendar window the recordings join against.
    ///
    /// **`Calendars.Read`, never `Calendars.ReadBasic`.** The intuitive choice
    /// is the wrong one: `ReadBasic` returns `attendees[]` without bodies —
    /// better data minimisation — and **requires admin consent**, which would
    /// move Teams from no-gate to admin-gated and destroy the reason it goes
    /// first. Less privileged does not imply easier to consent. (Third time
    /// this trap has appeared across the three platforms; see also Google's
    /// `meetings.space.created` and Zoom's `:admin` suffixes.)
    static let calendarsRead = "Calendars.Read"

    /// Identity, for the attendee line's "drop yourself" rule and the domain
    /// externality is measured against.
    static let userRead = "User.Read"

    /// Without this Microsoft issues no refresh token at all.
    static let offlineAccess = "offline_access"

    static let requested = [filesRead, calendarsRead, userRead, offlineAccess]

    /// **Never requested.** Named here with its price so it reads as a decision
    /// rather than an oversight: `Files.Read.All` and `Sites.Read.All` have
    /// been admin-consent-only since Aug 2025, and that is the procurement gate
    /// the customer profile is defined by avoiding.
    static let refused = ["Files.Read.All", "Sites.Read.All"]
}

// MARK: - Configuration

struct MicrosoftOAuthConfig {
    let clientID: String
    /// `common` unless a cohort tenant needs pinning. Personal accounts are
    /// deliberately admitted so the adapter can *explain* them.
    let tenant: String
    let redirectURI: String

    var callbackScheme: String? {
        URLComponents(string: redirectURI)?.scheme
    }

    static let clientIDDefaultsKey = "MicrosoftOAuthClientID"
    static let redirectDefaultsKey = "MicrosoftOAuthRedirectURI"
    static let tenantDefaultsKey = "MicrosoftOAuthTenant"

    static func resolve(
        defaults: UserDefaults = .standard,
        bundle: Bundle = .main
    ) -> MicrosoftOAuthConfig? {
        func value(_ key: String) -> String? {
            for candidate in [defaults.string(forKey: key),
                              bundle.object(forInfoDictionaryKey: key) as? String] {
                guard let trimmed = candidate?.trimmingCharacters(in: .whitespacesAndNewlines),
                      !trimmed.isEmpty else { continue }
                return trimmed
            }
            return nil
        }
        guard let clientID = value(clientIDDefaultsKey) else { return nil }
        return MicrosoftOAuthConfig(
            clientID: clientID,
            tenant: value(tenantDefaultsKey) ?? "common",
            // Azure's own convention for a native client, and the one MSAL
            // registers, so a hand-rolled client stays compatible with an app
            // registration made the normal way.
            redirectURI: value(redirectDefaultsKey) ?? "msauth.app.bristlenose://auth"
        )
    }
}

enum MicrosoftOAuthError: LocalizedError, Equatable {
    case notConfigured
    case cancelled
    case stateMismatch
    case noAuthorizationCode
    /// Microsoft returned an error on the authorize leg. `AADSTS65004` is the
    /// user declining; `AADSTS90094` is the one that matters — the tenant
    /// requires an administrator to consent, which no amount of retrying fixes.
    case consentRefused(code: String, description: String)
    case tokenExchangeFailed(status: Int, body: String)

    var errorDescription: String? {
        switch self {
        case .notConfigured:
            return "Bristlenose hasn't been set up with a Microsoft client ID yet."
        case .cancelled:
            return "Sign-in was cancelled."
        case .stateMismatch:
            return "The sign-in response didn't match the request, so it was rejected."
        case .noAuthorizationCode:
            return "Microsoft didn't return an authorisation code."
        case .consentRefused(let code, let description):
            return code.contains("90094")
                ? "Your organisation requires an administrator to approve Bristlenose before you can connect."
                : description
        case .tokenExchangeFailed(let status, let body):
            return "Microsoft refused the sign-in (HTTP \(status)). \(body)"
        }
    }
}

// MARK: - The client

@MainActor
final class MicrosoftOAuthClient: NSObject {
    private let config: MicrosoftOAuthConfig
    private let session: URLSession
    private var authSession: ASWebAuthenticationSession?
    private weak var anchorWindow: NSWindow?

    init(config: MicrosoftOAuthConfig, session: URLSession = .shared, anchorWindow: NSWindow? = nil) {
        self.config = config
        self.session = session
        self.anchorWindow = anchorWindow
    }

    private var tokenEndpoint: URL {
        URL(string: "https://login.microsoftonline.com/\(config.tenant)/oauth2/v2.0/token")!
    }

    func signIn(scopes: [String] = MicrosoftScopes.requested) async throws -> MicrosoftTokenResponse {
        let request = AuthorizationRequest(
            clientID: config.clientID,
            redirectURI: config.redirectURI,
            scopes: scopes,
            tenant: config.tenant
        )
        guard let url = request.authorizationURL else { throw MicrosoftOAuthError.notConfigured }
        guard let scheme = config.callbackScheme else { throw MicrosoftOAuthError.notConfigured }

        let callbackURL = try await presentConsent(url: url, scheme: scheme)

        // The parse and its constant-time state comparison already exist as a
        // pure function — the reason they are testable at all.
        switch AuthorizationCallback.parse(url: callbackURL, expecting: request) {
        case .success(let code):
            return try await exchange(code: code, verifier: request.pkce.verifier)
        case .stateMismatch:
            throw MicrosoftOAuthError.stateMismatch
        case .failure(let error, let description):
            throw MicrosoftOAuthError.consentRefused(
                code: error,
                description: description ?? "Microsoft declined the sign-in."
            )
        case .malformed:
            throw MicrosoftOAuthError.noAuthorizationCode
        }
    }

    private func presentConsent(url: URL, scheme: String) async throws -> URL {
        try await withCheckedThrowingContinuation { continuation in
            let session = ASWebAuthenticationSession(
                url: url,
                // A custom scheme, which Microsoft permits and Zoom does not.
                // The OS routes this callback to the initiating session alone,
                // even if another app registers the same scheme — the security
                // property §2 prefers it for.
                callbackURLScheme: scheme
            ) { callbackURL, error in
                if let error {
                    let code = (error as? ASWebAuthenticationSessionError)?.code
                    continuation.resume(throwing: code == .canceledLogin
                                        ? MicrosoftOAuthError.cancelled
                                        : error)
                    return
                }
                guard let callbackURL else {
                    continuation.resume(throwing: MicrosoftOAuthError.noAuthorizationCode)
                    return
                }
                continuation.resume(returning: callbackURL)
            }
            session.presentationContextProvider = self
            // False so an already-signed-in researcher gets one-click consent
            // rather than a full MFA round trip — which on a work account is
            // not a small ask.
            session.prefersEphemeralWebBrowserSession = false
            self.authSession = session
            session.start()
        }
    }

    private func exchange(code: String, verifier: String) async throws -> MicrosoftTokenResponse {
        try await postForm([
            "client_id": config.clientID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirectURI,
            "code_verifier": verifier,
            // No client_secret: a public client is issued none, and shipping
            // one in a distributed binary would not make it a secret.
        ])
    }

    func refresh(refreshToken: String) async throws -> MicrosoftTokenResponse {
        try await postForm([
            "client_id": config.clientID,
            "grant_type": "refresh_token",
            "refresh_token": refreshToken,
            // Microsoft rotates refresh tokens too, but unlike Zoom it tolerates
            // brief reuse — so a failed persist is recoverable here rather than
            // stranding the account. Persist the new one anyway.
        ])
    }

    private func postForm(_ fields: [String: String]) async throws -> MicrosoftTokenResponse {
        var request = URLRequest(url: tokenEndpoint)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        var body = URLComponents()
        body.queryItems = fields.map { URLQueryItem(name: $0.key, value: $0.value) }
        request.httpBody = body.percentEncodedQuery?.data(using: .utf8)

        let (data, response) = try await session.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200...299).contains(status) else {
            throw MicrosoftOAuthError.tokenExchangeFailed(
                status: status,
                body: String(data: data, encoding: .utf8) ?? ""
            )
        }
        guard let decoded = MicrosoftTokenResponse(data: data) else {
            throw MicrosoftOAuthError.tokenExchangeFailed(status: status, body: "unreadable response")
        }
        return decoded
    }
}

extension MicrosoftOAuthClient: ASWebAuthenticationPresentationContextProviding {
    nonisolated func presentationAnchor(
        for session: ASWebAuthenticationSession
    ) -> ASPresentationAnchor {
        MainActor.assumeIsolated {
            anchorWindow ?? PanelHost.window ?? NSApp.windows.first ?? NSWindow()
        }
    }
}
