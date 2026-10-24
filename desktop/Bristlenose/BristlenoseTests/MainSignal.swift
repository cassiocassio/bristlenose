import Foundation

/// A one-shot signal for a test whose fake runs on the main queue (a loopback `NWListener`
/// started with `.main`). `wait()` returns once `fire()` has been called, before or after,
/// or once the waiting task is cancelled.
///
/// The cancel is the point: a test's `.timeLimit` cancels the test and then waits for it to
/// finish, and a bare `withCheckedContinuation` never sees the cancel, so the wait would
/// outlive the limit. Waking on cancel lets the `#require` after the wait say what never
/// happened. Polling against `Date()` is what this replaces: a full suite keeps the main queue
/// busy for seconds, and the clock ran out before the fake had been reached (24 Oct 2026).
@MainActor
final class MainSignal {
    private(set) var fired = false
    private var waiters: [UUID: CheckedContinuation<Void, Never>] = [:]

    nonisolated init() {}

    func fire() {
        fired = true
        let all = waiters.values
        waiters = [:]
        all.forEach { $0.resume() }
    }

    func wait() async {
        if fired { return }
        let id = UUID()
        await withTaskCancellationHandler {
            await withCheckedContinuation { (c: CheckedContinuation<Void, Never>) in
                // Synchronous on the main actor, so nothing fires between this check and the store.
                if fired || Task.isCancelled { c.resume() } else { waiters[id] = c }
            }
        } onCancel: {
            // Only the stored continuation is resumed here, and only once: `fire()` and this
            // both run on the main actor, and each removes what it resumes.
            Task { @MainActor in self.waiters.removeValue(forKey: id)?.resume() }
        }
    }
}
