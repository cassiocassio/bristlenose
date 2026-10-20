import Testing
@testable import Bristlenose

/// R31: the first launch of the bundled sidecar on a new Mac can take longer
/// than 15 s before it prints its port, and the old flat 15 s timer failed it.
/// Each test feeds the policy a scripted sequence of what the watchdog would
/// see, one look per second, and asserts the first verdict that ends the watch.
@Suite("ServeStartPolicy")
struct ServeStartPolicyTests {

    private typealias Look = ServeStartPolicy.Observation

    /// The first verdict that is not `.keepWaiting`, with the second it came at.
    private func firstDecision(_ looks: [Look]) -> (ServeStartPolicy.Verdict, Int)? {
        for look in looks {
            let verdict = ServeStartPolicy.verdict(for: look)
            if verdict != .keepWaiting {
                return (verdict, Int(look.elapsed.components.seconds))
            }
        }
        return nil
    }

    private func looks(seconds: ClosedRange<Int>,
                       starting: (Int) -> Bool = { _ in true },
                       alive: (Int) -> Bool = { _ in true }) -> [Look] {
        seconds.map { s in
            Look(elapsed: .seconds(s), stillStarting: starting(s), processAlive: alive(s))
        }
    }

    /// Scenario 1: alive and slow, the cold first launch. It must not fail at
    /// 15 s, or at any point while it is alive and under the ceiling.
    @Test func aliveAndSlowIsNotFailedAt15Seconds() {
        let sequence = looks(seconds: 1...60)
        #expect(firstDecision(sequence) == nil)
    }

    /// Scenario 4: port parsed late. The serve leaves `.starting` at 40 s and
    /// the watchdog stands down instead of failing it.
    @Test func portParsedLateSettles() {
        let sequence = looks(seconds: 1...120, starting: { $0 < 40 })
        let decision = firstDecision(sequence)
        #expect(decision?.0 == .settled)
        #expect(decision?.1 == 40)
    }

    /// Scenario 3: exits early. The watchdog writes no timeout and leaves the
    /// message to `handleTermination`, which knows the exit status; its report
    /// lands a look later and settles the watch.
    @Test func exitsEarlyIsLeftToTheTerminationHandler() {
        let sequence = looks(seconds: 1...120, starting: { $0 < 4 }, alive: { $0 < 3 })
        let verdicts = sequence.map { ServeStartPolicy.verdict(for: $0) }
        #expect(verdicts[2] == .processExited)
        #expect(verdicts[3] == .settled)
        #expect(!verdicts.contains(.timedOut))
    }

    /// If an exit is never reported, the boot still fails at the ceiling
    /// rather than showing the progress bar forever.
    @Test func unreportedExitStillFailsAtTheCeiling() {
        let sequence = looks(seconds: 1...120, alive: { $0 < 3 })
        let firstTimeout = sequence.first { ServeStartPolicy.verdict(for: $0) == .timedOut }
        #expect(firstTimeout?.elapsed == ServeStartPolicy.ceiling)
    }

    /// Scenario 5: alive and never ready. It still fails, at the ceiling and
    /// not before.
    @Test func aliveAndWedgedFailsAtTheCeiling() {
        let sequence = looks(seconds: 1...120)
        let decision = firstDecision(sequence)
        #expect(decision?.0 == .timedOut)
        #expect(decision?.1 == Int(ServeStartPolicy.ceiling.components.seconds))
    }

    /// The failure copy names the ceiling as a literal number; keep the
    /// English fallback (and so the locales beside it) in step.
    @Test func timeoutCopyNamesTheCeiling() {
        let seconds = String(ServeStartPolicy.ceiling.components.seconds)
        let english = FailureMessage.englishSentence(for: "desktop.boot.failure.startTimeout", vars: [:])
        #expect(english.contains(seconds))
    }
}
