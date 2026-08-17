import AuthenticationServices
import CryptoKit
import Foundation

// Google OAuth for an installed app: authorization code + PKCE, no client
// secret, no server, refresh token in the Keychain.
//
// Everything here is measured against Google's own native-app documentation
// (https://developers.google.com/identity/protocols/oauth2/native-app),
// verified 15 Aug 2026. The four findings that shaped it, each of which the
// obvious implementation gets wrong:
//
//  1. **There is no "macOS" OAuth client type.** You pick `iOS` (bundle-ID
//     bound, no secret, custom scheme, loopback DEPRECATED) or `Desktop app`
//     (secret issued, loopback). A sandboxed Mac App Store app takes `iOS`, so
//     the redirect is the reversed client ID and nothing else.
//  2. **`access_type=offline` is not a parameter here.** Google: "refresh
//     tokens are always returned for installed applications." Sending it is
//     harmless but signals a copied web-server flow.
//  3. **Incremental authorisation does not exist for installed apps** — stated
//     twice on that page. There is no adding a scope later; every scope change
//     is a full re-consent. `GoogleScopes` therefore names the whole set it
//     will ever ask for in one place.
//  4. **The user can decline scopes individually**, and Google requires the app
//     to check: "Your app must verify which scopes were actually granted and
//     gracefully handle situations where some permissions are denied." That is
//     what `GrantedScopes` is for, and why it is part of the token type rather
//     than an afterthought.
//
// And one that is about the app store rather than the protocol: on macOS,
// `ASWebAuthenticationSession` opens the user's real default browser, not an
// embedded view. That is Apple's documented macOS behaviour, but Mac apps have
// been rejected for it under 5.1.1 (Apple Developer Forums thread 750400,
// Apr 2024, unresolved). The review notes need to say so, citing Apple's own
// documentation. Route through the app-store-police agent before submitting.
//
// What is deliberately NOT here: the client ID. Registering an OAuth client is
// an act of the maintainer's Google account, not something the app can do for
// itself, so the ID is configuration and its absence is a first-class state
// (`GoogleOAuthError.notConfigured`) rather than a crash.

// MARK: - Configuration

/// The scopes this app will ever request, named once.
///
/// One place, because incremental authorisation is unavailable: adding a scope
/// is a re-consent for every existing user, so the set is a design decision and
/// not a per-call-site one.
enum GoogleScopes {
    /// The meeting list and the attendee roster. **Sensitive**: verification
    /// (review, justification, demo video), weeks of latency, but no
    /// third-party security assessment and no fee.
    static let calendar = "https://www.googleapis.com/auth/calendar.events.readonly"

    /// Meet conference records: recordings metadata, **transcripts**,
    /// transcript entries and participants. **Sensitive**, same tier as
    /// calendar — no assessment, no fee, nothing admin-gated.
    ///
    /// This scope is the reason the Google design looks nothing like the Teams
    /// one. `conferenceRecords.transcripts.entries` returns, per utterance, a
    /// `participant` reference, `startTime`, `endTime` and `text` — a complete
    /// speaker-attributed, timecoded transcript — and `participants.get`
    /// resolves the reference to a display name. On the cheap tier.
    ///
    /// **Take `.readonly`, never `.created`.** The names invite the opposite
    /// choice, and `meetings.space.created` sounds like the more modest one.
    /// It scopes to spaces *this app created*, so an import tool — which by
    /// definition wants meetings it did not create — sees an empty list and no
    /// error. (GAM hit exactly this: github.com/GAM-team/GAM issue 1822.)
    static let meetReadonly = "https://www.googleapis.com/auth/meetings.space.readonly"

    /// Files this app opened via a picker, or that the user shared with it.
    /// **Non-sensitive** — no verification, no assessment, no fee.
    ///
    /// The only affordable door to recording *bytes*: the Meet API hands out a
    /// Drive `fileId` and an `exportUri` that is a browser view link
    /// (`drive.google.com/file/d/{id}/view`), never a byte stream. Downloading
    /// means the Drive API, and every blanket Drive scope is Restricted.
    static let driveFile = "https://www.googleapis.com/auth/drive.file"

