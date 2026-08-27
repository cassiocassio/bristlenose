import AuthenticationServices
import Foundation

// Zoom OAuth for an installed app: authorization code + PKCE against a **public
// client**, no secret, no server.
//
// Measured against Zoom's own docs, verified 15 Aug 2026. Four things differ
// from the Google adapter in ways that would be bugs if inherited by assumption:
//
//  1. **The redirect cannot be a custom scheme.** Zoom's build flow accepts
//     custom URL schemes only for Meeting SDK apps — a plain General App gets
//     "Wrong URL format" in the field and `errorCode 4700` from the server. So
//     this uses an **HTTPS callback with Associated Domains**, which needs a
//     static `apple-app-site-association` file on a domain we own. Static
//     hosting, not a server; §2's "no server needed" survives.
//
//     **Loopback is NOT the missing cheap alternative, though Zoom now allows
//     it.** This comment used to say loopback was unsupported; Zoom's docs
//     today permit `http://127.0.0.1:{port}/{path}` for PKCE clients (not
//     `localhost`, and matched ignoring only the port). It is still the wrong
//     door, for reasons that have nothing to do with Zoom:
//     `ASWebAuthenticationSession` takes a custom scheme or `.https(host:path:)`
//     and nothing else, so loopback means giving up the ephemeral in-app
//     session for a browser handoff plus a local listener — which under App
//     Sandbox needs `com.apple.security.network.server`, is reachable by any
//     local process, and is a worse answer to the code-interception threat PKCE
//     only mitigates.
//
//     And the entitlement is load-bearing rather than ceremonial:
//     `presentConsent` below checks only that the redirect is `https://` with a
//     host, so **the Associated Domains list is the only thing** preventing a
//     tampered `ZoomOAuthRedirectURI` default from sending the callback to
//     someone else's host. Do not remove it as dead weight.
//  2. **Refresh tokens are single-use and rotate on every refresh**, with no
//     documented grace window. Google tolerates brief reuse; Zoom does not. A
//     refresh that times out *after* Zoom rotated but *before* we persisted
//     strands the user with no recovery but full re-authorisation. See
//     `refresh(_:)`.
//  3. **Re-authorisation always shows the consent screen.** Zoom: "The OAuth
//     consent page must always be displayed for public clients that do not use
//     a client secret" (RFC 6819 §5.2.3.2). Silent *refresh* is fine; silent
//     re-auth is not. So a UI that treats a consent screen as an error, or
//     tries to hide re-auth, will fight the protocol.
//  4. **One live token per user per client ID.** Authorising on a second Mac
//     appears to invalidate the first. Not something this file can fix — it is
//     a product constraint — but it is why `invalid_token` must route to a
//     graceful reconnect rather than to an error state.
//
// PKCE itself is shared: `PKCEPair` lives in OAuthShared.swift, because RFC
// 7636 is not a vendor thing. That both the Teams and Google sessions reached
// for the same implementation is the spine asserting itself.

// MARK: - Scopes

/// Zoom's granular scopes (the 2024 replacement for `recording:read`).
///
/// Classic scopes still work but new apps get granular by default, so this is
/// not a choice we have to make — only one we must spell correctly.
enum ZoomScopes {
    /// List the signed-in user's own cloud recordings.
    ///
    /// The bare form, deliberately: the `:admin` and `:master` variants are for
    /// account-level and partner apps, and asking for one would move this from
    /// a user-managed app any researcher can add themselves to an
    /// admin-managed app requiring an account role — the same "narrower-sounding
    /// scope is the wrong scope" trap that `Calendars.ReadBasic` and
    /// `meetings.space.created` already sprang on this design, third time.
    static let listUserRecordings = "cloud_recording:read:list_user_recordings"

    /// Per-meeting recording files.
    static let listRecordingFiles = "cloud_recording:read:list_recording_files"

    /// **There is no download scope, and that is not an omission.** The list
    /// response carries `download_url`, and the same bearer token authorises
    /// the fetch. Good news at review time, where Zoom asks you to justify
    /// every scope and removes ones it considers unused.
    static let requested = [listUserRecordings, listRecordingFiles]
}

// MARK: - Configuration

