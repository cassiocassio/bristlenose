import Foundation

/// When a starting serve should be given up on.
///
/// The first launch of the bundled sidecar on a new Mac pays a one-time
/// code-signature check over its ~220 Mach-O files before Python prints a
/// line, and that can take longer than 15 s. A flat 15 s timer failed exactly
/// that launch, and Retry then worked because the check was cached (R31). So
/// the clock only matters while the process is alive: an exit is reported at
/// once by `ServeManager.handleTermination`, with its exit status, and a live
/// process gets `ceiling` to report its port.
///
/// The failure copy names the ceiling (`desktop.boot.failure.startTimeout`, as
/// a literal "90" in all 21 locales), so change both together.
enum ServeStartPolicy {
    /// How long a live, still-starting serve may take to report its port.
    static let ceiling: Duration = .seconds(90)

    /// How often the watchdog looks.
    static let pollInterval: Duration = .milliseconds(500)

    /// What the watchdog sees at one look.
    struct Observation: Equatable {
        /// Time since the process was launched.
        var elapsed: Duration
        /// The serve is still `.starting` (no port yet, no failure yet).
        var stillStarting: Bool
        /// The launched process is still running.
        var processAlive: Bool
    }

    enum Verdict: Equatable {
        /// Look again after `pollInterval`.
        case keepWaiting
        /// The serve left `.starting` on its own (port parsed, failed, or
        /// stopped). The watchdog's job is done.
        case settled
        /// The process ended. `handleTermination` reports it with the exit
        /// status, so the watchdog writes nothing and looks again: the next
        /// look is normally `.settled`.
        case processExited
        /// Still starting after `ceiling`: fail and terminate. For a dead
        /// process this is the backstop if no exit report ever arrives, so
        /// the boot never waits forever.
        case timedOut
    }

    static func verdict(for observation: Observation, ceiling: Duration = ceiling) -> Verdict {
        guard observation.stillStarting else { return .settled }
        if observation.elapsed >= ceiling { return .timedOut }
        return observation.processAlive ? .keepWaiting : .processExited
    }
}
