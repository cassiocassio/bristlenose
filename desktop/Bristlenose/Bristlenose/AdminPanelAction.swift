import AppKit
import Foundation

/// Opens the running sidecar's SQLAdmin database browser (`/admin`) in the
/// user's default browser.
///
/// Unlike `DebugMenuActions` (which is entirely `#if DEBUG`), this helper is
/// compiled in Release too — the "Open Admin Panel…" Debug-menu item is gated
/// by `DistributionChannel.exposesDebugTools`, which is `true` in the Release
/// Developer-ID `.dmg` beta (`DEVELOPER_ID_BETA` flag), so its action must
/// exist in that Release binary. It's a compile-time `false` (dead branch) in
/// App Store / TestFlight builds.
///
/// `/admin` is not under `/api/`, so it isn't behind `BearerTokenMiddleware`
/// (middleware.py guards only the `/api/` prefix). Localhost binding is its
/// sole protection, and the panel is read-only in every non-dev channel
/// (see `register_admin_views(read_only=...)`). Opening in the external
/// browser needs no bearer token.
///
/// See `docs/design-desktop-debug-admin-panel.md`.
@MainActor
enum AdminPanelAction {
    static func open(serveManager: ServeManager) {
        guard let port = serveManager.runningPort else { return }
        guard let url = URL(string: "http://127.0.0.1:\(port)/admin/") else { return }
        NSWorkspace.shared.open(url)
    }
}