/// Where Zoom's public client ID and HTTPS callback come from.
///
/// Two values rather than Google's one, because Zoom does not derive the
/// redirect from the client ID — it is whatever you registered in the app's
/// OAuth allow list, and it must match exactly (Zoom offers a "Strict Mode URL"
/// setting that enforces exact match).
struct ZoomOAuthConfig {
    /// The **public** client ID — the one issued by App Credentials ▸ "Use
    /// Public Client OAuth", not the confidential one that comes with a secret.
    /// Using the confidential ID here fails at the token exchange, where Zoom
    /// expects a secret we deliberately do not ship.
    let publicClientID: String

    /// An HTTPS URL on a domain we control, registered in Zoom's allow list and
    /// backed by an `apple-app-site-association` file so the OS routes it back
    /// to this app rather than opening a browser tab.
    let redirectURI: String

    /// The host and path `ASWebAuthenticationSession` matches on. Derived from
    /// `redirectURI` so the two cannot drift — a mismatch here produces a
    /// session that never calls back and no error at all, which is the worst
    /// failure shape available.
    var callbackHost: String? { URLComponents(string: redirectURI)?.host }
    var callbackPath: String? { URLComponents(string: redirectURI)?.path }

    static let clientIDDefaultsKey = "ZoomOAuthPublicClientID"
    static let redirectDefaultsKey = "ZoomOAuthRedirectURI"

    static func resolve(
        defaults: UserDefaults = .standard,
        bundle: Bundle = .main
    ) -> ZoomOAuthConfig? {
        func value(_ key: String) -> String? {
            let candidates = [
                defaults.string(forKey: key),
                bundle.object(forInfoDictionaryKey: key) as? String,
            ]
            for candidate in candidates {
                guard let trimmed = candidate?.trimmingCharacters(in: .whitespacesAndNewlines),
                      !trimmed.isEmpty
                else { continue }
                return trimmed
            }
            return nil
        }
        guard let clientID = value(clientIDDefaultsKey),
              let redirect = value(redirectDefaultsKey)
        else { return nil }
        return ZoomOAuthConfig(publicClientID: clientID, redirectURI: redirect)
    }
}

// MARK: - Errors

enum ZoomOAuthError: LocalizedError, Equatable {
    case notConfigured
    case cancelled
    case stateMismatch
    case noAuthorizationCode
    /// Zoom returned `?error=` on the callback — a scope it would not grant, a
    /// misconfigured redirect, an app not enabled for this account. Declining
    /// is *not* here: that arrives as `access_denied` and becomes `.cancelled`,
    /// because it is the researcher's own choice rather than a fault.
    case authorizationRefused(error: String, description: String?)
    /// The token response carried no refresh token on a **first** sign-in.
    ///
    /// Separate from `.refreshRejected`, which shares the same guard inside
    /// `postForm`: on the sign-in path that case would tell a researcher their
    /// connection had *expired* seconds after making it, and send them round a
    /// loop that cannot terminate. This one names the real cause, which is
    /// always the Marketplace app's own configuration.
    case noRefreshTokenIssued
    /// The callback URL could not be matched — almost always a redirect that
    /// isn't HTTPS, or one whose host lacks an Associated Domains entry.
    case unusableCallback(String)
    case tokenExchangeFailed(status: Int, body: String)
    /// The refresh token was rejected. Distinct from a generic failure because
    /// its remedy is specific and unavoidable: full re-authorisation, consent
    /// screen included.
    case refreshRejected
    /// Zoom rotated the token and we could not store the replacement.
    ///
    /// **Not a refusal, and the difference decides whether an account
    /// survives.** `refreshRejected` means Zoom said no and the grant is dead;
    /// this means Zoom said yes, spent the old token, and *we* dropped the new
    /// one. The stored grant is now stale rather than revoked, so the caller
    /// must keep it and let the next attempt re-authorise — tombstoning here
    /// would turn a full disk into a revocation.
    ///
    /// **It carries the live tokens, and that is the point.** The refresh
    /// genuinely succeeded: this pair works right now and is the only pair that
    /// does. Throwing it away would break the running session *and* leave the
    /// stored token dead, which is strictly worse than every alternative — so
    /// the caller adopts these and treats the failure as a loss of durability
    /// rather than of access. That distinction matters most on an ad-hoc-signed
    /// build, where `errSecMissingEntitlement` on every Keychain write is the
    /// documented ordinary state: discarding here would make Zoom unusable on
    /// exactly the builds this project develops against, while Teams and Meet
    /// degrade to one extra sign-in next launch.
    case rotationNotPersisted(ZoomTokens)