    /// Just enough identity to know which account is signed in — needed for two
    /// concrete things: dropping "you" from the attendee line, and the domain
    /// externality is measured against.
    static let email = "https://www.googleapis.com/auth/userinfo.email"

    /// **Restricted. Deliberately not requested.** Listed so the name appears
    /// once, with its price attached, rather than looking like an oversight to
    /// the next person who reads the Meet auth table.
    ///
    /// `drive.meet.readonly` was announced (Jul 2024) as the *granular*
    /// alternative to `drive.readonly` — "Drive access is not provisioned too
    /// broadly" — and Google still classifies it **Restricted**, the same tier
    /// as reading the user's entire Drive: annual third-party security
    /// assessment, 4–6 weeks, a recurring fee, revalidated every year. It
    /// narrows the *data*, not the *compliance cost*. Verified 15 Aug 2026
    /// against Google's own scope table, which is the claim
    /// `docs/design-cloud-import.md` §3 marked ⚠️unverified.
    static let driveMeetReadonly = "https://www.googleapis.com/auth/drive.meet.readonly"

    /// **The listing grant. `drive.file` is deliberately NOT in it.**
    ///
    /// This is not a preference — it is a hard constraint, and getting it wrong
    /// produces an OAuth request Google refuses. The desktop Picker flow's own
    /// documentation, verbatim: *"only the `drive.file` scope is permitted for
    /// these apps and it can't be combined with any other scope."*
    ///
    /// So Google's design forces two consents, and the shape that falls out is
    /// better than the one-grant version would have been:
    ///
    /// - **This grant** (sensitive) answers *what meetings are there* — titles,
    ///   times, attendees, and the full timecoded transcript.
    /// - **`mediaGrant`** (non-sensitive) answers *may I have these files* —
    ///   and, because the Picker takes `file_ids`, it asks that question once
    ///   for the whole ticked batch rather than once per file.
    ///
    /// Nothing here is Restricted, so no assessment, no fee, no annual audit.
    ///
    /// Two further consequences of the mix, both real:
    ///
    /// - **Partial consent is routine, not exotic.** Google shows the per-scope
    ///   checkbox screen whenever a request carries 2+ non-Sign-In scopes, so
    ///   the app must handle any subset — which Google requires explicitly.
    /// - **There is no adding one later.** Installed apps get no incremental
    ///   authorisation, so this list is the whole set, forever, and changing it
    ///   re-consents every existing user.
    static let requested = [calendar, meetReadonly, email]

    /// The second, separate grant: the bytes.
    ///
    /// Requested on its own, through the desktop Picker flow
    /// (`trigger_onepick=true`), never alongside anything above.
    static let mediaGrant = [driveFile]

    /// The subset that still yields a usable product if the user unticks Meet
    /// on the consent screen. Declining `meetings.space.readonly` costs the
    /// transcript and the recording join; the meeting list and roster survive.
    static let sufficientWithoutMeet = [calendar]
}

/// Where the client ID comes from, and what to say when it is absent.
///
/// Resolution order is deliberate: a build-time value ships to users, a
/// UserDefaults override lets the maintainer point a dev build at a test client
/// without a rebuild.
struct GoogleOAuthConfig {
    let clientID: String

    /// `NNNNNN-XXXX.apps.googleusercontent.com` → `com.googleusercontent.apps.NNNNNN-XXXX`
    ///
    /// Google issues no separate redirect value for an iOS client; it is
    /// derived from the client ID, and getting the derivation wrong produces a
    /// `redirect_uri_mismatch` that reads like a console misconfiguration.
    var callbackScheme: String {
        let suffix = ".apps.googleusercontent.com"
        let stem = clientID.hasSuffix(suffix) ? String(clientID.dropLast(suffix.count)) : clientID
        return "com.googleusercontent.apps.\(stem)"
    }

