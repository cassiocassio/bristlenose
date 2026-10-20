import Testing
@testable import Bristlenose

/// R34: a setting that restarts the serve commits at a gesture's end and only
/// when it changed — never per slider step, never for a Tab through a field.
@Suite("CommitGate")
struct CommitGateTests {

    @Test func aSettledValueCommittedUnchanged_isNotAChange() {
        var gate = CommitGate<Int>()
        gate.settle(3)

        let changed = gate.commit(3)

        #expect(changed == false)
    }

    /// The same commit is wired to blur, Return, pane leave and window close,
    /// so the first exit after an edit posts and every later one does nothing.
    @Test func onlyTheFirstExitAfterAnEditIsAChange() {
        var gate = CommitGate<String>()
        gate.settle("https://old.openai.azure.com")

        let first = gate.commit("https://new.openai.azure.com")
        let second = gate.commit("https://new.openai.azure.com")
        let third = gate.commit("https://new.openai.azure.com")

        #expect(first)
        #expect(second == false)
        #expect(third == false)
    }

    /// The pane appears again on every Settings tab switch; a second settle
    /// must not swallow the edit made before it.
    @Test func settlingAgain_doesNotSwallowAnUncommittedEdit() {
        var gate = CommitGate<Int>()
        gate.settle(3)
        gate.settle(7)

        let changed = gate.commit(7)

        #expect(changed)
    }

    /// Nothing settled (a commit before the pane appeared): post rather than
    /// drop a change.
    @Test func withNothingSettled_anyValueIsAChange() {
        var gate = CommitGate<Int>()

        let changed = gate.commit(3)

        #expect(changed)
    }
}