    var errorDescription: String? {
        switch self {
        case .notConfigured:
            return "Bristlenose hasn't been set up with a Zoom client ID yet."
        case .cancelled:
            return "Sign-in was cancelled."
        case .stateMismatch:
            return "The sign-in response didn't match the request, so it was rejected."
        case .noAuthorizationCode:
            return "Zoom didn't return an authorisation code."
        case .authorizationRefused(let error, let description):
            // Zoom's own `error_description` where there is one — these are
            // short, human-written strings from the authorize endpoint, not the
            // unbounded response bodies `tokenExchangeFailed` deliberately
            // drops.
            return description.map { "Zoom refused the sign-in: \($0)" }
                ?? "Zoom refused the sign-in (\(error))."
        case .noRefreshTokenIssued:
            return "Zoom signed you in but didn't issue a token Bristlenose can keep, "
                + "so the connection can't be saved."
        case .unusableCallback(let detail):
            return "Zoom's sign-in couldn't return to Bristlenose (\(detail))."
        case .tokenExchangeFailed(let status, _):
            // **The body is deliberately dropped, not truncated.** This string
            // reaches the window through `CloudImportStore`'s `.failed` phase,
            // and the body is an unbounded provider response — Zoom's OAuth
            // errors are terse JSON this quarter, which is a fact about this
            // quarter rather than a contract. Provider error bodies routinely
            // echo request fragments, and on the refresh path the request body
            // *is* a refresh token. `SECURITY.md` already forbids exactly this
            // shape on the Python side. The status carries the diagnostic
            // value; the body is available in the case for a caller that logs
            // it privately.
            return "Zoom refused the sign-in (HTTP \(status))."
        case .refreshRejected:
            return "Your Zoom connection expired. Signing in again will restore it."
        case .rotationNotPersisted:
            return "Bristlenose renewed your Zoom connection but couldn't save it, "
                + "so you may need to sign in again next time."
        }
    }
}

// MARK: - Tokens

struct ZoomTokens: Codable, Equatable, Sendable {
    let accessToken: String
    /// **Single-use.** Persist the replacement before discarding this one.
    ///
    /// It also has an outer clock the access token does not: Zoom's docs say
    /// *"Refresh tokens expire after 90 days."* Rotation resets it, so the only
    /// account this reaches is one nobody has imported from in three months —
    /// and that account is handled correctly already, by one refused POST that
    /// becomes `.refreshRejected` and then a tombstone the researcher can sign
    /// back into. Recorded here rather than pre-empted with an expiry check: a
    /// local clock that decides a credential is dead without asking is a new way
    /// to be wrong about a token that would have worked.
    let refreshToken: String
    let expiresAt: Date
    let scopes: [String]

    var isExpired: Bool { Date() >= expiresAt.addingTimeInterval(-60) }
}

private struct ZoomTokenResponse: Decodable {
    let access_token: String
    let refresh_token: String?
    let expires_in: Int?
    let scope: String?
}

// MARK: - The client

@MainActor
final class ZoomOAuthClient: NSObject {
    static let authorizeEndpoint = URL(string: "https://zoom.us/oauth/authorize")!
    static let tokenEndpoint = URL(string: "https://zoom.us/oauth/token")!
    static let revokeEndpoint = URL(string: "https://zoom.us/oauth/revoke")!

    private let config: ZoomOAuthConfig
    private let session: URLSession
    private var authSession: ASWebAuthenticationSession?
    private weak var anchorWindow: NSWindow?

    /// Persists a rotated refresh token. Injected rather than reached for, so
    /// the rotation contract is testable without a Keychain.
    ///
    /// **`async`, so that awaiting it is what enforces the ordering** — the
    /// write completes before `refresh(_:)` returns, without a synchronous
    /// Keychain call on the main actor. That call can block on an authorisation
    /// prompt, which on an ad-hoc-signed build is routine rather than
    /// hypothetical, and stalling the main actor is precisely what
    /// `CloudGrantWriter` was built to avoid.
    ///
    /// The default is a no-op, which means *nobody asked for persistence* — a
    /// transport test, or an adapter with no store behind it. That is different
    /// from a wired sink that failed, and `refresh(_:)` treats them differently:
    /// the first rotates in memory, the second is fatal.
    private let persist: @Sendable (ZoomTokens) async throws -> Void

    init(
        config: ZoomOAuthConfig,
        session: URLSession = .shared,
        anchorWindow: NSWindow? = nil,
        persist: @escaping @Sendable (ZoomTokens) async throws -> Void = { _ in }
    ) {
        self.config = config
        self.session = session
        self.anchorWindow = anchorWindow
        self.persist = persist
    }

