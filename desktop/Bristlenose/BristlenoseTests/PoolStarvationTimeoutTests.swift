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
/// The test body is synchronous and measures from outside the pool: an async
/// body would need a pool thread to resume on, and would hang with the thing
/// under test. Serialized: the two tests below saturate the same shared pool,
/// and run side by side the control would borrow the other's verdict.
@Suite("Timed reads on a saturated pool", .serialized)
struct PoolStarvationTimeoutTests {

    /// A blocking wait from synchronous code, off the async-context diagnostic.
    private static func block(_ gate: DispatchSemaphore) { gate.wait() }

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
    @Test func aTimedReadGivesUpWhenOnlyAFewReadsAreStuck() {
        #expect(Self.timeoutFires(amongStuckReads: 2), "a 0.3 s timeout had not fired after 3 s")
    }

    @Test func aTimedReadStillGivesUpWhileDeadReadsHoldEveryPoolThread() {
        let cores = ProcessInfo.processInfo.activeProcessorCount
        let fired = Self.timeoutFires(amongStuckReads: cores + 4)
        withKnownIssue("N36: the timeout's wake-up needs a pool thread, and every one is held") {
            #expect(fired, "a 0.3 s timeout had not fired after 3 s")
        }
    }
}
