import Foundation
import Testing
@testable import Bristlenose

/// R59 and R60 (owner go, 9 Nov 2026): a stat on a share that has stopped answering must not hold the
/// caller. These drive the check with a probe that never returns. A real stalled share could not be
/// staged on this Mac, so what is pinned is the behaviour around the stat, not the kernel's.
struct BoundedFileCheckTests {
    private func volumePath() -> String { "/Volumes/bn-test-\(UUID().uuidString)/study" }

    /// Counts how many times the probe was entered, from any thread.
    private final class Counter: @unchecked Sendable {
        private let lock = NSLock()
        private var n = 0
        func bump() { lock.lock(); n += 1; lock.unlock() }
        var count: Int { lock.lock(); defer { lock.unlock() }; return n }
    }

    @Test("A path outside /Volumes uses the direct call and is never bounded")
    func localPathIsDirect() {
        let counter = Counter()
        let result = BoundedFileCheck.exists(atPath: "/Users/nobody/study", probe: { _ in counter.bump(); return true })
        #expect(result)
        #expect(counter.count == 1)
    }

    @Test("A normal stat under /Volumes answers true and false as it is")
    func normalAnswers() {
        #expect(BoundedFileCheck.exists(atPath: volumePath(), probe: { _ in true }))
        #expect(!BoundedFileCheck.exists(atPath: volumePath(), probe: { _ in false }))
    }

    @Test("A genuine 'no' is not remembered as a stall: the same path answers true as soon as it exists")
    func noIsNotAStall() {
        let path = volumePath()
        #expect(!BoundedFileCheck.exists(atPath: path, probe: { _ in false }))
        #expect(BoundedFileCheck.exists(atPath: path, probe: { _ in true }))
    }

    @Test("A stat that never returns does not block the caller, and says no")
    func aHungStatDoesNotBlock() {
        let release = DispatchSemaphore(value: 0)
        defer { release.signal() }
        let start = Date()
        let result = BoundedFileCheck.exists(atPath: volumePath(), timeout: 0.1, probe: { _ in
            release.wait()
            return true
        })
        #expect(!result)
        #expect(Date().timeIntervalSince(start) < 1.0, "the caller waited for the stat instead of the timeout")
    }

    @Test("A stalled path is answered at once afterwards, with no second probe parked")
    func aStalledPathCostsOneWait() {
        let path = volumePath()
        let release = DispatchSemaphore(value: 0)
        defer { release.signal() }
        let counter = Counter()
        let probe: @Sendable (String) -> Bool = { _ in counter.bump(); release.wait(); return true }

        _ = BoundedFileCheck.exists(atPath: path, timeout: 0.1, probe: probe)
        // Under load the background queue can be slow to start the first probe; wait until it is
        // really running (and stuck) before asking whether a second one gets parked behind it.
        for _ in 0..<200 where counter.count == 0 { Thread.sleep(forTimeInterval: 0.01) }
        #expect(counter.count == 1, "the first probe never started")
        let start = Date()
        let again = BoundedFileCheck.exists(atPath: path, timeout: 0.1, probe: probe)
        #expect(!again)
        #expect(Date().timeIntervalSince(start) < 0.05, "the second call waited again")
        Thread.sleep(forTimeInterval: 0.05)
        #expect(counter.count == 1, "a second probe was parked on a path that is still stuck")
    }

    @Test("After the retry interval a stalled path is tried again, and answers true once the share is back")
    func aStalledPathIsRetried() async {
        let path = volumePath()
        let release = DispatchSemaphore(value: 0)
        _ = BoundedFileCheck.exists(atPath: path, timeout: 0.05, retryAfter: 0.2, probe: { _ in
            release.wait()
            return true
        })
        release.signal()                                  // the share comes back; the parked probe returns
        try? await Task.sleep(for: .milliseconds(400))    // past retryAfter, and the parked probe has finished
        #expect(BoundedFileCheck.exists(atPath: path, timeout: 0.5, retryAfter: 0.2, probe: { _ in true }))
    }
}
