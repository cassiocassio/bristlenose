import Foundation
import Testing
@testable import Bristlenose

/// R40: the "Out of credit" pill stayed lit after a top-up and a successful
/// run, because its verdict was sticky and nothing re-validated it.
@MainActor
@Suite("OutOfCreditModel")
struct OutOfCreditModelTests {

    private let key = "sk-ant-test-key-1234567890"

    /// Same isolation as `LLMValidatorTests`: a private verdict store per test.
    private func withIsolatedStore(_ body: () -> Void) {
        let suiteName = "OutOfCreditModelTests-\(UUID().uuidString)"
        let suite = UserDefaults(suiteName: suiteName)!
        let original = LLMValidator.verdictStore
        LLMValidator.verdictStore = suite
        defer {
            LLMValidator.verdictStore = original
            suite.removePersistentDomain(forName: suiteName)
        }
        body()
    }

    @Test func aSuccessfulRunClearsOutOfCredit() {
        withIsolatedStore {
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .outOfCredit)

            #expect(OutOfCreditModel.clearAfterSuccessfulRun(provider: .claude, key: key))
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == nil,
                    "the pill's verdict survived a run that worked")
        }
    }

    /// A run that finished proves credit, not a valid key: leave `.invalid`.
    @Test func aSuccessfulRunLeavesOtherVerdictsAlone() {
        withIsolatedStore {
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .invalid)
            #expect(!OutOfCreditModel.clearAfterSuccessfulRun(provider: .claude, key: key))
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == .invalid)
        }
    }

    @Test func onlyAFinishedAnalysisCounts() {
        let id = UUID()
        func succeeded(_ from: PipelineState?, _ to: PipelineState) -> Bool {
            OutOfCreditModel.aRunSucceeded(old: from.map { [id: $0] } ?? [:], new: [id: to])
        }
        #expect(succeeded(.running, .ready(Date())))
        // Stopped, failed and partial runs prove nothing about credit.
        #expect(!succeeded(.running, .stopped(stagesComplete: [])))
        #expect(!succeeded(.running, .failed(.passthrough("402"), category: .outOfCredit)))
        #expect(!succeeded(.running, .partial(kind: "transcribe-only", stagesComplete: [])))
        // A passive manifest read of an analysed study is not a run.
        #expect(!succeeded(.scanning, .ready(Date())))
        #expect(!succeeded(nil, .ready(Date())))
    }
}
