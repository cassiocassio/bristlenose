import Foundation

/// Human-readable duration formatting for native chrome.
///
/// For any measured length, a byte-for-byte mirror of the Project dashboard's `_format_duration_human`
/// (`bristlenose/server/routes/dashboard.py`) so the window subtitle's
/// total-session-time reads identically to the dashboard's "Total" stat — the
/// user's reference point ("format calculated from the Project dashboard").
/// Pure + side-effect-free so it carries a unit test rather than a view.
///
/// Examples: `66180 → "18h 23m"`, `3600 → "1h"`, `240 → "4m"`, `30 → "<1m"`,
/// `0 → "—"`.
///
/// Registered as a shared RENDER format in `docs/design-shared-formats.md`;
/// the case table below is duplicated in `tests/fixtures/shared-format-contract.json`,
/// which the Python and TypeScript sides assert against. A non-positive input
/// renders an em dash, as TypeScript's `formatDurationHuman` does: the sessions
/// popover and the cloud import list are per-row cells, where zero means the
/// length is unknown, not measured (the contract's `zero` block, R106). The
/// window subtitle is a total and drops a zero before it gets here.
enum DurationFormat {
    /// Format a non-negative second count the way the dashboard does. The "h"
    /// / "m" abbreviations are deliberately not localised — the Python source
    /// hardcodes them too, so the two surfaces stay in lockstep.
    static func human(seconds: Double) -> String {
        if seconds <= 0 { return "\u{2014}" }
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
