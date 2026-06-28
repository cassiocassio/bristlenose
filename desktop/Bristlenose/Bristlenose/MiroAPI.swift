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
        var errorDescription: String? { message }
    }

    private struct StatusResponse: Decodable { let connected: Bool }
    private struct ExportResponse: Decodable { let board_url: String; let stickies: Int }
    private struct ErrorBody: Decodable { let detail: String? }

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

    /// GET status — is a Miro token configured?
    ///
    /// Intentionally collapses every failure (network, 5xx, decode) to `false`,
    /// which routes the sheet to the connect screen. Safe because the recovery is
    /// idempotent — re-pasting a token just re-runs `/connect`; a transient server
    /// error at worst costs the user one extra paste, never wrong data. Don't widen
    /// this to a context where "no token" and "couldn't tell" must be distinguished.
    func status() async -> Bool {
        guard let req = request("/status", method: "GET") else { return false }
        guard let (data, resp) = try? await URLSession.shared.data(for: req),
              let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode),
              let parsed = try? JSONDecoder().decode(StatusResponse.self, from: data) else {
            return false
        }
        return parsed.connected
    }

    /// POST connect — validate + store a pasted token. Throws `APIError` with the
    /// server reason (invalid token / missing scope / network) on failure.
    @discardableResult
    func connect(token miroToken: String) async throws -> Bool {
        guard let req = request("/connect", method: "POST", body: ["token": miroToken]) else {
            throw APIError(message: "Could not reach the local server.")
        }
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse else {
            throw APIError(message: "Could not reach the local server.")
        }
        guard (200..<300).contains(http.statusCode) else {
            throw APIError(message: detail(from: data, status: http.statusCode))
        }
        return (try? JSONDecoder().decode(StatusResponse.self, from: data))?.connected ?? true
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
    func export(boardName: String?, colourBy: String, clipsBase: String) async throws -> ExportResult {
        guard let req = request(
            "/export", method: "POST",
            body: ["board_name": boardName, "colour_by": colourBy, "clips_base": clipsBase]
        ) else {
            throw APIError(message: "Could not reach the local server.")
        }
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse else {
            throw APIError(message: "Could not reach the local server.")
        }
        guard (200..<300).contains(http.statusCode) else {
            throw APIError(message: detail(from: data, status: http.statusCode))
        }
        let parsed = try JSONDecoder().decode(ExportResponse.self, from: data)
        return ExportResult(boardURL: parsed.board_url, stickies: parsed.stickies)
    }
}
