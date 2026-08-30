import Foundation
import Testing
@testable import Bristlenose

/// Tests for `ProcessOutcome` — the type that stops a signalled death being
/// reported as an exit code.
///
/// The incident these pin: on 30 Aug 2026 the sidecar died of SIGILL and every
/// surface reported `status=4`. Read as an exit code that is meaningless; read
/// as a signal it is "illegal instruction", which names the whole problem. The
/// distinguishing fact — `Process.terminationReason` — was available the entire
/// time and simply never consulted.
///
/// Pure value type, no process spawning, no `@MainActor`.
struct ProcessOutcomeTests {

    // MARK: The regression

    /// THE bug. Status 4 from a signalled process must never render as an exit.
    @Test func signalledFourIsSigillNotExitFour() {
        let outcome = ProcessOutcome(status: 4, reason: .uncaughtSignal)
        #expect(outcome == .signalled(signal: 4))
        #expect(outcome.logDescription == "signal=SIGILL(4)")
        #expect(!outcome.logDescription.contains("exit"))
    }

    /// The same number from a clean exit is a genuine exit code — the two cases
    /// are indistinguishable without `terminationReason`, which is the point.
    @Test func exitedFourIsExitFour() {
        let outcome = ProcessOutcome(status: 4, reason: .exit)
        #expect(outcome == .exited(code: 4))
        #expect(outcome.logDescription == "exit=4")
    }

    // MARK: Failure detection

    @Test func cleanExitIsNotFailure() {
        #expect(!ProcessOutcome(status: 0, reason: .exit).isFailure)
    }

    @Test func nonZeroExitIsFailure() {
        #expect(ProcessOutcome(status: 1, reason: .exit).isFailure)
    }

    /// A signal is always a failure, including signal 0 — which cannot occur,
    /// but must not read as success if it somehow did.
    @Test func anySignalIsFailure() {
        #expect(ProcessOutcome(status: SIGKILL, reason: .uncaughtSignal).isFailure)
        #expect(ProcessOutcome(status: 0, reason: .uncaughtSignal).isFailure)
    }

    // MARK: rawStatus is the untouched contract

    /// Everything downstream keys off this number. `ProcessOutcome` adds
    /// meaning; it must not change the value any existing branch sees.
    @Test func rawStatusRoundTripsBothWays() {
        #expect(ProcessOutcome(status: 4, reason: .uncaughtSignal).rawStatus == 4)
        #expect(ProcessOutcome(status: 4, reason: .exit).rawStatus == 4)
        #expect(ProcessOutcome(status: 137, reason: .exit).rawStatus == 137)
    }

    // MARK: The pointer to the evidence

    /// A signalled death leaves an `.ips` crash report naming the faulting
    /// frame. Nothing pointed at it, which is what cost the day.
    @Test func signalledOutcomeNamesTheCrashReport() {
        let hint = ProcessOutcome(status: SIGILL, reason: .uncaughtSignal).diagnosticHint
        #expect(hint != nil)
        #expect(hint?.contains("DiagnosticReports") == true)
    }

    /// An exit leaves no crash report, so pointing at one would be a wild goose
    /// chase — worse than saying nothing.
    @Test func exitedOutcomeHasNoCrashReportHint() {
        #expect(ProcessOutcome(status: 1, reason: .exit).diagnosticHint == nil)
    }

    // MARK: Signal naming

    @Test func namesTheSignalsThatActuallyShowUp() {
        #expect(ProcessOutcome.name(ofSignal: SIGILL) == "SIGILL")
        #expect(ProcessOutcome.name(ofSignal: SIGBUS) == "SIGBUS")
        #expect(ProcessOutcome.name(ofSignal: SIGSEGV) == "SIGSEGV")
        #expect(ProcessOutcome.name(ofSignal: SIGKILL) == "SIGKILL")
        #expect(ProcessOutcome.name(ofSignal: SIGTERM) == "SIGTERM")
        #expect(ProcessOutcome.name(ofSignal: SIGINT) == "SIGINT")
    }

    /// An unmapped number renders as itself rather than guessing a mnemonic.
    @Test func unknownSignalRendersAsItsNumber() {
        #expect(ProcessOutcome.name(ofSignal: 99) == "SIG99")
        #expect(ProcessOutcome(status: 99, reason: .uncaughtSignal).logDescription
                == "signal=SIG99(99)")
    }
}