    func signIn(scopes: [String] = ZoomScopes.requested) async throws -> ZoomTokens {
        let pkce = PKCEPair()
        let state = PKCEPair.randomVerifier(byteCount: 16)

        var components = URLComponents(url: Self.authorizeEndpoint, resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "response_type", value: "code"),
            // The PUBLIC client ID. The confidential one fails at the exchange,
            // where Zoom expects a secret this app deliberately does not ship.
            URLQueryItem(name: "client_id", value: config.publicClientID),
            URLQueryItem(name: "redirect_uri", value: config.redirectURI),
            URLQueryItem(name: "scope", value: scopes.joined(separator: " ")),
            URLQueryItem(name: "code_challenge", value: pkce.challenge),
            // Always explicit. Zoom's doc: the method "defaults to `plain` if
            // not present" — a silent downgrade to no protection at all.
            URLQueryItem(name: "code_challenge_method", value: "S256"),
            URLQueryItem(name: "state", value: state),
        ]

        let callbackURL = try await presentConsent(url: components.url!)
        guard let returned = URLComponents(url: callbackURL, resolvingAgainstBaseURL: false) else {
            throw ZoomOAuthError.noAuthorizationCode
        }
        let items = returned.queryItems ?? []
        guard let returnedState = items.first(where: { $0.name == "state" })?.value,
              OAuthCompare.constantTimeEquals(returnedState, state)
        else { throw ZoomOAuthError.stateMismatch }
        // **`error` before `code`, and it has to be.** An OAuth callback that
        // carries `?error=access_denied` has no `code` at all, so reading for
        // the code first reports the user's own decision — Decline on Zoom's
        // consent screen — as *"Zoom didn't return an authorisation code"*, a
        // wire fault for a routine act. `access_denied` is the declined case
        // and reuses the cancelled copy; anything else keeps Zoom's own words,
        // which is the only thing that will distinguish a scope problem from a
        // configuration one in a cohort tester's screenshot.
        //
        // Note this does **not** cover the Marketplace pre-approval wall: that
        // is enforced on Zoom's consent page before any redirect, so no
        // callback of any kind arrives and the session simply ends
        // (`CloudPlatform.signInMayAwaitAdminApproval` is what the UI reads for
        // that one).
        if let error = items.first(where: { $0.name == "error" })?.value {
            guard error != "access_denied" else { throw ZoomOAuthError.cancelled }
            let detail = items.first(where: { $0.name == "error_description" })?.value
            throw ZoomOAuthError.authorizationRefused(error: error, description: detail)
        }
        guard let code = items.first(where: { $0.name == "code" })?.value else {
            throw ZoomOAuthError.noAuthorizationCode
        }

