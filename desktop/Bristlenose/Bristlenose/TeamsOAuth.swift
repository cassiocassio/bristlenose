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

/// What an Entra refusal actually means — and, more usefully, **who can do
/// something about it**. Three refusals arrive down the same channel with the
/// same shape, and they have nothing in common: one the researcher undoes by
/// clicking again, one only their IT can lift, and one nobody in the
/// conversation can lift at all.
///
/// A pure function over the code so the mapping is testable without an OAuth
/// round trip, per the house rule that a decision belongs in a helper rather
/// than in whatever view happens to render it.
enum MicrosoftSignInRefusal: Equatable {
    /// `AADSTS65004` — they read the consent screen and said no. Retrying is
    /// exactly right, and is the only one of these where it is.
    case userDeclined

    /// `AADSTS90094` / `AADSTS65001` — the tenant requires an administrator.
    ///
    /// **We cannot tell which of Entra's two walls they hit**, and it is worth
    /// stating rather than discovering later: with the admin-consent workflow
    /// enabled the user sees "Approval required" and a Request-approval button;
    /// with it disabled they see "Need admin approval" and no way to ask. Both
    /// return this same code — the difference lives on Microsoft's page, not in
    /// the callback. So one honest screen serves both, and it must not offer
    /// "Try again": useless in the first case, actively misleading in the
    /// second.
    case adminApprovalRequired

    /// `AADSTS53003` — Conditional Access. The sign-in **succeeded** and the
    /// token was refused anyway, usually because a policy demands a compliant or
    /// hybrid-joined device and a hand-rolled flow transmits no Primary Refresh
    /// Token for the device to be judged by. Not a consent problem, not a
    /// licence problem, and not fixable by the researcher, their admin, or us —
    /// so it earns its own case purely to stop it being described as one of the
    /// others.
    case conditionalAccess

    case other(description: String)

    /// Entra puts the `AADSTSnnnnn` code inside the human-readable description
    /// as often as it puts it in `error`, so both are searched.
    static func classify(code: String, description: String) -> Self {
        let haystack = code + " " + description
        // **Match the full `AADSTSnnnnn`, never the bare number.** Entra always
        // writes the prefix, and its descriptions also carry correlation IDs and
        // timestamps — so a bare `contains("65001")` can be satisfied by a digit
        // run in a GUID and classify an unrelated failure as an admin gate. The
        // cost of being wrong here is telling someone to go to their IT
        // department about something else entirely.
        if haystack.contains("AADSTS53003") { return .conditionalAccess }
        if haystack.contains("AADSTS90094") || haystack.contains("AADSTS65001") {
            return .adminApprovalRequired
        }
        if haystack.contains("AADSTS65004") { return .userDeclined }
        return .other(description: description)
    }

    /// The sentence to show, given whatever Microsoft said.
    ///
    /// **Two of these four keep Microsoft's own words**, and that is the rule
    /// rather than an omission: substituting our sentence for a message we do
    /// not specifically understand replaces a searchable, specific string with a
    /// vaguer one. We only override where we can say something Microsoft's text
    /// does not — namely *who can act*, which is the whole reason these are
    /// classified at all.
    ///
    /// Note `adminApprovalRequired` deliberately keeps the word
    /// **"administrator"**: it is what Entra's own screen says, and echoing the
    /// platform's vocabulary is what makes the message recognisable rather than
    /// merely accurate.
    func message(rawDescription: String) -> String {
        switch self {
        case .userDeclined:
            // Their words. "User declined to consent" is already precise, and
            // ours would be strictly less informative — but only when there are
            // any: passing the description straight through means an empty one
            // becomes an empty error, which surfaces as a dialog with a title
            // and no body.
            return rawDescription.isEmpty ? "Sign-in was declined." : rawDescription
        case .adminApprovalRequired:
            return "Your organisation needs an administrator to approve "
                 + "Bristlenose before it can read your recordings. Send your IT "
                 + "team the approval link — this isn't one you can grant yourself."
        case .conditionalAccess:
            return "Your organisation's security policy blocked this sign-in. "
                 + "This usually means it only allows managed devices, and it "
                 + "can't be resolved from Bristlenose."
        case .other(let description):
            return description.isEmpty
                ? "Microsoft declined the sign-in and didn't say why."
                : description
        }
    }

    /// Whether trying again could plausibly work. False for both of the walls —
    /// and getting this wrong is the difference between a researcher waiting for
    /// their admin and a researcher clicking a button forever.
    var isWorthRetrying: Bool { self == .userDeclined }
}

enum MicrosoftOAuthError: LocalizedError, Equatable {
    case notConfigured
    case cancelled
    case stateMismatch
    case noAuthorizationCode
    /// Microsoft returned an error on the authorize leg. See
    /// `MicrosoftSignInRefusal` for what the codes actually mean.
    case consentRefused(code: String, description: String)
    case tokenExchangeFailed(status: Int, body: String)

    /// The refusal behind this error, when it is one. Callers branch on this
    /// rather than re-matching strings.
    var refusal: MicrosoftSignInRefusal? {
        switch self {
        case .consentRefused(let code, let description):
            return .classify(code: code, description: description)
        case .tokenExchangeFailed(_, let body):
            // Conditional Access can refuse at the *token* leg too, after the
            // authorize leg has already succeeded — which is precisely why it
            // reads as "sign-in worked, then nothing did".
            let refusal = MicrosoftSignInRefusal.classify(code: "", description: body)
            return refusal == .conditionalAccess ? refusal : nil
        default:
            return nil
        }
    }

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
            return MicrosoftSignInRefusal
                .classify(code: code, description: description)
                .message(rawDescription: description)
        case .tokenExchangeFailed(let status, let body):
            if let refusal, refusal == .conditionalAccess {
                return refusal.message(rawDescription: body)
            }
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
