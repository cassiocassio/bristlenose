import Foundation
import os

/// Thin native client for the Miro REST endpoints served by the local sidecar
/// (`bristlenose/server/routes/miro.py`). The SwiftUI Send-to-Miro sheet is a
/// presentation layer over the SAME API the web panel uses — all validation,
/// the agnostic board IR, layout, and the egress/anonymisation boundary stay in
/// Python (see docs/design-miro-bridge.md). Swift only renders + calls.
///
/// Auth + addressing mirror `ServeManager.probeHealth`: bearer token from
/// `ServeManager.authToken`, port from `ServeManager.runningPort`, project 1.
struct MiroAPI {
    let port: Int
    let token: String?
    var projectID: Int = 1

    private static let log = Logger(subsystem: "app.bristlenose", category: "miro")

    /// User-facing failure carrying the server's `detail` string (e.g. an
    /// invalid-token reason, or a partial-board recovery URL on a 502).
    struct APIError: LocalizedError {
        let message: String
        /// Set when the sentence is ours; `nil` when `message` is the **server's**
        /// own `detail` (an invalid-token reason, a partial-board recovery URL on
        /// a 502), which we pass through rather than second-guess.
        ///
        /// `errorDescription` keeps the English for the log, as elsewhere. The
        /// display path is `localeKey` — resolved by `MiroSheet`, which is a view
        /// and has an `I18n`; this type is not and does not.
        var localeKey: String?
        var localeVars: [String: String] = [:]
        var errorDescription: String? { message }

        /// The transport could not reach our own sidecar — not Miro's problem,
        /// and worth saying so, since the sheet's fallback blames the token.
        static func serverUnreachable() -> APIError {
            APIError(message: "Could not reach the local server.",
                     localeKey: "common.miro.serverUnreachable")
        }
    }

    private struct StatusResponse: Decodable {
        let connected: Bool
        let user_name: String?
        let team_name: String?
        let org_name: String?
    }
    private struct ExportResponse: Decodable { let board_url: String; let stickies: Int }
    private struct ErrorBody: Decodable {
        let detail: String?
        /// The discriminator, when the server had one. `nil` for a wire
        /// diagnostic (HTTP status plus Miro's response text), which is
        /// correctly English — it goes to a log, not to a researcher — and
        /// falls through to `detail` exactly as it always did.
        let code: String?
        let vars: [String: String]?
    }

    /// Server `code` → the key that says it in the reader's language.
    ///
    /// A table, not a `contains` on the sentence. The server's `detail` is
    /// English prose; matching on it breaks the day somebody rewords it, which
    /// is the whole reason `Cause.reason` and `CloudFetchFailure` exist. An
    /// unknown code falls through to `detail`, so a newer sidecar talking to an
    /// older app degrades to the previous behaviour rather than to nothing.
    private static let errorKeys: [String: String] = [
        "no_quotes_selected": "common.miro.errNoQuotesSelected",
        "no_board_id": "common.miro.errNoBoardId",
        "board_incomplete": "common.miro.errBoardIncomplete",
    ]

    /// Connection state + account identity surfaced to the configure screen.
    /// `userName` is the account holder; `teamName` is the workspace new boards
    /// land in; `orgName` is the company (Enterprise only — nil for personal
    /// accounts). The trio disambiguates users with several Miro accounts. All nil
    /// when identity couldn't be fetched (older sidecar / network) — the sheet
    /// degrades to a plain "Connected".
    struct Connection {
        let connected: Bool
        let userName: String?
        let teamName: String?
        let orgName: String?
    }

    /// Board-creation result surfaced to the done screen.
    struct ExportResult { let boardURL: String; let stickies: Int }

    private func base() -> String { "http://127.0.0.1:\(port)/api/projects/\(projectID)/miro" }

    private func request(_ path: String, method: String, body: [String: Any?]? = nil) -> URLRequest? {
        guard let url = URL(string: base() + path) else { return nil }
        var req = URLRequest(url: url)
        req.httpMethod = method
        if let token { req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            // Drop nil values; JSONSerialization can't encode them.
            let clean = body.compactMapValues { $0 }
            req.httpBody = try? JSONSerialization.data(withJSONObject: clean)
        }
        return req
    }

    /// Pull the server's `detail` off a non-2xx response for a useful message.
    private func detail(from data: Data, status: Int) -> String {
        if let body = try? JSONDecoder().decode(ErrorBody.self, from: data),
           let d = body.detail, !d.isEmpty {
            return d
        }
        return "Request failed (HTTP \(status))."
    }

