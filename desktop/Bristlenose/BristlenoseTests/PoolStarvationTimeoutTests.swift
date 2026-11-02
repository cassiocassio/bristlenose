import Dispatch
import Foundation
import Testing
@testable import Bristlenose

/// N36 — the timeout that guards a manifest read on a dead network mount is a
/// `Task.sleep` on the same cooperative pool as the reads it guards. A read that
/// never returns holds a pool thread for good (a thread blocked in the kernel
/// ignores cancellation), so once as many reads are stuck as the pool has
/// threads, nothing can run the wake-up that would give up on them.
///
/// The stuck read is a semaphore wait inside the injected `read`, which holds a
/// pool thread exactly as `parseManifest`'s synchronous `fileExists` does on a
/// dead mount. Nothing touches a real share.
///
/// The measurement runs on a thread of its own (`offThePool`) and the test
/// body suspends meanwhile, holding no pool thread. It was a synchronous body
/// until 2 Nov 2026, measuring "from outside the pool" — but Swift Testing
/// calls a synchronous test from an async context, so the body's own waits
/// held a pool thread too: on the 3-core macos-26 runner the control's "1 of
/// 3 stuck" was 2 of 3, and the one thread left did not run the 0.3 s timer
/// in 3 s (both of Xcode 26.6's cloned test hosts, mac-build 3bfbe1f28). The
/// resume needs a pool thread, which the clean-up inside `timeoutFires` frees
/// before it returns. Serialized: the two tests below saturate the same
/// shared pool, and run side by side the control would borrow the other's
/// verdict.
@Suite("Timed reads on a saturated pool", .serialized)
struct PoolStarvationTimeoutTests {

    /// A blocking wait from synchronous code, off the async-context diagnostic.
    private static func block(_ gate: DispatchSemaphore) { gate.wait() }

    /// Run a blocking measurement on a dedicated thread, never a pool thread,
    /// with the caller suspended rather than waiting.
    private static func offThePool<T: Sendable>(_ body: @escaping @Sendable () -> T) async -> T {
        await withCheckedContinuation { (done: CheckedContinuation<T, Never>) in
            Thread.detachNewThread { done.resume(returning: body()) }
        }
    }

    /// How many detached tasks the pool actually ran at once: `cores + 4` are
    /// started, each blocks until counted, and the count is taken after 0.5 s.
    /// For the failure message — the arithmetic above assumes one thread per
    /// core, and a red on a runner is the moment to know whether that held.
    private static func measuredPoolWidth(cores: Int) -> Int {
        let total = cores + 4
        let gate = DispatchSemaphore(value: 0)
        let running = DispatchSemaphore(value: 0)
        let finished = DispatchSemaphore(value: 0)
        for _ in 0..<total {
            Task.detached {
                running.signal()
                Self.block(gate)
                finished.signal()
            }
        }
        Thread.sleep(forTimeInterval: 0.5)
        var width = 0
        while running.wait(timeout: .now()) == .success { width += 1 }
        // Free every task, those not yet started included, and wait for them
        // all: nothing of this measurement may outlive it in the pool.
        for _ in 0..<total { gate.signal() }
        for _ in 0..<total { _ = finished.wait(timeout: .now() + 5) }
        return width
    }

    /// One read under a 0.3 s timeout that never returns, then `blockers` more
    /// stuck reads. True if the 0.3 s timeout fired within 3 s.
    private static func timeoutFires(amongStuckReads blockers: Int) -> Bool {
        let deadMount = DispatchSemaphore(value: 0)
        let started = DispatchSemaphore(value: 0)
        let returned = DispatchSemaphore(value: 0)
        let url = URL(fileURLWithPath: "/tmp/bn-n36/bristlenose-output/.bristlenose/pipeline-manifest.json")

        // The read under test: its own timeout is 0.3 s, and it never returns.
        Task.detached {
            _ = await PipelineRunner.readManifestState(
                at: url, timeout: .milliseconds(300),
                read: { _ in
                    started.signal()
                    Self.block(deadMount)
                    return .idle
                }
            )
            returned.signal()
        }
        #expect(started.wait(timeout: .now() + 5) == .success, "the read under test never started")

        // Other studies on the same dead mount: one stuck read each.
        for _ in 0..<blockers {
            Task.detached { Self.block(deadMount) }
        }
        Thread.sleep(forTimeInterval: 0.5)  // let them take the pool

        let gaveUp = returned.wait(timeout: .now() + 3)

        // Clean up first, whatever the verdict: free every stuck thread.
        for _ in 0..<(blockers + 8) { deadMount.signal() }
        // The read under test has returned once it gave up; otherwise wait for it.
        if gaveUp != .success { _ = returned.wait(timeout: .now() + 10) }
        return gaveUp == .success
    }

    /// Control: a few stuck reads leave threads free, and the timeout fires.
    /// "Few" is relative to the pool, which is one thread per core: the GitHub
    /// macOS runners have 3, so a fixed 2 blockers plus the read under test
    /// saturated it there and the control failed as the known issue does
    /// (1 Nov 2026). At most half the pool is held here, counting that read.
    @Test func aTimedReadGivesUpWhenOnlyAFewReadsAreStuck() async {
        let cores = ProcessInfo.processInfo.activeProcessorCount
        let blockers = max(0, cores / 2 - 1)
        let fired = await Self.offThePool { Self.timeoutFires(amongStuckReads: blockers) }
        // Measured only on a red, off the pool like the test itself.
        var width = cores
        if !fired { width = await Self.offThePool { Self.measuredPoolWidth(cores: cores) } }
        #expect(fired,
                "a 0.3 s timeout had not fired after 3 s with \(blockers + 1) of \(cores) pool threads stuck; the pool ran \(width) detached tasks at once")
    }

    @Test func aTimedReadStillGivesUpWhileDeadReadsHoldEveryPoolThread() async {
        let cores = ProcessInfo.processInfo.activeProcessorCount
        let fired = await Self.offThePool { Self.timeoutFires(amongStuckReads: cores + 4) }
        withKnownIssue("N36: the timeout's wake-up needs a pool thread, and every one is held") {
            #expect(fired, "a 0.3 s timeout had not fired after 3 s")
        }
    }
}
