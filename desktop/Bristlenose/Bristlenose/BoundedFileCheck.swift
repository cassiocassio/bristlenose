import Foundation
import os

/// "Does this path exist?" for a path that may live on a share that has stopped answering (R59, R60).
///
/// `Project.availability` asked `FileManager.fileExists` on whatever thread a view read it from, the
/// main thread included, and a stat on a mounted-but-unreachable share (or a drive that is spinning
/// up, or a server that has gone to sleep) does not return until the kernel gives up, which can be a
/// minute or more: a beachball, or a "Connect to server" prompt. Owner call, 9 Nov 2026: bound it.
///
/// Only paths under `/Volumes/` (where every network share and external drive mounts) are checked this
/// way; a local path cannot hang and keeps the direct call. The stat runs on a thread of its own and the
/// caller waits at most `timeout`. A stat that has not answered is reported as "does not exist", so the
/// study shows its existing "can't reach it" state instead of freezing the sidebar, and that verdict is
/// remembered for `retryAfter` so a stalled path costs one wait, not one per redraw. At most one probe per
/// path is ever outstanding, so a dead share leaves one parked thread, not one per call.
///
/// Not proven against a real stalled share (this Mac cannot stage one); what is tested is that a probe
/// that never returns does not block the caller, and that a normal one is unaffected.
enum BoundedFileCheck {
    /// How long a caller waits for a stat before treating it as stalled.
    static let timeout: TimeInterval = 0.25
    /// How long a stalled path is answered "no" without trying again.
    static let retryAfter: TimeInterval = 15

    private static let log = Logger(subsystem: "app.bristlenose", category: "availability")

    private final class State: @unchecked Sendable {
        let lock = NSLock()
        var stalledAt: [String: Date] = [:]
        var inFlight: Set<String> = []
    }
    private final class Box: @unchecked Sendable {
        var value = false
    }
    private static let state = State()

    static func exists(
        atPath path: String,
        timeout: TimeInterval = BoundedFileCheck.timeout,
        retryAfter: TimeInterval = BoundedFileCheck.retryAfter,
        now: () -> Date = Date.init,
        probe: @escaping @Sendable (String) -> Bool = { FileManager.default.fileExists(atPath: $0) }
    ) -> Bool {
        guard path.hasPrefix("/Volumes/") else { return probe(path) }

        state.lock.lock()
        if let at = state.stalledAt[path], now().timeIntervalSince(at) < retryAfter {
            state.lock.unlock()
            return false
        }
        if state.inFlight.contains(path) {
            // An earlier probe of this path is still stuck in the kernel; do not park another.
            state.lock.unlock()
            return false
        }
        state.stalledAt[path] = nil
        state.inFlight.insert(path)
        state.lock.unlock()

        let box = Box()
        let done = DispatchSemaphore(value: 0)
        // A thread of its own, not the shared background queue: that pool can be starved (the app has
        // had pool-starvation incidents), and a stat that merely waited for a free worker would read as
        // a stalled share and show a healthy study as unreachable.
        let prober = Thread {
            box.value = probe(path)
            state.lock.lock()
            state.inFlight.remove(path)
            state.lock.unlock()
            done.signal()
        }
        prober.name = "bristlenose.bounded-stat"
        prober.qualityOfService = .userInitiated
        prober.start()
        if done.wait(timeout: .now() + timeout) == .timedOut {
            state.lock.lock()
            state.stalledAt[path] = now()
            state.lock.unlock()
            log.info("a stat did not answer within \(timeout, privacy: .public)s; treating the path as unreachable")
            return false
        }
        return box.value
    }
}
