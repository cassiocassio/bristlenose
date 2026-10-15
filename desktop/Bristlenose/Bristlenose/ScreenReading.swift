import Foundation

/// The "Read shared screens" preference (Settings ▸ Transcription) — whether the
/// serve reads the text on screens participants shared in their recordings, for
/// the Screens lens (`docs/design-screens.md`). Its own key, **on by default**,
/// and nothing to do with Diagnostics: the lens left that menu's company when
/// it shipped in the main app.
///
/// It reaches the sidecar as `BRISTLENOSE_SCREEN_TEXT` (`overlayPreferences`),
/// always stated: "1" on, "0" off. The explicit "0" matters — the server deletes
/// what it read when it sees it, while an unset variable means the CLI default
/// and deletes nothing.
enum ScreenTextPreference {
    static let key = "readSharedScreens"

    static let defaultValue = true

    /// The stored preference, or the default when it has never been touched.
    static func isEnabled(_ defaults: UserDefaults = .standard) -> Bool {
        defaults.object(forKey: key) as? Bool ?? defaultValue
    }
}

/// How far the serve's screen-reading job has got through a project's
/// recordings — the Screens lens's background work (`docs/design-screens.md`),
/// shown as one more activity on the sidebar status line, like a copy or a
/// cloud batch.
///
/// Read from `GET /api/projects/1/screens/status`. Deliberately its own type
/// and its own store, not `RunProgressEvent` / `PipelineProgress`: screen
/// reading is not a pipeline stage, has no estimator behind it, and cannot be
/// stopped, so it borrows none of the run's ladder, ring or ETA model.
struct ScreenReadingProgress: Equatable {
    /// Recordings read so far, and in all.
    let done: Int
    let total: Int
    /// Seconds of recording read so far, and in all — the denominator the
    /// server's `rate` is measured against.
    let secondsDone: Double
    let secondsTotal: Double
    /// Seconds of recording read per second of wall clock, measured by the
    /// server; nil until it has measured one. **The only source of an ETA** —
    /// there is no constant to fall back on, so a warm-up says nothing about
    /// time rather than guessing.
    let rate: Double?

    /// Remaining wall-clock seconds, or nil while there is no measured rate.
    var etaSeconds: Double? {
        guard let rate, rate.isFinite, rate > 0 else { return nil }
        let left = secondsTotal - secondsDone
        guard left.isFinite, left > 0 else { return nil }
        return left / rate
    }

    /// Parse the status body, or nil when there is nothing to show: the job is
    /// off or unavailable, not running, or finished. Pure, so the "when does
    /// the row appear" rule is testable without a server.
    ///
    /// Response shape (server-owned): `{"enabled": bool, "unavailable":
    /// null|"not_macos"|"vision_missing"|"no_job", "running": bool, "done":
    /// int, "total": int, "seconds_done": float, "seconds_total": float,
    /// "rate": float|null, "has_screens": bool, "available": bool}`.
    static func parse(_ json: [String: Any]) -> ScreenReadingProgress? {
        guard json["enabled"] as? Bool == true,
              json["running"] as? Bool == true,
              let done = (json["done"] as? NSNumber)?.intValue,
              let total = (json["total"] as? NSNumber)?.intValue,
              total > 0, done >= 0, done < total
        else { return nil }
        return ScreenReadingProgress(
            done: done,
            total: total,
            secondsDone: (json["seconds_done"] as? NSNumber)?.doubleValue ?? 0,
            secondsTotal: (json["seconds_total"] as? NSNumber)?.doubleValue ?? 0,
            rate: (json["rate"] as? NSNumber)?.doubleValue
        )
    }

    /// Does this project have a Screens lens to offer? The rail row, ⌘7 and the
    /// View menu row follow the server's answer, `available` — the rule's one
    /// copy is `screens_available` in server/routes/screens.py, which the SPA's
    /// nav reads too. Never re-derived here from the counts. An older serve
    /// without the field answers no.
    static func isAvailable(_ json: [String: Any]) -> Bool {
        json["available"] as? Bool == true
    }
}

/// Per-project screen-reading progress, for the sidebar.
///
/// **Its own `ObservableObject`, never a field on `ServeInstance`.** A value
/// published through `ServeInstance` reaches `ServeManager` and then
/// `ServeFleet`, whose `objectWillChange` every window observes; republishing
/// on each poll tick that way collapsed an open Window menu on 20 Sep 2026.
/// So the poll writes here (the `PipelineLiveData` split, for the same
/// reason), and only on change: an unchanged tick publishes nothing.
@MainActor
final class ScreenReadingStore: ObservableObject {
    static let shared = ScreenReadingStore()

    @Published private(set) var progress: [UUID: ScreenReadingProgress] = [:]

    /// The projects that have a Screens lens to offer
    /// (`ScreenReadingProgress.isAvailable`). Windows mirror their own
    /// project's membership onto the bridge, which is what puts the Screens
    /// row on the rail and ⌘7 in the View menu.
    @Published private(set) var available: Set<UUID> = []

    /// Write `value` for `project` — and publish only if it differs. `nil`
    /// clears the row.
    func set(_ value: ScreenReadingProgress?, for project: UUID) {
        guard progress[project] != value else { return }
        progress[project] = value
    }

    /// Record whether `project` has a Screens lens — publishing only on change,
    /// for the same reason as `set`.
    func setAvailable(_ isAvailable: Bool, for project: UUID) {
        guard available.contains(project) != isAvailable else { return }
        if isAvailable { available.insert(project) } else { available.remove(project) }
    }
}
