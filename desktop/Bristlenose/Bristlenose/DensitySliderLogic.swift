import Foundation

/// The decisions behind the Display popover's Density slider, kept out of the
/// view so they can be tested (desktop/CLAUDE.md: a view that decides pulls the
/// decision into a helper).
///
/// The report owns the density value and echoes each one back; the slider sends
/// as it moves and shows its own value until the echo catches up.
enum DensitySliderLogic {
    /// The report stores two decimal places, so a sent value is compared to its
    /// echo at that precision.
    static func rounded(_ v: Double) -> Double { (v * 100).rounded() / 100 }

    /// Near Normal, a MOUSE drag settles on it exactly. A keyboard step does not
    /// snap, or the arrow keys could never leave Normal.
    static func snapped(_ v: Double, mouseEditing: Bool) -> Double {
        mouseEditing && abs(v - DisplayPrefs.densityNormal) < snapWindow ? DisplayPrefs.densityNormal : v
    }

    static let snapWindow = 0.04

    /// A send goes out at once if the last one was long enough ago; otherwise it
    /// is held back and goes out a moment later (see `trailingDelay`).
    static let sendInterval: TimeInterval = 0.06
    static let trailingDelay: UInt64 = 70_000_000

    static func shouldSendNow(now: Date, lastSent: Date) -> Bool {
        now.timeIntervalSince(lastSent) > sendInterval
    }

    /// Whether the report's value is the echo of what the slider showed: the
    /// tolerance covers rounding at exact half-way points (0.125 stores as 0.13).
    static func echoMatches(shown: Double, report: Double) -> Bool {
        abs(rounded(shown) - report) < 0.0051
    }

    /// How long the slider keeps showing its own value after the last change
    /// before it gives up waiting for an echo and follows the report. Covers an
    /// echo that never comes (the report reloaded, the web view went, a post was
    /// refused) and an `onEditingChanged(false)` that never arrives.
    static let settleDelay: UInt64 = 450_000_000
}