    /// **A single slash after the colon.** Google: "the path should begin with a
    /// single slash, which is different from regular HTTP URLs." The instinct to
    /// write `://` is wrong and fails at the redirect, not at the request.
    var redirectURI: String { "\(callbackScheme):/oauth2redirect" }

    static let defaultsKey = "GoogleOAuthClientID"

    static func resolve(
        defaults: UserDefaults = .standard,
        bundle: Bundle = .main
    ) -> GoogleOAuthConfig? {
        let candidates = [
            defaults.string(forKey: defaultsKey),
            bundle.object(forInfoDictionaryKey: "GoogleOAuthClientID") as? String,
        ]
        for candidate in candidates {
            guard let value = candidate?.trimmingCharacters(in: .whitespacesAndNewlines),
                  !value.isEmpty
            else { continue }
            return GoogleOAuthConfig(clientID: value)
        }
        return nil
    }
}

// MARK: - Errors

enum GoogleOAuthError: LocalizedError, Equatable {
    /// No client ID. Not a failure of the flow — the flow was never
    /// configurable. Surfaced as its own state so the window can say what is
    /// missing instead of "sign-in failed".
    case notConfigured
    case cancelled
    /// The `state` parameter did not come back intact. Treated as hostile, not
    /// as a glitch: this is the CSRF defence, and a soft failure here is the
    /// same as no defence.
    case stateMismatch
    case noAuthorizationCode
    case tokenExchangeFailed(status: Int, body: String)
    /// Sign-in succeeded but the scopes we need were declined. Carries what was
    /// actually granted so the UI can name the gap.
    case scopesDeclined(granted: [String], missing: [String])

    var errorDescription: String? {
        switch self {
        case .notConfigured:
            return "Bristlenose hasn't been set up with a Google client ID yet."
        case .cancelled:
            return "Sign-in was cancelled."
        case .stateMismatch:
            return "The sign-in response didn't match the request, so it was rejected."
        case .noAuthorizationCode:
            return "Google didn't return an authorisation code."
        case .tokenExchangeFailed(let status, let body):
            return "Google refused the sign-in (HTTP \(status)). \(body)"
        case .scopesDeclined(_, let missing):
            let names = missing.map { $0.replacingOccurrences(
                of: "https://www.googleapis.com/auth/", with: "") }
            return "These permissions were declined: \(names.joined(separator: ", "))."
        }
    }
}
// MARK: - Tokens

/// `Codable` so a sign-in can outlive the window — see `CloudGrantStore`. The
/// synthesised conformance is deliberate: every member is already a value the
/// encoder handles, and a hand-rolled one would be a second place to forget a
/// field the moment one is added.
struct GoogleTokens: Equatable, Codable, Sendable {
    let accessToken: String
    let refreshToken: String?
    let expiresAt: Date
    /// What Google actually granted — not what was asked for. The distinction
    /// is the whole point; see `GoogleScopes.requested`.
    let granted: [String]

    var isExpired: Bool { Date() >= expiresAt.addingTimeInterval(-60) }

    func has(_ scope: String) -> Bool { granted.contains(scope) }

    /// Which of the requested scopes did not come back.
    static func missing(from granted: [String], of requested: [String]) -> [String] {
        requested.filter { !granted.contains($0) }
    }
}

private struct TokenResponse: Decodable {
    let access_token: String
    let expires_in: Int
    let refresh_token: String?
    let scope: String?
    let token_type: String?
}

// MARK: - The client

/// Runs the flow. No UI decisions, no storage policy — those belong to the
/// caller.
@MainActor
final class GoogleOAuthClient: NSObject {
    static let authorizeEndpoint = URL(string: "https://accounts.google.com/o/oauth2/v2/auth")!
    static let tokenEndpoint = URL(string: "https://oauth2.googleapis.com/token")!
    static let revokeEndpoint = URL(string: "https://oauth2.googleapis.com/revoke")!

    private let config: GoogleOAuthConfig
    private let session: URLSession
    private var authSession: ASWebAuthenticationSession?
    /// Retained so `presentationAnchor(for:)` has a window to return; on macOS
    /// the provider is required.
    private weak var anchorWindow: NSWindow?

