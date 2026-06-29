import Foundation

/// Holds a `ProcessInfo` power assertion while a pipeline run is executing, so
/// the system won't *idle*-sleep mid-analysis (lid open, on AC, or the display
/// asleep). Without it, a long unattended run on mains power freezes at the
/// idle-sleep timer — the run doesn't fail, but it stalls until the user wakes
/// the machine, which reads as "the appliance gave up."
///
/// **What it does NOT do.** This only disables *idle* system sleep. It cannot
/// prevent *forced* sleep — closing the lid on battery sleeps the Mac no matter
/// what any app asserts; that's an OS guarantee. The honest promise is "an
/// unattended on-AC run finishes," not "a run never pauses." Recovery from a
/// forced sleep is the resume path's job, not this assertion's.
///
/// Idle *display* sleep is intentionally left enabled (`.userInitiated`
/// disables system sleep but not display sleep), so the screen can still dim
/// during an unattended run — no need to burn the backlight to keep computing.
///
/// The `begin`/`end` hooks are injected so the held/released state machine is
/// unit-testable without touching the real `ProcessInfo` (which returns an
/// opaque token and mutates global power state).
@MainActor
final class RunSleepAssertion {

    private var token: (any NSObjectProtocol)?
    private let reason: String
    private let begin: (ProcessInfo.ActivityOptions, String) -> any NSObjectProtocol
    private let end: (any NSObjectProtocol) -> Void

    // `pmset -g assertions` already attributes the assertion to "app.bristlenose",
    // so the reason omits the app name (else it reads doubled). "Analysis" not
    // "pipeline" per the analysis-not-pipeline chrome convention.
    init(
        reason: String = "Analysis in progress",
        begin: @escaping (ProcessInfo.ActivityOptions, String) -> any NSObjectProtocol
            = { ProcessInfo.processInfo.beginActivity(options: $0, reason: $1) },
        end: @escaping (any NSObjectProtocol) -> Void
            = { ProcessInfo.processInfo.endActivity($0) }
    ) {
        self.reason = reason
        self.begin = begin
        self.end = end
    }

    /// Drive the assertion to the desired state. Idempotent: begins exactly once
    /// on the not-held → held edge, ends exactly once on the held → not-held
    /// edge, and is a no-op when already in the requested state. Callers pass
    /// "is any run executing?" — the assertion owns the edge detection so churn
    /// in the caller's state never double-begins or leaks a token.
    func setHeld(_ held: Bool) {
        if held {
            guard token == nil else { return }
            token = begin(.userInitiated, reason)
        } else {
            guard let active = token else { return }
            end(active)
            token = nil
        }
    }

    /// True while the power assertion is active. Test/diagnostic hook.
    var isHeld: Bool { token != nil }
}
