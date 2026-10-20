import Darwin
import Testing
@testable import Bristlenose

/// Stop's SIGKILL waits out Python's hosted backstop, which is what records
/// the stop. SIGKILL writes no terminus, so a ladder that killed at +8 s left a
/// run still unwinding reading "Analysis stopped unexpectedly", and the next
/// run recorded the researcher's Stop as a failure (R20 follow-up, 20 Oct 2026).
/// `tests/test_swift_python_contract.py` pins the two mirrors to Python's
/// values; this pins the ladder to the mirrors.
@Suite("Stop ladder")
struct StopLadderTests {
    @Test func sigkillIsTheLastStepAndComesAfterTheBackstopCouldWrite() {
        let ladder = PipelineRunner.cancelLadder
        #expect(ladder.last?.signal == SIGKILL)
        // The FIRST SIGKILL: a ladder with an early one would kill before the backstop.
        let firstKill = ladder.firstIndex { $0.signal == SIGKILL } ?? ladder.endIndex - 1
        let killAt = ladder[...firstKill].reduce(Duration.zero) { $0 + $1.after }
        let latestWrite = PipelineRunner.pythonHostedStopGrace + PipelineRunner.pythonBackstopLockWait
        #expect(killAt > latestWrite)
    }
}
