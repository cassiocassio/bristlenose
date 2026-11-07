import AppKit
import Foundation
import os

/// Opens the running sidecar's SQLAdmin database browser (`/admin`) in the
/// user's default browser.
///
/// Compiled in Release — the "Open Admin Panel" item sits in Section 2 of the
/// Diagnostics menu, gated by `DistributionChannel.exposesDebugTools`, which
/// is `true` in the Release Developer-ID `.dmg` beta (`DEVELOPER_ID_BETA`
/// flag), so its action must exist in that Release binary. It's a runtime
/// `false` (hidden section) in App Store / TestFlight builds.
///
/// `/admin` is outside `/api/`, and a browser cannot send a bearer header, so
/// the app asks the authenticated `POST /api/admin/open` for a single-use code
/// and opens `/admin/?t=<code>`; the server swaps the code for a cookie scoped
/// to `/admin` and takes it out of the address (T21, 7 Nov 2026). A process
/// that can reach the port but holds neither the server token nor a fresh
/// code gets a 401. The panel is read-only in every non-dev channel (see
/// `register_admin_views(read_only=...)`).
///
/// See `docs/design-desktop-debug-admin-panel.md`.
@MainActor
enum AdminPanelAction {
    private static let log = Logger(subsystem: "app.bristlenose", category: "serve")

    static func open(serveManager: ServeManager) {
        guard let port = serveManager.runningPort, let token = serveManager.authToken else { return }
        Task {
            guard let url = await fetchURL(port: port, token: token) else { return }
            NSWorkspace.shared.open(url)
        }
    }

    private static func fetchURL(port: Int, token: String) async -> URL? {
        guard let endpoint = URL(string: "http://127.0.0.1:\(port)/api/admin/open") else { return nil }
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            let status = (response as? HTTPURLResponse)?.statusCode ?? -1
            guard status == 200 else {
                log.error("admin open: serve answered \(status, privacy: .public)")
                return nil
            }
            let path = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["path"] as? String
            guard let url = url(port: port, path: path) else {
                log.error("admin open: serve sent an unusable path")
                return nil
            }
            return url
        } catch {
            log.error("admin open failed: \(error.localizedDescription, privacy: .public)")
            return nil
        }
    }

    /// The address to open, from the path the server sent. Only a path under
    /// `/admin/` on this machine is accepted: the reply is a path, never a host.
    nonisolated static func url(port: Int, path: String?) -> URL? {
        guard let path, path.hasPrefix("/admin/"), !path.contains("//"), !path.contains("\\") else { return nil }
        return URL(string: "http://127.0.0.1:\(port)\(path)")
    }
}
