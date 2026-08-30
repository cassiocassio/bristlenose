import Foundation

/// How a spawned process actually died — exited, or was killed by a signal.
///
/// WHY THIS EXISTS
/// ---------------
/// `Process.terminationStatus` alone cannot tell you. When a process dies of a
/// signal, `terminationStatus` carries the SIGNAL NUMBER, and only
/// `terminationReason` says which of the two numbers you are holding. Logging
/// the bare number renders a signalled death as though it were a clean exit.
///
/// On 30 Aug 2026 that cost a working day. The sidecar was dying of SIGILL —
/// a corrupt `libllvmlite.dylib` with a hole of zeros in its executable code —
/// and every surface said `status=4`, which reads as "exited 4" and sends you
/// looking for an exit-code table that does not exist. The operating system had
/// already written the exact faulting frame to a crash report; nothing pointed
/// at it. The popover said "Something went wrong."
///
/// So: name the signal, and say where the crash report is.
enum ProcessOutcome: Equatable {
    case exited(code: Int32)
    case signalled(signal: Int32)

    init(status: Int32, reason: Process.TerminationReason) {
        self = reason == .uncaughtSignal
            ? .signalled(signal: status)
            : .exited(code: status)
    }

    /// True for any non-clean end, however it ended.
    var isFailure: Bool {
        switch self {
        case .exited(let code): return code != 0
        case .signalled: return true
        }
    }

    /// The number the rest of the pipeline has always used. Preserved so
    /// existing classification and cancellation logic are untouched by this
    /// type — it adds meaning, it does not redefine the contract.
    var rawStatus: Int32 {
        switch self {
        case .exited(let code): return code
        case .signalled(let signal): return signal
        }
    }

    /// Forensic rendering for logs and `last-run-failure.log`.
    /// `exit=1` / `signal=SIGILL(4)` — never a bare number whose meaning
    /// depends on a field the reader cannot see.
    var logDescription: String {
        switch self {
        case .exited(let code):
            return "exit=\(code)"
        case .signalled(let signal):
            return "signal=\(Self.name(ofSignal: signal))(\(signal))"
        }
    }

    /// Where the OS wrote the details, for the cases where it did. A signalled
    /// death leaves an `.ips` crash report naming the faulting frame; an exit
    /// does not. Emitting this path is the difference between "unknown" and a
    /// stack trace.
    var diagnosticHint: String? {
        guard case .signalled = self else { return nil }
        return "crash report: ~/Library/Logs/DiagnosticReports/bristlenose-sidecar-*.ips"
    }

    /// Mnemonic for a signal number. Explicit table rather than `sys_signame`
    /// so the mapping is readable at the call site and testable without libc.
    /// Unknown numbers render as `SIG<n>` rather than guessing.
    static func name(ofSignal signal: Int32) -> String {
        switch signal {
        case SIGHUP:  return "SIGHUP"
        case SIGINT:  return "SIGINT"
        case SIGQUIT: return "SIGQUIT"
        case SIGILL:  return "SIGILL"
        case SIGTRAP: return "SIGTRAP"
        case SIGABRT: return "SIGABRT"
        case SIGFPE:  return "SIGFPE"
        case SIGKILL: return "SIGKILL"
        case SIGBUS:  return "SIGBUS"
        case SIGSEGV: return "SIGSEGV"
        case SIGSYS:  return "SIGSYS"
        case SIGPIPE: return "SIGPIPE"
        case SIGALRM: return "SIGALRM"
        case SIGTERM: return "SIGTERM"
        case SIGXCPU: return "SIGXCPU"
        case SIGXFSZ: return "SIGXFSZ"
        default:      return "SIG\(signal)"
        }
    }
}