    init(config: GoogleOAuthConfig, session: URLSession = .shared, anchorWindow: NSWindow? = nil) {
        self.config = config
        self.session = session
        self.anchorWindow = anchorWindow
    }

    /// Full interactive sign-in.
    ///
    /// - Parameter requireAll: when true, a partial grant throws
    ///   `.scopesDeclined` rather than returning a half-usable token. The
    ///   caller decides, because "calendar but no Drive" is a legitimately
    ///   usable state for the roster feature and a useless one for importing
    ///   media.
    func signIn(
        scopes: [String] = GoogleScopes.requested,
        requireAll: Bool = false
    ) async throws -> GoogleTokens {
        let pkce = PKCEPair()
        let state = PKCEPair.randomVerifier(byteCount: 16)

        var components = URLComponents(url: Self.authorizeEndpoint, resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "client_id", value: config.clientID),
            URLQueryItem(name: "redirect_uri", value: config.redirectURI),
            URLQueryItem(name: "response_type", value: "code"),
            URLQueryItem(name: "scope", value: scopes.joined(separator: " ")),
            URLQueryItem(name: "code_challenge", value: pkce.challenge),
            URLQueryItem(name: "code_challenge_method", value: pkce.method),
            URLQueryItem(name: "state", value: state),
            // No `access_type`: refresh tokens are always returned to installed
            // apps. No `prompt=consent`: it would force a *new* refresh token
            // on every sign-in, and Google invalidates the oldest without
            // warning once an account holds 100 for one client.
        ]

        let callbackURL = try await presentConsent(url: components.url!)

        guard let returned = URLComponents(url: callbackURL, resolvingAgainstBaseURL: false) else {
            throw GoogleOAuthError.noAuthorizationCode
        }
        let items = returned.queryItems ?? []
        // Constant-time comparison. A timing-safe check on a CSRF token is
        // cheap; reasoning about whether this particular one is attackable is
        // not.
        guard let returnedState = items.first(where: { $0.name == "state" })?.value,
              constantTimeEquals(returnedState, state)
        else { throw GoogleOAuthError.stateMismatch }

        guard let code = items.first(where: { $0.name == "code" })?.value else {
            throw GoogleOAuthError.noAuthorizationCode
        }

        let tokens = try await exchange(code: code, verifier: pkce.verifier)

