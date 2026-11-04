import Foundation
import os

/// The moments the owner feels, as `os_signpost` intervals — subsystem `app.bristlenose`, category
/// `perf` — so a trace (Instruments, `xctrace`, `log stream --signpost`) can say how long each took
/// without a stopwatch. The names are shared with the server (`Server-Timing`) and the page
/// (`performance.mark`), so one moment reads the same in all three layers. Added 4 Nov 2026 after
/// the window-resize profile (docs/design-client-performance.md), which had to be built from
/// Time Profiler samples because nothing named these.
enum PerfMoment: String, CaseIterable {
    /// The app starting to its first report document being ready.
    case launchToReady = "launch-to-ready"
    /// A lens (Quotes, Sessions…) asked for, to the page reporting the new route.
    case lensSwitch = "lens-switch"
    /// A study picked in the sidebar, to its report document being ready.
    case projectSelect = "project-select"
    /// A study's serve starting, to its port answering.
    case serveReady = "serve-ready"
    /// A transcript route reached, to the page reporting the transcript painted (`perf-mark`).
    case openTranscript = "open-transcript"
    /// The report document ready, to the page reporting its first quote card painted (`perf-mark`).
    case firstCardPainted = "first-card-painted"

    /// `OSSignposter` wants a literal.
    var signpostName: StaticString {
        switch self {
        case .launchToReady: "launch-to-ready"
        case .lensSwitch: "lens-switch"
        case .projectSelect: "project-select"
        case .serveReady: "serve-ready"
        case .openTranscript: "open-transcript"
        case .firstCardPainted: "first-card-painted"
        }
    }
}

/// Opens and closes the moments. An interval belongs to a `scope` (a window's bridge, a study's
/// serve), so one window's lens switch is never closed by another window's route change: the
/// multi-window trap this app keeps meeting. Beginning a moment that is still open closes the old
/// one as "superseded", and ending one that is not open does nothing, so a path that never
/// finishes cannot leave an interval running for the rest of the session.
@MainActor
enum PerfSignpost {
    static let signposter = OSSignposter(subsystem: "app.bristlenose", category: "perf")
    private static var open: [String: OSSignpostIntervalState] = [:]

    private static func key(_ moment: PerfMoment, _ scope: String) -> String { "\(moment.rawValue)|\(scope)" }

    static func begin(_ moment: PerfMoment, scope: String = "") {
        end(moment, scope: scope, outcome: "superseded")
        open[key(moment, scope)] = signposter.beginInterval(moment.signpostName, id: signposter.makeSignpostID())
    }

    /// Closes the moment if it is open. Returns whether it was.
    @discardableResult
    static func end(_ moment: PerfMoment, scope: String = "", outcome: String = "done") -> Bool {
        guard let state = open.removeValue(forKey: key(moment, scope)) else { return false }
        signposter.endInterval(moment.signpostName, state, "\(outcome, privacy: .public)")
        return true
    }

    static func isOpen(_ moment: PerfMoment, scope: String = "") -> Bool {
        open[key(moment, scope)] != nil
    }

    /// For tests: forget everything without emitting.
    static func resetForTests() { open.removeAll() }
}