    /// The server's own `detail` when it sent one, plus the key its `code`
    /// names when the failure is one a researcher reads. `detail` stays on the
    /// error either way — it is what a bug report wants, and it is the fallback
    /// when the code is unknown or absent.
    private func apiError(from data: Data, status: Int) -> APIError {
        if let body = try? JSONDecoder().decode(ErrorBody.self, from: data),
           let d = body.detail, !d.isEmpty
        {
            return APIError(message: d,
                            localeKey: body.code.flatMap { Self.errorKeys[$0] },
                            localeVars: body.vars ?? [:])
        }
        return APIError(
            message: "Request failed (HTTP \(status)).",
            localeKey: "common.miro.requestFailed",
            localeVars: ["status": String(status)]
        )
    }

    /// GET status — is a Miro token configured?
    ///
    /// Intentionally collapses every failure (network, 5xx, decode) to `false`,
    /// which routes the sheet to the connect screen. Safe because the recovery is
    /// idempotent — re-pasting a token just re-runs `/connect`; a transient server
    /// error at worst costs the user one extra paste, never wrong data. Don't widen
    /// this to a context where "no token" and "couldn't tell" must be distinguished.
    func status() async -> Connection {
        guard let req = request("/status", method: "GET") else {
            return Connection(connected: false, userName: nil, teamName: nil, orgName: nil)
        }
        guard let (data, resp) = try? await URLSession.shared.data(for: req),
              let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode),
              let parsed = try? JSONDecoder().decode(StatusResponse.self, from: data) else {
            return Connection(connected: false, userName: nil, teamName: nil, orgName: nil)
        }
        return Connection(connected: parsed.connected, userName: parsed.user_name,
                          teamName: parsed.team_name, orgName: parsed.org_name)
    }

    /// POST connect — validate + store a pasted token. Throws `APIError` with the
    /// server reason (invalid token / missing scope / network) on failure.
    @discardableResult
    func connect(token miroToken: String) async throws -> Connection {
        guard let req = request("/connect", method: "POST", body: ["token": miroToken]) else {
            throw APIError.serverUnreachable()
        }
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse else {
            throw APIError.serverUnreachable()
        }
        guard (200..<300).contains(http.statusCode) else {
            throw apiError(from: data, status: http.statusCode)
        }
        let parsed = try? JSONDecoder().decode(StatusResponse.self, from: data)
        return Connection(connected: parsed?.connected ?? true,
                          userName: parsed?.user_name, teamName: parsed?.team_name,
                          orgName: parsed?.org_name)
    }

    /// POST disconnect — remove the stored token. Best-effort: the meaningful act
    /// is clearing the Swift-held Keychain copy (the env-injected key the sidecar
    /// reads), so a failed server call doesn't block disconnect — but it's logged
    /// rather than swallowed, so a server that kept the session is greppable.
    func disconnect() async {
        guard let req = request("/disconnect", method: "POST") else { return }
        do {
            _ = try await URLSession.shared.data(for: req)
        } catch {
            Self.log.warning("Miro /disconnect failed (local copy cleared anyway): \(error.localizedDescription, privacy: .public)")
        }
    }

    /// POST export — create a new board. Throws `APIError` with the server
    /// `detail` (which on a partial-board 502 includes the recovery URL).
    ///
    /// `locale` is the board's own language, not the app's convenience: the
    /// board is a deliverable, and its frame titles and per-column counts are
    /// rendered server-side, so the sheet has to say who is asking. Omitting it
    /// is what made every board English (fixed 22 Sep 2026).
    func export(boardName: String?, colourBy: String, clipsBase: String,
                locale: String) async throws -> ExportResult {
        guard let req = request(
            "/export", method: "POST",
            body: ["board_name": boardName, "colour_by": colourBy,
                   "clips_base": clipsBase, "locale": locale]
        ) else {
            throw APIError.serverUnreachable()
        }
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse else {
            throw APIError.serverUnreachable()
        }
        guard (200..<300).contains(http.statusCode) else {
            throw apiError(from: data, status: http.statusCode)
        }
        let parsed = try JSONDecoder().decode(ExportResponse.self, from: data)
        return ExportResult(boardURL: parsed.board_url, stickies: parsed.stickies)
    }
}