        return try await postForm([
            "grant_type": "authorization_code",
            "code": code,
            "client_id": config.publicClientID,
            "redirect_uri": config.redirectURI,
            "code_verifier": pkce.verifier,
            // No client_secret, and no Authorization header. Zoom: "Unlike the
            // confidential client flow, PKCE does not use an Authorization
            // header."
        ], missingRefreshToken: .noRefreshTokenIssued)
    }

    /// Presents Zoom's consent page.
    ///
    /// Uses the **HTTPS** callback form (macOS 14.4+) rather than a custom
    /// scheme, because Zoom rejects custom schemes for a General App. That form
    /// requires the host to be listed in the app's Associated Domains
    /// entitlement; without it the session opens, the user consents, and
    /// nothing ever comes back — so the configuration is checked up front and
    /// refused loudly rather than hanging.
    private func presentConsent(url: URL) async throws -> URL {
        guard let host = config.callbackHost, !host.isEmpty,
              config.redirectURI.lowercased().hasPrefix("https://")
        else {
            throw ZoomOAuthError.unusableCallback(
                "the redirect must be an https:// URL on a domain listed in Associated Domains")
        }
        let path = config.callbackPath ?? "/"

        return try await withCheckedThrowingContinuation { continuation in
            let session = ASWebAuthenticationSession(
                url: url,
                callback: .https(host: host, path: path)
            ) { callbackURL, error in
                if let error {
                    let code = (error as? ASWebAuthenticationSessionError)?.code
                    continuation.resume(throwing: code == .canceledLogin
                                        ? ZoomOAuthError.cancelled
                                        : error)
                    return
                }
                guard let callbackURL else {
                    continuation.resume(throwing: ZoomOAuthError.noAuthorizationCode)
                    return
                }
                continuation.resume(returning: callbackURL)
            }
            session.presentationContextProvider = self
            session.prefersEphemeralWebBrowserSession = false
            self.authSession = session
            session.start()
        }
    }

    /// Exchange a refresh token for a new pair.
    ///
    /// **The persist call happens before this returns, and a persistence
    /// failure is treated as a failure of the whole refresh.** That ordering is
    /// the entire point. Zoom rotates single-use refresh tokens with no grace
    /// window, so the moment this call succeeds the *old* token is already dead
    /// server-side; if we then fail to store the new one, the account is
    /// stranded and the only recovery is a full re-authorisation with a consent
    /// screen. Reporting success on a path where the write failed is the
    /// fake-success pattern this codebase keeps finding and removing.
    func refresh(_ current: ZoomTokens) async throws -> ZoomTokens {
        let refreshed: ZoomTokens
        do {
            refreshed = try await postForm([
                "grant_type": "refresh_token",
                "refresh_token": current.refreshToken,
                "client_id": config.publicClientID,
            ], carryingScopes: current.scopes)
        } catch let error as ZoomOAuthError {
            if case .tokenExchangeFailed(let status, _) = error, status == 400 || status == 401 {
                throw ZoomOAuthError.refreshRejected
            }
            throw error
        }
        do {
            try await persist(refreshed)
        } catch {
            // Hand the working pair back with the failure. The alternative —
            // letting the error escape bare — destroys a credential that was
            // just successfully minted, and leaves the caller with a stored
            // token Zoom has already spent.
            throw ZoomOAuthError.rotationNotPersisted(refreshed)
        }
        return refreshed
    }

    /// - Parameter missingRefreshToken: what to raise when the response carries
    ///   no refresh token. **Both callers hit the same guard and need opposite
    ///   messages**: on a refresh it means the token we just spent has no
    ///   replacement, which is `.refreshRejected` and correctly tells the
    ///   researcher to sign in again; on a first sign-in the same words would
    ///   announce that a connection made two seconds ago had *expired*, and the
    ///   remedy they imply — sign in again — reproduces it exactly.
    private func postForm(
        _ fields: [String: String],
        carryingScopes: [String] = [],
        missingRefreshToken: ZoomOAuthError = .refreshRejected
    ) async throws -> ZoomTokens {
        var request = URLRequest(url: Self.tokenEndpoint)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        var body = URLComponents()
        body.queryItems = fields.map { URLQueryItem(name: $0.key, value: $0.value) }
        request.httpBody = body.percentEncodedQuery?.data(using: .utf8)

        let (data, response) = try await session.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200...299).contains(status) else {
            throw ZoomOAuthError.tokenExchangeFailed(
                status: status,
                body: String(data: data, encoding: .utf8) ?? ""
            )
        }
        let decoded = try JSONDecoder().decode(ZoomTokenResponse.self, from: data)
        guard let refresh = decoded.refresh_token else {
            // A refresh response with no replacement token is not a success we
            // can carry forward: the one we just spent is dead.
            throw missingRefreshToken
        }
        let scopes = decoded.scope?.split(separator: " ").map(String.init) ?? carryingScopes
        return ZoomTokens(
            accessToken: decoded.access_token,
            refreshToken: refresh,
            expiresAt: Date().addingTimeInterval(TimeInterval(decoded.expires_in ?? 3600)),
            scopes: scopes
        )
    }
}

extension ZoomOAuthClient: ASWebAuthenticationPresentationContextProviding {
    nonisolated func presentationAnchor(
        for session: ASWebAuthenticationSession
    ) -> ASPresentationAnchor {
        MainActor.assumeIsolated {
            anchorWindow ?? PanelHost.window ?? NSApp.windows.first ?? NSWindow()
        }
    }
}

// MARK: - Shared comparison

/// Constant-time string comparison, shared by every adapter's `state` check.
///
/// Named once because reasoning about whether *this particular* CSRF token is
/// timing-attackable is more expensive than just always comparing safely.
enum OAuthCompare {
    static func constantTimeEquals(_ a: String, _ b: String) -> Bool {
        let lhs = Array(a.utf8), rhs = Array(b.utf8)
        guard lhs.count == rhs.count else { return false }
        var diff: UInt8 = 0
        for i in 0..<lhs.count { diff |= lhs[i] ^ rhs[i] }
        return diff == 0
    }
}
