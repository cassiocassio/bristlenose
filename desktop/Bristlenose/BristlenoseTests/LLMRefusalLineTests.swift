import Foundation
import Testing

@testable import Bristlenose

/// The sidecar's refusal line (`bristlenose/llm/refusal_report.py`) and what the host does
/// with it. The line is the pill's only feed for a call the sidecar made on its own.
@MainActor
@Suite struct LLMRefusalLineTests {
    private func line(_ json: String) -> String { LLMRefusalLine.prefix + json }

    @Test func aCreditRefusalParses() throws {
        let r = try #require(LLMRefusalLine.fromLine(line(
            #"{"v":1,"kind":"out_of_credit","provider":"anthropic","http_status":400,"phase":"http","provider_signature":true,"error_class":"BadRequestError"}"#)))
        #expect(r.condition == .outOfCredit)
        #expect(r.llmProvider == .claude)
        #expect(r.httpStatus == 400 && r.providerSignature == true && r.phase == "http")
    }

    @Test func anUnknownKindOrPhaseDegradesInsteadOfDroppingTheLine() throws {
        let r = try #require(LLMRefusalLine.fromLine(line(
            #"{"v":1,"kind":"something_new","provider":"anthropic","phase":"warp","future_field":1}"#)))
        #expect(r.condition == nil, "not acted on, but still read")
    }

    @Test func aLineThatIsNotOursIsNotOurs() {
        #expect(LLMRefusalLine.disposition(of: "[bristlenose] auth-token: abc") == .notOurs)
        #expect(LLMRefusalLine.disposition(of: "Report: http://127.0.0.1:1/report/") == .notOurs)
    }

    @Test func aPrefixedLineThatCannotBeReadIsConsumedNotPassedOn() {
        // Ours and unreadable is `malformed`, which the host drops and logs; it must never
        // fall through to the output buffer.
        #expect(LLMRefusalLine.disposition(of: line("not json")) == .malformed)
        #expect(LLMRefusalLine.disposition(of: line(#"{"kind":"invalid_key"}"#)) == .malformed, "no provider")
        #expect(LLMRefusalLine.disposition(of: line(#"{"kind":"invalid_key","provider":"anthropic","http_status":"401"}"#)) == .malformed, "a status that is a string")
        let long = line(#"{"kind":"invalid_key","provider":"anthropic","pad":""# + String(repeating: "x", count: 3000) + #""}"#)
        #expect(LLMRefusalLine.disposition(of: long) == .malformed, "longer than the writer ever sends")
        #expect(LLMRefusalLine.fromLine(line("not json")) == nil)
    }

    @Test func aLaterSchemaVersionIsNotActedOnAsIfItWereThisOne() {
        #expect(LLMRefusalLine.disposition(of: line(#"{"v":2,"kind":"invalid_key","provider":"anthropic"}"#)) == .malformed)
        #expect(LLMRefusalLine.fromLine(line(#"{"v":1,"kind":"invalid_key","provider":"anthropic"}"#)) != nil)
    }

    @Test func aRefusalLineIsNeverDisplayableOutput() {
        let l = line(#"{"v":1,"kind":"invalid_key","provider":"anthropic"}"#)
        #expect(ServeManager.displayableLine(l) == nil)
        #expect(ServeManager.displayableLine("Report: http://127.0.0.1:1/report/") != nil)
    }

    @Test func aRateLimitAndAnOutageAreNotForThePill() throws {
        for kind in ["rate_limited", "server_error", "network", "unknown", "bad_request"] {
            let r = try #require(LLMRefusalLine.fromLine(line(
                #"{"kind":"\#(kind)","provider":"openai"}"#)))
            #expect(r.condition == nil, "\(kind)")
        }
    }

    // MARK: the host's side

    private func manager(spawnedWith keys: [String: String]) -> (ServeManager, Recorded) {
        let m = ServeManager(resolvedMode: .success(.external(port: 1)))
        let rec = Recorded()
        m.llmRefusalRecorder = { rec.calls.append(($0, $1, $2)) }
        m.instance.spawnedKeyFingerprints = ServeManager.keyFingerprints(in: keys)
        return (m, rec)
    }

    final class Recorded { var calls: [(ProviderProblemCondition, LLMProvider, String?)] = [] }

    @Test func aRefusalIsRecordedAgainstTheKeyTheSidecarWasGiven() throws {
        let (m, rec) = manager(spawnedWith: ["BRISTLENOSE_ANTHROPIC_API_KEY": "sk-ant-one"])
        m.noteLLMRefusal(try #require(LLMRefusalLine.fromLine(line(
            #"{"kind":"invalid_key","provider":"anthropic"}"#))))
        #expect(rec.calls.count == 1)
        #expect(rec.calls.first?.0 == .keyRejected)
        #expect(rec.calls.first?.1 == .claude)
        #expect(rec.calls.first?.2 == LLMValidator.keyFingerprint("sk-ant-one"))
    }

    @Test func aRefusalForAProviderThisSidecarHoldsNoKeyForIsDropped() throws {
        let (m, rec) = manager(spawnedWith: ["BRISTLENOSE_ANTHROPIC_API_KEY": "sk-ant-one"])
        m.noteLLMRefusal(try #require(LLMRefusalLine.fromLine(line(
            #"{"kind":"out_of_credit","provider":"openai"}"#))))
        #expect(rec.calls.isEmpty, "nothing says it is the key in force")
    }

    @Test func aRefusalThatIsNotForThePillIsNotRecorded() throws {
        let (m, rec) = manager(spawnedWith: ["BRISTLENOSE_ANTHROPIC_API_KEY": "k"])
        m.noteLLMRefusal(try #require(LLMRefusalLine.fromLine(line(
            #"{"kind":"rate_limited","provider":"anthropic"}"#))))
        #expect(rec.calls.isEmpty)
    }

    @Test func keyFingerprintsAreHashesOfOnlyTheCloudKeysPresent() {
        let f = ServeManager.keyFingerprints(in: [
            "BRISTLENOSE_ANTHROPIC_API_KEY": "a", "BRISTLENOSE_GOOGLE_API_KEY": "",
            "BRISTLENOSE_LLM_MODEL": "x",
        ])
        #expect(f.keys.sorted() == ["anthropic"])
        #expect(f["anthropic"] == LLMValidator.keyFingerprint("a"))
        #expect(f["anthropic"] != "a", "a hash, never the key")
    }
}
