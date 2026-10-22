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
    private struct ScreensStart: Decodable { let status: String; let total: Int }
    /// Either board's job status: the quotes board's (`stickies`, `vars`) or the screens board's
    /// (`completed_count`, `skipped_count`), and the `build` both carry.
    private struct BoardJobStatus: Decodable {
        let status: String
        let board_url: String?
        let reason: String?
        let stickies: Int?
        let vars: [String: String]?
        let completed_count: Int?
        let skipped_count: Int?
        let build: MiroBoardBuild?
    }
    private struct ErrorBody: Decodable {
        let detail: String?
        /// The discriminator, when the server had one. `nil` for a wire
        /// diagnostic (HTTP status plus Miro's response text), which is
        /// correctly English — it goes to a log, not to a researcher — and
        /// falls through to `detail` exactly as it always did.
        ///
        /// Spelled `reason` because that is the field `routes/miro.py` writes.
        /// This was `code` for a day (22 Sep 2026): the server never sent one,
        /// so every failure fell through to the English `detail` and the key
        /// table below was decorative. `tests/test_miro_failure_keys.py` now
        /// asserts the spelling both clients decode.
        let reason: String?
        let vars: [String: String]?
    }

    /// Server `reason` → the key that says it in the reader's language.
    ///
    /// A table, not a `contains` on the sentence. The server's `detail` is
    /// English prose; matching on it breaks the day somebody rewords it, which
    /// is the whole reason `Cause.reason` and `CloudFetchFailure` exist. An
    /// unknown code falls through to `detail`, so a newer sidecar talking to an
    /// older app degrades to the previous behaviour rather than to nothing.
    /// The quotes board's reasons, and the screens board's one more: no still could be made.
    private static let screensErrorKeys = errorKeys.merging(
        ["no_stills": "common.export.screens.none"]) { a, _ in a }

    /// Not private so a test can pin an entry, as `FigJamAPI.reasonKeys` is.
    static let errorKeys: [String: String] = [
        // Named by the job route when Miro refuses the token (a 401/403 with no reason of its own).
        "token_rejected": "common.miro.tokenRejected",
        // Both boards' start, before any job: no Miro token at all (R94).
        "not_connected": "common.miro.errNotConnected",
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
    struct ExportResult {
        let boardURL: String
        let stickies: Int
        /// Screens the board could not show (their still could not be made); the sheet says so.
        var skipped = 0
    }

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

    /// The server's own `detail` when it sent one, plus the key its `reason`
    /// names when the failure is one a researcher reads. `detail` stays on the
    /// error either way — it is what a bug report wants, and it is the fallback
    /// when the code is unknown or absent.
    private func apiError(from data: Data, status: Int) -> APIError {
        if let body = try? JSONDecoder().decode(ErrorBody.self, from: data),
           let d = body.detail, !d.isEmpty
        {
            return APIError(message: d,
                            localeKey: body.reason.flatMap { Self.errorKeys[$0] },
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
    /// Throws when it could not tell, so the sheet can say so rather than show the
    /// Connect step as if signed out (R78): a transport failure is
    /// `APIError.serverUnreachable()`, a non-2xx is the server's own error, and a
    /// 200 that does not decode is `requestFailed` with that status. Only a 200
    /// that answers `connected: false` means "no token".
    func status() async throws -> Connection {
        guard let req = request("/status", method: "GET") else {
            throw APIError.serverUnreachable()
        }
        let (data, resp): (Data, URLResponse)
        do {
            (data, resp) = try await URLSession.shared.data(for: req)
        } catch {
            throw APIError.serverUnreachable()
        }
        guard let http = resp as? HTTPURLResponse else {
            throw APIError.serverUnreachable()
        }
        guard (200..<300).contains(http.statusCode) else {
            throw apiError(from: data, status: http.statusCode)
        }
        guard let parsed = try? JSONDecoder().decode(StatusResponse.self, from: data) else {
            throw APIError(message: "Request failed (HTTP \(http.statusCode)).",
                           localeKey: "common.miro.requestFailed",
                           localeVars: ["status": String(http.statusCode)])
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
        let (data, resp): (Data, URLResponse)
        do {
            (data, resp) = try await URLSession.shared.data(for: req)
        } catch {
            throw APIError.serverUnreachable()
        }
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

    /// A refused start: a 409 is the last build still running or stopping (Stop answers at once,
    /// the server finishes the call in hand), said in the reader's language, not the server's.
    private func startError(from data: Data, status: Int, screens: Bool = false) -> APIError {
        guard status == 409 else { return apiError(from: data, status: status) }
        return APIError(message: "A Miro board is still being built or stopped",
                        localeKey: screens ? "common.export.screens.inProgress" : "common.miro.stillStopping")
    }

    /// Called on the main actor with each progress read while a board builds.
    typealias ProgressHandler = @MainActor (MiroBoardBuild?) -> Void

    private func make(_ url: String, _ method: String, _ body: [String: Any?]? = nil) -> URLRequest? {
        guard let url = URL(string: url) else { return nil }
        var req = URLRequest(url: url)
        req.httpMethod = method
        if let token { req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try? JSONSerialization.data(withJSONObject: body.compactMapValues { $0 })
        }
        return req
    }

    /// The two boards' job roots: start is POST here, then `/status` and `/cancel`.
    private func jobRoot(screens: Bool) -> String {
        let project = "http://127.0.0.1:\(port)/api/projects/\(projectID)"
        return screens ? project + "/export/screens/miro" : project + "/miro/board"
    }

    /// Read a board's job until it ends, telling `onProgress` each read. Called inside a
    /// cancellation handler that asks the server to stop.
    private func pollUntilDone(screens: Bool, onProgress: ProgressHandler) async throws -> ExportResult {
        guard let poll = make(jobRoot(screens: screens) + "/status", "GET") else {
            throw APIError.serverUnreachable()
        }
        while true {
            let (sd, resp) = try await URLSession.shared.data(for: poll)
            guard let http = resp as? HTTPURLResponse else { throw APIError.serverUnreachable() }
            guard (200..<300).contains(http.statusCode) else { throw apiError(from: sd, status: http.statusCode) }
            let s = try JSONDecoder().decode(BoardJobStatus.self, from: sd)
            switch s.status {
            case "running":
                await onProgress(s.build)
                try await Task.sleep(nanoseconds: 1_500_000_000)
            case "completed":
                // A board with no link is not ready: Open in Miro would do nothing (R79).
                guard let url = s.board_url, !url.isEmpty else {
                    throw APIError(message: "Miro board completed without a link",
                                   localeKey: "common.miro.exportError")
                }
                return ExportResult(boardURL: url,
                                    stickies: s.completed_count ?? s.stickies ?? 0,
                                    skipped: s.skipped_count ?? 0)
            case "cancelled":
                throw CancellationError()
            case "idle":
                // The server no longer knows the build (it restarted): an error, not a quiet stop.
                throw APIError(message: "Miro board job unknown to the server",
                               localeKey: "common.miro.exportError")
            default:
                let keys = screens ? Self.screensErrorKeys : Self.errorKeys
                throw APIError(message: "Miro board \(s.status): \(s.reason ?? "")",
                               localeKey: s.reason.flatMap { keys[$0] } ?? "common.miro.exportError",
                               localeVars: s.vars ?? s.board_url.map { ["url": $0] } ?? [:])
            }
        }
    }

    /// Whether a board of this kind is being built right now — a sheet reopened while one builds
    /// picks it up rather than offering to start another.
    func boardIsBuilding(screens: Bool) async -> Bool {
        guard let poll = make(jobRoot(screens: screens) + "/status", "GET"),
              let (data, resp) = try? await URLSession.shared.data(for: poll),
              let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode),
              let s = try? JSONDecoder().decode(BoardJobStatus.self, from: data)
        else { return false }
        return s.status == "running"
    }

    /// Follow a build already running (see `boardIsBuilding`). Cancelling the Task stops it.
    func resumeBoard(screens: Bool, onProgress: @escaping ProgressHandler) async throws -> ExportResult {
        guard let cancel = make(jobRoot(screens: screens) + "/cancel", "POST") else {
            throw APIError.serverUnreachable()
        }
        return try await withTaskCancellationHandler {
            try await pollUntilDone(screens: screens, onProgress: onProgress)
        } onCancel: {
            Task { _ = try? await URLSession.shared.data(for: cancel) }
        }
    }

    /// The screens as a board, a frame per screengrab (docs/design-screens-export.md §6). A job,
    /// not one request: it starts, then its status is read until it ends. Cancelling the Task asks
    /// the server to stop after the call it is making; the board keeps what it has.
    func exportScreens(boardName: String?, colourBy: String, locale: String,
                       splitLongQuotes: Bool = true, stickyShape: String = "rectangle",
                       onProgress: @escaping ProgressHandler = { _ in }) async throws -> ExportResult {
        let root = jobRoot(screens: true)
        guard let start = make(root, "POST", ["board_name": boardName, "colour_by": colourBy, "locale": locale,
                                              "split_long_quotes": splitLongQuotes, "sticky_shape": stickyShape]),
              let cancel = make(root + "/cancel", "POST")
        else { throw APIError.serverUnreachable() }
        // Cancel reaches the server whenever it lands — in the start request, a status read or the
        // pause between them — not only in the pause, where it used to be caught.
        return try await withTaskCancellationHandler {
            let (data, resp) = try await URLSession.shared.data(for: start)
            guard let http = resp as? HTTPURLResponse else { throw APIError.serverUnreachable() }
            guard (200..<300).contains(http.statusCode) else {
                throw startError(from: data, status: http.statusCode, screens: true)
            }
            let started = try JSONDecoder().decode(ScreensStart.self, from: data)
            if started.total == 0 {
                throw APIError(message: "No screens to export", localeKey: "common.export.screens.none")
            }
            return try await pollUntilDone(screens: true, onProgress: onProgress)
        } onCancel: {
            Task { _ = try? await URLSession.shared.data(for: cancel) }
        }
    }

    /// Build a new quotes board — a job since 18 Oct 2026, like the screens board's: Miro refuses
    /// a new board's frames for about half a minute and every sticky batch is a round trip, so it
    /// is never "seconds". Its progress goes to `onProgress`; cancelling the Task stops it on the
    /// server. A failure carries the server's `reason`, and a part-built board its address.
    ///
    /// `locale` is the board's own language, not the app's convenience: the
    /// board is a deliverable, and its frame titles and per-column counts are
    /// rendered server-side, so the sheet has to say who is asking. Omitting it
    /// is what made every board English (fixed 22 Sep 2026).
    func export(boardName: String?, colourBy: String, clipsBase: String,
                locale: String, splitLongQuotes: Bool = true,
                stickyShape: String = "rectangle",
                onProgress: @escaping ProgressHandler = { _ in }) async throws -> ExportResult {
        let root = jobRoot(screens: false)
        guard let start = make(root, "POST",
                               ["board_name": boardName, "colour_by": colourBy,
                                "clips_base": clipsBase, "locale": locale,
                                "split_long_quotes": splitLongQuotes, "sticky_shape": stickyShape]),
              let cancel = make(root + "/cancel", "POST")
        else { throw APIError.serverUnreachable() }
        return try await withTaskCancellationHandler {
            let (data, resp) = try await URLSession.shared.data(for: start)
            guard let http = resp as? HTTPURLResponse else { throw APIError.serverUnreachable() }
            guard (200..<300).contains(http.statusCode) else { throw startError(from: data, status: http.statusCode) }
            return try await pollUntilDone(screens: false, onProgress: onProgress)
        } onCancel: {
            Task { _ = try? await URLSession.shared.data(for: cancel) }
        }
    }
}
