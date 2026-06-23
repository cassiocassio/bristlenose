import Foundation

/// Human-readable duration formatting for native chrome.
///
/// A byte-for-byte mirror of the Project dashboard's `_format_duration_human`
/// (`bristlenose/server/routes/dashboard.py`) so the window subtitle's
/// total-session-time reads identically to the dashboard's "Total" stat — the
/// user's reference point ("format calculated from the Project dashboard").
/// Pure + side-effect-free so it carries a unit test rather than a view.
///
/// Examples: `66180 → "18h 23m"`, `3600 → "1h"`, `240 → "4m"`, `30 → "<1m"`,
/// `0 → "0m"`.
enum DurationFormat {
    /// Format a non-negative second count the way the dashboard does. The "h"
    /// / "m" abbreviations are deliberately not localised — the Python source
    /// hardcodes them too, so the two surfaces stay in lockstep.
    static func human(seconds: Double) -> String {
        if seconds <= 0 { return "0m" }
        // Truncate to whole seconds first, then integer-divide — matches
        // Python's `int(seconds // 3600)` / `int((seconds % 3600) // 60)`
        // for the non-negative domain this is only ever called on.
        let total = Int(seconds)
        let hours = total / 3600
        let minutes = (total % 3600) / 60
        if hours > 0 {
            return minutes > 0 ? "\(hours)h \(minutes)m" : "\(hours)h"
        }
        return minutes > 0 ? "\(minutes)m" : "<1m"
    }
}
