import Foundation
import WebKit

/// One running sidecar, viewed by one or more windows.
///
/// The port is the sidecar's identity, not decoration: a warm-pool re-point
/// (Phase A2) keeps the project and changes the port, and that hand-off has to
/// re-create the view so the right auth token is injected.
struct ServeSession: Hashable {
    let projectID: UUID
    let port: Int

    /// Identity for the detail pane's `.id(…)` **and** the key for this
    /// session's storage partition. Deliberately one property feeding both: if
    /// they could drift, a view could be re-created without being re-keyed, and
    /// a fresh sidecar would inherit the previous one's cookies.
    var viewID: String { "\(projectID.uuidString)-\(port)" }
}

/// Vends one ephemeral `WKWebsiteDataStore` per serve session, so every window
/// showing the same project shares a storage partition.
///
/// **Why this exists.** `WKWebsiteDataStore.nonPersistent()` mints a *fresh*
/// partition on every call, so a `WebView` that called it directly was an
/// island. Two consequences, both observed on 16 Aug 2026 with nine windows
/// open on one project:
///
/// 1. **BroadcastChannel could not cross windows.** Cross-view messaging works
///    only between views sharing a data-store *instance* — validated 28 Mar
///    2026, `docs/design-wkwebview-messaging.md`. Nine islands meant nine mute
///    windows, which is precisely the "scroll the quotes window and jump to each
///    quote in context" case.
/// 2. **WebKit could not consolidate processes.** Separate partitions are
///    separate storage sessions, and WebKit uses that to decide it needs
///    separate content processes. Nine windows produced tens of helper processes
///    and ~2.4 GB of web content — the app fragmenting itself by construction,
///    which is the cost of a defect rather than the cost of nine windows.
///
/// **Keyed by session, not by project.** Cookies ignore port and every sidecar
/// is `127.0.0.1`, so a partition keyed on the project alone would outlive the
/// server that filled it: after a restart, a cookie minted by the previous
/// sidecar would be replayed at the new one. Keying on the serve session keeps
/// today's fresh-partition-per-sidecar isolation exactly as it was and adds only
/// the sharing we want — between views looking at the *same running server*.
///
/// Cross-project isolation (security rule 4) is untouched: two projects never
/// share a key, so they never share a partition.
@MainActor
final class SharedConfigStore {
    static let shared = SharedConfigStore()

    private var stores: [ServeSession: WKWebsiteDataStore] = [:]

    private init() {}

    /// The partition for `session`, created on first use and shared thereafter.
    func dataStore(for session: ServeSession) -> WKWebsiteDataStore {
        if let existing = stores[session] { return existing }
        // A new session supersedes any earlier one for the same project: the
        // `.id` change that brought us here is tearing those views down, so the
        // old partition has no remaining users and would otherwise sit in memory
        // for the lifetime of the app.
        stores = stores.filter { $0.key.projectID != session.projectID }
        let store = WKWebsiteDataStore.nonPersistent()
        stores[session] = store
        return store
    }

    /// Drop a project's partition — used when its windows are all gone. Safe to
    /// call for a project that has none.
    func release(projectID: UUID) {
        stores = stores.filter { $0.key.projectID != projectID }
    }

    /// Live partition count. Test seam — nothing in the app reads this.
    var partitionCount: Int { stores.count }
}
