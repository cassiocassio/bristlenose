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
///
/// Registered as a shared RENDER format in `docs/design-shared-formats.md`;
/// the case table below is duplicated in `tests/fixtures/shared-format-contract.json`,
/// which the Python and TypeScript sides assert against. Note the TypeScript
/// mirror (`formatDurationHuman`) deliberately returns an em-dash rather than
/// `"0m"` for a non-positive input — it formats per-row cells, where zero means
/// unknown, not measured. That divergence is recorded in the contract file.
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