        if requireAll {
            let missing = GoogleTokens.missing(from: tokens.granted, of: scopes)
            if !missing.isEmpty {
                throw GoogleOAuthError.scopesDeclined(granted: tokens.granted, missing: missing)
            }
        }
        return tokens
    }

    private func presentConsent(url: URL) async throws -> URL {
        try await withCheckedThrowingContinuation { continuation in
            let session = ASWebAuthenticationSession(
                url: url,
                callbackURLScheme: config.callbackScheme
            ) { callbackURL, error in
                if let error {
                    let code = (error as? ASWebAuthenticationSessionError)?.code
                    continuation.resume(throwing: code == .canceledLogin
                                        ? GoogleOAuthError.cancelled
                                        : error)
                    return
                }
                guard let callbackURL else {
                    continuation.resume(throwing: GoogleOAuthError.noAuthorizationCode)
                    return
                }
                continuation.resume(returning: callbackURL)
            }
            session.presentationContextProvider = self
            // Left false deliberately: an ephemeral session prevents reusing an
            // existing Google sign-in, which turns one-click consent into a
            // full credential round trip for a researcher who is already signed
            // in. (On macOS it is advisory anyway — the default browser decides.)
            session.prefersEphemeralWebBrowserSession = false
            self.authSession = session
            session.start()
        }
    }

    /// The second grant: hand the researcher Google's own file picker,
    /// pre-scoped to the recordings they ticked, and come back with permission
    /// to download all of them.
    ///
    /// **The desktop Picker is not the JavaScript one, and that is the whole
    /// point.** The Picker everyone knows is a JS library that needs a token
    /// you already hold — unusable here, because Google blocks OAuth in
    /// embedded webviews by name (`WKWebView` is called out explicitly;
    /// `disallowed_useragent`), so there is no way to obtain that token inside
    /// the app's own web view. The native flow is instead **one OAuth request
    /// with `trigger_onepick=true`**, which does authorisation and file
    /// selection in a single browser round trip and redirects back with
    /// `picked_file_ids` alongside the code.
    ///
    /// That collapses the objection this design was carrying. `drive.file` was
    /// written off as "the user picks each file in Google's own Picker — not a
    /// filterable list, not one-click", and on the desktop path it is neither
    /// per-file nor unfiltered:
    ///
    /// - `file_ids` pre-scopes the Picker to exactly the recordings the list
    ///   already found, so the researcher confirms a set rather than hunting
    ///   for files in a folder tree.
    /// - `allow_multiple` makes it one interaction for the whole batch.
    /// - `mimetypes` filters to media.
    ///
    /// So the affordable scope and the list UX are not mutually exclusive after
    /// all: Bristlenose builds the list from the sensitive grant, and the
    /// Picker becomes a single consent step over the ticked rows — which is
    /// arguably *better* consent UX than a blanket "read every Meet file in
    /// your Drive", and costs nothing per year.
    ///
    /// - Parameter fileIDs: Drive file ids from `conferenceRecords.recordings`
    ///   (`driveDestination.file`). Empty means an unfiltered picker.
    /// - Returns: the ids the user actually granted, and the token to read them
    ///   with. The two can differ — the user may deselect — and the caller must
    ///   honour the returned set, not the requested one.
    func pickMedia(
        fileIDs: [String],
        mimeTypes: [String] = ["video/mp4", "video/webm", "audio/mp4", "audio/mpeg"]
    ) async throws -> (tokens: GoogleTokens, pickedFileIDs: [String]) {
        let pkce = PKCEPair()
        let state = PKCEPair.randomVerifier(byteCount: 16)

        var components = URLComponents(url: Self.authorizeEndpoint, resolvingAgainstBaseURL: false)!
        var items = [
            URLQueryItem(name: "client_id", value: config.clientID),
            // The one scope this flow permits. Adding any other — even the
            // calendar scope this same app holds — makes Google refuse it.
            URLQueryItem(name: "scope", value: GoogleScopes.mediaGrant.joined(separator: " ")),
            URLQueryItem(name: "redirect_uri", value: config.redirectURI),
            URLQueryItem(name: "response_type", value: "code"),
            URLQueryItem(name: "code_challenge", value: pkce.challenge),
            URLQueryItem(name: "code_challenge_method", value: pkce.method),
            URLQueryItem(name: "state", value: state),
            // Both required by the desktop-Picker flow's own documentation.
            URLQueryItem(name: "prompt", value: "consent"),
            URLQueryItem(name: "trigger_onepick", value: "true"),
            URLQueryItem(name: "allow_multiple", value: "true"),
        ]
        if !mimeTypes.isEmpty {
            items.append(URLQueryItem(name: "mimetypes", value: mimeTypes.joined(separator: ",")))
        }
        if !fileIDs.isEmpty {
            items.append(URLQueryItem(name: "file_ids", value: fileIDs.joined(separator: ",")))
        }
        components.queryItems = items

        let callbackURL = try await presentConsent(url: components.url!)
        guard let returned = URLComponents(url: callbackURL, resolvingAgainstBaseURL: false) else {
            throw GoogleOAuthError.noAuthorizationCode
        }
        let returnedItems = returned.queryItems ?? []

        // The Picker reports cancellation as an `error` parameter rather than
        // as an ASWebAuthenticationSession cancellation, so it needs its own
        // check — otherwise a cancelled pick reads as "no code returned",
        // which surfaces to the researcher as a failure rather than as the
        // choice they just made.
        if let error = returnedItems.first(where: { $0.name == "error" })?.value {
            throw error.contains("cancel")
                ? GoogleOAuthError.cancelled
                : GoogleOAuthError.tokenExchangeFailed(status: 0, body: error)
        }
        guard let returnedState = returnedItems.first(where: { $0.name == "state" })?.value,
              constantTimeEquals(returnedState, state)
        else { throw GoogleOAuthError.stateMismatch }
        guard let code = returnedItems.first(where: { $0.name == "code" })?.value else {
            throw GoogleOAuthError.noAuthorizationCode
        }

        let picked = returnedItems.first(where: { $0.name == "picked_file_ids" })?.value?
            .split(separator: ",").map(String.init) ?? []
        let tokens = try await exchange(code: code, verifier: pkce.verifier)
        return (tokens, picked)
    }

    private func exchange(code: String, verifier: String) async throws -> GoogleTokens {
        try await postForm([
            "client_id": config.clientID,
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": config.redirectURI,
            // No client_secret: an iOS client is issued none.
        ])
    }

    /// Exchange a refresh token for a fresh access token.
    ///
    /// Google's response here typically omits `scope`, so the caller's
    /// previously-known grant set is passed through rather than being reset to
    /// empty — resetting it would make every scope check fail after the first
    /// refresh, which is a bug that only appears an hour into a session.
    func refresh(refreshToken: String, knownGrants: [String]) async throws -> GoogleTokens {
        let refreshed = try await postForm([
            "client_id": config.clientID,
            "refresh_token": refreshToken,
            "grant_type": "refresh_token",
        ])
        return GoogleTokens(
            accessToken: refreshed.accessToken,
            refreshToken: refreshed.refreshToken ?? refreshToken,
            expiresAt: refreshed.expiresAt,
            granted: refreshed.granted.isEmpty ? knownGrants : refreshed.granted
        )
    }

    private func postForm(_ fields: [String: String]) async throws -> GoogleTokens {
        var request = URLRequest(url: Self.tokenEndpoint)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        var body = URLComponents()
        body.queryItems = fields.map { URLQueryItem(name: $0.key, value: $0.value) }
        request.httpBody = body.percentEncodedQuery?.data(using: .utf8)

        let (data, response) = try await session.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200...299).contains(status) else {
            // The body is Google's own error JSON and is safe to surface: it
            // names the cause (`invalid_grant`, `redirect_uri_mismatch`) in a
            // way that is actionable during setup. It carries no token.
            throw GoogleOAuthError.tokenExchangeFailed(
                status: status,
                body: String(data: data, encoding: .utf8) ?? ""
            )
        }
        let decoded = try JSONDecoder().decode(TokenResponse.self, from: data)
        return GoogleTokens(
            accessToken: decoded.access_token,
            refreshToken: decoded.refresh_token,
            expiresAt: Date().addingTimeInterval(TimeInterval(decoded.expires_in)),
            granted: decoded.scope?.split(separator: " ").map(String.init) ?? []
        )
    }

    /// Revoke at Google's end. The local Keychain delete is the caller's job —
    /// two halves, and doing only the local one leaves a live grant the
    /// researcher believes they removed.
    func revoke(token: String) async {
        var components = URLComponents(url: Self.revokeEndpoint, resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "token", value: token)]
        var request = URLRequest(url: components.url!)
        request.httpMethod = "POST"
        _ = try? await session.data(for: request)
    }

    private func constantTimeEquals(_ a: String, _ b: String) -> Bool {
        let lhs = Array(a.utf8), rhs = Array(b.utf8)
        guard lhs.count == rhs.count else { return false }
        var diff: UInt8 = 0
        for i in 0..<lhs.count { diff |= lhs[i] ^ rhs[i] }
        return diff == 0
    }
}

extension GoogleOAuthClient: ASWebAuthenticationPresentationContextProviding {
    nonisolated func presentationAnchor(
        for session: ASWebAuthenticationSession
    ) -> ASPresentationAnchor {
        MainActor.assumeIsolated {
            anchorWindow ?? PanelHost.window ?? NSApp.windows.first ?? NSWindow()
        }
    }
}
